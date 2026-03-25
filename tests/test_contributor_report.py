import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from contributor_report import _log_path, _slugify, write_report


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Redirect all paths to temp directory."""
    import contributor_report
    import kit_config

    logs_dir = tmp_path / "contributor-logs"
    config_dir = tmp_path / "config"

    monkeypatch.setattr(contributor_report, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(kit_config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(kit_config, "CONFIG_FILE", config_dir / "config.json")

    # Enable contributor mode by default for tests
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text('{"contributor_mode": true}')

    yield {"logs": logs_dir, "config": config_dir}


class TestSlugify:
    def test_basic(self):
        assert _slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert _slugify("test! @#$% step") == "test-step"

    def test_max_length(self):
        long = "a" * 100
        assert len(_slugify(long)) <= 60


class TestWriteReport:
    def test_writes_report_to_log_dir(self, isolated_env):
        ok, msg = write_report("implement", "code review", 7, "Instructions unclear")
        assert ok
        assert "written" in msg.lower() or "Report" in msg

        # Verify file exists
        logs = isolated_env["logs"]
        files = list(logs.iterdir())
        assert len(files) == 1
        content = files[0].read_text()
        assert "code review" in content
        assert "Rating: 7" in content

    def test_skips_duplicate_report(self, isolated_env):
        write_report("implement", "code review", 7, "First note")
        ok, msg = write_report("implement", "code review", 7, "Second note")
        assert not ok
        assert "duplicate" in msg.lower() or "Skipping" in msg

    def test_allows_different_rating_same_step(self, isolated_env):
        write_report("implement", "code review", 7, "First note")
        ok, _ = write_report("implement", "code review", 8, "Better now")
        assert ok

    def test_max_three_reports_per_session(self, isolated_env):
        write_report("implement", "step1", 5, "note1")
        write_report("implement", "step2", 6, "note2")
        write_report("implement", "step3", 7, "note3")
        ok, msg = write_report("implement", "step4", 8, "note4")
        assert not ok
        assert "limit" in msg.lower() or "Skipping" in msg

    def test_skips_when_contributor_mode_off(self, isolated_env):
        config = isolated_env["config"]
        (config / "config.json").write_text('{"contributor_mode": false}')

        ok, msg = write_report("implement", "step1", 5, "note")
        assert not ok
        assert "off" in msg.lower() or "Skipping" in msg

    def test_rating_validation(self, isolated_env):
        ok, msg = write_report("implement", "step1", 11, "note")
        assert not ok
        assert "0-10" in msg

        ok, msg = write_report("implement", "step1", -1, "note")
        assert not ok
        assert "0-10" in msg
