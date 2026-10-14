# SPEC-081: Gate the gates — enforce paired disarm + composite evidence at a scripted review phase

> Linked Issue: ISSUE-081
> Status: `accepted`
> Date: 2026-10-14
> Author: claude-dev-kit (implement phase, dogfooding)

## Problem

"A newly added defence fails OPEN" has been measured at High severity in four consecutive sprints — ISSUE-068/PR #121, ISSUE-076/PR #128, ISSUE-078/PR #133, ISSUE-072/PR #135. In every instance the gate's *arm* direction was tested and the *disarm* direction was not: ISSUE-078's `sprint_status_is_running` returned `valid: true` / exit 0 for 22 of 23 inputs that literally contain the line `- Status: running`, while `next-action` on the same bytes dispatched three out-of-scope issues. The native-memory review lesson that records this pattern already auto-recalls into every review, and the pattern recurred **twice after** the lesson existed — so the open question this SPEC must answer is not *what the rule is* but *what seam can enforce it without being another instruction a reviewer may or may not act on*.

## Context

Bounding constraints, all quoted from the repo at `b4dda36` (plugin 0.7.0):

- `scripts/verify_checkpoint.py` already owns the review phase registry: `VERIFIERS` maps `("review", <phase>)` to a verifier, and `ADVISORY_PHASES` enumerates the non-blocking tier. The blocking/advisory split is itself pinned by `tests/test_verify_checkpoint_contract.py`, so a phase cannot be demoted to advisory without a failing test. This is the only place in the kit where a review obligation is an **exit code** rather than a sentence.
- `skills/review/SKILL.md` is **generated** — `scripts/gen_skills.py` renders it from `skills/review/SKILL.md.tmpl`. Any contract clause must be written in the template; `tests/test_gen_skills.py` pins that the generated file matches.
- The review path's correctness/security dimensions are delegated to runtime `/code-review` and `/security-review` (SPEC-019/066). Those are *models*, reached through `scripts/review_context.py decide`, and on CC 2.1.224 a `Skill` grant does not imply provisioning (ISSUE-072, `docs/cc_feature_matrix.md`). Any obligation that lives only inside a delegated model's prompt can silently not run at all.
- The motivating evidence is reproducible without invention: ISSUE-078 shipped as PR #133 (squash `3b716c7`); its pre-fix tree is `d328a6c^` and its post-fix tree is `d328a6c`, both branched from `a4338e2`. `git diff a4338e2..d328a6c^` and `git diff a4338e2..d328a6c` are the two fixtures ISSUE-081's AC-1/AC-2/AC-4 name. `actions/checkout@v4` in `.github/workflows/ci.yml` runs at the default `fetch-depth: 1`, so the fixtures must be **committed text**, not regenerated from git history at test time.
- Measured constraint on what the detector can know: the pre-fix and post-fix diffs are structurally near-identical at every coarse metric. Added test blocks referencing the gate: 7 vs 8. Consumer-driving blocks: 2 vs 2. Parametrized batteries with constant literal expectations: 3 vs 7. Both diffs already contain consumer-level refusal batteries (`test_ac2_rejected_boundary_is_refused_with_the_parsers_own_detail`, 6 cases, exit-code level). A naive "is there a variant battery / is a consumer driven / are both polarities asserted" rule **does not separate them**, so a rule built on those signals would pass the diff that shipped the fail-open.
- The one measured difference that *is* mechanical: the post-fix diff adds a battery of 8 input mutations carrying a **vacuity guard over the input** — `assert "- Status: running" in text` plus `assert "- Status: running" not in _meta_block(text)` — and asserts a constant consumer-level refusal across all 8 (`exit_code == sq.ROSTER_BOUNDARY_EXIT`, `out["valid"] is False`). The pre-fix diff has that vacuity guard in exactly one place, in a **single-case** test named `test_status_running_outside_meta_is_not_detected_and_is_not_refused` which asserts the *non*-refusal (exit 0, `valid is True`) — the fail-open, recorded as intended.

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line.

### Option A: Reviewer-prompt obligation

- **Approach**: State the requirement in `agents/reviewer.md` and in `skills/review/SKILL.md.tmpl` step 3.2 as a prose clause the reviewing model is instructed to apply, and record it as a native-memory review lesson so it auto-recalls.
- **Pros**:
  - Zero engine surface, zero new fixtures, zero added review wall-time.
  - Works identically on the primary (delegated) and degraded review paths.
- **Cons**:
  - This is the control condition and it has already been measured: the native-memory lesson existed before ISSUE-078 and ISSUE-072 and both recurred anyway.
  - On the primary path the correctness dimension is a runtime skill whose prompt the kit does not own, so the clause may never be read.
- **Trade-off**: +0 scripts, +0 test files, +0 s review time, and 0 of 4 measured instances detected — the lesson was live for 2 of the 4 and caught neither.

### Option B: Fold the requirement into the existing `review/test-quality` phase

- **Approach**: Extend `verify_review_test_quality` in `scripts/verify_checkpoint.py` so that, in addition to hollow-test detection, it computes the PR diff and fails when a gate-adding diff lacks paired evidence. No new phase, no new script, no SKILL template change beyond a sentence under step 4.5.
- **Pros**:
  - Reuses a phase that is already blocking and already runs on every review, so there is no new wiring and no risk of the phase being skipped.
  - Smallest diff of the three scripted options.
- **Cons**:
  - Couples two unrelated failure modes under one phase name: a hollow-test failure and a missing-disarm failure both print as `review/test-quality FAILED`, so the operator cannot tell from the phase which rule fired, and a future fix for one can mask the other.
  - `verify_review_test_quality` is already 45 lines of file-walking; adding ~200 lines of diff analysis to it makes the single largest verifier in the file the hardest to test in isolation.
