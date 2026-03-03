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
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


# ── Implement skill verifiers ────────────────────────────────────────


def verify_implement_issue(issue_id: str, **_) -> bool:
    """GH-Issue field exists in issues.md and `gh issue view` succeeds."""
    issues_md = Path("issues.md")
    if not issues_md.exists():
        print(f"FAIL: issues.md not found")
        return False

    text = issues_md.read_text(encoding="utf-8")
    pattern = rf"(?:^### {re.escape(issue_id)}:.*?)(?=\n### |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        print(f"FAIL: {issue_id} not found in issues.md")
        return False

    block = match.group(0)
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

    slug = issue_id.lower().replace("-", "-")
    pattern = rf"issue/{re.escape(slug)}"
    if not re.search(pattern, result.stdout, re.IGNORECASE):
        print(f"FAIL: no worktree found matching pattern '{pattern}'")
        return False

    print(f"PASS: worktree exists for {issue_id}")
    return True


def verify_implement_code(issue_id: str, **_) -> bool:
    """Worktree has non-docs file changes."""
    result = _run(["git", "worktree", "list", "--porcelain"])
    if result.returncode != 0:
        print(f"FAIL: git worktree list failed")
        return False

    slug = issue_id.lower()
    wt_path = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree ") and slug in line.lower():
            wt_path = line.split(" ", 1)[1]
            break

    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    diff = _run(["git", "diff", "--name-only", "main"], cwd=wt_path)
    if diff.returncode != 0:
        print(f"FAIL: git diff failed in worktree")
        return False

    changed = [f for f in diff.stdout.strip().splitlines() if f and not f.startswith("docs/")]
    if not changed:
        print(f"FAIL: no non-docs file changes found in worktree")
        return False

    print(f"PASS: {len(changed)} non-docs file(s) changed")
    return True


def verify_implement_test(issue_id: str, **_) -> bool:
    """pytest exits 0."""
    result = _run(["python3", "-m", "pytest", "-q", "--tb=short"])
    if result.returncode != 0:
        print(f"FAIL: pytest failed (exit {result.returncode})")
        if result.stdout:
            print(result.stdout[-500:])
        return False

    print(f"PASS: tests passed")
    return True


def verify_implement_push(issue_id: str, **_) -> bool:
    """Remote branch exists."""
    result = _run(["git", "branch", "-r"])
    if result.returncode != 0:
        print(f"FAIL: git branch -r failed")
        return False

    slug = issue_id.lower()
    if not any(slug in line.lower() for line in result.stdout.splitlines()):
        print(f"FAIL: no remote branch found containing '{slug}'")
        return False

    print(f"PASS: remote branch exists for {issue_id}")
    return True


def verify_implement_pr(issue_id: str, **_) -> bool:
    """PR exists and body contains `Closes #N`."""
    issues_md = Path("issues.md")
    if not issues_md.exists():
        print(f"FAIL: issues.md not found")
        return False

    text = issues_md.read_text(encoding="utf-8")
    pattern = rf"(?:^### {re.escape(issue_id)}:.*?)(?=\n### |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        print(f"FAIL: {issue_id} not found in issues.md")
        return False

    block = match.group(0)
    pr_field = _extract_field(block, "PR")
    if not pr_field:
        print(f"FAIL: {issue_id} has no PR field in issues.md")
        return False

    # Extract PR number
    pr_match = re.search(r"(\d+)\s*$", pr_field)
    if not pr_match:
        print(f"FAIL: cannot parse PR number from: {pr_field}")
        return False

    pr_num = pr_match.group(1)
    result = _run(["gh", "pr", "view", pr_num, "--json", "body", "-q", ".body"])
    if result.returncode != 0:
        print(f"FAIL: gh pr view {pr_num} failed: {result.stderr.strip()}")
        return False

    if not re.search(r"Closes\s+#\d+", result.stdout):
        print(f"FAIL: PR #{pr_num} body does not contain 'Closes #N'")
        return False

    print(f"PASS: PR #{pr_num} exists with Closes reference")
    return True


