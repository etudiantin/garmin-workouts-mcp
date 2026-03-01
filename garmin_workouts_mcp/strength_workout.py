from __future__ import annotations

import copy
import csv
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


STRENGTH_SPORT_TYPE = {
    "sportTypeId": 5,
    "sportTypeKey": "strength_training",
}

NO_TARGET_TYPE = {
    "workoutTargetTypeId": 1,
    "workoutTargetTypeKey": "no.target",
}

KILOGRAM_UNIT = {
    "unitId": 8,
    "unitKey": "kilogram",
    "factor": 1000.0,
}

STEP_TYPE_MAPPING = {
    "warmup": {"stepTypeId": 1, "stepTypeKey": "warmup"},
    "interval": {"stepTypeId": 3, "stepTypeKey": "interval"},
    "rest": {"stepTypeId": 5, "stepTypeKey": "rest"},
    "repeat": {"stepTypeId": 6, "stepTypeKey": "repeat"},
}

END_CONDITION_MAPPING = {
    "lap.button": {"conditionTypeId": 1, "conditionTypeKey": "lap.button"},
    "time": {"conditionTypeId": 2, "conditionTypeKey": "time"},
    "iterations": {"conditionTypeId": 7, "conditionTypeKey": "iterations"},
    "reps": {"conditionTypeId": 10, "conditionTypeKey": "reps"},
}

DEFAULT_CSV_FILENAME = "garmin_exercises_keys_en_fr.csv"
CSV_ENV_NAME = "GARMIN_STRENGTH_EXERCISES_CSV"
CATEGORY_MAPPING_ENV_NAME = "GARMIN_STRENGTH_CATEGORY_MAPPING"
EXERCISE_MAPPING_ENV_NAME = "GARMIN_STRENGTH_EXERCISE_MAPPING"
MAPPING_FILE_ENV_NAME = "GARMIN_STRENGTH_MAPPING_FILE"
DEFAULT_MAPPING_FILENAME = "garmin_workouts_mcp/config/strength_mapping.json"
PACKAGE_MAPPING_FILENAME = "config/strength_mapping.json"
LEGACY_REPO_MAPPING_FILENAME = "config/strength_mapping.json"
SUPPORTED_STRENGTH_STEP_TYPES = {"ExecutableStepDTO", "RepeatGroupDTO"}


def _resolve_strength_mapping_path(mapping_path: str | None = None) -> Path | None:
    if mapping_path:
        path = Path(mapping_path).expanduser()
    elif os.environ.get(MAPPING_FILE_ENV_NAME):
        path = Path(os.environ[MAPPING_FILE_ENV_NAME]).expanduser()
    else:
        package_root = Path(__file__).resolve().parent
        path = package_root / PACKAGE_MAPPING_FILENAME
        if not path.exists() or not path.is_file():
            # Backward compatibility with legacy repo layout.
            legacy_repo_root = package_root.parent
            path = legacy_repo_root / LEGACY_REPO_MAPPING_FILENAME

    if not path.exists() or not path.is_file():
        return None
    return path


