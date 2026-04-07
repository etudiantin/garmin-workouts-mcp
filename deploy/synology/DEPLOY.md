# Deployment Guide — garmin-workouts-mcp on Synology

Deploys the MCP server as a Docker container on a Synology NAS, exposed over HTTPS
with Bearer token authentication. See `securisation-mcp-garmin.md` for the full
security architecture.

---

## Architecture

```
Claude client (Desktop / Claude.ai)
    ↓ HTTPS  https://workouts.yourdomain.tld/?token=TOKEN
Synology Reverse Proxy  (SSL termination, DSM Application Portal)
    ↓ HTTP  localhost:8001
garmin-workouts-mcp-fork  (Docker container)
    ├── start.py           FastMCP HTTP + BearerAuthMiddleware
    └── /garth             garth OAuth tokens (volume)
```

---

## Prerequisites

- Synology NAS with Container Manager (Docker) and SSH access
- Domain `workouts.yourdomain.tld` pointing to the NAS (DNS + port-forward 443)
- Synology Application Portal → Reverse Proxy rule:
  - Source: HTTPS `workouts.yourdomain.tld:443`
  - Destination: HTTP `localhost:8001`
  - Custom headers: `Upgrade: $http_upgrade`, `Connection: $connection_upgrade`

---

## Initial Deployment

### 1. Configure local instance file

```bash
cp deploy/synology/.env.example deploy/synology/.env
# Edit .env: set API_TOKEN, DOMAIN, NAS_HOST, NAS_USER, NAS_PATH, GITHUB_REPO
```

Generate a token:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Clone repo on NAS

```bash
# From the NAS via SSH (source from .env for convenience)
source deploy/synology/.env
ssh ${NAS_USER}@${NAS_HOST} "git clone ${GITHUB_REPO} ${NAS_PATH} && mkdir -p ${NAS_PATH}/deploy/synology/garth"
```

### 3. Copy .env to NAS

```bash
source deploy/synology/.env
scp deploy/synology/.env ${NAS_USER}@${NAS_HOST}:${NAS_PATH}/deploy/synology/.env
```

### 4. First Garmin authentication (if garth tokens are missing)

Run interactively so garth can handle 2FA prompts:

```bash
source deploy/synology/.env
ssh -t ${NAS_USER}@${NAS_HOST} "
  /usr/local/bin/docker run --rm -it \
    -e GARTH_HOME=/garth \
    -v ${NAS_PATH}/deploy/synology/garth:/garth \
    garmin-workouts-mcp:fork-strength \
    python -c \"
import garth
garth.login('your_email@garmin.com', 'your_password')
garth.save('/garth')
print('Tokens saved.')
\"
"
```

### 5. Build and start

```bash
source deploy/synology/.env
ssh ${NAS_USER}@${NAS_HOST} "
  cd ${NAS_PATH}
  /usr/local/bin/docker compose -f deploy/synology/docker-compose.yml up -d --build
"
```

### 6. Verify

```bash
source deploy/synology/.env

# No token → must return 401
curl -s -o /dev/null -w '%{http_code}' https://${DOMAIN}/

# With token → must return non-401 (200 or 406 from curl which doesn't speak SSE)
curl -s -o /dev/null -w '%{http_code}' "https://${DOMAIN}/?token=${API_TOKEN}"
```

---

## Claude Client Configuration

### Claude Desktop

`%APPDATA%\Claude\claude_desktop_config.json` (Windows) or
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "garmin-workouts": {
      "url": "https://workouts.yourdomain.tld/?token=YOUR_TOKEN"
    }
  }
}
```

The `MCP_URL` value in your `.env` is the exact string to use here.

### Claude.ai (web)

**Settings → Connectors → Add custom connector** → paste `MCP_URL` from `.env`.

---

## Maintenance

### Update to latest code

```bash
source deploy/synology/.env
ssh ${NAS_USER}@${NAS_HOST} "
  cd ${NAS_PATH} && git pull
  /usr/local/bin/docker compose -f deploy/synology/docker-compose.yml up -d --build
"
```

### Rotate the Bearer token

1. Generate a new token: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Update `API_TOKEN` in `deploy/synology/.env` (local + NAS copy)
3. Restart the container:
   ```bash
   source deploy/synology/.env
   ssh ${NAS_USER}@${NAS_HOST} "
     cd ${NAS_PATH}
     /usr/local/bin/docker compose -f deploy/synology/docker-compose.yml up -d
   "
   ```
4. Update the URL in your Claude client config.

### Renew Garmin session (garth tokens expired)

```bash
source deploy/synology/.env
ssh -t ${NAS_USER}@${NAS_HOST} "
  /usr/local/bin/docker exec -it garmin-workouts-mcp-fork python -c \"
import garth
garth.login('your_email@garmin.com', 'your_password')
garth.save('/garth')
print('Done.')
\"
"
```

### View logs

```bash
source deploy/synology/.env
ssh ${NAS_USER}@${NAS_HOST} "/usr/local/bin/docker logs garmin-workouts-mcp-fork --tail 50 -f"
```

---

## Files

```
deploy/synology/
├── DEPLOY.md            ← this guide
├── Dockerfile           ← builds the image (python:3.12-slim, exposes 8001)
├── docker-compose.yml   ← service definition (loads .env for API_TOKEN)
├── start.py             ← FastMCP HTTP server + BearerAuthMiddleware
├── .env                 ← instance-specific secrets (NOT committed)
├── .env.example         ← template for .env
├── garth/               ← garth OAuth tokens (volume mount, NOT committed)
└── securisation-mcp-garmin.md  ← security architecture reference
```
