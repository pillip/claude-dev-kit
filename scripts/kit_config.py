#!/usr/bin/env python3
"""Kit configuration management.

Stores config in ~/.claude-kit/config.json (stdlib json, no dependencies).

Usage:
    python3 scripts/kit_config.py get <key>
    python3 scripts/kit_config.py set <key> <value>
    python3 scripts/kit_config.py list
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".claude-kit"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS: dict[str, object] = {
    "contributor_mode": True,
}


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load() -> dict[str, object]:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return dict(DEFAULTS)


def _save(config: dict[str, object]) -> None:
    _ensure_dir()
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )


def _parse_value(raw: str) -> object:
    """Parse a string value to its Python type."""
    lower = raw.lower()
    if lower in ("true", "yes", "1"):
        return True
    if lower in ("false", "no", "0"):
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def get(key: str) -> object:
    config = _load()
    return config.get(key, DEFAULTS.get(key))


def set_value(key: str, value: object) -> None:
    config = _load()
    config[key] = value
    _save(config)


def list_all() -> dict[str, object]:
    return _load()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: kit_config.py <get|set|list> [key] [value]", file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]

    if cmd == "get":
        if len(sys.argv) < 3:
            print("Usage: kit_config.py get <key>", file=sys.stderr)
            sys.exit(2)
        val = get(sys.argv[2])
        if val is not None:
            # Print lowercase for booleans to match shell conventions
            if isinstance(val, bool):
                print(str(val).lower())
            else:
                print(val)

    elif cmd == "set":
        if len(sys.argv) < 4:
            print("Usage: kit_config.py set <key> <value>", file=sys.stderr)
            sys.exit(2)
        set_value(sys.argv[2], _parse_value(sys.argv[3]))
        print(f"{sys.argv[2]} = {sys.argv[3]}")

    elif cmd == "list":
        config = list_all()
        for k, v in sorted(config.items()):
            print(f"{k} = {v}")

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
