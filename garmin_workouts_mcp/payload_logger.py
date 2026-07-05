"""
Append-only raw payload logging for upload_strength_workout.

Every payload received by upload_strength_workout is written to disk, verbatim
and before any validation/normalization, so it can later be used as a corpus
to calibrate a separate validation module.

Storage:
- Directory: GARMIN_STRENGTH_PAYLOAD_LOG_DIR env var, default "logs/strength_payloads"
  (relative to the process cwd -- /app inside the Docker image, see
  deploy/synology/docker-compose.yml).
- One file per call: "{utc_timestamp}_{sanitized_name}.json".
- This is APPEND-ONLY. There is no rotation, size cap, or automatic purge.
  A retention/cleanup policy is a deliberate TODO for later, once real
  payload volume is observed.

This module must never raise and must never influence the tool's return
value or control flow. All failures are caught and logged as warnings.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LOG_DIR = "logs/strength_payloads"
LOG_DIR_ENV_NAME = "GARMIN_STRENGTH_PAYLOAD_LOG_DIR"
_MAX_NAME_LEN = 80

logger = logging.getLogger(__name__)


def extract_workout_name(payload: Any) -> str:
    """
    Best-effort extraction of a human-readable workout name from a raw,
    not-yet-validated payload, for use in the log filename only.

    Checks, in order:
      1. top-level "workoutName" (native schema)
      2. top-level "name" (simple schema)
      3. payload["workout"]["workoutName"] / ["name"] (possible wrapper shape)
    Returns "unnamed" if payload is not a dict, or no string name is found.
    """
    if not isinstance(payload, dict):
        return "unnamed"

    for key in ("workoutName", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value

    nested = payload.get("workout")
    if isinstance(nested, dict):
        for key in ("workoutName", "name"):
            value = nested.get(key)
            if isinstance(value, str) and value.strip():
                return value

    return "unnamed"


def _sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not sanitized:
        return "unnamed"
    return sanitized[:_MAX_NAME_LEN]


def log_payload(payload: Any, name: str, *, logger: logging.Logger | None = None) -> None:
    """
    Write payload verbatim to a new JSON file in the payload log directory.

    Pure side effect: never raises. Any failure (permissions, disk full,
    non-serializable payload, etc.) is caught and logged as a warning via
    `logger` (defaults to this module's logger), and the function returns.
    """
    log = logger or globals()["logger"]
    try:
        log_dir = Path(os.environ.get(LOG_DIR_ENV_NAME, DEFAULT_LOG_DIR))
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        file_path = log_dir / f"{timestamp}_{_sanitize_name(name)}.json"

        file_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("Failed to log strength workout payload: %s", exc)
