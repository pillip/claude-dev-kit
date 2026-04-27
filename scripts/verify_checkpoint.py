#!/usr/bin/env python3
"""Verify skill phase checkpoints.

Validates that each phase of a skill pipeline produced its expected artifacts.

Exit codes:
  0 — checkpoint passed
  1 — checkpoint failed (agent should stop)
  2 — usage error
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def _extract_field(text: str, field_name: str) -> str:
    """Extract a metadata field value from issue text (reused pattern from validate_issues.py)."""
    match = re.search(rf"^- {field_name}:[ \t]*(.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _run(cmd: list[str], timeout: int = 30, **kwargs) -> subprocess.CompletedProcess:
    """Run a command and return the result (no exception on failure).

    Args:
        cmd: Command and arguments to run.
        timeout: Maximum seconds to wait (default 30). 0 means no timeout.
    """
    try:
        t = timeout if timeout > 0 else None
        return subprocess.run(cmd, capture_output=True, text=True, timeout=t, **kwargs)
    except subprocess.TimeoutExpired:
        prog = cmd[0] if cmd else "<unknown>"
        mock = subprocess.CompletedProcess(cmd, 124)
        mock.stdout = ""
        mock.stderr = f"{prog}: timed out after {timeout}s"
        return mock
    except FileNotFoundError:
        # Command binary not found (e.g. gh or git not installed)
        prog = cmd[0] if cmd else "<unknown>"
        mock = subprocess.CompletedProcess(cmd, 127)
        mock.stdout = ""
        mock.stderr = f"{prog}: command not found"
        return mock


def _run_with_retry(cmd: list[str], max_retries: int = 2, delay: float = 1.0, **kwargs) -> subprocess.CompletedProcess:
    """Run a command with retry logic for transient network failures.

    Retries on non-zero exit codes up to max_retries times with a delay between attempts.
    Useful for network-dependent commands like `gh`.
    """
    result = _run(cmd, **kwargs)
    attempt = 1
    while result.returncode != 0 and attempt < max_retries:
        time.sleep(delay)
        result = _run(cmd, **kwargs)
        attempt += 1
    return result


def _repo_root() -> Path:
    """Resolve the main repository root, even from inside a worktree.

    Uses `bash scripts/worktree.sh root` if available,
    falls back to git rev-parse with commondir detection.
    """
    # Try worktree.sh first (handles all edge cases)
    wt_script = Path("scripts/worktree.sh")
    if wt_script.exists():
        result = _run(["bash", str(wt_script), "root"])
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())

    # Fallback: git-based detection
    result = _run(["git", "rev-parse", "--git-dir"])
    if result.returncode != 0:
        return Path.cwd()

    git_dir = Path(result.stdout.strip())
    commondir = git_dir / "commondir"
    if commondir.exists():
        # Inside a worktree — follow commondir link to main repo
        cd = commondir.read_text().strip()
        if not Path(cd).is_absolute():
            cd = str(git_dir / cd)
        return Path(cd).resolve().parent

    result = _run(["git", "rev-parse", "--show-toplevel"])
    if result.returncode == 0:
        return Path(result.stdout.strip())

    return Path.cwd()


def _default_branch() -> str:
    """Detect the default branch name (main, master, etc.)."""
    result = _run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"])
    if result.returncode == 0:
        # refs/remotes/origin/main → main
        return result.stdout.strip().rsplit("/", 1)[-1]

    # Fallback: try common names
    for name in ("main", "master"):
        check = _run(["git", "rev-parse", "--verify", f"refs/heads/{name}"])
        if check.returncode == 0:
            return name

    return "main"


def _find_issue_block(issue_id: str) -> str | None:
    """Read issues.md (from repo root) and return the text block for the given issue."""
    root = _repo_root()
    issues_md = root / "issues.md"
    if not issues_md.exists():
        print(f"FAIL: issues.md not found (looked at {issues_md})")
        return None

    text = issues_md.read_text(encoding="utf-8")
    # Match from ### ISSUE-NNN: to the next ### or end-of-string
    pattern = rf"(?:^### {re.escape(issue_id)}:[^\n]*)(?:\n(?!### ).*)*"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        print(f"FAIL: {issue_id} not found in issues.md")
        return None

    return match.group(0)


# Shared worktree slug boundary pattern:
# slug must be followed by -, /, end-of-string, or end-of-line
_SLUG_BOUNDARY = r"(?:-|/|$)"


def _find_worktree_path(issue_id: str) -> str | None:
    """Find the worktree path for an issue using word-boundary matching."""
    result = _run(["git", "worktree", "list", "--porcelain"])
    if result.returncode != 0:
        print(f"FAIL: git worktree list failed: {result.stderr.strip()}")
        return None

    slug = issue_id.lower()
    wt_pattern = re.compile(
        rf"{re.escape(slug)}{_SLUG_BOUNDARY}", re.IGNORECASE
    )

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1]
            if wt_pattern.search(path):
                return path

    return None


def _extract_pr_number(issue_id: str) -> str | None:
    """Extract PR number from issues.md PR field for the given issue."""
    block = _find_issue_block(issue_id)
    if block is None:
        return None

    pr_field = _extract_field(block, "PR")
    if not pr_field:
        print(f"FAIL: {issue_id} has no PR field in issues.md")
        return None

    pr_match = re.search(r"(\d+)\s*$", pr_field)
    if not pr_match:
        print(f"FAIL: cannot parse PR number from: {pr_field}")
        return None

    return pr_match.group(1)


_FIGMA_URL_PATTERN = re.compile(
    r"https?://[^\s\]\)>,]*figma\.com/(?:design|file)/[^\s\]\)>,]+"
)


def _find_figma_urls(issue_id: str) -> list[str]:
    """Extract Figma URLs from the issue's Implementation Notes section only."""
    block = _find_issue_block(issue_id)
    if not block:
        return []
    # Extract only the Implementation Notes subsection
    impl_match = re.search(
        r"####\s+Implementation Notes.*?\n(.*?)(?=\n####|\Z)",
        block,
        re.DOTALL,
    )
    if not impl_match:
        return []
    return _FIGMA_URL_PATTERN.findall(impl_match.group(1))


# ── Implement skill verifiers ────────────────────────────────────────


