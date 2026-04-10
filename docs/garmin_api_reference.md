# Garmin Connect API Reference (Workout Service)

This document captures everything learned about the Garmin Connect API behavior through live testing, debugging, and production uploads. It serves as a reference for anyone building tools that interact with the Garmin Connect Workout Service.

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/workout-service/workouts` | GET | List all workouts |
| `/workout-service/workout` | POST | Create a workout |
| `/workout-service/workout/{id}` | GET | Get workout details |
| `/workout-service/workout/{id}` | DELETE | Delete a workout |
| `/workout-service/schedule/{id}` | POST | Schedule a workout on a date |
| `/activity-service/activity/{id}` | GET | Get activity details |
| `/activity-service/activity/{id}/weather` | GET | Get activity weather |
| `/activitylist-service/activities/search/activities` | GET | Search/list activities |
| `/calendar-service/year/{y}/month/{m}` | GET | Monthly calendar view |
| `/calendar-service/year/{y}/month/{m}/day/{d}/start/{s}` | GET | Weekly calendar view |

## Authentication

The API uses OAuth tokens managed by the `garth` library.

- Tokens are stored in `~/.garth` by default (configurable via `GARTH_HOME`).
- Tokens can be reused across sessions via `garth.resume()` / `garth.save()`.
- For debug/test isolation, use a dedicated `GARTH_HOME` directory (e.g. `~/.garth-debug-garmin`).
- After a debug session, explicitly clean up by removing `oauth1_token.json` / `oauth2_token.json` from the isolated directory.
- 2FA users should prefer token-based auth over email/password in production.

## Sport Type IDs

These are the IDs validated for **workout creation** (`POST /workout-service/workout`).
Only these six are accepted by `upload_workout` / `SPORT_TYPE_MAPPING`.

| sportTypeId | sportTypeKey | `upload_workout` key |
|---|---|---|
| 1 | `running` | `"running"` |
| 2 | `cycling` | `"cycling"` |
| 4 | `swimming` | `"swimming"` |
| 5 | `strength_training` | `"strength"` |
| 6 | `cardio_training` | `"cardio"` |
| 11 | `walking` | `"walking"` |

> **Note — activityType vs sportType**: `list_activities` accepts a much wider
> `activityType` filter (`hiking`, `yoga`, `surfing`, etc.) because it filters
> *completed activities*, not workouts. Those strings are **not** valid for
> workout creation and will raise `ValueError: Unsupported sport type`.
> Other sportTypeIds exist in Garmin's system but have not been validated
> against the write API — do not add them to `SPORT_TYPE_MAPPING` without live testing.

## Calendar API Quirk

The Garmin Calendar API uses **0-based months** (January = 0, December = 11), unlike the standard 1-based human convention. The MCP server handles this conversion internally.

---

## Read API vs. Write API: The Category Problem

This is the single most important lesson learned from live testing.

### The problem

Garmin exposes exercise catalogs via read endpoints that list exercise categories and names. However, **the write API (`POST /workout-service/workout`) does not accept all categories returned by the read API**.

The read API returns fine-grained categories like:
- `CURL_DUMBBELL`, `CURL_STANDING`, `CURL_ALTERNATING`
- `ROW_FACE`, `ROW_BENT`, `ROW_DUMBBELL`
- `FLYE_DUMBBELL`, `FLYE_INCLINE`
- `SHRUG_SCAPULAR`
- `DEADLIFT_ROMANIAN`
- `SQUAT_WEIGHTED`
- `LUNGE_WEIGHTED`
- `PLANK_PLANK`

The write API **rejects** all of these with `400 Invalid category`. It only accepts the **root categories**:
- `CURL`, `ROW`, `FLYE`, `SHRUG`, `DEADLIFT`, `SQUAT`, `LUNGE`, `PLANK`

### Root cause

The Garmin exercise catalog has a hierarchical structure:
```
ROOT_CATEGORY (write-side)
  └── SUB_CATEGORY (read-side only)
       └── EXERCISE_NAME
