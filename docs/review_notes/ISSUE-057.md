# Review Notes — PR #102

## Code Review
_Source: reviewer-degraded_

- **[Medium] --issue made optional globally fails open on pre-existing blocking gates [FIXED in review]**
  Evidence: scripts/verify_checkpoint.py:2108 — with the "-" default, implement/figma auto-passes, implement|generic/test runs the suite in the current directory instead of the issue worktree, and ship/cleanup trivially passes; all were previously loud argparse exit-2 errors.
  Fix: FIXED in review commit: main() now rejects the "-" sentinel for all issue-scoped skills (ISSUELESS_SKILLS = kickoff/scan/uiux family only) with exit 2 before verifier dispatch; 3 parametrized regression tests added (implement/figma, ship/cleanup, review/test) asserting the verifier is never dispatched.

- **[Low] DB heuristic omits mainstream Node drivers pg/mongodb — scan data-model SKIPs (fails open) on common stacks**
  Evidence: scripts/verify_checkpoint.py:1830 _DB_DEPENDENCY_PATTERN — matches mongoose/knex/drizzle but not the bare "pg" or "mongodb" package names.
  Fix: Add quoted-key patterns for package.json (e.g. "\"pg\"", "\"mongodb\""). Acceptable to defer: SPEC-057 documents the heuristic's fail-open trade-off and the SKIP line names the heuristic.

- **[Low] Philosophy skip-line regex misses the colon variant; fallthrough FAIL message omits the skip-line option**
  Evidence: scripts/verify_checkpoint.py:1934 — r"reference anchors?\s+skipped" does not match "Reference Anchors: skipped (no image input)"; the missing-section FAIL text does mention the skip line, but the literal_quote FAIL does not restate it.
  Fix: Widen the regex to allow an optional colon (r"reference anchors?:?\s+skipped") in a follow-up; low risk since the fragment template emits the exact non-colon wording.

- **[Low] checkpoint command string duplicated between fragments.py and gen_skills.CHECKPOINT_CMD**
  Evidence: scripts/fragments.py:106 hard-codes `bash scripts/checkpoint.sh` while scripts/gen_skills.py:46 defines CHECKPOINT_CMD with the same literal.
  Fix: Single-source it (fragments importing from gen_skills is cycle-free). Cosmetic; both are covered by generation-drift tests.

- **[Low] Test gaps: _scan_detects_db manifest/indicator-file branches and SKIP-line heuristic naming unasserted**
  Evidence: tests/test_verify_checkpoint_orchestration.py covers requirements.txt and migrations/ branches only; package.json/pyproject indicator-file branches and the SPEC-057 commitment that the SKIP line names the heuristic are untested. (The third reported gap — no test pinning --issue-required behavior — was closed by the in-review regression tests.)
  Fix: Extend TestScanDataModelConditional with package.json and schema.prisma fixtures and assert "heuristic" appears in the SKIP line.

- **[Low] [debt] 3 pre-existing no-trigger KIT-DEBT markers are the debt harvester's own docstring/test fixtures**
  Evidence: scripts/debt_harvest.py:44, tests/test_debt_harvest.py:27, tests/test_debt_harvest.py:59 — flagged by the advisory debt ledger; none are introduced by this PR and all are pattern examples/fixtures for the harvester itself.
  Fix: No action — false-positive class of the harvester scanning its own fixtures; recorded here to keep the ledger contract honest without manufacturing backlog items.

## Security Findings
_Source: reviewer-degraded_

- **[Medium] kickoff gains unused Bash(python3 scripts/*) grant beyond SPEC-057's stated scope [FIXED in review]**
  Evidence: skills/kickoff/SKILL.md:6 + .tmpl:6 — the project-relative python3 grant had zero call sites in the skill body (every checkpoint goes through bash scripts/checkpoint.sh) and allows prompt-free execution of any project-local scripts/*.py in brownfield repos.
  Fix: FIXED in review commit: removed Bash(python3 scripts/*) from the tmpl and regenerated. Both plugin-root forms retained — tests/test_plugin_root_resolution.py contractually requires them whenever kit scripts are allowlisted.

- **[Low] _scan_detects_db swallows OSError silently — unreadable manifest flips the data-model gate from FAIL to SKIP with no log line**
  Evidence: scripts/verify_checkpoint.py:1855 — except OSError: continue (note IsADirectoryError is an OSError subclass).
  Fix: Print a WARN naming the unreadable manifest before continuing. Fail-closed direction unaffected when indicators are readable.

- **[Low] Unvalidated leading-dash "-" sentinel could reach _find_worktree_path for issue-scoped skills [MITIGATED in review]**
  Evidence: scripts/verify_checkpoint.py:2110 — _find_worktree_path("-") compiles \-(?:-|/|$) which can match an unrelated worktree path containing --/trailing -.
  Fix: MITIGATED by the same in-review main() guard: the sentinel is rejected with exit 2 for all issue-scoped skills before any verifier (and thus any worktree lookup) runs; orchestration-skill verifiers ignore issue_id entirely.

- **[Low] Uncapped read_text on symlink-following artifact paths**
  Evidence: scripts/verify_checkpoint.py:1714/1772/1853/1930 — a malicious symlink at a fixed artifact path in a brownfield /scan target could cause local hang/OOM; fail-closed, no disclosure.
  Fix: Optional hardening: is_file() check or bounded read. Consistent with the engine's existing readers; defer unless brownfield threat model tightens.

## Over-Engineering

- **[Low] [delete] dead "prisma/schema.prisma" indicator entry — the prisma dir check always fires first**
  Evidence: scripts/verify_checkpoint.py:1828 — _DB_INDICATOR_DIRS contains "prisma", so any repo with prisma/schema.prisma already matched on the directory.
  Fix: Remove the redundant tuple entry (1 line). Not applied in review — zero behavioral impact; fold into the next touch of this file.

- **[Low] [yagni] Bash(python3 scripts/*) allowance with no caller in kickoff [FIXED in review]**
  Evidence: skills/kickoff/SKILL.md.tmpl:6 — duplicate of security SEC-1.
  Fix: FIXED in review commit (same change as SEC-1).
