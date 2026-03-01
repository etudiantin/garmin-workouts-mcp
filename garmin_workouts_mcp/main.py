from fastmcp import FastMCP
import garth
import os
import sys
import logging
from datetime import datetime
from typing import Any
from .garmin_workout import make_payload
from .strength_workout import (
    CATEGORY_MAPPING_ENV_NAME,
    DEFAULT_MAPPING_FILENAME,
    EXERCISE_MAPPING_ENV_NAME,
    build_strength_workout_from_simple,
    get_strength_category_mapping,
    get_strength_exercise_mapping,
    prepare_strength_workout_payload,
    remap_strength_exercises,
    remap_strength_categories,
)

LIST_WORKOUTS_ENDPOINT = "/workout-service/workouts"
GET_WORKOUT_ENDPOINT = "/workout-service/workout/{workout_id}"
DELETE_WORKOUT_ENDPOINT = "/workout-service/workout/{workout_id}"
GET_ACTIVITY_ENDPOINT = "/activity-service/activity/{activity_id}"
GET_ACTIVITY_WEATHER_ENDPOINT = "/activity-service/activity/{activity_id}/weather"
LIST_ACTIVITIES_ENDPOINT = "/activitylist-service/activities/search/activities"
CREATE_WORKOUT_ENDPOINT = "/workout-service/workout"
SCHEDULE_WORKOUT_ENDPOINT = "/workout-service/schedule/{workout_id}"
CALENDAR_WEEK_ENDPOINT = "/calendar-service/year/{year}/month/{month}/day/{day}/start/{start}"
CALENDAR_MONTH_ENDPOINT = "/calendar-service/year/{year}/month/{month}"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

mcp = FastMCP(name="GarminConnectWorkoutsServer")


def _format_garth_error(error: Exception) -> str:
    """
    Add HTTP status/body details when available from garth exceptions.
    """
    http_error = getattr(error, "error", None)
    response = getattr(http_error, "response", None)

    if response is None:
        return str(error)

    try:
        error_body: Any = response.json()
    except Exception:
        error_body = response.text

    return f"{error} | status={response.status_code} | body={error_body}"


def _extract_garth_error_details(error: Exception) -> tuple[int | None, Any]:
    """
    Return HTTP status code and body from a garth-wrapped exception when available.
    """
    http_error = getattr(error, "error", None)
    response = getattr(http_error, "response", None)
    if response is None:
        return None, None

    try:
        body: Any = response.json()
    except Exception:
        body = response.text

    return response.status_code, body


def _is_invalid_category_error(error: Exception) -> bool:
    """
    Detect Garmin write-API invalid category errors.
    """
    status_code, body = _extract_garth_error_details(error)
    if status_code != 400:
        return False

    if isinstance(body, dict):
        message = body.get("message")
        if isinstance(message, str) and "invalid category" in message.lower():
            return True
        error_key = body.get("error")
        if isinstance(error_key, str) and "invalid category" in error_key.lower():
            return True
        return False

    if isinstance(body, str):
        return "invalid category" in body.lower()

    return False


def _iter_strength_executable_steps(workout_data: dict[str, Any]):
    for segment in workout_data.get("workoutSegments", []):
        if not isinstance(segment, dict):
            continue
        for step in segment.get("workoutSteps", []):
            yield from _iter_strength_steps(step)


def _iter_strength_steps(step: dict[str, Any]):
    if not isinstance(step, dict):
        return
    step_type = step.get("type")
    if step_type == "ExecutableStepDTO":
        yield step
        return
    if step_type == "RepeatGroupDTO":
        for child_step in step.get("workoutSteps", []):
            yield from _iter_strength_steps(child_step)


def _normalize_name_for_match(name: str) -> str:
    return name.strip().casefold()


