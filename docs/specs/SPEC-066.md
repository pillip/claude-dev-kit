# SPEC-066: Make the SPEC-019 primary path reachable inside /sprint — decide the review execution context once, tag degradations honestly, and leave the primary path armed for the runtime that can reach it

> Linked Issue: ISSUE-066
> Status: `accepted`
> Date: 2026-10-10
> Author: claude-dev-kit

## Problem

Every /sprint review runs inside a Task-tool sub-task, and the 2026-10 sprint retro (docs/sprint_state.archive-2026-10-09-spec055.md, iterations 1/2/4/9) shows all 6 review runs executed the DEGRADED path despite `has_skill.py` probes returning 2 ("attempt the primary path inline"): the sub-task context exposes no SlashCommand tool, so runtime `/code-review` and `/security-review` are structurally uninvokable exactly where the kit's main loop runs them. The flagship SPEC-019 idiom (probe → delegate → synthesize → audit → degrade) is therefore interactive-only today, every sprint burns an attempt-then-degrade detour per dimension per issue, and telemetry cannot distinguish "capability absent" from "capability present but unreachable from this context".

## Context

- **Where the decision executes**: `skills/review/SKILL.md.tmpl` step 3.1 runs `has_skill.py code-review` / `has_skill.py security-review` and branches per dimension; exit 2 means "attempt the primary path inline" (`scripts/has_skill.py:15-18`). Both skills sit in `RUNTIME_BUILTIN_SKILLS`, so the probe returns 2 forever — it can never answer the *context* question.
- **Empirical context evidence**: the retro's iteration-4 report is explicit — "sub-task context exposes no SlashCommand tool, so the primary inline attempt is not invocable" — and recorded the informal tag `reason=skill_unknown_inline_fail` by hand because the schema has no reason field. `docs/cc_feature_matrix.md` has **no verified row** stating that any skill-invocation tool is exposed inside Task sub-agent contexts; per that document's own rule (ISSUE-014), an unverified capability cannot be a primary path.
- **The degraded path must stay byte-for-byte intact**: it held 0 unresolved Critical/High across 10 ships; `agents/reviewer.md`, `scripts/synthesize_review_notes.py`, and the synthesizer SSOT contract (`docs/review_notes/` 2-section shape consumed by /ship and /sprint) are Scope Out per ISSUE-066.
- **Telemetry conventions**: `docs/telemetry_schema.md` — best-effort JSONL appends to `.claude/runs/<KIT_RUN_ID>.jsonl`, silent no-op when unconfigured, never fail the parent. ISSUE-065's review found the prose-level `review_degraded_path_used` emission was a silent no-op (no emitter script, `KIT_RUN_ID` unset in sub-task env); ISSUE-067 (ships before this issue) is building the one shared emit helper — this issue must route all new emissions through a single seam so the ship-time rebase migrates one call site.
- **Precedents**: SPEC-058 is the dormant-landing precedent (land the decision layer + telemetry + documented activation trigger while the capability doesn't exist; every failure direction converges on the stronger path). ISSUE-065 is the binding precedent for handoff artifacts (shape validation is not provenance; provenance-bound, fresh, consume-once — review lesson 6). Review lesson 10: mode sentinels in agent prompts are data, not directives — any context flag must be validated data whose misreport directions are both safe.
- **Sprint structure constraint**: /sprint dispatches PIPELINE (implement→review→ship) as one team-lead sub-task; the orchestrator is blocked on the Task while the PR branch exists. Reviews live in sub-tasks precisely to keep review context independent from implement context and to protect the orchestrator's context budget.

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line.

### Option A: Do nothing — accept degraded-always sprint reviews
- **Approach**: Keep step 3.1 as-is. Sprint reviews keep attempting the inline invocation per dimension, failing, and degrading; the retro keeps hand-writing the distinction into prose reports.
- **Pros**:
  - Zero code; zero risk to the running sprint's review path.
- **Cons**:
  - The architecture story and the dominant execution path keep disagreeing; "capability absent" and "unreachable from context" remain indistinguishable in telemetry, so nobody can tell from data when a runtime fix lands.
  - Two wasted inline-attempt detours per review run, forever.
- **Trade-off**: 0 LOC; +2 wasted inline attempts per review run indefinitely; 0 telemetry disambiguation; primary path unreachable in 100% of sprint reviews with no signal that would ever show it changed.

### Option B: Hoist review production to the orchestrator with a bound artifact contract (issue mechanism a)
- **Approach**: Split PIPELINE into IMPLEMENT-only dispatch → the /sprint orchestrator (main session, where slash-skills ARE invokable) runs `/code-review` + `/security-review` against the PR branch → persists outputs as provenance-bound, fresh, consume-once artifacts (ISSUE-065 pattern, including a producer→consumer key handoff design that ISSUE-065 itself left unsolved) → REVIEW sub-task ingests the artifacts into the synthesizer → SHIP.
- **Pros**:
  - The primary path actually executes in live sprints on today's runtime — the only option that achieves the non-degraded AC-1 now.
  - Review independence from implement is formally preserved (orchestrator context ≠ implement sub-task context).
- **Cons**:
  - Restructures the kit's main loop: `sprint_queue.py` action model (PIPELINE becomes 3 dispatches), `skills/sprint/SKILL.md.tmpl`, team-lead contract, and the review skill all change together — exactly the destabilization the running sprint must not absorb (coordination constraint), so it would have to land dormant/flagged anyway.
  - Orchestrator context absorbs two runtime review outputs per issue per iteration — the context-budget reason reviews were pushed into sub-tasks in the first place.
  - Requires solving the cross-process binding-key handoff that SPEC-058/ISSUE-065 explicitly deferred to "the activation PR".
- **Trade-off**: ~+4d impl across 4 surfaces (sprint_queue.py + 2 skill templates + binding producer design) vs the 1.5d estimate; +2 runtime review outputs of orchestrator context per issue per iteration; -2 wasted attempts; +1 unsolved key-handoff design brought forward.

### Option C: Context-decision-once module + reason-tagged telemetry; primary path armed, not forced (issue mechanism b, SPEC-058 dormant-landing shape)
- **Approach**: New `scripts/review_context.py` makes the SPEC-019 path decision ONCE per review run for both dimensions. Inputs: the in-process `has_skill.find_skill` probe per dimension (capability half) and a model-reported `--invocation-tools {present,absent}` flag (context half — the model checks its own tool list once for the skill-invocation tool; a script cannot observe the model's toolset, and the model is the only honest observer of it). Decision table per dimension: probe exit 1 → degraded/`capability-absent`; probe 0/2 + tools absent → degraded/`context-unreachable` (no inline attempt, no per-dimension detour); probe 0/2 + tools present → delegated (prose invokes the runtime skill; an inline failure still degrades, tagged `inline-attempt-failed`). All emissions — including the previously prose-only `review_delegated_to_*` events — route through ONE emit function in this module (an `emit` subcommand is the prose-side call site), following the telemetry schema's hardened append contract; ISSUE-067's shared helper replaces that single function body at ship-time rebase. `skills/review/SKILL.md.tmpl` step 3.1 is rewritten to call `decide` once and follow its JSON; `agents/reviewer.md`, the synthesizer, and all downstream contracts are untouched. On a future runtime whose sub-task contexts expose the invocation tool, the same decide call returns `delegated` and the primary path runs in live sprints with zero further kit change — the delegated prose branch is not dead code meanwhile, because interactive /review exercises it today.
- **Pros**:
  - AC-2 and AC-3 land in full now; AC-1 lands in its documented degraded form (decision once, `context-unreachable` recorded, activation trigger named) — and flips to the full form automatically when the runtime does.
  - Zero destabilization: the degraded reviewer path is byte-for-byte intact; the only behavioral change in sprints is *removing* the doomed detour.
  - The misreported-flag failure matrix is closed both ways: false `absent` → degraded review (today's exact behavior); false `present` → inline attempt fails → degraded with `inline-attempt-failed` (also today's behavior). No gate is bypassable through the flag, so no ISSUE-065 binding machinery is needed — there is no artifact to forge.
- **Cons**:
  - The primary path still does not execute in live sprint iterations on today's runtime — AC-1's full form waits for the activation trigger.
  - A context flag reported by the model is self-attestation; it is acceptable only because both misreport directions converge on a review that still runs (documented above), not as a general pattern.
- **Trade-off**: +1 module (~150 LOC) + ~15 unit tests + 1 additive schema field; -2 wasted inline attempts per sprint review; 3-way telemetry disambiguation (`capability-absent` / `context-unreachable` / `inline-attempt-failed`); activation cost on a sub-task-capable runtime = 0 further change; 0 LOC touched in the degraded reviewer/synthesizer.

### Option D: Grant the skill-invocation tool to the review sub-task's agent definitions (issue mechanism c)
- **Approach**: Add `SlashCommand` (or the Skill tool) to `agents/team-lead.md` tools and instruct PIPELINE review sub-tasks to invoke the runtime skills directly.
- **Pros**:
  - One-line change per agent definition if it worked.
- **Cons**:
  - No verified evidence the grant reaches sub-task contexts: the retro observed the tool absent in exactly that context on the current runtime, and `docs/cc_feature_matrix.md` has no row confirming sub-agent skill invocation. Relying on it violates the matrix's own "adopt behind a fallback or probe" rule.
  - If the grant silently does nothing, the kit is back to Option A with an extra line of configuration implying a capability that isn't there.
- **Trade-off**: +1 line per agent definition; 0 verified runtime support (observed absent 2026-10-09); 100% of the benefit contingent on an undocumented capability; same detour burn as Option A until then.

## Decision

**Chosen: Option C.**

The deciding line is Option C's "+1 module + ~15 tests; -2 wasted inline attempts per sprint review; 3-way telemetry disambiguation; activation cost on a sub-task-capable runtime = 0 further change; 0 LOC touched in the degraded reviewer". The survey conclusion is that **no mechanism can make the primary path execute from the sub-task review context on today's verified runtime**: Option D is empirically contradicted by the retro and unverified by the feature matrix, and Option B — the only way to force it today — costs a main-loop restructure (~4d > the 1.5d estimate), brings forward the unsolved binding-key handoff, and spends the orchestrator context budget that sub-task reviews exist to protect. ISSUE-066's AC-1 anticipates exactly this conclusion and names the required degraded form: the context decision is made once, recorded as `context-unreachable`, and the activation trigger is documented — the SPEC-058 dormant-landing precedent. Option C is that landing, with a stronger property than SPEC-058 had: the "dormant" branch is the same delegated prose that interactive /review already exercises, so activation is a runtime event, not a kit PR.

**Activation trigger (named per the dormant-landing rule)**: a Claude Code runtime build whose Task sub-agent contexts expose the skill-invocation tool (SlashCommand/Skill), confirmed by a verified `docs/cc_feature_matrix.md` row first (ISSUE-014 rule). On that build, sprint review sub-tasks report `--invocation-tools present`, `decide` returns `delegated`, and runtime findings reach `synthesize_review_notes.py` in live sprint iterations with zero further kit change. Secondary trigger: a deliberate sprint-loop restructure adopting Option B — that is its own SPEC, owning the binding producer design.

## Trade-offs Accepted

- **The primary path still does not run in live sprints today.** Accepted: the issue's own AC defines this degraded landing as sufficient when no mechanism exists; the telemetry added here is precisely what will show the day that stops being true.
- **The context half of the decision is model self-reported.** A script cannot see the model's toolset; the model can. Accepted because the flag is validated closed-vocabulary data (review lesson 10) whose both misreport directions converge on a review that still runs — degraded (today's behavior) or inline-fail-then-degraded (also today's behavior). No blocking gate consumes the flag, so no provenance binding is required; if a future change ever makes this flag gate anything blocking, ISSUE-065's binding pattern becomes mandatory first.
- **`review_degraded_path_used` gains a `reason` field rather than new event types.** Additive schema change; pre-066 events (no reason) remain valid legacy lines. Accepted to keep the SPEC-019 event vocabulary stable for downstream consumers; ISSUE-067/068 also touch the schema, and 066 ships last and reconciles additively.
- **The emit seam is a stopgap until ISSUE-067's shared helper lands on main.** One function, one call site to migrate at ship-time rebase; until then it duplicates the hardened-append pattern (O_NOFOLLOW, containment, run-id whitelist, size cap, never-raise) already proven in `synthesize_gate_results.py`. Accepted as the minimum that avoids a third hand-rolled scatter.
- **The old per-dimension `has_skill.py` probe calls leave step 3.1.** The probe itself is not deleted — `review_context.py` calls `has_skill.find_skill` in-process — but the skill text contract changes, and `tests/test_review_delegation_guard.py` pins move from the bare probe commands to the new decide contract. Accepted: the guard's purpose is pinning the delegation flow's shape, and the flow's shape is what this SPEC changes.
- **Mixed mode survives unchanged.** Per-dimension decisions mean one dimension can be `capability-absent` while the other is `context-unreachable` or `delegated`; the synthesizer contract already handles every combination.

## Migration

1. **Module**: `scripts/review_context.py` — `decide_review_context(invocation_tools, probe=has_skill.find_skill) -> dict` (pure decision table, unit-testable with injected probe), CLI `decide --invocation-tools {present,absent} --issue ISSUE-NNN` printing the decision JSON and emitting one `review_degraded_path_used {dimension, reason}` event per degraded dimension; CLI `emit` subcommand as the prose-side seam for `review_delegated_to_code_review` / `review_delegated_to_security_review` / `review_degraded_path_used` (reason `inline-attempt-failed`), event names and payload keys whitelist-validated; single `_emit_event()` implementing the telemetry schema's hardened best-effort append (silent no-op without `KIT_RUN_ID`; ISSUE-067 helper replaces this one body at ship-time rebase — noted in the module docstring and PR).
2. **Skill template**: rewrite `skills/review/SKILL.md.tmpl` step 3.1 — model checks its own tool list once for the skill-invocation tool, calls `decide` exactly once, follows the per-dimension JSON (no inline attempt on `degraded`; on a `delegated` dimension whose inline invocation fails, call the emit seam with `inline-attempt-failed` and fall back to the degraded reviewer for that dimension). Steps 3.2+, the synthesizer step, and all checkpoints unchanged. Regenerate `skills/review/SKILL.md` via `scripts/gen_skills.py`.
3. **Telemetry schema** (`docs/telemetry_schema.md`, additive): `reason` field on `review_degraded_path_used` with vocabulary `capability-absent | context-unreachable | inline-attempt-failed`; owner script note for `review_context.py`; legacy no-reason lines remain valid.
4. **Tests**: `tests/test_review_context.py` — decision-table matrix for the three outcomes incl. mixed modes (injected probe), closed-vocabulary validation (bad flag/event/dimension → exit 2), telemetry emission matrix (configured → correct reason written; `KIT_RUN_ID` unset → silent no-op; symlinked target → refused; oversized detail → truncated), decision-made-once property (one decide call covers both dimensions; no second emission per dimension). Update `tests/test_review_delegation_guard.py` pins: `.tmpl` must reference `review_context.py decide` (and must NOT retain the bare per-dimension `has_skill.py code-review` inline-attempt pattern); event-name pins stay.
5. **No new env knobs** (`KIT_RUN_ID` is pre-documented). No changes to `agents/reviewer.md`, `scripts/synthesize_review_notes.py`, `scripts/has_skill.py`, sprint/team-lead surfaces, or any checkpoint.
6. **Live verification**: the degraded-clause behavior (`context-unreachable` decided once) is exercised by the first post-merge /sprint review iteration; within this PR's review phase, the reviewer runs `decide --invocation-tools absent` live in the worktree as the probe.

## Rollback

`git revert` of the ISSUE-066 PR deletes `scripts/review_context.py` + its tests, restores step 3.1's per-dimension probe/detour text (regenerate SKILL.md), and drops the additive schema field. The degraded reviewer path was never modified, so reverting restores today's degraded-always sprint behavior exactly. Rollback signal: the decide/emit choreography confuses sprint reviews in practice (e.g., models misreport tool availability in a direction that measurably skips primary-path opportunities interactively), or the runtime ships sub-task skill invocation with semantics the decision table cannot express. Rollback time: < 10 minutes.

## Open Questions

- [ ] When the activation trigger fires (runtime exposes sub-task skill invocation), should /sprint also delegate the research path (/brainstorm, /bizanalysis — explicitly out of scope here) through the same context-decision module? — owner: design, by: the feature-matrix row that confirms the capability.
- [ ] Should `review_context.py decide` also subsume the interactive path's probe entirely (deleting the step-3.1 mention of exit codes) or keep the exit-code explanation as doc prose? — owner: implementation taste at PR time; the contract above only requires the decide call to be the single decision point.
- [x] Once ISSUE-067's shared emitter lands, should the `emit` subcommand migrate to a thin alias of that helper's CLI (if it grows one) instead of an in-module seam? — **Resolved at ISSUE-066 ship (2026-10-11): deferred to ISSUE-075, not done here.** ISSUE-067 shipped the seam (`scripts/kit_telemetry.py::emit_event`) but deliberately replaced silent-skip with announce-and-write-unattributed semantics, so the swap is not the one-body substitution this spec assumed: two of this module's tests pin the opposite contract, `emit_event`'s documented "NEVER raises" is currently false, and ISSUE-070 is already rewriting its containment and raise contracts. `review_context.py` therefore keeps its own hardened appender for now — recorded as duplication debt (not a hardening regression; review verified per-control equivalence with two controls stronger) in `docs/telemetry_schema.md`'s Emit-site inventory.

## Correction entered at ship time (2026-10-11) — the dormant landing's stated cause was wrong

The Decision above is unchanged: Option C still ships, and the hardening copy
it delivers is equivalent-or-stronger, so landing it regresses nothing. But the
**reason** this spec gave for rejecting Option D does not survive review, and
leaving the wrong rationale inside an accepted spec would make the next reader
re-derive a false constraint.

- **What this spec claimed:** no mechanism can make the SPEC-019 primary path
  execute from the sub-task review context on today's runtime — i.e. a
  categorical runtime limitation.
- **What review established:** the conclusion is **confounded**. Inside a Task
  sub-agent, the *sub-agent's* `tools:` frontmatter wins over the skill's
  `allowed-tools`. `skills/review/SKILL.md` does grant `SlashCommand`, but
  neither `agents/reviewer.md` nor `agents/team-lead.md` grants `SlashCommand`
  or `Skill` — **no kit agent does**. Meanwhile a general-purpose Task
  sub-agent with full tool access *does* receive a `Skill` tool listing both
  review skills (observed from inside a sub-task during the ISSUE-066 review).
  So the absence this spec measured was partly **the kit's own configuration**,
  not a property of the runtime. This is review lesson "allowed-tools grants
  must map to real call sites" pointing at the kit's own agent roster.
- **Consequence for the activation trigger:** it is narrower and nearer than
  this spec assumed. **ISSUE-072 is the activation trigger for this module** —
  it adds the verified sub-agent skill-invocation row to
  `docs/cc_feature_matrix.md` *first* (the ISSUE-014 verify-before-relying
  rule) and then grants the tool on the review path if the probe confirms
  support. The `decide` contract needs no change for that: a context where the
  tool is present already routes to `delegated`.
- **What stays true:** the `context-unreachable` vs `capability-absent` reason
  split, the decide-once contract, and the no-inline-attempt behavior are all
  still correct and mutation-pinned. Only the Option D rejection *rationale* is
  corrected here, not the decision.