def verify_implement_figma(issue_id: str, **_) -> bool:
    """If the issue has Figma URLs, verify design data was fetched.

    Auto-passes when no Figma URLs are found in Implementation Notes.
    Only requires figma-export/design_data.json — does NOT require
    prototype/screens/ (that's /figma2proto's job for greenfield projects).
    """
    urls = _find_figma_urls(issue_id)
    if not urls:
        print(f"PASS: {issue_id} has no Figma URLs — figma checkpoint skipped")
        return True

    # FIGMA_TOKEN is required when Figma URLs are present
    if not os.environ.get("FIGMA_TOKEN"):
        print(f"FAIL: {issue_id} has {len(urls)} Figma URL(s) but FIGMA_TOKEN is not set")
        print(f"  FIGMA_TOKEN is REQUIRED for issues with Figma URLs.")
        print(f"  Set it with: export FIGMA_TOKEN=figd_...")
        print(f"  Then run: python3 scripts/figma_fetch.py {' '.join(urls)}")
        return False

    root = _repo_root()

    # Check design_data.json was fetched
    data_file = root / "figma-export" / "design_data.json"
    if not data_file.exists():
        print(f"FAIL: {issue_id} has {len(urls)} Figma URL(s) but figma-export/design_data.json not found")
        print(f"  Step 2a was NOT executed. You MUST run figma_fetch.py before proceeding.")
        print(f"  Run: python3 scripts/figma_fetch.py {' '.join(urls)}")
        return False

    # Verify the JSON has a summary section with actual data
    try:
        data = json.loads(data_file.read_text(encoding="utf-8"))
        summary = data.get("summary", {})
        if not summary.get("colors") and not summary.get("text_styles"):
            print(f"FAIL: design_data.json exists but summary has no colors or text styles")
            print(f"  The Figma fetch may have returned empty data — check the URLs")
            return False
    except (json.JSONDecodeError, OSError) as e:
        print(f"FAIL: cannot read design_data.json: {e}")
        return False

    # Verify prototype files were generated (upsert) — platform-aware
    platform = data.get("platform", "web")
    platform_config = data.get("platform_config", {})
    proto_base = platform_config.get("prototype_dir", "prototype")
    proto_dir = root / proto_base

    # Determine screen dir and file pattern based on platform
    if platform == "mobile":
        screen_dir = proto_dir / "src" / "screens"
        screen_glob = "*.tsx"
    else:
        screen_dir = proto_dir / "screens"
        screen_glob = "*.html"

    if not screen_dir.is_dir() or not list(screen_dir.glob(screen_glob)):
        print(f"FAIL: design_data.json exists but no screen files in {screen_dir.relative_to(root)}/")
        print(f"  Expected {screen_glob} files from figma-converter agent (platform: {platform})")
        return False

    # Verify assets were exported if any were detected
    asset_count = summary.get("asset_count", 0)
    assets_dir = root / "figma-export" / "assets"
    actual_assets = list(assets_dir.glob("*.*")) if assets_dir.is_dir() else []
    if asset_count > 0 and not actual_assets:
        print(f"FAIL: design_data.json reports {asset_count} asset(s) but figma-export/assets/ is empty")
        print(f"  Asset download may have failed — check network and FIGMA_TOKEN permissions")
        return False

    color_count = len(summary.get("colors", []))
    style_count = len(summary.get("text_styles", []))
    frame_count = summary.get("frame_count", 0)
    screen_count = len(list(screen_dir.glob(screen_glob)))
    print(f"PASS: {issue_id} — Figma prototype upserted (platform={platform}, {frame_count} frame(s), {screen_count} screen(s), {color_count} colors, {style_count} text styles, {len(actual_assets)} asset(s))")
    return True


def verify_implement_test_plan(issue_id: str, **_) -> bool:
    """Verify docs/test_plan.md exists and has a non-empty Risk Matrix.

    test_plan.md is required so the developer knows which flows are high-risk
    and what test types (unit/integration/e2e) each flow needs.
    """
    root = _repo_root()
    test_plan = root / "docs" / "test_plan.md"
    if not test_plan.exists():
        print("FAIL: docs/test_plan.md not found")
        print("  Run /kickoff first to generate a test plan, or create one manually.")
        return False

    content = test_plan.read_text(encoding="utf-8")

    # Check Risk Matrix has at least one data row (not just the header)
    # The template has: | Flow | Likelihood | Impact | Risk | Coverage Level |
    # A filled row would be: | Login | High | High | Critical | unit + e2e |
    risk_rows = re.findall(
        r"^\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|",
        content,
        re.MULTILINE,
    )
    # Filter out header and separator rows
    data_rows = [
        r for r in risk_rows
        if "Flow" not in r and "---" not in r and r.strip("| \n-")
    ]
    if not data_rows:
        print("FAIL: docs/test_plan.md exists but Risk Matrix is empty")
        print("  Fill in the Risk Matrix so developers know which flows need deep testing.")
        return False

    print(f"PASS: test_plan.md exists with {len(data_rows)} risk-assessed flow(s)")
    return True


def verify_implement_issue(issue_id: str, **_) -> bool:
    """GH-Issue field exists in issues.md and `gh issue view` succeeds."""
    block = _find_issue_block(issue_id)
    if block is None:
        return False

    gh_issue = _extract_field(block, "GH-Issue")
    if not gh_issue:
        print(f"FAIL: {issue_id} has no GH-Issue field in issues.md")
        return False

    # Extract issue number from URL or plain number
    num_match = re.search(r"(\d+)\s*$", gh_issue)
    if not num_match:
        print(f"FAIL: cannot parse issue number from GH-Issue: {gh_issue}")
        return False

    result = _run_with_retry(["gh", "issue", "view", num_match.group(1)])
    if result.returncode != 0:
        print(f"FAIL: gh issue view {num_match.group(1)} failed: {result.stderr.strip()}")
        return False

    print(f"PASS: {issue_id} — GH-Issue exists and is viewable")
    return True


def verify_implement_worktree(issue_id: str, **_) -> bool:
    """Worktree directory exists for the issue branch."""
    result = _run(["git", "worktree", "list", "--porcelain"])
    if result.returncode != 0:
        print(f"FAIL: git worktree list failed: {result.stderr.strip()}")
        return False

    slug = issue_id.lower()
    wt_pattern = re.compile(
        rf"{re.escape(slug)}{_SLUG_BOUNDARY}", re.IGNORECASE
    )
    if not wt_pattern.search(result.stdout):
        print(f"FAIL: no worktree found matching '{slug}'")
        return False

    print(f"PASS: worktree exists for {issue_id}")
    return True


def verify_implement_code(issue_id: str, **_) -> bool:
    """Worktree has non-docs file changes (committed or uncommitted)."""
    wt_path = _find_worktree_path(issue_id)
    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    base = _default_branch()

    # Committed changes vs default branch
    diff_committed = _run(["git", "diff", "--name-only", base], cwd=wt_path)
    # Staged but not yet committed
    diff_staged = _run(["git", "diff", "--name-only", "--cached"], cwd=wt_path)
    # Unstaged modifications
    diff_unstaged = _run(["git", "diff", "--name-only"], cwd=wt_path)
    # Untracked files
    untracked = _run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=wt_path
    )

    all_files: set[str] = set()
    for r in (diff_committed, diff_staged, diff_unstaged, untracked):
        if r.returncode == 0 and r.stdout.strip():
            all_files.update(r.stdout.strip().splitlines())

    changed = [f for f in all_files if f and not f.startswith("docs/")]
    if not changed:
        print("FAIL: no non-docs file changes found in worktree")
        return False

    print(f"PASS: {len(changed)} non-docs file(s) changed")
    return True


