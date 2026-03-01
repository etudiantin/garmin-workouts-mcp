from __future__ import annotations

import logging
from typing import Any, Callable

import garth

from .strength_workout import (
    CATEGORY_MAPPING_ENV_NAME,
    DEFAULT_MAPPING_FILENAME,
    EXERCISE_MAPPING_ENV_NAME,
    get_strength_category_mapping,
    get_strength_exercise_mapping,
    remap_strength_categories,
    remap_strength_exercises,
)

LIST_WORKOUTS_ENDPOINT = "/workout-service/workouts"
GET_WORKOUT_ENDPOINT = "/workout-service/workout/{workout_id}"
DELETE_WORKOUT_ENDPOINT = "/workout-service/workout/{workout_id}"
CREATE_WORKOUT_ENDPOINT = "/workout-service/workout"
STRENGTH_SPORT_TYPE_KEY = "strength_training"

ConnectApiFn = Callable[..., Any]
FormatErrorFn = Callable[[Exception], str]


def _default_format_error(error: Exception) -> str:
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


def _extract_workout_sport_type_key(workout: dict[str, Any]) -> str | None:
    sport_type = workout.get("sportType")
    if isinstance(sport_type, dict):
        sport_type_key = sport_type.get("sportTypeKey")
        if isinstance(sport_type_key, str) and sport_type_key.strip():
            return sport_type_key.strip().lower()

    sport_type_key = workout.get("sportTypeKey")
    if isinstance(sport_type_key, str) and sport_type_key.strip():
        return sport_type_key.strip().lower()

    return None


def _workout_matches_sport_type(
    workout: dict[str, Any],
    connectapi_fn: ConnectApiFn,
    logger: logging.Logger,
    format_error: FormatErrorFn,
    sport_type_key: str | None = None,
) -> bool:
    if not sport_type_key:
        return True

    normalized_sport_type_key = sport_type_key.strip().lower()
    if not normalized_sport_type_key:
        return True

    resolved_sport_type_key = _extract_workout_sport_type_key(workout)
    if resolved_sport_type_key is None:
        workout_id = workout.get("workoutId")
        if workout_id is None:
            return False
        endpoint = GET_WORKOUT_ENDPOINT.format(workout_id=workout_id)
        try:
            workout_details = connectapi_fn(endpoint)
        except Exception as inspect_error:
            logger.warning(
                "Skipping replacement candidate workoutId=%s: unable to inspect sportType (%s)",
                workout_id,
                format_error(inspect_error),
            )
            return False
        if isinstance(workout_details, dict):
            resolved_sport_type_key = _extract_workout_sport_type_key(workout_details)

    return resolved_sport_type_key == normalized_sport_type_key


def _find_workouts_by_name(
    workout_name: str,
    connectapi_fn: ConnectApiFn,
    logger: logging.Logger,
    format_error: FormatErrorFn,
    match_mode: str = "exact",
    sport_type_key: str | None = None,
) -> list[dict[str, Any]]:
    normalized_match_mode = match_mode.lower().strip()
    if normalized_match_mode not in {"exact", "contains"}:
        raise ValueError("name_match_mode must be either 'exact' or 'contains'.")

    normalized_target = _normalize_name_for_match(workout_name)
    if not normalized_target:
        return []

    workouts = connectapi_fn(LIST_WORKOUTS_ENDPOINT)
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
        if is_match and _workout_matches_sport_type(
            workout,
            connectapi_fn=connectapi_fn,
            logger=logger,
            format_error=format_error,
            sport_type_key=sport_type_key,
        ):
            matches.append(workout)

    return matches


def _delete_workouts(
    workouts: list[dict[str, Any]],
    workout_name: str,
    connectapi_fn: ConnectApiFn,
    logger: logging.Logger,
    format_error: FormatErrorFn,
    created_workout_id: str | None = None,
) -> tuple[list[str], list[str]]:
    replaced_ids: list[str] = []
    cleanup_errors: list[str] = []

    for workout in workouts:
        workout_id = workout.get("workoutId")
        if workout_id is None:
            continue
        workout_id = str(workout_id)
        if created_workout_id is not None and workout_id == created_workout_id:
            continue
        endpoint = DELETE_WORKOUT_ENDPOINT.format(workout_id=workout_id)
        try:
            connectapi_fn(endpoint, method="DELETE")
            replaced_ids.append(workout_id)
        except Exception as delete_error:
            cleanup_errors.append(f"workoutId={workout_id}: {format_error(delete_error)}")

    if cleanup_errors:
        logger.error(
            "replace_existing cleanup had %s deletion error(s) for '%s': %s",
            len(cleanup_errors),
            workout_name,
            cleanup_errors,
        )

    return replaced_ids, cleanup_errors


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