@lru_cache(maxsize=4)
def _load_strength_mappings_from_file(
    mapping_path: str,
) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    with open(mapping_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Strength mapping file must be a JSON object.")

    raw_categories = data.get("categoryMapping", {})
    raw_exercises = data.get("exerciseMapping", {})

    if not isinstance(raw_categories, dict):
        raise ValueError("strength mapping file key 'categoryMapping' must be an object.")
    if not isinstance(raw_exercises, dict):
        raise ValueError("strength mapping file key 'exerciseMapping' must be an object.")

    category_mapping: dict[str, str] = {}
    exercise_mapping: dict[tuple[str, str], str] = {}

    for source, target in raw_categories.items():
        source_key = _normalize_optional_string(source)
        target_key = _normalize_optional_string(target)
        if not source_key or not target_key:
            continue
        category_mapping[source_key] = target_key

    for source_pair, target in raw_exercises.items():
        source_pair_key = _normalize_optional_string(source_pair)
        target_key = _normalize_optional_string(target)
        if not source_pair_key or not target_key:
            continue
        source_category, separator, source_exercise = source_pair_key.partition("/")
        source_category = source_category.strip()
        source_exercise = source_exercise.strip()
        if separator != "/" or not source_category or not source_exercise:
            raise ValueError(
                "Invalid exerciseMapping key in strength mapping file. "
                "Use format 'CATEGORY/EXERCISE_NAME'."
            )
        exercise_mapping[(source_category, source_exercise)] = target_key

    return category_mapping, exercise_mapping


def build_strength_step(
    category: str,
    exercise_name: str,
    reps: int | None = None,
    duration_seconds: float | None = None,
    weight_kg: float = -1.0,
    step_type: str = "interval",
    description: str | None = None,
) -> dict[str, Any]:
    """
    Build a strength exercise step in Garmin native format.
    """
    if not category or not exercise_name:
        raise ValueError("Exercise steps require both category and exerciseName.")

    step_type_key = step_type.lower()
    if step_type_key not in {"warmup", "interval"}:
        raise ValueError("Exercise stepType must be either 'warmup' or 'interval'.")

    has_reps = reps is not None
    has_duration = duration_seconds is not None
    if has_reps == has_duration:
        raise ValueError("Exercise step must define exactly one of reps or durationSeconds.")

    if has_reps and (not isinstance(reps, int) or reps <= 0):
        raise ValueError("reps must be a positive integer.")
    if has_duration and (not isinstance(duration_seconds, (int, float)) or duration_seconds <= 0):
        raise ValueError("durationSeconds must be a positive number.")

    condition_key = "reps" if has_reps else "time"
    condition_value = float(reps) if has_reps else float(duration_seconds)

    return {
        "type": "ExecutableStepDTO",
        "stepId": None,
        "description": description,
        "stepType": copy.deepcopy(STEP_TYPE_MAPPING[step_type_key]),
        "endCondition": copy.deepcopy(END_CONDITION_MAPPING[condition_key]),
        "endConditionValue": condition_value,
        "targetType": copy.deepcopy(NO_TARGET_TYPE),
        "targetValueOne": None,
        "targetValueTwo": None,
        "zoneNumber": None,
        "category": category,
        "exerciseName": exercise_name,
        "weightValue": float(weight_kg),
        "weightUnit": copy.deepcopy(KILOGRAM_UNIT),
    }


def build_rest_step(duration_seconds: float | None = None) -> dict[str, Any]:
    """
    Build a rest step in Garmin native format.
    """
    if duration_seconds is None:
        condition_key = "lap.button"
        condition_value = 0.0
    else:
        if not isinstance(duration_seconds, (int, float)) or duration_seconds <= 0:
            raise ValueError("durationSeconds must be a positive number when provided.")
        condition_key = "time"
        condition_value = float(duration_seconds)

    return {
        "type": "ExecutableStepDTO",
        "stepId": None,
        "description": None,
        "stepType": copy.deepcopy(STEP_TYPE_MAPPING["rest"]),
        "endCondition": copy.deepcopy(END_CONDITION_MAPPING[condition_key]),
        "endConditionValue": condition_value,
        "targetType": copy.deepcopy(NO_TARGET_TYPE),
        "targetValueOne": None,
        "targetValueTwo": None,
        "zoneNumber": None,
        "category": None,
        "exerciseName": None,
        "weightValue": -1.0,
        "weightUnit": copy.deepcopy(KILOGRAM_UNIT),
    }


def build_repeat_group(
    iterations: int,
    steps: list[dict[str, Any]],
    skip_last_rest: bool = True,
) -> dict[str, Any]:
    """
    Build a repeat group in Garmin native format.
    """
    if not isinstance(iterations, int) or iterations <= 0:
        raise ValueError("iterations must be a positive integer.")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Repeat steps must be a non-empty list.")

    return {
        "type": "RepeatGroupDTO",
        "stepId": None,
        "stepType": copy.deepcopy(STEP_TYPE_MAPPING["repeat"]),
        "numberOfIterations": iterations,
        "workoutSteps": copy.deepcopy(steps),
        "endCondition": copy.deepcopy(END_CONDITION_MAPPING["iterations"]),
        "endConditionValue": float(iterations),
        "skipLastRestStep": bool(skip_last_rest),
        "smartRepeat": False,
    }


def build_strength_workout_native(
    name: str,
    description: str | None,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Build a complete native Garmin strength workout payload.
    """
    if not name:
        raise ValueError("Workout name is required.")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Workout steps must be a non-empty list.")

    return {
        "workoutName": name,
        "description": description,
        "sportType": copy.deepcopy(STRENGTH_SPORT_TYPE),
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "sportType": copy.deepcopy(STRENGTH_SPORT_TYPE),
                "workoutSteps": copy.deepcopy(steps),
            }
        ],
    }


def build_strength_workout_from_simple(workout_data: dict[str, Any]) -> dict[str, Any]:
    """
    Build a native Garmin strength workout from the simplified schema.
    """
    if not isinstance(workout_data, dict):
        raise ValueError("workout_data must be an object.")

    name = workout_data.get("name")
    description = workout_data.get("description")
    steps = workout_data.get("steps")

    if not name:
        raise ValueError("Simple strength workout requires 'name'.")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Simple strength workout requires a non-empty 'steps' list.")

    native_steps = [_build_simple_step(step) for step in steps]
    return build_strength_workout_native(name=name, description=description, steps=native_steps)


def _build_simple_step(step: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(step, dict):
        raise ValueError("Each simple step must be an object.")

    step_kind = step.get("type")
    if not isinstance(step_kind, str):
        raise ValueError("Each simple step requires a string 'type'.")

    normalized_kind = step_kind.lower()
    if normalized_kind == "exercise":
        return build_strength_step(
            category=step.get("category"),
            exercise_name=step.get("exerciseName"),
            reps=step.get("reps"),
            duration_seconds=step.get("durationSeconds"),
            weight_kg=step.get("weightKg", -1.0),
            step_type=step.get("stepType", "interval"),
            description=step.get("description"),
        )

    if normalized_kind == "rest":
        return build_rest_step(step.get("durationSeconds"))

    if normalized_kind == "repeat":
        nested_steps = step.get("steps")
        if not isinstance(nested_steps, list) or not nested_steps:
            raise ValueError("Repeat step requires a non-empty 'steps' list.")
        iterations = step.get("iterations")
        skip_last_rest = step.get("skipLastRest", True)
        built_steps = [_build_simple_step(child_step) for child_step in nested_steps]
        return build_repeat_group(iterations=iterations, steps=built_steps, skip_last_rest=skip_last_rest)

    raise ValueError(f"Unsupported simple step type: {step_kind}")


def validate_strength_root_structure(workout_data: dict[str, Any]) -> None:
    """
    Validate the minimal expected native structure for strength workouts.
    """
    if not isinstance(workout_data, dict):
        raise ValueError("workout_data must be an object.")

    workout_name = workout_data.get("workoutName")
    if not isinstance(workout_name, str) or not workout_name.strip():
        raise ValueError("workoutName is required for strength workouts.")

    sport_type = workout_data.get("sportType")
    if not isinstance(sport_type, dict) or sport_type.get("sportTypeKey") != "strength_training":
        raise ValueError("sportType.sportTypeKey must be 'strength_training'.")

    workout_segments = workout_data.get("workoutSegments")
    if not isinstance(workout_segments, list) or not workout_segments:
        raise ValueError("workoutSegments must be a non-empty list.")

    for segment_index, segment in enumerate(workout_segments, start=1):
        if not isinstance(segment, dict):
            raise ValueError(f"workoutSegments[{segment_index}] must be an object.")

        steps = segment.get("workoutSteps")
        if not isinstance(steps, list) or not steps:
            raise ValueError(
                f"workoutSegments[{segment_index}].workoutSteps must be a non-empty list."
            )
        _validate_steps_recursive(steps, location=f"workoutSegments[{segment_index}].workoutSteps")


def _validate_steps_recursive(steps: list[dict[str, Any]], location: str) -> None:
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ValueError(f"{location}[{index}] must be an object.")
        step_type = step.get("type")
        if step_type not in SUPPORTED_STRENGTH_STEP_TYPES:
            raise ValueError(
                f"{location}[{index}].type must be one of {sorted(SUPPORTED_STRENGTH_STEP_TYPES)}."
            )
        if step_type == "RepeatGroupDTO":
            iterations = step.get("numberOfIterations")
            if not isinstance(iterations, int) or iterations <= 0:
                raise ValueError(f"{location}[{index}].numberOfIterations must be a positive integer.")
            child_steps = step.get("workoutSteps")
            if not isinstance(child_steps, list) or not child_steps:
                raise ValueError(f"{location}[{index}].workoutSteps must be a non-empty list.")
            _validate_steps_recursive(child_steps, location=f"{location}[{index}].workoutSteps")


def normalize_strength_workout(workout_data: dict[str, Any]) -> dict[str, Any]:
    """
    Return a deep-copied native workout payload with deterministic numbering.
    """
    normalized = copy.deepcopy(workout_data)

    next_step_order = 1
    for segment_order, segment in enumerate(normalized["workoutSegments"], start=1):
        segment["segmentOrder"] = segment_order
        next_step_order = _normalize_steps(steps=segment["workoutSteps"], next_step_order=next_step_order)

    return normalized


def _normalize_steps(
    steps: list[dict[str, Any]],
    next_step_order: int,
    assign_child_step_id: bool = False,
) -> int:
    # Garmin expects deterministic ordering. We assign stepOrder depth-first so
    # nested repeat-group children are contiguous and reproducible.
    for child_index, step in enumerate(steps, start=1):
        if "stepId" not in step:
            step["stepId"] = None

        step["stepOrder"] = next_step_order
        next_step_order += 1

        if assign_child_step_id:
            step["childStepId"] = child_index

        if step.get("type") == "RepeatGroupDTO":
            child_steps = step.get("workoutSteps", [])
            next_step_order = _normalize_steps(
                steps=child_steps,
                next_step_order=next_step_order,
                assign_child_step_id=True,
            )

    return next_step_order


def prepare_strength_workout_payload(
    workout_data: dict[str, Any],
    csv_path: str | None = None,
) -> dict[str, Any]:
    """
    Validate, normalize and CSV-check a native strength workout payload.
    """
    validate_strength_root_structure(workout_data)
    normalized = normalize_strength_workout(workout_data)
    validate_strength_exercise_pairs(normalized, csv_path=csv_path)
    return normalized


def validate_strength_exercise_pairs(workout_data: dict[str, Any], csv_path: str | None = None) -> None:
    """
    Validate that all category/exerciseName pairs are known in the CSV reference.
    """
    exercises = _load_exercise_pairs(str(_resolve_exercise_csv_path(csv_path)))

    for step in _iter_executable_steps(workout_data):
        category = _normalize_optional_string(step.get("category"))
        exercise_name = _normalize_optional_string(step.get("exerciseName"))

        if category is None and exercise_name is None:
            continue

        if category is None or exercise_name is None:
            raise ValueError("Both category and exerciseName must be set together for exercise steps.")

        if (category, exercise_name) not in exercises:
            raise ValueError(
                f"Unknown Garmin exercise pair category='{category}', exerciseName='{exercise_name}'."
            )


def _iter_executable_steps(workout_data: dict[str, Any]):
    for segment in workout_data.get("workoutSegments", []):
        for step in segment.get("workoutSteps", []):
            yield from _iter_steps(step)


def _iter_steps(step: dict[str, Any]):
    if step.get("type") == "ExecutableStepDTO":
        yield step
        return
    if step.get("type") == "RepeatGroupDTO":
        for child_step in step.get("workoutSteps", []):
            yield from _iter_steps(child_step)


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return str(value)


def get_strength_category_mapping(
    mapping: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """
    Build category mapping used to improve Garmin write-API compatibility.
    """
    resolved_mapping: dict[str, str] = {}

    mapping_path = _resolve_strength_mapping_path()
    if mapping_path is not None:
        file_category_mapping, _ = _load_strength_mappings_from_file(str(mapping_path))
        resolved_mapping.update(file_category_mapping)

    env_mapping = os.environ.get(CATEGORY_MAPPING_ENV_NAME, "").strip()
    if env_mapping:
        for entry in env_mapping.split(","):
            pair = entry.strip()
            if not pair:
                continue
            source, separator, target = pair.partition(":")
            source = source.strip()
            target = target.strip()
            if separator != ":" or not source or not target:
                raise ValueError(
                    f"Invalid {CATEGORY_MAPPING_ENV_NAME} entry '{entry}'. "
                    "Use format 'SOURCE:TARGET,SOURCE2:TARGET2'."
                )
            resolved_mapping[source] = target

    if mapping:
        for source, target in mapping.items():
            source_key = _normalize_optional_string(source)
            target_key = _normalize_optional_string(target)
            if not source_key or not target_key:
                continue
            resolved_mapping[source_key] = target_key

    return resolved_mapping


def get_strength_exercise_mapping(
    mapping: Mapping[tuple[str, str], str] | None = None,
) -> dict[tuple[str, str], str]:
    """
    Build exercise-name mapping used to improve Garmin write-API compatibility.
    """
    resolved_mapping: dict[tuple[str, str], str] = {}

    mapping_path = _resolve_strength_mapping_path()
    if mapping_path is not None:
        _, file_exercise_mapping = _load_strength_mappings_from_file(str(mapping_path))
        resolved_mapping.update(file_exercise_mapping)

    env_mapping = os.environ.get(EXERCISE_MAPPING_ENV_NAME, "").strip()
    if env_mapping:
        for entry in env_mapping.split(","):
            pair = entry.strip()
            if not pair:
                continue
            source_pair, separator, target = pair.partition(":")
            source_pair = source_pair.strip()
            target = target.strip()
            source_category, category_separator, source_exercise = source_pair.partition("/")
            source_category = source_category.strip()
            source_exercise = source_exercise.strip()
            if (
                separator != ":"
                or category_separator != "/"
                or not source_category
                or not source_exercise
                or not target
            ):
                raise ValueError(
                    f"Invalid {EXERCISE_MAPPING_ENV_NAME} entry '{entry}'. "
                    "Use format 'CATEGORY/EXERCISE:TARGET,CATEGORY2/EXERCISE2:TARGET2'."
                )
            resolved_mapping[(source_category, source_exercise)] = target

    if mapping:
        for key, value in mapping.items():
            if not isinstance(key, tuple) or len(key) != 2:
                continue
            source_category = _normalize_optional_string(key[0])
            source_exercise = _normalize_optional_string(key[1])
            target_exercise = _normalize_optional_string(value)
            if not source_category or not source_exercise or not target_exercise:
                continue
            resolved_mapping[(source_category, source_exercise)] = target_exercise

    return resolved_mapping


def remap_strength_categories(
    workout_data: dict[str, Any],
    mapping: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """
    Return a deep-copied workout with remapped categories and the applied map.
    """
    resolved_mapping = get_strength_category_mapping(mapping=mapping)
    remapped_workout = copy.deepcopy(workout_data)
    applied_mappings: dict[str, str] = {}

    for step in _iter_executable_steps(remapped_workout):
        category = _normalize_optional_string(step.get("category"))
        if category is None:
            continue
        remapped_category = resolved_mapping.get(category)
        if remapped_category is None or remapped_category == category:
            continue
        step["category"] = remapped_category
        applied_mappings[category] = remapped_category

    return remapped_workout, applied_mappings


def remap_strength_exercises(
    workout_data: dict[str, Any],
    mapping: Mapping[tuple[str, str], str] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """
    Return a deep-copied workout with remapped exercise names and applied map.
    """
    resolved_mapping = get_strength_exercise_mapping(mapping=mapping)

    remapped_workout = copy.deepcopy(workout_data)
    applied_mappings: dict[str, str] = {}

    for step in _iter_executable_steps(remapped_workout):
        category = _normalize_optional_string(step.get("category"))
        exercise_name = _normalize_optional_string(step.get("exerciseName"))
        if category is None or exercise_name is None:
            continue

        source_key = (category, exercise_name)
        remapped_exercise = resolved_mapping.get(source_key)
        if remapped_exercise is None or remapped_exercise == exercise_name:
            continue

        step["exerciseName"] = remapped_exercise
        applied_mappings[f"{category}/{exercise_name}"] = remapped_exercise

    return remapped_workout, applied_mappings


def _resolve_exercise_csv_path(csv_path: str | None = None) -> Path:
    if csv_path:
        path = Path(csv_path).expanduser()
    elif os.environ.get(CSV_ENV_NAME):
        path = Path(os.environ[CSV_ENV_NAME]).expanduser()
    else:
        repo_root = Path(__file__).resolve().parent.parent
        path = repo_root / DEFAULT_CSV_FILENAME

    if not path.exists() or not path.is_file():
        raise ValueError(
            f"Exercise CSV file not found: {path}. Set {CSV_ENV_NAME} or place "
            f"{DEFAULT_CSV_FILENAME} at the repository root."
        )

    return path


@lru_cache(maxsize=8)
def _load_exercise_pairs(csv_path: str) -> set[tuple[str, str]]:
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as csv_handle:
            reader = csv.DictReader(csv_handle)
            if not reader.fieldnames:
                raise ValueError("Exercise CSV is empty.")

            missing_columns = {"key", "category"} - set(reader.fieldnames)
            if missing_columns:
                missing_list = ", ".join(sorted(missing_columns))
                raise ValueError(f"Exercise CSV missing required columns: {missing_list}")

            exercise_pairs: set[tuple[str, str]] = set()
            for row in reader:
                key = (row.get("key") or "").strip()
                category = (row.get("category") or "").strip()

                if not key or not category:
                    continue

                expected_prefix = f"{category}_"
                if key.startswith(expected_prefix):
                    # Garmin key format is CATEGORY_EXERCISE_NAME. The API payload
                    # requires category + exerciseName separately.
                    exercise_name = key[len(expected_prefix):].strip()
                    if exercise_name:
                        exercise_pairs.add((category, exercise_name))
                    continue

                if key == category:
                    # Some rows are self-keyed (e.g. PLANK_PLANK,PLANK_PLANK).
                    # Accept both the full key and the trailing token form so
                    # native Garmin payloads like PLANK_PLANK/PLANK are not rejected.
                    exercise_pairs.add((category, category))
                    trailing_token = category.rsplit("_", 1)[-1].strip()
                    if trailing_token:
                        exercise_pairs.add((category, trailing_token))

            if not exercise_pairs:
                raise ValueError("Exercise CSV did not yield any valid (category, exerciseName) pairs.")

            return exercise_pairs
    except OSError as exc:
        raise ValueError(f"Unable to read exercise CSV file: {csv_path}") from exc
