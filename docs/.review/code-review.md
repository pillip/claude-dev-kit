# Code Review (degraded path — reviewer agent) — PR #68 / ISSUE-043

Source: claude-dev-kit:reviewer (degraded path; runtime /code-review not exposed to sub-agents).

## Verdict
Nothing blocking. Pure-cleanup PR; all three ACs independently confirmed green, the guard test is non-hollow (mutation-tested both directions), and the deletions are genuinely dead with complete doc-sync.

## Correctness — no blocking findings
- All four scripts genuinely dead before deletion. At base 5990c93, across every active surface (excluding ISSUE-027-exempt docs/, issues.md, CHANGELOG.md): ensure_permissions and ensure_gh appeared only in the README tree listing (lines 599/598); lint_skill_cache_order had zero external references; kit_root.sh (the script filename) appeared only in issues.md (historical, exempt) and its own test. No wrapper sources kit_root.sh — the ISSUE-023 "wrappers inline their own root resolution" claim holds.
- README doc-sync complete. Only those two scripts were ever in the README tree; the remaining listed scripts still exist.
- lint delete-vs-wire decision is non-regressive. The script was unwired to CI or any skill, so deleting it does not change enforcement status (was already zero). The referenced docs/cache_friendly_authoring.md does not exist, so no stale "run this lint" instruction is left behind.
- AC1/2/3 all green first-hand.

## Test quality — non-hollow, mutation-sound
- TC-043a mutation-tested: re-adding scripts/kit_root.sh -> FAILS (correct). TC-043b mutation-tested: dropping an active-surface file containing `bash scripts/ensure_gh.sh` -> FAILS (correct). Both probes cleaned up.
- The recalled-lesson collision is handled: kit_root.sh keeps its .sh extension so it is NOT a substring of the live find_kit_root in session_start.py.

## Low / informational (non-blocking, no fix required)
- [Low] tests/ excluded from the TC-043b scan (necessary — the guard file self-contains the banned tokens). A dead-script name re-introduced in a DIFFERENT test file would not be caught. Impact minimal, largely self-covering.
- [Low] Extension-less BANNED substring tokens (ensure_gh / ensure_permissions / lint_skill_cache_order) are broader than the kit_root.sh token; a future live identifier like ensure_github_token would false-positive. Currently zero collisions; broader direction favors catching regressions.