def _has_real_tests(filepath: str, wt_path: str) -> bool:
    """Check that a test file contains at least one real test with assertions."""
    full_path = Path(wt_path) / filepath
    if not full_path.exists():
        return False

    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False

    # Python test files
    if filepath.endswith(".py"):
        test_defs = re.findall(r"def (test_\w+)\s*\(", content)
        if not test_defs:
            return False
        has_assert = bool(re.search(
            r"\b(?:assert\b|assertEqual|assertTrue|assertFalse|assertRaises"
            r"|assertIn|assertIs|mock|patch|raises|pytest\.raises)\b",
            content,
        ))
        return has_assert

    # JS/TS test files
    if filepath.endswith((".ts", ".tsx", ".js", ".jsx")):
        has_test_block = bool(re.search(r"\b(?:it|test|describe)\s*\(", content))
        has_expect = bool(re.search(
            r"\b(?:expect|assert|should|toEqual|toBe|toThrow|toHaveBeenCalled"
            r"|toContain|toMatch|rejects|resolves"
            r"|expectType|expectNotType|expectAssignable|expectNotAssignable"
            r"|expectError|expectDeprecated|expectNotDeprecated)\b",
            content,
        ))
        return has_test_block and has_expect

    return True  # Unknown language, pass through


def _check_ac_test_coverage(issue_id: str, wt_path: str, test_files: list[str]) -> bool:
    """Check if AC items have corresponding tests. Returns True if coverage is insufficient.

    Matching strategy: extract meaningful keywords (5+ chars) from each AC line,
    then search test content for those keywords. Also searches for test function
    names that reference key verbs/nouns from the AC.
    """
    block = _find_issue_block(issue_id)
    if not block:
        return False

    # Extract AC lines: lines starting with "- [ ]" or "- [x]" or numbered items under AC
    ac_lines = re.findall(r"(?:^[-*]\s+\[.\]\s+|^\s+\d+\.\s+)(.+)", block, re.MULTILINE)
    if not ac_lines:
        return False

    # Read all test content
    test_content = ""
    for tf in test_files:
        full = Path(wt_path) / tf
        if full.exists():
            try:
                test_content += full.read_text(encoding="utf-8", errors="replace") + "\n"
            except OSError:
                continue

    test_content_lower = test_content.lower()

    # Also extract test function names for matching
    test_func_names = " ".join(
        re.findall(r"(?:def |function |it\(|test\()[\s'\"]*([\w_]+)", test_content_lower)
    )

    uncovered = []
    for ac in ac_lines:
        # Extract keywords (5+ chars, skip common stop words)
        stop_words = {"given", "which", "should", "their", "there", "these", "those", "about", "after", "before", "between"}
        keywords = [
            w.lower() for w in re.findall(r"\b\w{5,}\b", ac)
            if w.lower() not in stop_words
        ]
        if not keywords:
            continue

        # Check if any keyword appears in test content or test function names
        found_in_content = any(kw in test_content_lower for kw in keywords[:7])
        found_in_funcs = any(kw in test_func_names for kw in keywords[:7])

        if not found_in_content and not found_in_funcs:
            uncovered.append(ac.strip()[:80])

    if uncovered:
        print(f"FAIL: {len(uncovered)} AC item(s) have no corresponding test coverage:")
        for ac in uncovered[:5]:
            print(f"  - {ac}")
        print("  Each AC must map to at least one test case.")
        return True

    return False


def verify_implement_red(issue_id: str, **_) -> bool:
    """TDD Red phase: tests exist with real assertions but FAIL (no implementation yet).

    This verifier has inverted logic — pytest returning non-zero is the expected outcome.
    If tests pass, it means they were written after implementation (not TDD).
    """
    wt_path = _find_worktree_path(issue_id)
    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    wt = Path(wt_path)

    # First, verify test files exist and have real assertions
    base = _default_branch()
    diff_committed = _run(["git", "diff", "--name-only", base], cwd=wt_path)
    diff_staged = _run(["git", "diff", "--name-only", "--cached"], cwd=wt_path)
    diff_unstaged = _run(["git", "diff", "--name-only"], cwd=wt_path)
    untracked = _run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=wt_path
    )

    all_files: set[str] = set()
    for r in (diff_committed, diff_staged, diff_unstaged, untracked):
        if r.returncode == 0 and r.stdout.strip():
            all_files.update(r.stdout.strip().splitlines())

    test_pattern = re.compile(
        r"(?:^|/)(?:test_[^/]+\.py|[^/]+_test\.py|[^/]+\.(?:spec|test)\.(?:ts|tsx|js|jsx))$"
    )
    test_dir_pattern = re.compile(r"(?:^|/)(?:tests?|__tests__)/")

    test_files = [f for f in all_files if test_pattern.search(f)]
    test_dir_files = [f for f in all_files if test_dir_pattern.search(f) and f.endswith((".py", ".ts", ".tsx", ".js", ".jsx"))]
    all_test_files = sorted(set(test_files + test_dir_files))

    if not all_test_files:
        print("FAIL: no test files found — write tests before RED phase")
        return False

    # Check tests have real assertions
    shallow = [f for f in all_test_files if not _has_real_tests(f, wt_path)]
    if shallow:
        print(f"FAIL: test files have no real assertions: {', '.join(shallow)}")
        return False

    # Now run tests — they SHOULD FAIL (exit code != 0)
    has_python = (
        (wt / "pyproject.toml").exists()
        or (wt / "setup.py").exists()
        or (wt / "tests").is_dir()
    )

    if has_python:
        result = _run(["python3", "-m", "pytest", "-q", "--tb=short"], cwd=wt_path, timeout=60)
        if result.returncode == 0:
            print("FAIL: RED phase — tests passed but should fail before implementation.")
            print("  TDD requires: write failing tests first, then implement to make them pass.")
            return False
        print(f"PASS: RED phase — tests fail as expected (exit {result.returncode})")
        return True

    # JS/TS fallback
    has_js = (wt / "package.json").exists()
    if has_js:
        result = _run(["npm", "test", "--", "--passWithNoTests"], cwd=wt_path, timeout=60)
        if result.returncode == 0:
            print("FAIL: RED phase — tests passed but should fail before implementation.")
            return False
        print(f"PASS: RED phase — tests fail as expected (exit {result.returncode})")
        return True

    # Fallback: try pytest
    result = _run(["python3", "-m", "pytest", "-q", "--tb=short"], cwd=wt_path, timeout=60)
    if result.returncode == 0:
        print("FAIL: RED phase — tests passed but should fail before implementation.")
        return False

    print(f"PASS: RED phase — tests fail as expected (exit {result.returncode})")
    return True