def _find_workouts_by_name(workout_name: str, match_mode: str = "exact") -> list[dict[str, Any]]:
    normalized_match_mode = match_mode.lower().strip()
    if normalized_match_mode not in {"exact", "contains"}:
        raise ValueError("name_match_mode must be either 'exact' or 'contains'.")

    normalized_target = _normalize_name_for_match(workout_name)
    if not normalized_target:
        return []

    workouts = garth.connectapi(LIST_WORKOUTS_ENDPOINT)
    if not isinstance(workouts, list):
        return []

    matches: list[dict[str, Any]] = []
    for workout in workouts:
        if not isinstance(workout, dict):
            continue
        name = workout.get("workoutName")
        workout_id = workout.get("workoutId")
        if not isinstance(name, str) or workout_id is None:
            continue
        normalized_name = _normalize_name_for_match(name)
        if normalized_match_mode == "exact":
            is_match = normalized_name == normalized_target
        else:
            is_match = normalized_target in normalized_name
        if is_match:
            matches.append(workout)

    return matches


def _replace_workouts_by_name(workout_name: str, match_mode: str = "exact") -> list[str]:
    replaced_ids: list[str] = []
    for workout in _find_workouts_by_name(workout_name, match_mode=match_mode):
        workout_id = str(workout.get("workoutId"))
        endpoint = DELETE_WORKOUT_ENDPOINT.format(workout_id=workout_id)
        try:
            garth.connectapi(endpoint, method="DELETE")
            replaced_ids.append(workout_id)
        except Exception as delete_error:
            raise Exception(
                f"Failed to replace existing workout '{workout_name}' (workoutId={workout_id}): "
                f"{_format_garth_error(delete_error)}"
            ) from delete_error
    return replaced_ids


def _infer_category_target(source_category: str) -> str | None:
    if "_" not in source_category:
        return None
    inferred = source_category.split("_", 1)[0].strip()
    if not inferred or inferred == source_category:
        return None
    return inferred


def _build_mapping_guidance(
    original_payload: dict[str, Any],
    applied_mappings: dict[str, Any] | None = None,
) -> str:
    applied_mappings = applied_mappings or {}
    applied_categories = set((applied_mappings.get("categories") or {}).keys())
    applied_exercises = set((applied_mappings.get("exercises") or {}).keys())

    category_mapping = get_strength_category_mapping()
    exercise_mapping = get_strength_exercise_mapping()

    suggested_categories: dict[str, str] = {}
    suggested_exercises: dict[str, str] = {}

    for step in _iter_strength_executable_steps(original_payload):
        category = step.get("category")
        exercise_name = step.get("exerciseName")
        if not isinstance(category, str) or not isinstance(exercise_name, str):
            continue
        category_key = category.strip()
        exercise_key = exercise_name.strip()
        if not category_key or not exercise_key:
            continue

        pair_key = f"{category_key}/{exercise_key}"
        if category_key not in applied_categories:
            suggested_category = category_mapping.get(category_key) or _infer_category_target(category_key)
            if suggested_category and suggested_category != category_key:
                suggested_categories.setdefault(category_key, suggested_category)

        if pair_key in applied_exercises:
            continue

        suggested_exercise = exercise_mapping.get((category_key, exercise_key))
        if suggested_exercise is None:
            candidate_category = suggested_categories.get(category_key)
            if candidate_category:
                suggested_exercise = exercise_mapping.get((candidate_category, exercise_key))
        if suggested_exercise and suggested_exercise != exercise_key:
            suggested_exercises.setdefault(pair_key, suggested_exercise)

    category_items = sorted(suggested_categories.items())[:8]
    exercise_items = sorted(suggested_exercises.items())[:8]

    guidance_parts: list[str] = []
    if category_items:
        category_env = ",".join(f"{source}:{target}" for source, target in category_items)
        guidance_parts.append(f'{CATEGORY_MAPPING_ENV_NAME}="{category_env}"')
    if exercise_items:
        exercise_env = ",".join(f"{source}:{target}" for source, target in exercise_items)
        guidance_parts.append(f'{EXERCISE_MAPPING_ENV_NAME}="{exercise_env}"')

    if not guidance_parts:
        return (
            "No automatic mapping suggestion available. Check Garmin Connect canonical category/exercise "
            f"values and update '{DEFAULT_MAPPING_FILENAME}'."
        )

    return (
        "Mapping suggestion: set "
        + " and ".join(guidance_parts)
        + f", or edit '{DEFAULT_MAPPING_FILENAME}'."
    )

