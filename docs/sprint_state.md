# Sprint State

## Meta
- Started: 2026-11-01
- Iteration: 1 / 20
- Parallel: 3
- Status: running
- Roster-Watermark: ISSUE-103
- Scope: **the pipeline's own gates do not gate.** Three defects sharing one shape, all found by turning a control on itself, all in controls the kit runs on every issue rather than in a new feature. ISSUE-096 (the delegated review auto-collects an empty diff, so a blocking review pass can return a clean bill having reviewed nothing — reproduced FOUR times), ISSUE-103 (the `implement/red` checkpoint accepts any pre-existing failure as RED, so the TDD gate can be satisfied by an unrelated breakage), ISSUE-102 (`spec_gate.py` can never return `proceed` for the issues it fires on, so the gate is structurally unsatisfiable — reproduced from both call sites).
- Ship order: **096 -> 103 -> 102**, and the reason is not arbitrary. If a delegated review collects an empty diff, every later review in this sprint would be reviewing nothing — so fixing 096 first makes 103's and 102's reviews real rather than ceremonial. Unlike the 081 -> 077 self-test, this one is not vacuous: 096's fix is verifiable by whether the subsequent reviews see their own diffs.
- Deferred: ISSUE-104 (SPEC validation not enforced in CI) and ISSUE-105 (the `Status: done` contradiction between implement step 12 and the team-lead contract) sit above the watermark and are flagged-not-dispatched. ISSUE-077 remains held. ISSUE-082 is `Manual: true` — a session restart plus a plugin update, not autonomously dispatchable.
- Boundary note: never set `KIT_SPRINT_DISPATCH_ABOVE_WATERMARK`.

## Issue Progress
| Issue | Status | Attempts | Last Error | Phase |
|-------|--------|----------|------------|-------|
| ISSUE-096 | doing | 0 | - | implemented |
| ISSUE-102 | backlog | 0 | - | backlog |
| ISSUE-103 | backlog | 0 | - | backlog |

## Measured Baseline (team-lead, measured directly — not inherited)
- `uv run pytest -q` on main at `778ccc7`: **2504 passed, 1 skipped in 28.81s**. The figure carried into this sprint's brief (2501) is wrong; this row is the measured one. Worktrees collect fewer tests because `tests/test_sprint_queue.py` parametrizes over untracked `docs/sprint_state.archive-*.md` files present only in the main checkout — decompose deltas with `--collect-only`, never by comparing totals.

## Discovered Issues