```

The write API only accepts the root level. Sub-categories exist in the read-side catalog and in the Garmin app UI, but they are **not valid for workout creation via the API**.

### The validated whitelist approach

To solve this definitively, we built a whitelist of 1636 exercises across 40 root categories by testing each `(category, exerciseName)` pair against the live API. This whitelist lives in `garmin_exercises_keys_en_fr.csv` at the repository root.

### The 40 accepted root categories

These are the categories confirmed to work with `POST /workout-service/workout`:

| Category | Category | Category | Category |
|---|---|---|---|
| `BANDED_EXERCISES` | `BENCH_PRESS` | `CABLE_CROSSOVER` | `CALF_RAISE` |
| `CARDIO` | `CARRY` | `CHOP` | `CORE` |
| `CRUNCH` | `CURL` | `DEADLIFT` | `FLYE` |
| `HIP_RAISE` | `HIP_STABILITY` | `HYPEREXTENSION` | `KETTLEBELL_SWING` |
| `LATERAL_RAISE` | `LEG_CURL` | `LEG_RAISE` | `LUNGE` |
| `OLYMPIC_LIFT` | `PLANK` | `PLYO` | `PULL_UP` |
| `PUSH_UP` | `ROW` | `SHOULDER_PRESS` | `SHOULDER_STABILITY` |
| `SHRUG` | `SIT_UP` | `SQUAT` | `STEP_UP` |
| `SUSPENSION` | `TOTAL_BODY` | `TRICEPS_EXTENSION` | `TRICEPS_PRESS` |
| `WARM_UP` | `WOODCHOP` | | |

Note: 38 categories listed (some categories like `STIFF_LEG_DEADLIFT` and `TRX` were also validated but are less commonly used).

### Categories excluded from the whitelist

These are intentionally excluded because they are not strength-training exercises:
- Yoga poses (`POSE` category)
- Pilates moves (`MOVE` category)
- Running drills
- Cycling drills
- Metadata-only entries

---

## Workout Payload Structure

### Native Strength Workout JSON

```json
{
  "workoutName": "My Workout",
  "description": "Optional description",
  "sportType": {
    "sportTypeId": 5,
    "sportTypeKey": "strength_training"
  },
  "workoutSegments": [
    {
      "segmentOrder": 1,
      "sportType": {
        "sportTypeId": 5,
        "sportTypeKey": "strength_training"
      },
      "workoutSteps": [
        // ExecutableStepDTO or RepeatGroupDTO
      ]
    }
  ]
}
```

### ExecutableStepDTO (Exercise Step)

```json
{
  "type": "ExecutableStepDTO",
  "stepId": null,
  "stepOrder": 1,
  "stepType": { "stepTypeId": 3, "stepTypeKey": "interval" },
  "endCondition": { "conditionTypeId": 10, "conditionTypeKey": "reps" },
  "endConditionValue": 12.0,
  "targetType": { "workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target" },
  "category": "BENCH_PRESS",
  "exerciseName": "DUMBBELL_BENCH_PRESS",
  "weightValue": 30.0,
  "weightUnit": { "unitId": 8, "unitKey": "kilogram", "factor": 1000.0 }
}
```

### ExecutableStepDTO (Rest Step)

```json
{
  "type": "ExecutableStepDTO",
  "stepId": null,
  "stepType": { "stepTypeId": 5, "stepTypeKey": "rest" },
  "endCondition": { "conditionTypeId": 1, "conditionTypeKey": "lap.button" },
  "endConditionValue": 0.0,
  "category": null,
  "exerciseName": null,
  "weightValue": -1.0
}
```

Rest steps support:
- `lap.button` — user taps to end rest (endConditionValue = 0)
- `time` — timed rest in seconds
- Heart rate zone target for cardio-guided rest

### RepeatGroupDTO (Superset / Circuit)

```json
{
  "type": "RepeatGroupDTO",
  "stepId": null,
  "stepType": { "stepTypeId": 6, "stepTypeKey": "repeat" },
  "numberOfIterations": 3,
  "endCondition": { "conditionTypeId": 7, "conditionTypeKey": "iterations" },
  "endConditionValue": 3.0,
  "skipLastRestStep": true,
  "smartRepeat": false,
  "workoutSteps": [
    // child ExecutableStepDTO steps
  ]
}
```

### End Conditions

| conditionTypeId | conditionTypeKey | Usage |
|---|---|---|
| 1 | `lap.button` | Manual stop (rest steps) |
| 2 | `time` | Duration in seconds |
| 7 | `iterations` | Repeat group count |
| 10 | `reps` | Exercise repetitions |

### Step Types

| stepTypeId | stepTypeKey | Usage |
|---|---|---|
| 1 | `warmup` | Warm-up exercise |
| 3 | `interval` | Main exercise |
| 5 | `rest` | Rest between sets |
| 6 | `repeat` | Repeat group container |

---

## Numbering Rules

The API expects deterministic, depth-first numbering:

- `segmentOrder`: sequential per segment (1..N)
- `stepOrder`: depth-first across all steps in segment order (continuous counter)
- `childStepId`: local 1-based index within each repeat group's children
- `stepId`: can be `null` for new workouts; preserved on read-back

The MCP server normalizes these automatically before upload.

---

## Error Handling Patterns

### 400 Invalid category

The most common write-side error. Returned when:
- A sub-category (e.g. `CURL_DUMBBELL`) is used instead of its root (e.g. `CURL`)
- An exerciseName is not recognized for the given category

The MCP server handles this with a retry mechanism:
1. First attempt: send payload as-is
2. On `400 Invalid category`: apply exercise remaps, then category remaps, then exercise remaps again
3. Retry with remapped payload
4. If still failing, return error with mapping guidance

### Exercise Name Changes After Category Remap

When a category is remapped (e.g. `ROW_FACE` → `ROW`), the exercise name often needs remapping too because the exercise name is category-relative:

| Original | After Category Remap | After Exercise Remap |
|---|---|---|
| `ROW_FACE/PULL` | `ROW/PULL` | `ROW/FACE_PULL` |
| `ROW_FACE/PULL_WITH_EXTERNAL_ROTATION` | `ROW/PULL_WITH_EXTERNAL_ROTATION` | `ROW/FACE_PULL_WITH_EXTERNAL_ROTATION` |
| `SHRUG_SCAPULAR/RETRACTION` | `SHRUG/RETRACTION` | `SHRUG/SCAPULAR_RETRACTION` |
| `FLYE_DUMBBELL/FLYE` | `FLYE/FLYE` | `FLYE/DUMBBELL_FLYE` |
| `CURL_DUMBBELL/REVERSE_WRIST_CURL` | `CURL/REVERSE_WRIST_CURL` | `CURL/DUMBBELL_REVERSE_WRIST_CURL` |

### Deleted Workout Ghost Reads

Garmin may keep deleted workouts accessible by direct ID lookup (`GET /workout-service/workout/{id}`) for a period after deletion, even if they no longer appear in the workout list. This is a caching/eventual-consistency behavior, not a bug.

---

## Weight Handling

- `weightValue` is in kilograms (float)
- `weightValue = -1.0` means "no weight specified" (bodyweight exercises)
- `weightUnit` is always `{ "unitId": 8, "unitKey": "kilogram", "factor": 1000.0 }`

---

## Idempotent Replacement Pattern

For iterative development and debugging, the MCP server supports idempotent workout replacement:

1. Before upload, search for existing workouts with the same name
2. Filter matches to `strength_training` sport type only
3. Upload the new workout first (create-then-delete, not delete-then-create)
4. Only after successful upload, delete old matching workouts
5. Return `replacedWorkoutIds` in response

This pattern prevents data loss: if the upload fails, the old workout is still intact.

---

## Rate Limits and Session Management

- No explicit rate limits documented, but rapid successive calls may trigger throttling.
- Long-lived sessions via `garth.resume()` work reliably for batch operations.
- 12 consecutive workout uploads in a single session completed without issues.
- Token refresh is handled transparently by `garth`.