@mcp.tool
def list_workouts() -> dict:
    """
    List all workouts available on Garmin Connect.

    Returns:
        A dictionary containing a list of workouts.
    """
    workouts = garth.connectapi(LIST_WORKOUTS_ENDPOINT)
    return {"workouts": workouts}

@mcp.tool
def get_workout(workout_id: str) -> dict:
    """
    Get details of a specific workout by its ID.

    Args:
        workout_id: ID of the workout to retrieve.

    Returns:
        Workout details as a dictionary.
    """
    endpoint = GET_WORKOUT_ENDPOINT.format(workout_id=workout_id)
    workout = garth.connectapi(endpoint)
    return {"workout": workout}

@mcp.tool
def get_activity(activity_id: str) -> dict:
    """
    Get details of a specific activity by its ID. An activity represents a completed run, ride, swim, etc.

    Args:
        activity_id: ID of the activity to retrieve. As returned by the `get_calendar` tool.

    Returns:
        Activity details as a dictionary.
    """
    endpoint = GET_ACTIVITY_ENDPOINT.format(activity_id=activity_id)
    activity = garth.connectapi(endpoint)
    return {"activity": activity}

@mcp.tool
def list_activities(limit: int = 20, start: int = 0, activityType: str = None, search: str = None) -> dict:
    """
    List activities (completed runs, rides, swims, etc.) from Garmin Connect.

    Args:
        limit: Number of activities to return (default=20)
        start: Starting position for pagination (default=0)
        activityType: Filter by activity type. Accepted values include:
            - "auto_racing", "backcountry_skiing_snowboarding_ws", "bouldering", "breathwork"
            - "cross_country_skiing_ws", "cycling", "diving", "e_sport", "fitness_equipment"
            - "hiking", "indoor_climbing", "motorcycling", "multi_sport", "offshore_grinding"
            - "onshore_grinding", "other", "resort_skiing_snowboarding_ws", "running"
            - "safety", "skate_skiing_ws", "surfing", "swimming", "walking"
            - "windsurfing", "winter_sports", "yoga"
        search: Search for activities containing this string in their name

    Returns:
        A dictionary containing a list of activities and pagination info.
    """
    params = {
        "limit": limit,
        "start": start
    }

    if activityType is not None:
        params["activityType"] = activityType

    if search is not None:
        params["search"] = search

    activities = garth.connectapi(LIST_ACTIVITIES_ENDPOINT, "GET", params=params)
    return {"activities": activities}

@mcp.tool
def get_activity_weather(activity_id: str) -> dict:
    """
    Get weather information for a specific activity.

    Args:
        activity_id: ID of the activity to retrieve weather for.

    Returns:
        Weather details as a dictionary containing temperature, conditions, etc.
    """
    endpoint = GET_ACTIVITY_WEATHER_ENDPOINT.format(activity_id=activity_id)
    weather = garth.connectapi(endpoint)
    return {"weather": weather}

@mcp.tool
def schedule_workout(workout_id: str, date: str) -> dict:
    """
    Schedule a workout on Garmin Connect.

    Args:
        workout_id: ID of the workout to schedule.
        date: Date to schedule the workout in ISO format (YYYY-MM-DD).

    Returns:
        workoutScheduleId: ID of the scheduled workout.

    Raises:
        ValueError: If the date format is incorrect.
        Exception: If scheduling the workout fails.
    """

    # verify date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Date must be in ISO format (YYYY-MM-DD)")

    payload = {
        "date": date,
    }

    endpoint = SCHEDULE_WORKOUT_ENDPOINT.format(workout_id=workout_id)
    result = garth.connectapi(endpoint, method="POST", json=payload)
    workout_scheduled_id = result.get("workoutScheduleId")
    if workout_scheduled_id is None:
        raise Exception(f"Scheduling workout failed: {result}")

    return {"workoutScheduleId": str(workout_scheduled_id)}