def verify_implement_tests_written(issue_id: str, **_) -> bool:
    """Verify that test files were actually created or modified for this issue."""
    wt_path = _find_worktree_path(issue_id)
    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    base = _default_branch()

    # Committed changes vs default branch
    diff_committed = _run(["git", "diff", "--name-only", base], cwd=wt_path)
    # Staged but not yet committed
    diff_staged = _run(["git", "diff", "--name-only", "--cached"], cwd=wt_path)
    # Unstaged modifications
    diff_unstaged = _run(["git", "diff", "--name-only"], cwd=wt_path)
    # Untracked files
    untracked = _run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=wt_path
    )

    all_files: set[str] = set()
    for r in (diff_committed, diff_staged, diff_unstaged, untracked):
        if r.returncode == 0 and r.stdout.strip():
            all_files.update(r.stdout.strip().splitlines())

    # Match test files: test_*.py, *_test.py, *.spec.ts, *.test.ts, etc.
    test_pattern = re.compile(
        r"(?:^|/)(?:test_[^/]+\.py|[^/]+_test\.py|[^/]+\.(?:spec|test)\.(?:ts|tsx|js|jsx))$"
    )
    test_files = [f for f in all_files if test_pattern.search(f)]

    # Also match files inside tests/ or __tests__/ directories
    test_dir_pattern = re.compile(r"(?:^|/)(?:tests?|__tests__)/")
    test_dir_files = [f for f in all_files if test_dir_pattern.search(f) and f.endswith((".py", ".ts", ".tsx", ".js", ".jsx"))]

    all_test_files = sorted(set(test_files + test_dir_files))

    if not all_test_files:
        print("FAIL: no test files were created or modified.")
        print("  Every new behavior must have at least one test.")
        print("  Expected: test_*.py, *_test.py, *.spec.ts, or files in tests/ directory")
        return False

    # Verify test files contain real assertions (not hollow tests)
    shallow_files = [f for f in all_test_files if not _has_real_tests(f, wt_path)]
    if shallow_files:
        print(f"FAIL: test files exist but contain no real assertions: {', '.join(shallow_files)}")
        print("  Each test file must contain at least one test function with assertions.")
        print("  Python: def test_*() with assert/assertEqual/raises/mock")
        print("  JS/TS: it()/test() with expect/toBe/toEqual/toThrow")
        return False

    # Check test type coverage based on issue characteristics
    e2e_pattern = re.compile(r"(?:^|/)(?:e2e|tests/e2e)/")
    integration_pattern = re.compile(r"(?:^|/)(?:integration|tests/integration)/")
    e2e_files = [f for f in all_test_files if e2e_pattern.search(f)]
    integration_files = [f for f in all_test_files if integration_pattern.search(f)]

    # UI issues should have e2e tests
    if _is_ui_issue(issue_id) and not e2e_files:
        print(f"FAIL: {issue_id} is a UI issue but no e2e test files found")
        print("  UI issues must include at least one e2e test.")
        print("  Web: tests/e2e/*.spec.ts | Mobile: e2e/*.yaml or e2e/*.test.ts")
        return False

    # Issues touching high-risk flows should have integration tests
    if _test_plan_has_high_risk(_repo_root()) and not integration_files:
        print(f"WARN: High-risk flows in test_plan.md but no integration tests found")
        print("  Consider adding tests in tests/integration/ with @pytest.mark.integration")
        # Warning only — not all issues touch high-risk flows

    # AC coverage check — now blocking
    ac_fail = _check_ac_test_coverage(issue_id, wt_path, all_test_files)
    if ac_fail:
        return False

    print(f"PASS: {len(all_test_files)} test file(s) with real assertions: {', '.join(all_test_files)}")
    if e2e_files:
        print(f"  e2e: {', '.join(e2e_files)}")
    if integration_files:
        print(f"  integration: {', '.join(integration_files)}")
    return True


_MIN_COVERAGE = 60  # Minimum line coverage percentage


def _run_python_tests_with_coverage(cwd: str | None) -> bool:
    """Run pytest with coverage and enforce minimum threshold."""
    result = _run(
        [
            "python3", "-m", "pytest", "-q", "--tb=short",
            "--cov=.", "--cov-report=term-missing",
            f"--cov-fail-under={_MIN_COVERAGE}",
        ],
        cwd=cwd,
        timeout=60,
    )

    if result.returncode != 0:
        stderr_lower = (result.stderr or "").lower()
        # pytest-cov not installed — fall back to plain pytest
        if "no module named" in stderr_lower or "unrecognized arguments: --cov" in stderr_lower:
            print(f"WARN: pytest-cov not available, running without coverage enforcement")
            result = _run(["python3", "-m", "pytest", "-q", "--tb=short"], cwd=cwd, timeout=60)
            if result.returncode != 0:
                print(f"FAIL: pytest failed (exit {result.returncode})")
                if result.stdout:
                    print(result.stdout[-500:])
                return False
            return True

        print(f"FAIL: pytest failed (exit {result.returncode})")
        if result.stdout:
            print(result.stdout[-500:])
        return False

    return True


def _run_js_tests_in_worktree(cwd: str | None) -> bool:
    """Run JS/TS test suite if package.json has a test script."""
    wt = Path(cwd) if cwd else Path.cwd()
    pkg_json = wt / "package.json"
    if not pkg_json.exists():
        return True

    try:
        pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
        if "test" not in pkg.get("scripts", {}):
            return True  # No test script defined
    except (OSError, json.JSONDecodeError):
        return True

    result = _run(["npm", "test", "--", "--passWithNoTests"], cwd=cwd, timeout=60)
    if result.returncode != 0:
        print(f"FAIL: npm test failed (exit {result.returncode})")
        if result.stdout:
            print(result.stdout[-500:])
        return False
    return True


def _test_plan_has_high_risk(root: Path) -> bool:
    """Check if test_plan.md Risk Matrix contains High or Critical risk flows."""
    test_plan = root / "docs" / "test_plan.md"
    if not test_plan.exists():
        return False
    content = test_plan.read_text(encoding="utf-8")
    # Look for High or Critical in Risk column of the Risk Matrix table
    return bool(re.search(
        r"^\|[^|]+\|[^|]+\|[^|]+\|\s*(?:High|Critical)\s*\|",
        content,
        re.MULTILINE | re.IGNORECASE,
    ))


