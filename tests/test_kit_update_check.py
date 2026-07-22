import json
import sys
import time
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from kit_update_check import (
    SNOOZE_DURATIONS,
    _is_snoozed,
    _local_version,
    _parse_version,
    _read_cache,
    _write_cache,
)


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Redirect state files to temp directory."""
    import kit_update_check

    monkeypatch.setattr(kit_update_check, "STATE_DIR", tmp_path)
    monkeypatch.setattr(kit_update_check, "CACHE_FILE", tmp_path / "update-cache.json")
    monkeypatch.setattr(kit_update_check, "SNOOZE_FILE", tmp_path / "update-snooze.json")
    monkeypatch.setattr(kit_update_check, "_remote_version", lambda: None)
    yield tmp_path


class TestParseVersion:
    def test_simple(self):
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_comparison(self):
        assert _parse_version("0.6.0") > _parse_version("0.5.0")
        assert _parse_version("1.0.0") > _parse_version("0.9.9")
        assert _parse_version("0.5.0") == _parse_version("0.5.0")

    def test_invalid(self):
        assert _parse_version("unknown") == (0,)


class TestLocalVersion:
    def test_reads_version_file(self):
        ver = _local_version()
        assert ver != "unknown"
        assert "." in ver


class TestCache:
    def test_write_and_read(self, isolated_state):
        _write_cache("0.5.0", "0.6.0")
        cache = _read_cache()
        assert cache is not None
        assert cache["local_version"] == "0.5.0"
        assert cache["remote_version"] == "0.6.0"

    def test_expired_cache(self, isolated_state):
        import kit_update_check

        _write_cache("0.5.0", "0.6.0")
        # Manually expire the cache
        cache_file = isolated_state / "update-cache.json"
        data = json.loads(cache_file.read_text())
        data["timestamp"] = time.time() - 25 * 60 * 60  # 25 hours ago
        cache_file.write_text(json.dumps(data))

        assert _read_cache() is None

    def test_no_cache(self, isolated_state):
        assert _read_cache() is None


class TestSnooze:
    def test_not_snoozed_by_default(self, isolated_state):
        assert _is_snoozed() is False

    def test_snoozed_when_set(self, isolated_state):
        snooze_file = isolated_state / "update-snooze.json"
        snooze_file.write_text(json.dumps({
            "until": time.time() + 3600,
            "version": "0.6.0",
            "duration": "24h",
        }))
        assert _is_snoozed() is True

    def test_expired_snooze(self, isolated_state):
        snooze_file = isolated_state / "update-snooze.json"
        snooze_file.write_text(json.dumps({
            "until": time.time() - 1,
            "version": "0.6.0",
            "duration": "24h",
        }))
        assert _is_snoozed() is False

    def test_snooze_durations_exist(self):
        assert "24h" in SNOOZE_DURATIONS
        assert "48h" in SNOOZE_DURATIONS
        assert "7d" in SNOOZE_DURATIONS


class TestUpdateCheckMovedToSessionStart:
    """ISSUE-032: the update check runs once per session in the SessionStart
    hook — preambles must NOT re-instruct it per skill invocation."""

    def test_no_tier_carries_update_check(self):
        from preambles import preamble_tier1, preamble_tier2, preamble_tier3

        for result in (preamble_tier1("brainstorm"), preamble_tier2("implement"),
                       preamble_tier3("sprint")):
            assert "Kit Update Check" not in result
            assert "kit_update_check.py" not in result

    def test_session_start_hook_runs_update_check(self):
        hook = Path(__file__).resolve().parents[1] / "project" / ".claude" / "hooks" / "session_start.py"
        assert "kit_update_check.py" in hook.read_text(encoding="utf-8")
