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


# ── helpers ───────────────────────────────────────────────────────────


def _mock_run(returncode=0, stdout="", stderr=""):
    """Create a mock CompletedProcess."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def _setup_issues(tmp_path: Path, content: str) -> None:
    """Write issues.md and patch _repo_root to return tmp_path."""
    (tmp_path / "issues.md").write_text(content)


@pytest.fixture()
def repo_root(tmp_path, monkeypatch):
    """Fixture that patches _repo_root to return tmp_path."""
    monkeypatch.setattr(vc, "_repo_root", lambda: tmp_path)
    return tmp_path


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


# ── _run — FileNotFoundError handling ─────────────────────────────────


class TestRun:
    def test_returns_127_when_command_not_found(self):
        result = vc._run(["nonexistent_binary_xyz_123"])
        assert result.returncode == 127
        assert "command not found" in result.stderr

    def test_normal_command_works(self):
        result = vc._run(["python3", "--version"])
        assert result.returncode == 0


# ── _repo_root ────────────────────────────────────────────────────────


class TestRepoRoot:
    def test_returns_path(self):
        """_repo_root should return a Path (basic smoke test)."""
        root = vc._repo_root()
        assert isinstance(root, Path)


# ── _default_branch ──────────────────────────────────────────────────


class TestDefaultBranch:
    def test_detects_main(self):
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="refs/remotes/origin/main\n")):
            assert vc._default_branch() == "main"

    def test_detects_master(self):
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="refs/remotes/origin/master\n")):
            assert vc._default_branch() == "master"

    def test_fallback_to_main(self):
        """When symbolic-ref fails, fall back to checking refs/heads."""
        call_count = {"n": 0}

        def side_effect(cmd, **kwargs):
            call_count["n"] += 1
            if "symbolic-ref" in cmd:
                return _mock_run(1)
            if "main" in cmd:
                return _mock_run(0)
            return _mock_run(1)

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc._default_branch() == "main"


# ── _find_issue_block ─────────────────────────────────────────────────


class TestFindIssueBlock:
    def test_returns_block_for_existing_issue(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: First issue\n"
            "- Status: doing\n"
            "- GH-Issue: #1\n"
            "\n"
            "### ISSUE-002: Second issue\n"
            "- Status: backlog\n",
        )
        block = vc._find_issue_block("ISSUE-001")
        assert block is not None
        assert "First issue" in block
        assert "Second issue" not in block

    def test_returns_last_issue_without_trailing_newline(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: First\n"
            "- Status: doing\n"
            "### ISSUE-002: Last\n"
            "- Status: done\n"
            "- PR: #99",  # no trailing newline
        )
        block = vc._find_issue_block("ISSUE-002")
        assert block is not None
        assert "PR: #99" in block

    def test_returns_none_for_missing_issue(self, repo_root):
        _setup_issues(repo_root, "### ISSUE-001: Only issue\n- Status: doing\n")
        assert vc._find_issue_block("ISSUE-999") is None

    def test_returns_none_when_file_missing(self, repo_root):
        # issues.md not created — repo_root points to empty tmp_path
        assert vc._find_issue_block("ISSUE-001") is None


# ── _find_worktree_path ───────────────────────────────────────────────


class TestFindWorktreePath:
    def test_finds_exact_match(self):
        stdout = "worktree /tmp/wt/issue/issue-001-slug\nbranch refs/heads/issue/issue-001-slug\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=stdout)):
            assert vc._find_worktree_path("ISSUE-001") == "/tmp/wt/issue/issue-001-slug"

    def test_does_not_match_similar_ids(self):
        """ISSUE-001 must NOT match worktree for ISSUE-0010."""
        stdout = "worktree /tmp/wt/issue/issue-0010-other\nbranch refs/heads/issue/issue-0010-other\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=stdout)):
            assert vc._find_worktree_path("ISSUE-001") is None

    def test_returns_none_when_no_worktree(self):
        stdout = "worktree /main\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=stdout)):
            assert vc._find_worktree_path("ISSUE-001") is None


# ── Implement verifiers ──────────────────────────────────────────────


class TestVerifyImplementIssue:
    def test_pass_when_issue_exists(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Test issue\n"
            "- GH-Issue: https://github.com/org/repo/issues/1\n"
            "- Status: doing\n",
        )
        with patch.object(vc, "_run", return_value=_mock_run(0)):
            assert vc.verify_implement_issue("ISSUE-001") is True

    def test_fail_when_no_gh_issue_field(self, repo_root):
        _setup_issues(repo_root, "### ISSUE-001: Test issue\n- Status: doing\n")
        assert vc.verify_implement_issue("ISSUE-001") is False

    def test_fail_when_issues_md_missing(self, repo_root):
        assert vc.verify_implement_issue("ISSUE-001") is False

    def test_fail_when_gh_view_fails(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Test issue\n"
            "- GH-Issue: #1\n",
        )
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

    def test_no_false_positive_on_similar_id(self):
        """ISSUE-001 must NOT match ISSUE-0010."""
        stdout = "worktree /tmp/wt/issue/issue-0010-feature\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=stdout)):
            assert vc.verify_implement_worktree("ISSUE-001") is False


class TestVerifyImplementCode:
    @pytest.fixture(autouse=True)
    def _patch_default_branch(self, monkeypatch):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

    def test_pass_with_committed_non_docs_changes(self):
        wt_path = "/tmp/wt/issue/issue-001-slug"

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt_path}\n")
            if cmd[:2] == ["git", "diff"] and "main" in cmd:
                return _mock_run(0, stdout="src/main.py\ntests/test_main.py\n")
            return _mock_run(0, stdout="")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_code("ISSUE-001") is True

    def test_pass_with_untracked_files(self):
        wt_path = "/tmp/wt/issue/issue-001-slug"

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt_path}\n")
            if "ls-files" in cmd:
                return _mock_run(0, stdout="src/new_file.py\n")
            return _mock_run(0, stdout="")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_code("ISSUE-001") is True

    def test_fail_with_only_docs_changes(self):
        wt_path = "/tmp/wt/issue/issue-001-slug"

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt_path}\n")
            if cmd[:2] == ["git", "diff"] and "main" in cmd:
                return _mock_run(0, stdout="docs/readme.md\ndocs/notes.md\n")
            return _mock_run(0, stdout="")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_code("ISSUE-001") is False

    def test_fail_with_no_changes_at_all(self):
        wt_path = "/tmp/wt/issue/issue-001-slug"

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt_path}\n")
            return _mock_run(0, stdout="")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_code("ISSUE-001") is False


class TestHasRealTests:
    """Tests for _has_real_tests() — hollow test detection."""

    def test_empty_python_file_fails(self, tmp_path):
        (tmp_path / "test_empty.py").write_text("")
        assert vc._has_real_tests("test_empty.py", str(tmp_path)) is False

    def test_pass_only_python_file_fails(self, tmp_path):
        (tmp_path / "test_stub.py").write_text("def test_nothing():\n    pass\n")
        assert vc._has_real_tests("test_stub.py", str(tmp_path)) is False

    def test_python_file_with_assert_passes(self, tmp_path):
        (tmp_path / "test_real.py").write_text(
            "def test_addition():\n    assert 1 + 1 == 2\n"
        )
        assert vc._has_real_tests("test_real.py", str(tmp_path)) is True

    def test_python_file_with_mock_passes(self, tmp_path):
        (tmp_path / "test_mock.py").write_text(
            "from unittest.mock import mock\n"
            "def test_with_mock():\n    mock.call()\n"
        )
        assert vc._has_real_tests("test_mock.py", str(tmp_path)) is True

    def test_python_file_with_pytest_raises_passes(self, tmp_path):
        (tmp_path / "test_raises.py").write_text(
            "import pytest\n"
            "def test_error():\n    with pytest.raises(ValueError): pass\n"
        )
        assert vc._has_real_tests("test_raises.py", str(tmp_path)) is True

    def test_python_file_without_test_functions_fails(self, tmp_path):
        (tmp_path / "test_no_funcs.py").write_text(
            "# Just a comment\nprint('hello')\n"
        )
        assert vc._has_real_tests("test_no_funcs.py", str(tmp_path)) is False

    def test_js_file_with_expect_passes(self, tmp_path):
        (tmp_path / "app.test.ts").write_text(
            "describe('app', () => {\n"
            "  it('works', () => { expect(true).toBe(true); });\n"
            "});\n"
        )
        assert vc._has_real_tests("app.test.ts", str(tmp_path)) is True

    def test_js_file_without_expect_fails(self, tmp_path):
        (tmp_path / "app.test.ts").write_text(
            "describe('app', () => {\n"
            "  it('empty', () => {});\n"
            "});\n"
        )
        assert vc._has_real_tests("app.test.ts", str(tmp_path)) is False

    def test_js_file_without_test_block_fails(self, tmp_path):
        (tmp_path / "app.test.js").write_text("console.log('no tests');\n")
        assert vc._has_real_tests("app.test.js", str(tmp_path)) is False

    def test_nonexistent_file_fails(self, tmp_path):
        assert vc._has_real_tests("missing.py", str(tmp_path)) is False

    def test_unknown_extension_passes(self, tmp_path):
        (tmp_path / "test_file.rb").write_text("# ruby file")
        assert vc._has_real_tests("test_file.rb", str(tmp_path)) is True


class TestCheckAcTestCoverage:
    """Tests for _check_ac_test_coverage() — advisory AC matching."""

    def test_warns_on_uncovered_ac(self, repo_root, capsys):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Login feature\n"
            "- Status: doing\n"
            "#### AC\n"
            "- [ ] User should authenticate with valid credentials\n"
            "- [ ] Invalid password returns error message\n",
        )
        # Write a test that only covers authentication
        tests_dir = repo_root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_login.py").write_text(
            "def test_authenticate():\n    assert True\n"
        )
        vc._check_ac_test_coverage(
            "ISSUE-001", str(repo_root), ["tests/test_login.py"]
        )
        captured = capsys.readouterr()
        # Should warn about the uncovered AC
        assert "WARN" in captured.out

    def test_no_warning_when_all_covered(self, repo_root, capsys):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Login feature\n"
            "- Status: doing\n"
            "- [ ] authenticate with credentials\n",
        )
        tests_dir = repo_root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_login.py").write_text(
            "def test_authenticate_with_credentials():\n    assert True\n"
        )
        vc._check_ac_test_coverage(
            "ISSUE-001", str(repo_root), ["tests/test_login.py"]
        )
        captured = capsys.readouterr()
        assert "WARN" not in captured.out

    def test_no_crash_when_issue_missing(self, repo_root, capsys):
        _setup_issues(repo_root, "### ISSUE-002: Other\n- Status: doing\n")
        vc._check_ac_test_coverage("ISSUE-001", str(repo_root), [])
        # Should not crash, just return silently


class TestVerifyImplementTestsWrittenStrengthened:
    """Tests for strengthened verify_implement_tests_written — hollow test rejection."""

    @pytest.fixture(autouse=True)
    def _patch_default_branch(self, monkeypatch):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

    def test_fail_with_hollow_test_file(self, repo_root, tmp_path):
        """Test file exists but contains no assertions — should FAIL."""
        wt_path = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt_path.mkdir(parents=True)

        tests_dir = wt_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_hollow.py").write_text("def test_nothing():\n    pass\n")

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt_path}\n")
            if cmd[:2] == ["git", "diff"] and "main" in cmd:
                return _mock_run(0, stdout="tests/test_hollow.py\n")
            return _mock_run(0, stdout="")

        _setup_issues(repo_root, "### ISSUE-001: Test\n- Status: doing\n")
        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_tests_written("ISSUE-001") is False

    def test_pass_with_real_test_file(self, repo_root, tmp_path):
        """Test file with real assertions — should PASS."""
        wt_path = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt_path.mkdir(parents=True)

        tests_dir = wt_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_real.py").write_text(
            "def test_addition():\n    assert 1 + 1 == 2\n"
        )

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt_path}\n")
            if cmd[:2] == ["git", "diff"] and "main" in cmd:
                return _mock_run(0, stdout="tests/test_real.py\n")
            return _mock_run(0, stdout="")

        _setup_issues(repo_root, "### ISSUE-001: Test\n- Status: doing\n")
        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_tests_written("ISSUE-001") is True


class TestVerifyImplementTest:
    def test_pass_when_pytest_succeeds(self, tmp_path):
        wt_path = str(tmp_path)
        # Create markers so the function detects Python project
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
        wt_stdout = f"worktree {wt_path}\n"

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=wt_stdout)
            return _mock_run(0)

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_test("ISSUE-001") is True

    def test_fail_when_pytest_fails(self, tmp_path):
        wt_path = str(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
        wt_stdout = f"worktree {wt_path}\n"

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=wt_stdout)
            return _mock_run(1, stdout="FAILED")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_test("ISSUE-001") is False

    def test_runs_in_worktree_cwd(self, tmp_path):
        """Verify pytest is invoked with cwd set to the worktree path."""
        # Create a worktree-like path that contains the issue slug
        wt_dir = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt_dir.mkdir(parents=True)
        (wt_dir / "pyproject.toml").write_text("[tool.pytest]\n")
        wt_path = str(wt_dir)
        wt_stdout = f"worktree {wt_path}\n"
        captured_cwds = []

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=wt_stdout)
            captured_cwds.append(kwargs.get("cwd"))
            return _mock_run(0)

        with patch.object(vc, "_run", side_effect=side_effect):
            vc.verify_implement_test("ISSUE-001")

        # At least one call should use the worktree path as cwd
        assert wt_path in captured_cwds

    def test_fallback_when_pytest_cov_missing(self, tmp_path):
        """When pytest-cov is not installed, should fall back to plain pytest."""
        wt_path = str(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
        wt_stdout = f"worktree {wt_path}\n"
        call_count = {"n": 0}

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=wt_stdout)
            call_count["n"] += 1
            if call_count["n"] == 1 and "--cov=." in cmd:
                # First call with coverage fails
                return _mock_run(1, stderr="unrecognized arguments: --cov")
            return _mock_run(0)  # Fallback plain pytest passes

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_test("ISSUE-001") is True


class TestVerifyImplementPush:
    def test_pass_when_remote_branch_exists(self):
        def side_effect(cmd, **kwargs):
            if "fetch" in cmd:
                return _mock_run(0)
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout="worktree /tmp/wt/issue/issue-001-slug\n")
            return _mock_run(0, stdout="  origin/issue/issue-001-slug\n  origin/main\n")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_push("ISSUE-001") is True

    def test_fail_when_no_remote_branch(self):
        def side_effect(cmd, **kwargs):
            if "fetch" in cmd:
                return _mock_run(0)
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout="worktree /tmp/wt/issue/issue-001-slug\n")
            return _mock_run(0, stdout="  origin/main\n")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_push("ISSUE-001") is False

    def test_no_false_positive_on_similar_branch(self):
        """ISSUE-001 must NOT match origin/issue/issue-0010-feature."""
        def side_effect(cmd, **kwargs):
            if "fetch" in cmd:
                return _mock_run(0)
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout="")
            return _mock_run(0, stdout="  origin/issue/issue-0010-feature\n")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_push("ISSUE-001") is False


class TestVerifyImplementPr:
    def test_pass_when_pr_has_closes_ref(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Test\n"
            "- PR: https://github.com/org/repo/pull/42\n",
        )
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="Closes #1\nSome description")):
            assert vc.verify_implement_pr("ISSUE-001") is True

    def test_pass_when_pr_has_fixes_ref(self, repo_root):
        """GitHub also accepts 'Fixes #N' as a closing keyword."""
        _setup_issues(
            repo_root,
            "### ISSUE-001: Test\n"
            "- PR: https://github.com/org/repo/pull/42\n",
        )
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="Fixes #1\nSome description")):
            assert vc.verify_implement_pr("ISSUE-001") is True

    def test_pass_when_pr_has_resolves_ref(self, repo_root):
        """GitHub also accepts 'Resolves #N' as a closing keyword."""
        _setup_issues(
            repo_root,
            "### ISSUE-001: Test\n"
            "- PR: https://github.com/org/repo/pull/42\n",
        )
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="Resolves #1\nSome description")):
            assert vc.verify_implement_pr("ISSUE-001") is True

    def test_fail_when_no_closing_keyword(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Test\n"
            "- PR: https://github.com/org/repo/pull/42\n",
        )
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="Just a PR body")):
            assert vc.verify_implement_pr("ISSUE-001") is False


class TestVerifyImplementRegistry:
    def test_pass_when_done_with_pr(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Test\n"
            "- Status: done\n"
            "- PR: https://github.com/org/repo/pull/42\n",
        )
        assert vc.verify_implement_registry("ISSUE-001") is True

    def test_fail_when_status_not_done(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Test\n"
            "- Status: doing\n"
            "- PR: https://github.com/org/repo/pull/42\n",
        )
        assert vc.verify_implement_registry("ISSUE-001") is False


# ── Review verifiers ─────────────────────────────────────────────────


class TestVerifyReviewReview:
    def test_pass_with_markdown_header_sections(self, tmp_path):
        wt_stdout = f"worktree {tmp_path}/wt/issue/issue-001-slug\n"
        notes_dir = tmp_path / "wt" / "issue" / "issue-001-slug" / "docs"
        notes_dir.mkdir(parents=True)
        (notes_dir / "review_notes.md").write_text(
            "# Code Review\nFindings here.\n\n# Security Findings\nNone.\n"
        )

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=wt_stdout)):
            assert vc.verify_review_review("ISSUE-001") is True

    def test_pass_with_h2_headers(self, tmp_path):
        wt_stdout = f"worktree {tmp_path}/wt/issue/issue-001-slug\n"
        notes_dir = tmp_path / "wt" / "issue" / "issue-001-slug" / "docs"
        notes_dir.mkdir(parents=True)
        (notes_dir / "review_notes.md").write_text(
            "## Code Review\nFindings.\n\n## Security Findings\nNone.\n"
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

    def test_fail_when_text_not_header(self, tmp_path):
        """Plain text 'Code Review' without markdown header prefix should fail."""
        wt_stdout = f"worktree {tmp_path}/wt/issue/issue-001-slug\n"
        notes_dir = tmp_path / "wt" / "issue" / "issue-001-slug" / "docs"
        notes_dir.mkdir(parents=True)
        (notes_dir / "review_notes.md").write_text(
            "No Code Review was needed.\nNo Security Findings found.\n"
        )

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=wt_stdout)):
            assert vc.verify_review_review("ISSUE-001") is False


# ── _is_ui_issue ─────────────────────────────────────────────────────


class TestIsUiIssue:
    def test_detects_ui_track(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Add login\n"
            "- Track: UI\n"
            "- Status: doing\n",
        )
        assert vc._is_ui_issue("ISSUE-001") is True

    def test_detects_component_in_title(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Build dashboard component\n"
            "- Status: doing\n",
        )
        assert vc._is_ui_issue("ISSUE-001") is True

    def test_detects_screen_keyword(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Design settings screen\n"
            "- Status: doing\n",
        )
        assert vc._is_ui_issue("ISSUE-001") is True

    def test_returns_false_for_backend_issue(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Add rate limiting to API\n"
            "- Track: Backend\n"
            "- Status: doing\n",
        )
        assert vc._is_ui_issue("ISSUE-001") is False

    def test_returns_false_when_issue_missing(self, repo_root):
        _setup_issues(repo_root, "### ISSUE-002: Other\n- Status: doing\n")
        assert vc._is_ui_issue("ISSUE-001") is False


# ── Review UI-review verifier ─────────────────────────────────────────


class TestVerifyReviewUiReview:
    def test_pass_with_required_sections(self, tmp_path, repo_root):
        # Setup as UI issue
        _setup_issues(repo_root, "### ISSUE-001: Build dashboard component\n- Status: doing\n")

        wt_stdout = f"worktree {tmp_path}/wt/issue/issue-001-slug\n"
        notes_dir = tmp_path / "wt" / "issue" / "issue-001-slug" / "docs"
        notes_dir.mkdir(parents=True)
        (notes_dir / "ui_review_notes.md").write_text(
            "# UI Review Notes\n\n"
            "## State Coverage\nAll screens covered.\n\n"
            "## Copy Compliance\nAll copy matches guide.\n\n"
            "## Design Token Compliance\nNo issues.\n"
        )

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=wt_stdout)):
            assert vc.verify_review_ui_review("ISSUE-001") is True

    def test_fail_when_file_missing(self, tmp_path, repo_root):
        _setup_issues(repo_root, "### ISSUE-001: Build UI screen\n- Status: doing\n")

        wt_stdout = f"worktree {tmp_path}/wt/issue/issue-001-slug\n"
        wt_dir = tmp_path / "wt" / "issue" / "issue-001-slug" / "docs"
        wt_dir.mkdir(parents=True)

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=wt_stdout)):
            assert vc.verify_review_ui_review("ISSUE-001") is False

    def test_fail_when_sections_missing(self, tmp_path, repo_root):
        _setup_issues(repo_root, "### ISSUE-001: Build UI screen\n- Status: doing\n")

        wt_stdout = f"worktree {tmp_path}/wt/issue/issue-001-slug\n"
        notes_dir = tmp_path / "wt" / "issue" / "issue-001-slug" / "docs"
        notes_dir.mkdir(parents=True)
        (notes_dir / "ui_review_notes.md").write_text(
            "# UI Review Notes\n\n## Some Other Section\nContent.\n"
        )

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=wt_stdout)):
            assert vc.verify_review_ui_review("ISSUE-001") is False

    def test_fail_when_no_worktree(self, repo_root):
        _setup_issues(repo_root, "### ISSUE-001: Build UI screen\n- Status: doing\n")

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="worktree /main\n")):
            assert vc.verify_review_ui_review("ISSUE-001") is False

    def test_auto_skip_for_non_ui_issue(self, repo_root):
        """Non-UI issues should auto-pass the ui-review checkpoint."""
        _setup_issues(
            repo_root,
            "### ISSUE-001: Add rate limiting to API\n"
            "- Track: Backend\n"
            "- Status: doing\n",
        )
        assert vc.verify_review_ui_review("ISSUE-001") is True


# ── Ship verifiers ───────────────────────────────────────────────────


class TestVerifyImplementRed:
    """Tests for TDD Red phase verifier — tests should exist but FAIL."""

    @pytest.fixture(autouse=True)
    def _patch_default_branch(self, monkeypatch):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

    def test_pass_when_tests_fail(self, tmp_path):
        """Tests exist with assertions and pytest fails — RED phase PASS."""
        wt_path = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt_path.mkdir(parents=True)
        (wt_path / "pyproject.toml").write_text("[tool.pytest]\n")
        tests_dir = wt_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_feature.py").write_text(
            "def test_new_feature():\n    assert False  # not implemented yet\n"
        )

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt_path}\n")
            if cmd[:2] == ["git", "diff"] and "main" in cmd:
                return _mock_run(0, stdout="tests/test_feature.py\n")
            if "pytest" in cmd:
                return _mock_run(1, stdout="FAILED")  # Tests fail = good for RED
            return _mock_run(0, stdout="")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_red("ISSUE-001") is True

    def test_fail_when_tests_pass(self, tmp_path):
        """Tests exist and pass — RED phase FAIL (tests should fail before implementation)."""
        wt_path = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt_path.mkdir(parents=True)
        (wt_path / "pyproject.toml").write_text("[tool.pytest]\n")
        tests_dir = wt_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_feature.py").write_text(
            "def test_trivial():\n    assert True  # passes without implementation\n"
        )

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt_path}\n")
            if cmd[:2] == ["git", "diff"] and "main" in cmd:
                return _mock_run(0, stdout="tests/test_feature.py\n")
            if "pytest" in cmd:
                return _mock_run(0)  # Tests pass = bad for RED
            return _mock_run(0, stdout="")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_red("ISSUE-001") is False

    def test_fail_when_no_test_files(self, tmp_path):
        """No test files found — RED phase FAIL."""
        wt_path = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt_path.mkdir(parents=True)

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt_path}\n")
            return _mock_run(0, stdout="")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_red("ISSUE-001") is False

    def test_fail_when_tests_are_hollow(self, tmp_path):
        """Test files exist but have no assertions — RED phase FAIL."""
        wt_path = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt_path.mkdir(parents=True)
        tests_dir = wt_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_empty.py").write_text("def test_nothing():\n    pass\n")

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=f"worktree {wt_path}\n")
            if cmd[:2] == ["git", "diff"] and "main" in cmd:
                return _mock_run(0, stdout="tests/test_empty.py\n")
            return _mock_run(0, stdout="")

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_implement_red("ISSUE-001") is False


class TestVerifyReviewTestQuality:
    """Tests for verify_review_test_quality — hollow test detection during review."""

    def test_pass_with_real_tests(self, tmp_path):
        wt_path = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt_path.mkdir(parents=True)
        tests_dir = wt_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_good.py").write_text(
            "def test_addition():\n    assert 1 + 1 == 2\n"
        )

        wt_stdout = f"worktree {wt_path}\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=wt_stdout)):
            assert vc.verify_review_test_quality("ISSUE-001") is True

    def test_fail_with_hollow_tests(self, tmp_path):
        wt_path = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt_path.mkdir(parents=True)
        tests_dir = wt_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_hollow.py").write_text("def test_nothing():\n    pass\n")

        wt_stdout = f"worktree {wt_path}\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=wt_stdout)):
            assert vc.verify_review_test_quality("ISSUE-001") is False

    def test_pass_when_no_test_files(self, tmp_path):
        """No test files at all — should still pass (some repos may not have tests)."""
        wt_path = tmp_path / "wt" / "issue" / "issue-001-slug"
        wt_path.mkdir(parents=True)

        wt_stdout = f"worktree {wt_path}\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=wt_stdout)):
            assert vc.verify_review_test_quality("ISSUE-001") is True


class TestVerifyShipSmoke:
    """Tests for verify_ship_smoke — post-merge regression test on main."""

    def test_pass_when_tests_pass_on_main(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vc, "_repo_root", lambda: tmp_path)
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")

        def side_effect(cmd, **kwargs):
            if cmd == ["git", "branch", "--show-current"]:
                return _mock_run(0, stdout="main\n")
            return _mock_run(0)

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_ship_smoke("ISSUE-001") is True

    def test_fail_when_not_on_main(self, monkeypatch):
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="feature-branch\n")):
            assert vc.verify_ship_smoke("ISSUE-001") is False

    def test_fail_when_tests_fail(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vc, "_repo_root", lambda: tmp_path)
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")

        def side_effect(cmd, **kwargs):
            if cmd == ["git", "branch", "--show-current"]:
                return _mock_run(0, stdout="main\n")
            if "pytest" in cmd:
                return _mock_run(1, stdout="FAILED")
            return _mock_run(0)

        with patch.object(vc, "_run", side_effect=side_effect):
            assert vc.verify_ship_smoke("ISSUE-001") is False


class TestVerifyShipChecks:
    def test_pass_when_checks_green(self, repo_root):
        _setup_issues(repo_root, "### ISSUE-001: Test\n- PR: #42\n")

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="build\tpass\t1m\ntest\tpass\t2m\n")):
            assert vc.verify_ship_checks("ISSUE-001") is True

    def test_fail_when_no_checks_configured(self, repo_root):
        """Empty stdout from gh pr checks means no CI — should fail."""
        _setup_issues(repo_root, "### ISSUE-001: Test\n- PR: #42\n")

        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="")):
            assert vc.verify_ship_checks("ISSUE-001") is False

    def test_fail_when_checks_fail(self, repo_root):
        _setup_issues(repo_root, "### ISSUE-001: Test\n- PR: #42\n")

        with patch.object(vc, "_run", return_value=_mock_run(1, stdout="build\tfail\n")):
            assert vc.verify_ship_checks("ISSUE-001") is False


class TestVerifyShipMerge:
    def test_pass_when_merged(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Test\n"
            "- PR: https://github.com/org/repo/pull/42\n",
        )
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout="MERGED")):
            assert vc.verify_ship_merge("ISSUE-001") is True

    def test_fail_when_open(self, repo_root):
        _setup_issues(
            repo_root,
            "### ISSUE-001: Test\n"
            "- PR: https://github.com/org/repo/pull/42\n",
        )
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

    def test_no_false_positive_on_similar_id(self):
        """ISSUE-001 cleanup should pass even if ISSUE-0010 worktree exists."""
        stdout = "worktree /tmp/wt/issue/issue-0010-feature\n"
        with patch.object(vc, "_run", return_value=_mock_run(0, stdout=stdout)):
            assert vc.verify_ship_cleanup("ISSUE-001") is True


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


# ── Timeout handling ──────────────────────────────────────────────────


class TestRunTimeout:
    def test_timeout_returns_124(self):
        """_run should return exit code 124 on timeout."""
        # Use a command that sleeps longer than the timeout
        result = vc._run(["sleep", "10"], timeout=1)
        assert result.returncode == 124
        assert "timed out" in result.stderr

    def test_default_timeout_is_30(self):
        """_run should accept timeout parameter with default of 30."""
        import inspect
        sig = inspect.signature(vc._run)
        assert "timeout" in sig.parameters
        assert sig.parameters["timeout"].default == 30


# ── Retry helper ──────────────────────────────────────────────────────


class TestRunWithRetry:
    def test_retries_on_failure(self):
        """_run_with_retry should retry failed commands."""
        call_count = {"n": 0}
        original_run = vc._run

        def counting_run(cmd, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 2:
                return _mock_run(1, stderr="transient error")
            return _mock_run(0, stdout="success")

        with patch.object(vc, "_run", side_effect=counting_run):
            result = vc._run_with_retry(["some", "cmd"], max_retries=2, delay=0)
            assert result.returncode == 0
            assert call_count["n"] == 2

    def test_gives_up_after_max_retries(self):
        """_run_with_retry should stop retrying after max_retries."""
        with patch.object(vc, "_run", return_value=_mock_run(1, stderr="persistent error")):
            result = vc._run_with_retry(["some", "cmd"], max_retries=3, delay=0)
            assert result.returncode == 1

    def test_no_retry_on_success(self):
        """_run_with_retry should not retry on success."""
        call_count = {"n": 0}

        def counting_run(cmd, **kwargs):
            call_count["n"] += 1
            return _mock_run(0)

        with patch.object(vc, "_run", side_effect=counting_run):
            result = vc._run_with_retry(["some", "cmd"], max_retries=3, delay=0)
            assert result.returncode == 0
            assert call_count["n"] == 1


# ── verify_gates integration ──────────────────────────────────────────


# Import verify_gates for mocking
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_gates as vg


def _make_gate_result(gate: str, status: str, blocking: bool = True) -> vg.GateResult:
    """Create a GateResult for testing."""
    return vg.GateResult(gate=gate, status=status, blocking=blocking, output="test output", duration_s=0.1)


class TestRunVerifyGates:
    """Tests for _run_verify_gates() — gate integration helper."""

    def test_returns_true_when_import_fails(self, monkeypatch):
        """If verify_gates can't be imported, skip silently."""
        import builtins
        original_import = builtins.__import__

        def fail_import(name, *args, **kwargs):
            if name == "verify_gates":
                raise ImportError("no verify_gates")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fail_import)
        assert vc._run_verify_gates("/tmp/fake", blocking=True) is True

    def test_returns_true_when_no_gates(self):
        """Empty results → pass."""
        with patch.object(vg, "run_applicable_gates", return_value=[]):
            assert vc._run_verify_gates("/tmp/fake", blocking=True) is True

    def test_non_blocking_returns_true_on_gate_failure(self):
        """Non-blocking mode: gate failure is a warning, returns True."""
        results = [_make_gate_result("e2e-web", "fail", blocking=True)]
        with patch.object(vg, "run_applicable_gates", return_value=results):
            assert vc._run_verify_gates("/tmp/fake", blocking=False) is True

    def test_blocking_returns_false_on_gate_failure(self):
        """Blocking mode: gate failure returns False."""
        results = [_make_gate_result("e2e-web", "fail", blocking=True)]
        with patch.object(vg, "run_applicable_gates", return_value=results):
            assert vc._run_verify_gates("/tmp/fake", blocking=True) is False

    def test_blocking_returns_true_when_all_pass(self):
        """All gates pass → True regardless of blocking mode."""
        results = [
            _make_gate_result("unit", "pass"),
            _make_gate_result("e2e-web", "pass"),
        ]
        with patch.object(vg, "run_applicable_gates", return_value=results):
            assert vc._run_verify_gates("/tmp/fake", blocking=True) is True

    def test_skip_gates_dont_block(self):
        """Skipped gates should not cause failures."""
        results = [_make_gate_result("e2e-mobile", "skip", blocking=True)]
        with patch.object(vg, "run_applicable_gates", return_value=results):
            assert vc._run_verify_gates("/tmp/fake", blocking=True) is True

    def test_non_blocking_gate_failure_doesnt_block(self):
        """A non-blocking gate failure shouldn't block even in blocking mode."""
        results = [_make_gate_result("load", "fail", blocking=False)]
        with patch.object(vg, "run_applicable_gates", return_value=results):
            assert vc._run_verify_gates("/tmp/fake", blocking=True) is True

    def test_exception_in_gates_returns_true(self):
        """Unexpected exception in gates → warning, return True."""
        with patch.object(vg, "run_applicable_gates", side_effect=RuntimeError("boom")):
            assert vc._run_verify_gates("/tmp/fake", blocking=True) is True