def _run_verify_gates(project_path: str, blocking: bool = False) -> bool:
    """Run verify_gates.py and report results.

    If blocking=True, gate failures cause checkpoint failure.
    If blocking=False, gate failures are warnings only.
    """
    try:
        import verify_gates
    except ImportError:
        print("WARN: verify_gates.py not available — gate checks skipped")
        return not blocking  # If blocking=True and module missing, FAIL

    pp = Path(project_path)
    try:
        results = verify_gates.run_applicable_gates(pp)
    except Exception as exc:
        print(f"WARN: verify_gates raised an error: {exc}")
        return not blocking  # If blocking=True and gates crash, FAIL

    if not results:
        return True

    has_blocking_failure = False
    for r in results:
        icon = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "warn": "WARN"}[r.status]
        blocking_tag = " [blocking]" if r.blocking else ""
        print(f"  GATE {icon}: {r.gate}{blocking_tag} ({r.duration_s:.1f}s)")
        if r.status == "fail":
            if r.blocking:
                has_blocking_failure = True
            # Show last few lines of output for failures
            lines = r.output.strip().splitlines()
            for line in lines[-3:]:
                print(f"        {line}")

    if has_blocking_failure:
        if blocking:
            print("FAIL: one or more blocking gates failed")
            return False
        else:
            print("WARN: gate failures detected (non-blocking during implement phase)")

    return True


def _ensure_deps_installed(wt: Path, cwd: str | None) -> bool:
    """Install dependencies in worktree if not already present.

    Returns True if deps are ready, False if installation failed.
    """
    ok = True

    # JS/TS: install node_modules if package.json exists but node_modules doesn't
    if (wt / "package.json").exists() and not (wt / "node_modules").is_dir():
        print("  Installing npm dependencies in worktree...")
        result = _run(["npm", "install", "--legacy-peer-deps"], cwd=cwd, timeout=120)
        if result.returncode != 0:
            print(f"  WARN: npm install failed (exit {result.returncode})")
            ok = False

    # Python: install if pyproject.toml exists
    if (wt / "pyproject.toml").exists():
        result = _run(["uv", "sync"], cwd=cwd, timeout=60)
        if result.returncode != 0:
            result = _run(["pip", "install", "-e", "."], cwd=cwd, timeout=60)
            if result.returncode != 0:
                print(f"  WARN: dependency install failed (uv sync and pip install both failed)")
                ok = False

    return ok


def verify_implement_test(issue_id: str, **_) -> bool:
    """Tests pass AND meet minimum coverage threshold."""
    wt_path = _find_worktree_path(issue_id)
    cwd = wt_path if wt_path else None
    wt = Path(cwd) if cwd else Path.cwd()

    # Ensure dependencies are installed before running tests
    _ensure_deps_installed(wt, cwd)

    has_python = (
        (wt / "pyproject.toml").exists()
        or (wt / "setup.py").exists()
        or any(wt.glob("*.py"))
        or (wt / "tests").is_dir()
    )
    has_js = (wt / "package.json").exists()

    ok = True

    if has_python:
        ok = ok and _run_python_tests_with_coverage(cwd)

    if has_js:
        ok = ok and _run_js_tests_in_worktree(cwd)

    if not has_python and not has_js:
        # Fallback: try pytest anyway
        result = _run(["python3", "-m", "pytest", "-q", "--tb=short"], cwd=cwd, timeout=60)
        if result.returncode != 0:
            print(f"FAIL: pytest failed (exit {result.returncode})")
            if result.stdout:
                print(result.stdout[-500:])
            return False

    if ok:
        print("PASS: tests passed")

    # Run verify_gates — blocking if test_plan.md has High/Critical risk flows
    if ok:
        has_high_risk = _test_plan_has_high_risk(_repo_root())
        if has_high_risk:
            print("  High-risk flows detected in test_plan.md — gates are BLOCKING")
            ok = ok and _run_verify_gates(str(wt), blocking=True)
        else:
            _run_verify_gates(str(wt), blocking=False)

    return ok


def verify_implement_push(issue_id: str, **_) -> bool:
    """Remote branch exists (fetches latest refs first)."""
    wt_path = _find_worktree_path(issue_id)
    cwd = wt_path if wt_path else None

    # Fetch to ensure local remote-tracking refs are up to date
    _run(["git", "fetch", "--prune"], cwd=cwd)

    result = _run(["git", "branch", "-r"], cwd=cwd)
    if result.returncode != 0:
        print("FAIL: git branch -r failed")
        return False

    slug = issue_id.lower()
    branch_pattern = re.compile(
        rf"{re.escape(slug)}{_SLUG_BOUNDARY}", re.IGNORECASE
    )
    if not any(branch_pattern.search(line) for line in result.stdout.splitlines()):
        print(f"FAIL: no remote branch found matching '{slug}'")
        return False

    print(f"PASS: remote branch exists for {issue_id}")
    return True


def verify_implement_pr(issue_id: str, **_) -> bool:
    """PR exists and body contains a GitHub closing keyword (`Closes/Fixes/Resolves #N`)."""
    pr_num = _extract_pr_number(issue_id)
    if pr_num is None:
        return False

    result = _run_with_retry(["gh", "pr", "view", pr_num, "--json", "body", "-q", ".body"])
    if result.returncode != 0:
        print(f"FAIL: gh pr view {pr_num} failed: {result.stderr.strip()}")
        return False

    # GitHub recognizes: close(s/d), fix(es/ed), resolve(s/d) + #N
    if not re.search(r"(?:Close[sd]?|Fix(?:e[sd])?|Resolve[sd]?)\s+#\d+", result.stdout, re.IGNORECASE):
        print(f"FAIL: PR #{pr_num} body does not contain a closing keyword (Closes/Fixes/Resolves #N)")
        return False

    print(f"PASS: PR #{pr_num} exists with closing keyword reference")
    return True


def verify_implement_registry(issue_id: str, **_) -> bool:
    """Status=done and PR field exists in issues.md."""
    block = _find_issue_block(issue_id)
    if block is None:
        return False

    status = _extract_field(block, "Status")
    pr_field = _extract_field(block, "PR")

    if status != "done":
        print(f"FAIL: {issue_id} Status is '{status}', expected 'done'")
        return False
    if not pr_field:
        print(f"FAIL: {issue_id} has no PR field")
        return False

    print(f"PASS: {issue_id} registry updated (Status=done, PR present)")
    return True


# ── Review skill verifiers ───────────────────────────────────────────


def verify_review_checkout(issue_id: str, **_) -> bool:
    """Worktree exists for the PR branch."""
    return verify_implement_worktree(issue_id)