- **Trade-off**: +~200 lines inside an existing 45-line verifier, +0 new phases, -1 independently diagnosable phase, and -1 independently skippable unit (the two rules can no longer be exercised separately in CI).

### Option C: A new blocking review phase `review/gate-evidence` backed by `scripts/verify_gate_evidence.py`

- **Approach**: A new standalone module exposes a pure `analyze(diff_text) -> Report` over unified-diff text plus a CLI (`--diff-file`; a `--range`/`--repo` variant was implemented and then **deleted** by the 2026-10-14 amendment — zero callers, zero tests, and it disagreed with the real consumer's merge-base semantics). `scripts/verify_checkpoint.py` gains `verify_review_gate_evidence`, registered as `("review", "gate-evidence")` and deliberately **absent** from `ADVISORY_PHASES`, so it is a blocking exit code. `skills/review/SKILL.md.tmpl` gains the contract clause and the checkpoint block; `agents/team-lead.md`'s review phase table gains the row. Because `analyze` takes diff text, the four fixture replays ISSUE-081's ACs demand are ordinary unit tests over committed fixtures.
- **Pros**:
  - The obligation is an exit code produced by a script, and the blocking tier is pinned by `tests/test_verify_checkpoint_contract.py` — it cannot be demoted to advisory, deleted from the registry, or softened to a warning without a failing test. That is the specific property Option A lacks.
  - Pure-function core means the mechanism is testable against the real pre-fix and post-fix diffs rather than against a hand-written imitation of them.
  - A failure names the gate symbol and `file:line`, so the finding is actionable without re-deriving the evidence trail.
- **Cons**:
  - +1 blocking gate on the review path: a false positive halts a review until an exemption is written.
  - The detector is syntactic. It cannot infer *input families*, which is why the attribution of a composite battery to a gate rides on the vacuity guard (see Trade-offs Accepted).
  - ~3.4k lines of committed fixture diff text.
- **Trade-off**: +1 blocking review phase, **+848 engine lines** in 1 new file (`wc -l`; the pre-implementation estimate written here was `+~240` and was wrong by 3.5x — corrected by the 2026-10-14 amendment, because a comparator that justified this decision has to be the measured number), +3 fixture files (~4.7k lines), +~0.3 s review wall-time, and 4 of 4 measured instances are gate-detected with the ISSUE-078 pair separating correctly (pre-fix → finding, post-fix → clean).

### Option D: PR-body self-attestation checklist

- **Approach**: A blocking check parses the PR body via `gh pr view --json body` and requires a `## Gate Evidence` section naming, per gate, the disarm test and the composite test.
- **Pros**:
  - ~25 lines, no diff analysis, no fixtures.
  - Forces the author to name the tests explicitly, which is useful review context regardless.
- **Cons**:
  - All four measured instances shipped with long, conscientious, accurate-sounding PR bodies. ISSUE-078's PR #133 body described its arming predicate's scoping *as a deliberate residual*; a checklist would have been filled in and passed.
  - Depends on `gh` and on network reachability inside the review phase.
- **Trade-off**: +~25 lines, +1 network dependency in a blocking phase, and 0 of 4 measured instances detected — every one of the 4 PR bodies would have satisfied the checklist.

### Option E: Require a refusal-shaped expectation (mechanical direction detection)

> Added by the 2026-10-14 amendment. Options E/F/G answer the amendment's decision 1, not the original seam question; the seam remains Option C.

- **Approach**: Keep Option C's seam and add a **direction** predicate to the evidence evaluation. A battery counts toward `disarm` only when at least one of its assertions has a *refusal-shaped expected side*, evaluated operator-aware: for `==`/`is`, an expected `False`, a non-zero int literal, a SCREAMING_CASE constant whose name carries a refusal token (`EXIT|FAIL|ERROR|REFUS|REJECT|BOUNDARY|INVALID|BLOCK`), or a refusal string literal; for `!=`/`is not`, a *success* literal (so `!= 0` counts and `!= False` does not); plus `assert not …`, `pytest.raises`/`assertRaises`. The composite half's consumer-level literal must itself pass the same test under its own operator.
- **Pros**:
  - Takes arm-only recall from **1 of 8** to **8 of 8** synthetic arm-only shapes, including the no-guard shape that is literally the shape of all four historical fail-opens.
  - Blocks the decisive attack: the committed pre-fix fixture plus two purely arm-direction batteries goes from `exit 0 / PASS — 2 gate(s) carry both directions` back to the exact unattacked pre-fix findings at `exit 1`.
  - Measured **0 regressions** across 15 corpus diffs and **0 recursive bite** on this PR — both gates it evidences (`main`, `verify_review_gate_evidence`) are credited by batteries carrying `is False` / `rc == 1` / `returncode == 1`.
- **Cons**:
  - Hand-classified per battery, it misclassifies **16 of 27** `direction=False` verdicts (59%) as missing when the battery is a genuine disarm battery. `any()` semantics masks all 16 on the unmodified corpus, which is why 0 regressions is a weaker result than it looks.
  - The masking is **reachable**: deleting one incidental smoke battery from the PR #129 diff flips `parse_roster_watermark` from `missing-composite-pin` to `missing-disarm-battery`, telling the reviewer to add a disarm battery that already exists twice.
  - One error class is **irreducible**: for a *detector-shaped* gate the disarm direction is asserted as `is True` ("the decorated variant is still detected"), so polarity depends on gate semantics and is not lexically knowable. 3 of the 16 are this class, and 3 more are this PR's own suite tripping the rule.
- **Trade-off**: +1 direction predicate (~40 lines), arm-only recall **+7 of 8** (1/8 → 8/8), **0** false blocks measured over 15 real diffs, against a **59%** latent per-battery misclassification rate with 1 measured reachable false block and 1 permanently undecidable class.

### Option F: Drop mechanical evidence evaluation for an attested obligation

- **Approach**: Keep gate *detection* blocking, but stop evaluating evidence mechanically. A detected gate passes only with an inline, reasoned attestation naming the disarm test, recorded in the review notes; whether the named test really asserts refusal becomes a reviewer obligation.
- **Pros**:
  - Cannot produce a false block from a misread assertion — the 59% misclassification rate and the undecidable polarity class both disappear.
  - The detection half, which is the measurable half, keeps naming the gate symbol and `file:line`, so the author cannot miss the obligation.
- **Cons**:
  - This is the control condition the SPEC already measured. Option A (prose obligation) is **0 of 4** with the native-memory lesson live for 2 of them, and Option D (attestation checklist) is **0 of 4** because all four PR bodies were conscientious and accurate-sounding.
  - It would discard Option E's measured 8-of-8 recovery of exactly the shape that failed four times.
- **Trade-off**: -40 engine lines and **-100%** of the false-block risk, but **0 of 4** historical instances detected versus Option E's 8 of 8 on the arm-only shapes — a measured regression against the pattern this SPEC exists to stop.

### Option G: Mechanical direction detection, demoted to advisory

- **Approach**: Option E's predicate, with `("review", "gate-evidence")` added to `ADVISORY_PHASES` so the phase reports and never blocks.
- **Pros**:
  - Zero false blocks by construction while the input-handling defects found in review are hardened.
  - One-line change, and the Rollback section already describes it as the declared intermediate step.
- **Cons**:
  - Removes the single property that distinguishes Option C from Option A — the obligation being an exit code rather than a sentence. An advisory `gate-evidence` is Option A with a script, and Option A is measured at 0 of 4.
  - The SPEC's own stated demotion criterion is a **measured false-positive rate**; the measured rate is **0 false positives over 12 real merged diffs** and **0 false blocks over 15**, so the criterion is not met.
- **Trade-off**: -1 blocking gate and **0** possible false blocks, against **0 of 4** enforcement strength and a demotion the SPEC's own criterion does not license at a measured **0%** false-positive rate.

## Decision

**Chosen: Option C**

Option A and Option D are measured failures, not hypotheses: A's trade-off line records 0/4 detection with the lesson already live for 2 of the 4, and D's records 0/4 because all four PR bodies would have passed a checklist. That eliminates both of the "not prose-only?" candidates named in the issue's Scope In. Between the two scripted seams, Option C is chosen over Option B on B's trade-off line specifically — `-1 independently diagnosable phase` and `-1 independently skippable unit`: a gate whose failure is indistinguishable from an unrelated rule's failure is the start of the same erosion this SPEC exists to stop, and a mechanism that must be exercised through hollow-test detection cannot be mutation-pinned in isolation, which AC-5 requires. Option C's cost (+1 blocking phase, +~240 lines, +3.4k fixture lines) buys the only property that distinguishes it from the prose it replaces: the obligation is an exit code in the blocking tier, and that tier membership is itself test-pinned.

### Why this seam is not prose-only

Three independent properties, each test-backed:

1. The requirement is evaluated by `scripts/verify_gate_evidence.py` and surfaced as a non-zero exit from `scripts/checkpoint.sh --skill review --phase gate-evidence`. No model decides whether it ran.
2. `("review", "gate-evidence")` is registered in `VERIFIERS` and absent from `ADVISORY_PHASES`. `tests/test_verify_checkpoint_contract.py` enumerates both sets, so demoting the phase, deleting it, or renaming it breaks the suite rather than silently relaxing the contract.
3. The SKILL clause is in `skills/review/SKILL.md.tmpl` and therefore regenerated, with `tests/test_gen_skills.py` pinning template↔generated agreement — the prose and the gate cannot drift apart.

### What counts as "adds a gate"

A **gate** is a function in a changed non-test source file whose *diff-added* lines contain **both**:

- a **conditional** — an `if`/`elif`/`assert`/ternary, or a `while` with a comparison or membership test; and
- a **refusal** — one of: `sys.exit(<nonzero>)`, `raise SystemExit(<nonzero>)`, `raise <...>Error/Exception`, `return <nonzero int>`, a `False`/`"invalid"`/`"rejected"`/`"blocked"`/`FAIL` verdict value, **or** `return True`/`return False` when the function is predicate-shaped (annotated `-> bool`, or named `is_*`/`has_*`/`can_*`/`should_*`/`must_*`/`*_is_*`/`check_*`/`verify_*`/`validate_*`/`guard*`/`assert_*`/`*_valid*`/`*_ok`).

The definition deliberately **over-detects**, per the issue's Scope In. A tightened predicate inside an existing function counts: attribution is to the enclosing function, so adding one `if ...: return False` line to a shipped function arms the obligation for that function. The escape hatch is an explicit, inline, reasoned exemption — `GATE-EVIDENCE-EXEMPT(<symbol>): <reason>` on an added line of the diff — which the checker reports (so it appears in the review record) rather than silently honouring, and which the `/review` contract clause requires the PR body to justify.

### What counts as evidence

Per detected gate symbol `S`, two things must be present among the diff's **added test lines**:

- **E1 — disarm battery at the gate.** An added test that calls `S(` and is a *battery*: parametrized (or looping) over **≥ 3** variants whose parameters feed only the input (no parameter appears on the expected side of any assertion), asserting **constant literal** outcomes.
- **E2 — composite pin through the consumer.** An added test that is a battery by the same definition, asserts a **consumer-level outcome** (an exit code, a process return code, or a refusal constant introduced by the same diff), and carries a **vacuity guard over the input** — an `assert <literal> (not) in <input-expr>` whose literal shares a significant name token with `S`. The vacuity guard is what attributes the battery to `S` *and* what makes the battery non-vacuous; a syntactic checker cannot infer input families, and without the guard 8 heading mutations are indistinguishable from 8 copies of a case that already passed.

Attribution comes from **either** a direct call to `S` **or** a name-matched vacuity guard; the guard itself stays mandatory for E2 because it is what makes the battery non-vacuous. (Amended during implementation: requiring *name* attribution alone made E2 unreachable for a gate whose input vocabulary does not echo its own name, which is the normal case for a gate reached through a CLI.)

Measured against the motivating pair: pre-fix `d328a6c^` satisfies E1 for `sprint_status_is_running` and fails E2 (its only vacuity-guarded block is a single case asserting the *non*-refusal), so the finding fires naming that symbol — which is the symbol that actually failed open. Post-fix `d328a6c` satisfies both and is clean. The second gate the same PR added — `cmd_validate`, the CLI leg that returns exit 3 — is unevidenced in **both** diffs and is reported in both; its boundary-field rejection battery is consumer-level but carries no input-side vacuity guard. That is a true finding, not a separation signal, and it is the concrete shape of the cost recorded under Trade-offs Accepted. (`check_roster_boundary` is *not* detected, correctly: it is a pure verdict builder that blocks nothing. The enforcement point is.)

### The duplicated-oracle sub-pattern (observation 4) — DECLINED, with a carrier

**Decision: declined for this issue; carrier = ISSUE-084, to be filed on `main` as part of this change.**

Reason, measured rather than asserted: the instance that motivates the rule is PR #135's `_tool_grants`, re-typed from `tests/test_registry_lock_contract.py`'s `_split_tools`. Those two functions share **no** name, no signature, and no location — the duplication is purely behavioural. Every cheap syntactic rule therefore misses it: a name-collision check sees two distinct names; an import check sees a module that legitimately imports nothing; a "parser-shaped helper added" check fires on almost every guard and would be a pure false-positive tax on the phase this SPEC is adding. Detecting it requires behavioural-equivalence analysis over two function bodies, which is a new analysis class, is named by none of ISSUE-081's five ACs, and is precisely the unspecified-engine-surface failure ISSUE-079 was filed for. Encoding it here would ship ~100 lines of unrequested analysis with no acceptance criteria — the exact shape of the two defects the ISSUE-079 review found.

It is recorded as a requirement rather than dropped: ISSUE-084 carries "a new guard must import the project's existing splitter/parser rather than re-type it, and the review must check a gate-adding diff for a duplicated oracle", with `_split_tools` named as today's instance. A PR body is not a carrier; an issue is.

### Already-shipped gates that lack the paired evidence (recorded; backfill is OUT)

Measured at `b4dda36` by counting, per guard test module, parametrized batteries and input-side vacuity guards (`grep -cE 'assert "[^"]{3,}" (not )?in (text|content|src|source|raw|body|doc|document|sprint_text)'`):

| Guard | Test module | parametrize | input vacuity guards | paired evidence |
|---|---|---|---|---|
| `sprint_queue.py` roster boundary | `test_sprint_queue_watermark.py` | 25 | 10 | yes (ISSUE-078 review fix) |
| `registry lock contract` | `test_registry_lock_contract.py` | 11 | 4 | yes |
| `review_delegation_guard` | `test_review_delegation_guard.py` | 0 | 9 | partial — guards, no battery |
| `research_fabrication_guard` | `test_research_fabrication_guard.py` | 0 | 7 | partial — guards, no battery |
| `verify_gates.py` | `test_verify_gates.py` | 2 | 0 | **no** |
| `review_context.py` | `test_review_context.py` | 6 | 0 | **no** |
| `spec_gate.py` | `test_spec_gate.py` | 1 | 0 | **no** |
| `validate_spec.py` | `test_validate_spec.py` | 2 | 0 | **no** |
| `validate_frontmatter.py` | `test_validate_frontmatter.py` | 0 | 0 | **no** |
| `verify_checkpoint.py` | `test_verify_checkpoint.py` | 0 | 0 | **no** |
| `secret_guard` | `test_secret_guard.py` | 0 | 0 | **no** |
| `freeze_guard` | `test_freeze_guard.py` | 0 | 0 | **no** |
| `dangerous_command_guard` | `test_dangerous_command_guard.py` | 0 | 0 | **no** |
| `verify_hollow_tests.py` | *(no test module)* | — | — | **no** |

Ten shipped gates carry neither a disarm battery nor a composite pin, and one blocking guard (`verify_hollow_tests.py`) has no test module at all. Backfilling them is out of ISSUE-081's scope; the list exists so a later issue can carry it, and the carrier is named in Open Questions below.

## Amendment — 2026-10-14 (direction, the under-detection class, and the tier)

> Recorded as a dated amendment rather than a silent rewrite of the Decision above, following the discipline SPEC-056's contract-4 amendment used. The seam is **not** amended: Option C stands. What is amended is the *evidence semantics*, the *detection boundary's honesty*, and two record defects. Raised by the PR #137 review (5 Critical, 7 High, `docs/review_notes/ISSUE-081.md` at `ab907ea`) and decided on measurement taken for this amendment.

**The diagnosis this amendment starts from, adopted verbatim from the review because it is correct:** the implementation measured **end-to-end-ness** while the requirement names **direction** — a proxy mistaken for the property it stands in for. The discriminator genuinely separates the pre/post ISSUE-078 pair, which is why it looked right; it simply did not measure what this SPEC is about. Measured consequence: `disarm` was `True` for **7 of 8** purely arm-only shapes, including the no-guard shape that is the shape of all four historical fail-opens, and the committed `issue_078_pre_fix.diff` — the diff AC-1/AC-2 require to be BLOCKED — reached `exit 0` when the only addition was two arm-direction batteries with mechanically **zero** refusal assertions.

### Decision 1 — direction detection: **adopt Option E, blocking, with its error rate disclosed**

Mechanical direction detection **is** achievable for the shapes this SPEC exists to stop, and the measurement is unambiguous on every real input: arm-only recall **1/8 → 8/8**, the decisive attack returns to `exit 1` with the exact unattacked pre-fix findings, **0 regressions across 15 corpus diffs**, and **0 recursive bite** on this PR.

It is **not** achievable as a general classifier of "does this battery assert refusal", and this SPEC records that plainly rather than letting the 0-regression number stand alone:

- Hand-classified per battery, **16 of 27** `direction=False` verdicts are wrong — the battery is a genuine disarm battery the rule fails to recognise.
- **`any()` semantics, not classifier accuracy, is what makes this safe.** A gate passes when *any* attributed battery is recognised, and on the real corpus every genuinely-evidenced gate has at least one. That is why 0 regressions coexists with a 59% per-battery error rate, and it means the safety margin is incidental rather than designed.
- The masking is **reachable, measured**: deleting one incidental smoke battery from PR #129's diff flips `parse_roster_watermark` from `missing-composite-pin` to `missing-disarm-battery`, instructing the reviewer to add a disarm battery that already exists twice.
- One class is **permanently undecidable**: for a *detector-shaped* gate the disarm direction is written `assert detected is True` ("the decorated variant is still caught"), so refusal polarity depends on the gate's semantics, not on its syntax. 3 of the 16 are this class; 3 more are this PR's own test suite tripping the rule it proposes.

**Option F (attestation only) and Option G (advisory) were rejected on this SPEC's own prior measurements, not on preference.** Both reduce to Option A, which is recorded at **0 of 4**, with the native-memory lesson live for 2 of the 4. Trading a measured 8-of-8 recovery of the failing shape for a measured 0-of-4 is a regression, and "the gate might block an honest PR" does not outweigh "the gate passes the exact shape that shipped four fail-opens."

**What the amendment therefore requires:**

1. `disarm` requires a refusal-shaped expectation; `composite` requires the consumer-level literal to be refusal-shaped under its own operator.
2. The two failure modes must be **separately named** in the output, because they have very different reliability: *no attributed battery at all* versus *batteries present, none recognised as refusal-direction*. The second carries the 59% error rate and its remedy text must say so and must offer the polarity escape explicitly.
3. **The claim this SPEC makes about what the gate verifies must shrink to what it measures.** The gate does not verify that a battery exercises "adversarial-but-plausible input variation" — that is semantic and remains a proxy via the vacuity guard. It verifies that ≥3 variants exist, that their parameters feed only the input, and that some assertion is refusal-shaped. The `/review` contract text must stop implying more.
4. Because the irreducible class needs an escape, the inline attestation path must be made **trustworthy** — see decision 4.

### Decision 2 — the `return None` under-detection class: **explicitly OUT of scope, with a durable carrier**

Measured recall is **4 of 6** genuine gate-adders; both false negatives (`_gh_pr_merge_state` in PR #127, `parse_roster_watermark` in PR #129) refuse by `return None`, which `REFUSAL_PATTERNS` does not recognise. Four candidate closures were measured against this repo rather than reasoned about:

| form | whole-tree gates (base 124) | recovers both FNs | mutation-robust | verdict |
|---|---|---|---|---|
| naive `return None` | **+29**, overwhelmingly ordinary accessors | yes | yes | breaches the rollback trigger at scale |
| conditional references a declared parameter | +6 | **no** (`parse_roster_watermark` guards only locals) | yes | fails recall |
| refusal vocabulary anywhere in the def | +3, 0 FP | yes | **no** | a measurement artifact — rejected |
| ≥3 `return None` sites OR refusal vocabulary in a non-docstring literal | +6 | yes | yes | overfit, and see the coupling cost |

Two of those rows are the reason this is deferred rather than improvised:

- **The best-looking form is a mirage, and a mutation test in both directions killed it.** Its signal was *pure docstring prose*: rewording only the docstrings (`refusal`→`fallback`, `refused`→`declined`) with the code byte-identical turned detection off for 2 of its 3 hits. It detects the author's vocabulary, not the refusal. This is review lesson 4 applied to a *detector* rather than a parser, and it is exactly the trap a non-measured "just add `return None`" decision would have shipped.
- **Recovering the recall immediately produces a false BLOCK on an honest security PR.** Promoting `_gh_pr_merge_state` to a gate makes PR #127 fail with `missing-disarm-battery` **despite carrying two genuine disarm batteries**, because they drive the gate through a test helper `_probe_ref(value)` that neither `_calls` (a literal symbol-name regex) nor `_attributed` (the vacuity guard) can see. That is **1 false block per 2 recalls recovered**, and the defect is in the **attribution** layer, not the direction layer. Closing the recall gap therefore requires repairing attribution first — a larger piece of work with no acceptance criterion in ISSUE-081.

The surviving form's `≥3` threshold is additionally **overfit on a single negative** (`_gate_evidence_diff` has 2 sites), and 2 of its 3 whole-tree extras are clear false positives (`_remote_version`, `_read_cache`).

A fifth shape is out of reach of every `return None` form: PR #129's `cmd_next_action` refuses by **withholding** — 157 added lines, a conditional, and zero `return`/`exit`/`raise` among them, filtering the dispatch list instead. PR-level recall for the best form is 6/6 but symbol-level is only 3 of 4.

**Decision: out of scope for ISSUE-081, carried as a durable issue** (review lesson 15 — a PR body is not a carrier). Per review lesson 14, an analysis no acceptance criterion names must not be improvised into this PR; both engine defects ISSUE-079's review found lived in exactly that kind of unrequested code.

**Two consequences this amendment makes binding, because a deferral that changes nothing is not a decision:**

- **The declared error direction is corrected.** This SPEC states under Trade-offs Accepted that "over-detection is the chosen error direction" and accepts an exemption-writing tax over an under-detection hole. The delivered behaviour is the **inverse** — 0% false positives, 33% false negatives on genuine gate-adders. The honest statement is that the detector over-detects *within its boundary* and under-detects *at its boundary*, and the boundary is where the gate-adders it missed live.
- **The verdict vocabulary must stop asserting what the detector cannot know** — see decision 3.

**Sprint consequence, recorded because it was load-bearing on a plan.** The sprint fixed ship order 081 → 077 so that ISSUE-077 would be "the FIRST PR reviewed under the new requirement — an in-batch self-test of whether the mechanism is real rather than prose." ISSUE-077 tightens `_gh_pr_merge_state` — the exact function and exact `return None` shape scored as a false negative on its own predecessor PR #127. That self-test would have evaluated to a no-op. **A green `gate-evidence` verdict on ISSUE-077 is not evidence that this mechanism works**, and ISSUE-077 is not the self-test.

### Decision 3 — tier: **blocking stands; the verdict vocabulary is what changes**

The review raised three input-handling fail-opens as grounds for an advisory first landing: an author-writable `origin/HEAD` flipping FAIL→PASS, git's default C-quoting of non-ASCII paths skipping a file, and `_CONDITIONAL` backtracking 40 s on a 7-line diff against a 600 s runner watchdog. All three are fixed and pinned in this PR with tests verified RED first, so the ground is whether the hardening holds, not whether the defects existed.

Blocking is retained because:

- **This SPEC's own demotion criterion is a measured false-positive rate**, and it is explicit that an undeclared demotion is not legitimate. The measured rate is **0 false positives over 12 real merged diffs** and **0 false blocks over 15** with Option E applied. The criterion is not met.
- **The error directions are not symmetric.** Under-detection — the residual after decision 2 — does not halt an honest review; it only fails to catch. Over-detection halts one, and it is measured at zero.
- **Demotion would remove the only property separating Option C from Option A.** Option A is 0 of 4.

What does change, because it is a false claim rather than a tier problem: **a miss is currently indistinguishable from a clean pass.** Measured with a def/class control pair, a gate is detected *only* inside an added `def` in a changed non-test `.py` file. Each of these prints the **byte-identical** line `PASS: gate-evidence — no gate-adding change in the diff`:

- a gate at **module level** (no enclosing `def`);
- a gate in a **non-Python source file** — this kit itself ships eight `.sh` scripts under `scripts/`, including `checkpoint.sh` and `wt_setup.sh`;
- a gate in a **source file whose name matches the test-path heuristics** (e.g. `scripts/test_runner.py`);
- a tightened predicate in a hunk whose **function hint resolves to a `class`** rather than a `def` — the control case with a `def` hint is detected, which isolates the mechanism.

The fourth item **contradicts this SPEC's own "What counts as adds a gate"** claim that "a tightened predicate inside an existing function counts … adding one `if …: return False` line to a shipped function arms the obligation." It does so only when an added `def` or a resolvable hunk hint supplies attribution.

This was demonstrated on this branch, not hypothesised: commit `7949ccb`, authored to harden this very gate, adds **four** blocking `return None` refusals inside the pre-existing `def _gate_evidence_diff` and the detector reports `gates: []` / `PASS — no gate-adding change in the diff` / `exit 0`. **The gate cannot see its own hardening commit** — decision 2's class and this boundary composing into a complete miss.

**Requirement:** the gate-free verdict must read as "no gate **detected**", naming the boundary, never as "no gate-adding change". A pass from this phase means *no gate was detected*, never *no gate was added*. Carried as a durable issue.

### Decision 4 — the attestation path must be trustworthy (promoted from the review's finding 12)

Decision 1 leaves an undecidable class whose only escape is the inline `GATE-EVIDENCE-EXEMPT(<symbol>): <reason>` marker, so that marker stops being a convenience and becomes load-bearing. It is currently not trustworthy, and on this branch it is **live, not latent**:

The review recorded the hole as latent because all three existing marker occurrences use the literal `<symbol>` placeholder, whose angle brackets do not match `[\w.]+`. That was true at `7a10422`. It is false at `ab907ea`, because the review then committed `docs/review_notes/ISSUE-081.md`, whose prose describing the cross-file leak contains a marker naming a **real** symbol. Traced over the branch's own merge-base diff, that line — not `#`-prefixed, not in a `.py` file, with no locality to the gate — was collected as a live exemption and **changed the gate's own verdict**:

```
at 7a10422 (what the review measured):
  PASS — 2 gate(s) carry both directions: main, verify_review_gate_evidence | 5 exempted
at ab907ea (what the review committed):
  PASS — 1 gate(s) carry both directions: verify_review_gate_evidence     | 6 exempted
```

`main` moved from *evidenced* to *waived* because the review wrote finding 12 down. **Documenting the vulnerability exploited it**, on the production path, confirmed through the real blocking checkpoint. Dropping the `.md` marker lines restores the `7a10422` state exactly, which also confirms the five intended self-exemptions are `#`-prefixed, in `.py`, and in the gate's own file, so all five survive the fix.

**Requirements:** collect exemptions only from `#`-prefixed lines in non-test `.py` files, keyed `(path, symbol)` and scoped to the file that defines the gate; key `evidence` on `(path, symbol)` too. Review lesson 6 applies — shape validation is not provenance — and so does the measured corollary that *visibility is not enough if the waiver is unrecognisable*: an `EXEMPT:` line did print, but its reason rendered as a truncated fragment of review prose that no reviewer would read as an accidental waiver. This also closes the cross-file leak, measured naturally on PR #101, which detects **6** gates but yields only **5** evidence keys because `main` in two different scripts collapses into one record.

### Decision 5 — two record corrections, and one surface deletion

- **The engine-size trade-off line was wrong by 3.5x and is corrected in place** (the correction is recorded here rather than made silently). Option C estimated `+~240 engine lines`; the measured file is **848** lines — 129 blank, 45 comment, 74 docstring, **600 executable**, of which ~144 are regex/vocabulary data tables, so a fair "logic" figure is ≈456. Prose does not explain the overrun. Two competing figures are also settled: 862 was a stale uncommitted number, and 849 came from `len(text.split("\n"))` counting the trailing empty string.
- **`--range`/`--repo`/`_diff_from_range`/`_GIT_TIMEOUT` and `--json` are deleted**, so Option C's approach line now describes a `--diff-file`-only CLI. Justification: zero callers and zero tests for the range path, while `--json`'s sole consumer is the test written for it; the real consumer computes its own diff with a merge-base correction the deleted path lacks. Deleting it closes two further findings at no cost — the documented `--range main..HEAD` is two-dot while the consumer is merge-base and the two provably disagree, and `_GIT_TIMEOUT = 30` was hard-coded with an **untrue** provenance comment (it claimed to reuse "the project's documented 30 s subprocess default"; the only documented knobs are `KIT_CHECKPOINT_TEST_TIMEOUT` and `KIT_SPRINT_QUEUE_GH_TIMEOUT`). This is a **removal**, so it cannot be the unrequested-surface failure review lesson 14 names — an untested `subprocess` leg inside a blocking gate is.
- **The duplicated-oracle declination keeps its decision but loses its reason.** The declination above argues that the duplication is "purely behavioural … a name-collision check sees two distinct names". Measured inside this PR, that is false for 2 of the 3 instances now on record: `scripts/verify_checkpoint.py` carried the **same regex under the same local name** `test_dir_pattern` in two places, `verify_gate_evidence.py:is_test_path` re-typed that classifier a third time while dropping `tests?` singular and `__tests__`, and a fourth, weaker name-only definition sits at `:1250-1262` — four disagreeing definitions of "test file". A same-name-across-modules collision is grep-level, not behavioural-equivalence analysis. The declination may still be right, because the *general* case does need behavioural equivalence and no AC names it; the corrected reason is that the **cheap syntactic subset is real and is ISSUE-084's to scope**, and ISSUE-084 is already amended with all three instances. `is_test_path` itself is resolved in this PR by importing the oracle rather than re-typing it, which is an AC-3 obligation (a repo laid out with `test/` or `__tests__/` currently pays a fabricated-finding tax), not new scope.

## Trade-offs Accepted

- **The detector is syntactic, and its attribution rides on the vacuity guard.** A composite battery with no input-side vacuity guard is not credited to the gate even if a human would credit it, so the first PRs under this rule will sometimes have to *add* a guard to a test that was already adequate. Accepted deliberately: the alternative is crediting batteries that may be vacuous, which is how the arm-only diffs passed four times. The cost is bounded — one assertion per composite test.
- **Over-detection is the chosen error direction.** Adding `if x: return False` to a predicate-shaped function arms the obligation. Ordinary PRs that touch no predicate pay nothing (AC-3 pins this with a real non-gate diff), but a PR that tightens a shipped predicate incidentally will have to either evidence it or write an exemption. We accept an exemption-writing tax over an under-detection hole.
- **The exemption is honoured, not refused.** `GATE-EVIDENCE-EXEMPT(<symbol>)` lets any author pass the gate. The protection is that it must be inline in the diff, must carry a reason, and is echoed in the checkpoint output and therefore in the review record. This is a deliberately defeatable gate; the claim is that defeating it is *visible*, not impossible.
- **No new mutation-testing harness.** AC-5 is met by a hand-written mutation matrix in the test module that flips the checker's own thresholds and predicates one at a time, validated by a known-killing mutant. The issue's Scope Out forbids a general framework and this SPEC does not build one.
- **Scope of the rule is the diff, not the repo.** The 10 shipped gates listed above stay unevidenced after this change. The phase only constrains what a PR adds.
- **A guard implemented AS a test is invisible to this phase.** Gate detection is scoped to the source half of the diff, because every added `assert` in a test file is a predicate with a refusing branch and crediting them would make every PR a gate-adding PR (destroying AC-3). ISSUE-072's instance — where the defences that failed open *were* the guard tests the PR added — is therefore **not** covered by this mechanism. Disclosed, not fixed: closing it needs a different detector, and no ISSUE-081 criterion names one.
- **Exemptions are read from the source half only, for the same reason.** Measured during implementation by running this gate on its own diff: scanning test files too meant a test that merely *quotes* the marker in a fixture string silently exempted the symbol named in the string — a fail-open in the gate itself, caught by dogfooding it and now pinned by `test_an_exemption_quoted_in_a_TEST_file_does_not_count`.
- **A gate reached only through a CLI will usually need an exemption or a direct-call battery.** Name-token attribution works when the gate's input vocabulary echoes its name (the ISSUE-078 case: a `sprint_status_is_running` predicate over text containing `- Status: running`). Where it does not, the author must either write a battery that calls the gate directly or write a justified exemption. This PR's own five private detector predicates take the exemption path, visibly, with reasons naming the mutation knob that pins each.
- **The phase does not run on the primary review path's behalf.** It is a kit checkpoint, so it runs whether the correctness dimension was delegated to a runtime skill or fell back to the degraded `reviewer` agent. That is the point of choosing a checkpoint over a prompt clause, but it also means the phase sees only the diff — it cannot reason about findings the delegated model produced.

## Migration

No data migration, no schema change, no staged rollout. Ordered steps:

1. Commit this SPEC on `issue/ISSUE-081-gate-evidence`; set `Spec:` on ISSUE-081 in `issues.md` on `main`.
2. Commit the three fixture diffs under `tests/fixtures/gate_evidence/` with a `README.md` recording the exact SHAs and the `git diff` command that produced each, so provenance is checkable without regenerating them (CI runs at `fetch-depth: 1`).
3. Write `tests/test_gate_evidence_contract.py` first and observe RED.
4. Add `scripts/verify_gate_evidence.py`.
5. Register `("review", "gate-evidence")` in `scripts/verify_checkpoint.py`'s `VERIFIERS`, leaving it out of `ADVISORY_PHASES`, and extend the contract test's expected phase set.
6. Add the clause + checkpoint block to `skills/review/SKILL.md.tmpl`, regenerate via `python3 scripts/gen_skills.py`, and add the row to `agents/team-lead.md`'s review phase table.
7. File ISSUE-084 (duplicated oracle) and ISSUE-085 (backfill the 10 unevidenced gates) on `main` as the durable carriers this SPEC's declined and out-of-scope items require.

Existing in-flight PRs are unaffected until their review phase runs; the first gate-adding PR after this lands is the first one constrained.

## Rollback

`git revert` the PR. The obligation is purely additive: the phase is a new registry entry, the clause is a new template block, and no existing verifier's behaviour changes, so reverting restores today's review behaviour exactly and leaves the native-memory lesson as the only (measured-insufficient) prevention — the pre-issue state, which is what ISSUE-081's Rollback section already states.

**Rollback trigger**: two or more false positives on non-gate PRs within one sprint, or any review blocked by this phase for more than one iteration without a genuine missing-evidence finding behind it. **Rollback cost**: one revert commit; no state to unwind, since the phase writes nothing.

A cheaper intermediate step exists if the trigger fires once rather than twice: add `("review", "gate-evidence")` to `ADVISORY_PHASES`, which converts the gate to a reported-but-non-blocking note in 1 line. The contract test will fail until the tier change is declared, which is the intended friction — this SPEC records that demoting the tier is a legitimate response to a measured false-positive rate, and an undeclared demotion is not.

## Open Questions

- [ ] Backfill the 10 shipped gates recorded above that carry neither a disarm battery nor a composite pin, starting with `verify_hollow_tests.py`, which is a blocking guard with no test module at all — owner: next sprint planner, by: file as ISSUE-085 during this implement phase, schedule in the sprint after ISSUE-081 ships.
- [ ] Decide whether the duplicated-oracle rule is worth a behavioural-equivalence detector, or whether a convention (a single `kit_parsers` module every guard imports from) is the cheaper fix — owner: ISSUE-084, by: the sprint after ISSUE-081 ships.
- [ ] Measure the false-positive rate of the over-detecting gate definition over the first 5 PRs reviewed under this phase, and tune the `MIN_VARIANTS = 3` threshold or the refusal vocabulary only on that evidence rather than on anticipation — owner: the reviewer of the 5th PR after this lands, by: 5 PRs after merge.
- [ ] Decide whether the composite pin should also be required to drive the **CLI boundary** (subprocess) rather than any consumer-level outcome, which would have caught ISSUE-076's `SHIP → PIPELINE` exit-0 case more directly — owner: ISSUE-085's reviewer, by: when the backfill forces the question on a gate with no CLI.

Added by the 2026-10-14 amendment — each of these is a *durable carrier* for something the amendment deferred, because a deferred finding with no carrier is not real (review lesson 15):

- [ ] **ISSUE-086 — close the under-detection class (amendment decision 2).** Recognise refusal by `return None`, by returning a sentinel tuple, and by **withholding** (filtering a dispatch list with no `return`/`exit`/`raise` at all, which PR #129's `cmd_next_action` does across 157 added lines). Blocked behind repairing **attribution** first: the measured form that recovers both false negatives also produces 1 false block on PR #127, an honest security PR with two genuine disarm batteries, because they drive the gate through a test helper that neither `_calls` nor `_attributed` can see. Measurements to start from are in the amendment's table; note the `≥3`-sites threshold there is overfit on a single negative — owner: ISSUE-086, by: before any PR that tightens `_gh_pr_merge_state` is read as self-testing this phase.
- [ ] **ISSUE-087 — widen or honestly bound the detection boundary (amendment decision 3).** A gate is seen only inside an added `def` in a changed non-test `.py` file; module-level gates, gates in the kit's own eight `.sh` scripts, gates in source files whose names match the test-path heuristics, and tightened predicates in `class`-hinted hunks are all invisible and print byte-identically to a gate-free PR. Includes the sub-case that commit `7949ccb` demonstrated on this branch — a gate added by *modifying an existing function* — which contradicts this SPEC's own "a tightened predicate inside an existing function counts" claim — owner: ISSUE-087, by: the sprint after ISSUE-081 ships.
- [ ] Re-examine the direction predicate's **59% per-battery misclassification rate** once real PRs have exercised it. `any()` semantics masks it today; the measured reachable case is one deleted smoke battery away. Specifically decide whether the undecidable **predicate-polarity** class (for a detector-shaped gate, `assert detected is True` *is* the refusal) should be handled by a per-gate polarity declaration rather than by the attestation escape — owner: the reviewer of the 5th PR under this phase, by: 5 PRs after merge.
