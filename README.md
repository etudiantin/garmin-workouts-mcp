# Garmin Workouts MCP Server

[![CI/CD Pipeline](https://github.com/st3v/garmin-workouts-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/st3v/garmin-workouts-mcp/actions/workflows/ci.yml)

An MCP server that allows you to create, list, and manage Garmin Connect workouts using natural language descriptions through MCP-compatible clients.

## Features

- **Create workouts**: Generate structured Garmin workouts from natural language descriptions using AI
- **Strength native upload**: Upload full Garmin strength workout JSON without dropping category/exercise/weight metadata
- **Validated exercise whitelist**: 1636 strength exercises across 40 root categories, validated against the live Garmin API
- **Write-API compatibility**: Automatic category/exercise remapping when the Garmin write API rejects fine-grained categories
- **Idempotent replacement**: Replace existing workouts by name with create-then-delete safety
- **List workouts**: View all your existing workouts on Garmin Connect
- **Get workout details**: Retrieve detailed information about specific workouts
- **Schedule workouts**: Schedule workouts on specific dates in Garmin Connect
- **Delete workouts**: Remove workouts from Garmin Connect
- **Activity management**: List, view, and get weather data for completed activities
- **Calendar integration**: View calendar data with workouts and activities
- **MCP Integration**: Works with any MCP-compatible client (Claude Desktop, etc.)

## Setup

1. Install and run using uvx:
```bash
uvx garmin-workouts-mcp
```

2. Configure in your MCP client (e.g., Claude Desktop):

Add to your MCP client configuration:
```json
{
  "mcpServers": {
    "garmin-workouts": {
      "command": "uvx",
      "args": ["garmin-workouts-mcp"],
      "env": { # See Authentication section for details
        "GARMIN_EMAIL": "your_email@example.com",
        "GARMIN_PASSWORD": "your_password"
      }
    }
  }
}
```

## Authentication

The Garmin Workouts MCP Server authenticates with Garmin Connect using `garth` [[https://github.com/matin/garth](https://github.com/matin/garth)]. There are two primary ways to provide your Garmin credentials:

### 1. Using Environment Variables

You can set your Garmin Connect email and password as environment variables before starting the MCP server.

- `GARMIN_EMAIL`: Your Garmin Connect email address.
- `GARMIN_PASSWORD`: Your Garmin Connect password.

Example:
```bash
export GARMIN_EMAIL="your_email@example.com"
export GARMIN_PASSWORD="your_password"
uvx garmin-workouts-mcp
```

### 2. Out-of-Band Authentication with `garth`

Alternatively, you can log in to Garmin Connect once using the `garth` library directly and save your authentication tokens to a directory, which the MCP server will then use for subsequent sessions. This method is useful if you prefer not to store your credentials as environment variables or as part of your MCP client configuration.

To log in out-of-band:

1.  Install `garth`:
    ```bash
    pip install garth
    ```
2.  Run the following Python script in your terminal:
    ```python
    import garth
    from getpass import getpass

    email = input("Enter email address: ")
    password = getpass("Enter password: ")
    # If there's MFA, you'll be prompted during the login
    garth.login(email, password)

    garth.save("~/.garth")
    ```
    Follow the prompts to enter your Garmin Connect email and password. Upon successful login, `garth` will save your authentication tokens to `~/.garth`.

    The MCP server will automatically look for these saved tokens. If you wish to store them in a custom location, you can set the `GARTH_HOME` environment variable.

### 3. Optional Custom Token Location

If you want to isolate tokens for debug sessions, use a dedicated `GARTH_HOME` directory.

```bash
export GARTH_HOME="$HOME/.garth-debug-garmin"
```

Then authenticate once with `garth` and save in this directory:

```python
import garth
from getpass import getpass

email = input("Enter email address: ")
password = getpass("Enter password: ")
garth.login(email, password)
garth.save("~/.garth-debug-garmin")
```

To explicitly close this session, remove token files in that directory.

## Usage

This server provides the following MCP tools that can be used through any MCP-compatible client:

### Generate Workout Data Prompt

Use the `generate_workout_data_prompt` tool to create a prompt for an LLM to generate structured workout data:

```
generate_workout_data_prompt("10 min warmup, 5x(1km at 4:30 pace, 2min recovery), 10 min cooldown")
```

### Upload Workout

Use the `upload_workout` tool to upload structured workout data to Garmin Connect:

```
upload_workout(workout_data_json)
```

This tool remains optimized for the simplified cardio-oriented workout schema.

### Build Strength Workout

Use the `build_strength_workout` tool to build and validate a Garmin native strength workout payload.

```
build_strength_workout(workout_data, "simple")
build_strength_workout(workout_data, "native")
```

- `input_format="simple"` accepts a simplified schema:
  - root: `name`, `description`, `steps`
  - step types: `exercise`, `rest`, `repeat`
- `input_format="native"` accepts native Garmin JSON directly and normalizes numbering (`stepOrder`, `childStepId`).

The tool returns:

```
{"workout": <native_garmin_strength_payload>}
```

### Upload Strength Workout

Use the `upload_strength_workout` tool to upload native Garmin strength JSON directly.

```
upload_strength_workout(native_strength_workout_json)
upload_strength_workout(native_strength_workout_json, replace_existing=True, name_match_mode="exact")
```

This preserves strength-specific metadata such as:
- `category`
- `exerciseName`
- `weightValue`
- `weightUnit`
- `endCondition` (including `reps`, `time`, and `lap.button`)
- `RepeatGroupDTO` structure

Write-API compatibility:
- The exercise whitelist (`garmin_exercises_keys_en_fr.csv`) contains only the 40 root categories accepted by the Garmin write API (see [`docs/garmin_api_reference.md`](docs/garmin_api_reference.md) for the full list and explanation).
- The tool first uploads your payload as-is.
- If Garmin returns `Invalid category` (`400`), the server retries once with a conservative category/exercise remap (e.g. `ROW_FACE` → `ROW`, `ROW/PULL` → `ROW/FACE_PULL`).
- All default remaps are versioned in `garmin_workouts_mcp/config/strength_mapping.json`.
- You can override or extend remaps with:
  - `GARMIN_STRENGTH_CATEGORY_MAPPING=SOURCE:TARGET,SOURCE2:TARGET2`
  - `GARMIN_STRENGTH_EXERCISE_MAPPING=CATEGORY/EXERCISE:TARGET_EXERCISE,...`
  - `GARMIN_STRENGTH_MAPPING_FILE=/abs/path/strength_mapping.json`
- On successful retry, response includes `{"workoutId": "...", "categoryRemaps": {...}}`.
- With `replace_existing=True`, matching **strength** workouts are deleted only after a successful upload:
  - response includes `replacedWorkoutIds`
  - `name_match_mode` supports `exact` or `contains`
  - if cleanup deletion fails, response includes `replacementCleanupErrors`

### Strength Workflow Quick Guide

Recommended end-to-end workflow:

1. Build and validate your payload:
```
build_strength_workout(workout_data, "simple")
```
or
```
build_strength_workout(workout_data, "native")
```
2. Upload it:
```
upload_strength_workout(native_strength_workout_json)
```
3. Read it back for verification:
```
get_workout("workout_id_here")
```

For implementation details and complete examples, see:
- [`docs/garmin_api_reference.md`](docs/garmin_api_reference.md) — Garmin API behavior, category rules, payload structure
- [`docs/strength_support.md`](docs/strength_support.md) — Strength workflow technical details
- [`docs/changes_strength_support.md`](docs/changes_strength_support.md) — Change log
- [`docs/synology_update_guide.md`](docs/synology_update_guide.md) — Synology Docker deployment

### Schedule Workout

Use the `schedule_workout` tool to schedule a workout on a specific date:

```
schedule_workout("workout_id_here", "2024-01-15")
```

### Delete Workout

Use the `delete_workout` tool to remove a workout from Garmin Connect:

```
delete_workout("workout_id_here")
```

### List Workouts

```
list_workouts()
```

### Get Workout Details

```
get_workout("workout_id_here")
```

### List Activities

Use the `list_activities` tool to view completed activities (runs, rides, swims, etc.) from Garmin Connect:

```
list_activities()
```

Optional parameters:
- `limit`: Number of activities to return (default: 20)
- `start`: Starting position for pagination (default: 0)
- `activityType`: Filter by activity type (e.g., "running", "cycling", "swimming")
- `search`: Search for activities containing specific text

Example with filters:
```
list_activities(limit=50, activityType="running", search="Marathon")
```

### Get Activity Details

Use the `get_activity` tool to retrieve detailed information about a specific activity:

```
get_activity("activity_id_here")
```

Returns comprehensive activity data including distance, duration, pace, heart rate, and more, wrapped as:

```json
{"activity": { ... }}
```

### Get Activity Weather

Use the `get_activity_weather` tool to get weather conditions during a specific activity:

```
get_activity_weather("activity_id_here")
```

Returns weather data including temperature, humidity, wind conditions, and weather descriptions, wrapped as:

```json
{"weather": { ... }}
```

### Get Calendar Data

Use the `get_calendar` tool to view calendar data with workouts and activities:

```
get_calendar(2024, 7)      # Monthly view for July 2024
get_calendar(2024, 7, 15)  # Weekly view including July 15th
```

The tool validates that `year`, `month`, and `day` form a real calendar date (e.g., February 30 is rejected).

The tool supports various workout types:
- **Running**: pace targets, distance/time based intervals
- **Walking**: pace targets, distance/time based intervals
- **Cycling**: power, cadence, speed targets
- **Swimming**: time/distance based sets
- **Strength training**: circuit-style workouts
- **General cardio**: heart rate based training

## Workout Description Examples

### Creating New Workouts

- `"30min easy run at conversational pace"`
- `"5km tempo run at 4:15 min/km pace"`
- `"45min walk at 8:00 min/km pace"`
- `"10 min warmup, 3x(20min at 280w, 5min at 150w), 10min cooldown"`
- `"Swimming: 400m warmup, 8x(50m sprint, 30s rest), 400m cooldown"`
- `"Strength circuit: 5x(30s pushups, 30s squats, 30s plank, 60s rest)"`

### Querying Activities

- `"Show me my last 10 running activities"`
- `"Find all cycling activities from last month"`
- `"What was the weather like during my morning run on July 4th?"`
- `"Get details for my longest run this year"`

### Supported Activity Types

The `list_activities` tool supports filtering by the following activity types:
- `running`, `cycling`, `swimming`, `walking`, `hiking`
- `fitness_equipment`, `multi_sport`, `yoga`, `diving`
- `auto_racing`, `motorcycling`, `surfing`, `windsurfing`
- `skiing` variants: `backcountry_skiing_snowboarding_ws`, `cross_country_skiing_ws`, `resort_skiing_snowboarding_ws`, `skate_skiing_ws`
- `climbing` variants: `bouldering`, `indoor_climbing`
- `specialized`: `breathwork`, `e_sport`, `safety`
- `water_sports`: `offshore_grinding`, `onshore_grinding`
- `other` and `winter_sports` for general categorization

## Environment Variables

- `GARMIN_EMAIL`: Your Garmin Connect email address (optional)
- `GARMIN_PASSWORD`: Your Garmin Connect password (optional)
- `GARTH_HOME`: Custom location for Garmin credentials (optional, defaults to `~/.garth`)
- `GARMIN_STRENGTH_EXERCISES_CSV`: Path to a custom Garmin exercises CSV for strict `(category, exerciseName)` validation (optional — the bundled `garmin_exercises_keys_en_fr.csv` is used by default, no file required)
- `GARMIN_STRENGTH_CATEGORY_MAPPING`: Override category remaps (`SOURCE:TARGET,SOURCE2:TARGET2`)
- `GARMIN_STRENGTH_EXERCISE_MAPPING`: Override exercise remaps (`CATEGORY/EXERCISE:TARGET,...`)
- `GARMIN_STRENGTH_MAPPING_FILE`: Path to a custom strength mapping JSON file
- `garmin_exercises_keys_en_fr.csv` (1636 exercises, 40 root categories, API-validated) is bundled inside the package — strict validation works out of the box after `pip install`, no extra file required.


## Development

Requires Python 3.10+.

```bash
make init    # create .venv and install all dependencies (runtime + dev)
make test    # run test suite with coverage
make lint    # ruff check
```

`make init` creates a `.venv` in the repo root and installs the package in editable
mode along with dev dependencies from `requirements.txt`. Run `source .venv/bin/activate`
(or `.venv\Scripts\activate` on Windows) before running `pytest` or `python -m` commands directly.

## Credits

This project incorporates ideas and prompt designs inspired by [openai-garmin-workout](https://github.com/veelenga/openai-garmin-workout), which is licensed under the MIT License.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
