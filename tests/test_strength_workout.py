import pytest

from garmin_workouts_mcp.strength_workout import (
    build_repeat_group,
    build_rest_step,
    build_strength_step,
    build_strength_workout_from_simple,
    build_strength_workout_native,
    normalize_strength_workout,
    prepare_strength_workout_payload,
    validate_strength_exercise_pairs,
    validate_strength_root_structure,
)


def _write_exercise_csv(tmp_path):
    csv_path = tmp_path / "exercise_keys.csv"
    csv_path.write_text(
        "\n".join(
            [
                "key,category,language_en,name_en,language_fr,name_fr",
                "BENCH_PRESS_DUMBBELL_BENCH_PRESS,BENCH_PRESS,en,Dumbbell Bench Press,fr,Test",
                "ROW_FACE_PULL,ROW,en,Face Pull,fr,Test",
                "BANDED_EXERCISES_INTERNAL_ROTATION,BANDED_EXERCISES,en,Internal Rotation,fr,Test",
            ]
        ),
        encoding="utf-8",
    )
    return str(csv_path)


def _make_native_strength_workout():
    return {
        "workoutName": "Push Day",
        "description": "Strength session",
        "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training"},
        "workoutSegments": [
            {
                "segmentOrder": 99,
                "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training"},
                "workoutSteps": [
                    {
                        "type": "ExecutableStepDTO",
                        "stepType": {"stepTypeId": 3, "stepTypeKey": "interval"},
                        "endCondition": {"conditionTypeId": 10, "conditionTypeKey": "reps"},
                        "endConditionValue": 10.0,
                        "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"},
                        "category": "BENCH_PRESS",
                        "exerciseName": "DUMBBELL_BENCH_PRESS",
                        "weightValue": 14.0,
                        "weightUnit": {"unitId": 8, "unitKey": "kilogram", "factor": 1000.0},
                    },
                    {
                        "type": "RepeatGroupDTO",
                        "numberOfIterations": 2,
                        "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat"},
                        "workoutSteps": [
                            {
                                "type": "ExecutableStepDTO",
                                "stepType": {"stepTypeId": 3, "stepTypeKey": "interval"},
                                "endCondition": {"conditionTypeId": 10, "conditionTypeKey": "reps"},
                                "endConditionValue": 12.0,
                                "targetType": {
                                    "workoutTargetTypeId": 1,
                                    "workoutTargetTypeKey": "no.target",
                                },
                                "category": "ROW",
                                "exerciseName": "FACE_PULL",
                                "weightValue": 12.0,
                                "weightUnit": {"unitId": 8, "unitKey": "kilogram", "factor": 1000.0},
                            },
                            {
                                "type": "ExecutableStepDTO",
                                "stepType": {"stepTypeId": 5, "stepTypeKey": "rest"},
                                "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
                                "endConditionValue": 60.0,
                                "targetType": {
                                    "workoutTargetTypeId": 1,
                                    "workoutTargetTypeKey": "no.target",
                                },
                                "category": None,
                                "exerciseName": None,
                                "weightValue": -1.0,
                                "weightUnit": {"unitId": 8, "unitKey": "kilogram", "factor": 1000.0},
                            },
                        ],
                    },
                ],
            },
            {
                "segmentOrder": 12,
                "sportType": {"sportTypeId": 5, "sportTypeKey": "strength_training"},
                "workoutSteps": [
                    {
                        "type": "ExecutableStepDTO",
                        "stepType": {"stepTypeId": 5, "stepTypeKey": "rest"},
                        "endCondition": {"conditionTypeId": 1, "conditionTypeKey": "lap.button"},
                        "endConditionValue": 0.0,
                        "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"},
                        "category": None,
                        "exerciseName": None,
                        "weightValue": -1.0,
                        "weightUnit": {"unitId": 8, "unitKey": "kilogram", "factor": 1000.0},
                    }
                ],
            },
        ],
    }


def test_validate_strength_root_structure_valid():
    validate_strength_root_structure(_make_native_strength_workout())


def test_validate_strength_root_structure_invalid_sport_type():
    workout = _make_native_strength_workout()
    workout["sportType"]["sportTypeKey"] = "running"
    with pytest.raises(ValueError, match="sportType.sportTypeKey must be 'strength_training'."):
        validate_strength_root_structure(workout)


def test_validate_strength_root_structure_missing_segments():
    workout = _make_native_strength_workout()
    workout["workoutSegments"] = []
    with pytest.raises(ValueError, match="workoutSegments must be a non-empty list."):
        validate_strength_root_structure(workout)


def test_validate_strength_exercise_pairs_valid(tmp_path):
    workout = _make_native_strength_workout()
    csv_path = _write_exercise_csv(tmp_path)
    validate_strength_exercise_pairs(workout, csv_path=csv_path)


