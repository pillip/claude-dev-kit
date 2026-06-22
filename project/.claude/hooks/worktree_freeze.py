#!/usr/bin/env python3
"""WorktreeCreate hook — auto-write the kit's freeze marker for a new worktree.

When Claude Code creates a git worktree, this writes `.claude-kit/freeze-dir.txt`
(containing the worktree's absolute path) inside it, so `/freeze` / `/guard`
scope file edits to that worktree without any manual skill step. This is the
*primary* path on builds that fire `WorktreeCreate`; `scripts/wt_setup.sh` keeps
an identical write as a fallback for builds that don't (see ISSUE-014 matrix:
WorktreeCreate is doc-supported but not locally exercised).

Robust by design: the exact payload key for the new worktree path is not pinned,
so several likely keys are tried before falling back to `cwd`. Any malformed or
missing payload is a clean no-op (exit 0) — a hook must never break worktree
creation.
"""

import json
import os
import sys
from pathlib import Path

# Candidate payload keys for the new worktree's path, most-specific first.
_PATH_KEYS = ("worktree_path", "worktreePath", "worktree", "new_worktree",
              "path", "dir", "directory")


def _resolve_worktree(payload: dict) -> Path | None:
    for key in _PATH_KEYS:
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return Path(val)
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        return Path(cwd)
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # no payload — nothing to do
    if not isinstance(payload, dict):
        return 0

    wt = _resolve_worktree(payload)
    if wt is None:
        return 0
    try:
        marker_dir = wt / ".claude-kit"
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / "freeze-dir.txt").write_text(f"{wt}\n", encoding="utf-8")
    except OSError:
        return 0  # never fail worktree creation over a marker write
    return 0


if __name__ == "__main__":
    # HOOK_ROOT is set by the inline wrapper for consistency with other hooks,
    # but this hook resolves its target from the payload, not the repo root.
    _ = os.environ.get("HOOK_ROOT")
    raise SystemExit(main())
