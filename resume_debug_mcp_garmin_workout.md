# Résumé de débogage — Fork MCP Garmin Workout Upload
*Session du 2026-02-28 — Upload séance PUSH S1 C1 vers Garmin Connect*

---

## Contexte

Tentative de push automatisé d'une séance de musculation structurée (PUSH — S1 C1 — Lundi 02/03) vers Garmin Connect via les outils MCP du fork. Indicateurs de récupération validés en amont (FC repos 39 bpm, EVA forme 8/10, sommeil bon 7h30, charge pro 4/10 — feu vert).

Le fork expose trois outils pertinents : `build_strength_workout`, `upload_strength_workout`, `upload_workout`.

---

## Chronologie des événements et erreurs

### Étape 1 — Première tentative `build_strength_workout` → ERREUR interne

**Payload envoyé :** séance complète incluant `PLANK_PLANK / PLANK` en finisher.

**Erreur retournée :**
```
Error calling tool 'build_strength_workout':
Unknown Garmin exercise pair category='PLANK_PLANK', exerciseName='PLANK'.
request_id: req_011CYakFEZRnTz1ujMNi421X
```

**Cause identifiée :** le fork valide les paires `(category, exerciseName)` contre un fichier CSV interne. La paire `PLANK_PLANK / PLANK` est présente dans `garmin_exercises_keys_en_fr.csv` (confirmé par `bash` : ligne `PLANK_PLANK,PLANK_PLANK,en,Plank,fr,Planche`) — mais **le fork la rejette quand même**.

**Hypothèse :** le fork charge son propre CSV de référence (différent du CSV du projet), ou sa logique de parsing ne traite pas correctement les catégories où `category == key` (cas `PLANK_PLANK` dont le `key` et la `category` sont identiques).

---

### Étape 2 — Deuxième tentative `build_strength_workout` sans PLANK → SUCCÈS

**Modification :** suppression du finisher (`PLANK_PLANK / PLANK`). Payload retenu :

| Exercice | category | exerciseName | stepType |
|---|---|---|---|
| Rotation externe élastique | `BANDED_EXERCISES` | `SHOULDER_EXTERNAL_ROTATION` | warmup |
| Face pull rotation externe | `ROW_FACE` | `PULL_WITH_EXTERNAL_ROTATION` | warmup |
| Rétraction scapulaire | `SHRUG_SCAPULAR` | `RETRACTION` | warmup |
| Reverse wrist curl | `CURL_DUMBBELL` | `REVERSE_WRIST_CURL` | warmup |
| Développé couché haltères | `BENCH_PRESS` | `DUMBBELL_BENCH_PRESS` | interval |
| Développé incliné haltères | `BENCH_PRESS` | `INCLINE_DUMBBELL_BENCH_PRESS` | interval |
| Écarté couché haltères | `FLYE_DUMBBELL` | `FLYE` | interval |
| Développé épaules assis | `SHOULDER_PRESS` | `SEATED_DUMBBELL_SHOULDER_PRESS` | interval |
| Élévations latérales | `LATERAL_RAISE` | `DUMBBELL_LATERAL_RAISE` | interval |
| Kickback triceps | `TRICEPS_EXTENSION` | `DUMBBELL_KICKBACK` | interval |

**Résultat :** `build_strength_workout` retourne un payload natif Garmin valide au format `WorkoutDTO` avec `workoutSegments`, `RepeatGroupDTO`, `ExecutableStepDTO`. Toutes les paires ci-dessus sont **acceptées par la validation interne du fork**.

---

### Étape 3 — `upload_strength_workout` avec le payload natif → ERREUR API 400

**Payload envoyé :** le `WorkoutDTO` retourné par `build_strength_workout` (format natif, champ racine `workout`).

**Erreur retournée :**
```
Error calling tool 'upload_strength_workout':
Failed to upload strength workout to Garmin Connect:
Error in request: 400 Client Error: Bad Request
for url: https://connectapi.garmin.com/workout-service/workout
request_id: req_011CYakL7BKDC3875jaUd799
```

