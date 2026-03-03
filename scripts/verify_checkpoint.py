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
import re
import subprocess
import sys
from pathlib import Path


def _extract_field(text: str, field_name: str) -> str:
    """Extract a metadata field value from issue text (reused pattern from validate_issues.py)."""
    match = re.search(rf"^- {field_name}:[ \t]*(.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command and return the result (no exception on failure)."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    except FileNotFoundError:
        # Command binary not found (e.g. gh or git not installed)
        prog = cmd[0] if cmd else "<unknown>"
        mock = subprocess.CompletedProcess(cmd, 127)
        mock.stdout = ""
        mock.stderr = f"{prog}: command not found"
        return mock


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


# ── Implement skill verifiers ────────────────────────────────────────


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

    result = _run(["gh", "issue", "view", num_match.group(1)])
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


def verify_implement_test(issue_id: str, **_) -> bool:
    """pytest exits 0 (runs inside the issue's worktree if one exists)."""
    wt_path = _find_worktree_path(issue_id)
    cwd = wt_path if wt_path else None

    result = _run(["python3", "-m", "pytest", "-q", "--tb=short"], cwd=cwd)
    if result.returncode != 0:
        print(f"FAIL: pytest failed (exit {result.returncode})")
        if result.stdout:
            print(result.stdout[-500:])
        return False

    print("PASS: tests passed")
    return True


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

    result = _run(["gh", "pr", "view", pr_num, "--json", "body", "-q", ".body"])
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


def verify_review_test(issue_id: str, **_) -> bool:
    """pytest exits 0 (inside worktree)."""
    return verify_implement_test(issue_id)


def verify_review_push(issue_id: str, **_) -> bool:
    """Review commits pushed to remote."""
    return verify_implement_push(issue_id)


# ── Ship skill verifiers ─────────────────────────────────────────────


def verify_ship_checks(issue_id: str, **_) -> bool:
    """`gh pr checks` passes with at least one check present."""
    pr_num = _extract_pr_number(issue_id)
    if pr_num is None:
        return False

    result = _run(["gh", "pr", "checks", pr_num])
    if result.returncode != 0:
        print(f"FAIL: gh pr checks failed for PR #{pr_num}")
        return False

    # Ensure there is at least one check (not just an empty success)
    lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
    if not lines:
        print(f"FAIL: PR #{pr_num} has no CI checks configured")
        return False

    print("PASS: PR checks are green")
    return True


def verify_ship_merge(issue_id: str, **_) -> bool:
    """PR is in merged state."""
    pr_num = _extract_pr_number(issue_id)
    if pr_num is None:
        return False

    result = _run(["gh", "pr", "view", pr_num, "--json", "state", "-q", ".state"])
    if result.returncode != 0:
        print("FAIL: gh pr view failed")
        return False

    state = result.stdout.strip()
    if state != "MERGED":
        print(f"FAIL: PR #{pr_num} state is '{state}', expected 'MERGED'")
        return False

    print(f"PASS: PR #{pr_num} is merged")
    return True


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


# ── Registry ─────────────────────────────────────────────────────────

VERIFIERS = {
    ("implement", "issue"): verify_implement_issue,
    ("implement", "worktree"): verify_implement_worktree,
    ("implement", "code"): verify_implement_code,
    ("implement", "test"): verify_implement_test,
    ("implement", "push"): verify_implement_push,
    ("implement", "pr"): verify_implement_pr,
    ("implement", "registry"): verify_implement_registry,
    ("review", "checkout"): verify_review_checkout,
    ("review", "review"): verify_review_review,
    ("review", "test"): verify_review_test,
    ("review", "push"): verify_review_push,
    ("ship", "checks"): verify_ship_checks,
    ("ship", "merge"): verify_ship_merge,
    ("ship", "cleanup"): verify_ship_cleanup,
}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Verify skill phase checkpoint")
    parser.add_argument("--skill", required=True, choices=["implement", "review", "ship"])
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
