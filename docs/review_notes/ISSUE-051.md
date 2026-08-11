# Review notes — ISSUE-051 (PR #81)

_Source: degraded path — claude-dev-kit:reviewer agent, dimensions: code (correctness + minimality) + security (runtime /code-review and /security-review unavailable to sub-agents)._

Scope: gitignore `docs/.review/` and untrack the 4 tracked scratch artifacts so parallel review branches stop conflicting on them; add a guard test. Diff: `.gitignore` (+7), 4 file deletions (`git rm --cached`), `tests/test_review_scratch_gitignore.py` (+57). Net +64 / -150.

**Verdict: APPROVE.** Clean, minimal, and correctly scoped. Both ACs are satisfied and verified independently (not on trust).

## Verification performed (evidence, not trust)

- **AC1 (no scratch-path conflicts):** `docs/.review/` is force-ignored (`git check-ignore docs/.review/findings.json` → rc=0) and nothing under it remains in the index (`git ls-files docs/.review` → empty). Untracked + ignored ⇒ scratch never enters a commit ⇒ parallel branches cannot collide on these paths.
- **AC2 (review flow still finds inputs):** The path is UNCHANGED. No committed-blob consumer exists — `grep -rn "\.review" scripts/` is empty; `.github/` has no reference; no `git show`/`git cat-file :docs/.review`. The synthesizer reads its input from a working-tree filesystem path (`scripts/synthesize_review_notes.py:207` `args.input.read_text(...)`), and the merge-auditor reads `docs/.review/{code-review,security-review}.md` from the working tree — both of which still exist on disk (ignored, not deleted). All references outside `scripts/` are prose (skills/agents/specs) read within one `/review` invocation.
- **Canonical record preserved:** `docs/.review/` does NOT over-match `docs/review_notes/` (`git check-ignore docs/review_notes/ISSUE-042.md` → rc=1; still tracked). This very file lands in the tracked canonical location.
- **Mutation (fail→pass) proven against the real pre-fix state:** on `main` the `.gitignore` has NO `docs/.review` rule and all 4 scratch files are tracked (`git ls-tree -r main` lists them). Therefore pre-fix: `test_no_review_scratch_files_are_tracked` fails (ls-files non-empty), `test_review_scratch_dir_is_gitignored` fails (check-ignore rc=1), `test_gitignore_documents_the_scratch_rule` fails (no rule). All three genuinely flip — this is a real guard, not an absence-fragile/hollow one. The untracked assertion is an occurrence check (list of tracked paths == []), not a phrasing-blacklist, per the ISSUE-040 lesson.
- **No regression:** full suite 1319 passed; the 3 new tests pass.

## Code Review (correctness + minimality)

### Low — `test_gitignore_documents_the_scratch_rule` is a substring/prose check that would also pass on the rationale comment alone (record-only)

Evidence: `tests/test_review_scratch_gitignore.py:53-56` asserts `"docs/.review" in gitignore`. The added `.gitignore` block (`.gitignore:15-19`) mentions `docs/.review/...` twice inside the rationale **comment**, so this assertion would stay green even if the actual functional rule line (`.gitignore:18`) were deleted and only the comment remained. Per the ISSUE-040 absence-guard lesson, a presence check keyed on a string that also appears in prose is loose.

Why it does not block: the loose check is fully backstopped by `test_review_scratch_dir_is_gitignored` (functional `git check-ignore`, index-aware) and `test_no_review_scratch_files_are_tracked` — no false-green is possible where the path is actually un-ignored or re-tracked. The three tests are complementary, not redundant: `check-ignore` rc=0 could in principle be satisfied by a local `.git/info/exclude` entry, and this documents-the-rule test is what pins the rule to the **committed, shared** `.gitignore` (the only artifact that fixes the problem for every clone/branch). So the intent is correct; only the matcher is imprecise.

Fix (optional, non-blocking): tighten to a line-oriented match, e.g. assert a non-comment line equals `docs/.review/` (skip lines starting with `#`), so deleting the functional rule while keeping the comment flips the test red.

_Minimality axis:_ Lean already. Ship. — `.gitignore` rule + `git rm --cached` + one guard test with three complementary assertions is the exact minimal shape for option (b). No abstraction, no dependency, no dead code, no speculative knob. The three test functions are not YAGNI duplication (each pins a distinct property: ignored / untracked / rule-is-in-committed-.gitignore). Checking a single representative file under the directory-level pattern is sufficient (the `docs/.review/` rule covers all four scratch types).

## Security Findings

_No findings._

The change removes files from tracking and adds a subprocess-based test. The test invokes `git` with a fixed argv list (`["git", "-C", str(REPO_ROOT), *args]`, `tests/test_review_scratch_gitignore.py:22-26`), no `shell=True`, no interpolation of untrusted/dynamic values; `REPO_ROOT` is derived from `__file__`. No secrets, no injection surface, no path traversal, no network egress. Un-tracking scratch artifacts reduces (does not increase) the committed surface.