@mcp.tool
def delete_workout(workout_id: str) -> bool:
    """
    Delete a workout from Garmin Connect.

    Args:
        workout_id: ID of the workout to delete.

    Returns:
        True if the deletion was successful, False otherwise.
    """
    endpoint = DELETE_WORKOUT_ENDPOINT.format(workout_id=workout_id)

    try:
        garth.connectapi(endpoint, method="DELETE")
        logger.info("Workout %s deleted successfully", workout_id)
        return True
    except Exception as e:
        logger.error("Failed to delete workout %s: %s", workout_id, e)
        return False

@mcp.tool
def upload_workout(workout_data: dict) -> dict:
    """
    Uploads a structured workout to Garmin Connect.

    Args:
        workout_data: Workout data in JSON format to upload. Use the `generate_workout_data_prompt` tool to create a prompt for the LLM to generate this data.

    Returns:
        The uploaded workout's ID on Garmin Connect.

    Raises:
        Exception: If the upload fails or the workout ID is not returned.
    """

    logger.info("Workout data received from client: %s", workout_data)

    if not isinstance(workout_data, dict):
        raise ValueError("workout_data must be an object.")

    if "type" not in workout_data:
        required_native_keys = {"workoutName", "sportType", "workoutSegments"}
        if required_native_keys.issubset(workout_data):
            raise ValueError(
                "upload_workout expects the simplified schema with root 'type'. "
                "Detected native Garmin payload; use upload_strength_workout instead."
            )
        raise ValueError("upload_workout requires root field 'type'.")

    try:
        # Convert to Garmin payload format
        payload = make_payload(workout_data)

        # logging the payload for debugging
        logger.info("Payload to be sent to Garmin Connect: %s", payload)

        # Create workout on Garmin Connect
        result = garth.connectapi("/workout-service/workout", method="POST", json=payload)

        # logging the result for debugging
        logger.info("Response from Garmin Connect: %s", result)

        workout_id = result.get("workoutId")

        if workout_id is None:
            raise Exception("No workout ID returned")

        return {"workoutId": str(workout_id)}

    except ValueError:
        raise
    except Exception as e:
        raise Exception(f"Failed to upload workout to Garmin Connect: {_format_garth_error(e)}")


@mcp.tool
def build_strength_workout(workout_data: dict, input_format: str) -> dict:
    """
    Build and validate a strength workout using Garmin's native workout JSON shape.

    Args:
        workout_data: Workout payload in either "simple" or "native" format.
        input_format: Must be either "simple" or "native".

    Returns:
        A dictionary with a normalized native Garmin strength workout payload.
    """
    if not isinstance(input_format, str):
        raise ValueError("input_format must be 'simple' or 'native'.")

    normalized_input_format = input_format.lower().strip()
    if normalized_input_format not in {"simple", "native"}:
        raise ValueError("input_format must be 'simple' or 'native'.")

    if normalized_input_format == "simple":
        native_workout = build_strength_workout_from_simple(workout_data)
    else:
        native_workout = workout_data

    payload = prepare_strength_workout_payload(native_workout)
    return {"workout": payload}