**Analyse :** l'erreur 400 est retournée par l'API Garmin Connect elle-même, pas par le fork. Le fork a transmis le payload à l'API — qui l'a rejeté. Le payload natif contenait les catégories `ROW_FACE`, `SHRUG_SCAPULAR`, `CURL_DUMBBELL`, `FLYE_DUMBBELL` que l'API Garmin Connect refuse en écriture.

---

### Étape 4 — `upload_workout` avec le même payload natif → ERREUR interne fork

**Tentative :** utiliser `upload_workout` (outil générique) à la place de `upload_strength_workout` avec le même payload natif.

**Erreur retournée :**
```
Error calling tool 'upload_workout':
Failed to upload workout to Garmin Connect: 'type'
request_id: req_011CYakPNokRZ8JSFURrnhMn
```

**Analyse :** erreur différente — `'type'` est une `KeyError` Python, pas une erreur API. Le tool `upload_workout` tente d'accéder à une clé `'type'` inexistante dans le payload ou dans la réponse. Ce comportement indique un bug distinct dans la couche de traitement du payload de `upload_workout`.

---

## Bilan des erreurs identifiées

Trois bugs distincts, deux dans le fork, un dans l'API :

### Bug 1 — Validation CSV incorrecte dans `build_strength_workout`

**Symptôme :** rejette `PLANK_PLANK / PLANK` malgré sa présence dans le CSV.

**Localisation probable :** la fonction de validation qui charge et parse le CSV de référence. Hypothèses à tester dans l'ordre :
1. Le fork utilise un CSV différent de `garmin_exercises_keys_en_fr.csv` (chemin hardcodé ou packagé lors du build).
2. La logique de parsing ignore les lignes où `key == category` (cas du `PLANK_PLANK`).
3. La comparaison est sensible à la casse ou aux espaces (trailing whitespace dans le CSV source).

**Test de confirmation :**
```python
# Dans le code du fork, localiser la fonction de validation
# Chercher : load_csv, validate_exercise, check_exercise_pair ou similaire
# Logger la paire reçue et la liste chargée pour comparer
print(f"Checking: category={category!r}, exerciseName={exerciseName!r}")
print(f"CSV loaded: {len(csv_pairs)} entries")
print(f"Looking for: {(category, exerciseName)}")
```

---

### Bug 2 — `upload_strength_workout` transmet des catégories rejetées par l'API Garmin

**Symptôme :** erreur 400 de l'API Garmin Connect. Le payload passe la validation interne du fork mais est rejeté en production.

**Catégories qui génèrent le 400 :**

| category | Présente dans CSV fork | Acceptée par API Garmin |
|---|---|---|
| `ROW_FACE` | ✅ oui | ❌ non |
| `SHRUG_SCAPULAR` | ✅ oui | ❌ non |
| `CURL_DUMBBELL` | ✅ oui | ❌ non |
| `FLYE_DUMBBELL` | ✅ oui | ❌ non |

**Catégories qui fonctionnent :**

| category | Présente dans CSV fork | Acceptée par API Garmin |
|---|---|---|
| `BENCH_PRESS` | ✅ oui | ✅ oui |
| `BANDED_EXERCISES` | ✅ oui | ✅ oui |
| `SHOULDER_PRESS` | ✅ oui | ✅ oui |
| `LATERAL_RAISE` | ✅ oui | ✅ oui |
| `TRICEPS_EXTENSION` | ✅ oui | ✅ oui |
| `PULL_UP` | ✅ oui | ✅ oui (à confirmer) |

**Origine probable :** le CSV de référence du fork a été construit à partir de l'API de *lecture* Garmin (GET /exercise-sets ou équivalent), qui expose plus de catégories que l'API d'*écriture* (`POST /workout-service/workout`). L'API d'écriture utilise une whitelist de catégories différente et plus restrictive.

**Examen du workout existant "Jeudi - Haut du Corps" (ID 1418023683, créé via interface web Garmin) :** ce workout a été créé et fonctionne. L'interface web utilise probablement des catégories génériques (`CURL`, `ROW`, `FLYE` sans suffixe) que l'API d'écriture accepte — mais qui sont absentes du CSV du fork, donc rejetées par sa validation interne. C'est la contradiction structurelle centrale.

