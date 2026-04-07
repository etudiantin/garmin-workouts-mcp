# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
make init                  # Create .venv and install dependencies

# Testing
make test                  # All tests with coverage
python -m pytest tests/test_strength_workout.py -v --tb=short   # Single test file
python -m pytest tests/ -k "test_name" -v                       # Single test by name

# Linting
make lint                  # ruff check .

# Build & release
make build                 # hatch build (produces dist/)
make release               # build + twine upload
```

Python 3.10+ required. Runtime deps: `fastmcp`, `garth`. Dev deps in `requirements.txt`.

## Architecture

This is a **FastMCP server** that bridges an MCP client (e.g. Claude Desktop) to the Garmin Connect API via the `garth` library.

### Entry point

`garmin_workouts_mcp/main.py` — instantiates `FastMCP`, registers all `@mcp.tool` decorated functions, and calls `main()` via the `garmin-workouts-mcp` console script. Authentication is handled transparently by `garth` (tokens cached in `~/.garth` or `$GARTH_HOME`).

### Two workout pipelines

**Cardio** (`garmin_workout.py`): Converts a simplified JSON schema (sport type + steps with targets/end-conditions) into the native Garmin workout payload via `make_payload()`. Called by `upload_workout` tool.

**Strength** (split across three files):
- `strength_workout.py` — core logic: validates exercises against the CSV whitelist, normalizes `segmentOrder`/`stepOrder`/`childStepId` numbering, converts a simple schema to native Garmin JSON via `build_strength_workout_from_simple()`, and loads remap configs.
- `strength_upload_service.py` — service layer: calls the Garmin API, detects `400 Invalid category` errors, and retries automatically with category/exercise remaps from `strength_mapping.json`.
- Tools in `main.py`: `build_strength_workout` (validate + preview) and `upload_strength_workout` (upload with optional idempotent replace).

### Exercise validation

`garmin_workouts_mcp/data/garmin_exercises_keys_en_fr.csv` — whitelist of 1,636 exercises (API-validated) as `(category, exerciseName)` pairs. Strength workouts are validated against this before upload.

`garmin_workouts_mcp/config/strength_mapping.json` — versioned remaps used when the write API rejects a fine-grained category that the read API returns. Override via `GARMIN_STRENGTH_MAPPING_FILE` (path to a custom JSON file) or inline with `GARMIN_STRENGTH_CATEGORY_MAPPING` / `GARMIN_STRENGTH_EXERCISE_MAPPING` (comma-separated `SOURCE:TARGET` pairs).

### Remap retry flow

1. Build payload → validate → upload.
2. If `400 Invalid category` → apply `strength_mapping.json` remaps → retry once.
3. Remap-derived exercises are accepted by the validator (alias support).

### Key environment variables

| Variable | Purpose |
|---|---|
| `GARTH_HOME` | Override garth token cache directory |
| `GARMIN_STRENGTH_EXERCISES_CSV` | Path to a custom exercise whitelist CSV |
| `GARMIN_STRENGTH_MAPPING_FILE` | Path to a custom remap JSON file |
| `GARMIN_STRENGTH_CATEGORY_MAPPING` | Inline category remaps: `SOURCE:TARGET,...` |
| `GARMIN_STRENGTH_EXERCISE_MAPPING` | Inline exercise remaps: `SOURCE:TARGET,...` |

### MCP server config for local dev

`.mcp.json` at repo root wires up the dev server. The installed console script is `garmin-workouts-mcp`.
