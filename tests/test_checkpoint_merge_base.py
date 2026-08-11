"""ISSUE-048: implement checkpoints scope to the branch's own delta (merge-base).

A worktree built on a stale main must not surface files that main added or
deleted after the fork point. Diffing against ``git merge-base HEAD main``
(instead of ``main`` directly), plus intersecting with files that exist in the
worktree tree, keeps the classified set to the branch's own delta so no
phantom hollow-test FAIL is manufactured for a normal source+test change.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_checkpoint as vc


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture()
def stale_base_repo(tmp_path):
    """Real git repo where main advances past the branch's fork point.

    Timeline:
      A (main)   -- fork point; branch 'feature' is cut here
      B (main)   -- main adds tests/test_mainonly.py, which 'feature' never has
      feature    -- adds arith.py + tests/test_arith.py (its own delta)

    Diffing 'feature' against main (=B) would surface tests/test_mainonly.py as
    a phantom path absent from the worktree tree; diffing against merge-base
    (=A) must not.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "A: fork point")

    # Cut the branch at the fork point A.
    _git(repo, "branch", "feature")

    # main advances to B, adding a test file the branch will never have.
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_mainonly.py").write_text(
        "def test_main_only():\n    assert True\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "B: main-only test added after fork")

    # Switch to the branch (still at A) and add its own source + test delta.
    _git(repo, "checkout", "feature")
    (repo / "arith.py").write_text(
        "def total(a, b):\n    return a + b\n", encoding="utf-8"
    )
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_arith.py").write_text(
        "from arith import total\n\n"
        "def test_total_regression():\n"
        "    assert total(1, 2) == 3\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feature: arithmetic source + test")
    return repo


class TestMergeBaseHelpers:
    def test_changed_files_vs_base_excludes_post_fork_main_files(self, stale_base_repo):
        # merge-base diff scopes to the branch's own delta; the main-only file
        # added on main after the fork point is NOT reported for this branch.
        changed = vc._changed_files_vs_base(str(stale_base_repo), "main")
        assert "tests/test_arith.py" in changed
        assert "arith.py" in changed
        assert "tests/test_mainonly.py" not in changed

    def test_existing_intersection_drops_absent_paths(self, stale_base_repo):
        # Belt-and-suspenders: a path absent from the worktree tree is dropped
        # before classification even if a raw diff had surfaced it.
        classified = vc._existing(
            str(stale_base_repo),
            {"tests/test_arith.py", "tests/test_mainonly.py"},
        )
        assert "tests/test_arith.py" in classified
        assert "tests/test_mainonly.py" not in classified

    def test_merge_base_falls_back_when_unresolvable(self, tmp_path, monkeypatch):
        # Empty/detached merge-base -> fall back to <base> rather than crashing.
        monkeypatch.setattr(vc, "_merge_base", lambda wt, base: None)
        repo = tmp_path / "r"
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(repo, "config", "user.email", "t@e")
        _git(repo, "config", "user.name", "T")
        (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "init")
        # Must return a set without raising even when merge-base is None.
        result = vc._changed_files_vs_base(str(repo), "main")
        assert isinstance(result, set)


class TestTestsWrittenScopedToBranchDelta:
    @pytest.fixture()
    def _synthetic_issue(self, stale_base_repo, monkeypatch):
        monkeypatch.setattr(vc, "_find_worktree_path", lambda issue_id: str(stale_base_repo))
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        monkeypatch.setattr(vc, "_repo_root", lambda: stale_base_repo)
        # Non-UI issue block, no AC checkboxes -> AC-coverage check is a no-op.
        (stale_base_repo / "issues.md").write_text(
            "### ISSUE-001: Add arithmetic total\n- Status: doing\n", encoding="utf-8"
        )
        return stale_base_repo

    def test_stale_base_branch_passes_without_phantom_hollow_fail(self, _synthetic_issue):
        # The whole point: a stale-base branch's tests-written checkpoint passes
        # on its own real test; the phantom main-only file never triggers a
        # hollow-test FAIL because it is scoped out by the merge-base diff.
        assert vc.verify_implement_tests_written("ISSUE-001") is True

    def test_no_regression_branch_delta_test_still_detected(self, _synthetic_issue):
        # No-regression AC: the branch's own added source+test is still detected
        # exactly as before.
        changed = vc._changed_files_vs_base(str(_synthetic_issue), "main")
        assert "tests/test_arith.py" in changed
        assert vc.verify_implement_tests_written("ISSUE-001") is True
