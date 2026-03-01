#!/usr/bin/env python3
"""Upload the 4-week strength plan to Garmin Connect via MCP tools."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# Allow direct execution from scripts/ without requiring PYTHONPATH.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def call(tool: Any, *args: Any, **kwargs: Any) -> Any:
    fn = getattr(tool, "fn", tool)
    return fn(*args, **kwargs)


def ex(
    category: str,
    exercise_name: str,
    *,
    reps: int | None = None,
    duration: int | None = None,
    weight: float | None = None,
    step_type: str | None = None,
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "type": "exercise",
        "category": category,
        "exerciseName": exercise_name,
    }
    if reps is not None:
        step["reps"] = reps
    if duration is not None:
        step["durationSeconds"] = duration
    if weight is not None:
        step["weightKg"] = weight
    if step_type is not None:
        step["stepType"] = step_type
    return step


def stretch(exercise_name: str, duration: int) -> dict[str, Any]:
    return ex("WARM_UP", exercise_name, duration=duration, step_type="warmup")


def rest(seconds: int) -> dict[str, Any]:
    return {"type": "rest", "durationSeconds": seconds}


def rpt(iterations: int, steps: list[dict[str, Any]], *, skip_last_rest: bool = True) -> dict[str, Any]:
    return {
        "type": "repeat",
        "iterations": iterations,
        "skipLastRest": skip_last_rest,
        "steps": steps,
    }


def build_workouts() -> list[dict[str, Any]]:
    workouts: list[dict[str, Any]] = []

    # S1
    workouts.append(
        {
            "name": "S1 - Lundi PUSH (Complet)",
            "description": "Semaine 1 accumulation | 3 series | RIR 3",
            "steps": [
                rpt(2, [ex("BANDED_EXERCISES", "INTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(
                    2,
                    [ex("ROW_FACE", "PULL_WITH_EXTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)],
                ),
                rpt(3, [stretch("STRETCH_FOREARMS", 30)]),
                rpt(2, [ex("PUSH_UP", "PUSH_UP", reps=10, step_type="warmup"), rest(45)]),
                rpt(2, [ex("WARM_UP", "SHOULDER_CIRCLES", reps=10, step_type="warmup")]),
                rpt(3, [ex("BENCH_PRESS", "DUMBBELL_BENCH_PRESS", reps=10, weight=14.0), rest(150)]),
                rpt(
                    3,
                    [ex("BENCH_PRESS", "INCLINE_DUMBBELL_BENCH_PRESS", reps=10, weight=14.0), rest(120)],
                ),
                rpt(3, [ex("FLYE_INCLINE", "REVERSE_FLYE", reps=12, weight=8.0), rest(90)]),
                rpt(
                    3,
                    [ex("SHOULDER_PRESS", "SEATED_DUMBBELL_SHOULDER_PRESS", reps=10, weight=10.0), rest(120)],
                ),
                rpt(3, [ex("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE", reps=12, weight=4.0), rest(90)]),
                rpt(3, [ex("BANDED_EXERCISES", "TRICEPS_EXTENSION_WHEELCHAIR", reps=15), rest(90)]),
                rpt(3, [ex("HIP_STABILITY", "DEAD_BUG", reps=8), rest(30)]),
                rpt(2, [stretch("STRETCH_PECTORAL", 30)]),
                rpt(2, [stretch("STRETCH_TRICEPS", 30)]),
                rpt(2, [stretch("STRETCH_SHOULDER", 30)]),
                rpt(2, [stretch("STRETCH_FOREARMS", 30)]),
            ],
        }
    )

    workouts.append(
        {
            "name": "S1 - Mercredi PULL (Complet)",
            "description": "Semaine 1 accumulation | 3 series | RIR 3",
            "steps": [
                rpt(2, [ex("BANDED_EXERCISES", "INTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(3, [stretch("STRETCH_FOREARMS", 30)]),
                rpt(2, [ex("ROW_DUMBBELL", "ROW", reps=10, weight=10.0, step_type="warmup"), rest(45)]),
                rpt(2, [ex("WARM_UP", "THORACIC_ROTATION", reps=8, step_type="warmup")]),
                rpt(3, [ex("ROW_BENT", "OVER_ROW_WITH_BARBELL", reps=8, weight=41.5), rest(150)]),
                rpt(3, [ex("ROW_DUMBBELL", "ROW", reps=10, weight=14.0), rest(90)]),
                rpt(3, [ex("ROW_FACE", "PULL", reps=15), rest(90)]),
                rpt(3, [ex("PULL_UP", "EZ_BAR_PULLOVER", reps=12, weight=15.0), rest(90)]),
                rpt(3, [ex("CURL_DUMBBELL", "HAMMER_CURL", reps=12, weight=10.0), rest(90)]),
                rpt(3, [ex("CURL_STANDING", "EZ_BAR_BICEPS_CURL", reps=10, weight=21.0), rest(90)]),
                rpt(3, [ex("PLANK_PLANK", "PLANK", duration=30), rest(30)]),
                rpt(2, [stretch("STRETCH_LAT", 30)]),
                rpt(2, [stretch("BICEPS_STRETCH", 30)]),
                rpt(2, [stretch("STRETCH_SHOULDER", 30)]),
                rpt(2, [stretch("STRETCH_FOREARMS", 30)]),
            ],
        }
    )

    workouts.append(
        {
            "name": "S1 - Vendredi LOWER+Accessoires (Complet)",
            "description": "Semaine 1 accumulation | 3 series | RIR 3",
            "steps": [
                rpt(2, [ex("WARM_UP", "HIP_CIRCLES", reps=10, step_type="warmup")]),
                rpt(2, [ex("WARM_UP", "ANKLE_STRETCH", reps=8, step_type="warmup")]),
                rpt(2, [ex("BANDED_EXERCISES", "INTERNAL_ROTATION", reps=12, step_type="warmup"), rest(30)]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=12, step_type="warmup"), rest(30)]),
                rpt(3, [ex("SQUAT_WEIGHTED", "SQUAT", reps=8, weight=21.0), rest(180)]),
                rpt(3, [ex("DEADLIFT_ROMANIAN", "DEADLIFT", reps=8, weight=41.5), rest(180)]),
                rpt(3, [ex("HIP_RAISE", "WEIGHTED_HIP_RAISE", reps=12, weight=21.0), rest(120)]),
                rpt(3, [ex("LUNGE_WEIGHTED", "LUNGE", reps=10, weight=20.0), rest(150)]),
                rpt(3, [ex("CALF_RAISE", "WEIGHTED_STANDING_CALF_RAISE", reps=15, weight=30.0), rest(90)]),
                rpt(3, [ex("BANDED_EXERCISES", "HAMSTRING_CURLS", reps=12), rest(90)]),
                rpt(
                    3,
                    [
                        ex("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE", reps=12, weight=4.0),
                        ex("CURL_DUMBBELL", "HAMMER_CURL", reps=12, weight=8.0),
                        rest(90),
                    ],
                ),
                rpt(3, [ex("HIP_STABILITY", "DEAD_BUG", reps=8), rest(30)]),
                rpt(2, [stretch("STRETCH_HIP_FLEXOR_AND_QUAD", 30)]),
                rpt(2, [stretch("STRETCH_HAMSTRING", 30)]),
                rpt(2, [stretch("STRETCH_CALF", 30)]),
                rpt(2, [stretch("STRETCH_FORWARD_GLUTES", 30)]),
            ],
        }
    )

    # S2
    workouts.append(
        {
            "name": "S2 - Lundi PUSH",
            "description": "Semaine 2 accumulation montee | RIR 2-3 | myoreps isolation (manuel)",
            "steps": [
                rpt(2, [ex("BANDED_EXERCISES", "INTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(
                    2,
                    [ex("ROW_FACE", "PULL_WITH_EXTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)],
                ),
                rpt(3, [stretch("STRETCH_FOREARMS", 30)]),
                rpt(2, [ex("PUSH_UP", "TRIPLE_STOP_PUSH_UP", reps=10, step_type="warmup"), rest(45)]),
                rpt(4, [ex("BENCH_PRESS", "DUMBBELL_BENCH_PRESS", reps=10, weight=15.0), rest(150)]),
                rpt(
                    3,
                    [ex("BENCH_PRESS", "INCLINE_DUMBBELL_BENCH_PRESS", reps=10, weight=14.0), rest(120)],
                ),
                rpt(3, [ex("FLYE_INCLINE", "REVERSE_FLYE", reps=12, weight=8.0), rest(90)]),
                rpt(
                    3,
                    [ex("SHOULDER_PRESS", "SEATED_DUMBBELL_SHOULDER_PRESS", reps=10, weight=10.5), rest(120)],
                ),
                rpt(3, [ex("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE", reps=12, weight=4.0), rest(90)]),
                rpt(4, [ex("BANDED_EXERCISES", "TRICEPS_EXTENSION_WHEELCHAIR", reps=15), rest(75)]),
                rpt(3, [ex("HIP_STABILITY", "DEAD_BUG", reps=10), rest(30)]),
                rpt(2, [stretch("STRETCH_PECTORAL", 30)]),
                rpt(2, [stretch("STRETCH_TRICEPS", 30)]),
                rpt(2, [stretch("STRETCH_SHOULDER", 30)]),
            ],
        }
    )

    workouts.append(
        {
            "name": "S2 - Mercredi PULL",
            "description": "Semaine 2 accumulation montee | RIR 2-3 | myoreps isolation (manuel)",
            "steps": [
                rpt(2, [ex("BANDED_EXERCISES", "INTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(3, [stretch("STRETCH_FOREARMS", 30)]),
                rpt(2, [ex("ROW_DUMBBELL", "ROW", reps=10, weight=10.0, step_type="warmup"), rest(45)]),
                rpt(2, [ex("WARM_UP", "THORACIC_ROTATION", reps=8, step_type="warmup")]),
                rpt(4, [ex("ROW_BENT", "OVER_ROW_WITH_BARBELL", reps=8, weight=41.5), rest(150)]),
                rpt(3, [ex("ROW_DUMBBELL", "ROW", reps=10, weight=14.0), rest(90)]),
                rpt(3, [ex("PULL_UP", "EZ_BAR_PULLOVER", reps=12, weight=15.0), rest(90)]),
                rpt(3, [ex("ROW_FACE", "PULL", reps=15), rest(90)]),
                rpt(3, [ex("FLYE_INCLINE", "REVERSE_FLYE", reps=12, weight=5.0), rest(90)]),
                rpt(3, [ex("CURL_DUMBBELL", "HAMMER_CURL", reps=12, weight=10.0), rest(90)]),
                rpt(3, [ex("CURL_STANDING", "EZ_BAR_BICEPS_CURL", reps=10, weight=21.0), rest(90)]),
                rpt(2, [stretch("STRETCH_SIDE", 30)]),
                rpt(2, [stretch("BICEPS_STRETCH", 30)]),
                rpt(2, [stretch("STRETCH_SHOULDER", 30)]),
                rpt(2, [ex("WARM_UP", "UPPER_BACK_STRETCH", duration=30, step_type="warmup")]),
            ],
        }
    )

    workouts.append(
        {
            "name": "S2 - Vendredi LOWER+Accessoires",
            "description": "Semaine 2 accumulation montee | RIR 2-3",
            "steps": [
                rpt(2, [ex("WARM_UP", "HIP_CIRCLES", reps=10, step_type="warmup")]),
                rpt(2, [ex("WARM_UP", "ANKLE_STRETCH", reps=8, step_type="warmup")]),
                rpt(2, [ex("BANDED_EXERCISES", "INTERNAL_ROTATION", reps=12, step_type="warmup"), rest(30)]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=12, step_type="warmup"), rest(30)]),
                rpt(3, [ex("SQUAT_WEIGHTED", "SQUAT", reps=8, weight=21.0), rest(180)]),
                rpt(3, [ex("DEADLIFT_ROMANIAN", "DEADLIFT", reps=8, weight=41.5), rest(180)]),
                rpt(3, [ex("HIP_RAISE", "WEIGHTED_HIP_RAISE", reps=12, weight=21.0), rest(120)]),
                rpt(3, [ex("LUNGE_WEIGHTED", "LUNGE", reps=10, weight=20.0), rest(150)]),
                rpt(3, [ex("CALF_RAISE", "WEIGHTED_STANDING_CALF_RAISE", reps=15, weight=30.0), rest(90)]),
                rpt(3, [ex("BANDED_EXERCISES", "HAMSTRING_CURLS", reps=12), rest(90)]),
                rpt(
                    3,
                    [
                        ex("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE", reps=12, weight=4.0),
                        ex("CURL_DUMBBELL", "HAMMER_CURL", reps=10, weight=8.0),
                        rest(90),
                    ],
                ),
                rpt(2, [ex("PLANK_PLANK", "PLANK", duration=30)]),
                rpt(2, [stretch("STRETCH_HIP_FLEXOR_AND_QUAD", 30)]),
                rpt(2, [stretch("STRETCH_HAMSTRING", 30)]),
                rpt(2, [stretch("STRETCH_CALF", 30)]),
                rpt(2, [stretch("STRETCH_FORWARD_GLUTES", 30)]),
            ],
        }
    )

    # S3
    workouts.append(
        {
            "name": "S3 - Lundi PUSH",
            "description": "Semaine 3 intensification | RIR 1-2 | myoreps isolation (manuel)",
            "steps": [
                rpt(2, [ex("BANDED_EXERCISES", "INTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(
                    2,
                    [ex("ROW_FACE", "PULL_WITH_EXTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)],
                ),
                rpt(3, [stretch("STRETCH_FOREARMS", 30)]),
                rpt(2, [ex("PUSH_UP", "TRIPLE_STOP_PUSH_UP", reps=12, step_type="warmup"), rest(45)]),
                rpt(4, [ex("BENCH_PRESS", "DUMBBELL_BENCH_PRESS", reps=10, weight=16.0), rest(150)]),
                rpt(
                    4,
                    [ex("BENCH_PRESS", "INCLINE_DUMBBELL_BENCH_PRESS", reps=10, weight=15.0), rest(120)],
                ),
                rpt(3, [ex("FLYE_INCLINE", "REVERSE_FLYE", reps=12, weight=8.0), rest(90)]),
                rpt(
                    3,
                    [ex("SHOULDER_PRESS", "SEATED_DUMBBELL_SHOULDER_PRESS", reps=10, weight=10.5), rest(120)],
                ),
                rpt(4, [ex("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE", reps=12, weight=4.0), rest(75)]),
                rpt(4, [ex("BANDED_EXERCISES", "TRICEPS_EXTENSION_WHEELCHAIR", reps=15), rest(75)]),
                rpt(2, [ex("PUSH_UP", "DIAMOND_PUSH_UP", reps=12), rest(90)]),
                rpt(2, [stretch("STRETCH_PECTORAL", 45)]),
                rpt(2, [stretch("STRETCH_TRICEPS", 30)]),
                rpt(2, [stretch("STRETCH_SHOULDER", 30)]),
                rpt(2, [stretch("STRETCH_FOREARMS", 30)]),
            ],
        }
    )

    workouts.append(
        {
            "name": "S3 - Mercredi PULL",
            "description": "Semaine 3 intensification | RIR 1-2 | myoreps isolation (manuel)",
            "steps": [
                rpt(2, [ex("BANDED_EXERCISES", "INTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(3, [stretch("STRETCH_FOREARMS", 30)]),
                rpt(4, [ex("ROW_BENT", "OVER_ROW_WITH_BARBELL", reps=8, weight=41.5), rest(150)]),
                rpt(4, [ex("ROW_DUMBBELL", "ROW", reps=10, weight=16.0), rest(90)]),
                rpt(3, [ex("PULL_UP", "EZ_BAR_PULLOVER", reps=12, weight=17.0), rest(90)]),
                rpt(4, [ex("ROW_FACE", "PULL", reps=15), rest(75)]),
                rpt(3, [ex("FLYE_INCLINE", "REVERSE_FLYE", reps=12, weight=5.0), rest(75)]),
                rpt(4, [ex("CURL_DUMBBELL", "HAMMER_CURL", reps=10, weight=10.0), rest(90)]),
                rpt(3, [ex("CURL_STANDING", "EZ_BAR_BICEPS_CURL", reps=10, weight=21.0), rest(90)]),
                rpt(2, [stretch("STRETCH_SIDE", 45)]),
                rpt(2, [stretch("BICEPS_STRETCH", 30)]),
                rpt(2, [stretch("STRETCH_SHOULDER", 30)]),
                rpt(2, [ex("WARM_UP", "UPPER_BACK_STRETCH", duration=30, step_type="warmup")]),
            ],
        }
    )

    workouts.append(
        {
            "name": "S3 - Vendredi LOWER+Accessoires",
            "description": "Semaine 3 intensification | RIR 1-2",
            "steps": [
                rpt(2, [ex("WARM_UP", "HIP_CIRCLES", reps=10, step_type="warmup")]),
                rpt(2, [ex("WARM_UP", "ANKLE_STRETCH", reps=8, step_type="warmup")]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=12, step_type="warmup"), rest(30)]),
                rpt(3, [ex("SQUAT_WEIGHTED", "SQUAT", reps=8, weight=21.0), rest(180)]),
                rpt(3, [ex("DEADLIFT_ROMANIAN", "DEADLIFT", reps=8, weight=41.5), rest(180)]),
                rpt(3, [ex("HIP_RAISE", "WEIGHTED_HIP_RAISE", reps=12, weight=21.0), rest(120)]),
                rpt(3, [ex("LUNGE_WEIGHTED", "LUNGE", reps=10, weight=20.0), rest(150)]),
                rpt(4, [ex("CALF_RAISE", "WEIGHTED_STANDING_CALF_RAISE", reps=15, weight=30.0), rest(90)]),
                rpt(3, [ex("BANDED_EXERCISES", "HAMSTRING_CURLS", reps=12), rest(90)]),
                rpt(
                    3,
                    [
                        ex("ROW_FACE", "PULL", reps=15),
                        ex("BANDED_EXERCISES", "TRICEPS_EXTENSION_WHEELCHAIR", reps=15),
                        rest(90),
                    ],
                ),
                rpt(
                    3,
                    [
                        ex("CURL_DUMBBELL", "HAMMER_CURL", reps=10, weight=10.0),
                        ex("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE", reps=12, weight=4.0),
                        rest(90),
                    ],
                ),
                rpt(3, [ex("HIP_STABILITY", "DEAD_BUG", reps=10), rest(30)]),
                rpt(2, [stretch("STRETCH_HIP_FLEXOR_AND_QUAD", 30)]),
                rpt(2, [stretch("STRETCH_HAMSTRING", 30)]),
                rpt(2, [stretch("STRETCH_CALF", 30)]),
                rpt(2, [stretch("STRETCH_FORWARD_GLUTES", 30)]),
            ],
        }
    )

    # S4
    workouts.append(
        {
            "name": "S4 - Lundi PUSH (DECHARGE)",
            "description": "Semaine 4 deload | 50% volume S3 | RIR 3-4",
            "steps": [
                rpt(2, [ex("BANDED_EXERCISES", "INTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(2, [ex("ROW_FACE", "PULL", reps=15, step_type="warmup"), rest(30)]),
                rpt(3, [stretch("STRETCH_FOREARMS", 30)]),
                rpt(2, [ex("BENCH_PRESS", "DUMBBELL_BENCH_PRESS", reps=10, weight=16.0), rest(150)]),
                rpt(
                    2,
                    [ex("BENCH_PRESS", "INCLINE_DUMBBELL_BENCH_PRESS", reps=10, weight=15.0), rest(120)],
                ),
                rpt(
                    2,
                    [ex("SHOULDER_PRESS", "SEATED_DUMBBELL_SHOULDER_PRESS", reps=10, weight=10.5), rest(120)],
                ),
                rpt(2, [ex("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE", reps=12, weight=4.0), rest(90)]),
                rpt(2, [ex("BANDED_EXERCISES", "TRICEPS_EXTENSION_WHEELCHAIR", reps=15), rest(75)]),
                rpt(3, [stretch("STRETCH_PECTORAL", 45)]),
                rpt(2, [stretch("STRETCH_TRICEPS", 45)]),
                rpt(3, [stretch("STRETCH_SHOULDER", 30)]),
                rpt(2, [stretch("STRETCH_WALL_CHEST_AND_SHOULDER", 30)]),
                rpt(2, [stretch("STRETCH_FOREARMS", 45)]),
            ],
        }
    )

    workouts.append(
        {
            "name": "S4 - Mercredi PULL (DECHARGE)",
            "description": "Semaine 4 deload | 50% volume S3 | RIR 3-4",
            "steps": [
                rpt(2, [ex("BANDED_EXERCISES", "INTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=15, step_type="warmup"), rest(30)]),
                rpt(3, [stretch("STRETCH_FOREARMS", 30)]),
                rpt(2, [ex("ROW_BENT", "OVER_ROW_WITH_BARBELL", reps=8, weight=41.5), rest(150)]),
                rpt(2, [ex("ROW_DUMBBELL", "ROW", reps=10, weight=16.0), rest(90)]),
                rpt(2, [ex("PULL_UP", "EZ_BAR_PULLOVER", reps=12, weight=17.0), rest(90)]),
                rpt(2, [ex("ROW_FACE", "PULL", reps=15), rest(75)]),
                rpt(2, [ex("CURL_DUMBBELL", "HAMMER_CURL", reps=10, weight=10.0), rest(90)]),
                rpt(2, [ex("CURL_STANDING", "EZ_BAR_BICEPS_CURL", reps=10, weight=21.0), rest(90)]),
                rpt(3, [stretch("STRETCH_SIDE", 45)]),
                rpt(2, [stretch("BICEPS_STRETCH", 45)]),
                rpt(3, [stretch("STRETCH_SHOULDER", 30)]),
                rpt(2, [ex("WARM_UP", "UPPER_BACK_STRETCH", duration=45, step_type="warmup")]),
                rpt(2, [stretch("STRETCH_FOREARMS", 45)]),
            ],
        }
    )

    workouts.append(
        {
            "name": "S4 - Vendredi LOWER (DECHARGE)",
            "description": "Semaine 4 deload | 50% volume S3 | RIR 3-4",
            "steps": [
                rpt(2, [ex("WARM_UP", "HIP_CIRCLES", reps=10, step_type="warmup")]),
                rpt(2, [ex("WARM_UP", "ANKLE_STRETCH", reps=8, step_type="warmup")]),
                rpt(2, [ex("BANDED_EXERCISES", "SHOULDER_EXTERNAL_ROTATION", reps=12, step_type="warmup"), rest(30)]),
                rpt(2, [ex("SQUAT_WEIGHTED", "SQUAT", reps=8, weight=21.0), rest(180)]),
                rpt(2, [ex("DEADLIFT_ROMANIAN", "DEADLIFT", reps=8, weight=41.5), rest(180)]),
                rpt(2, [ex("HIP_RAISE", "WEIGHTED_HIP_RAISE", reps=12, weight=21.0), rest(120)]),
                rpt(2, [ex("CALF_RAISE", "WEIGHTED_STANDING_CALF_RAISE", reps=15, weight=30.0), rest(90)]),
                rpt(2, [ex("BANDED_EXERCISES", "HAMSTRING_CURLS", reps=12), rest(90)]),
                rpt(3, [stretch("STRETCH_HIP_FLEXOR_AND_QUAD", 45)]),
                rpt(3, [stretch("STRETCH_HAMSTRING", 45)]),
                rpt(2, [stretch("STRETCH_CALF", 30)]),
                rpt(3, [stretch("STRETCH_FORWARD_GLUTES", 45)]),
                rpt(2, [stretch("STRETCH_CHILDS_POSE", 60)]),
            ],
        }
    )

    return workouts


def collect_empty_exercise_steps(workout_id: str) -> list[tuple[str | None, str | None]]:
    from garmin_workouts_mcp import main as m

    fetched = call(m.get_workout, workout_id)
    empty_steps: list[tuple[str | None, str | None]] = []

    def walk(step: dict[str, Any]) -> None:
        step_type = step.get("type")
        if step_type == "ExecutableStepDTO":
            category = step.get("category")
            exercise_name = step.get("exerciseName")
            if category is not None and not exercise_name:
                empty_steps.append((category, exercise_name))
            return
        if step_type == "RepeatGroupDTO":
            for child in step.get("workoutSteps", []):
                walk(child)

    for segment in fetched.get("workout", {}).get("workoutSegments", []):
        for workout_step in segment.get("workoutSteps", []):
            walk(workout_step)

    return empty_steps


def main() -> None:
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("garmin_workouts_mcp.main").setLevel(logging.WARNING)
    from garmin_workouts_mcp import main as m

    workouts = build_workouts()
    results: list[dict[str, Any]] = []

    for workout in workouts:
        built = call(m.build_strength_workout, workout, "simple")
        created = call(m.upload_strength_workout, built, replace_existing=True, name_match_mode="exact")
        workout_id = created["workoutId"]
        empty_steps = collect_empty_exercise_steps(workout_id)
        results.append(
            {
                "name": workout["name"],
                "workoutId": workout_id,
                "emptyExerciseSteps": len(empty_steps),
                "replacedWorkoutIds": created.get("replacedWorkoutIds"),
                "categoryRemaps": created.get("categoryRemaps"),
            }
        )

    print("UPLOAD_4_WEEKS_RESULTS_START")
    for result in results:
        print(
            f"{result['name']} | workoutId={result['workoutId']} | "
            f"emptyExerciseSteps={result['emptyExerciseSteps']}"
        )
        print(f"  replaced={result['replacedWorkoutIds']}")
        print(f"  remaps={result['categoryRemaps']}")
    print("UPLOAD_4_WEEKS_RESULTS_END")


if __name__ == "__main__":
    main()
