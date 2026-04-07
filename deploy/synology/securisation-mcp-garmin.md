# Sécurisation des MCP Garmin — Documentation technique

**Date :** Février 2026  
**Auteur :** Pierre (Hypnosos)  
**NAS :** Synology DS224+  
**Domaines exposés :** `mcp.hypnosos.fr` · `workouts.hypnosos.fr`

---

## 1. Architecture générale

```
Internet (Claude.ai / autres clients)
        ↓ HTTPS
Synology Reverse Proxy (SSL termination)
        ↓ HTTP interne
garmin-mcp:8787          workouts-mcp:8001
(python:3.12-slim)       (image buildée locale)
FastMCP + uvicorn        FastMCP + uvicorn
garth / secrets          garth / tokens OAuth
```

### Conteneurs actifs

| Conteneur | Image | Port | Compose |
|---|---|---|---|
| `garmin-mcp` | `python:3.12-slim` | 8787 | `/volume1/docker/garmin-mcp/` |
| `workouts-mcp` | `garmin-workouts-mcp-workouts-mcp` | 8001 | `/volume1/docker/garmin-workouts-mcp/` |

---

## 2. Stratégie de sécurité retenue

### Contraintes initiales

- Le **Synology Reverse Proxy natif (DSM)** ne supporte pas la validation de token Bearer sur les headers entrants — il ne peut pas bloquer conditionnellement selon `Authorization`.
- Les MCP utilisent le protocole **SSE (Server-Sent Events)** : connexions HTTP persistantes. Tout middleware d'authentification doit valider à l'établissement de la connexion, pas sur chaque requête.
- L'interface Claude.ai ne permet pas d'injecter des headers personnalisés dans les connecteurs MCP (uniquement OAuth dans l'UI actuelle).

### Solution adoptée : middleware ASGI Bearer + query param

Authentification intégrée directement dans chaque serveur Python via un middleware Starlette `BaseHTTPMiddleware`. Le token est accepté de deux façons :

1. **Header** `Authorization: Bearer <TOKEN>` — pour les clients qui le supportent
2. **Query parameter** `?token=<TOKEN>` — pour Claude.ai qui ne supporte pas les headers custom

```python
class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not API_TOKEN:
            return JSONResponse({"error": "API_TOKEN not configured"}, status_code=500)
        auth_header = request.headers.get("Authorization", "")
        auth_query = request.query_params.get("token", "")
        if auth_header != f"Bearer {API_TOKEN}" and auth_query != API_TOKEN:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)
```

### Token

Généré avec `openssl rand -hex 32`. Stocké en variable d'environnement `API_TOKEN` dans chaque `docker-compose.yml`.

> ⚠️ **Note SSE critique** : si un proxy nginx est ajouté en amont, les directives `proxy_buffering off`, `proxy_cache off` et `proxy_read_timeout 3600s` sont obligatoires pour que les événements SSE passent correctement.

---

## 3. Fichiers modifiés

### 3.1 `garmin-mcp` — `/volume1/docker/garmin-mcp/app/server.py`

Code complet du serveur avec middleware intégré :

```python
import os
from datetime import date, timedelta
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

GARTH_HOME = os.getenv("GARTH_HOME", "/secrets/garth")
API_TOKEN = os.getenv("API_TOKEN", "")

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not API_TOKEN:
            return JSONResponse({"error": "API_TOKEN not configured"}, status_code=500)
        auth_header = request.headers.get("Authorization", "")
        auth_query = request.query_params.get("token", "")
        if auth_header != f"Bearer {API_TOKEN}" and auth_query != API_TOKEN:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

mcp = FastMCP("Garmin MCP (garth)")

def get_garth():
    import garth
    os.makedirs(GARTH_HOME, exist_ok=True)
    try:
        garth.resume(GARTH_HOME)
        return garth, True, None
    except Exception as e:
        return garth, False, str(e)

@mcp.tool
def garmin_status():
    """Vérifie si la session Garmin est valide."""
    _, ok, err = get_garth()
    return {"logged_in": ok, "garth_home": GARTH_HOME, "error": err}

@mcp.tool
def activities(from_days_ago: int = 7, limit: int = 20):
    """Liste les activités Garmin récentes."""
    garth, ok, err = get_garth()
    if not ok:
        return {"error": "Not logged in", "details": err}
    start_date = (date.today() - timedelta(days=from_days_ago)).isoformat()
    path = (
        f"/activitylist-service/activities/search/activities"
        f"?start=0&limit={limit}&startDate={start_date}"
    )
    try:
        data = garth.connectapi(path)
        return {"from": start_date, "limit": limit, "activities": data}
    except Exception as e:
        return {"error": str(e), "path": path}

@mcp.tool
def daily_summary(day: str = ""):
    """Résumé santé quotidien (HRV, body battery, sommeil)."""
    garth, ok, err = get_garth()
    if not ok:
        return {"error": "Not logged in", "details": err}
    target_date = date.fromisoformat(day) if day else date.today()
    iso = target_date.isoformat()
    result = {"date": iso, "data": {}}
    def safe_call(key, endpoint):
        try:
            result["data"][key] = garth.connectapi(endpoint)
        except Exception as e:
            result["data"][f"{key}_error"] = str(e)
    safe_call("hrv", f"/hrv-service/hrv/{iso}")
    safe_call("body_battery", f"/wellness-service/wellness/dailyBodyBattery/{iso}")
    safe_call("sleep", f"/wellness-service/wellness/dailySleepData/{iso}")
    return result

app = mcp.http_app(path="/")
app.add_middleware(BearerAuthMiddleware)
```

### 3.2 `garmin-mcp` — `/volume1/docker/garmin-mcp/docker-compose.yml`

```yaml
version: "3.9"
services:
  garmin-mcp:
    image: python:3.12-slim
    container_name: garmin-mcp
    working_dir: /app
    volumes:
      - ./app:/app
      - ./data:/data
      - ./secrets:/secrets
    environment:
      GARTH_HOME: /secrets/garth
      API_TOKEN: "<TOKEN>"
    ports:
      - "8787:8787"
    command: >
      bash -lc "
      pip install --no-cache-dir --disable-pip-version-check fastmcp garth uvicorn &&
      uvicorn server:app --host 0.0.0.0 --port 8787
      "
    restart: unless-stopped
```

> Le service `cloudflared` a été supprimé (tunnel inutilisé).

### 3.3 `workouts-mcp` — `/volume1/docker/garmin-workouts-mcp/start.py`

```python
import os
from garmin_workouts_mcp.main import mcp
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

API_TOKEN = os.getenv("API_TOKEN", "")

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not API_TOKEN:
            return JSONResponse({"error": "API_TOKEN not configured"}, status_code=500)
        auth_header = request.headers.get("Authorization", "")
        auth_query = request.query_params.get("token", "")
        if auth_header != f"Bearer {API_TOKEN}" and auth_query != API_TOKEN:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

transport = os.getenv("MCP_TRANSPORT", "http")
host = os.getenv("MCP_HOST", "0.0.0.0")
port = int(os.getenv("MCP_PORT", "8001"))
path = os.getenv("MCP_PATH", "/")

app = mcp.http_app(path=path)
app.add_middleware(BearerAuthMiddleware)
uvicorn.run(app, host=host, port=port)
```

### 3.4 `workouts-mcp` — `/volume1/docker/garmin-workouts-mcp/docker-compose.yml`

```yaml
services:
  workouts-mcp:
    build: .
    container_name: workouts-mcp
    environment:
      - GARTH_HOME=/garth
      - MCP_TRANSPORT=http
      - MCP_HOST=0.0.0.0
      - MCP_PORT=8001
      - MCP_PATH=/
      - API_TOKEN=<TOKEN>
    volumes:
      - ./garth:/garth
    ports:
      - "8001:8001"
    restart: unless-stopped
```

---

## 4. Configuration Claude.ai

Dans **Settings → Connectors**, chaque connecteur MCP est configuré avec l'URL incluant le token en query param :

```
https://mcp.hypnosos.fr/?token=<TOKEN>
https://workouts.hypnosos.fr/?token=<TOKEN>
```

---

## 5. Procédures de maintenance

### 5.1 Mise à jour du code de `garmin-mcp`

`garmin-mcp` installe ses dépendances **au démarrage du conteneur** via pip (pas de build Docker). La mise à jour du code Python ne nécessite pas de rebuild :

```bash
# Modifier server.py directement
nano /volume1/docker/garmin-mcp/app/server.py

# Redémarrer le conteneur (pip réinstalle tout au démarrage)
cd /volume1/docker/garmin-mcp && sudo docker compose down && sudo docker compose up -d

# Suivre le démarrage (~2-3 min le temps que pip installe)
sudo docker logs garmin-mcp --tail 20 -f
```

### 5.2 Mise à jour du code de `workouts-mcp`

`workouts-mcp` utilise une image buildée. Toute modification de `start.py` nécessite un rebuild :

```bash
# Modifier start.py
nano /volume1/docker/garmin-workouts-mcp/start.py

# Rebuild et redémarrage
cd /volume1/docker/garmin-workouts-mcp && sudo docker compose up -d --build

# Vérification
sudo docker logs workouts-mcp --tail 20
```

### 5.3 Mise à jour du package `garmin-workouts-mcp` (upstream GitHub)

Le package est installé via pip dans l'image Docker. Pour mettre à jour vers une nouvelle version :

```bash
# Modifier le Dockerfile pour forcer la mise à jour
# Changer : pip install garmin-workouts-mcp
# En :      pip install --upgrade garmin-workouts-mcp

cd /volume1/docker/garmin-workouts-mcp
sudo docker compose build --no-cache
sudo docker compose up -d
```

### 5.4 Rotation du token

```bash
# Générer un nouveau token
openssl rand -hex 32

# Mettre à jour les deux compose files
nano /volume1/docker/garmin-mcp/docker-compose.yml      # modifier API_TOKEN
nano /volume1/docker/garmin-workouts-mcp/docker-compose.yml  # modifier API_TOKEN

# Redémarrer les deux conteneurs
cd /volume1/docker/garmin-mcp && sudo docker compose up -d
cd /volume1/docker/garmin-workouts-mcp && sudo docker compose up -d --build

# Mettre à jour les URLs dans Claude.ai Settings → Connectors
```

### 5.5 Vérification de l'authentification

```bash
# Sans token → doit retourner {"error":"Unauthorized"}
curl -s http://localhost:8787/ | head -c 100
curl -s http://localhost:8001/ | head -c 100

# Avec token → doit retourner une réponse MCP (erreur SSE normale depuis curl)
curl -s "http://localhost:8787/?token=<TOKEN>" | head -c 200
curl -s "http://localhost:8001/?token=<TOKEN>" | head -c 200
```

### 5.6 Renouvellement de la session Garmin (garth)

Si les outils retournent `{"error": "Not logged in"}` :

```bash
# Pour garmin-mcp
sudo docker exec -it garmin-mcp bash
# Puis dans le conteneur :
python -c "
import garth, os
garth.login('ton_email@garmin.com', 'ton_mot_de_passe')
garth.save('/secrets/garth')
"
exit

# Pour workouts-mcp
sudo docker exec -it workouts-mcp bash
# Puis :
python -c "
import garth
garth.login('ton_email@garmin.com', 'ton_mot_de_passe')
garth.save('/garth')
"
exit
```

---

## 6. Structure des fichiers sur le NAS

```
/volume1/docker/
├── garmin-mcp/
│   ├── docker-compose.yml      ← config principale + API_TOKEN
│   ├── app/
│   │   └── server.py           ← code MCP + middleware auth
│   ├── secrets/
│   │   └── garth/              ← tokens OAuth Garmin (garth)
│   └── data/                   ← données persistantes
│
└── garmin-workouts-mcp/
    ├── docker-compose.yml      ← config principale + API_TOKEN
    ├── Dockerfile              ← image buildée localement
    ├── start.py                ← point d'entrée + middleware auth
    └── garth/                  ← tokens OAuth Garmin
```

---

## 7. Limitations connues et pistes d'évolution

**Token en query param visible dans les logs** : le Synology Reverse Proxy loggue les URLs complètes. Le token apparaît en clair dans les logs d'accès DSM. Acceptable pour un usage personnel, problématique pour un usage multi-utilisateurs.

**Pas de rotation automatique** : le token est statique. Aucun mécanisme d'expiration. À rotation manuelle selon les besoins.

**Évolutions possibles** :
- Migrer vers Traefik (remplacement du Synology RP) pour une validation Bearer native en header, sans exposition dans les URLs
- Ajouter un conteneur `nginx-auth-proxy` entre le Synology RP et les MCP pour centraliser la sécurité
- Implémenter un rate limiting pour limiter les tentatives de brute-force sur le token