@mcp.tool
def upload_strength_workout(
    workout_data: dict,
    replace_existing: bool = False,
    name_match_mode: str = "exact",
) -> dict:
    """
    Upload a strength training workout using Garmin's native workout JSON format.

    Args:
        workout_data: Native Garmin strength workout JSON.
        replace_existing: If true, delete existing workouts with the same name before upload.
        name_match_mode: Name matching strategy when replace_existing is true ("exact" or "contains").

    Returns:
        The uploaded workout's ID on Garmin Connect.
    """
    logger.info("Strength workout data received from client: %s", workout_data)

    if isinstance(workout_data, dict) and "workout" in workout_data and "workoutName" not in workout_data:
        nested_workout = workout_data.get("workout")
        if isinstance(nested_workout, dict):
            workout_data = nested_workout

    payload = prepare_strength_workout_payload(workout_data)
    logger.info("Strength workout payload to be sent to Garmin Connect: %s", payload)

    replaced_workout_ids: list[str] = []
    if replace_existing:
        workout_name = payload.get("workoutName")
        if not isinstance(workout_name, str) or not workout_name.strip():
            raise ValueError("replace_existing requires a non-empty workoutName in workout_data.")
        replaced_workout_ids = _replace_workouts_by_name(workout_name, match_mode=name_match_mode)
        if replaced_workout_ids:
            logger.warning(
                "replace_existing enabled: deleted %s existing workout(s) named '%s': %s",
                len(replaced_workout_ids),
                workout_name,
                replaced_workout_ids,
            )

    def _create_strength_workout(request_payload: dict[str, Any]) -> str:
        result = garth.connectapi(CREATE_WORKOUT_ENDPOINT, method="POST", json=request_payload)
        logger.info("Response from Garmin Connect for strength workout: %s", result)

        workout_id = result.get("workoutId")
        if workout_id is None:
            raise Exception("No workout ID returned")
        return str(workout_id)

    try:
        workout_id = _create_strength_workout(payload)
        response: dict[str, Any] = {"workoutId": workout_id}
        if replaced_workout_ids:
            response["replacedWorkoutIds"] = replaced_workout_ids
        return response
    except Exception as first_error:
        if not _is_invalid_category_error(first_error):
            raise Exception(
                f"Failed to upload strength workout to Garmin Connect: {_format_garth_error(first_error)}"
            )

        # Apply exercise remap on original categories first (e.g. DEADLIFT_ROMANIAN/DEADLIFT),
        # then category remap, then a second exercise pass for canonical categories.
        remapped_payload, applied_exercise_mappings_pre = remap_strength_exercises(payload)
        remapped_payload, applied_category_mappings = remap_strength_categories(remapped_payload)
        remapped_payload, applied_exercise_mappings_post = remap_strength_exercises(remapped_payload)

        applied_exercise_mappings = dict(applied_exercise_mappings_pre)
        applied_exercise_mappings.update(applied_exercise_mappings_post)

        applied_mappings: dict[str, Any] = {}
        if applied_category_mappings:
            applied_mappings["categories"] = applied_category_mappings
        if applied_exercise_mappings:
            applied_mappings["exercises"] = applied_exercise_mappings

        if not applied_mappings:
            guidance = _build_mapping_guidance(payload, applied_mappings={})
            raise Exception(
                "Failed to upload strength workout to Garmin Connect: "
                f"{_format_garth_error(first_error)} | guidance={guidance}"
            )

        logger.warning(
            "Retrying strength upload with category remapping after invalid category error. Applied mappings: %s",
            applied_mappings,
        )

        try:
            workout_id = _create_strength_workout(remapped_payload)
            response = {"workoutId": workout_id, "categoryRemaps": applied_mappings}
            if replaced_workout_ids:
                response["replacedWorkoutIds"] = replaced_workout_ids
            return response
        except Exception as remap_error:
            guidance = _build_mapping_guidance(payload, applied_mappings=applied_mappings)
            raise Exception(
                "Failed to upload strength workout to Garmin Connect after category remap. "
                f"first_attempt={_format_garth_error(first_error)} | "
                f"remapped_attempt={_format_garth_error(remap_error)} | "
                f"applied_mappings={applied_mappings} | "
                f"guidance={guidance}"
            )

