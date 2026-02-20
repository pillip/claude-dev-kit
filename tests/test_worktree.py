"""Tests for scripts/worktree.sh — git worktree lifecycle manager."""

import os
import subprocess
import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "worktree.sh")


def _run(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", SCRIPT, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def git_repo(tmp_path):
    """Create a minimal git repo with an initial commit."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.run(["git", "init", repo], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", repo, "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )
    return repo


class TestRoot:
    def test_returns_repo_root(self, git_repo):
        result = _run(["root"], git_repo)
        assert result.returncode == 0
        assert result.stdout.strip() == os.path.realpath(git_repo)


class TestCreate:
    def test_creates_worktree_and_returns_path(self, git_repo):
        result = _run(["create", "feature/foo-bar"], git_repo)
        assert result.returncode == 0
        wt_path = result.stdout.strip()
        assert wt_path.endswith(".worktrees/feature-foo-bar")
        assert os.path.isdir(wt_path)

    def test_idempotent_create(self, git_repo):
        r1 = _run(["create", "feature/foo"], git_repo)
        r2 = _run(["create", "feature/foo"], git_repo)
        assert r1.stdout.strip() == r2.stdout.strip()

    def test_slug_conversion(self, git_repo):
        result = _run(["create", "issue/ISSUE-001-login"], git_repo)
        assert result.returncode == 0
        assert "issue-ISSUE-001-login" in result.stdout


class TestPath:
    def test_existing_worktree(self, git_repo):
        _run(["create", "feature/x"], git_repo)
        result = _run(["path", "feature/x"], git_repo)
        assert result.returncode == 0
        assert result.stdout.strip().endswith(".worktrees/feature-x")

    def test_missing_worktree(self, git_repo):
        result = _run(["path", "feature/nonexistent"], git_repo)
        assert result.returncode == 1
        assert "error" in result.stderr.lower()


class TestRemove:
    def test_removes_worktree_and_branch(self, git_repo):
        _run(["create", "feature/rm-me"], git_repo)
        result = _run(["remove", "feature/rm-me"], git_repo)
        assert result.returncode == 0

        # worktree dir should be gone
        path_result = _run(["path", "feature/rm-me"], git_repo)
        assert path_result.returncode == 1

        # branch should be gone
        branch_check = subprocess.run(
            ["git", "-C", git_repo, "branch", "--list", "feature/rm-me"],
            capture_output=True,
            text=True,
        )
        assert branch_check.stdout.strip() == ""

    def test_remove_from_inside_worktree(self, git_repo):
        """Remove should succeed even when CWD is inside the worktree."""
        create_result = _run(["create", "feature/cwd-test"], git_repo)
        wt_path = create_result.stdout.strip()

        # Run remove with CWD inside the worktree
        result = _run(["remove", "feature/cwd-test"], wt_path)
        assert result.returncode == 0

        # Output should be the repo root
        assert result.stdout.strip() == os.path.realpath(git_repo)

        # Worktree should be gone
        assert not os.path.isdir(wt_path)

    def test_remove_nonexistent_is_noop(self, git_repo):
        result = _run(["remove", "feature/ghost"], git_repo)
        assert result.returncode == 0


class TestUsage:
    def test_no_args(self, git_repo):
        result = _run([], git_repo)
        assert result.returncode == 1

    def test_create_no_branch(self, git_repo):
        result = _run(["create"], git_repo)
        assert result.returncode == 1
