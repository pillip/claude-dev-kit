import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from kit_config import _load, _parse_value, _save, get, list_all, set_value


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect config to a temp directory."""
    import kit_config

    monkeypatch.setattr(kit_config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(kit_config, "CONFIG_FILE", tmp_path / "config.json")
    yield tmp_path


class TestGetSet:
    def test_get_missing_key_returns_none(self):
        assert get("nonexistent") is None

    def test_default_contributor_mode_true(self):
        assert get("contributor_mode") is True

    def test_set_and_get_roundtrip(self):
        set_value("contributor_mode", True)
        assert get("contributor_mode") is True

    def test_set_string_value(self):
        set_value("username", "alice")
        assert get("username") == "alice"

    def test_set_overwrites(self):
        set_value("contributor_mode", True)
        set_value("contributor_mode", False)
        assert get("contributor_mode") is False


class TestListAll:
    def test_list_returns_defaults_initially(self):
        config = list_all()
        assert "contributor_mode" in config

    def test_list_includes_set_values(self):
        set_value("custom_key", "custom_value")
        config = list_all()
        assert config["custom_key"] == "custom_value"


class TestConfigDir:
    def test_creates_config_dir_if_missing(self, isolated_config):
        # Remove the dir
        import shutil

        shutil.rmtree(str(isolated_config), ignore_errors=True)
        assert not isolated_config.exists()

        set_value("test_key", "test_value")
        assert isolated_config.exists()
        assert get("test_key") == "test_value"


class TestParseValue:
    def test_true_values(self):
        assert _parse_value("true") is True
        assert _parse_value("yes") is True
        assert _parse_value("1") == 1  # parsed as int first

    def test_false_values(self):
        assert _parse_value("false") is False
        assert _parse_value("no") is False
        assert _parse_value("0") == 0  # parsed as int first

    def test_int_value(self):
        assert _parse_value("42") == 42

    def test_string_value(self):
        assert _parse_value("hello") == "hello"