def verify_review_review(issue_id: str, **_) -> bool:
    """review_notes.md has Code Review and Security Findings as markdown headers."""
    wt_path = _find_worktree_path(issue_id)
    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    notes = Path(wt_path) / "docs" / "review_notes.md"
    if not notes.exists():
        print("FAIL: docs/review_notes.md not found in worktree")
        return False

    content = notes.read_text(encoding="utf-8")
    # Check for markdown headers (# or ##, etc.) containing the section name
    missing = []
    if not re.search(r"^#{1,6}\s+.*Code Review", content, re.MULTILINE):
        missing.append("Code Review")
    if not re.search(r"^#{1,6}\s+.*Security Findings", content, re.MULTILINE):
        missing.append("Security Findings")

    if missing:
        print(f"FAIL: review_notes.md missing header sections: {', '.join(missing)}")
        return False

    print("PASS: review_notes.md has required sections")
    return True


_UI_KEYWORDS = re.compile(
    r"\b(?:UI|screen|component|prototype|frontend|widget|layout)\b", re.IGNORECASE
)


def _is_ui_issue(issue_id: str) -> bool:
    """Determine if an issue involves UI/frontend work.

    Priority:
      1. Explicit ``UI: true`` / ``UI: false`` field (set by planner at kickoff)
      2. Keyword fallback — Track field and title scanning (backward-compat)
    """
    block = _find_issue_block(issue_id)
    if block is None:
        return False

    # 1) Explicit UI field — authoritative when present
    ui_field = _extract_field(block, "UI")
    if ui_field:
        return ui_field.lower() == "true"

    # 2) Fallback: keyword matching on Track and title
    track = _extract_field(block, "Track")
    if track and _UI_KEYWORDS.search(track):
        return True

    # Check title line (### ISSUE-NNN: <title>)
    title_match = re.match(r"^### [^:]+:\s*(.+)", block)
    if title_match and _UI_KEYWORDS.search(title_match.group(1)):
        return True

    return False


def verify_review_ui_review(issue_id: str, **_) -> bool:
    """ui_review_notes.md exists with State Coverage and Copy Compliance sections.

    Automatically passes for non-UI issues (no ui_review_notes.md expected).
    """
    if not _is_ui_issue(issue_id):
        print(f"PASS: {issue_id} is not a UI issue — ui-review checkpoint skipped")
        return True

    wt_path = _find_worktree_path(issue_id)
    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    notes = Path(wt_path) / "docs" / "ui_review_notes.md"
    if not notes.exists():
        print("FAIL: docs/ui_review_notes.md not found in worktree")
        return False

    content = notes.read_text(encoding="utf-8")
    missing = []
    if not re.search(r"^#{1,6}\s+.*State Coverage", content, re.MULTILINE):
        missing.append("State Coverage")
    if not re.search(r"^#{1,6}\s+.*Copy Compliance", content, re.MULTILINE):
        missing.append("Copy Compliance")

    if missing:
        print(f"FAIL: ui_review_notes.md missing header sections: {', '.join(missing)}")
        return False

    print("PASS: ui_review_notes.md has required sections")
    return True


def verify_review_test_quality(issue_id: str, **_) -> bool:
    """Verify test quality: no hollow tests and coverage threshold met."""
    wt_path = _find_worktree_path(issue_id)
    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    wt = Path(wt_path)

    # Find all test files in worktree
    test_files: list[str] = []
    tests_dir = wt / "tests"
    if tests_dir.is_dir():
        for f in tests_dir.rglob("*.py"):
            rel = str(f.relative_to(wt))
            if f.name.startswith("test_") or f.name.endswith("_test.py"):
                test_files.append(rel)

    # Also check for JS/TS test files
    for f in wt.rglob("*.test.*"):
        if "node_modules" not in str(f):
            test_files.append(str(f.relative_to(wt)))
    for f in wt.rglob("*.spec.*"):
        if "node_modules" not in str(f):
            test_files.append(str(f.relative_to(wt)))

    test_files = sorted(set(test_files))

    if not test_files:
        # No test files at all — this is a warning but not necessarily a failure
        # (some repos may not have tests yet)
        print("WARN: no test files found in worktree")
        print("PASS: test-quality check (no test files to validate)")
        return True

    # Check for hollow tests
    hollow = [f for f in test_files if not _has_real_tests(f, wt_path)]
    if hollow:
        print(f"FAIL: hollow test files found (no real assertions):")
        for f in hollow[:5]:
            print(f"  - {f}")
        return False

    print(f"PASS: {len(test_files)} test file(s) have real assertions")
    return True


def verify_review_visual_diff(issue_id: str, **_) -> bool:
    """Visual diff: compare Figma renders or prototype against implementation.

    FAILS when Figma data exists but Playwright can't be installed or
    no implementation HTML is found (required checks cannot be skipped).
    Only auto-passes when there is genuinely no Figma data to compare against.
    """
    wt_path = _find_worktree_path(issue_id)
    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    result = _run(
        ["python3", str(Path(__file__).resolve().parent / "verify_visual_diff.py"),
         "--project-path", wt_path, "--threshold", "1"],
        timeout=120,
    )

    if result.returncode == 0:
        if result.stdout:
            for line in result.stdout.strip().splitlines():
                print(f"  {line}")
        return True

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(f"  {line}")
    return False


def verify_review_layout(issue_id: str, **_) -> bool:
    """Verify implementation layout matches Figma spatial arrangement.

    Checks container direction (row/column), sibling ordering, and
    spatial relationships. Auto-passes when no Figma data exists.
    """
    wt_path = _find_worktree_path(issue_id)
    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    wt = Path(wt_path)
    design_data = wt / "figma-export" / "design_data.json"
    if not design_data.exists():
        root = _repo_root()
        design_data = root / "figma-export" / "design_data.json"

    if not design_data.exists():
        figma_urls = _find_figma_urls(issue_id)
        if figma_urls:
            print(f"FAIL: {issue_id} has Figma URLs but design_data.json not found")
            return False
        print(f"PASS: {issue_id} has no Figma data — layout check skipped")
        return True

    result = _run(
        ["python3", str(Path(__file__).resolve().parent / "verify_layout.py"),
         "--project-path", wt_path],
        timeout=30,
    )

    if result.returncode == 0:
        if result.stdout:
            for line in result.stdout.strip().splitlines():
                print(f"  {line}")
        return True

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(f"  {line}")
    print(f"FAIL: {issue_id} — layout doesn't match Figma spatial arrangement")
    return False


