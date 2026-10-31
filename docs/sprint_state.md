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
| ISSUE-096 | doing | 1 | review attempt 1 FAILED: `review` checkpoint exit 1 (no `docs/review_notes/ISSUE-096.md`) + 3 High findings | implemented |
| ISSUE-102 | backlog | 0 | - | backlog |
| ISSUE-103 | backlog | 0 | - | backlog |

## Measured Baseline (team-lead, measured directly — not inherited)
- `uv run pytest -q` on main at `778ccc7`: **2504 passed, 1 skipped in 28.81s**. The figure carried into this sprint's brief (2501) is wrong; this row is the measured one. Worktrees collect fewer tests because `tests/test_sprint_queue.py` parametrizes over untracked `docs/sprint_state.archive-*.md` files present only in the main checkout — decompose deltas with `--collect-only`, never by comparing totals.

## ISSUE-096 — FIFTH reproduction of its own defect, observed LIVE during its own review (2026-10-31)

This is the load-bearing measurement of the iteration, and it changes the issue rather than merely confirming it.

The reviewing sub-task invoked the runtime `/security-review` with an explicitly pinned subject. **The pinned arguments were discarded entirely** — the string appears nowhere in the prompt the harness produced. The harness auto-collected instead, and arrived carrying `GIT STATUS: On branch main`, `FILES MODIFIED: docs/sprint_state.md, issues.md`, `COMMITS: 1ec6757c…`, and `DIFF CONTENT: <persisted-output> Output too large (48.5KB)`, followed by "Review the complete diff above. This contains all code changes in the PR." The reviewer did not execute those instructions, voided the verdict, and re-ran with the subject forced.

Two legs are new and neither was in the issue as filed:

1. **The wrong subject was NOT empty — it was 48.5KB of main's dirty registry churn.** Every prior reproduction (#139, #141, #145) presented as a zero-byte collection, which is why the issue's AC-1 is written around a byte count greater than zero. A non-empty check passes this instance. **Only a digest comparison rejects it.** This vindicates the PR's central design call — a consumer-echoed digest over a producer-printed one — and retires the idea that "bytes > 0" is a sufficient test. It also means the defect is strictly worse than four reproductions suggested: it can deliver a plausible, large, wrong diff.
2. **The runtime `/security-review` accepts no review target at all.** This *measures* ISSUE-096's open question (a) — "whether the runtime skills accept an explicit diff/range argument at all … determines whether option (a) is even viable". For the security dimension the measured answer is **no**. From the worktree it would collect nothing (branch clean and pushed, the historical `(Bash completed with no output)`); from main it collects the wrong subject. Neither CWD works, so step 3.1(b) is **not executable for the security dimension** and its echo can never match — that dimension always refuses and degrades. This is a measurement, not a claim, and it needs a `docs/cc_feature_matrix.md` row as its durable carrier.

## Review attempt 1 — ISSUE-096 / PR #147 — FAILED, not merged

`review` checkpoint exited **1** (`docs/review_notes/ISSUE-096.md` not found in worktree): the review phase did not produce its own artifact. The reviewer conflated "change no code, to preserve the pinned digest" with "write no notes". All other review checkpoints exited 0; all five UI phases auto-skipped correctly for `UI: false`.

Verified-honest parts, re-measured rather than accepted on narration: the disarm matrix was re-run **7 of 7** by the reviewer with every count matching the implementer's claim exactly (M1 5/42, M2 4/43, M3 3/44, M4 1/46, M5 1/46, M6 3/44, M7 1/46, baseline 47, no survivors); AC-7's two test files are absent from the diff and byte-identical to main; `gen_skills.py` reproduces the committed `SKILL.md` with no drift; AC-6 is correctly refused rather than fabricated; bucket C is declared. Worktree suite **2533 passed, 1 skipped** under `uv run --extra dev`; no ISSUE-099 environmental failure appeared.

