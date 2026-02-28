# Change Log: Strength Support Fork

This file summarizes the concrete code changes introduced for complete strength support.

## New Files

- `garmin_workouts_mcp/strength_workout.py`
  - Native-strength payload helpers
  - Validation logic (schema + CSV exercise pairs)
  - Numbering normalization (`segmentOrder`, `stepOrder`, `childStepId`, `stepId`)

- `tests/test_strength_workout.py`
  - Unit tests for helper functions and strength validation pipeline

- `docs/strength_support.md`
  - Functional and technical documentation for strength workflows

## Modified Files

- `garmin_workouts_mcp/main.py`
  - Added MCP tool: `build_strength_workout(workout_data, input_format)`
  - Added MCP tool: `upload_strength_workout(workout_data)`
  - Both tools use shared preparation path from `strength_workout.py`

- `tests/test_main.py`
  - Added test class `TestStrengthWorkoutTools`
  - Covers successful path and error conditions

- `tests/test_integration.py`
  - Added expected MCP tools:
    - `build_strength_workout`
    - `upload_strength_workout`

- `README.md`
  - Added strength workflow guidance
  - Added environment variable docs for `GARMIN_STRENGTH_EXERCISES_CSV`
  - Linked to detailed strength documentation

## Behavioral Summary

Strength upload now preserves:

- `category`
- `exerciseName`
- `weightValue`
- `weightUnit`
- `RepeatGroupDTO` nesting and iteration counts
- reps/time/lap-button end conditions

## Compatibility Notes

- Existing tools were not changed in behavior.
- `upload_workout` remains the cardio-oriented simplified path.
- New strength flow is opt-in via the new tools.
