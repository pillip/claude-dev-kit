# Sprint State

## Meta
- Started: 2026-11-01
- Iteration: 1 / 20
- Parallel: 3
- Status: paused — both remaining target issues are at `waiting` / `review-rework` awaiting a human. Not blocked on infrastructure this time, and nothing is left mid-flight: both reworks are committed and pushed, both reviews completed with all 12 checkpoints green, and both escalations are the issues' own pre-registered conditions firing as written.
- Roster-Watermark: ISSUE-103
- Scope: **the pipeline's own gates do not gate.** Three defects sharing one shape, all found by turning a control on itself, all in controls the kit runs on every issue rather than in a new feature. ISSUE-096 (the delegated review auto-collects an empty diff, so a blocking review pass can return a clean bill having reviewed nothing — reproduced FOUR times), ISSUE-103 (the `implement/red` checkpoint accepts any pre-existing failure as RED, so the TDD gate can be satisfied by an unrelated breakage), ISSUE-102 (`spec_gate.py` can never return `proceed` for the issues it fires on, so the gate is structurally unsatisfiable — reproduced from both call sites).
- Ship order: **096 -> 103 -> 102**, and the reason is not arbitrary. If a delegated review collects an empty diff, every later review in this sprint would be reviewing nothing — so fixing 096 first makes 103's and 102's reviews real rather than ceremonial. Unlike the 081 -> 077 self-test, this one is not vacuous: 096's fix is verifiable by whether the subsequent reviews see their own diffs.
- Deferred: ISSUE-104 (SPEC validation not enforced in CI) and ISSUE-105 (the `Status: done` contradiction between implement step 12 and the team-lead contract) sit above the watermark and are flagged-not-dispatched. ISSUE-077 remains held. ISSUE-082 is `Manual: true` — a session restart plus a plugin update, not autonomously dispatchable.
- Boundary note: never set `KIT_SPRINT_DISPATCH_ABOVE_WATERMARK`.

## Orchestrator Hold (2026-11-07) — blocked on the account spend limit, not on the work

**The account's monthly spend limit is exhausted and sub-agent dispatch now fails instantly, including with the `opus` override.** Earlier in this session the limit was model-scoped (Fable 5 only) and `opus` was the workaround; it is now account-wide. Two agents died to it mid-phase. Nothing is lost — every artifact below was verified from branch, PR and worktree state rather than from an agent report.

