"""Unit tests for scripts/verify_checkpoint.py."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_checkpoint as vc


# ── _extract_field ────────────────────────────────────────────────────


class TestExtractField:
    def test_extracts_existing_field(self):
        text = "- Status: done\n- PR: https://github.com/org/repo/pull/42\n"
        assert vc._extract_field(text, "Status") == "done"
        assert vc._extract_field(text, "PR") == "https://github.com/org/repo/pull/42"

    def test_returns_empty_for_missing_field(self):
        text = "- Status: doing\n"
        assert vc._extract_field(text, "PR") == ""

    def test_handles_empty_value(self):
        text = "- Branch:\n- Status: backlog\n"
        assert vc._extract_field(text, "Branch") == ""

    def test_handles_whitespace_around_value(self):
        text = "- GH-Issue:   #55  \n"
        assert vc._extract_field(text, "GH-Issue") == "#55"


# ── Implement verifiers ──────────────────────────────────────────────


def _mock_run(returncode=0, stdout="", stderr=""):
    """Create a mock CompletedProcess."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class TestVerifyImplementIssue:
    def test_pass_when_issue_exists(self, tmp_path, monkeypatch):
        issues = tmp_path / "issues.md"
        issues.write_text(
            "### ISSUE-001: Test issue\n"
            "- GH-Issue: https://github.com/org/repo/issues/1\n"
            "- Status: doing\n"
        )
        monkeypatch.chdir(tmp_path)

        with patch.object(vc, "_run", return_value=_mock_run(0)):
            assert vc.verify_implement_issue("ISSUE-001") is True

    def test_fail_when_no_gh_issue_field(self, tmp_path, monkeypatch):
        issues = tmp_path / "issues.md"
        issues.write_text("### ISSUE-001: Test issue\n- Status: doing\n")
        monkeypatch.chdir(tmp_path)

        assert vc.verify_implement_issue("ISSUE-001") is False

    def test_fail_when_issues_md_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert vc.verify_implement_issue("ISSUE-001") is False

    def test_fail_when_gh_view_fails(self, tmp_path, monkeypatch):
        issues = tmp_path / "issues.md"
        issues.write_text(
            "### ISSUE-001: Test issue\n"
            "- GH-Issue: #1\n"
        )
        monkeypatch.chdir(tmp_path)

        with patch.object(vc, "_run", return_value=_mock_run(1, stderr="not found")):
            assert vc.verify_implement_issue("ISSUE-001") is False


class TestVerifyImplementWorktree:
    def test_pass_when_worktree_exists(self):
        stdout = "worktree /tmp/wt/issue/issue-001-slug\nbranch refs/heads/issue/issue-001-slug\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=stdout)):
            assert vc.verify_implement_worktree("ISSUE-001") is True

    def test_fail_when_no_matching_worktree(self):
        stdout = "worktree /tmp/wt/issue/issue-999-other\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=stdout)):
            assert vc.verify_implement_worktree("ISSUE-001") is False


class TestVerifyImplementCode:
    def test_pass_with_non_docs_changes(self):
        wt_stdout = "worktree /tmp/wt/issue/issue-001-slug\n"
        diff_stdout = "src/main.py\ntests/test_main.py\n"

        def side_effect(cmd, **kwargs):
            if cmd[0] == "git" and cmd[1] == "worktree":
                return _mock_run(0, stdout=wt_stdout)
            return _mock_run(0, stdout=diff_stdout)

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_code("ISSUE-001") is True

    def test_fail_with_only_docs_changes(self):
        wt_stdout = "worktree /tmp/wt/issue/issue-001-slug\n"
        diff_stdout = "docs/readme.md\ndocs/notes.md\n"

        def side_effect(cmd, **kwargs):
            if cmd[0] == "git" and cmd[1] == "worktree":
                return _mock_run(0, stdout=wt_stdout)
            return _mock_run(0, stdout=diff_stdout)

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_code("ISSUE-001") is False


class TestVerifyImplementTest:
    def test_pass_when_pytest_succeeds(self):
        with patch.object(vc, "_run", return_value=_mock_run(0)):
            assert vc.verify_implement_test("ISSUE-001") is True

    def test_fail_when_pytest_fails(self):
        with patch.object(vc, "_run", return_value=_mock_run(1, stdout="FAILED")):
            assert vc.verify_implement_test("ISSUE-001") is False


class TestVerifyImplementPush:
    def test_pass_when_remote_branch_exists(self):
        stdout = "  origin/issue/issue-001-slug\n  origin/main\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=stdout)):
            assert vc.verify_implement_push("ISSUE-001") is True

    def test_fail_when_no_remote_branch(self):
        stdout = "  origin/main\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=stdout)):
            assert vc.verify_implement_push("ISSUE-001") is False