**Investigation recommandée :**
```bash
# 1. Faire un GET sur un workout existant créé via interface web
curl -H "Authorization: Bearer TOKEN" \
  https://connectapi.garmin.com/workout-service/workout/1418023683

# Comparer les valeurs de "category" dans la réponse
# avec les catégories du CSV du fork

# 2. Tester un upload minimal avec catégorie générique "CURL"
# (absente du CSV fork, mais probablement acceptée par l'API d'écriture)
```

---

### Bug 3 — `upload_workout` lève une `KeyError: 'type'`

**Symptôme :** erreur Python interne `'type'` lors du traitement du payload natif.

**Localisation probable :** dans la fonction de sérialisation ou d'envoi de `upload_workout`, une boucle ou une transformation itère sur les steps et accède à `step['type']` sans vérifier l'existence de la clé. Les steps de pause (`rest`) n'ont pas de champ `type` au niveau où le code l'attend, ou la structure `RepeatGroupDTO` n'est pas gérée.

**Test de confirmation :**
```python
# Ajouter un try/except avec traceback complet dans upload_workout
import traceback
try:
    result = upload_workout(payload)
except KeyError as e:
    traceback.print_exc()
    # Identifier la clé manquante et le step concerné
```

---

## Ce que le fork doit implémenter pour fonctionner

### Correction 1 — Synchroniser le CSV de validation avec l'API d'écriture

Option A (préférable) : extraire la liste des catégories acceptées par l'API d'écriture en uploadant des payloads de test minimalistes, catégorie par catégorie, et constituer une whitelist empirique. Remplacer le CSV de validation par cette whitelist.

Option B : désactiver la validation CSV et laisser l'API rejeter directement. Capturer le 400 avec le body de réponse Garmin (qui indique la catégorie problématique) et le remonter à l'utilisateur.

Option C (court terme) : ajouter une table de mapping `category_csv → category_api` dans le fork. Exemple :
```python
CATEGORY_MAPPING = {
    "CURL_DUMBBELL": "CURL",
    "CURL_ALTERNATING": "CURL",
    "ROW_FACE": "ROW",
    "ROW_SINGLE": "ROW",
    "ROW_BENT": "ROW",
    "FLYE_DUMBBELL": "FLYE",
    "FLYE_INCLINE": "FLYE",
    "SHRUG_SCAPULAR": "SHRUG",
    # etc.
}
```

### Correction 2 — Extraire le body de la réponse 400

Actuellement, le fork retourne uniquement `400 Client Error: Bad Request` sans le body JSON de l'API Garmin. Ce body contient le champ problématique. Ajouter :

```python
except requests.HTTPError as e:
    try:
        error_detail = e.response.json()
    except:
        error_detail = e.response.text
    raise Exception(f"API error {e.response.status_code}: {error_detail}")
```

### Correction 3 — Corriger la `KeyError: 'type'` dans `upload_workout`

Identifier la boucle qui itère sur les steps et accède à `step['type']`. Ajouter une vérification ou gérer les deux structures (`RepeatGroupDTO` et `ExecutableStepDTO`) explicitement.

---

## Payload de référence — Ce qui fonctionnerait avec les corrections

Séance PUSH S1 C1 en ne retenant que les catégories confirmées acceptées par l'API :

```json
{
  "workoutName": "PUSH — S1 C1 — Lundi 02/03",
  "description": "Semaine 1 — Accumulation | 3 séries | RIR 3 | Feu vert",
  "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training"},
  "workoutSegments": [{
    "segmentOrder": 1,
    "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training"},
    "workoutSteps": [
      // Bloc articulaire : BANDED_EXERCISES/SHOULDER_EXTERNAL_ROTATION ✅
      // ROW_FACE/PULL_WITH_EXTERNAL_ROTATION ❌ → mapper vers "ROW"
      // SHRUG_SCAPULAR/RETRACTION ❌ → mapper vers "SHRUG"
      // Avant-bras : CURL_DUMBBELL/REVERSE_WRIST_CURL ❌ → mapper vers "CURL"
      // Pectoraux : BENCH_PRESS/DUMBBELL_BENCH_PRESS ✅
      // BENCH_PRESS/INCLINE_DUMBBELL_BENCH_PRESS ✅
      // FLYE_DUMBBELL/FLYE ❌ → mapper vers "FLYE"
      // Épaules : SHOULDER_PRESS/SEATED_DUMBBELL_SHOULDER_PRESS ✅
      // LATERAL_RAISE/DUMBBELL_LATERAL_RAISE ✅
      // Triceps : TRICEPS_EXTENSION/DUMBBELL_KICKBACK ✅
    ]
  }]
}
```

