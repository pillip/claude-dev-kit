#!/usr/bin/env python3
import json, sys
from pathlib import Path

def load_json(p: Path):
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

def deep_merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst

def main():
    if len(sys.argv) != 3:
        print("Usage: merge_settings.py <project_settings.json> <snippet.json>", file=sys.stderr)
        sys.exit(2)
    project_path = Path(sys.argv[1])
    snippet_path = Path(sys.argv[2])
    merged = deep_merge(load_json(project_path), load_json(snippet_path))
    project_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = project_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(project_path)

if __name__ == "__main__":
    main()
