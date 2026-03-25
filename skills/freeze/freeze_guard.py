#!/usr/bin/env python3
"""PreToolUse hook: block Edit/Write outside the freeze boundary.

Reads the allowed directory from .claude-kit/freeze-dir.txt (relative to repo root).
If the file doesn't exist, all edits are allowed (freeze not configured).
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def _find_repo_root() -> Path:
    """Find the git repo root, handling worktrees."""
    try:
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()

        commondir = Path(git_dir) / "commondir"
        if commondir.exists():
            common = commondir.read_text().strip()
            return (Path(git_dir) / common / "..").resolve()

        toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return Path(toplevel)
    except Exception:
        return Path.cwd()


def _read_freeze_dir(repo_root: Path) -> str | None:
    """Read the freeze boundary path from .claude-kit/freeze-dir.txt."""
    freeze_file = repo_root / ".claude-kit" / "freeze-dir.txt"
    if not freeze_file.exists():
        return None
    boundary = freeze_file.read_text(encoding="utf-8").strip()
    if not boundary:
        return None
    # Resolve relative paths against repo root
    boundary_path = Path(boundary)
    if not boundary_path.is_absolute():
        boundary_path = (repo_root / boundary_path).resolve()
    return str(boundary_path)


def check_path(file_path: str, freeze_dir: str | None) -> tuple[bool, str]:
    """Check if file_path is within freeze_dir. Returns (blocked, reason)."""
    if freeze_dir is None:
        return False, ""

    resolved = str(Path(file_path).resolve())
    freeze_resolved = str(Path(freeze_dir).resolve())

    # Check if file is inside the freeze boundary
    if resolved.startswith(freeze_resolved + os.sep) or resolved == freeze_resolved:
        return False, ""

    return True, f"Outside freeze boundary ({freeze_dir})"


def main():
    hook_input = json.loads(sys.stdin.read())
    tool_name = hook_input.get("tool_name", "")

    if tool_name not in ("Edit", "Write"):
        return

    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        return

    repo_root = _find_repo_root()
    freeze_dir = _read_freeze_dir(repo_root)

    blocked, reason = check_path(file_path, freeze_dir)
    if blocked:
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"[freeze] Blocked: {file_path} is outside the allowed directory. "
                f"{reason}. Only files within the freeze boundary can be edited."
            ),
        }))


if __name__ == "__main__":
    main()
