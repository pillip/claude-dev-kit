"""Tests for ISSUE-016 lifecycle hooks: SessionEnd/Stop cleanup.

The WorktreeCreate freeze hook was removed in ISSUE-027: the live probe +
official docs showed WorktreeCreate is a CREATOR contract ("replaces default
git behavior" — the hook must create the worktree and print its path; no
output aborts creation). The kit's notification-consumer hook therefore broke
native worktree creation for plugin users. Freeze markers are written by
scripts/wt_setup.sh on the skill path instead."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "project" / ".claude" / "hooks"
CLEANUP = HOOKS / "run_cleanup.py"


def _run(script: Path, payload, cwd: Path, env_root: Path | None = None) -> int:
    import os
    env = dict(os.environ)
    if env_root is not None:
        env["HOOK_ROOT"] = str(env_root)
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=(payload if isinstance(payload, str) else json.dumps(payload)).encode("utf-8"),
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode


# ── SessionEnd / Stop cleanup hook ───────────────────────────────────


def test_cleanup_removes_state_and_rotates_events():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        run = root / ".claude" / "run"
        run.mkdir(parents=True)
        (run / "agent-state.json").write_text('{"active_agents": {}}', encoding="utf-8")
        (run / "events.jsonl").write_text('{"e": 1}\n{"e": 2}\n', encoding="utf-8")

        rc = _run(CLEANUP, {"hook_event_name": "SessionEnd", "cwd": str(root)}, root, env_root=root)
        assert rc == 0
        assert not (run / "agent-state.json").exists()
        assert not (run / "events.jsonl").exists()
        rotated = run / "events.jsonl.1"
        assert rotated.exists()
        assert rotated.read_text() == '{"e": 1}\n{"e": 2}\n'


def test_cleanup_noops_when_run_dir_absent():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".claude").mkdir()  # .claude exists but no run/
        rc = _run(CLEANUP, {"hook_event_name": "Stop", "cwd": str(root)}, root, env_root=root)
        assert rc == 0


def test_cleanup_empty_events_not_rotated():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        run = root / ".claude" / "run"
        run.mkdir(parents=True)
        (run / "events.jsonl").write_text("", encoding="utf-8")
        rc = _run(CLEANUP, {"hook_event_name": "SessionEnd", "cwd": str(root)}, root, env_root=root)
        assert rc == 0
        # empty log: nothing to preserve, no rotation created
        assert not (run / "events.jsonl.1").exists()
