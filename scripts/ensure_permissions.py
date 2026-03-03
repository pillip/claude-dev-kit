#!/usr/bin/env python3
"""Ensure settings.local.json contains the Bash permissions required by the sprint pipeline."""
import json, sys
from pathlib import Path

REQUIRED_PERMISSIONS = [
    "Bash(git:*)",
    "Bash(gh:*)",
    "Bash(bash scripts/*)",
    "Bash(python3:*)",
    "Bash(cd:*)",
    "Bash(mkdir:*)",
    "Bash(cat:*)",
    "Bash(pytest:*)",
]


def main():
    if len(sys.argv) != 2:
        print("Usage: ensure_permissions.py <settings.local.json>", file=sys.stderr)
        sys.exit(2)

    path = Path(sys.argv[1])
    if path.exists():
        settings = json.loads(path.read_text(encoding="utf-8"))
    else:
        settings = {}

    allow = settings.setdefault("permissions", {}).setdefault("allow", [])

    added = []
    for perm in REQUIRED_PERMISSIONS:
        if perm not in allow:
            allow.append(perm)
            added.append(perm)

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

    if added:
        print(f"  ➕ Added {len(added)} permissions: {', '.join(added)}")
    else:
        print("  ✓ All required permissions already present")


if __name__ == "__main__":
    main()
