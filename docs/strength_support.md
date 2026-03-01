# Strength Support (Native Garmin JSON)

This document describes the strength-training implementation added in this fork.

## What Was Added

Two new MCP tools are available:

- `build_strength_workout(workout_data, input_format)`
- `upload_strength_workout(workout_data)`

Existing tools remain unchanged (`upload_workout`, `list_workouts`, `get_workout`, etc.).

## Why A New Upload Tool

`upload_workout` uses a simplified schema built for cardio workflows.  
For strength sessions, that conversion drops important metadata (`category`, `exerciseName`, `weightValue`, reps conditions).

`upload_strength_workout` bypasses that conversion and posts Garmin-native JSON directly to:

`POST /workout-service/workout`

## Validation Rules

The strength flow applies strict validation before upload:

1. Root payload:
- `workoutName` is required
- `sportType.sportTypeKey` must be `strength_training`
- `workoutSegments` must be non-empty

2. Step structure:
- step `type` must be `ExecutableStepDTO` or `RepeatGroupDTO`
- `RepeatGroupDTO.numberOfIterations` must be a positive integer
- `RepeatGroupDTO.workoutSteps` must be non-empty

3. Exercise pair validation (strict):
- If both `category` and `exerciseName` are null: accepted (rest/transition steps)
- If only one is set: rejected
- If both are set: pair must exist in exercise CSV

## CSV Source For Exercise Validation

CSV lookup order:

1. `GARMIN_STRENGTH_EXERCISES_CSV` env variable
2. Fallback repository root file: `garmin_exercises_keys_en_fr.csv`

Required CSV columns:

- `key`
- `category`

The pair is built as:

- `category = row["category"]`
- `exerciseName = row["key"].removeprefix(f"{category}_")`

## Numbering Normalization

Before upload, numbering is normalized on a deep copy:

- `segmentOrder`: sequential by segment (1..N)
- `stepOrder`: depth-first across all steps in segment order
- `childStepId`: local index inside each repeat group children (1..n)
- `stepId`: preserved if present, otherwise injected as `null`

## Tool: `build_strength_workout`

`input_format` must be:

- `simple`
- `native`

### Simple Input Format

Root:

- `name` (required)
- `description` (optional)
- `steps` (required, non-empty)

Steps:

- `exercise`
  - `category`, `exerciseName` required
  - exactly one of `reps` or `durationSeconds`
  - `weightKg` optional, default `-1.0`
  - `stepType`: `warmup` or `interval` (default `interval`)
- `rest`
  - `durationSeconds` optional
  - if omitted, creates `lap.button` rest
- `repeat`
  - `iterations` required (>0)
  - `steps` required
  - `skipLastRest` optional (default `true`)

Return shape:

```json
{
  "workout": { "workoutName": "...", "...": "native Garmin payload" }
}
```

## Tool: `upload_strength_workout`

Input: Garmin native strength JSON.  
Optional flags:
- `replace_existing` (bool, default `false`)
- `name_match_mode` (`exact` or `contains`, default `exact`)

Output:

```json
{ "workoutId": "123456789" }
```

Behavior:

1. Validate structure
2. Normalize numbering
3. Validate `(category, exerciseName)` pairs against CSV
4. Upload to Garmin Connect
5. If Garmin responds with `400 Invalid category`, retry once with conservative category remapping
6. Return `workoutId` (and `categoryRemaps` when retry remapping was applied)
7. If `replace_existing=true`, create first, then delete matching strength workouts by name and return `replacedWorkoutIds`
8. If deletion cleanup has errors, return `replacementCleanupErrors` without losing the newly created workout

Default remaps used for retry:

- `ROW_FACE -> ROW`
- `FLYE_DUMBBELL -> FLYE`
- `CURL_DUMBBELL -> CURL`
- `SHRUG_SCAPULAR -> SHRUG`
- `PLANK_PLANK -> PLANK`

Exercise remaps used on retry (selected examples):

- `ROW/PULL_WITH_EXTERNAL_ROTATION -> FACE_PULL_WITH_EXTERNAL_ROTATION`
- `SHRUG/RETRACTION -> SCAPULAR_RETRACTION`
- `CURL/REVERSE_WRIST_CURL -> DUMBBELL_REVERSE_WRIST_CURL`
- `FLYE/FLYE -> DUMBBELL_FLYE`

You can override/extend remaps with:

- `GARMIN_STRENGTH_CATEGORY_MAPPING=SOURCE:TARGET,SOURCE2:TARGET2`
- `GARMIN_STRENGTH_EXERCISE_MAPPING=CATEGORY/EXERCISE:TARGET_EXERCISE,...`

Mappings are versioned in:

- `garmin_workouts_mcp/config/strength_mapping.json` (packaged default)
- Override file path with `GARMIN_STRENGTH_MAPPING_FILE=/abs/path/strength_mapping.json`
- This file is the default source of truth for built-in remaps.

## Supported Rest Patterns

The strength model supports all common rest patterns used in this fork:

- Lap-button rest (`endCondition.conditionTypeKey = "lap.button"`)
- Timed rest (`"time"`)
- Cardio-guided rest via target type (`targetType.workoutTargetTypeKey = "heart.rate.zone"`)

## Example: Native Strength Skeleton

```json
{
  "workoutName": "S1 Push",
  "sportType": { "sportTypeId": 5, "sportTypeKey": "strength_training" },
  "workoutSegments": [
    {
      "segmentOrder": 1,
      "sportType": { "sportTypeId": 5, "sportTypeKey": "strength_training" },
      "workoutSteps": []
    }
  ]
}
```

## Tests Added

- `tests/test_strength_workout.py`
  - validation rules
  - CSV pair checks
  - numbering normalization
  - helper/build behavior

- `tests/test_main.py`
  - `build_strength_workout` and `upload_strength_workout`

- `tests/test_integration.py`
  - new tools registration in MCP server