def verify_review_structural_match(issue_id: str, **_) -> bool:
    """Verify Figma element structure is present in implementation.

    Checks that all visible Figma elements (buttons, inputs, icons, text)
    exist in the implementation with correct content.
    Auto-passes when no design_data.json exists.
    """
    wt_path = _find_worktree_path(issue_id)
    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    wt = Path(wt_path)
    design_data = wt / "figma-export" / "design_data.json"
    if not design_data.exists():
        root = _repo_root()
        design_data = root / "figma-export" / "design_data.json"

    if not design_data.exists():
        figma_urls = _find_figma_urls(issue_id)
        if figma_urls:
            print(f"FAIL: {issue_id} has Figma URLs but design_data.json not found")
            return False
        print(f"PASS: {issue_id} has no Figma data — structural match skipped")
        return True

    result = _run(
        ["python3", str(Path(__file__).resolve().parent / "verify_structural_match.py"),
         "--project-path", wt_path],
        timeout=30,
    )

    if result.returncode == 0:
        if result.stdout:
            for line in result.stdout.strip().splitlines():
                print(f"  {line}")
        return True

    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(f"  {line}")
    print(f"FAIL: {issue_id} — implementation is missing Figma elements")
    return False


def verify_review_figma_compliance(issue_id: str, **_) -> bool:
    """Verify implementation matches Figma design tokens.

    Auto-passes when no figma-export/design_data.json exists (non-Figma issues).
    Fails if hardcoded colors, fonts, or spacings deviate from Figma tokens.
    """
    wt_path = _find_worktree_path(issue_id)
    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    wt = Path(wt_path)
    design_data = wt / "figma-export" / "design_data.json"

    # Also check main repo root for design data
    if not design_data.exists():
        root = _repo_root()
        design_data = root / "figma-export" / "design_data.json"

    if not design_data.exists():
        # Check if the issue has Figma URLs — if so, design_data.json SHOULD exist
        figma_urls = _find_figma_urls(issue_id)
        if figma_urls:
            print(f"FAIL: {issue_id} has Figma URLs but figma-export/design_data.json not found")
            print(f"  Run figma_fetch.py first: python3 scripts/figma_fetch.py {' '.join(figma_urls)}")
            return False
        print(f"PASS: {issue_id} has no Figma data — compliance check skipped")
        return True

    # Run the compliance script
    result = _run(
        ["python3", str(Path(__file__).resolve().parent / "verify_figma_compliance.py"),
         "--project-path", wt_path],
        timeout=30,
    )

    if result.returncode == 0:
        print(f"PASS: {issue_id} — implementation matches Figma design tokens")
        return True

    # Print compliance output for the agent to see
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(f"  {line}")

    print(f"FAIL: {issue_id} — implementation deviates from Figma design")
    print(f"  Fix the violations above, then re-run this checkpoint.")
    return False


def verify_review_test(issue_id: str, **_) -> bool:
    """pytest exits 0 (inside worktree)."""
    return verify_implement_test(issue_id)


def verify_review_push(issue_id: str, **_) -> bool:
    """Review commits pushed to remote."""
    return verify_implement_push(issue_id)


# ── Ship skill verifiers ─────────────────────────────────────────────


def verify_ship_checks(issue_id: str, **_) -> bool:
    """`gh pr checks` passes with at least one check present.

    Waits up to 60 seconds for CI checks to appear (race condition:
    CI may not have started yet when this runs immediately after PR creation).
    """
    pr_num = _extract_pr_number(issue_id)
    if pr_num is None:
        return False

    # Wait for CI checks to appear (up to 60 seconds)
    max_wait = 60
    waited = 0
    lines: list[str] = []
    result = _run_with_retry(["gh", "pr", "checks", pr_num])
    while waited < max_wait:
        result = _run_with_retry(["gh", "pr", "checks", pr_num])
        if result.returncode == 0:
            lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
            if lines:
                break
        if waited == 0:
            print(f"  Waiting for CI checks on PR #{pr_num}...", flush=True)
        time.sleep(5)
        waited += 5

    if not lines:
        print(f"FAIL: PR #{pr_num} has no CI checks after {max_wait}s")
        return False

    if result.returncode != 0:
        print(f"FAIL: gh pr checks failed for PR #{pr_num}")
        if result.stdout:
            print(result.stdout[-300:])
        return False

    print("PASS: PR checks are green")
    return True


def verify_ship_merge(issue_id: str, **_) -> bool:
    """PR is in merged state."""
    pr_num = _extract_pr_number(issue_id)
    if pr_num is None:
        return False

    result = _run_with_retry(["gh", "pr", "view", pr_num, "--json", "state", "-q", ".state"])
    if result.returncode != 0:
        print("FAIL: gh pr view failed")
        return False

    state = result.stdout.strip()
    if state != "MERGED":
        print(f"FAIL: PR #{pr_num} state is '{state}', expected 'MERGED'")
        return False

    print(f"PASS: PR #{pr_num} is merged")
    return True


def verify_ship_smoke(issue_id: str, **_) -> bool:
    """Post-merge smoke test: run tests on main branch to verify no regression."""
    # Verify we're on the default branch
    result = _run(["git", "branch", "--show-current"])
    if result.returncode != 0:
        print("FAIL: cannot determine current branch")
        return False

    current = result.stdout.strip()
    default = _default_branch()
    if current != default:
        print(f"FAIL: expected to be on '{default}' but on '{current}'")
        print(f"  Run: git checkout {default} && git pull")
        return False

    # Run tests on main
    root = _repo_root()
    has_python = (
        (root / "pyproject.toml").exists()
        or (root / "setup.py").exists()
        or (root / "tests").is_dir()
    )
    has_js = (root / "package.json").exists()

    ok = True

    if has_python:
        result = _run(["python3", "-m", "pytest", "-q", "--tb=short"], cwd=str(root), timeout=120)
        if result.returncode != 0:
            print("FAIL: post-merge smoke test failed on main")
            if result.stdout:
                print(result.stdout[-500:])
            print("  Consider reverting: git revert -m 1 <merge_commit>")
            ok = False

    if has_js:
        result = _run(["npm", "test", "--", "--passWithNoTests"], cwd=str(root), timeout=120)
        if result.returncode != 0:
            print("FAIL: npm test failed on main")
            if result.stdout:
                print(result.stdout[-500:])
            ok = False

    # Run verify_gates as blocking (gate failures block ship)
    if ok:
        ok = ok and _run_verify_gates(str(root), blocking=True)

    if ok:
        print("PASS: post-merge smoke test passed on main")
    return ok


def verify_ship_cleanup(issue_id: str, **_) -> bool:
    """Worktree has been removed."""
    result = _run(["git", "worktree", "list", "--porcelain"])
    if result.returncode != 0:
        print("FAIL: git worktree list failed")
        return False

    slug = issue_id.lower()
    wt_pattern = re.compile(
        rf"{re.escape(slug)}{_SLUG_BOUNDARY}", re.IGNORECASE
    )
    for line in result.stdout.splitlines():
        if line.startswith("worktree ") and wt_pattern.search(line):
            print(f"FAIL: worktree for {issue_id} still exists")
            return False

    print(f"PASS: worktree cleaned up for {issue_id}")
    return True