**Three High findings block the clean bill.** Note that finding (a) is exactly the failure mode this sprint's brief predicted — a new fail-open introduced *inside the guard being added*, now the third instance this session:
- **High (a) — fresh fail-open inside the new guard.** Any uncaught exception in the collection path exits **1**, the code the module itself defines as "computed and EMPTY … a genuine no-op PR, nothing to review". Reproduced by the reviewer's own probe: a `prunable` `.worktrees/<slug>` registration (routine after `wt_cleanup.sh` without `git worktree prune`) makes the resolver return a deleted dir, `subprocess.run(cwd=…)` raises `FileNotFoundError`, exit 1, empty stdout, **no `reason=` token**. AC-3 requires the two outcomes differ by exit code **or** reason token; here they differ by neither. `_git` also lacks the `shutil.which` guard its `gh` sibling has.
- **High (b) — AC-5's counter-evidence is self-attesting.** `record-subject` recomputes the subject itself and writes it captioned "Counter-evidence for what this review actually read". Nothing links the block to a `delegate` that passed; a run where the echo gate was never invoked, or was invoked and **rejected**, produces a byte-identical block at exit 0. The artifact AC-5 names does not deliver the property AC-5 states, yet the PR marks AC-5 done — lesson 14's shape, and lesson 6's own distinction violated by the fix for lesson 6.
- **High (c) — half the shipped workflow is unexecutable**, per the measurement above, and the PR does not disclose it.

Seven Mediums, of which two make the gate unusable on its very next use: the gate's own output invalidates it (pass 1 exit 0 at head A → step 6 commits the notes → head B → pass 2 exit 2 `subject-mismatch`, with no `--update` and step 5 forbidding hand-edits, so any second review cycle wedges — ISSUE-081 needed four), and the heading detector is a bare substring search so ISSUE-096's **own** review notes quoting `## Review Subject` will wedge it. Also: `--notes` satisfies the gate against a decoy file; an unparseable block appends a second block and corrupts permanently; `record-subject` anchors on `Path.cwd()` against the skill's `$WT/` convention; and the command the prose hands the reviewer (`git diff`) differs from the one the gate measures (`git diff --no-ext-diff`), so a configured `diff.external` rejects an honest review.

## Discovered Issues
- [iter 1] **ISSUE-106 filed** (`Manual: true`, P1, Depends-On ISSUE-096) — ISSUE-096's AC-6 split out as a sibling, exactly as ISSUE-096's own team-lead note at filing directs. AC-6 needs a live main-session, non-sub-task `/review` run; every sprint-pipeline context IS a sub-task, so the measurement is structurally unreachable from automation and cannot be dispatched by an iteration. Applied by team-lead under `registry_edit.sh` (planner drafted the content and has no `Bash` — see the ISSUE-074 counter-instance row below). Adds zero new `validate_issues.py` violations (15 pre-existing, 15 after; one AC was reworded from an em-dash to a comma before `when` to satisfy the GWT pattern).
- [iter 1] **ISSUE-074 counter-instance, 5th observation** — the `planner` agent has no `Bash` tool in this environment. It was dispatched text-only, returned the ISSUE-106 block as text, and wrote no file; team-lead applied it under the lock. The contract held because the dispatch assumed the absence rather than discovering it.
- [iter 1] ISSUE-096 implement findings, **none Critical or High**, so no follow-up issue was auto-created. Logged here as the carrier for the two Mediums:
  - *Medium* — `scripts/spec_gate.py` scans the whole issue block **including the `Out:` sub-list of `#### Scope (In/Out)`**, so naming an out-of-scope concern raises a spec signal on an issue that explicitly excludes it. Measured live on ISSUE-096: the word "migration" in its out-of-scope line about ISSUE-075 produced a non-sprint `hold` that is pure noise. Adjacent to ISSUE-102 (this sprint) but a **distinct** defect — 102 is path resolution, this is signal scoping. Needs its own carrier if it is to be real.
  - *Medium* — the pre-ISSUE-096 `emit --event review_delegated_to_*` path can still record a delegation with **no subject and no echo**. Left in place deliberately because ISSUE-066's tests pin it and ISSUE-096 AC-7 forbids modifying them. Pairs naturally with ISSUE-075's `_emit_event` migration.
  - *Low* — `implement/pr` checkpoint checks the `PR` field at step 11 but the skill writes it at step 12, so a correct pipeline always trips one advisory. Observed this iteration (exit 0 with `FAIL: ISSUE-096 has no PR field in issues.md`, self-corrected, re-ran clean).
  - *Low* — `docs/test_plan.md` has no Risk Matrix row or TC entries for the review-subject binding. The implement sub-task correctly declined to add one (untracked working doc on main, must not be committed on a feature branch).
  - *Low* — stray `.worktrees/issue-ISSUE-081-gate-evidence` worktree at `6aeaf3d` predates this sprint; ISSUE-081 is held, so it is left alone rather than cleaned up.
