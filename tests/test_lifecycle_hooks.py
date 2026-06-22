"""Tests for ISSUE-016 lifecycle hooks: WorktreeCreate freeze + SessionEnd cleanup."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "project" / ".claude" / "hooks"
FREEZE = HOOKS / "worktree_freeze.py"
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


# ── WorktreeCreate freeze hook ───────────────────────────────────────


def test_freeze_writes_marker_from_payload_path():
    with tempfile.TemporaryDirectory() as td:
        wt = Path(td) / "wt" / "issue-x"
        wt.mkdir(parents=True)
        rc = _run(FREEZE, {"hook_event_name": "WorktreeCreate", "worktree_path": str(wt)}, Path(td))
        assert rc == 0
        marker = wt / ".claude-kit" / "freeze-dir.txt"
        assert marker.exists()
        assert marker.read_text().strip() == str(wt)


def test_freeze_falls_back_to_cwd_when_no_path_key():
    with tempfile.TemporaryDirectory() as td:
        wt = Path(td)
        rc = _run(FREEZE, {"hook_event_name": "WorktreeCreate", "cwd": str(wt)}, wt)
        assert rc == 0
        assert (wt / ".claude-kit" / "freeze-dir.txt").read_text().strip() == str(wt)


def test_freeze_noops_on_empty_payload():
    with tempfile.TemporaryDirectory() as td:
        rc = _run(FREEZE, "", Path(td))
        assert rc == 0  # no crash, no marker


def test_freeze_noops_on_malformed_payload():
    with tempfile.TemporaryDirectory() as td:
        rc = _run(FREEZE, "not json at all {", Path(td))
        assert rc == 0


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
