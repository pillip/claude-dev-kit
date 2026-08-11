"""Guard: the review scratch dir docs/.review/ is gitignored and untracked (ISSUE-051).

Parallel review branches previously conflicted on the *committed* scratch files
``docs/.review/{code-review,findings.json,minimality,security-review}.md`` — every
later PR in a sprint went CONFLICTING on exactly these paths (PRs #58/#64/#65/#72).

The chosen fix (option b) gitignores ``docs/.review/`` so scratch artifacts never
enter a commit. They are read only within a single review invocation (the
synthesizer reads ``findings.json`` → ``docs/review_notes/ISSUE-XXX.md``; the
merge-auditor reads ``.review/*.md``), so working-tree presence suffices and no
checkpoint depends on them being committed. The canonical per-issue record
``docs/review_notes/ISSUE-XXX.md`` is unaffected.
"""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRATCH_DIR = "docs/.review"
REPRESENTATIVE_FILE = "docs/.review/findings.json"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
    )


def test_review_scratch_dir_is_gitignored():
    """A representative scratch file under docs/.review/ is matched by .gitignore."""
    proc = _git("check-ignore", REPRESENTATIVE_FILE)
    assert proc.returncode == 0, (
        f"{REPRESENTATIVE_FILE} is not gitignored (check-ignore rc={proc.returncode}); "
        "add 'docs/.review/' to .gitignore so parallel review branches don't collide "
        f"on scratch artifacts. stderr={proc.stderr!r}"
    )


def test_no_review_scratch_files_are_tracked():
    """No docs/.review scratch artifacts remain tracked in the index."""
    proc = _git("ls-files", SCRATCH_DIR)
    tracked = [line for line in proc.stdout.splitlines() if line.strip()]
    assert tracked == [], (
        f"tracked scratch artifacts still present: {tracked}. Run "
        "`git rm --cached docs/.review/*` so they no longer enter commits and can "
        "no longer conflict across parallel review branches."
    )


def test_gitignore_documents_the_scratch_rule():
    """A functional (non-comment) .gitignore rule ignores docs/.review/ (durable decision).

    Matches the actual rule LINE, not any substring — a rationale comment alone
    (which also contains 'docs/.review') must not keep this green if the functional
    rule is deleted (ISSUE-040 absence-guard: occurrence-whitelist, not phrasing).
    """
    lines = [
        line.strip()
        for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    ]
    rule_lines = [line for line in lines if line and not line.startswith("#")]
    assert "docs/.review/" in rule_lines, (
        "a non-comment '.gitignore' rule line must equal 'docs/.review/' so review "
        "scratch artifacts are intentionally untracked (ISSUE-051); a rationale "
        "comment alone is not enough."
    )