def test_validate_strength_exercise_pairs_invalid_pair(tmp_path):
    workout = _make_native_strength_workout()
    workout["workoutSegments"][0]["workoutSteps"][0]["exerciseName"] = "NOT_IN_CSV"
    csv_path = _write_exercise_csv(tmp_path)
    with pytest.raises(ValueError, match="Unknown Garmin exercise pair"):
        validate_strength_exercise_pairs(workout, csv_path=csv_path)


def test_validate_strength_exercise_pairs_category_without_exercise(tmp_path):
    workout = _make_native_strength_workout()
    workout["workoutSegments"][0]["workoutSteps"][0]["exerciseName"] = None
    csv_path = _write_exercise_csv(tmp_path)
    with pytest.raises(ValueError, match="Both category and exerciseName must be set together"):
        validate_strength_exercise_pairs(workout, csv_path=csv_path)


def test_normalize_strength_workout_assigns_orders_and_child_ids():
    workout = _make_native_strength_workout()
    normalized = normalize_strength_workout(workout)

    assert normalized["workoutSegments"][0]["segmentOrder"] == 1
    assert normalized["workoutSegments"][1]["segmentOrder"] == 2

    first_segment_steps = normalized["workoutSegments"][0]["workoutSteps"]
    second_segment_steps = normalized["workoutSegments"][1]["workoutSteps"]

    assert first_segment_steps[0]["stepOrder"] == 1
    assert first_segment_steps[1]["stepOrder"] == 2

    repeat_children = first_segment_steps[1]["workoutSteps"]
    assert repeat_children[0]["stepOrder"] == 3
    assert repeat_children[1]["stepOrder"] == 4
    assert repeat_children[0]["childStepId"] == 1
    assert repeat_children[1]["childStepId"] == 2

    assert second_segment_steps[0]["stepOrder"] == 5
    assert first_segment_steps[0]["stepId"] is None


def test_build_strength_step_with_reps():
    step = build_strength_step(
        category="BENCH_PRESS",
        exercise_name="DUMBBELL_BENCH_PRESS",
        reps=10,
        weight_kg=14.0,
    )
    assert step["type"] == "ExecutableStepDTO"
    assert step["endCondition"]["conditionTypeKey"] == "reps"
    assert step["endCondition"]["conditionTypeId"] == 10
    assert step["endConditionValue"] == 10.0
    assert step["weightValue"] == 14.0


def test_build_strength_step_with_duration():
    step = build_strength_step(
        category="BANDED_EXERCISES",
        exercise_name="INTERNAL_ROTATION",
        duration_seconds=40.0,
        weight_kg=-1.0,
    )
    assert step["endCondition"]["conditionTypeKey"] == "time"
    assert step["endCondition"]["conditionTypeId"] == 2
    assert step["endConditionValue"] == 40.0


def test_build_rest_step_lap_button():
    step = build_rest_step()
    assert step["stepType"]["stepTypeKey"] == "rest"
    assert step["endCondition"]["conditionTypeKey"] == "lap.button"
    assert step["endCondition"]["conditionTypeId"] == 1
    assert step["endConditionValue"] == 0.0


def test_build_repeat_group():
    exercise = build_strength_step(
        category="BENCH_PRESS",
        exercise_name="DUMBBELL_BENCH_PRESS",
        reps=8,
    )
    rest = build_rest_step(duration_seconds=90)
    repeat = build_repeat_group(iterations=3, steps=[exercise, rest], skip_last_rest=True)
    assert repeat["type"] == "RepeatGroupDTO"
    assert repeat["numberOfIterations"] == 3
    assert repeat["endCondition"]["conditionTypeKey"] == "iterations"
    assert repeat["skipLastRestStep"] is True


def test_build_strength_workout_from_simple(tmp_path):
    workout_data = {
        "name": "Simple Strength",
        "description": "Simple schema",
        "steps": [
            {
                "type": "repeat",
                "iterations": 2,
                "steps": [
                    {
                        "type": "exercise",
                        "category": "BENCH_PRESS",
                        "exerciseName": "DUMBBELL_BENCH_PRESS",
                        "reps": 10,
                        "weightKg": 14.0,
                    },
                    {
                        "type": "rest",
                        "durationSeconds": 120,
                    },
                ],
            }
        ],
    }

    native = build_strength_workout_from_simple(workout_data)
    csv_path = _write_exercise_csv(tmp_path)
    prepared = prepare_strength_workout_payload(native, csv_path=csv_path)

    assert prepared["workoutName"] == "Simple Strength"
    assert prepared["sportType"]["sportTypeKey"] == "strength_training"
    repeat_group = prepared["workoutSegments"][0]["workoutSteps"][0]
    assert repeat_group["type"] == "RepeatGroupDTO"
    assert repeat_group["numberOfIterations"] == 2


def test_build_strength_workout_native_requires_steps():
    with pytest.raises(ValueError, match="Workout steps must be a non-empty list."):
        build_strength_workout_native(name="Empty", description=None, steps=[])