def verify_implement_registry(issue_id: str, **_) -> bool:
    """Status=done and PR field exists in issues.md."""
    issues_md = Path("issues.md")
    if not issues_md.exists():
        print(f"FAIL: issues.md not found")
        return False

    text = issues_md.read_text(encoding="utf-8")
    pattern = rf"(?:^### {re.escape(issue_id)}:.*?)(?=\n### |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        print(f"FAIL: {issue_id} not found in issues.md")
        return False

    block = match.group(0)
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
    """review_notes.md has Code Review and Security Findings sections."""
    # Find worktree for issue
    result = _run(["git", "worktree", "list", "--porcelain"])
    slug = issue_id.lower()
    wt_path = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree ") and slug in line.lower():
            wt_path = line.split(" ", 1)[1]
            break

    if not wt_path:
        print(f"FAIL: no worktree found for {issue_id}")
        return False

    notes = Path(wt_path) / "docs" / "review_notes.md"
    if not notes.exists():
        print(f"FAIL: docs/review_notes.md not found in worktree")
        return False

    content = notes.read_text(encoding="utf-8")
    missing = []
    if "Code Review" not in content:
        missing.append("Code Review")
    if "Security Findings" not in content:
        missing.append("Security Findings")

    if missing:
        print(f"FAIL: review_notes.md missing sections: {', '.join(missing)}")
        return False

    print(f"PASS: review_notes.md has required sections")
    return True


def verify_review_test(issue_id: str, **_) -> bool:
    """pytest exits 0."""
    return verify_implement_test(issue_id)


def verify_review_push(issue_id: str, **_) -> bool:
    """Review commits pushed to remote."""
    return verify_implement_push(issue_id)


# ── Ship skill verifiers ─────────────────────────────────────────────


def verify_ship_checks(issue_id: str, **_) -> bool:
    """`gh pr checks` passes."""
    issues_md = Path("issues.md")
    if not issues_md.exists():
        print(f"FAIL: issues.md not found")
        return False

    text = issues_md.read_text(encoding="utf-8")
    pattern = rf"(?:^### {re.escape(issue_id)}:.*?)(?=\n### |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        print(f"FAIL: {issue_id} not found in issues.md")
        return False

    pr_field = _extract_field(match.group(0), "PR")
    pr_match = re.search(r"(\d+)\s*$", pr_field)
    if not pr_match:
        print(f"FAIL: cannot parse PR number for {issue_id}")
        return False

    result = _run(["gh", "pr", "checks", pr_match.group(1)])
    if result.returncode != 0:
        print(f"FAIL: gh pr checks failed for PR #{pr_match.group(1)}")
        return False

    print(f"PASS: PR checks are green")
    return True


def verify_ship_merge(issue_id: str, **_) -> bool:
    """PR is in merged state."""
    issues_md = Path("issues.md")
    if not issues_md.exists():
        print(f"FAIL: issues.md not found")
        return False

    text = issues_md.read_text(encoding="utf-8")
    pattern = rf"(?:^### {re.escape(issue_id)}:.*?)(?=\n### |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        print(f"FAIL: {issue_id} not found in issues.md")
        return False

    pr_field = _extract_field(match.group(0), "PR")
    pr_match = re.search(r"(\d+)\s*$", pr_field)
    if not pr_match:
        print(f"FAIL: cannot parse PR number for {issue_id}")
        return False

    result = _run(["gh", "pr", "view", pr_match.group(1), "--json", "state", "-q", ".state"])
    if result.returncode != 0:
        print(f"FAIL: gh pr view failed")
        return False

    state = result.stdout.strip()
    if state != "MERGED":
        print(f"FAIL: PR #{pr_match.group(1)} state is '{state}', expected 'MERGED'")
        return False

    print(f"PASS: PR #{pr_match.group(1)} is merged")
    return True


def verify_ship_cleanup(issue_id: str, **_) -> bool:
    """Worktree has been removed."""
    result = _run(["git", "worktree", "list", "--porcelain"])
    if result.returncode != 0:
        print(f"FAIL: git worktree list failed")
        return False

    slug = issue_id.lower()
    if any(slug in line.lower() for line in result.stdout.splitlines() if line.startswith("worktree ")):
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