class TestVerifyGatesIntegration:
    """Integration tests: gates are called from implement_test and ship_smoke."""

    def test_implement_test_runs_gates_as_warning(self, tmp_path):
        """verify_implement_test calls _run_verify_gates with blocking=False."""
        wt_path = str(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
        wt_stdout = f"worktree {wt_path}\n"

        def run_side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=wt_stdout)
            return _mock_run(0)

        gate_calls = []

        def mock_gates(project_path, blocking=False):
            gate_calls.append({"path": str(project_path), "blocking": blocking})
            return True

        with patch.object(vc, "_run", side_effect=run_side_effect), \
             patch.object(vc, "_run_verify_gates", side_effect=mock_gates):
            result = vc.verify_implement_test("ISSUE-001")
            assert result is True
            assert len(gate_calls) == 1
            assert gate_calls[0]["blocking"] is False

    def test_ship_smoke_runs_gates_blocking(self, tmp_path, monkeypatch):
        """verify_ship_smoke calls _run_verify_gates with blocking=True."""
        monkeypatch.setattr(vc, "_repo_root", lambda: tmp_path)
        monkeypatch.setattr(vc, "_default_branch", lambda: "main")
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")

        def run_side_effect(cmd, **kwargs):
            if cmd == ["git", "branch", "--show-current"]:
                return _mock_run(0, stdout="main\n")
            return _mock_run(0)

        gate_calls = []

        def mock_gates(project_path, blocking=False):
            gate_calls.append({"path": str(project_path), "blocking": blocking})
            return True

        with patch.object(vc, "_run", side_effect=run_side_effect), \
             patch.object(vc, "_run_verify_gates", side_effect=mock_gates):
            result = vc.verify_ship_smoke("ISSUE-001")
            assert result is True
            assert len(gate_calls) == 1
            assert gate_calls[0]["blocking"] is True

    def test_gates_skip_gracefully_when_no_platforms(self, tmp_path):
        """When verify_gates detects no platforms, gates return empty and pass."""
        wt_path = str(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
        wt_stdout = f"worktree {wt_path}\n"

        def run_side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "worktree"]:
                return _mock_run(0, stdout=wt_stdout)
            return _mock_run(0)

        with patch.object(vc, "_run", side_effect=run_side_effect), \
             patch.object(vg, "run_applicable_gates", return_value=[]):
            result = vc.verify_implement_test("ISSUE-001")
            assert result is True
