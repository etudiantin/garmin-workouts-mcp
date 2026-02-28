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
Output:

```json
{ "workoutId": "123456789" }
```

Behavior:

1. Validate structure
2. Normalize numbering
3. Validate `(category, exerciseName)` pairs against CSV
4. Upload to Garmin Connect
5. Return `workoutId`

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
