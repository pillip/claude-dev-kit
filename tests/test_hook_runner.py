"""End-to-end test: inline hook command resolves repo root correctly in worktrees."""
import json, subprocess, tempfile
from pathlib import Path

HOOK_SCRIPT_REL = ".claude/hooks/agent_state.py"
HOOK_SOURCE = Path(__file__).resolve().parents[1] / "project" / HOOK_SCRIPT_REL

# The inline command from settings.snippet.json (minus the outer bash -c wrapper
# so we can inject it programmatically).
INLINE_CMD = (
    'R=$(git rev-parse --show-toplevel 2>/dev/null || echo "."); '
    'G=$(git rev-parse --git-dir 2>/dev/null || echo ".git"); '
    '[ -f "$G/commondir" ] && R=$(cd "$G/$(cat "$G/commondir")/.." && pwd); '
    '[ -f "$R/.claude/hooks/agent_state.py" ] && HOOK_ROOT="$R" python3 "$R/.claude/hooks/agent_state.py" || true'
)


def _git(cwd, *args):
    subprocess.run(["git"] + list(args), cwd=str(cwd), check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_inline_hook_in_main_repo():
    """Hook command works when CWD is the main repo root."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        _git(td, "init")
        _git(td, "config", "user.email", "test@test.com")
        _git(td, "config", "user.name", "Test")

        # Set up hook script
        hook_dir = td / ".claude" / "hooks"
        hook_dir.mkdir(parents=True)
        hook_script = hook_dir / "agent_state.py"
        hook_script.write_text(HOOK_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")

        # Need at least one commit for worktree
        (td / "dummy.txt").write_text("x")
        _git(td, "add", ".")
        _git(td, "commit", "-m", "init")

        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "cwd": str(td),
            "tool_name": "Read",
        })

        result = subprocess.run(
            ["bash", "-c", INLINE_CMD],
            input=payload.encode(),
            cwd=str(td),
            capture_output=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr.decode()}"

        state_path = td / ".claude" / "run" / "agent-state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["last_tool"] == "Read"


def test_inline_hook_in_worktree():
    """Hook command resolves main repo root when CWD is a git worktree."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        main_repo = td / "main"
        main_repo.mkdir()

        _git(main_repo, "init")
        _git(main_repo, "config", "user.email", "test@test.com")
        _git(main_repo, "config", "user.name", "Test")

        # Initial commit (without .claude/ — it's untracked in real usage)
        (main_repo / "dummy.txt").write_text("x")
        _git(main_repo, "add", ".")
        _git(main_repo, "commit", "-m", "init")

        # Set up hook script AFTER commit (untracked, like real .claude/)
        hook_dir = main_repo / ".claude" / "hooks"
        hook_dir.mkdir(parents=True)
        hook_script = hook_dir / "agent_state.py"
        hook_script.write_text(HOOK_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")

        # Create a branch and worktree
        _git(main_repo, "branch", "feature-test")
        wt_path = td / "worktree-dir"
        _git(main_repo, "worktree", "add", str(wt_path), "feature-test")

        # Verify worktree has NO .claude/ directory (it's untracked)
        assert not (wt_path / ".claude").exists(), "worktree should not have .claude/"

        payload = json.dumps({
            "hook_event_name": "SubagentStart",
            "cwd": str(wt_path),
            "agent_id": "wt-agent",
            "agent_type": "developer",
        })

        result = subprocess.run(
            ["bash", "-c", INLINE_CMD],
            input=payload.encode(),
            cwd=str(wt_path),
            capture_output=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr.decode()}"

        # State should be written in the MAIN repo's .claude/run/
        state_path = main_repo / ".claude" / "run" / "agent-state.json"
        assert state_path.exists(), "agent-state.json should be in main repo, not worktree"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["active_agents"]["wt-agent"] == "developer"


def test_inline_hook_no_hook_file_graceful():
    """When hook script doesn't exist, the inline command exits 0 (non-blocking)."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        _git(td, "init")

        # No .claude/ directory at all
        payload = json.dumps({"hook_event_name": "PreToolUse", "cwd": str(td)})

        result = subprocess.run(
            ["bash", "-c", INLINE_CMD],
            input=payload.encode(),
            cwd=str(td),
            capture_output=True,
        )
        assert result.returncode == 0, "Should exit 0 even without hook script"
