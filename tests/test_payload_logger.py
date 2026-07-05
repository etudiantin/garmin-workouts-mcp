import json
import logging
from pathlib import Path

from garmin_workouts_mcp.payload_logger import extract_workout_name, log_payload


class TestExtractWorkoutName:
    def test_top_level_workout_name(self):
        assert extract_workout_name({"workoutName": "Leg Day"}) == "Leg Day"

    def test_top_level_name(self):
        assert extract_workout_name({"name": "Leg Day"}) == "Leg Day"

    def test_prefers_workout_name_over_name(self):
        payload = {"workoutName": "Native Name", "name": "Simple Name"}
        assert extract_workout_name(payload) == "Native Name"

    def test_nested_under_workout_key_with_workout_name(self):
        payload = {"workout": {"workoutName": "Nested Name"}}
        assert extract_workout_name(payload) == "Nested Name"

    def test_nested_under_workout_key_with_name(self):
        payload = {"workout": {"name": "Nested Simple Name"}}
        assert extract_workout_name(payload) == "Nested Simple Name"

    def test_falls_back_to_unnamed_when_missing(self):
        assert extract_workout_name({}) == "unnamed"

    def test_falls_back_to_unnamed_when_not_dict(self):
        assert extract_workout_name("not a dict") == "unnamed"
        assert extract_workout_name(None) == "unnamed"
        assert extract_workout_name([1, 2]) == "unnamed"

    def test_ignores_non_string_name(self):
        assert extract_workout_name({"name": 123}) == "unnamed"


class TestLogPayload:
    def test_writes_exact_json_content(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GARMIN_STRENGTH_PAYLOAD_LOG_DIR", str(tmp_path))
        payload = {"workoutName": "My Workout", "steps": [1, 2, 3]}

        log_payload(payload, "My Workout")

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        assert json.loads(files[0].read_text(encoding="utf-8")) == payload

    def test_creates_directory_if_missing(self, tmp_path, monkeypatch):
        target_dir = tmp_path / "nested" / "dir"
        monkeypatch.setenv("GARMIN_STRENGTH_PAYLOAD_LOG_DIR", str(target_dir))

        log_payload({"name": "X"}, "X")

        assert target_dir.is_dir()
        assert len(list(target_dir.glob("*.json"))) == 1

    def test_filename_uses_sanitized_name_and_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GARMIN_STRENGTH_PAYLOAD_LOG_DIR", str(tmp_path))

        log_payload({"name": "Leg Day #1!"}, "Leg Day #1!")

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        assert files[0].name.endswith("_leg_day_1.json")
        assert files[0].name[:8].isdigit()

    def test_default_dir_when_env_unset(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GARMIN_STRENGTH_PAYLOAD_LOG_DIR", raising=False)
        monkeypatch.chdir(tmp_path)

        log_payload({"name": "X"}, "X")

        default_dir = tmp_path / "logs" / "strength_payloads"
        assert default_dir.is_dir()
        assert len(list(default_dir.glob("*.json"))) == 1

    def test_swallows_mkdir_failure_and_logs_warning(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setenv("GARMIN_STRENGTH_PAYLOAD_LOG_DIR", str(tmp_path / "some_dir"))

        def _raise_mkdir(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(Path, "mkdir", _raise_mkdir)

        with caplog.at_level(logging.WARNING):
            log_payload({"name": "X"}, "X")

        assert "Failed to log strength workout payload" in caplog.text

    def test_swallows_failure_when_log_dir_path_is_a_file(self, tmp_path, monkeypatch, caplog):
        occupied_path = tmp_path / "occupied"
        occupied_path.write_text("I am a file, not a directory")
        monkeypatch.setenv("GARMIN_STRENGTH_PAYLOAD_LOG_DIR", str(occupied_path))

        with caplog.at_level(logging.WARNING):
            log_payload({"name": "X"}, "X")

        assert "Failed to log strength workout payload" in caplog.text

    def test_accepts_injected_logger(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setenv("GARMIN_STRENGTH_PAYLOAD_LOG_DIR", str(tmp_path / "some_dir"))

        def _raise_mkdir(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(Path, "mkdir", _raise_mkdir)
        stub_logger = logging.getLogger("test_stub_payload_logger")

        with caplog.at_level(logging.WARNING, logger="test_stub_payload_logger"):
            log_payload({"name": "X"}, "X", logger=stub_logger)

        assert "Failed to log strength workout payload" in caplog.text
