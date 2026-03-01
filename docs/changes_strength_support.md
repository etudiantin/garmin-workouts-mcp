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

- `config/strength_mapping.json`
  - Versioned category/exercise remap configuration for Garmin write-API compatibility

## Modified Files

- `garmin_workouts_mcp/main.py`
  - Added MCP tool: `build_strength_workout(workout_data, input_format)`
  - Added MCP tool: `upload_strength_workout(workout_data, replace_existing=False, name_match_mode="exact")`
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

---

## Bug Fixes

### `garmin_workouts_mcp/garmin_workout.py`

- **`SPORT_TYPE_MAPPING`**: Added missing `"walking"` entry (`sportTypeId=11`). Previously, passing `type: "walking"` to `upload_workout` raised `ValueError: Unsupported sport type: walking` despite walking being listed in the prompt template.

- **`process_regular_step`**: Distance step fallthrough made explicit. When `endConditionType == "distance"` but `stepDistance` or `distanceUnit` is absent, a clear `ValueError` is now raised instead of silently falling through to time-based handling with a misleading error.

- **`process_step`**: Repeat step detection now uses `isinstance(step.get("steps"), list)` instead of truthiness check, allowing empty-list cases to reach proper validation rather than being silently misrouted.

- **`process_target`**: Target value check changed from `if value:` to `if value is not None:`, so a numeric `0` is no longer silently dropped.

### `garmin_workouts_mcp/main.py`

- **`get_activity`**: Now returns `{"activity": <data>}` for consistency with all other tools (`get_workout` → `{"workout": ...}`, `list_workouts` → `{"workouts": ...}`).

- **`get_activity_weather`**: Now returns `{"weather": <data>}` for the same reason.

- **`delete_workout`**: Now uses `DELETE_WORKOUT_ENDPOINT` (new constant) instead of `GET_WORKOUT_ENDPOINT` to make intent explicit.

- **`get_calendar`**: Added real-date validation via `datetime(year, month, day)` after the range check. Dates like February 30 or April 31 are now rejected with a clear error (`Invalid date: YYYY-MM-DD`).

- **`upload_strength_workout`**: Added write-API compatibility fallback:
  - first upload attempt uses original payload untouched
  - on Garmin `400 Invalid category`, retry once with conservative category remapping
  - successful retry now returns `categoryRemaps` in the response
  - remapping can be overridden/extended via:
    - `GARMIN_STRENGTH_CATEGORY_MAPPING`
    - `GARMIN_STRENGTH_EXERCISE_MAPPING`
    - `GARMIN_STRENGTH_MAPPING_FILE`
  - `replace_existing=true` enables idempotent replacement by workout name before upload
  - when remap is insufficient, error includes mapping guidance snippets

- **Error detail enrichment**: Upload errors now preserve Garmin HTTP response details (`status` + response body) for faster diagnosis.

### `garmin_workouts_mcp/strength_workout.py`

- **CSV parser fix**: Self-keyed rows (`key == category`, e.g. `PLANK_PLANK`) are now handled correctly.
- **Category remapping utilities**: Added helper functions to resolve and apply write-API category mappings.
- **Exercise remapping utilities**: Added helper functions and env overrides for pair-level mapping.
- **External mapping config**: Remaps can be loaded from `config/strength_mapping.json`.

### `tests/test_main.py`

- Updated `TestGetActivity` and `TestGetActivityWeather` assertions to match the new wrapped return formats.
- Added `test_get_calendar_impossible_date` covering calendar-impossible dates.
- Added strength upload fallback tests for invalid-category retry with remapping.
- Added tests for idempotent replacement mode and mapping-guidance errors.

### `tests/test_strength_workout.py`

- Added coverage for self-keyed CSV rows and category remapping helpers.
- Added coverage for file/env exercise mapping overrides and validation.

---

## Live Debug Learnings (2026-03-01)

This section captures what was validated during live debugging against Garmin Connect on March 1, 2026.

### What we changed to make debugging reliable

- Added `scripts/garth_session.sh` to keep a persistent Garmin auth session with isolated tokens:
  - `login`, `check`, `run`, `close`
  - dedicated token home via `GARTH_HOME` (default `~/.garth-debug-garmin`)
- Updated `scripts/upload_4_weeks_program.py` to:
  - upload with `replace_existing=True` + `name_match_mode="exact"`
  - print `replacedWorkoutIds` and `categoryRemaps`
  - run directly from `scripts/` by injecting repo root into `sys.path`

### What we learned about Garmin behavior

- Read-side exercise catalogs and write-side workout validation are not equivalent.
  - Some category/exercise pairs can appear valid in reference data but are rejected by `POST /workout-service/workout`.
- The most robust upload strategy is:
  1. preserve the original payload
  2. retry once only on Garmin invalid-category errors
  3. apply exercise remap (original category), then category remap, then exercise remap again
- Pair-level remaps are required in addition to category remaps (e.g. `ROW_FACE/PULL` -> `FACE_PULL`).
- Error payload quality matters for fast triage: status/body details and mapping guidance significantly reduce debug time.
- Idempotent replacement before upload is mandatory for iterative debugging to avoid duplicate workouts.

### Operational validation outcome

- Full S1/S2/S3/S4 upload run completed in live mode with authenticated session reuse.
- 12/12 workouts uploaded successfully.
- `emptyExerciseSteps=0` on all uploaded workouts after read-back checks.
- Replacement mode deleted previous same-name workouts and returned `replacedWorkoutIds` as expected.
