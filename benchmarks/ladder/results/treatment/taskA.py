import json
from pathlib import Path
from typing import Any


def get_config_value(config_path: str | Path, key: str, default: Any = None) -> Any:
    path = Path(config_path)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{config_path!r} must contain a JSON object at the top level")
    return data.get(key, default)