class TestVerifyImplementPr:
    def test_pass_when_pr_has_closes_ref(self, tmp_path, monkeypatch):
        issues = tmp_path / "issues.md"
        issues.write_text(
            "### ISSUE-001: Test\n"
            "- PR: https://github.com/org/repo/pull/42\n"
        )
        monkeypatch.chdir(tmp_path)

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="Closes #1\nSome description")):
            assert vc.verify_implement_pr("ISSUE-001") is True

    def test_fail_when_no_closes_ref(self, tmp_path, monkeypatch):
        issues = tmp_path / "issues.md"
        issues.write_text(
            "### ISSUE-001: Test\n"
            "- PR: https://github.com/org/repo/pull/42\n"
        )
        monkeypatch.chdir(tmp_path)

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="Just a PR body")):
            assert vc.verify_implement_pr("ISSUE-001") is False


class TestVerifyImplementRegistry:
    def test_pass_when_done_with_pr(self, tmp_path, monkeypatch):
        issues = tmp_path / "issues.md"
        issues.write_text(
            "### ISSUE-001: Test\n"
            "- Status: done\n"
            "- PR: https://github.com/org/repo/pull/42\n"
        )
        monkeypatch.chdir(tmp_path)

        assert vc.verify_implement_registry("ISSUE-001") is True

    def test_fail_when_status_not_done(self, tmp_path, monkeypatch):
        issues = tmp_path / "issues.md"
        issues.write_text(
            "### ISSUE-001: Test\n"
            "- Status: doing\n"
            "- PR: https://github.com/org/repo/pull/42\n"
        )
        monkeypatch.chdir(tmp_path)

        assert vc.verify_implement_registry("ISSUE-001") is False


# ── Review verifiers ─────────────────────────────────────────────────


class TestVerifyReviewReview:
    def test_pass_with_required_sections(self, tmp_path):
        wt_stdout = f"worktree {tmp_path}/wt/issue/issue-001-slug\n"
        notes_dir = tmp_path / "wt" / "issue" / "issue-001-slug" / "docs"
        notes_dir.mkdir(parents=True)
        (notes_dir / "review_notes.md").write_text(
            "# Code Review\nFindings here.\n\n# Security Findings\nNone.\n"
        )

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=wt_stdout)):
            assert vc.verify_review_review("ISSUE-001") is True

    def test_fail_missing_sections(self, tmp_path):
        wt_stdout = f"worktree {tmp_path}/wt/issue/issue-001-slug\n"
        notes_dir = tmp_path / "wt" / "issue" / "issue-001-slug" / "docs"
        notes_dir.mkdir(parents=True)
        (notes_dir / "review_notes.md").write_text("# Some other section\n")

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=wt_stdout)):
            assert vc.verify_review_review("ISSUE-001") is False


# ── Ship verifiers ───────────────────────────────────────────────────


class TestVerifyShipMerge:
    def test_pass_when_merged(self, tmp_path, monkeypatch):
        issues = tmp_path / "issues.md"
        issues.write_text(
            "### ISSUE-001: Test\n"
            "- PR: https://github.com/org/repo/pull/42\n"
        )
        monkeypatch.chdir(tmp_path)

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="MERGED")):
            assert vc.verify_ship_merge("ISSUE-001") is True

    def test_fail_when_open(self, tmp_path, monkeypatch):
        issues = tmp_path / "issues.md"
        issues.write_text(
            "### ISSUE-001: Test\n"
            "- PR: https://github.com/org/repo/pull/42\n"
        )
        monkeypatch.chdir(tmp_path)

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="OPEN")):
            assert vc.verify_ship_merge("ISSUE-001") is False


class TestVerifyShipCleanup:
    def test_pass_when_no_worktree(self):
        stdout = "worktree /main\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=stdout)):
            assert vc.verify_ship_cleanup("ISSUE-001") is True

    def test_fail_when_worktree_exists(self):
        stdout = "worktree /tmp/wt/issue/issue-001-slug\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=stdout)):
            assert vc.verify_ship_cleanup("ISSUE-001") is False


# ── CLI main() ────────────────────────────────────────────────────────


class TestMain:
    def test_returns_0_on_pass(self):
        with patch.dict(vc.VERIFIERS, {("implement", "issue"): lambda *a, **k: True}):
            assert vc.main(["--skill", "implement", "--phase", "issue", "--issue", "ISSUE-001"]) == 0

    def test_returns_1_on_fail(self):
        with patch.dict(vc.VERIFIERS, {("implement", "issue"): lambda *a, **k: False}):
            assert vc.main(["--skill", "implement", "--phase", "issue", "--issue", "ISSUE-001"]) == 1

    def test_returns_2_on_unknown_phase(self):
        assert vc.main(["--skill", "implement", "--phase", "nonexistent", "--issue", "ISSUE-001"]) == 2

    def test_returns_2_on_missing_args(self):
        assert vc.main([]) == 2
