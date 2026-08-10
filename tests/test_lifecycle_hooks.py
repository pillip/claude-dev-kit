"""Tests for ISSUE-016 lifecycle hooks: SessionEnd/Stop cleanup.

The WorktreeCreate freeze hook was removed in ISSUE-027: the live probe +
official docs showed WorktreeCreate is a CREATOR contract ("replaces default
git behavior" — the hook must create the worktree and print its path; no
output aborts creation). The kit's notification-consumer hook therefore broke
native worktree creation for plugin users. Freeze markers are written by
scripts/wt_setup.sh on the skill path instead."""

import json
import re
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


# ── SessionStart hook (ISSUE-032) ────────────────────────────────────

SESSION_START = HOOKS / "session_start.py"


def _run_session_start(cwd: Path, extra_env: dict | None = None) -> str:
    import os
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["HOOK_ROOT"] = str(cwd)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, str(SESSION_START)],
        input=b"{}",
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.returncode == 0, proc.stderr.decode()
    return proc.stdout.decode()


def test_session_start_silent_when_nothing_to_report():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        scripts = root / "scripts"
        scripts.mkdir()
        (scripts / "kit_update_check.py").write_text("import sys; sys.exit(0)\n")
        (scripts / "kit_config.py").write_text("print('false')\n")
        out = _run_session_start(root)
        assert out.strip() == ""


def test_session_start_reports_update_and_contributor_mode():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        scripts = root / "scripts"
        scripts.mkdir()
        (scripts / "kit_update_check.py").write_text(
            "import sys; print('kit update available: v9'); sys.exit(1)\n")
        (scripts / "kit_config.py").write_text("print('true')\n")
        out = _run_session_start(root)
        assert "kit update available: v9" in out
        assert "CONTRIBUTOR MODE: ON" in out
        assert "contributor_report.py" in out


def test_session_start_noops_without_kit_root():
    # Run a COPY of the hook from a temp tree so its own-location fallback
    # (parents[3], meant for the standalone kit repo) can't find the real repo.
    import os
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        copy = root / "project" / ".claude" / "hooks" / "session_start.py"
        copy.parent.mkdir(parents=True)
        copy.write_text(SESSION_START.read_text(encoding="utf-8"), encoding="utf-8")
        env = dict(os.environ)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        env["HOOK_ROOT"] = str(root)
        proc = subprocess.run(
            [sys.executable, str(copy)], input=b"{}", cwd=str(root), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        assert proc.returncode == 0, proc.stderr.decode()
        assert proc.stdout.decode().strip() == ""


def test_session_start_wired_in_both_hook_configs():
    root = Path(__file__).resolve().parents[1]
    plugin = json.loads((root / "hooks" / "hooks.json").read_text())
    assert "SessionStart" in plugin["hooks"]
    assert "session_start.py" in json.dumps(plugin["hooks"]["SessionStart"])
    snippet = json.loads((root / "project" / ".claude" / "settings.snippet.json").read_text())
    assert "SessionStart" in snippet["hooks"]
    assert "session_start.py" in json.dumps(snippet["hooks"]["SessionStart"])


# ── SessionStart contributor path must not be version-pinned (ISSUE-037) ─

VERSION_PINNED_CACHE_RE = r"cache/.+/\d+\.\d+\.\d+/"


def _make_kit_scripts(root: Path) -> None:
    """Fake kit root: update check quiet, contributor mode ON, report stub."""
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "kit_update_check.py").write_text("import sys; sys.exit(0)\n")
    (scripts / "kit_config.py").write_text("print('true')\n")
    (scripts / "contributor_report.py").write_text("pass\n")


def test_session_start_plugin_root_output_has_no_version_pinned_path():
    """TC-037a: with CLAUDE_PLUGIN_ROOT at a version-pinned cache dir, the
    contributor-mode instruction must not bake in the pinned absolute path
    (it dies on plugin update / cache GC). It must instead direct the model
    to resolve the CURRENT kit root via the "Kit Script Root" shown in the
    preamble of any active kit skill."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pinned_root = root / "cache" / "claude-dev-kit" / "claude-dev-kit" / "0.2.0"
        _make_kit_scripts(pinned_root)
        # HOOK_ROOT (= cwd = tmp root) has no scripts/, so the kit root can
        # only come from CLAUDE_PLUGIN_ROOT — the plugin-install layout.
        out = _run_session_start(root, extra_env={"CLAUDE_PLUGIN_ROOT": str(pinned_root)})

        assert "CONTRIBUTOR MODE: ON" in out
        assert "contributor_report.py" in out
        # No version-pinned cache path segment anywhere in the instruction.
        assert not re.search(VERSION_PINNED_CACHE_RE, out), (
            f"contributor instruction leaks a version-pinned cache path:\n{out}")
        assert str(pinned_root) not in out, (
            f"contributor instruction bakes in the pinned plugin root:\n{out}")
        # The instruction must name the durable resolution mechanism: the
        # Kit Script Root printed in every active kit skill's preamble.
        assert "Kit Script Root" in out


def test_session_start_standalone_root_prints_resolvable_report_path():
    """TC-037b: standalone kit checkout (no CLAUDE_PLUGIN_ROOT) — the hook
    keeps printing a concrete absolute path, and that path must exist on
    disk (repo paths are not version-pinned; regression guard)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_kit_scripts(root)
        out = _run_session_start(root)

        assert "CONTRIBUTOR MODE: ON" in out
        match = re.search(r"python3 (\S*contributor_report\.py)", out)
        assert match, f"no contributor_report.py invocation found in:\n{out}"
        assert Path(match.group(1)).is_file(), (
            f"printed invocation path does not exist on disk: {match.group(1)}")
        assert not re.search(VERSION_PINNED_CACHE_RE, out)