# ── Generic verifiers (reused by debug/refactor/devops/migrate) ──────


def verify_generic_worktree(issue_id: str, **_) -> bool:
    """Worktree exists for the given slug."""
    return verify_implement_worktree(issue_id)


def verify_generic_test(issue_id: str, **_) -> bool:
    """pytest exits 0 (inside worktree)."""
    return verify_implement_test(issue_id)


def verify_generic_push(issue_id: str, **_) -> bool:
    """Remote branch exists for the given slug."""
    return verify_implement_push(issue_id)


def verify_generic_validate(issue_id: str, **_) -> bool:
    """Worktree has file changes (committed or uncommitted)."""
    wt_path = _find_worktree_path(issue_id)
    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    # Check for any changed files
    diff_staged = _run(["git", "diff", "--name-only", "--cached"], cwd=wt_path)
    diff_unstaged = _run(["git", "diff", "--name-only"], cwd=wt_path)
    untracked = _run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=wt_path
    )

    all_files: set[str] = set()
    for r in (diff_staged, diff_unstaged, untracked):
        if r.returncode == 0 and r.stdout.strip():
            all_files.update(r.stdout.strip().splitlines())

    if not all_files:
        print("FAIL: no file changes found in worktree")
        return False

    print(f"PASS: {len(all_files)} file(s) changed in worktree")
    return True


# ── uiux / mobile-uiux verifiers ─────────────────────────────────────


def verify_uiux_context(issue_id: str) -> bool:
    """Verify Phase 1 context: ux_spec.md exists."""
    root = _repo_root()
    ux_spec = root / "docs" / "ux_spec.md"
    if not ux_spec.exists():
        print(f"FAIL: docs/ux_spec.md not found — run /kickoff first")
        return False
    print("OK: ux_spec.md exists")
    return True


def verify_uiux_philosophy(issue_id: str) -> bool:
    """Verify Phase 2: design_philosophy.md exists with Decision Matrix."""
    root = _repo_root()
    phil = root / "docs" / "design_philosophy.md"
    if not phil.exists():
        print(f"FAIL: docs/design_philosophy.md not found")
        return False
    content = phil.read_text(encoding="utf-8")
    if "Decision Matrix" not in content:
        print("FAIL: design_philosophy.md missing Decision Matrix section")
        return False
    print("OK: design_philosophy.md exists with Decision Matrix")
    return True


def verify_uiux_system(issue_id: str) -> bool:
    """Verify Phase 4 (web): all design docs exist."""
    root = _repo_root()
    required = ["design_system.md", "wireframes.md", "interactions.md", "copy_guide.md"]
    ok = True
    for name in required:
        path = root / "docs" / name
        if not path.exists():
            print(f"FAIL: docs/{name} not found")
            ok = False
    if ok:
        print("OK: all web design docs exist")
    return ok


def verify_mobile_uiux_system(issue_id: str) -> bool:
    """Verify Phase 4 (mobile): all mobile design docs exist."""
    root = _repo_root()
    required = ["design_system_mobile.md", "wireframes_mobile.md", "interactions_mobile.md", "copy_guide.md"]
    ok = True
    for name in required:
        path = root / "docs" / name
        if not path.exists():
            print(f"FAIL: docs/{name} not found")
            ok = False
    if ok:
        print("OK: all mobile design docs exist")
    return ok


# ── Registry ─────────────────────────────────────────────────────────

VERIFIERS = {
    ("implement", "test-plan"): verify_implement_test_plan,
    ("implement", "figma"): verify_implement_figma,
    ("implement", "issue"): verify_implement_issue,
    ("implement", "worktree"): verify_implement_worktree,
    ("implement", "code"): verify_implement_code,
    ("implement", "tests-written"): verify_implement_tests_written,
    ("implement", "red"): verify_implement_red,
    ("implement", "test"): verify_implement_test,
    ("implement", "push"): verify_implement_push,
    ("implement", "pr"): verify_implement_pr,
    ("implement", "registry"): verify_implement_registry,
    ("review", "checkout"): verify_review_checkout,
    ("review", "review"): verify_review_review,
    ("review", "ui-review"): verify_review_ui_review,
    ("review", "figma-compliance"): verify_review_figma_compliance,
    ("review", "structural-match"): verify_review_structural_match,
    ("review", "layout"): verify_review_layout,
    ("review", "test-quality"): verify_review_test_quality,
    ("review", "test"): verify_review_test,
    ("review", "push"): verify_review_push,
    ("ship", "checks"): verify_ship_checks,
    ("ship", "merge"): verify_ship_merge,
    ("ship", "smoke"): verify_ship_smoke,
    ("ship", "cleanup"): verify_ship_cleanup,
    ("diagnose", "worktree"): verify_generic_worktree,
    ("diagnose", "test"): verify_generic_test,
    ("diagnose", "push"): verify_generic_push,
    ("refactor", "worktree"): verify_generic_worktree,
    ("refactor", "test"): verify_generic_test,
    ("refactor", "push"): verify_generic_push,
    ("devops", "worktree"): verify_generic_worktree,
    ("devops", "validate"): verify_generic_validate,
    ("devops", "push"): verify_generic_push,
    ("migrate", "worktree"): verify_generic_worktree,
    ("migrate", "test"): verify_generic_test,
    ("migrate", "push"): verify_generic_push,
    ("testgen", "worktree"): verify_generic_worktree,
    ("testgen", "test"): verify_generic_test,
    ("testgen", "push"): verify_generic_push,
    ("uiux", "context"): verify_uiux_context,
    ("uiux", "philosophy"): verify_uiux_philosophy,
    ("uiux", "system"): verify_uiux_system,
    ("mobile-uiux", "context"): verify_uiux_context,
    ("mobile-uiux", "philosophy"): verify_uiux_philosophy,
    ("mobile-uiux", "system"): verify_mobile_uiux_system,
}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Verify skill phase checkpoint")
    parser.add_argument("--skill", required=True, choices=["implement", "review", "ship", "diagnose", "refactor", "devops", "migrate", "testgen", "uiux", "mobile-uiux"])
    parser.add_argument("--phase", required=True)
    parser.add_argument("--issue", required=True, help="Issue ID (e.g. ISSUE-001)")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    key = (args.skill, args.phase)
    if key not in VERIFIERS:
        print(f"ERROR: unknown phase '{args.phase}' for skill '{args.skill}'", file=sys.stderr)
        print(f"Valid phases: {[p for s, p in VERIFIERS if s == args.skill]}", file=sys.stderr)
        return 2

    ok = VERIFIERS[key](args.issue)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
