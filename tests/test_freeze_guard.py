import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "freeze" / "freeze_guard.py"


def run_hook(payload: dict, repo_root: Path | None = None) -> dict | None:
    env = None
    if repo_root:
        env = {**dict(__import__("os").environ), "GIT_WORK_TREE": str(repo_root)}

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(repo_root) if repo_root else None,
        env=env,
    )
    stdout = result.stdout.strip()
    if stdout:
        return json.loads(stdout)
    return None


def make_edit_payload(file_path: str) -> dict:
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "old_string": "a", "new_string": "b"},
    }


def make_write_payload(file_path: str) -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": "test"},
    }


@pytest.fixture
def repo_with_freeze(tmp_path):
    """Create a fake git repo with .claude-kit/freeze-dir.txt."""
    # Create a minimal git repo
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=str(tmp_path), capture_output=True,
    )

    # Create freeze boundary
    allowed_dir = tmp_path / "src" / "app"
    allowed_dir.mkdir(parents=True)
    claude_kit = tmp_path / ".claude-kit"
    claude_kit.mkdir()
    (claude_kit / "freeze-dir.txt").write_text(str(allowed_dir))

    return tmp_path, allowed_dir


class TestFreezeGuard:
    def test_blocks_edit_outside_boundary(self, repo_with_freeze):
        repo, allowed = repo_with_freeze
        outside_file = str(repo / "other" / "file.py")
        out = run_hook(make_edit_payload(outside_file), repo)
        assert out is not None
        assert out["decision"] == "block"
        assert "freeze" in out["reason"].lower()

    def test_allows_edit_inside_boundary(self, repo_with_freeze):
        repo, allowed = repo_with_freeze
        inside_file = str(allowed / "main.py")
        out = run_hook(make_edit_payload(inside_file), repo)
        assert out is None

    def test_allows_subdirectory(self, repo_with_freeze):
        repo, allowed = repo_with_freeze
        sub_file = str(allowed / "sub" / "module.py")
        out = run_hook(make_edit_payload(sub_file), repo)
        assert out is None

    def test_no_freeze_file_allows_all(self, tmp_path):
        # Git repo without freeze-dir.txt
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=str(tmp_path), capture_output=True,
        )
        out = run_hook(make_edit_payload("/anywhere/file.py"), tmp_path)
        assert out is None

    def test_blocks_write_outside_boundary(self, repo_with_freeze):
        repo, allowed = repo_with_freeze
        outside_file = str(repo / "config" / "settings.json")
        out = run_hook(make_write_payload(outside_file), repo)
        assert out is not None
        assert out["decision"] == "block"

    def test_ignores_non_edit_tools(self, repo_with_freeze):
        repo, _ = repo_with_freeze
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
        }
        out = run_hook(payload, repo)
        assert out is None