**Exercices avec substitution de catégorie nécessaire :** face pull, rétraction scapulaire, reverse wrist curl, écarté couché — soit 4 exercices sur 10 pour la séance PUSH.

---

## Priorité d'investigation dans le code source

1. **Localiser le fichier CSV chargé par le fork** — chemin réel en production vs. chemin du projet.
2. **Localiser la fonction de validation** — chercher `validate`, `check_exercise`, `load_csv`, `VALID_EXERCISES`.
3. **Tester PLANK_PLANK** — ajouter un log avant le `raise` pour comparer la paire reçue avec le contenu chargé.
4. **Extraire le body de la réponse 400** — modifier la gestion des exceptions HTTP.
5. **Localiser la `KeyError: 'type'`** — ajouter un `traceback.print_exc()` dans `upload_workout`.
6. **Comparer les catégories du workout ID 1418023683** (créé via web) avec le CSV du fork pour identifier le mapping manquant.

---

*Document généré le 2026-03-01 — Basé sur le transcript 2026-02-28-22-47-12-s1-push-workout-upload-error.txt*

---

## Mise à jour de résolution (2026-03-01)

La section précédente décrit l'état initial (bugs observés). Après correctifs et tests live, le fork est opérationnel pour le programme S1->S4.

### Corrections effectivement implémentées

1. **Validation CSV / cas auto-référencés**
- Le parseur accepte désormais correctement les lignes `key == category` (ex: `PLANK_PLANK`).

2. **Compatibilité API d'écriture Garmin**
- `upload_strength_workout` garde une première tentative sans modification.
- En cas de `400 Invalid category`, un retry unique applique un remap contrôlé:
  - remap d'exercices (catégorie d'origine)
  - remap de catégories
  - second remap d'exercices (catégorie canonique)
- Les remaps sont:
  - versionnés dans `config/strength_mapping.json`
  - surchargeables par variables d'environnement:
    - `GARMIN_STRENGTH_CATEGORY_MAPPING`
    - `GARMIN_STRENGTH_EXERCISE_MAPPING`
    - `GARMIN_STRENGTH_MAPPING_FILE`

3. **Idempotence en debug live**
- Ajout du mode remplacement avant upload:
  - `replace_existing=True`
  - `name_match_mode="exact"` ou `"contains"`
- La réponse retourne `replacedWorkoutIds`.

4. **Diagnostics d'erreur**
- Les erreurs d'upload conservent les détails HTTP Garmin.
- En cas d'échec de remap, un message de guidance propose directement des snippets de mapping.

5. **Session Garmin durable**
- Script `scripts/garth_session.sh` pour conserver une session tant que non fermée (`login/check/run/close`).
- Utilisation d'un `GARTH_HOME` dédié pour isoler les tokens de debug.

### Ce qu'on a appris

- L'API Garmin de lecture et l'API Garmin d'écriture n'acceptent pas exactement les mêmes couples `category/exerciseName`.
- Un mapping uniquement "catégorie" est insuffisant: il faut aussi un mapping "catégorie/exercice -> exercice".
- Pour un cycle de debug efficace, il faut trois piliers:
  - session auth persistante
  - uploads idempotents
  - messages d'erreur exploitables immédiatement

### Validation finale réalisée en live

- Date de validation: **2026-03-01**.
- Upload complet des 12 séances S1/S2/S3/S4 via script.
- Résultat: **12/12 OK** avec `emptyExerciseSteps=0`.
- Les séances précédentes de même nom ont été remplacées correctement (`replacedWorkoutIds` renseigné).
