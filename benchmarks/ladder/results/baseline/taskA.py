"""
config_reader.py — Read a single value from a JSON config file by key.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_MISSING = object()


def get_config_value(
    config_path: str | Path,
    key: str,
    default: Any = _MISSING,
) -> Any:
    """Return the value for *key* from the JSON config file at *config_path*.

    Parameters
    ----------
    config_path:
        Path to the JSON file on disk.
    key:
        Top-level key to look up in the parsed JSON object.
    default:
        Value to return when the key is absent from the config.
        If omitted and the key is missing, ``KeyError`` is raised.

    Raises
    ------
    FileNotFoundError
        If *config_path* does not exist.
    ValueError
        If the file content is not a valid JSON object (dict).
    KeyError
        If *key* is absent and no *default* was supplied.
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in config file '{path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Config file '{path}' must contain a JSON object (dict), "
            f"got {type(data).__name__}."
        )

    if key in data:
        return data[key]

    if default is not _MISSING:
        return default

    raise KeyError(f"Key '{key}' not found in config file '{path}'.")


# ---------------------------------------------------------------------------
# Example / smoke-test (runs only when executed directly)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile
    import os

    sample = {"host": "localhost", "port": 5432, "debug": True}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(sample, tmp)
        tmp_path = tmp.name

    try:
        assert get_config_value(tmp_path, "host") == "localhost"
        assert get_config_value(tmp_path, "port") == 5432
        assert get_config_value(tmp_path, "missing_key", default="fallback") == "fallback"
        assert get_config_value(tmp_path, "missing_key", default=None) is None

        try:
            get_config_value(tmp_path, "missing_key")
            assert False, "Expected KeyError"
        except KeyError:
            pass

        try:
            get_config_value("/nonexistent/path/config.json", "key")
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError:
            pass

        print("All assertions passed.")
    finally:
        os.unlink(tmp_path)
