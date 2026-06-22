#!/usr/bin/env python3
"""SessionEnd / Stop hook — prune & rotate the kit's per-project runtime state.

`.claude/run/` accumulates state the `agent_state.py` hook writes during a
session. This cleans it up when the session ends so the directory doesn't grow
unbounded across sessions. Policy:

- `agent-state.json` — **removed.** It tracks *active* agents for the current
  session and is meaningless once the session ends.
- `events.jsonl` — **rotated.** If present and non-empty, it is moved to
  `events.jsonl.1` (replacing any older `.1`), and the next session starts a
  fresh log. This bounds disk to the current + one prior session without
  destroying the most recent trace (telemetry schema work is ISSUE-001).

No-ops cleanly when `.claude/run/` is absent. Never raises (a cleanup hook must
not disrupt session teardown).
"""

import json
import os
import sys
from pathlib import Path


def _project_root(payload: dict) -> Path:
    # HOOK_ROOT is set by the inline wrapper to handle git worktrees.
    hook_root = os.environ.get("HOOK_ROOT")
    if hook_root and (Path(hook_root) / ".claude").is_dir():
        return Path(hook_root)
    start = Path(payload.get("cwd") or os.getcwd())
    cur = start
    while True:
        if (cur / ".claude").is_dir():
            return cur
        if cur.parent == cur:
            return start
        cur = cur.parent


def cleanup(run_dir: Path) -> None:
    if not run_dir.is_dir():
        return
    state = run_dir / "agent-state.json"
    if state.exists():
        state.unlink()
    events = run_dir / "events.jsonl"
    if events.exists() and events.stat().st_size > 0:
        events.replace(run_dir / "events.jsonl.1")
    # Drop any leftover temp file from an interrupted atomic write.
    tmp = run_dir / "agent-state.json.tmp"
    if tmp.exists():
        tmp.unlink()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    try:
        cleanup(_project_root(payload) / ".claude" / "run")
    except OSError:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