def upload_strength_workout_payload(
    payload: dict[str, Any],
    *,
    replace_existing: bool = False,
    name_match_mode: str = "exact",
    connectapi_fn: ConnectApiFn | None = None,
    format_error: FormatErrorFn | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    connectapi_fn = connectapi_fn or garth.connectapi
    format_error = format_error or _default_format_error
    logger = logger or logging.getLogger(__name__)

    replacement_candidates: list[dict[str, Any]] = []
    replaced_workout_ids: list[str] = []
    replacement_cleanup_errors: list[str] = []
    if replace_existing:
        workout_name = payload.get("workoutName")
        if not isinstance(workout_name, str) or not workout_name.strip():
            raise ValueError("replace_existing requires a non-empty workoutName in workout_data.")
        replacement_candidates = _find_workouts_by_name(
            workout_name,
            connectapi_fn=connectapi_fn,
            logger=logger,
            format_error=format_error,
            match_mode=name_match_mode,
            sport_type_key=STRENGTH_SPORT_TYPE_KEY,
        )
        if replacement_candidates:
            candidate_ids = [str(workout.get("workoutId")) for workout in replacement_candidates]
            logger.warning(
                "replace_existing enabled: %s existing strength workout(s) named '%s' will be deleted "
                "after successful upload: %s",
                len(replacement_candidates),
                workout_name,
                candidate_ids,
            )

    def _create_strength_workout(request_payload: dict[str, Any]) -> str:
        result = connectapi_fn(CREATE_WORKOUT_ENDPOINT, method="POST", json=request_payload)
        logger.info("Response from Garmin Connect for strength workout: %s", result)

        workout_id = result.get("workoutId")
        if workout_id is None:
            raise Exception("No workout ID returned")
        return str(workout_id)

    try:
        workout_id = _create_strength_workout(payload)
        if replacement_candidates:
            replaced_workout_ids, replacement_cleanup_errors = _delete_workouts(
                replacement_candidates,
                payload.get("workoutName", ""),
                connectapi_fn=connectapi_fn,
                logger=logger,
                format_error=format_error,
                created_workout_id=workout_id,
            )
        response: dict[str, Any] = {"workoutId": workout_id}
        if replaced_workout_ids:
            response["replacedWorkoutIds"] = replaced_workout_ids
        if replacement_cleanup_errors:
            response["replacementCleanupErrors"] = replacement_cleanup_errors
        return response
    except Exception as first_error:
        if not _is_invalid_category_error(first_error):
            raise Exception(
                f"Failed to upload strength workout to Garmin Connect: {format_error(first_error)}"
            )

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
                f"{format_error(first_error)} | guidance={guidance}"
            )

        logger.warning(
            "Retrying strength upload with category remapping after invalid category error. Applied mappings: %s",
            applied_mappings,
        )

        try:
            workout_id = _create_strength_workout(remapped_payload)
            if replacement_candidates:
                replaced_workout_ids, replacement_cleanup_errors = _delete_workouts(
                    replacement_candidates,
                    payload.get("workoutName", ""),
                    connectapi_fn=connectapi_fn,
                    logger=logger,
                    format_error=format_error,
                    created_workout_id=workout_id,
                )
            response = {"workoutId": workout_id, "categoryRemaps": applied_mappings}
            if replaced_workout_ids:
                response["replacedWorkoutIds"] = replaced_workout_ids
            if replacement_cleanup_errors:
                response["replacementCleanupErrors"] = replacement_cleanup_errors
            return response
        except Exception as remap_error:
            guidance = _build_mapping_guidance(payload, applied_mappings=applied_mappings)
            raise Exception(
                "Failed to upload strength workout to Garmin Connect after category remap. "
                f"first_attempt={format_error(first_error)} | "
                f"remapped_attempt={format_error(remap_error)} | "
                f"applied_mappings={applied_mappings} | "
                f"guidance={guidance}"
            )