**Where the two issues actually stand:**
- **ISSUE-103** (`implementing`, Attempts 1, PR **#150** OPEN, branch `issue/ISSUE-103-red-scope` at `0c10ca5`): review 1 returned **PASS-with-findings** and a rework for findings F1/F2 was in flight when the limit hit. Its worktree carries **3 uncommitted files** — `scripts/verify_checkpoint.py`, `tests/test_red_gate_scoping.py`, `tests/test_verify_checkpoint.py`. The dying sub-agent's last report said *"All kill-mutants killed, both negative controls survived. Now the full suite and the collection decomposition"* — i.e. the rework's substance was done and it was in the verification step. **Those three files are deliberately left uncommitted:** committing another agent's half-verified work would put unmeasured changes on a PR under review, and the mutation evidence it cited is not reproducible from the files alone.
- **ISSUE-102** (`reviewing`, Attempts 1, PR **#151** OPEN, branch `issue/ISSUE-102-spec-gate-satisfiable` at `b557abf`, worktree clean): its rework was verified and **review 2 was in flight** at that tip when the limit hit. Nothing uncommitted.

**Resume procedure when the limit resets:** re-read this file, then for ISSUE-103 inspect the three uncommitted files against review 1's F1/F2 findings and re-run the mutation matrix yourself before committing — do not adopt them on the strength of the dead agent's report (a sub-agent's narration of its own probe result has been unreliable repeatedly this session). For ISSUE-102, re-dispatch review 2 at `b557abf`. Neither issue needs its implement phase redone.

**Sprint scope reached 1 of 3** (ISSUE-096 shipped at `f3d4ed6`); 102 and 103 are mid-pipeline, not failed. Attempts stay at 1 for both — the deaths were infra, not phase failures.

## Orchestrator Hold #2 (2026-11-07) — both issues escalated by their own pre-registered conditions

**Sprint scope: 1 of 3. ISSUE-096 shipped (`f3d4ed6`); ISSUE-102 and ISSUE-103 are both at `waiting` / `review-rework`, Attempts 2, and are NOT being re-dispatched.** Neither PR was merged, both worktrees are clean and deliberately kept, and `issues.md` was never written during the phase (both still `Status: doing`). This is the escalation rule firing as written, not a failure to execute.

**ISSUE-103 — 7 Highs on review 2, 4 of them new.** The resume adjudicated the dead agent's three uncommitted files rather than adopting them, and that adjudication is the part worth keeping: F2's hoist and F1's pytest half were **adopted on measurement** (reverting each kills a real-consumer test, and F2's test asserts `runs == []` so it pins ordering rather than output), but **F1's JS half had been quietly declined** by the dead agent and disclosed as a residual. Measured against real npm, exit 1 does collide (`Missing script` vs a real failure) so that half was forced — but **exit 127 collides with nothing**, so "the runner never executed" was still certifying RED. The resume wrote that fix plus five tests including a real-npm consumer probe (`1a68895`, CI green).

Then review 2 reopened **ISSUE-103's own defect one layer up**: the parser scans all of stdout, so an unrelated failing test that merely *prints* a `FAILED <branch file>` line forges attribution — ground truth `tests/test_new.py` **passes**, the gate reports `failing: tests/test_new.py`, exit 0. **The provenance is the lesson, not the bug:** review 1 filed this Medium because "the verdict is driven by the exit code", and the F1 fix made *attribution* drive the verdict — so the severity rationale **expired and nobody re-derived it**. H3 also reproduced: `FORCE_COLOR=1` alone refuses every genuine RED.

**ISSUE-102 — satisfiability is genuinely fixed, and it still failed.** Both directions confirmed 16/16, both mandated mutants dead, the rework properly bounded. The failure is a different shape: **review 1 scoped a defect *class* to a single *line*.** The same shape sits at four I/O sites — `_git`'s tuple omits `PermissionError`; `:197`'s `is_dir()` has no guard at all; `:258`'s stat sits outside its `try`, which is the identical defect the rework was dispatched to fix; and non-strict `resolve()` raises `RuntimeError` on ELOOP, which `(OSError, ValueError)` does not catch. Plus a reproduced High 2: the untrusted `Spec:` value bare-interpolates into `reasons` and forges the `INCOMPLETE` marker step 0c greps for.

**Self-corrections the resume made against its own work**, which is why its verdict is worth trusting: its "8 mutants, zero survivors" was true of **its matrix, not of the guard** — the reviewer's 25-mutant battery found 2 survivors, one of them in surface the resume itself had added (npm's legacy contract unpinned for exits 4/5). Its hazard-note bound was false, so **its own disclosure became the defect** — the rule it had just applied to the inherited work. Against that, the reviewer's refutation of its exit-127 branch **does not reproduce** (npm 11.5.2 collapses script codes to 1): right finding, wrong mechanism, recorded both ways.

**A correction to the orchestrator's own brief:** the inherited "concurrent suites damage the tree" constraint is **overstated** — every test `.worktrees/` path is throwaway, and the two reviews ran in parallel without incident. Future briefs should not carry it as written.

**What this sprint actually established.** Its thesis — that the pipeline's own gates do not gate — was confirmed more thoroughly by *trying to fix it* than by the original findings. ISSUE-103 produced a new defect of the same class at **three successive layers**, including inside the resume's own work, which is why no third rework was attempted from inside the loop. Both issues now need a human to decide whether the remaining classes are worth closing at this depth or whether these two gates should be bounded and declared, the way SPEC-088 declined the disarm-direction property.

**Filed by the orchestrator, because it had no carrier and will not be reproducible:** **ISSUE-110** — the two concurrent reviewers diverged on whether `decide`'s `delegated` verdict means independent delegation or self-invocation, and ISSUE-102's reviewer **refused a `Skill` that loads into its own context as self-attesting**. If `delegated` can be returned for a self-invoked pass, the tag is not evidence of independence, which undercuts SPEC-019's framing. It sharpens ISSUE-106 rather than duplicating it.

**Resume facts for whoever picks this up:** ISSUE-103 at PR #150, branch tip `1a68895` (the resume's own committed fix, CI green); ISSUE-102 at PR #151, branch `b557abf`. Findings are in `docs/review_notes/ISSUE-103.md` and `docs/review_notes/ISSUE-102.md`. ISSUE-105 was guarded a 4th and 5th time. Measure any baseline yourself — orchestrator-supplied numbers have been wrong three times this session.

## Issue Progress
| Issue | Status | Attempts | Last Error | Phase |
|-------|--------|----------|------------|-------|
| ISSUE-096 | done | 2 | - | shipped |
| ISSUE-102 | waiting | 2 | review 2 REWORK (2 High, both reproduced by team-lead); Reason=review-rework — escalated, no second rework | reviewed |
| ISSUE-103 | waiting | 2 | review 2 REWORK (7 High, 4 new; H1/H3 reproduced by team-lead by execution, H2/H4 confirmed structurally); Reason=review-rework — escalated, no second rework | reviewed |

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

## ISSUE-096 — rework landed, review attempt 2 dispatched

Rework pushed **fast-forward** `ee60437..7e3d5f9` (no force-push; `ee60437` verified an ancestor of `7e3d5f9`). Team-lead verified independently rather than on narration: PR #147 `OPEN`/not-draft/`MERGEABLE`, 7 files, AC-7's `tests/test_review_context.py` and `tests/test_review_delegation_guard.py` byte-identical to `origin/main` and absent from the diff, and `tests/test_subagent_skill_grant.py` byte-identical (genuinely unmodified, so the new matrix row did not buy its green by editing the guard).

All three Highs addressed. High (a) — the new fail-open — was fixed by giving "could not compute" its own exit code and named reasons (`git-unavailable`, `worktree-path-missing` naming `git worktree prune`, and a dispatcher mapping anything unmodelled to `collection-error` at exit 2), leaving exit 1 to mean only a genuinely computed-empty diff. The new reasons stayed inside the subject-reason set; the closed three-value event vocabulary was not touched. High (b) was fixed by making `record-subject` **consume** a verification emitted by a passing `delegate` through the existing single emission seam, with the run file validated on read as untrusted input. High (c) was fixed by disclosure plus one dated matrix row.

Disarm matrix grew **7 → 22 mutants**, baseline 126 passed, zero survivors. Two results are worth more than their counts, and both are the kind of disclosure that is hard to fake:
- **M19 did not fail — it HUNG.** Removing the non-blocking open together with the regular-file check made the gate block indefinitely on a planted FIFO (timed out at 150s). That is the planted-FIFO hazard class the kit already knows, caught inside a new guard, and it is why the receipt open carries both defences — the non-blocking open is what keeps the regular-file check reachable.
- **M22 survived on its first run.** Through the CLI the read half always refuses first, so the write half's symlink defence was an untested branch. It was pinned at its own boundary and re-run rather than deleted, and the whole 22-row table was then re-measured against the final baseline so no row came from a stale tree.

Module tests 47 → 126; worktree suite **2533 → 2612 passed, 1 skipped**, delta decomposed with `--collect-only` (+79, fully accounted). No ISSUE-099 environmental failure appeared in either run.

The diff nearly doubled during a rework (97827 → 169229 bytes), so scope discipline is the thing review 2 is told to weigh hardest — ISSUE-079 exists because unrequested surface shipped and the defects lived in it.

Registry commits `1ec6757` and `355da06` pushed to `origin/main` fast-forward (`778ccc7..355da06`), so the remote registry is durable and the eventual squash lands on top of it. Review subject for attempt 2 re-measured by team-lead against the **committed** tree: `778ccc7..7e3d5f9`, **169229 bytes / 7 headers / sha256 `0fe8490f2ceb0c79…`**.

## Review attempt 2 — ISSUE-096 / PR #147 — checkpoints all PASS, one High remains

All review checkpoints exited **0**, including `review` (attempt 1's failure, resolved: the notes artifact now exists). Five UI phases auto-skipped correctly. Worktree suite **2612 passed, 1 skipped**, decomposed with `--collect-only` and fully reconciled against the measured main baseline (2504 + 126 new − 18 archive-parametrized tests unreachable in a worktree = 2612). Zero environmental failures; ISSUE-099 did not appear.

The reviewer regenerated the subject digest and it **matched exactly** (169229 / 7 / `0fe8490f…`), and all three runtime passes that produced a verdict echoed a matching byte count. The three previously-open Highs all verify as genuinely fixed, probed adversarially rather than read: exit 1 is now reachable only from the two computed-empty constructions, both carrying reason tokens, across prunable-worktree, `git`-absent, `gh`-absent, non-git-CWD, unreachable-head-oid, malformed-`--pr`, closed-fd-2 and broken-pipe probes.

**Reproduction #6, during attempt 2.** The runtime `/security-review` again discarded every pinned argument and auto-collected `GIT STATUS: On branch main` with `DIFF CONTENT: (Bash completed with no output)` — the zero-byte shape this time, because main was clean. The dimension was correctly degraded to the kit's own reviewer. One leg worth recording: had that pass been fed to the new echo gate it would have echoed 0 bytes, and the gate was verified to refuse exactly that with nothing recorded. So the six reproductions now span both shapes — zero-byte and plausible-but-wrong — and the digest comparison is the only check that catches both.

**End-to-end dogfood on the live PR, verified by execution.** `collect` driven with CWD at the **main** checkout resolved the `.worktrees/…` path at 169229 bytes — the exact input that yielded zero bytes four times, which is AC-4 measured on the real repository rather than a fixture. A second review cycle after committing the notes (the head-moved case that wedged the previous design) exits 0 with exactly one counter-evidence block, replaced in place.

**One High remains, and it is the fourth fail-open inside a guard being added — the predicted failure mode, in the predicted place.** `delegate`'s "verify the receipt landed" read-back is satisfied by **another dimension's** receipt, so it is vacuous for every dimension after the first. It is the lesson-16 shape precisely: the read-back was tested in one arm, at whole-file level, never per-dimension. Two of three passes rated it Medium; the reviewer preserved the higher upstream severity rather than averaging, which is the right call. Blast radius is bounded because `record-subject` re-verifies, and the fix is reported as two lines plus one test.

**The structurally important Medium: no gate checks that the binding ran.** `verify_review_review` passes byte-identically with or without the counter-evidence block, so ISSUE-096's machinery is still **prose-gated at the point of use** — nothing fails if `collect` / `delegate` / `record-subject` are never called. This is the issue's own Implementation Note coming true: "if it stays prose, AC-2 has to be satisfied by something else, because an instruction is exactly what was skipped twice." Shipping a gate that does not gate, in a sprint whose theme is that the pipeline's own gates do not gate, would be self-defeating.

**Decision: rework 2 rather than ship with follow-up carriers.** The team-lead contract does permit shipping with unresolved Highs carried as follow-up issues, and all checkpoints passed, so `reviewed` was available. It was declined: the remaining High is a fail-open *inside the new guard* and is a two-line fix, and the Medium above is one checkpoint assertion. Deferring either would hand the next sprint the same defect class this one exists to remove. Attempts is recorded as 2; attempt 2 was a checkpoint-pass-with-findings, not a failure, so this is not two consecutive review failures. If re-verification still shows a High, ISSUE-096 goes to `waiting` / `review-rework` for a human.

Other Mediums folded into rework 2: notes are mutated **before** the read-back, so one unpaired fence wedges `record-subject` permanently while accumulating a block per retry; and step 3.1's degradation `emit` omits the run id, silently dropping the very event that proves a degradation happened (`emit` anchors on CWD while `delegate` anchors on the worktree). Lows folded in: a tracked, pushed file publishes an absolute `/Users/<name>/…` path; the `main-checkout` fallback writes notes where its own docstring says it will not; "nothing else exits 1" is true but unenforced because the exit code is a free parameter; the PR declares no Kept-Surface bucket (it is **C**); and a scope-discipline trim of surface with no AC and no consumer (`head_ref` written-never-read, `base_oid` duplicating `range`) — ISSUE-079's species, in a diff that nearly doubled during a rework.

## Baseline re-measured on main at `fa9daad` (team-lead, this iteration)

`uv run pytest -q` = **2504 passed, 1 skipped in 28.55s**. Measured directly rather than inherited: the figure carried in the dispatch brief (2501) is wrong for the third time this session, and the measured one is unchanged from the previous iteration's measurement at `778ccc7`. The archive-parametrization gap between main and a worktree is unchanged, so test-count deltas are still only legible through `--collect-only`.

Diff size pinned before the rework so "it shrank" is checkable rather than asserted. The product diff — `git diff --no-ext-diff $(git merge-base origin/main HEAD)..HEAD -- . ':(exclude)docs/review_notes/ISSUE-096.md'` — measures **169229 bytes / 7 headers**, byte-identical to the digest review 2 verified, which confirms the excluded file is the reviewer's own artifact and not product surface. The full `base..head` diff is 202098 / 8. The shrink target for rework 2 is therefore the product figure, and the comparison is like-for-like.

## Rework 2 — dispatched (2026-11-02)

Dispatched to one `developer` sub-task at `opus`, scoped to the named findings only, with the review-2 record as its input and no licence to redesign. The predecessor's decision is honoured rather than re-litigated.

Required: the High (bind `delegate`'s read-back to `args.dimension` — `_require_verification`'s return value is discarded today, so another dimension's receipt satisfies it, and `verification-missing` already exists so no vocabulary change is needed) with its per-dimension disarm test at the arm nothing reaches — a readable-but-unappendable run file plus a pre-existing receipt for the OTHER dimension, driven through the real CLI. Written test-first, red observed before the fix. Three Mediums: write-the-notes-once (validate the candidate before mutating, so a refusal leaves the file byte-untouched and retries stop accumulating), the degradation `emit`'s missing run id, and the checkpoint assertion that makes the binding gated rather than prose-enforced. Four Lows: the absolute home path out of the committed block, the `main-checkout` write making code and docstring agree, the exit-code/reason pairing enforced as a real check rather than left a free parameter, and the bucket declaration.

Three constraints the sub-task was given as hard limits rather than preferences:
- **The diff must shrink below 169229 product bytes.** It nearly doubled during rework 1, which is ISSUE-079's species. `head_ref` (written, never read) and `base_oid` (the left half of `range`) are deleted outright; the six-way restatement of the 2026-10-31 anecdote collapses to a citation of the measurement registry that owns it; and the minimality pass's test trims are taken only in the loss-free form it specified, with the two M22 killers explicitly kept.
- **No new reason tokens and no shared-contract change.** The unterminated-fence refusal reuses an existing token with a message that names the real cause. The degradation event is fixed in the skill (prefix the knob, run from the worktree) rather than by re-anchoring `cmd_emit`, whose `Path.cwd()` contract is pinned by ISSUE-066 tests that AC-7 forbids touching — review lesson 8.
- **`KIT_REVIEW_GH_TIMEOUT` is kept, against the minimality finding.** Deleting the override to hard-code the 30s bound would reinstate the hard-coded-subprocess-timeout class this repo already learned (ISSUE-046/047), and review lesson 2 is fully satisfied for this knob. Kept surface, declared in the PR body.

The nested-fence defect (a 4-backtick fence wrapping a 3-backtick fence re-opens the parser) is deliberately NOT fixed here: its fix belongs in `sprint_queue`'s shared helper so both consumers inherit it, which is a shared-contract change with no AC in this issue. It needs its own carrier.

## Rework 2 — landed at `710092c`; review 3 dispatched (2026-11-02)

Rework 2 pushed and verified by team-lead independently rather than on narration, because the developer sub-agent may still have been finalising its own report when this iteration began.

- Branch tip moved `47ad48b` -> **`710092c`** ("fix(review): bind delegate's read-back to its own dimension; gate the binding at the point of use"). Worktree **clean, 0 dirty files**, so the tree under review is the committed one. PR #147 `OPEN` / not draft / `MERGEABLE`, `headRefOid` equal to the branch tip.
- **The scope trim is real, verified mechanically rather than from the insertion delta.** At `47ad48b` the payload carried `"base_oid": base_oid` and `"head_ref": f"gh:pr/{pr}#headRefOid"` (`scripts/review_context.py:722-723`). At `710092c` both are gone from the payload; `base_oid` survives only as a local in `_resolve` feeding `merge-base` and `range`, which is the consumer it was supposed to have, and `head_ref` appears nowhere in `scripts/`. The key-set test's forbidden set grew to `{"merge_base", "head_ref", "base_oid"}` — which is exactly the fix review 2 asked for, since that test previously passed with an unread field still present.
- **Diff sizes re-measured like-for-like.** Product diff (excluding the reviewer's own `docs/review_notes/ISSUE-096.md`): **167453 bytes / 9 headers / sha256 `4c73e35a0bbe40c7...`**, down from 169229 / 7 — a real shrink of 1776 bytes below the target. The header count rose 7 -> 9 because the checkpoint-assertion Medium added `scripts/verify_checkpoint.py` and `tests/test_verify_checkpoint.py` to the product surface, so the shrink absorbed two new files rather than being bought by deleting them.
- **Gate subject for review 3, measured by team-lead and then confirmed by the gate's own `collect`:** full `base..head` = **200322 bytes / 10 headers / sha256 `e75fc65b5ab832df...`**, range `b4b7f13...710092c`. The full figure now exceeds the product figure because the notes artifact is committed as of `47ad48b`; at `7e3d5f9` the two coincided, which is why review 2 saw one number. Review 3's reviewer was given NO numbers and asked to measure its own — a pasted digest is the one remaining way past this gate.
- **AC-4 dogfooded again on the live repository.** `collect --pr 147` driven with CWD at the **main checkout** resolved `worktree_source=branch-worktree` and 200322 bytes — the exact input that yielded zero bytes on four prior reproductions.

Review 3 dispatched to one reviewer sub-task at `opus`, scoped to re-verification with five priorities: the per-dimension binding probed in the **disarm** direction through the real CLI (lesson 16, seventh observation); the exit-1-only-from-computed-empty invariant re-established across review 2's probe matrix; the three Mediums at their named failure signatures; the test trim checked for lost mutant killers (M19's FIFO hang pair and M22's write-half symlink defence); and the subject binding turned on this review itself. Two measurement demands were added that review 2 did not carry:

- **The trimmed prose made a new claim that has to be measured.** Step 3.1(a) deleted the enumerated reason list and now asserts stderr "names `reason=` *and its remedy*". That relocates review 1's finding into stderr, so stderr has to deliver it — `worktree-path-missing` must still name `git worktree prune`.
- **The new checkpoint assertion discloses its own blind spot, and a disclosed residual is a CLAIM.** `_review_subject_bound` triggers on the presence of a receipt, so a delegated review that skipped the binding entirely leaves no receipt and passes. The reviewer was asked to measure which inputs can suppress the trigger (noting the helper defaults `KIT_RUN_ID` to `review-<issue>`), and to report whether a stronger trigger exists in **existing** surface — `decide` already knows which dimensions it routed `delegated` — without implementing it. Whether that residual is a design limit or an unclosed gap is the question that decides the severity.

The predecessor's escalation condition is carried forward unchanged and is binding: **if review 3 still shows a High, ISSUE-096 goes to `waiting` / `review-rework` and stops for a human. No third rework.**

## Rework 2 — a SECOND team-lead instance is live on ISSUE-096 (concurrency hazard, measured)

**Two team-lead instances were dispatched for this issue and both acted on it.** This instance dispatched the rework-2 `developer` sub-task that produced `710092c`; while that sub-task was finalising, a second instance measured the same tip, wrote the section above, and **dispatched its own review 3**. Established by measurement, not inference:

- Every digest in the section above is exact — full `b4b7f13...710092c` = 200322 bytes / 10 headers / sha256 `e75fc65b5ab832df…`, product sha256 `4c73e35a0bbe40c7…` — so the writer measured this tree rather than narrating. It is a competent peer, not a stray write.
- The progress row had been set by this instance to `implementing` / "rework 2 IN FLIGHT" and was found rewritten to `reviewing` / "review 3 IN FLIGHT … at `710092c`", referencing an oid that did not exist when this instance last wrote.
- The review is **running**, not merely dispatched: `.worktrees/issue-ISSUE-096-bind-review-diff/.claude/runs/unattributed.jsonl` took fresh `gates_degraded_path_used` writes at 23:13, one minute before this check, and `docs/.review/*` plus the notes file still carry their 2026-10-31 review-2 mtimes — a reviewer is executing the suite in that worktree right now.

**This instance therefore declined to dispatch a second review 3, and declined to ship.** Both would have damaged the artifact under review rather than merely duplicated effort:

- Two reviewers in one worktree both re-synthesize `docs/review_notes/ISSUE-096.md` and both run `record-subject`. The second write lands a second `## Review Subject` block and the gate then refuses `subject-duplicate-block` — "two records cannot both be THE record". The duplicate-block wedge that review 1 found and rework 1 fixed would have been re-created by the pipeline itself, on the PR that exists to fix it.
- Shipping would have run `wt_cleanup.sh` on a worktree a live reviewer is reading, and that is **ISSUE-091's exact mechanism**: the local delete fails while the worktree still holds the branch, the cascade aborts the remote delete, and the remote ref is orphaned. Merging a PR whose blocking review is still executing is the fail-open this sprint exists to remove, arrived at from the orchestration side.
- Both instances pushing to `issue/ISSUE-096-bind-review-diff` invites a non-fast-forward race, and no-force-push leaves no clean recovery.

**Ownership must be resolved before ISSUE-096 advances.** One instance should own the review-3 verdict and the ship decision; this one yields to the instance already holding the review, having completed and verified the rework. If that instance does not return a verdict, the recovery is to re-dispatch review 3 **once**, after confirming no reviewer is live in the worktree and that `docs/review_notes/ISSUE-096.md` carries exactly one subject block.

### Rework 2 verification by this instance — complementary, and not reproducible after the fact

Recorded because two of these checks had to be set up BEFORE the sub-task ran and cannot be re-created from the finished tree:

- **AC-7 non-modification proved against a pre-recorded baseline.** The three protected files' git blob OIDs were captured from `origin/main` *before dispatch* and compared after: `tests/test_review_context.py` `30d7c4ad…`, `tests/test_review_delegation_guard.py` `745a76be…`, `tests/test_subagent_skill_grant.py` `15498a54…` — identical, and all three absent from the diff. A sha256 printed by the agent under review cannot satisfy this check; a pre-recorded OID can.
- **The shrink target was pinned before the rework**, which is what makes "it shrank" checkable: 169229 product bytes / 7 headers at `47ad48b`, 167453 / 9 at `710092c` — 1776 bytes below the bound while absorbing two new files the checkpoint fix required.
- **Module suites re-run by this instance**: 266 passed = 121 (`test_review_subject_binding.py`) + 145 (`test_verify_checkpoint.py`), matching the sub-task's claimed counts exactly; the new per-dimension disarm test was also run in isolation and passes.
- **The High's fix is the per-dimension one**, read from the committed tree rather than the report: `verified = _require_verification(...)` then `if args.dimension not in verified: raise _refuse("verification-missing", …)`, the refusal naming which dimensions *were* verified. `head_ref` and `base_oid` are gone from the payload. The exit-code invariant is now a real check — `(exit_code == 1) != reason.startswith("empty-diff-")` raises `ValueError` — not a docstring claim.
- `docs/review_notes/ISSUE-096.md` is **byte-unchanged** against `47ad48b`: the implementer did not touch the artifact its reviewer judges.
- The red evidence is the part worth keeping: the new test, run against the unfixed code, produced a **fourth independent reproduction** of the High as its own failure message (`echo verified: security reviewed 810 bytes …`, `assert 0 == 2`) while the premise assertion above it confirmed the run file held only `review_delegated_to_code_review`. Eleven tests were red before the fixes.
- Disarm matrix **22 -> 27 mutants, zero survivors**, re-measured on the final tree. M12 now has **two** independent killers — it had one, which is why the vacuous read-back survived rework 1.

### Two items review 3 must weigh, whichever instance renders the verdict

1. **~448 test-file lines changed beyond the named trims.** The sub-task disclosed this rather than letting it pass: the named trims (~195 lines) could not offset what six fixes add, so it also compressed restated narrative and normalised the test module's docstrings. It claims no test, assertion, validation, error path or security control was removed — a claim a shrink constraint actively incentivises, so it must be measured, not accepted. The shrink is only honest if nothing load-bearing paid for it.
2. **The new checkpoint's FAIL direction was never probed on the real tree.** It required transiently removing the subject block from the committed notes, which was prohibited and which the permission system blocked; it is pinned by unit test only. A gate verified in the arm direction alone is precisely the defect this rework exists to remove, so that direction needs a fixture probe.

### Decisions recorded instead of implemented — each needs a carrier

- **The nested-fence defect is NOT fixed** (a 4-backtick fence wrapping a 3-backtick one lets the inner fence re-open the parser, exposing a heading inside an illustration). The fix belongs in `sprint_queue`'s shared fence helper so both consumers inherit it — a shared-contract change for a new caller class, with no AC in this issue. Every wedge case is fail-CLOSED today, so nothing false is ever recorded. **Needs its own issue.**
- **The echo-gate receipt still lives inside the worktree under review**, so anything executing there during a review — including the PR's own tests and hooks — could append a well-formed receipt. Moving it out of tree or binding it with a per-run MAC is a design change with no AC. The docstring's disclosed residual WAS corrected to name the real writer set, which was the finding's own stated minimum. **Needs its own issue.**
- `cmd_emit`'s `Path.cwd()` anchor was left alone and the degradation event fixed in the skill instead (its contract is pinned by ISSUE-066 tests AC-7 forbids touching); refusing the `main-checkout` write was declined because no token in the closed vocabulary fits a legitimate fallback, so the success line now prints where the block went; `KIT_REVIEW_GH_TIMEOUT` was kept and declared as bucket-C surface rather than deleted, because hard-coding that bound would reinstate a defect class this repo already learned (ISSUE-046/047).

## The test-trim claim, MEASURED rather than accepted (team-lead, review 3 iteration)

The rework was given a shrink constraint and its sub-task claimed "nothing load-bearing was removed". That claim is exactly what a numeric target incentivises, so it was measured. **It holds.** The measurement is recorded here because the method matters more than the verdict: a diff reading would not have settled it, and three of the counts that look alarming are artefacts of counting the wrong thing.

Method: set-diff of test FUNCTION NAMES between `47ad48b` and `710092c`, then body-level verification that each removal was absorbed. **84 -> 80 functions: 9 removed, 5 added.** All nine removals are genuine consolidation:

- `test_a_wrong_but_non_empty_echo_is_refused` + `test_the_empty_collection_digest_cannot_satisfy_the_gate` -> both absorbed into one parametrized `test_wrong_echo_is_refused_and_records_nothing`, ids `["bytes", "sha", "received-nothing", "wrong-but-bigger"]`. The replacement is **stronger than the sum of the two**: the ids name the reproduction shapes ("the first four reproductions" and "the FIFTH reproduction (2026-10-31) … a `bytes > 0` check passes this; only the digest rejects it"), and it adds a premise assertion that the echo under test really is wrong, `_no_events`, and a **same-fixture positive control** (correct echo DOES record, exactly 1 event) — the arm and disarm paired in one test, which is what lesson 16 asks for.
- `test_an_unmodelled_exception_becomes_a_named_could_not_compute` -> a strict SUBSET of the surviving parametrized `test_every_subject_subcommand_is_covered_by_the_mapping`. The deleted one raised at the `_pr_refs` seam for `collect` only; the survivor raises at the same seam for **all three** subcommands and asserts exit 2 + empty stdout + `collection-error` + the exception class in stderr. High (a)'s dispatcher pin survived and widened; the only delta is `RuntimeError` vs `OSError`, both equally unmodelled.
- `test_genuinely_empty_pr_refuses_with_its_own_reason` + `test_unreachable_head_oid_refuses_with_a_different_code_and_reason` -> absorbed into a combined construction that asserts the two reasons DIFFER (lines 534-535), plus `empty-diff-unexplained` at 571-572 which carries a **negative** arm (`"reason=empty-diff-head-is-merge-base" not in out.err`). That is the both-directions discipline of review lesson 4, which neither deleted test had.
- `test_an_incomplete_block_is_completed` -> the behaviour it pinned **no longer exists**. The Medium fix replaced complete-the-block with refuse-without-writing, now pinned by the two new `test_an_unterminated_fence_refuses_without_writing` and `test_three_retries_do_not_accumulate_blocks`. Deleting a test whose subject was removed is correct, not loss.
- `test_a_forged_block_is_replaced_by_the_verified_one` -> renamed `test_a_pre_existing_block_is_replaced_by_the_verified_one`.
- `test_decide_still_prints_its_json_and_exits_0` -> was a DUPLICATE of a legacy pin that lives in `tests/test_review_context.py`, which this iteration confirmed **byte-identical to `origin/main`** (empty `git diff --stat`) and which carries 34 test functions with six-plus `decide` sites. The legacy contract is pinned in the file AC-7 forbids touching, which is where review lesson 8 says it belongs.
- `test_the_notes_flag_decoy_is_gone` -> the weakest of the nine and the only one worth a note: `--notes` is now structurally absent from `scripts/review_context.py` (grep: zero hits), so argparse rejects it by construction. An absence-guard asserting a flag does not exist is also the `[record]` class the backlog triage gate now excludes, so its removal is consistent with this repo's own deflation decision rather than a gap.

**Three counts that mislead, recorded so the next reader does not repeat the error.** Function count 84 -> 80 understates coverage badly: the two PR test files collect **266 cases** (`tests/test_review_subject_binding.py` **121**, `tests/test_verify_checkpoint.py` **145**), so parametrization carries most of the weight. A grep for `echo-mismatch` assertion SITES falls 4 -> 2 while the executed cases stay at 4, because the survivor is parametrized. A grep for `collection-error` falls 2 -> 1 while executed cases RISE 2 -> 3. **Count executions, never grep hits or function definitions** — the same rule that applies to a sub-agent's narration.

## The new checkpoint's FAIL direction — already pinned at fixture level

`TestVerifyReviewRequiresTheSubjectBinding` in `tests/test_verify_checkpoint.py` collects **8** cases, and the refusal path is among them rather than missing: `test_fail_when_a_receipt_exists_but_the_block_does_not`, `test_fail_loudly_when_the_receipt_cannot_be_read`, `test_fail_loudly_when_review_context_cannot_be_imported`, `test_fail_when_the_notes_carry_two_blocks`, against `test_pass_when_a_receipt_exists_and_so_does_the_block`.

This also **measures the disclosed residual** rather than leaving it a claim: `test_pass_without_the_block_when_no_receipt_triggers_it` is parametrized `[no-run-file]` / `[no-runs-dir]` / `[other-issue]`, so the three inputs that suppress the trigger are pinned as intended behaviour. The residual is therefore a **tested design limit, not an unclosed gap** — which caps its severity. The open question that remains is only whether a stronger trigger exists in existing surface (`decide` already knows which dimensions it routed `delegated`), and that is a follow-up carrier at most, not a blocker.

What is still owed is the **real-consumer** probe: every one of those 8 cases is a fixture, and lesson 16 asks for the defence through its real consumer. Team-lead will run `checkpoint.sh --skill review --phase review --issue ISSUE-096` against the LIVE worktree in both directions (block present -> expect 0; block withheld with the real receipt in place -> expect non-zero), with a checksum taken before and after so the restore is proven byte-exact. Sequenced AFTER the reviewer finishes writing the notes, because two writers in that worktree would land a second `## Review Subject` block and wedge the gate on `subject-duplicate-block` — re-creating, on the PR that fixes it, the exact wedge review 1 found.

## Concurrency note — sole ownership of the worktree established

The rework-2 team-lead was still alive when review 3 was dispatched (`ListAgents` had reported it completed; it had not). It detected the overlap by measurement — digests it never computed, its own progress row rewritten to `reviewing`, fresh gate writes in the worktree run file — and yielded rather than duplicating. Recorded because the reasoning generalises: concurrent `record-subject` calls are not merely wasteful, they are **wedging**, so the worktree has exactly one writer at a time by construction and not by convention.

## Baseline figures: the orchestrator-supplied number was wrong a THIRD time

The dispatch brief for this iteration quoted 2501 passed. Main measured **2504 passed, 1 skipped** at both `778ccc7` and `fa9daad`. Team-lead re-measures on main before the merge rather than carrying any quoted figure, and deliberately did NOT run main's suite while the reviewer held the worktree: several kit tests drive real-repo worktree operations, so a concurrent run risks damaging the tree under review — a false failure would cost more than the wall time saved.

## Carriers still unfiled, with their id allocation resolved

`issues.md` allocates by next-free-number and the max id is **ISSUE-106**, so the two deliberately-unfiled carriers take **ISSUE-107** and **ISSUE-108**: the nested-fence Medium (a 4-backtick fence wrapping a 3-backtick fence re-opens the parser; its fix belongs in `sprint_queue`'s shared helper so both consumers inherit it, which is a shared-contract change with no AC in ISSUE-096) and the receipt-in-worktree Low. They are filed by team-lead in ONE batch after the review verdict, not now — the nested-fence item's priority depends on what review 3 concludes, and a single batched write avoids repeated `issues.md` churn under the lock. The `planner` agent has no `Bash` in this environment, so its content is applied by team-lead under `registry_edit.sh` as usual.

## Review attempt 3 — ISSUE-096 / PR #147 at `710092c` — PASS, no High remains

**All 12 review checkpoints exit 0** (`checkout`, the five UI phases auto-skipping correctly for `UI: false`, `test`, `test-quality` over 74 files, `debt` advisory, **`review`**, `push`). **No Critical, no High. Two Mediums, twelve Lows.** The predecessor's escalation condition is therefore NOT met, and ISSUE-096 ships.

**The reviewer's digests match team-lead's independent measurements byte-for-byte** — full **200322 / 10 / `e75fc65b5ab832df…`**, product-only **167453 / 9 / `4c73e35a0bbe40c7…`**. Neither party was given the other's numbers, which is the only form of agreement that means anything here: two independent collections of the same subject, rather than one party echoing a figure the other printed. That is lesson 6's distinction applied to the review process itself.

**The remaining High is closed, established by MUTATION rather than by reading.** Arm: with the run file `chmod 0444` (readable, un-appendable) and only the code receipt present, `delegate(security)` exits 2 with `reason=verification-missing` naming `verified there: code`. Disarm, two independent mutants, both killed by `test_delegate_refuses_when_only_another_dimension_was_recorded` — reverting the membership test to truthiness (`if not verified:`) fails with the vacuous pass printed verbatim (`echo verified: security reviewed 810 bytes … assert 0 == 2`), and dropping the `event_type` comparison inside `_verified_dimensions` fails identically. Caveat recorded rather than glossed: fix and test landed in one commit, so **committed history cannot establish test-first/red-observed** — the mutation result substitutes for it and is the stronger evidence anyway.

**The three earlier Highs hold.** Exit 1 is reachable only from the two computed-empty constructions, both reason-tagged (`empty-diff-head-is-merge-base`, `empty-diff-unexplained`); everything else lands at exit 2 with a named reason (`gh-unavailable`, `git-unavailable`, `worktree-path-missing`, `base-ref-unresolvable`, `head-oid-unreachable`, `gh-bad-output`, `collection-error`), and a broken pipe exits 120 rather than 1.

### The real-consumer probe team-lead owed — run, and conclusive

Every one of the eight new `TestVerifyReviewRequiresTheSubjectBinding` cases is a fixture, and lesson 16 asks for the defence through its real consumer. Team-lead ran it against the LIVE tree via `checkpoint.sh`, with both files checksummed before and after:

1. no receipt, no block -> **exit 0** (the trigger legitimately does not fire)
2. a VALID-shaped receipt planted (real head oid, bytes and digest), 0 blocks -> **exit 1**, printing the exact remediation command
3. run file restored, **both checksums byte-identical to baseline** (`9b6f6e7c…` / `a9996137…`)
4. re-run -> **exit 0**

So the refusal path works through the real consumer on the real tree, not only in fixtures. The eighth-observation risk is retired by measurement rather than argued away.

### This review ran fully DEGRADED, and that is the honest result

`decide` returned `degraded` / `context-unreachable` for **both** dimensions: the reviewing context had neither a `Skill` nor a `SlashCommand` tool, which is ISSUE-072's "a grant does not imply provisioning" observed again. Two `review_degraded_path_used` events were written and **no delegation receipt exists**, so step 5.3 was correctly skipped and the notes carry **zero** `## Review Subject` blocks — by design, not by omission. The reviewer declined to manufacture a receipt to produce the expected shape, which is exactly right: a forged attestation used to satisfy this gate is the defect ISSUE-096 exists to prevent.

Two consequences worth carrying forward. **This is NOT reproduction #7** — the runtime `/security-review` was unreachable, so its target-discard behaviour was neither reproduced nor refuted; the count stays at six. And **the PR that binds the delegated review could not exercise its own binding on its own final review**, because the binding only engages on the delegated path. Review 2 did reach that path; review 3 did not. On the degraded path the apparatus is inert, so a degraded review's notes are identically shaped whether or not the reviewer read the diff — recorded in the notes as a `[note]` finding carrying the reviewer's independently measured digest, which is the available substitute.

### Suite

Worktree **2615 passed, 1 skipped, 0 failed**. Delta decomposed with `--collect-only` rather than by totals: 2616 worktree vs 2505 main = **+121** (new `test_review_subject_binding.py`) **+8** (`test_verify_checkpoint.py`, 145 vs 137) **−18** (`test_sprint_queue.py`, 189 vs 207 — main carries 10 untracked archive files to the worktree's 4, times three parametrized tests), reconciling exactly. The one skip is environmental and pre-existing (`tests/test_kit_telemetry.py`, mknod of a character device not permitted). **ISSUE-099 did not bite.** Team-lead re-measured main independently at `f80b077`: **2504 passed, 1 skipped** — confirming 2504/1 for the third time and the brief's 2501 wrong for the third time.

### Two reviewer claims checked against the tree; one was wrong

Narration is not evidence, so the two load-bearing artifact claims were re-measured. "Zero username leaks" is **correct** — the single `/Users/` hit in the new notes is a deliberately redacted `/Users/<username>/…` inside the very finding about publishing that identifier, and the reviewer said so explicitly. But "`docs/sprint_state.md` is untracked" is **false**: `git ls-files --error-unmatch` resolves it. The reviewer's conclusion survives its wrong reason — a carrier in sprint_state is still not durable, because the file is archived and reset at each sprint boundary — but the reason is corrected here so it is not inherited.

The stale block committed at `47ad48b` published an absolute `/Users/<account>` path and attested to the previous head; the synthesizer rewrote the file wholesale and the review-3 notes were committed and pushed fast-forward `710092c..0c380f6` (no force). The committed artifact now carries **0** real-username leaks, verified after the push.

## ISSUE-096 SHIPPED — squash `f3d4ed6`, PR #147 merged, GH issue #146 closed

**All four ship checkpoints exit 0** (`checks`, `merge`, `cleanup`, `smoke` — the last with its blocking unit gate at 73.7s). Nothing was taken on narration; each step was cross-checked against an independent oracle.

- **Pre-merge probe cross-checked, per ISSUE-077.** `ship-merge-decision --pr 147` (bare number) returned `{"action": "merge", "reason": "PR 147 not merged (state=open)"}` and `gh pr view` independently reported `OPEN` / not-draft with `headRefOid` **equal to the local branch tip** — so no wrong-target ref could have forged a MERGED. After the merge the same probe returns `{"action": "skip"}`, which exercises the **ISSUE-052 idempotency guard on the live PR** rather than in a fixture.
- **CI verified against the head that actually merged**, not against the PR's latest-run summary: `gh api repos/.../commits/0c380f6/check-runs` shows `test (3.11)` and `test (3.12)` both `completed/success`. Mergeability was `UNKNOWN` immediately after the push (GitHub still recomputing) and was re-polled to `MERGEABLE`/`CLEAN` **before** merging rather than merged through the ambiguity.
- **ISSUE-091 avoided by sequencing, not by luck.** `--delete-branch` was deliberately NOT used: its documented mechanism is that a local delete fails while a worktree still holds the branch, and that cascade aborts the remote delete and orphans the remote ref. Instead: worktree cleanup, then explicit local delete, then explicit remote delete, then an orphan check. `git ls-remote --heads origin | grep ISSUE-096` returns **nothing** and no local ref survives. The local delete reported "not found" because cleanup had already removed it — which is exactly the half of the cascade that would have aborted the remote half.
- **Smoke on main: 2633 passed, 1 skipped**, and it decomposes exactly against the independently measured baseline — 2504 + 121 (`test_review_subject_binding.py`) + 8 (new `test_verify_checkpoint.py` cases) = **2633**. No failures; **ISSUE-099 did not bite** on main either. The single skip is the pre-existing environmental one (mknod of a character device not permitted).
- **ISSUE-105 did not bite, because it was guarded for.** `Status: done` was written only AFTER the squash landed and `gh pr view` reported `MERGED`; at no point was it set while the PR was open. The implement skill's step 12 still contradicts the team-lead contract, so the hazard is unchanged for the next issue — ISSUE-105 remains the carrier.
- **Registry writes were team-lead's own work under the lock**, via `registry_edit.sh` with commit messages passed as files (`git commit -F`), never inline. `issues.md`: ISSUE-096 `Status: done` plus its backlog `[x]`. `CHANGELOG.md`: one `### Added` entry under Unreleased recording the provenance distinction, the exit-1 split, the point-of-use enforcement, bucket C, and the disclosed degraded-path residual.

## The three deferred findings now have durable carriers — ISSUE-107, ISSUE-108, ISSUE-109

Filed in ONE batched write under the lock. The `planner` agent drafted all three as text and wrote nothing — the **sixth** observation that it has no `Bash` tool in this environment, and the sixth time the contract held because the dispatch assumed the absence rather than discovering it. Team-lead applied the content. **`validate_issues.py`: 15 violations before, 15 after — zero new**, and none of the three new blocks is named in any violation.

- **ISSUE-107 (P1)** — the review-subject checkpoint's trigger set is strictly LARGER than its satisfiable set. `_review_subject_bound` fires on any `review_delegated_to_*` receipt for the issue, but `record-subject` is satisfied only by one carrying matching `head_oid`/`diff_sha256`/`diff_bytes`. The legacy pre-096 emit path writes one with none of them at exit 0, so the checkpoint demands `record-subject` and `record-subject` refuses at exit 2, with step 5 forbidding the hand-edit that would escape it — a **wedged blocking gate**. It fails CLOSED, which is why review 3 rated it Medium and not High, but it is the wedge class that cost ISSUE-081 four review cycles. Root cause is review lesson 8: the new gate's trigger fires on the legacy caller class it was never meant to govern, and both new tests plant a subject-bearing payload, so the gap is untested in exactly the arm that matters. ISSUE-096's AC-7 forbade touching `tests/test_review_context.py`, which is *why* the legacy path survived — so 107 explicitly owns that interaction.
- **ISSUE-108 (P2)** — step 3.1's `$WT/` emit anchor is prose-only (`STEP_31_REQUIREMENTS` mutation-tests nine obligations including the `KIT_RUN_ID=` literal but has no entry for the anchor), and from the main checkout the degradation emit exits 0 while landing the event in the WRONG run file, split from the receipts. Plus the trimmed "stderr names `reason=` and its remedy" claim, measured **false for 10 of 25 tokens**. Notably, 108 explicitly DECLINES the documentation-lint fix: this repo decided that class manufactures triage work, so either the message carries its remedy or the prose stops promising one.
- **ISSUE-109 (P2)** — the nested-fence defect, carried to the shared `sprint_queue` helper both consumers inherit, with lesson 4's both-directions mutation requirement written into its ACs so widening the detector cannot buy the nested case by breaking the single-fence case.

Lows deliberately NOT filed, recorded so the omission is a decision rather than a leak: the `--notes` absence-guard deletion (an absence guard for a flag that no longer exists is the `[record]` class this repo just voted out of its backlog), and the `pytest-timeout` gap whereby an `O_NONBLOCK` regression surfaces only as a CI hang. The second is a real detectability gap and is the one most likely to deserve a carrier later; it is named here rather than filed because sprint_state is not durable across sprint boundaries — if it matters, it needs an id.

## Iteration close

ISSUE-096 is **done**. ISSUE-102 and ISSUE-103 were NOT touched: still `backlog`, Attempts 0, exactly as handed over — the brief reserved them for the orchestrator's next dispatch. `KIT_SPRINT_DISPATCH_ABOVE_WATERMARK` was never set, and ISSUE-107/108/109 are all above the pinned mark, so filing them cannot widen this sprint's dispatch set.

## Iteration 2 — ISSUE-103 + ISSUE-102 dispatched (2026-11-03)

### Sole ownership established by measurement BEFORE any dispatch

The previous iteration's concurrency damage (two team-leads on ISSUE-096, both re-synthesizing notes, both running `record-subject`, wedging the gate on `subject-duplicate-block`) was checked for rather than assumed away:

- `git worktree list` carries exactly two entries — the main checkout at `ce44206` and the stale pre-sprint `.worktrees/issue-ISSUE-081-gate-evidence` at `6aeaf3d` (ISSUE-081 is held; left alone, as the previous iteration also decided). **No worktree exists for either target issue.**
- No local branch and **no remote branch** matches `102` or `103` (`git ls-remote --heads origin` returns nothing for either). The one `remotes/pr/102` ref is a GitHub PR-head fetch ref for an unrelated old PR number, not a branch for this issue.
- `docs/sprint_state.md` is at its ISSUE-096-close content with no writes from another party.

If another writer appears on either worktree or on this file, the rule is stop and report, not race.

### Baseline MEASURED on main at `ce44206`, not inherited

`uv run --extra dev pytest -q` = **2633 passed, 1 skipped in 68.22s**; `--collect-only` = **2634 collected**. The brief's quoted 2633 is **correct this time** — recorded explicitly because the orchestrator-supplied figure was wrong three times in the previous iteration, so "the brief was right" is itself a measurement worth pinning rather than an assumption to carry forward.

Measured **before** dispatching any worktree work, deliberately: several kit tests drive real-repo worktree operations, so running main's suite while implement sub-tasks hold live worktrees risks a false failure or damage to a tree under review.

Per-file collection counts captured now so later deltas are decomposable by set rather than by total:

| file | main collects |
|------|---------------|
| `tests/test_sprint_queue.py` | 207 |
| `tests/test_verify_checkpoint.py` | 145 |
| `tests/test_spec_gate.py` | 20 |

**Predicted worktree baseline: 2616 collected / 2615 passed / 1 skipped.** The gap is arithmetic, not mystery: 10 `docs/sprint_state.archive-*.md` files sit on disk in the main checkout but only **4 are tracked** (`2026-10-10-retro`, `2026-10-11-failopen`, `2026-10-11-integrity`, `2026-10-31-issue088`), and `test_sprint_queue.py` parametrizes three tests over them — 6 untracked archives x 3 tests = **−18**. This reproduces the previous iteration's 207-vs-189 observation exactly and from first principles. Any sub-task reporting a worktree total near 2615 is consistent; totals must never be compared across checkouts.

### Both defect sites read from the committed tree by team-lead before dispatch

Neither issue's premise was taken from its own filing text:

- **ISSUE-103.** `verify_implement_red` (`scripts/verify_checkpoint.py:619`) already computes the branch's own test-file delta — `_existing(wt_path, _changed_files_vs_base(wt_path, base))` at line 636 — and uses it for the file-existence and hollow-assertion checks. It then **discards that scoping** and runs bare `python3 -m pytest -q --tb=short` over the whole worktree in all three branches (JS, Python, fallback), treating any non-zero exit as `PASS: RED phase — tests fail as expected (exit N)`. So the defect is precisely as filed, and the Implementation Note is correct that the scoping input already exists one screen above the run — this is a plumbing fix, not a new oracle. The existing hazard note is a **three-line inline comment at 657-660** covering only the JS-mis-run/exit-5 route; AC-4's "hazard note" is that comment plus the docstring at 620-624.
- **ISSUE-102.** `spec_path_exists` (`scripts/spec_gate.py:88-92`) is three lines: `none`-guard, then `(issues_md_dir / spec_path).resolve().exists()`. Single resolution root, exactly as filed. The module is 218 lines, so the blast radius is small and `decide()` at line 94 is the only consumer.

### Dispatch plan

Two `developer` sub-tasks at `opus`, in **parallel worktrees** (the issues touch disjoint files — `verify_checkpoint.py`'s red phase vs `spec_gate.py`), then **serial ship in the mandated order ISSUE-103 -> ISSUE-102**. Review lesson 8 is the governing lesson for both and was passed verbatim into both prompts, together with lesson 16 and the two aphorisms about computed-vs-uncomputable subjects and disclosed residuals being claims.

Each prompt carries the hazards as hard constraints rather than as context: `Status: done` is team-lead's to write after MERGED (ISSUE-105); no `--delete-branch` (ISSUE-091); registry writes are team-lead's own under `registry_edit.sh`; expect the review to run degraded with `context-unreachable` and do not forge a receipt to produce an expected shape (ISSUE-096 residual / ISSUE-106); do not chase a single environmental worktree failure (ISSUE-099).

### Pre-registered predictions and pre-recorded baselines (written BEFORE either sub-task reported)

Recorded here in advance deliberately: ISSUE-096 established that two of its strongest verification checks had to be set up before the sub-task ran and could not be re-created from the finished tree. A prediction written after the result is a rationalisation; these are written before.

**Pre-recorded, not reconstructable later:**
- main HEAD `ce4420666baf2128c0a63f204b1a4073031a3bee`.
- Registry sha256 BEFORE any sub-task write: `issues.md` `fb6fb3bf21e01d3d…`, `CHANGELOG.md` `385781b40c05eca1…`.
- `validate_issues.py issues.md` BEFORE: **15 violations**, and **neither ISSUE-102 nor ISSUE-103 is named in any of them**. So any violation naming either issue after the implements is new and attributable, and the total must return to 15.
- Blob OIDs of files these fixes must NOT touch: `tests/conftest.py` `4da52d00…` (ISSUE-094's territory), `scripts/sprint_queue.py` `237fd3d5…` (ISSUE-109's), `scripts/review_context.py` `1bd08b1d…`, `tests/test_review_context.py` `30d7c4ad…` (ISSUE-096 AC-7's protected file, unchanged since). A sha256 printed by the agent under review cannot satisfy this check; a pre-recorded OID can.
- Blob OIDs of the target files BEFORE: `scripts/verify_checkpoint.py` `9d958070…`, `scripts/spec_gate.py` `05e9f334…`, `tests/test_verify_checkpoint.py` `4776d0af…`, `tests/test_spec_gate.py` `9e58137c…`, `skills/implement/SKILL.md` `c3e24a5d…`.

**Prediction 1 (ISSUE-103) — scoping can CREATE the exit-5 fake-RED the hazard note already names.** Read from the committed tree: `_changed_files_vs_base` returns a set of **file paths** (committed + staged + unstaged + **untracked**), and `_existing` filters to paths present in the worktree. The red verifier's `test_dir_pattern` is `(?:^|/)(?:tests?|__tests__)/` over `.py`, so a modified **`tests/conftest.py` is itself a member of `all_test_files`**. Therefore if the fix scopes the pytest invocation to the branch's changed test files, a branch whose only test-file change is `conftest.py` — or any changed test file that collects zero cases — yields **pytest exit 5 (no tests collected)**, which is non-zero, which today's inverted logic reports as `PASS: RED phase — tests fail as expected (exit 5)`. That is the exact fake-RED route the existing hazard comment at lines 657-660 was written for, **re-reachable through the new scoped path**. A fix that scopes the run without special-casing exit 5 has moved the fail-open rather than closed it. This is also precisely the "computed and empty vs could not compute" aphorism: "the branch's tests ran and failed" and "the branch's tests collected nothing" must not share an exit code or a message. **I will check this specifically and will not accept a report that is silent on it.**

**Prediction 2 (ISSUE-103) — the file-path unit cannot see "failed for the right reason".** A changed test file that fails only because an unrelated module it imports is broken attributes cleanly to the branch and certifies RED. Scoping to the branch's own files tightens the gate from "any suite failure" to "any failure in the branch's test files", which is a real and worthwhile tightening, but it is not "the new test fails because the implementation is absent". The honest claim is the former. Also: running a subset changes which fixtures and plugins load, so a scoped run is not a projection of the full run — and untracked files are in the set, so a stray untracked test file in the worktree enters the scope.

**Prediction 3 (ISSUE-102) — the issue's own one-line diagnosis is INCOMPLETE, and widening the path roots alone cannot satisfy AC-1.** The issue calls `scripts/spec_gate.py:92` "the one-line diagnosis". Traced through `decide()` (line 94) myself, it is not sufficient for the worktree direction:

`decide` computes `spec_present = spec_path_exists(issue["spec_path"], issues_md_dir)`, and `spec_path_exists` returns **False immediately** when the value is empty or `none`. Run from the worktree, `--issues-md issues.md` resolves to the **branch's frozen copy**, whose `Spec:` field reads `none` — so the gate never reaches a path resolution at all. The blocker from the worktree side is the **FIELD**, not the PATH. Widening the roots fixes only the main-checkout direction (field present, file on branch); from the worktree the field itself is unreadable, so AC-1's "both locations asserted" half would still fail.

The coherent fix therefore has to resolve the **registry** to the main checkout (per the kit's own Shared-Registry rule, which is explicitly out of scope to change and so must be worked with) while resolving the **SPEC file** against the branch worktree — two different roots for two different artifacts, which is exactly why one root was never going to be enough.

**This makes Prediction 3 a falsifiable test of the report rather than of the code.** If the sub-task reports AC-1 passing from the worktree while having changed only `spec_path_exists`'s resolution root, the claim is false and I will catch it. If it reports the field/path split, it genuinely traced the defect rather than implementing the issue's summary. Either way the measurement is mine, taken from both CWDs. Recorded now so the check cannot be retrofitted.

### Prediction 3 CONFIRMED BY EXECUTION — ISSUE-102's "one-line diagnosis" is wrong about which line

Measured by team-lead on main at `ce44206` with a scratchpad fixture, independently of the implement sub-task and before it reported. Three runs of the real `scripts/spec_gate.py` CLI against a synthetic `ISSUE-900` (`Spec-Required: true`):

| # | configuration | decision | reason / evidence |
|---|---------------|----------|-------------------|
| A | `Spec: docs/specs/SPEC-900.md` set, file ABSENT | `auto_spec` | "Spec-Required=true, SPEC missing, sprint mode → auto-run /spec" |
| B | **co-located** — field set, file present in the same tree | **`proceed`** | "Spec-Required=true and SPEC exists at docs/specs/SPEC-900.md" |
| C | **worktree direction** — field frozen to `none`, SPEC file present | `auto_spec` | same reason string, and the payload carries **`"spec_path": "none"`** |

**B vindicates the issue's claim that the decision logic is sound** and only resolution is at fault — the co-located control really does return `proceed`, so there is a satisfiable configuration and the table is not broken.

**C falsifies the issue's framing of its own fix.** The issue calls `scripts/spec_gate.py:92` "the one-line diagnosis", and line 92 is the path resolution inside `spec_path_exists`. But run C never reaches line 92: `spec_path_exists` returns False at its **`none`-guard** (line ~90), two lines earlier, and the emitted `"spec_path": "none"` is the proof it never had a path to resolve. From the worktree the branch's frozen `issues.md` reads `Spec: none`, so the blocker is the **FIELD, not the PATH**.

Consequence, stated as a falsifiable claim about the work rather than about the code: **widening the resolution roots is sufficient for the main-checkout half of AC-1 and cannot satisfy the worktree half.** AC-1 demands `proceed` from both locations and was written that way precisely because "the defect was invisible from either one alone" — and the same is true of the fix. The coherent repair resolves the **registry** to the main checkout (honouring the Shared-Registry rule, which is out of scope to change and so must be worked with) while resolving the **SPEC file** against the branch worktree: two roots for two artifacts, which is why one root was never going to be enough.

So any report claiming AC-1 green from the worktree while having changed only `spec_path_exists`'s resolution root is making a false claim, and this table is what detects it. Recorded before the report arrived.

## Both implements landed — verified by team-lead's own measurement, not by reading the reports

| | ISSUE-103 | ISSUE-102 |
|---|---|---|
| branch tip | `7a8c14551b4e5af3718ed80c087f6fe3a71e9261` | `a01e416a333d09e2f7d107c1bd08d6596f9e1a8d` |
| local == origin | yes | yes |
| worktree `status --porcelain` | empty | empty (`--untracked-files=all`) |
| GH issue / PR | #149 / **#150** | #148 / **#151** |
| diff | `scripts/verify_checkpoint.py` +113/−30, `tests/test_red_gate_scoping.py` +509 | `scripts/spec_gate.py` +311, `tests/test_spec_gate.py` +567, `skills/implement/SKILL.md` +3, `.tmpl` +3 |
| registry | `Status: doing`, PR present | `Status: doing`, PR present |

**Independently re-verified, not accepted on narration:**
- The four pre-recorded protected blob OIDs are **byte-identical** on `origin/main` after both implements: `tests/conftest.py` `4da52d00…`, `scripts/sprint_queue.py` `237fd3d5…`, `scripts/review_context.py` `1bd08b1d…`, `tests/test_review_context.py` `30d7c4ad…`. The pre-recording is what makes this check real.
- `validate_issues.py issues.md` → still **15 violations**, and **neither ISSUE-102 nor ISSUE-103 is named in any of them**. Matches the pre-recorded baseline exactly; zero new.
- Collection counts re-measured by team-lead in each worktree: `tests/test_red_gate_scoping.py` **23**, `tests/test_verify_checkpoint.py` **145 (unchanged)**, `tests/test_spec_gate.py` **60** (was 20). All three match the reports.
- **ISSUE-105 did not bite on either issue.** Both registries read `Status: doing` with an open PR. Both dispatches overrode step 12 explicitly, so the contract held because the defect was assumed rather than discovered — the same shape as the ISSUE-074 counter-instance. Nothing had to be reverted under the lock. ISSUE-105 remains the carrier; the hazard is unchanged for the next issue.
- **No new env knobs.** `KIT_CHECKPOINT_TEST_TIMEOUT`, which ISSUE-103's harness uses, is pre-existing ISSUE-046/047 surface already documented in `README.md`, `docs/troubleshooting.md` and `docs/test_plan.md`; `git diff` adds no `getenv`/`environ` line in `scripts/`. **Review lesson 2 owes nothing on either PR** — checked rather than presumed.
- **ISSUE-102's generated-file handling is correct and drift-free.** `skills/implement/SKILL.md` is generated (`AUTO-GENERATED by scripts/gen_skills.py … Edit SKILL.md.tmpl instead`); the sub-task edited the template and regenerated. Team-lead re-ran `gen_skills.py` for real inside the worktree: `git status --porcelain` came back **empty**, so the committed `.md` is byte-identical to what the committed `.tmpl` produces. Only the implement skill's output moved; the other 19 are untouched.

### ISSUE-103's real-consumer probe — reproduced independently, on a tree team-lead built

The sub-task's central claim is AC-1's "both numbers". Rather than read its probe, team-lead built a separate throwaway repo (own issue ids, own paths) where the branch's test **passes** and an unrelated pre-existing test **fails**, then drove the same real consumer twice:

```
----- MAIN (unfixed) — the defect -----
PASS: RED phase — tests fail as expected (exit 1)
exit=0
----- BRANCH (fixed) — the repair -----
FAIL: RED phase — tests passed but should fail before implementation.
  The branch's own tests all passed: tests/test_branch_feature.py
  TDD requires: write failing tests first, then implement to make them pass.
  An unrelated failure elsewhere in the suite no longer certifies RED (ISSUE-103).
exit=1
```

Byte-identical to the sub-task's reported output, from a tree it never saw. That is the ISSUE-096 form of agreement — two independent constructions of the same subject, neither party echoing the other's figure. AC-3 re-measured on team-lead's own tree too: branch red **and** unrelated red → `exit=0`, `failing: tests/test_branch_feature.py`. No over-refusal.

Also confirmed: `TestRedScopeRealConsumer` genuinely shells out to `bash <kit>/scripts/checkpoint.sh` as a subprocess against real git worktrees (4 invocation sites read from the source), so the class earns its name rather than asserting at a helper. Its disarm case additionally asserts the unrelated test's path is **absent** from the output, pinning that the verdict was not decided by the unrelated failure.

### PREDICTION 1 — confirmed, but my guessed construction was WRONG, and the correction matters

Recorded as a correction to team-lead's own pre-registered prediction, because a prediction that gets quietly reinterpreted to match the result is worthless.

I predicted the scoped run would re-create the exit-5 fake-RED via a **`tests/conftest.py`-only** change. Measured through the real consumer, that construction **never reaches the run**: both main and the branch refuse it upstream at the pre-existing hollow-assertion check (`FAIL: test files have no real assertions: tests/conftest.py`, exit 1). A second attempt — a changed test file containing a real `assert` inside a non-test helper, so `_has_real_tests` would be satisfied while pytest collects nothing — was **also** refused upstream by the same check. `_has_real_tests` is stricter than "contains an assert".

The route is nonetheless live, via a construction I had not considered: a genuinely collectable failing test that the **project's own `addopts` deselect** (`-m "not slow"`).

```
=== pytest alone on that scope ===  1 deselected  ->  pytest exit=5
----- MAIN (unfixed) -----
PASS: RED phase — tests fail as expected (exit 1)
exit=0
----- BRANCH (fixed) -----
FAIL: RED phase — pytest evaluated none of the branch's own tests (exit 5: nothing collected / usage error) — inconclusive, cannot verify genuine RED
  Scope was: tests/test_branch_feature.py
exit=1
```

So: **the guard is load-bearing on the real path and is not fixture-only surface** — main certifies this branch as RED off an unrelated failure at exit 0, while the branch refuses it as inconclusive. And the "computed and empty vs could not compute" distinction is delivered at the real consumer, with three outcomes carrying three different messages: branch tests failed (PASS, exit 0), branch tests all passed (FAIL, exit 1), branch tests not evaluated at all (FAIL inconclusive, exit 1, naming the scope).

This is a **stronger** result than the sub-task's own evidence, which measured exit 5 at the pytest level only. The honest summary is that my prediction was right about the hazard class and wrong about its entry point, and the fix covers the entry point that actually exists.

### Severity CORRECTION on ISSUE-102's reported High — measured down to Medium

The sub-task rated its `validate_issues.py` finding **High** on the grounds that the same single-root resolution "feeds a CI gate". The defect itself is real and team-lead confirmed it by reading the committed code: `_spec_path_satisfied` (`scripts/validate_issues.py:87-98`) carries the identical `(issues_md_dir / spec_path).resolve().exists()` assumption, uses `.exists()` so a **directory** satisfies it, and is invoked at `:146-155`; `.github/workflows/ci.yml:39` does run it.

But the premise that it gates anything is false, and the measurement is one command:

```
validate_issues exit code with 15 violations present = 0
```

`main()` prints `Found 15 violation(s):` and returns **0**. Violations are a warning stream that **cannot fail CI**, so this defect produces noise rather than the wedge ISSUE-102 itself produced. **Recorded as Medium, not High** — the previous iteration preserved a higher upstream severity when two of three passes rated a finding lower, and the same discipline cuts the other way here: severity follows the measurement, in whichever direction it points.

**A separate observation falls out of that measurement, and it is ISSUE-104's species at a third control.** ISSUE-104 Route 1 is "CI runs the validator in a mode that cannot fail" for `validate_spec.py` at `ci.yml:45`. `validate_issues.py` at `ci.yml:39` has the same shape — it calls its findings "violations" and exits 0 regardless. ISSUE-104 names only `validate_spec.py`, so this is **uncovered** by any existing carrier. Stated with its caveat rather than overclaimed: the 15 standing findings are all style-level ("AC #N not in Given/When/Then format"), so advisory-by-design is a defensible reading — the defect, if it is one, is that the word "violation" and the exit code disagree. Needs a carrier to be real.

### Review subjects measured by team-lead BEFORE the reviewers reported, so agreement can be checked

Both reviewers were dispatched with **no digests and no suite totals** — the predecessor issue established that a pasted figure is the one remaining way past the subject gate, so agreement only means something when both parties measure independently. Team-lead's figures, taken from the committed tree against the merge-base:

| issue | range | full diff | product diff (excl. `docs/review_notes/*`) |
|---|---|---|---|
| ISSUE-103 | `ce44206..7a8c145` | **31090 bytes / 2 headers / sha256 `2e5f756073f40c21…`** | identical (no notes committed yet) |
| ISSUE-102 | `ce44206..a01e416` | **45707 bytes / 4 headers / sha256 `7bc58048288921c5…`** | identical (no notes committed yet) |

Full and product coincide at this point because neither reviewer has committed its notes artifact; once they do, the full figure will exceed the product figure, exactly as it did on the predecessor issue at `47ad48b`. Recorded so that divergence is expected rather than alarming.

### Both PRs verified independently against the live GitHub state

| | PR #150 (ISSUE-103) | PR #151 (ISSUE-102) |
|---|---|---|
| state / draft | `OPEN` / not draft | `OPEN` / not draft |
| mergeable / mergeState | `MERGEABLE` / `CLEAN` | `MERGEABLE` / `CLEAN` |
| base | `main` | `main` |
| `headRefOid` == local tip | yes (`7a8c1455…`) | yes (`a01e416a…`) |

`headRefOid` is cross-checked against the local branch tip per **ISSUE-077**, which is open — so the bare PR number passed to `ship-merge-decision` is validated against an independent oracle rather than trusted. Both merge-bases are `ce44206`, i.e. current main, so neither branch is stale.

### The mandated serial ship order cannot conflict — measured, not assumed

`comm -12` over the two branches' changed-file sets returns **empty**: ISSUE-103 touches `scripts/verify_checkpoint.py` + `tests/test_red_gate_scoping.py`; ISSUE-102 touches `scripts/spec_gate.py` + `tests/test_spec_gate.py` + `skills/implement/SKILL.md` + its `.tmpl`. **Disjoint.** So shipping ISSUE-103 first leaves ISSUE-102 one commit behind main with no overlapping file, and the second merge stays clean without any rebase. The no-force-push conflict policy therefore has nothing to resolve — recorded because "they touch different files" was an assumption in the dispatch brief and is now a measurement.

One ordering consequence worth noting: once ISSUE-103 merges, any later `implement/red` checkpoint run from main's scripts uses the **new scoped** verifier. ISSUE-102's red checkpoint already ran against the old one, so nothing retroactively changes — but if ISSUE-102 needed a rework after 103 lands, its re-run would be governed by the new logic. Not a problem, and not a surprise if it happens.

## Review attempt 1 — ISSUE-102 / PR #151 — all 12 checkpoints PASS, verdict REWORK on a named set of 2

All twelve review checkpoints exited **0**, with the five UI phases auto-skipping correctly for `UI: false` (confirmed by their literal skip messages, not assumed). Worktree **2655 passed, 1 skipped**; the reviewer's per-file decomposition (`test_spec_gate.py` 20→60, `test_sprint_queue.py` 207→189, net +22) reconciles exactly against team-lead's independently measured main figures, and **no ISSUE-099 failure appeared**. The review ran fully **degraded**, both dimensions `context-unreachable` (ISSUE-082, as predicted); no runtime skill was reachable, so no echo was fabricated, `record-subject` was correctly skipped, and the notes carry **zero** `## Review Subject` blocks by design. The reviewer declined to forge a receipt to produce the expected shape — the right call, and the thing this apparatus exists to protect.

Two pieces of the review are worth more than the verdict, because both were measured rather than asserted:

- **The nine legacy pins were anchored to the real oracle.** The reviewer executed `origin/main`'s own `spec_gate.py` on equivalent fixtures and diffed against the literals embedded in the PR's tests — **all nine matched, zero mis-transcriptions**. That is the right technique: an embedded literal is only as good as its provenance.
- **The relaxation's scoping was proved with a logging `git` shim**, not by reading the claim: `bypassed` (both modes), signals-only `proceed`, and non-sprint `hold`-by-signal each made **zero** git calls, while the new `Spec-Required=true` path made exactly one (`worktree list --porcelain`). So the widening genuinely does not touch the caller classes it was not meant to govern — review lesson 8 satisfied on the relaxation half.

Team-lead also independently re-measured the registry claim and it matches to the digit: **80 `Spec:` occurrences, 31 distinct, 0 absolute, 0 traversing, 40 `none`.**

### The High finding: the defect is REAL and newly introduced, but its stated reproduction is WRONG — both halves established by execution

The reviewer reported `scripts/spec_gate.py:287` (`resolved.is_file()` outside `_contain`'s `except (OSError, ValueError)`) as a **strict regression**: "`origin/main` EXIT=0 ⇄ PR head EXIT=1 `PermissionError` on identical input". Team-lead adjudicated by running both gate versions against the same fixtures, because a sub-agent's narration of its own probe is exactly what this session has been burned by twice.

**First, team-lead's own initial skepticism was wrong and is recorded as such.** I expected `Path.is_file()` to swallow `OSError` and therefore doubted the mechanism. Measured on Python 3.12.7: `is_file()` **raises** `PermissionError [Errno 13]` and `OSError [Errno 63] File name too long`, because pathlib's `_ignore_error` ignores only the not-found class (ENOENT/ENOTDIR/ELOOP), not EACCES or ENAMETOOLONG — while non-strict `resolve()` does **not** raise on either. That asymmetry is precisely why a stat placed outside `_contain`'s guard is reachable. The reviewer's mechanism is correct; my prior was not.

**Second, the "strict regression" claim is false as stated.** Single-root configuration, SPEC genuinely present under a mode-`000` `docs/specs`:

| configuration | `origin/main` | PR #151 head |
|---|---|---|
| single root, `docs/specs` mode 000 (EACCES) | **exit 1 `PermissionError`** | exit 1 `PermissionError` |
| single root, 600-char `Spec:` basename (ENAMETOOLONG) | **exit 1 `OSError`** | exit 1 `OSError` |

**Identical.** Main's `spec_path_exists` does `.resolve().exists()`, and `.exists()` propagates the same two errno classes, so main crashes too. On identical single-root input this is a **pre-existing** defect, not one this PR introduced.

**Third, the finding survives anyway, in the configuration the widening itself creates.** Root A (the main checkout) has no `docs/` at all; root B (a sibling worktree) holds the SPEC under a mode-`000` `docs/specs` — a checkout main never stats and the PR does:

| | `origin/main` | PR #151 head |
|---|---|---|
| two checkouts, only the sibling unreadable | **exit 0, `"decision": "auto_spec"`** | **exit 1 `PermissionError`** |

So the crash **is** newly introduced, by the widened enumeration, in exactly the multi-checkout configuration that is this PR's entire purpose. The reviewer's conclusion is right; its reproduction was over-broad. Recorded both ways because a finding that is correct for the wrong reason gets inherited as fact, and the previous iteration had to correct a reviewer's "`docs/sprint_state.md` is untracked" the same way.

**Reachability measured, and it is zero today.** No live issue triggers it: 0 absolute and 0 traversing `Spec:` values, and **0** issues with `Spec-Required: true` carrying an over-long basename. ISSUE-087's 554-character `Spec:` line — the one the reviewer named as a live trigger — has **`Spec-Required: false`**, so it cannot fire. The failure is also fail-**loud** (traceback, exit 1), not fail-open.

### Decision: REWORK, not ship-with-carriers — and the reasoning is the predecessor's, applied consistently

The team-lead contract permits shipping with unresolved Highs carried as follow-up issues, and all twelve checkpoints passed, so `reviewed` was available. It is declined for the same reasons ISSUE-096 declined it:

- It is a **newly introduced crash inside the guard being added** — the predicted failure mode in the predicted place, and this sprint exists to remove that class.
- The fix is **three lines** (move the stat inside the OSError guard, treating an error as "not in this root"), plus one disarm test. The second item is a **test-fixture** change only.
- The gate runs at `/implement` step 0 for every `Spec-Required` issue, and step 0c has **no branch for a traceback** — a non-JSON exit 1 is not one of the four decisions the skill knows, so when it fires it wedges the pipeline rather than degrading. That is ISSUE-102's own disease (an unsatisfiable gate) reappearing as an uncatchable one.

Rework set, exactly two items, no licence to redesign:
1. `scripts/spec_gate.py:287` — move the regular-file stat inside `_contain`'s guard; pin **both** raisers (EACCES and ENAMETOOLONG) in the disarm direction; require mutant **R1** to die. The reviewer's fixture warning is binding and is passed through verbatim: `docs/specs/` **must exist** in the fixture, or the kernel returns ENOENT first and the probe gives a false all-clear — its own PROBE N did exactly that before PROBE N4 reached the code.
2. `tests/test_spec_gate.py:259-275` — give `_REPRO_BLOCK` a second issue block so the sibling registry has something to mis-select; require mutant **R3b** to die. Today the id-scoping of the sibling field read is claimed in the module docstring, the test docstring and the PR body, and **pinned by nothing** — the same weakness as M11, not generalised.

Attempts is recorded as **1**: attempt 1 was a checkpoint-pass-with-findings, not a checkpoint failure, so this is not a review failure and the two-consecutive-failure rule is not engaged. Escalation condition carried forward: **if review 2 still shows a High, ISSUE-102 goes to `waiting` / `review-rework` for a human. No second rework.**

Everything else the review found is carrier work, not rework: the sibling-FIELD residual (a sibling checkout can supply the *field* as well as the file, flipping an authoritative `auto_spec` to `proceed`; 0 live divergences), the non-sprint cross-checkout `hold`→`proceed` row (declared out of scope at `issues.md:6302` and absent from the nine pins), the unreadable-sibling registry dropped silently with the verbatim legacy "SPEC missing" string and no `INCOMPLETE` marker (the exact collapse `INCOMPLETE_MARKER` was built to prevent), and the Low cluster. Five further reviewer mutants (R2 prunable guard, R4 sibling regular-file guard, R5 self-checkout skip, R6 `GIT_QUERY_TIMEOUT`, R9 field-read order) **survived** — unexercised guards, which is lesson 16's shape at the helper level and belongs in a carrier rather than in this rework.

**Negative results worth keeping, because the reviewer hunted the opposite finding rather than only confirming its own.** The tightening refuses nothing legitimate: `./`, embedded `./`, `//`, trailing `/`, case-differing paths on APFS, and an in-checkout symlinked `docs/` all return `proceed`. The `git worktree list --porcelain` parser handled paths with spaces, locked worktrees, detached HEAD, and — the case that mattered most — a **prunable/stale** registration, which was correctly excluded with no `FileNotFoundError`. The predecessor's prunable-worktree mechanism does **not** reproduce here. No branch or trunk name is resolved anywhere (ISSUE-089 respected), `gen_skills.py` shows no drift, and step 0c's gate re-run still sits downstream of the `/spec` output (lesson 12 holds).

### Scope: the module more than doubled, and lesson 14 held empirically

218 → 487 lines. The reviewer mapped every addition to an AC and named what was unmapped: `_contain`'s containment/absolute/NUL handling plus `refused` plumbing (~35 lines), regular-file-only (1), `INCOMPLETE_MARKER` with its `rev-parse` fallback (~16), cross-checkout counter-evidence (~6), and a 49-line docstring. The issue did request a DECISION (`issues.md:6297` — "The choice is the issue's to make; it must be stated with the failure mode it accepts"), so **review lesson 14 is live, and it held empirically: the High and two of the four Mediums live in that unmapped decision surface, not in the AC-mapped core.** The 49-line docstring is the decision record the issue demanded and is explicitly kept. Bucket C is the right declaration.

## Review attempt 1 — ISSUE-103 / PR #150 — all 12 checkpoints PASS, verdict REWORK on two Highs

All twelve review checkpoints exited **0**, with the five Figma/visual phases **plus** `ui-review` auto-skipping correctly for `UI: false` (confirmed by execution). Worktree **2638 passed, 1 skipped**. The reviewer's per-file decomposition reconciles exactly and was derived independently: `test_red_gate_scoping.py` +23, `test_sprint_queue.py` −18, everything else 0, so `2634 + 23 − 18 = 2639` collected. It even re-derived the −18 from first principles (10 archive files on disk in main, 4 tracked, 6 × 3 parametrized tests) without being told the arithmetic. **ISSUE-099 did not occur**; the single skip is the pre-existing `mknod` environmental one. The review ran fully **degraded**, both dimensions `context-unreachable`, `record-subject` correctly **refused** with `reason=verification-missing` and wrote nothing, so the notes carry **0** subject blocks and no receipt was forged.

The reviewer also independently reproduced all three of the implementer's disclosed first-pass mutation survivors as now-dying (M4, M5, M10) and reproduced the implementer's baseline sha256 `45125d78b729a81c…` exactly — so the disclosed residual is a **verified claim** rather than an unexamined disclosure. Its negative control survived, confirming the guards do not fire on honest input. It added three mutants of its own; two killed, one survived (F6).

### F1 — High — CONFIRMED BY TEAM-LEAD'S OWN EXECUTION, and it is a strict regression

This is the finding that decides the verdict, so it was adjudicated rather than read. **It is the predicted failure mode in the predicted place: a new fail-open introduced inside the guard being added** — the same shape that cost ISSUE-096 two reworks, now at the gate ISSUE-103 exists to repair.

Read from the committed tree first (`scripts/verify_checkpoint.py:771-783`): after the `124` / `no_run_codes` / `0` branches, the function computes `failed = _failed_test_files(...)` and then returns **`True` unconditionally**, merely relabelling the empty case as "per-file attribution unavailable". So **any** non-zero exit outside `{0, 4, 5, 124}` certifies RED even when the gate's own computed subject — the set of attributed failures — is **empty**. That is precisely the rule "a gate whose subject is COMPUTED must distinguish 'computed and empty' from 'could not compute'", violated by the fix written to honour it.

Team-lead built the reviewer's construction independently (own repo, own issue id, `--cov=src --cov-fail-under=50` in `addopts`; branch test PASSES and covers nothing):

```
scoped child's own summary:
  TOTAL             42     42     0%
  FAIL Required test coverage of 50% not reached. Total coverage: 0.00%
  1 passed, 2 warnings in 0.02s        <- ZERO test failures, exit 1 from coverage alone

----- MAIN (unfixed) -----
FAIL: RED phase — tests passed but should fail before implementation.
exit=1                                 <- CORRECT
----- BRANCH (PR #150) -----
PASS: RED phase — the branch's own tests fail as expected (exit 1) — scope was
tests/test_branch_feature.py (per-file attribution unavailable from pytest's output)
exit=0                                 <- WRONG
```

The branch's own test **passed** and the gate says "the branch's own tests fail as expected". The PR converts a correct refusal into a certification, so this is a **strict regression**, not a pre-existing hole — the opposite of the ISSUE-102 High, where team-lead's probe showed the single-root case was pre-existing. Each was measured rather than assumed, and they came out differently.

**Reachability, measured and stated precisely because it changes the severity argument but not the verdict.** This repo's own `[tool.pytest.ini_options]` carries **no** coverage flags — `testpaths` and `pythonpath` only — and CI passes `--cov=. --cov-fail-under=60` on the **command line**, which the checkpoint's child (`python3 -m pytest -q --tb=short -rfE <files>`) does not inherit. So the kit's own RED gate is **not** defeated today. But the gate demonstrably reads the *consumer* project's `addopts` — the PR's own `-rN` test worktree is the proof — and `--cov-fail-under` in `addopts` is a common convention in exactly the projects this kit is installed into. For a distributed tool, the consumer configuration is the point, so High stands.

The reviewer gave two further reproductions of the same root cause, which is what makes it a class rather than a case: `python3 -m pytest` with pytest absent (`No module named pytest`, exit 1 → certified RED having run nothing), and the JS branch, where `no_run_codes = ()` means npm's no-run exits are never refused at all — while the hazard note claims that route closed.

### F2 — High — CONFIRMED structurally: the could-not-compute refusal is positionally bypassable

`scripts/verify_checkpoint.py:680-695`. The new "cannot compute the branch's test-file delta" refusal — the one that exists to distinguish UNKNOWN from EMPTY — is nested **inside `if not all_test_files:`**. Since `_changed_files_vs_base` includes **untracked** paths (`git ls-files --others`), a single stray untracked test file makes `all_test_files` non-empty and the guard is never reached, so an **unresolvable base** is silently treated as a known delta. The reviewer measured both halves in one worktree: base unresolvable with an empty delta → correct `cannot compute … inconclusive` exit 1; add one untracked `tests/test_stray.py` → `PASS … failing: tests/test_stray.py` exit 0.

This is **review lesson 12's shape** — "a relocated gate call site must stay downstream of every step that mutates the surface it gates; pin position, not just presence" — and the fix is positional. The reviewer's caution is correct and is passed into the rework: do **not** fix it by restricting the delta to tracked paths, because a genuine RED's new test is very often untracked.

### Decision: REWORK, set of two Highs plus one bounded correction

Both Highs are gate-integrity failures in the control this PR exists to repair, both reproduced at the real consumer, and F1 is a fail-open *inside the new guard*. Shipping a RED gate that any coverage threshold defeats, in a sprint whose theme is that the pipeline's own gates do not gate, would be self-defeating — the same reasoning that made ISSUE-096 rework rather than carry its last High. Everything the four ACs actually name is **done and verified**; the defects live in the unspecified surface around them, which is exactly what review lesson 14 predicts.

Rework set:
1. **F1** — a non-zero exit with **zero attributed failures** must not certify RED. Must also cover the JS branch's empty `no_run_codes`.
2. **F2** — hoist the could-not-compute determination so it cannot be bypassed by a non-empty delta; pin **position**, not just presence.
3. **One bounded correction, in-scope because AC-4 governs it.** F3 measured that the hazard note's own justifying example does not reproduce: `pytest -q --tb=short -rfE tests/conftest.py` yields **`1 passed`, exit 0**, not exit 5. Team-lead's independent probes agree the conftest route is unreachable — `_has_real_tests` refuses a conftest-only change and a no-collectable-test change **upstream**, before the run. But the exit-5 guard is nonetheless **load-bearing**, via a construction neither the implementer nor the reviewer used: a collectable failing test that the project's own `addopts` **deselect** (`-m "not slow"`), which team-lead measured as `1 deselected` → pytest exit 5 → main certifies RED at exit 0 while the branch refuses. So the guard is right and its stated reason is false. AC-4 requires the note to name this route; naming it with a non-reproducing example fails that, and leaving a measurably false claim in the artifact an AC governs is not acceptable. Replace the example with the one that reproduces. This is a comment change, not new behaviour.

Attempts is recorded as **1**: attempt 1 was a checkpoint-pass-with-findings, not a checkpoint failure. Escalation condition, binding: **if review 2 still shows a High, ISSUE-103 goes to `waiting` / `review-rework` for a human. No second rework.**

Carriers, not rework (team-lead files them in one batch): F4 (the attribution parser scans the whole stream rather than the summary section, so a test that *prints* a `FAILED <path>` line can make a **passing** file be named first — diagnostic-only, cannot flip the verdict), F5 (three behaviours ship with no AC — the exit-4/5 refusal, the uncomputable-delta message, and the "none that `<runner>` can execute" refusal — and **both Highs live in exactly this unspecified surface**, which is lesson 14 measured rather than asserted), F6 (`_hazard_note()` reads a superset of its subject; reviewer mutant M13 survived), the security Low (scope paths splat into the runner argv with no `--` guard; fails closed for pytest at exit 4 but open for JS), and the minimality `[shrink]` of `_mock_run`. **ReDoS was cleared by execution** rather than by inspection, with the pattern printed back to prove the real object ran: 100k-space, 1M-char, 50k-line and 1MB-no-match inputs all linear at ≤9.2 ms.

Two reviewer self-corrections worth recording, because self-correction is the behaviour to reinforce: it reported its own commit message as saying "3 Low" where the accurate count is **4**, and it explicitly bounded F3 to pytest 9.0.3 rather than claiming the 8.3.4 the docstring also cites. Separately, team-lead independently confirmed the implementer's own Medium about interpreter divergence: the gate's bare `python3` carries pytest **8.3.4** while the declared `uv run --extra dev` environment carries **9.0.3**, so the gates measure a different interpreter from the one CI uses.

### Both reworks dispatched in parallel; pre-rework state recorded so the checks are real

Two `developer` sub-tasks at `opus`, one per issue, in their existing worktrees. Parallel is safe here and the reason is measured rather than assumed: the two branches touch **disjoint** file sets (`verify_checkpoint.py` vs `spec_gate.py`), each rework was told explicitly to stay out of the other's worktree and out of the other's module, and each was given a uniquely-prefixed scratchpad namespace (`i103r2_`, `i102_`) after the first round produced a real collision — one sub-task's `scratchpad/mutate.py` was overwritten mid-task by the other's file of the same name. No project file was affected that time and the battery was re-run from a uniquely-named copy, but a collision on a *result* file would have silently corrupted evidence. That is now a Medium finding with a carrier owed.

Recorded **before** the tips move, because neither check can be reconstructed afterwards:

| issue | pre-rework tip | `docs/review_notes/<id>.md` blob |
|---|---|---|
| ISSUE-103 | `0c10ca5f15bfb09f2b3a0b873c4cb61de1aa1d18` | `4e100fce3ea4a92bda04850334ac2d843933716b` |
| ISSUE-102 | `af2d22a4280c5d6f38a009285e6a4ca8c7e600df` | `18cfcc67429bbeeeaee034c3f85c220ebf0192bb` |

These give two things a post-hoc read cannot. First, **fast-forward verification**: the pre-recorded tip must be an ancestor of the new tip, which is how the no-force-push rule is checked rather than trusted. (ISSUE-103's tip had already advanced `7a8c145` → `0c10ca5` when its reviewer committed its notes, so the pre-record is taken at the real starting point, not at the implement tip.) Second, **notes-integrity verification**: the implementer must not touch the artifact its own reviewer judges, and a pre-recorded blob OID settles that, where a sha256 printed by the agent under review would not.

Both reworks carry the same escalation condition, which is binding and is the predecessor's rule applied unchanged: **if review 2 still shows a High on either issue, that issue goes to `waiting` / `review-rework` and stops for a human. No second rework.** This bounds the iteration to exactly one rework and one re-review per issue.

Ship order is unchanged and still **ISSUE-103 → ISSUE-102**, independent of which rework returns first.

## ISSUE-102 rework landed at `b557abf` — verified by team-lead's own execution

**Integrity checks, all against pre-recorded values rather than agent-reported ones:**
- **Fast-forward confirmed:** the pre-recorded `af2d22a` is an ancestor of `b557abf` (`git merge-base --is-ancestor`). No force-push, no history rewrite. Push was `af2d22a..b557abf`.
- **The implementer did not touch the artifact its reviewer judges:** `docs/review_notes/ISSUE-102.md` blob is `18cfcc67429bbeeeaee034c3f85c220ebf0192bb`, byte-identical to the pre-record taken before dispatch.
- **All four protected blob OIDs unchanged**, and `scripts/verify_checkpoint.py` is **absent from the diff** — the rework stayed out of ISSUE-103's module, as instructed. Changed files: `scripts/spec_gate.py`, `tests/test_spec_gate.py`, `docs/review_notes/ISSUE-102.md` (the reviewer's earlier commit), and the two `skills/implement/SKILL.md{,.tmpl}` from before the rework.
- Registry untouched; `Status` still `doing` with PR #151 open. **ISSUE-105 did not bite for the third time this iteration.**

**The fix, read from the committed tree.** `_contain` now returns a `(path, is_regular_file)` tuple with the stat **inside** the existing `except (OSError, ValueError)`, and the call site consumes the second element. The tuple is not gratuitous: it keeps "statted, nothing there" as the pre-existing **`absent`** outcome instead of folding it into `refused`, which would have made the `absent from all N checkout(s)` reason unreachable and reported a plainly-missing SPEC as an `absolute path, '..' escape, or symlink` refusal — a reason-vocabulary change the rework brief forbade. No new reason token, no env knob, no new decision value. 8 non-comment lines.

**Team-lead re-ran its own three probes against the reworked tree.** All three now behave, and one is better than required:

| probe | `origin/main` | PR head before rework | **after rework** |
|---|---|---|---|
| single root, `docs/specs` mode 000 (EACCES) | exit 1 crash | exit 1 crash | **exit 0 `auto_spec`** |
| single root, 600-char `Spec:` basename (ENAMETOOLONG) | exit 1 crash | exit 1 crash | **exit 0 `auto_spec`** |
| two checkouts, only the sibling unreadable | exit 0 | **exit 1 crash** | **exit 0 `auto_spec`** |

The newly-introduced crash (row 3) is closed, which was the rework's actual requirement. Rows 1 and 2 are a **bonus that was disclosed rather than hidden**, and team-lead confirmed the mechanism rather than the claim: because the guard sits inside the per-root loop and `roots[0]` *is* a root, the pre-existing single-root crash closes as a consequence of the same three lines. So the PR now **strictly improves on main** for these inputs instead of merely not regressing — and it did so without adding surface, which is the distinction that matters under ISSUE-079.

**Both mutants killed under team-lead's own mutation, with a byte-exact restore proven:**

```
baseline  src=d0d34026a770bd5e…  tst=a40e2b64b050676c…
BASELINE (unmutated):                       64 passed in 3.50s
R1  (drop OSError from _contain's except):  3 failed, 61 passed
    FAILED …TestUnstattableRootIsRefusedNotFatal::test_unreadable_sibling_checkout_is_refused_not_fatal
    FAILED …::test_overlong_spec_value_is_refused_not_fatal
    FAILED …::test_a_refused_root_does_not_end_the_enumeration
R3b (neutralise parse_issue's id argument): 11 failed, 53 passed
restored  src=d0d34026a770bd5e…  identical=true
restored  tst=a40e2b64b050676c…  identical=true
dirty files: 0
```

R1 is the mutant that **survived** the reviewer's battery (60 passed) and now dies on three independent tests, all of which drive the **step-0c CLI by subprocess** — the disarm direction at the real consumer, which is what review lesson 16 asks for. The third of those, `test_a_refused_root_does_not_end_the_enumeration`, pins the "**and the loop continues**" half that nothing else covered; the implementer's own R1d mutant (`continue` → `break`) dies only on it. Team-lead's R3b variant is harsher than the reviewer's (it neutralises the id wherever threaded rather than only taking the first match) and kills 11 tests, which independently establishes that the id-scoping is now load-bearing where previously it was pinned by nothing but prose in three places.

The reviewer's own fixture trap was heeded rather than rediscovered: the new tests assert the **premise** (`_premise_the_stat_raises`) that `is_file()` really raises on the constructed input, because a fixture whose parent directory does not exist returns `False` from `is_file()` and yields a false all-clear. Measured on this platform: EACCES and ENAMETOOLONG both raise from `is_file()` while `resolve()` does not, and the no-parent case returns `False` — the exact trap.

**Suite:** `test_spec_gate.py` re-measured by team-lead at **64** collected (20 on main → 64, i.e. +44). The claimed worktree total of 2659 passed / 1 skipped reconciles by arithmetic against team-lead's independently measured main figures: `2634 + 44 − 18 = 2660` collected, and 2660 − 1 skip = 2659. The full worktree suite was deliberately **not** re-run while the ISSUE-103 rework sub-task held its own live worktree, because several kit tests drive real-repo worktree operations and a concurrent run risks a false failure costing more than the wall time saved — the same judgement the previous iteration recorded. The authoritative check is the post-merge smoke on main, which is blocking.

**Nine legacy pins re-run green**, plus a live sweep over the real registry from both CWDs: **108 live issues, 0 non-zero exits, `{proceed: 102, auto_spec: 6}` identical from the main checkout and from the worktree** — including ISSUE-088, the issue the defect was originally measured on, now `proceed` from both locations, which is AC-1 dogfooded on the real repository rather than in a fixture.

**Rework diff is small and bounded**, which is the discipline the predecessor's near-doubling violated: `+19/−10` in `spec_gate.py` and `+169/−1` in the test file — **188 insertions, 11 deletions** total against `af2d22a`.

**One honest survivor, reported rather than deleted:** mutant **A1** — deleting `_contain`'s `if candidate.is_absolute(): return None, False` early return leaves all 64 green, because the containment check refuses absolute paths anyway. It is a redundant guard whose test pins the outcome rather than the guard. It falls inside the reviewer's already-named Low about unexercised guards, and was correctly left alone rather than fixed in a scoped rework.

### Review 2 subject for ISSUE-102, measured by team-lead before the reviewer reported

| | range | bytes / headers / sha256 |
|---|---|---|
| full | `ce44206..b557abf` | **80003 / 5 / `2b4d25c4acc2eece…`** |
| product (excl. `docs/review_notes/*`) | same | **54651 / 4 / `b662025d07362fe2…`** |

Full now **exceeds** product because the reviewer's notes are committed as of `af2d22a` — the divergence predicted when the attempt-1 digests were recorded, and the same pattern the predecessor issue showed at `47ad48b`. Review 2's reviewer was again given **no figures** and asked to compute its own.

PR #151 re-verified live: `OPEN` / not draft / `MERGEABLE` / `CLEAN`, `headRefOid` == `b557abf` == the local tip (ISSUE-077 cross-check).

Review 2 for ISSUE-102 was dispatched **in parallel with the still-running ISSUE-103 rework**, which is safe for the measured reason: disjoint worktrees and disjoint modules, with each sub-task told explicitly to stay out of the other's. Ship order remains **ISSUE-103 → ISSUE-102** regardless of which returns first.

### Carrier id allocation resolved in advance

`issues.md` allocates by next-free-number and the current maximum is **ISSUE-109**, so this iteration's carriers take **ISSUE-110** onward. They are filed by team-lead in **ONE batched write** under `registry_edit.sh` after both review verdicts are in — not incrementally. Two reasons, both learned: concurrent or piecemeal filing collides on the id (the previous iteration deferred two carriers for exactly this reason), and several findings' priorities depend on what review 2 concludes. The `planner` agent drafts the text and applies nothing, because it has **no `Bash` tool** in this environment — now the seventh observation, and the contract holds each time because the dispatch assumes the absence rather than discovering it.

The backlog checklist entries that must be ticked at ship are located and unchecked: `issues.md:75` (ISSUE-102) and `issues.md:76` (ISSUE-103).

### Carrier queue as it stands (not yet filed)

From ISSUE-102's review 1 and rework: the sibling-**FIELD** residual plus a read-ordering pin; the non-sprint cross-checkout `hold`→`proceed` row (declared out of scope at `issues.md:6302`, absent from the nine pins); the unreadable-sibling registry collapsing to the legacy "SPEC missing" string with no `INCOMPLETE` marker; and the Low cluster (directory refusal not reported as `REFUSED`, step 0c naming two outcomes where the gate emits three, absolute checkout paths in reasons, four unexercised guards incl. surviving mutant A1, `GIT_QUERY_TIMEOUT` documented in the module docstring only, a duplicate test that no implementation can fail, and the module-suite runtime).

From ISSUE-103's review 1: the attribution parser scanning the whole stream rather than the summary section (a test that *prints* `FAILED <path>` can mis-name a passing file — diagnostic-only, cannot flip the verdict); three behaviours shipping with no AC; `_hazard_note()` reading a superset of its subject (reviewer mutant M13 survived); scope paths splatting into the runner argv with no `--` guard; and the `_mock_run` minimality shrink.

From both implements, independently confirmed by team-lead: `scripts/validate_issues.py:87-98` `_spec_path_satisfied` carrying the identical single-root `.resolve().exists()` assumption and accepting a directory — **Medium, not the High it was reported as**, because the validator exits **0** with 15 violations present and so cannot fail CI; the separate observation that `validate_issues.py` at `ci.yml:39` is **ISSUE-104 Route 1's species at a third control** and uncovered by any existing carrier; the gate family invoking bare `python3 -m pytest` (pytest **8.3.4**) rather than the declared runner (**9.0.3**), so the gates measure a different interpreter than CI; `_changed_files_vs_base` including untracked paths in every delta-scoped gate's subject; the `implement/pr` step-11-vs-step-12 advisory; and the stale `.worktrees/issue-ISSUE-081-gate-evidence` registration at `6aeaf3d` which `_find_worktree_path` would match by slug for any future ISSUE-081 checkpoint.

New this iteration and operational rather than code: **parallel sub-agents share one session scratchpad with no namespacing.** One sub-task's `scratchpad/mutate.py` was overwritten mid-task by a concurrent sibling's file of the same name; it was detected because the header named the other issue, and the battery was re-run from a uniquely-named copy, so no result was corrupted. A collision on a *result* file would have been silent. All later sub-tasks were dispatched with per-issue filename prefixes, which is a workaround, not a fix. **Medium.**

## Discovered Issues
- [iter 1] **Two carriers from rework 2 are PENDING and deliberately unfiled** — the nested-fence defect in the shared fence predicate (Medium; fix belongs in `sprint_queue`'s helper so both consumers inherit it) and the echo-gate receipt living inside the worktree under review (Low; anything executing there during a review, including the PR's own tests and hooks, could append a well-formed receipt). Both are described in full in the rework-2 section above. They were NOT filed because **two team-lead instances are live on this issue and `issues.md` allocates ids by next-free-number**: concurrent filing would hand both carriers the same id. Whichever instance resolves ownership files them, under `registry_edit.sh`, after confirming the next free id against the committed file. Neither is Critical or High, so no auto-created follow-up was owed.
- [iter 1] **ISSUE-105 did not bite, and that is a measurement rather than luck.** The rework sub-task was dispatched with an explicit override of `skills/implement/SKILL.md` step 12, and the `implement/registry` checkpoint re-run by team-lead after the push reports `PASS: ISSUE-096 registry updated (Status=doing, PR present)` — `Status` is still `doing` with PR #147 open, which is what the team-lead contract requires and what step 12 would have broken. The contract held because the dispatch assumed the defect rather than discovering it, the same shape as the ISSUE-074 counter-instance row. Nothing had to be reverted under the lock.
- [iter 1] Implement checkpoints re-run by team-lead rather than accepted from the sub-task's report: `worktree`, `push`, `pr`, `registry` all exit **0**. The `red` and `test` phases are not re-runnable after the fact (the tree is green now) and `test` was deliberately not re-run because a reviewer is executing the suite in that worktree; the sub-task reported both at 0 with literal output, and team-lead independently re-ran the two module suites (266 passed) and the new disarm test in isolation.
- [iter 1] **ISSUE-106 filed** (`Manual: true`, P1, Depends-On ISSUE-096) — ISSUE-096's AC-6 split out as a sibling, exactly as ISSUE-096's own team-lead note at filing directs. AC-6 needs a live main-session, non-sub-task `/review` run; every sprint-pipeline context IS a sub-task, so the measurement is structurally unreachable from automation and cannot be dispatched by an iteration. Applied by team-lead under `registry_edit.sh` (planner drafted the content and has no `Bash` — see the ISSUE-074 counter-instance row below). Adds zero new `validate_issues.py` violations (15 pre-existing, 15 after; one AC was reworded from an em-dash to a comma before `when` to satisfy the GWT pattern).
- [iter 1] **ISSUE-074 counter-instance, 5th observation** — the `planner` agent has no `Bash` tool in this environment. It was dispatched text-only, returned the ISSUE-106 block as text, and wrote no file; team-lead applied it under the lock. The contract held because the dispatch assumed the absence rather than discovering it.
- [iter 1] ISSUE-096 implement findings, **none Critical or High**, so no follow-up issue was auto-created. Logged here as the carrier for the two Mediums:
  - *Medium* — `scripts/spec_gate.py` scans the whole issue block **including the `Out:` sub-list of `#### Scope (In/Out)`**, so naming an out-of-scope concern raises a spec signal on an issue that explicitly excludes it. Measured live on ISSUE-096: the word "migration" in its out-of-scope line about ISSUE-075 produced a non-sprint `hold` that is pure noise. Adjacent to ISSUE-102 (this sprint) but a **distinct** defect — 102 is path resolution, this is signal scoping. Needs its own carrier if it is to be real.
  - *Medium* — the pre-ISSUE-096 `emit --event review_delegated_to_*` path can still record a delegation with **no subject and no echo**. Left in place deliberately because ISSUE-066's tests pin it and ISSUE-096 AC-7 forbids modifying them. Pairs naturally with ISSUE-075's `_emit_event` migration.
  - *Low* — `implement/pr` checkpoint checks the `PR` field at step 11 but the skill writes it at step 12, so a correct pipeline always trips one advisory. Observed this iteration (exit 0 with `FAIL: ISSUE-096 has no PR field in issues.md`, self-corrected, re-ran clean).
  - *Low* — `docs/test_plan.md` has no Risk Matrix row or TC entries for the review-subject binding. The implement sub-task correctly declined to add one (untracked working doc on main, must not be committed on a feature branch).
  - *Low* — stray `.worktrees/issue-ISSUE-081-gate-evidence` worktree at `6aeaf3d` predates this sprint; ISSUE-081 is held, so it is left alone rather than cleaned up.

## Resume after the spend-limit hold — sole ownership re-established by measurement (2026-11-07)

The limit is cleared. Before touching anything, the concurrency hazard that damaged ISSUE-096 was checked for rather than assumed away, and the check is a real one: **every mutable artifact in both worktrees is 4 days stale.** `.worktrees/issue-ISSUE-103-red-scope`'s three dirty files carry mtimes of Nov 3 01:54–02:02 and its run file Nov 3 02:03; ISSUE-102's run file is Nov 3 01:53 and its `docs/.review/findings.json` Nov 3 01:27. `docs/sprint_state.md` was last written 09:12 today by the orchestrator hold note and by nothing since. No live writer on either worktree or on this file, so this instance owns both issues outright. Status set back to `running`.

Baseline **re-measured on main at `4466d7c`: 2633 passed, 1 skipped in 89.95s**; `--collect-only` = **2634 collected**. The brief's quoted 2633 is **correct**, which is recorded explicitly because the orchestrator figure was wrong three times in the previous iteration — "the brief was right" is itself a measurement, not an assumption to inherit. Per-file on main: `test_verify_checkpoint.py` **145**, `test_sprint_queue.py` **207**, `test_red_gate_scoping.py` **absent**.

## ISSUE-103 — the three uncommitted files ADJUDICATED, then completed, then committed at `1a68895`

The dead sub-agent's last words were *"All kill-mutants killed, both negative controls survived. Now the full suite and the collection decomposition"*. That was treated as a **claim**, not a result. Verdict: **the substance was sound and the verification was genuinely unfinished — and it had also quietly declined half of one of the two findings it was dispatched to fix.** What follows separates what was adopted on this instance's own measurement from what this instance wrote.

### Adopted on measurement — F2, the positional finding

The hoist is real, read from the tree rather than the report: the determination moved into a named `_delta_base_unresolvable(wt_path, base)` and is called **before** `_changed_files_vs_base` is read, so a non-empty delta can no longer bypass it. The guard's own two legs are both required (no merge-base **and** the base ref does not resolve), so it cannot fire on a merely-stale base.

**Position is pinned, not merely presence** — which is the whole of review lesson 12 and the thing F2 actually demanded. Verified by mutation, not by reading: reverting the hoist exactly (`F2-POSITION`: delete the early block, re-nest the original inside `if not all_test_files:`) **kills** `TestUncomputableDeltaPosition::test_untracked_test_file_does_not_mask_the_refusal`. That test additionally asserts `runs == []`, i.e. nothing was executed on an unknown subject, so it pins the ordering rather than only the output string. Deleting the guard outright (`F2-DELETE`) kills a second, independent test.

### Adopted on measurement — F1, the pytest half

A non-zero exit with zero attributed failures no longer certifies RED. The verdict previously returned `True` unconditionally after computing the attributed set, relabelling the empty case as "attribution unavailable" — the exact "computed and empty" / "could not compute" collapse. Now attribution is required for pytest and the two empty cases **refuse with different diagnoses** (nothing blamed at all, vs blamed only outside the branch's delta), so the implementer is sent to the right place without re-running anything.

Reverting it (`F1-REVERT`: `attributes_failures = False` for pytest) **kills a REAL-CONSUMER test** — `test_nothing_blamed_coverage_threshold_real_consumer`, which drives `bash scripts/checkpoint.sh` against a throwaway repo with real `pytest-cov` where the branch's own test passes and exit 1 comes from `--cov-fail-under` alone. That is review lesson 16 satisfied at the consumer, not at a helper. `F1-MERGE` (collapse the two diagnoses) and `F1-SCOPE` (attribution stops being scoped to the delta) also die, the latter on the out-of-scope attribution pin.

### Adopted on measurement — the AC-4 correction, and a fixture change that had to be checked

The hazard note's exit-5 example was replaced with the route that actually reproduces (the project's own `addopts` **deselecting** the branch's test — `-m 'not slow'` plus a `@pytest.mark.slow` test gives `1 deselected`, exit 5), and the `probe_repo` fixture carries that construction for real. This is the correction the review asked for and it is a comment-plus-fixture change, not new behaviour.

One inherited change needed scrutiny rather than acceptance, because "adjust a fixture until the new code passes" is how a tightening gets bought cheaply: three pre-existing tests had their mocked runner stdout changed from the bare token `"FAILED"` to `_RED_FAILED_SUMMARY = "FAILED tests/test_feature.py::test_new_feature - assert False"`. Under the new attribution requirement the bare token parses to zero blamed files, so those tests would have failed. **Measured rather than argued:** real pytest `-rfE` emits `FAILED tests/test_branch_feature.py::test_branch_feature - assert False`. The old fixture was an *unfaithful* model of the oracle and the new one is faithful, and the path it names is the one the fixture's own delta returns. This is a faithfulness upgrade, not a weakened test — and the bare token now has a legitimate separate meaning ("an exit code with nobody to blame") which the new tests use deliberately.

### The negative control the inherited work did NOT cover — measured, and it holds

The module docstring makes one load-bearing claim that **no test pins**: that with the verifier's call shape, nodeids come back relative to the invocation dir rather than to `rootdir`, "so hoisting `rootdir` above the worktree still attributes". Every `probe_repo` config anchors `rootdir` **at** the worktree with `[tool.pytest.ini_options]`, so the hoisted case was measured by nothing. This mattered more than any mutant: if the claim were false, F1's new requirement would **refuse genuine REDs** in every consumer project whose pytest rootdir sits above the worktree — a fresh over-refusal inside the guard being added, which is this sprint's signature defect.

Constructed and measured on **pytest 8.3.4, the version the gate's child actually runs** (not the 9.0.3 the declared `uv run --extra dev` environment carries — the interpreter divergence this iteration already recorded):

| probe | rootdir | nodeid emitted | result |
|---|---|---|---|
| invocation dir has no ini, parent does | hoisted one level up, `configfile: pyproject.toml` | `tests/test_branch_feature.py::test_branch_feature` | relative to the **invocation dir** |
| genuine RED at the real consumer, same shape | hoisted above the worktree | — | **exit 0**, `PASS … failing: tests/test_branch_feature.py` |

So the claim is **true**, the arm direction survives the tightening, and the disclosed residual is now a measurement instead of a claim. Recorded with its caveat: this is one platform and one pytest version, and the refusal is fail-CLOSED, so the residual's cost is a false refusal that names both the scope and whatever was blamed — diagnosable from the gate's own output.

### Rewritten by this instance — F1's npm half, which the inherited work declined

F1's rework item was explicit: *"Must also cover the JS branch's empty `no_run_codes`."* The inherited work **did not fix it.** It disclosed it instead, with the note "npm therefore keeps BOTH legacy holes", justified by review lesson 8 (requiring attribution for npm would refuse every JS RED, since there is no npm output format to parse). That justification covers the **attribution** half and was accepted — the legacy npm contract is kept and, correctly, *pinned* by a test, which is lesson 8's actual requirement.

It does **not** cover the `no_run_codes` half, and "a disclosed residual is a CLAIM — measure it, or the disclosure itself becomes the defect." Measured, with real npm:

| measured route | exit | safely refusable? |
|---|---|---|
| npm, no `test` script — nothing ran | **1** | **no** — collides |
| npm, a genuine JS test failure — GENUINE RED | **1** | must stay RED |
| npm, `test` script's binary absent — nothing ran | **127** | **yes** |
| runner binary absent (`_run` synthesises it) | **127** | **yes** |

npm uses exit 1 for both `Missing script: "test"` and a real test failure, so refusing exit 1 would refuse every genuine JS RED — **that half is genuinely forced**, and the inherited disclosure is right about it. But **exit 127 collides with nothing**, so "the runner was never executed" was still certifying the TDD RED phase. That is a fake-RED route of exactly the class ISSUE-103 exists to close, left open in the branch that closes the others, and it costs one branch to fix with zero over-refusal risk.

Written by this instance: a 127 branch refusing for **both** runners, a hazard note stating the measured reason rather than implying the whole class is unrefusable, and five tests — including a **real-consumer probe driving real npm** against a `test` script whose binary does not exist, plus a parametrized both-runners pin and a negative control asserting npm exit 1 **still** certifies RED (so a future "close the npm hole" that refuses exit 1 fails this test, which is the point).

**One self-correction, recorded because narration is the thing this session keeps catching.** The npm real-consumer probe ran in 0.35s and this instance judged that too fast for a real `npm test`, suspecting it had actually measured `_run`'s synthetic 127 from npm being off the subprocess PATH — which would have made the test's own docstring false. Measured: npm **was** executed, returned **127 itself** (`sh: definitely-not-a-real-binary-xyz: command not found`), and a direct control invocation of the same argv took 0.09s. npm is simply faster here than assumed. The suspicion was wrong and the docstring is accurate; recorded in the same spirit as the previous iteration's wrong prior about `is_file()`.

### Team-lead's own 8-mutant matrix — ZERO survivors, restore byte-exact

Run on a **scratchpad copy** of the worktree (`rsync` without `.git`, so no mutation could reach the shared tree), against a pristine sha256 re-asserted after every row.

```
pristine sha256 = e70da2b4e9e1042fe96f765b8b3227ab8eb66067209f60a6068fdff62d40b1bb
BASELINE (unmutated)                                      186 passed
KILLED  F2-POSITION        re-nest the hoisted check      -> test_untracked_test_file_does_not_mask_the_refusal
KILLED  F2-DELETE          guard returns False            -> test_uncomputable_delta_is_distinct_from_an_empty_delta
KILLED  F1-REVERT          attribution not required       -> test_nothing_blamed_coverage_threshold_real_consumer
KILLED  F1-SCOPE           attribution ignores the delta  -> test_out_of_scope_path_is_not_attributed
KILLED  F1-MERGE           the two empty cases collapse   -> test_blamed_only_outside_the_delta_real_consumer
KILLED  F1-DEDUP           parser stops deduplicating     -> test_multiple_failures_collect_all_without_duplicates
KILLED  F1-NPM127          the 127 refusal deleted        -> test_npm_exit_127_real_consumer
KILLED  F1-NPM127-PYONLY   127 refused for pytest only    -> test_npm_exit_127_real_consumer
restored sha256 = e70da2b4e9e1042fe96f765b8b3227ab8eb66067209f60a6068fdff62d40b1bb  identical=true
survivors: NONE
```

Four of the eight die at the **real consumer** rather than at a helper. The two npm mutants are this instance's own addition proving itself load-bearing — `F1-NPM127-PYONLY` matters most of the pair, because it is the mutant that would have reproduced the inherited work's own omission.

### Integrity, suite, and scope — checked against values recorded BEFORE the tips moved

- **Fast-forward confirmed:** the pre-recorded `0c10ca5` is an ancestor of `1a68895`; push was `0c10ca5..1a68895`. No force-push.
- **The implementer did not touch the artifact its reviewer judges:** `docs/review_notes/ISSUE-103.md` blob is `4e100fce3ea4a92bda04850334ac2d843933716b`, **byte-identical** to the pre-record taken before the rework was dispatched. A sha256 printed by the agent under review could not have settled this; a pre-recorded OID does.
- **All four protected blob OIDs unchanged**, and `scripts/spec_gate.py` is still `05e9f334…` — i.e. the ISSUE-103 branch stayed out of ISSUE-102's module, so the mandated serial ship order still has nothing to resolve. Exactly three files in the commit.
- **Suite 2656 passed / 1 skipped**, decomposed by set rather than by total: main 2634 collected **+41** (`test_red_gate_scoping.py`, absent on main) **−18** (`test_sprint_queue.py` 207→189, the 6 untracked archive files × 3 parametrized tests) = **2657**, and 2657 − 1 skip = 2656. Reconciles exactly. The single skip is the pre-existing environmental `mknod` one; **ISSUE-099 did not bite.**
- **Zero new lint findings.** `ruff` is not a CI gate here (CI runs `validate_frontmatter`, `validate_issues`, `validate_spec` only), but it was checked anyway: `scripts/verify_checkpoint.py` carries **17** findings on main and **17** here, none at any changed line, and `tests/test_red_gate_scoping.py` is **clean**.
- **ISSUE-105 did not bite, for the fourth time this sprint, because it was guarded for.** The registry still reads `Status: doing` with PR #150 open. Nothing was written to `issues.md` at commit time; `Status: done` is team-lead's to write only after `gh pr view` reports MERGED.
- Module file grew 23 → 36 (inherited rework) → **41** (this instance's five tests), which is why the total delta is +41 rather than the +23 recorded at implement time.

### Review 2 subject, measured by team-lead BEFORE the reviewer reports

| | range | bytes / headers / sha256 |
|---|---|---|
| full | `ce44206..1a68895` | **85693 / 4 / `71dbb9b436446185…`** |
| product (excl. `docs/review_notes/*`) | same | **71565 / 3 / `3d1c637afd4f5dc2…`** |

Full exceeds product because the reviewer's notes are committed as of `0c10ca5`. PR #150 re-verified live: `OPEN` / not draft, `headRefOid` == `1a68895` == the local tip (the ISSUE-077 cross-check), `MERGEABLE`, `mergeStateStatus` `UNSTABLE` because CI is still running — CI will be verified against the head that actually merges, not against a stale run summary.

Review 2 is dispatched with **no digests and no suite totals**, as on the predecessor issue: a pasted figure is the one remaining way past the subject gate, so agreement only means something when both parties measure independently.

**Escalation condition, carried forward unchanged and binding: if review 2 still shows a High, ISSUE-103 goes to `waiting` / `review-rework` and stops for a human. No second rework.** Attempts stays **1** — review 1 was a checkpoint-pass-with-findings and the two deaths were infra, not phase failures.

## ISSUE-102 — re-dispatched at `b557abf`, and the tree is PROVABLY un-drifted across the hold

Review 2 was in flight when the limit hit, so it is re-dispatched from the start at the same tip. The worktree needed no repair beyond debris:

- **The `docs/.review/findings.json` scratch from attempt 1 was removed**, after confirming it is safe to remove rather than assuming it: `git check-ignore -v` resolves it to `.gitignore:23` (`docs/.review/`) and `git ls-files docs/.review/` returns **nothing tracked**. (The forced untracked-clean form is blocked by this environment's command policy, so the single verified-untracked file was removed directly — same effect, and the verification is what made it safe either way.)
- **Worktree clean** under `--untracked-files=all`, tip `b557abf`.
- **The notes artifact is byte-identical to the pre-record:** `docs/review_notes/ISSUE-102.md` blob `18cfcc67429bbeeeaee034c3f85c220ebf0192bb`, matching the value recorded before the rework was dispatched. The rework did not touch the artifact its reviewer judges.
- **All four protected blob OIDs unchanged**, and `scripts/verify_checkpoint.py` is still `9d958070…` — i.e. ISSUE-102's branch never entered ISSUE-103's module, and ISSUE-103's commit left `scripts/spec_gate.py` at `05e9f334…`. **The disjointness the serial ship order relies on is re-measured, not assumed**, in both directions.
- `docs/review_notes/ISSUE-102.md` carries **0** `## Review Subject` blocks, so there is no duplicate-block wedge waiting for the next writer.

**The digests are byte-identical to the ones recorded before the hold** — full `ce44206..b557abf` = **80003 / 5 / `2b4d25c4acc2eece…`**, product = **54651 / 4 / `b662025d07362fe2…`**. Measured fresh by this instance and only then compared against the stored figures. That is a useful result rather than a formality: it establishes that nothing drifted in either tree during the four-day hold, so review 2 is reviewing exactly the tree the previous iteration verified.

PR #151 live: `OPEN` / not draft, `headRefOid` == `b557abf` == the local tip (ISSUE-077 cross-check). `mergeable` reads `UNKNOWN` — expected for a PR untouched for four days (GitHub's mergeability cache is cold, not conflicted) and it will be **re-polled to `MERGEABLE`/`CLEAN` before any merge**, never merged through the ambiguity.

### An inherited hazard MEASURED and found overstated — the two reviews run in parallel

The previous two iterations both declined to run a suite concurrently with a live worktree, on the stated ground that "several kit tests drive real-repo worktree operations, so a concurrent run risks damaging the tree under review." That is a load-bearing constraint which was costing an entire review cycle of serialisation, and this sprint's whole discipline is that an inherited claim is a claim. So it was measured.

**Every `.worktrees/` reference in `tests/` is rooted at a throwaway path or is an assertion on a path string** — `repo / ".worktrees" / "feat"` in `test_kit_telemetry.py`, `clone / ".worktrees" / WT_SLUG` in `test_review_subject_binding.py`, `tmp_path`-derived repos in `test_worktree.py` and `test_gen_skills.py`. No test mutates the real repository's worktrees. The residual risk is therefore **CPU contention only, not mutation** — and the real-consumer probes carry a 120s `KIT_CHECKPOINT_TEST_TIMEOUT` against children that collect one or two short test files, so contention cannot plausibly exhaust that budget.

The two reviews were therefore dispatched **in parallel**, on disjoint worktrees and disjoint modules, each told explicitly to stay out of the other's and not to run the main checkout's suite. **Ship order is unchanged and still serial, ISSUE-103 → ISSUE-102, regardless of which review returns first.** Each reviewer also got a uniquely-prefixed scratchpad namespace (`i103rev2_`, `i102rev2_`) because the shared session scratchpad has no namespacing and a prior collision overwrote one sub-task's `mutate.py` mid-task.

Recorded as a correction rather than a liberty: the constraint was real in intent, the mechanism it named does not exist, and the narrower true constraint (one writer per worktree) is still honoured in full.

### ISSUE-103 CI is green on the head that would actually merge

`gh api .../commits/1a6889506dc1bcd4917ac9afdc6c472fb88a3450/check-runs` → `test (3.11)` **completed/success**, `test (3.12)` **completed/success**. Verified against the commit oid rather than against the PR's latest-run summary, per ISSUE-077, so a stale or wrong-target run cannot be mistaken for this head's result. `ship-merge-decision --pr 150` (bare number) currently returns `{"action": "merge", "reason": "PR 150 not merged (state=open)"}`, which will be re-probed and cross-checked against `gh pr view` at ship time.

### Registry work pre-positioned (not yet applied)

`issues.md` allocates by next-free-number and the current maximum is **ISSUE-109**, so this iteration's carriers take **ISSUE-110 onward**, filed by team-lead in **ONE batched write** under `registry_edit.sh` after both verdicts are in — never incrementally, because piecemeal filing collides on the id and several priorities depend on what the reviews conclude. `validate_issues.py issues.md` baseline re-measured: **15 violations, exit 0** (it prints "violations" and cannot fail CI), and neither ISSUE-102 nor ISSUE-103 is named in any of them.

Ship-time targets located and unchanged: the `- Status: doing` line inside each issue block, and the backlog checklist entries at `issues.md:75` (ISSUE-102) and `issues.md:76` (ISSUE-103), both currently `- [ ]`. `Status: done` is written **only** after `gh pr view` reports MERGED (ISSUE-105 is still the live carrier; the implement skill's step 12 still contradicts the team-lead contract).

### Pre-registered smoke prediction for ISSUE-103 — written BEFORE the merge

A prediction written after the result is a rationalisation, so this is recorded now. The post-merge smoke on main is a **blocking** checkpoint and it should be a real verification rather than a rubber stamp, which requires knowing the expected number in advance.

Main at `4466d7c` measures **2633 passed / 1 skipped / 2634 collected**, with `test_sprint_queue.py` at **207** (the main checkout sees more archive files on disk than are tracked, which is the whole reason worktree totals are not comparable to main totals).

ISSUE-103's squash adds `tests/test_red_gate_scoping.py` (**41** collected, absent from main) and modifies `tests/test_verify_checkpoint.py` with fixture-string changes only, which the worktree measurement confirms do not move its count (**145** on main, **145** in the worktree). `test_sprint_queue.py` is untouched, so main keeps its 207.

**Predicted main after the squash: 2675 collected = 2674 passed + 1 skipped.** The one skip is the pre-existing environmental `mknod` character-device permission in `tests/test_kit_telemetry.py`.

The worktree's own 2656/2657 must NOT be expected on main — the −18 archive-parametrization gap runs the other way once the code is on the main checkout. If the smoke lands on 2656 rather than 2674, that is the signal that something merged wrong, not that the arithmetic drifted. Any other number than 2674 gets investigated before `Status: done` is written, not after.

## Review attempt 2 — ISSUE-103 / PR #150 at `1a68895` — all 12 checkpoints PASS, verdict REWORK. ESCALATED to `waiting` / `review-rework`.

**The binding escalation condition is met and is honoured without re-litigation.** It was recorded twice before this review was dispatched: *"if review 2 still shows a High, ISSUE-103 goes to `waiting` / `review-rework` and stops for a human. No second rework."* Review 2 returned **7 High / 7 Medium / 15 Low**. ISSUE-103 therefore **does not ship**, and no second rework is dispatched. Attempts moves to **2**; both attempts were checkpoint-passes-with-findings rather than checkpoint failures.

All twelve review checkpoints exited **0** (`checkout`, the five Figma phases plus `ui-review` auto-skipping with their literal skip messages for `UI: false`, `test`, `test-quality`, `debt`, `review`, `push`). No environmental failure; ISSUE-099 did not bite. The reviewer committed **only** `docs/review_notes/ISSUE-103.md` (`d0fac1f`) — verified by team-lead: `git diff 1a68895..HEAD --name-only` names that one file, `scripts/verify_checkpoint.py` is blob `64400d54…` in both commits, the worktree is clean, and the notes carry **exactly one** `## Review Subject` block, so the duplicate-block wedge did not recur.

**F1 and F2 ARE genuinely closed, and that is not in dispute.** The reviewer reproduced both at the real consumer on repos it built, in both directions, and replayed them against the pre-rework commit to establish they were live before. It also confirmed the forbidden "restrict the delta to tracked paths" route was not taken, and that moving the F2 check back inside `if not all_test_files:` is killed by three tests — position pinned, not merely presence. That matches this instance's own matrix exactly.

### The review ran on the PRIMARY path, not degraded — the first time this sprint

`decide` returned **`delegated` for both dimensions**, not the `context-unreachable` every previous review hit. The runtime `/code-review` echoed **85693 bytes** and **sha256 `71dbb9b4…`**, `delegate` exited 0 ("echo verified"), and `record-subject` exited 0 with `verified_dimensions: code`. The security dimension degraded with `reason=inline-attempt-failed`. No receipt was forged.

**Those echoed figures are byte-identical to the ones this instance measured before dispatch, and the reviewer was given neither.** Full `ce44206..1a68895` = 85693 / 4 / `71dbb9b4364461850fdff53f8d902d1600c88c34c1cacad8314ec25c9812a77b`; product-only 71565 / 3 / `3d1c637a…`. Three independent collections of the same subject agreeing — team-lead's, the reviewer's, and the runtime skill's echo — which is the only form of agreement that means anything here. It also means **ISSUE-096's apparatus did its job on a live review for the first time**: the binding engaged on the delegated path, which review 3 of ISSUE-096 itself could not exercise.

### The four new Highs — ADJUDICATED BY TEAM-LEAD, not relayed

A sub-agent's narration of its own probe has been unreliable repeatedly this session, so the two that execution can settle were reproduced on repos this instance built, and the two whose mechanism is structural were traced in the committed code.

**H1 — whole-stdout parsing forges attribution. CONFIRMED BY EXECUTION. This is ISSUE-103's own defect, reopened.** `_PYTEST_SUMMARY_RE` is applied to the whole of `result.stdout`, not to the `short test summary info` section its own docstring names as the oracle — and a failing test's captured stdout is echoed at column 0 by default. Team-lead's own construction: `main` carries `addopts = "extra_tests/test_extra.py"`, that unrelated test prints one line `FAILED tests/test_new.py::test_new_feature - forged` and then fails; the branch adds **only a passing test and changes no configuration**.

```
GROUND TRUTH — the branch's own test alone: tests/test_new.py PASSES
GATE:  PASS: RED phase — the branch's own tests fail as expected (exit 1) — failing: tests/test_new.py
exit=0        <- an unrelated failure certifies RED, laundered through a forged attribution
```

This defeats precisely the route the hazard note advertises as refused. **The provenance is the most important part and it generalises beyond this issue:** review 1 filed this exact root cause as a **Medium**, on the explicit ground that *"the verdict is driven by the exit code, so this cannot flip the gate — which is why it is Medium and not High."* The F1 fix then made **attribution drive the verdict**, which invalidated that rationale — and the severity was never re-derived. Worse, the rework *refactored* the parse into `_blamed_test_files` and widened it to two call sites per verdict while leaving the regex byte-identical. **A deferred finding's severity rationale can expire when the code it was conditional on changes, and a refactor that preserves a defect verbatim can promote it.** That is a new lesson, not an instance of an existing one.

**H3 — forced colour defeats the `^`-anchor and refuses every genuine RED. CONFIRMED BY EXECUTION.** No project configuration is needed; a single inherited environment variable suffices. Team-lead's own control-and-probe pair on one repo with a genuinely failing branch test:

```
control (no colour forced) :  PASS: RED phase — … failing: tests/test_branch_feature.py   exit=0
FORCE_COLOR=1              :  FAIL: RED phase — pytest exited 1 but reported no test failure at all   exit=1
PY_COLORS=1                :  FAIL: RED phase — … reported no test failure at all                     exit=1
```

The control passing is what makes the probe valid. This is a **new over-refusal introduced inside the guard this instance helped build**, and the diagnostic it prints names two causes that are both wrong ("a coverage threshold … or pytest not being installed"). It fails CLOSED, which is better than the fail-open it replaced, but `FORCE_COLOR` is set by default in a number of CI runners and developer shells, so the blast radius is wide. The reviewer found a sibling route this instance had not considered — `addopts = "--no-summary"`, which `-rfE` does **not** override — with the same over-refusal and the same wrong stated cause.

**H2 — the both-legs predicate lets a shallow clone pollute the executed scope. CONFIRMED STRUCTURALLY** by reading the committed code rather than by execution, and stated as such. `_delta_base_unresolvable` requires *both* "no fork point" *and* "`<base>` does not resolve", so the standard CI `fetch-depth: 1` shape — no merge-base but `main` resolves — falls through. `_changed_files_vs_base` then takes `diff_base = _merge_base(...) or base` and runs a **two-dot** `git diff --name-only main`, which reports files **main** changed after the fork point. So the gate executes, and can attribute to, files the branch never touched. This is a hole in the F2 predicate this instance adopted: the sprint log above reads the two-legged requirement as a feature ("so it cannot fire on a merely-stale base"); it is also the bypass.

**H4 — a `develop`-default repository can no longer pass the gate at all. CONFIRMED STRUCTURALLY.** `_default_branch()` returns the `origin/HEAD` basename, so a repo defaulting to `develop` with no local `develop` ref fails both legs, and the hoisted refusal now fires **unconditionally**. Before the hoist the same repo proceeded, because the check only ran when the delta was empty. **The F2 hoist is correct for the property it protects and it converted a narrow case into a permanent block** — the precise cost of hoisting a refusal upstream, which this instance did not probe for.

### The npm items — the reviewer's conclusion is right, its stated mechanism is WRONG, and both halves are recorded

This is the one place a reviewer claim attacked code **this instance wrote**, so it was measured rather than conceded or dismissed. The reviewer reported that "npm forwards its script's code verbatim: I measured 1/4/5/124/127 passing through", which would falsify the comment this instance added ("127 is never a test failure for either runner").

Measured on **npm 11.5.2**, `{"scripts": {"test": "exit N"}}`:

| construction | npm exit |
|---|---|
| script `exit 1` / `4` / `5` / `9` / `42` / `124` / `127` | **1 in every case** |
| test-script binary absent (`sh: command not found`) | **127** |
| `sh -c 'exit 127'` | **127** |
| a real failing `node:test` suite | **1** |
| `node --test` with nothing to run | **1** |

**npm does NOT forward exit codes verbatim** — it collapses a script's own non-zero code to 1, and 127 surfaces only when the command could not be executed. So the claim that refutes this instance's comment **does not reproduce**, and the 127 branch is sound: no construction in which tests genuinely ran and failed yields 127.

**But the reviewer's conclusion holds anyway, for a different reason, and the finding lands.** Its exit-9 observation is corroborated: a runner that **rejects the injected `--passWithNoTests` and runs nothing** exits non-zero (9 in the shapes measured here) and is still certified RED. So the hazard note's bound that this instance wrote — *"npm's residual hole is therefore exactly 'nothing ran AND npm chose exit 1', not every no-run route"* — is **FALSE**: the hole is broader than exit 1. That is "a disclosed residual is a CLAIM — measure it, or the disclosure itself becomes the defect", applied to this instance's own disclosure, and it is the correct finding even though its stated mechanism is not. Recorded both ways deliberately, because the previous iteration had to correct a reviewer finding that was right for the wrong reason and noted that such findings get inherited as fact.

### Team-lead's own matrix was NARROWER than the reviewer's, and that matters

This instance reported **8 mutants, zero survivors**. The reviewer ran **25 mutants, 23 killed, 2 survived** — and one survivor is in surface this instance added. **M20** changes npm's `no_run_codes` from `()` to `(4, 5)`, an over-refusal that would break npm's legacy contract, and **it survives**: the legacy npm mode that review lesson 8 requires to be pinned is pinned only for exit 1 and for the 127 refusal, while exits 4 and 5 are unpinned in the npm direction. The second survivor, M14, widens the attribution call from `scoped` to `all_test_files`; the reviewer could not construct a behavioural difference and recorded it honestly as an unpinned narrowing rather than a defect.

So "zero survivors" was true of the matrix this instance built and **not** of the guard's actual pinning. A matrix is only as strong as its mutant set, which is the same rule as "a count is not a set" one level up. Recorded as a correction to this instance's own earlier claim in this file.

### Two further Highs worth naming for the human, both with review-1 provenance

- **Argument injection through the scope splat.** `cmd` is built by splatting `*scoped`, and `scoped` derives from a set that includes `git ls-files --others`, so repository filenames decide argv content. There is no *command* injection (`subprocess.run` in list form, no `shell=True`), but a directory named `-p no:cacheprovider` — a path the kit's own `test_dir_pattern` accepts — is consumed by pytest as the `-p` value, after which **pytest collected the whole suite and exited 1**, not the exit 4 review 1 cleared this as. The scoping mechanism AC-1 exists for is bypassed while the gate's own `Scope was:` line reports a scope that was not applied. Review 1 filed the root cause as a Low with the same fix (`--` before the paths); it was not applied.
- **A polyglot repository can never pass the RED gate.** `_, has_js = _detect_test_runners(wt)` discards `has_python`, and the branch keys on `has_js` alone, which is true whenever `package.json` declares `scripts.test` — ordinary in a Python repo with a JS frontend. A branch whose changed test files are all `.py` then reaches the "none that `npm test` can execute" refusal with no route to a RED pass. Not itself a regression, but **the new code forecloses the fix** by throwing `has_python` away. The GREEN gate disagrees with the RED gate here: `verify_implement_test` runs both runners.

### Suite — the reviewer's decomposition is independent, agrees, and uses a better method

**2616 → 2657 collected (+41)**, every one of the 41 in the single new file, and **zero of the 73 shared files changing by even one case**. `tests/test_verify_checkpoint.py` is **145 in both trees** despite its `+23/−4` diff, because the node-id set is byte-identical and the diff only introduces `_RED_FAILED_SUMMARY` and substitutes it into four fixture bodies — which independently confirms this instance's own judgement that the fixture change was a faithfulness upgrade and not a count-moving edit.

The reviewer materialised its baseline with `git archive ce44206` into a separate copy rather than comparing against the main checkout, which is **a better technique than the one this instance used**: it sidesteps the `test_sprint_queue.py` archive-parametrization gap entirely instead of subtracting it, and it confirmed the two compared trees carry the identical 5 selected docs so that file is legitimately 189 in both. Adopted as the method for future deltas.

### Disposition

ISSUE-103 is **`waiting` / `review-rework`**, Attempts **2**, PR #150 left **OPEN** at `d0fac1f`, branch and worktree left intact for the human. Nothing was merged, no branch was deleted, and `Status` in `issues.md` remains **`doing`** — `Status: done` is written only after `gh pr view` reports MERGED, so **ISSUE-105 did not bite for the fourth time this sprint**.

**No follow-up carrier issues were filed for these findings, and that is a decision rather than an omission.** All seven Highs live in ISSUE-103's own module and in the surface its own rework set governs, so ISSUE-103 itself is the durable carrier and splitting them out would fragment a single rework across several ids. The handover for the human is the rework set below, plus `docs/review_notes/ISSUE-103.md` (7 High / 7 Medium / 15 Low) which is committed and pushed.

**Rework set for the human, in the order the reviewer's own fix verification supports:** slice the parse at the `short test summary info` header (kills both forgery routes while preserving genuine and collection-error REDs — verified by execution); pass `--color=no` (overrides both `addopts` and the environment — verified) and handle `--no-summary` honestly; put `--` before the scope paths (verified to make pytest accept a dash-leading file); make `_delta_base_unresolvable` single-legged or make the fallback a three-dot diff; stop discarding `has_python`; and either widen the npm no-run refusal beyond 127 or restate the hazard note's bound to what is actually true. The last item is this instance's own defect and is named as such.

**This sprint's theme held all the way down.** Three gates were found not to gate; ISSUE-103's repair of one of them introduced a fresh fail-open *inside the new guard* at review 1, and its repair of **that** introduced a forgeable attribution and two new over-refusals. The defect class this sprint exists to remove reproduced at every layer, including in work this instance did itself — which is the strongest available argument for the escalation rather than a third attempt from inside the loop.

## Review attempt 2 — ISSUE-102 / PR #151 at `b557abf` — all 12 checkpoints PASS, verdict REWORK. ESCALATED to `waiting` / `review-rework`.

**The binding escalation condition is met and honoured.** Recorded before this review was dispatched: *"if review 2 still shows a High, ISSUE-102 goes to `waiting` / `review-rework` for a human. No second rework."* Review 2 returned **2 High / 8 Medium / 12 Low**. ISSUE-102 therefore **does not ship**, and no second rework is dispatched. Attempts moves to **2**; both attempts were checkpoint-passes-with-findings rather than checkpoint failures.

All twelve review checkpoints exited **0**, each reported literally (`checkout`, `figma-compliance`, `computed-styles`, `structural-match`, `layout`, `visual-diff`, `ui-review`, `test`, `test-quality`, `debt`, `review`, `push`), with the `UI: false` skips confirmed by their literal messages rather than assumed. Worth noting as a methodological catch: the reviewer's **first pass misread those exit codes through a pipe** — reading `tail`'s status instead of pytest's — and it detected and re-measured that itself. That is the same error class this instance hit earlier in this session when parsing collection counts through `tail | head`, and it is worth carrying forward: **an exit code read through a pipe is the pipe's, not the command's.**

The reviewer committed **only** `docs/review_notes/ISSUE-102.md` (`5a285c7`) — verified by team-lead: `git diff b557abf..HEAD --name-only` names that one file and `scripts/spec_gate.py` is blob `85e63ab0…` in both commits.

### What the rework got right, and it is the thing the issue exists for

**Satisfiability is confirmed in BOTH directions, 16/16 cells**, on fixtures the reviewer built from scratch: a genuinely-specced issue returns `proceed`, an unspecced one returns `auto_spec`/`hold`, across both call sites (the step-0b/0c CLI and the in-process `decide()` API) × both CWDs × sprint and non-sprint. On the identical satisfiable fixture the pre-PR gate returns `auto_spec` from **both** CWDs — so defect and repair were each reproduced independently. The cross-checkout `proceed` names which checkout supplied the field and which held the file. **Both mandated mutants die:** R1 by all three `TestUnstattableRootIsRefusedNotFatal` tests, R3b by 18 tests, and the sharper **R3b-prime** (id dropped only at the sibling call site) by 12 including the new decoy test. `gen_skills.py` re-run for real → `git status --porcelain` **empty**, so the generated `SKILL.md` matches its committed template. Review lesson 8 holds: mutant N5 (drop the `Spec-Required` scoping) dies via 6 tests including 3 legacy full-dict pins.

That is the issue's own goal met. The verdict turns on something else.

### High 1 — the rework fixed ONE site of a defect class that exists at FOUR. ADJUDICATED BY TEAM-LEAD.

Review 1's rework item was "move the regular-file stat inside `_contain`'s guard". The rework did exactly that and no more — but the same shape (an I/O call whose raising set exceeds its guard's except-tuple) occurs at four sites, and three are **strict regressions**: base exits 0, head exits 1 with a traceback, outside the module's own documented exit contract of {0, 2}, and step 0c has **no branch for a traceback**, so when it fires it wedges the pipeline rather than degrading.

Three of the four were confirmed by **reading the committed code directly**, and the fourth by **execution**:

| site | call | guard today | missing | status |
|---|---|---|---|---|
| `:161` `_git` | `subprocess.run` | `(FileNotFoundError, TimeoutExpired)` | `PermissionError`, ENOEXEC `OSError` | **confirmed structurally** — `PermissionError` is not a `FileNotFoundError`, so a present-but-unusable `git` escapes. Regresses the legacy co-located class AC-3 pins, which main never called git for at all. |
| `:197` `checkout_roots` | `candidate.is_dir()` | **no try/except at all** | `OSError` EACCES / ENAMETOOLONG | **confirmed structurally** — bare `if not candidate.is_dir(): continue`, and `is_dir()` raises on the same two errno classes as `is_file()`. |
| `:233` `_contain` | `.resolve()` | `(OSError, ValueError)` | `RuntimeError` on ELOOP | **CONFIRMED BY EXECUTION** (below) — and this is the rework's own line. |
| `:258` sibling field read | `candidate.is_file()` | sits OUTSIDE the `try`, which wraps only `parse_issue` | `OSError` EACCES / ENAMETOOLONG | **confirmed structurally** — *the identical defect the rework was dispatched to fix*, at a second site, on the primary `auto_spec` path. |

The ELOOP leg measured on this interpreter rather than assumed, because the previous iteration was burned by a wrong prior about pathlib's raising behaviour in this exact module:

```
python 3.12.7
Path.resolve()               -> RuntimeError: Symlink loop from '…/a/x.md'
Path.resolve(strict=False)   -> RuntimeError: Symlink loop from '…/a/x.md'
   caught by (OSError, ValueError)?  False
Path.is_file()               -> returned False   (so is_file is NOT the raiser here)
```

So a symlink loop in **any** checkout escapes `_contain`'s guard as an uncaught `RuntimeError`. The docstring the rework wrote at `:225-227` is accurate about EACCES/ENAMETOOLONG and silent about ELOOP, which is why the guard's tuple looks complete and is not.

**The generalisable point, and it is review lesson 8 turned on the fix rather than on the feature:** review 1 scoped its rework item to one *line* when the finding was a *class*. `:197` and `:258` are precisely the guards review 1 mutated as **R2/R4**, watched survive, and triaged as "unexercised guards → carriers". They are not unexercised; they are fatal. A surviving mutant triaged as "merely unpinned" deserves the question "what happens if this guard is actually reached", and that question was not asked.

**Live blast radius is zero today**, measured rather than assumed: **0 decision divergences** across all 26 `Spec-Required=true` issues from both CWDs. The failures are also fail-**loud** (traceback, exit 1), not fail-open. That bounds the urgency; it does not change the verdict, because the gate runs at `/implement` step 0 for every `Spec-Required` issue and a non-JSON exit 1 is not one of the four decisions the skill knows.

### High 2 — the untrusted `Spec:` value forges the `INCOMPLETE` control marker. CONFIRMED BY EXECUTION.

`INCOMPLETE_MARKER = "checkout enumeration INCOMPLETE"` (`:94`) is the string step 0c greps `reasons` for to learn that the enumeration was incomplete and that an `absent` verdict is therefore not authoritative. `_spec_present_reason` (`:319`) **bare-interpolates** the registry's `Spec:` value into a reason: `f"Spec-Required=true and SPEC exists at {spec_path}"`. Team-lead's own probe, with a real SPEC file whose name embeds the marker and a healthy git repo whose enumeration genuinely COMPLETED:

```json
{
  "decision": "proceed",
  "reasons": ["Spec-Required=true and SPEC exists at docs/checkout enumeration INCOMPLETE (forged) SPEC.md"],
  "spec_path": "docs/checkout enumeration INCOMPLETE (forged) SPEC.md",
  "sprint_mode": true
}
```

exit 0, and the marker is in `reasons` with the enumeration complete. **This is new in this PR** — main emits a fixed string and never embeds the value. The PR hardened the *path* use of this untrusted value and, in the same commit that made prose a control channel, left the *prose* use unhardened. Exactly 2 bare interpolations against 2 `!r`-quoted ones, so the module already knows the right idiom and applies it inconsistently.

Severity nuance recorded rather than glossed, since it cuts in the issue's favour: the direction demonstrated forges a **false INCOMPLETE** on a valid `proceed`, which makes a consumer distrust a good answer — unpleasant but fail-safe. The dangerous dual (suppressing a genuine marker) was not demonstrated by either party. What makes it a High regardless is the structural fact, which is review lessons 5 and 6 exactly: workspace-persisted state a gate reads is untrusted input, and a control signal that untrusted input can synthesise is not a control signal.

### The degraded-path judgement the reviewer flagged for me to overrule — I endorse it

`decide --invocation-tools present` returned **`path=delegated` for both dimensions**, not the predicted `context-unreachable`, because the reviewer did observe a `Skill` tool listing `code-review`/`security-review` and **reported that honestly instead of reporting the expected shape**. It then declined to invoke them, on the ground that those skills load into its *own* context, so the resulting echo would be **self-attestation** rather than independent verification. It ran both dimensions as separate-context reviewers with the subject pinned and echoed, emitted `review_degraded_path_used --reason inline-attempt-failed` for each, forged no receipt, and pasted no digest. `record-subject` consequently refused with **`reason=verification-missing`, exit 2** — correct — and the notes carry **zero** `## Review Subject` blocks.

**That reasoning is right and it is ISSUE-096's own distinction applied unprompted: shape validation is not provenance.** Producing a receipt by invoking a skill inside one's own context would have satisfied the gate while delivering nothing the gate exists to guarantee. Endorsed, not overruled.

**An asymmetry worth carrying to ISSUE-106.** The ISSUE-103 reviewer reached a genuinely delegated path and its echo (85693 / `71dbb9b4…`) matched team-lead's independent measurement byte-for-byte, which is positive evidence the diff was really read. The ISSUE-102 reviewer, offered what looked like the same affordance, judged it self-attesting and refused. Both are defensible and they diverged on the same repo within the same hour, so **`decide`'s `delegated` verdict does not by itself distinguish independent delegation from self-invocation** — the distinction lives in whether the echo comes from a context that could not have seen the answer. That is a sharper statement of ISSUE-106's open question than the issue currently carries, and it came from the two reviews disagreeing rather than from either one alone.

### Scope, and lesson 14 for a second consecutive cycle

**15 of 44 added executions (34%) cover surface no AC asks for — and both Highs live there.** The issue did request a DECISION (`issues.md:6297`), so lesson 14 is live, and this is now its second consecutive empirical confirmation on this issue. The rework itself was properly bounded: **+14/−9** non-comment lines, **0** new env reads, **0** new decision literals, **0** marker-constant changes, bucket **C** declared and correct.

### Mutation — 9 survivors, and one Medium is a trap worth naming

`R2, R4, R5, R9, A1` (review 1's five, re-confirmed) plus `N8` (`registry_name` hard-coded), `N9` (the lesson-12 ordering), `N10` (non-regular-file refusal), `S1` (the marker constant). Killed: `R1, R3b, R3b-prime, R6, N1–N7`. `R6` is disclosed as a **weak** kill — it pins "git must work", not the constant it claims to.

Two Mediums deserve the human's attention ahead of the rest:
- **Review lesson 12 is UNHELD and that was proven by mutation**: hoisting the step-0c gate re-run above the `/spec` output leaves the suite green, so the ordering the lesson requires is pinned by nothing. (Review 1 reported lesson 12 as holding; it checked the position, not its pinning.)
- **The PR's own Over-Engineering note recommends deleting the `:258` guard**, and doing so hangs the gate on a planted FIFO (rc=124). A minimality recommendation that would reinstate a known hazard class is the ISSUE-096 `M19` shape — the non-blocking-open lesson — arriving as *advice inside the PR*. The minimality axis correctly declines 3 of the PR's 5 proposed cuts; this is the one that mattered.

### Negative results genuinely hunted, all clean

Prunable-by-deletion, locked worktree, detached HEAD, worktree paths with spaces, symlinked `docs/` escaping, absolute / `..` / NUL `Spec:` values, missing git → `INCOMPLETE`, `_git` argv injection, git-config-driven execution, lock-reason injection, branch-name injection, `registry_name` traversal, a 13-case containment matrix (all REFUSED), `_spec_present_reason` None-deref, and `Path` reaching `json.dumps`. The previously-triaged carriers were re-confirmed as carriers.

### Measurements

Subject, with **no digests supplied** to the reviewer: **80003 bytes / 5 headers / `2b4d25c4acc2eece…`**; excluding its own notes **54651 / 4 / `b662025d07362fe2…`**. These match team-lead's independent measurement exactly, and the reviewer reports **five** independent agreements (its own `ce44206..HEAD`, `collect`'s `4466d7c...b557abf`, both dimension echoes, and `record-subject`'s re-collection).

Suite **2659 passed / 1 skipped / 0 failed** in 74.9s; the skip is the known `mknod` one and **ISSUE-099's budget went unused**. Collection decomposed by set: main 2634 vs worktree 2660, `+26 = +44` (`test_spec_gate.py` 20→64, the PR's own) `−18` (`test_sprint_queue.py` 207→189, environmental — `tests/test_sprint_queue.py:1821` globs `docs/sprint_state*.md`, 11 such files in the main checkout against 5 in the worktree, × 3 parametrized tests). Reconciles exactly, and the reviewer located the glob line rather than inheriting the arithmetic.

### Disposition

ISSUE-102 is **`waiting` / `review-rework`**, Attempts **2**, PR #151 left **OPEN** at `5a285c7`, branch and worktree intact for the human. Nothing merged, no branch deleted, `Status` in `issues.md` remains **`doing`** — so **ISSUE-105 did not bite here either**.

**No follow-up carrier issues were filed for these findings, by the same reasoning as ISSUE-103:** both Highs live in `scripts/spec_gate.py`, inside the surface ISSUE-102's own rework set governs, so the issue itself is the durable carrier and splitting them would fragment one rework across several ids. The handover is the rework set below plus the committed `docs/review_notes/ISSUE-102.md`.

**Rework set for the human:** fix the defect class at all four I/O sites rather than one (`_git`'s tuple, `checkout_roots:197`'s absent guard, `_contain:233`'s missing `RuntimeError`, and the `:258` stat outside its try) and pin each in the disarm direction through the step-0c CLI; `!r`-quote the two bare `spec_path` interpolations so the untrusted value cannot synthesise `INCOMPLETE_MARKER`, and pin the marker constant on both sides so `S1` dies; add the lesson-12 ordering pin so `N9` dies; and **decline** the PR's own minimality recommendation to delete the `:258` guard, recording why (the FIFO hang).

## Escalations — both target issues, handed to a human with their rework sets

Neither escalation is a failure to execute. Both are **pre-registered conditions firing exactly as written**, which is the outcome the conditions existed to produce.

| issue | PR | tip | state | Attempts | reason |
|---|---|---|---|---|---|
| ISSUE-103 | #150 OPEN | `d0fac1f` | `waiting` / `review-rework` | 2 | review 2: 7 High (4 new). H1 + H3 reproduced by team-lead by execution; H2 + H4 confirmed structurally in the committed code. |
| ISSUE-102 | #151 OPEN | `5a285c7` | `waiting` / `review-rework` | 2 | review 2: 2 High. H2 reproduced by team-lead by execution; High 1 confirmed at 3 of 4 sites structurally and its ELOOP leg by execution. |

**Sprint scope reached 1 of 3.** ISSUE-096 shipped at `f3d4ed6`. ISSUE-102 and ISSUE-103 both reached `reviewed` with green checkpoints and then stopped on their own escalation conditions rather than shipping.

**Nothing is left mid-flight and nothing needs cleanup to be safe.** Both branches are pushed and fast-forward-only (no force-push anywhere this iteration), both worktrees are clean and intact, both PRs are open, no branch was deleted, and **`issues.md` was never written** — `Status` is still `doing` for both, with `validate_issues.py` at **15 violations / exit 0**, unchanged from the pre-recorded baseline, and neither issue named in any violation. **ISSUE-105 did not bite on either issue**, for the fourth and fifth observations this sprint: `Status: done` was never written, because it is only written after `gh pr view` reports MERGED. The worktrees are deliberately NOT cleaned up — they hold the reviewed trees and the human will need them.

### Why no second rework was attempted, stated so it is a decision and not an omission

The team-lead contract permits shipping with unresolved Highs carried as follow-up issues, and all twelve checkpoints passed on both issues, so `reviewed` was available on both. It was declined on both, for the reason the predecessor issue established and this iteration now has direct evidence for:

**ISSUE-103's own repair history is the argument.** The original defect was a gate that did not gate. Review 1 found that its fix introduced a fresh fail-open *inside the new guard*. The rework for that — which this instance adjudicated, completed and committed — introduced a **forgeable attribution** (H1, the original defect reopened through a laundered channel) and **two new over-refusals** (H3's `FORCE_COLOR`, and the `--no-summary` sibling). Three layers deep, the same class each time, including in surface this instance wrote itself. A third attempt from inside the same loop is not a plan; it is the fourth instance waiting to happen.

**ISSUE-102's is the dual.** Its rework was *correct* — satisfiability confirmed 16/16, both mandated mutants dead, bounded at +14/−9 lines. It still failed review, because review 1 had scoped a **class** of defect to a single **line**, and the three unfixed siblings are strict regressions. Dispatching another single-item rework would repeat the scoping error that produced this verdict.

### No follow-up carrier issues were filed, and that is also a decision

Every High on both issues lives inside the module and the surface its own rework set governs — `scripts/verify_checkpoint.py`'s red verifier for ISSUE-103, `scripts/spec_gate.py` for ISSUE-102. The issues are therefore their own durable carriers, and splitting their Highs into new ids would fragment one rework across several and lose the provenance that makes each finding legible. The handover is the two rework sets recorded above plus the two committed review artifacts: `docs/review_notes/ISSUE-103.md` (7 High / 7 Medium / 15 Low) and `docs/review_notes/ISSUE-102.md` (2 High / 8 Medium / 12 Low). Carrier ids **ISSUE-110 onward** remain unallocated and the current maximum is still **ISSUE-109**, so whoever files next can allocate cleanly.

### Three findings that outlive these two issues, and one of them needs an id to survive

1. **A deferred finding's severity rationale can expire when the code it was conditional on changes — and a refactor that preserves the defect verbatim can promote it.** ISSUE-103's H1 was filed at review 1 as a Medium on the explicit ground that "the verdict is driven by the exit code, so this cannot flip the gate". The F1 fix made attribution drive the verdict, which voided that rationale; the rework then refactored the parse into a new helper and widened it to two call sites while leaving the regex byte-identical. Nobody re-derived the severity. This is a new lesson rather than an instance of an existing one, and the reviewer recorded it to native memory.
2. **A surviving mutant triaged as "merely unpinned" deserves the question "what happens if this guard is actually reached".** ISSUE-102's review 1 watched R2 and R4 survive and filed them as unexercised-guard carriers. Review 2 established they are not unexercised, they are **fatal**. The triage category "unexercised guard" quietly assumed the guard's absence was harmless.
3. **`decide`'s `delegated` verdict does not distinguish independent delegation from self-invocation — and this needs an id.** The two reviewers, on the same repo within the same hour, were offered what looked like the same affordance and diverged: ISSUE-103's reached a genuine delegated path whose echo matched team-lead's independent digest byte-for-byte, while ISSUE-102's judged the same `Skill` affordance self-attesting (the skills load into its own context, so the echo would attest to itself) and refused, correctly. The distinction that matters is **whether the echo comes from a context that could not have seen the answer**, and `decide` does not currently model it. That is a sharper statement of ISSUE-106's open question than ISSUE-106 carries, it was only visible because two reviews disagreed, and it will not be reproducible after the fact. **It is recorded here and nowhere durable.** Per review lesson 15 — a deferred finding is only real if it has a durable carrier, and a sprint_state file that is archived and reset at the sprint boundary is not one — this needs to be added to ISSUE-106 or filed as ISSUE-110 to be real. Named rather than filed because it is not Critical or High and because filing it was outside this dispatch's scope; flagged explicitly so the omission is visible rather than silent.

### Measurement corrections this iteration made to its own earlier claims

Recorded because a log that only accumulates confirmations is not a measurement record:

- **"8 mutants, zero survivors" was true of the matrix this instance built and false of the guard's actual pinning.** The reviewer's 25-mutant battery found 2 survivors, one (`M20`) in surface this instance added — npm's legacy contract is pinned for exit 1 and 127 but not for exits 4 and 5. A matrix is only as strong as its mutant set.
- **The hazard-note bound this instance wrote is false.** "npm's residual hole is exactly 'nothing ran AND npm chose exit 1'" — the hole is broader; a runner rejecting the injected `--passWithNoTests` runs nothing and is still certified RED. This instance's own disclosure became the defect, which is the rule it had just applied to the inherited work.
- **The reviewer's refutation of this instance's 127 branch does NOT reproduce.** It claimed npm forwards script exit codes verbatim (1/4/5/124/127). Measured on npm 11.5.2: npm collapses a script's own code to **1**, and 127 surfaces only when the command cannot be executed; a real failing `node:test` suite returns 1. So the 127 branch is sound and the finding is right for a different reason — recorded both ways, because the previous iteration noted that findings correct for the wrong reason get inherited as fact.
- **The "concurrent suites damage the tree under review" constraint was overstated** and cost two iterations of serialisation. Every `.worktrees/` reference in `tests/` is rooted at a throwaway path; only CPU contention is real. The two reviews ran in parallel without incident.
- **An exit code read through a pipe is the pipe's, not the command's.** This instance hit it parsing collection counts through `tail | head`; ISSUE-102's reviewer hit it reading checkpoint exit codes through `tail` and caught itself. Worth a permanent place in the measurement discipline.
- **A method worth adopting:** ISSUE-102's and ISSUE-103's reviewers both materialised their baseline with `git archive <merge-base>` into a separate copy instead of comparing against the main checkout. That sidesteps the `test_sprint_queue.py` archive-parametrization gap entirely rather than subtracting it, and ISSUE-102's reviewer located the responsible glob at `tests/test_sprint_queue.py:1821` rather than inheriting the arithmetic.

### What a human needs to decide

Both issues are one scoped rework away from shippable, and both rework sets are written above with the fixes the reviewers verified by execution. The judgement call is not technical — it is whether to rework these two inside this sprint at all, given that ISSUE-103 has now produced a new defect of the same class at each of three successive layers, and that the sprint's own thesis ("the pipeline's own gates do not gate") has been confirmed more thoroughly by the attempt to fix it than it was by the original three findings.