@mcp.tool
def get_calendar(year: int, month: int, day: int = None, start: int = 1) -> dict:
    """
    Get calendar data from Garmin Connect for different time periods.

    Args:
        year: Year (e.g., 2025)
        month: Month (1-12)
        day: Day of month (1-31). If provided, gets corresponding weekly view that includes this day.
             If omitted, gets monthly view for the entire month.
        start: Day offset for weekly queries (defaults to 1). Controls which day of the week
               the 7-day period begins. Each increment shifts the start date forward by one day:
               - start=0: Week starts on Sunday
               - start=1: Week starts on Monday (DEFAULT)
               - start=2: Week starts on Tuesday
               - start=3: Week starts on Wednesday
               - start=4: Week starts on Thursday
               And so on. Different start values return different 7-day windows with varying
               calendar items, useful for different training schedules and calendar preferences.

    Returns:
        Calendar data with workouts and activities for the specified period.

    Raises:
        ValueError: If any of the date parameters are invalid.
    """
    # Input validation
    if not (1900 <= year <= 2100):
        raise ValueError(f"Year must be between 1900 and 2100, got {year}")

    if not (1 <= month <= 12):
        raise ValueError(f"Month must be between 1 and 12, got {month}")

    if day is not None:
        if not (1 <= day <= 31):
            raise ValueError(f"Day must be between 1 and 31, got {day}")
        try:
            datetime(year, month, day)
        except ValueError:
            raise ValueError(f"Invalid date: {year}-{month:02d}-{day:02d}")

    # Convert month from 1-based (human readable) to 0-based (Garmin API)
    garmin_month = month - 1

    if day is not None:
        # Weekly view
        endpoint = CALENDAR_WEEK_ENDPOINT.format(
            year=year, month=garmin_month, day=day, start=start
        )
        view_type = "week"
    else:
        # Monthly view (default)
        endpoint = CALENDAR_MONTH_ENDPOINT.format(
            year=year, month=garmin_month
        )
        view_type = "month"

    calendar_data = garth.connectapi(endpoint)

    return {
        "calendar": calendar_data,
        "view_type": view_type,
        "period": {
            "year": year,
            "month": month,
            "day": day,
            "start": start if day else None
        }
    }

@mcp.tool
def generate_workout_data_prompt(description: str) -> dict:
    """
    Generate prompt for LLM to create structured workout data based on a natural language description. The LLM
    should use the returned prompt to generate a JSON object that can then be used with the `upload_workout` tool.

    Args:
        description: Natural language description of the workout

    Returns:
        Prompt for the LLM to generate structured workout data
    """

    return {"prompt": f"""
    You are a fitness coach.
    Given the following workout description, create a structured JSON object that represents the workout.
    The generated JSON should be compatible with the `upload_workout` tool.

    Workout Description:
    {description}

    Requirements:
    - The output must be valid JSON.
    - For pace targets, use decimal minutes per km (e.g., 4:40 min/km = 4.67 minutes per km)
    - For time-based steps, use stepDuration in seconds
    - For distance-based steps, use stepDistance with appropriate distanceUnit
    - Use the following structure for the workout object:
    {{
    "name": "Workout Name",
    "type": "running" | "cycling" | "swimming" | "walking" | "cardio" | "strength",
    "steps": [
        {{
        "stepName": "Step Name",
        "stepDescription": "Description",
        "endConditionType": "time" | "distance",
        "stepDuration": duration_in_seconds,
        "stepDistance": distance_value,
        "distanceUnit": "m" | "km" | "mile",
        "stepType": "warmup" | "cooldown" | "interval" | "recovery" | "rest" | "repeat",
        "target": {{
            "type": "no target" | "pace" | "heart rate" | "power" | "cadence" | "speed",
            "value": [minValue, maxValue] | singleValue,
            "unit": "min_per_km" | "bpm" | "watts"
        }},
        "numberOfIterations": number,
        "steps": []
        }}
    ]
    }}

    Examples:
    - For 4:40 min/km pace: "value": 4.67 or "value": [4.5, 4.8]
    - For 160 bpm heart rate: "value": 160 or "value": [150, 170]
    - For no target: "type": "no target", "value": null, "unit": null
    """}

def login():
    """Login to Garmin Connect."""
    garth_home = os.environ.get("GARTH_HOME", "~/.garth")
    try:
        garth.resume(garth_home)
    except Exception:
        email = os.environ.get("GARMIN_EMAIL")
        password = os.environ.get("GARMIN_PASSWORD")

        if not email or not password:
            raise ValueError("Garmin email and password must be provided via environment variables (GARMIN_EMAIL, GARMIN_PASSWORD).")

        try:
            garth.login(email, password)
        except Exception as e:
            logger.error("Login failed: %s", e)
            sys.exit(1)

        # Save credentials for future use
        garth.save(garth_home)

def main():
    """Main entry point for the console script."""
    login()
    mcp.run()

if __name__ == "__main__":
    main()
