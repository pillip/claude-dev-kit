# SPEC-058: Delegation idiom expansion — test execution (dormant delegation behind a probe + deterministic gate-result synthesis)

> Linked Issue: ISSUE-058
> Status: `draft`
> Date: 2026-10-09
> Author: claude-dev-kit

## Problem

SPEC-019 named test execution the next delegation candidate ("test execution → `/verify` — flagged as a follow-up signal in ISSUE-014's Implementation Notes") and called the probe → delegate → synthesize → degrade pipeline "a reusable kit idiom worth investing in". Today the kit owns test execution end-to-end: `scripts/verify_gates.py` (1,014 lines — platform detection + six gate runners) is invoked from `scripts/verify_checkpoint.py::_run_verify_gates` at the implement-test checkpoint and the ship post-merge smoke checkpoint. If the Claude Code runtime ships a test-execution capability, the kit should delegate to it; but the Spec-Required question this SPEC must answer first is: **does such a capability actually exist today, and if not, what should land now so activation later is cheap?**

## Context

- **Survey result — no runtime test-execution capability with a machine-readable result contract is confirmed today.**
  - `scripts/has_skill.py` lists `verify` and `run` in `RUNTIME_BUILTIN_SKILLS` — names the kit *anticipates* as runtime built-ins. For such names the probe returns exit 2 ("unknown — filesystem-invisible by design; ask the runtime"), never exit 0. This is an allowlist of expectations, not evidence of exposure.
  - `docs/cc_feature_matrix.md` (ISSUE-014, verified against Claude Code 2.1.185, official docs current 2026-06-22) contains **no row for any test-execution skill**. Per that document's own rule — "adopt behind a fallback or probe before relying on it" — an unverified capability cannot be the primary path.
  - No official doc cited by the feature matrix documents a machine-readable per-gate result format for any runtime test skill. Without a result contract there is nothing to synthesize from.
- **Structural asymmetry vs SPEC-018/019**: research and review delegation happen at the *model layer* — skill prose invokes `/deep-research` or `/code-review` and captures prose output. Test execution happens at the *script layer*: `verify_checkpoint.py` is a Python subprocess launched by `checkpoint.sh`; a Python script cannot invoke a runtime skill. Delegation therefore requires a **handoff artifact**: the model layer (ship/review skill prose) invokes the future runtime capability, persists machine-readable per-gate results, and the checkpoint script ingests them.
- **The synthesis target is the existing gate-result contract**: `verify_gates.GateResult` — `{gate: str, status: "pass"|"fail"|"skip"|"warn", blocking: bool, output: str, duration_s: float}`. `_run_verify_gates` consumes exactly this shape (its `icon` lookup KeyErrors on any other status vocabulary). Checkpoint consumers must not change (ISSUE-058 AC-2).
- **Call sites to wire**: `verify_checkpoint.py::_run_verify_gates` is the single chokepoint — both the implement-test gate run (non-blocking unless the test plan carries High/Critical risk flows) and the blocking ship-smoke gate run flow through it. Wiring the probe there covers every current and future caller.
- `verify_gates.py` itself is **out of scope to modify** (issue Scope Out): it remains the degraded fallback unchanged, so `git revert` of this issue restores today's behavior exactly.
- Review lessons applied by construction: a results file read by a gate is **untrusted input** (validate type/shape/path on read, fail toward the stronger path — run the real gates); no new subprocess calls are introduced (the probe is an in-process import), so no new timeout class; new env knobs are documented at introduction in the owning module docstring and the README env-var list.
- Telemetry follows `docs/telemetry_schema.md` conventions: best-effort local JSONL append, silent no-op when unconfigured, never fails the parent.

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line.

### Option A: Do nothing until the runtime capability ships
- **Approach**: Close ISSUE-058 as "blocked on runtime"; revisit when a test-execution skill appears in `docs/cc_feature_matrix.md`.
- **Pros**:
  - Zero code now; zero risk to the blocking ship-smoke path.
- **Cons**:
  - The SPEC-019 roadmap item stays open indefinitely with no forcing function; the probe/telemetry signal that would *detect* the capability's arrival is never collected.
  - When the capability ships, the whole design (probe semantics, handoff contract, synthesis schema, untrusted-input rules) must be re-litigated from scratch.
- **Trade-off**: 0 LOC now; +1 re-opened design issue (~1d) later; 0 interim telemetry signal; the ingestion contract the runtime side would need to target is never published.

### Option B: Eager delegation — treat probe exit 2 as "attempt the primary path inline" at the gate call site
- **Approach**: Copy SPEC-018/019's exit-code semantics literally into `_run_verify_gates`: on probe exit 0/2, attempt runtime delegation each run and degrade on failure.
- **Pros**:
  - Maximum symmetry with the review/research idiom on paper.
- **Cons**:
  - "Attempt inline" does not transfer to a script call site: `verify_checkpoint.py` is a subprocess and cannot invoke a runtime skill. There is nothing a script can *attempt*.
  - `verify` sits permanently in the runtime-builtin allowlist, so the probe returns 2 forever — 100% of gate runs would enter a delegation branch that structurally cannot succeed, adding a failure mode to the **blocking** ship-smoke path for zero benefit.
- **Trade-off**: +~40 LOC at the call site; 100% of gate runs attempt a capability no script can invoke; +0 successful delegated runs ever; +1 new failure mode on a blocking gate.

### Option C: Dormant delegation — land probe + telemetry + deterministic synthesis mapper + an explicit handoff contract; keep the degraded path byte-identical
- **Approach**:
  - New module `scripts/synthesize_gate_results.py` owns the path decision and the mapper:
    - **Probe**: in-process `has_skill.find_skill("verify")`. Exit 1 → always degrade (AC-1). Exit 0/2 → delegation-*eligible*, not delegation-*active*.
    - **Activation trigger (the dormant switch)**: delegation activates only when the `KIT_GATE_RESULTS_FILE` env var points to a valid runtime-results JSON file. The variable is set by the model layer (ship/review skill prose) after it has actually invoked the runtime capability and persisted its results — the handoff artifact the script layer can ingest. Until the runtime capability ships, nothing sets it, so every run degrades with reason `capability_dormant`.
    - **Synthesis** (`synthesize_gate_results()`): deterministic mapper from the documented ingestion contract — a non-empty JSON array of `{gate, status, blocking, output?, duration_s?}` objects — to `verify_gates.GateResult` instances, preserving the blocking flag and the exact status vocabulary. Any violation raises; unit-tested like `synthesize_review_notes.py`. No merge-auditor: inputs are structured data, not prose (issue Implementation Notes).
    - **Untrusted input rules** on the results file: string path, no leading `-`, realpath containment inside `<project>/.claude/run/` (the kit's gitignored run-scoped scratch dir — tighter than project-wide containment so a *committed* artifact cannot serve as the handoff; review hardening, PR #100), regular file, ≤ 1 MiB, JSON array only, non-empty (an empty array — "zero gates ran" — can attest nothing and must not skip real gates), slug-constrained gate names, control-character-free output (`\n`/`\t` allowed), finite bounded `duration_s`. Any violation → degraded path with reason `invalid_results`. Failure direction is always toward *running the real gates*, never toward skipping them.
    - **Telemetry**: `gates_delegated_to_runtime {skill, gate_count}` / `gates_degraded_path_used {reason: "skill_missing" | "capability_dormant" | "invalid_results"}` appended to `<project>/.claude/runs/<KIT_RUN_ID>.jsonl` per the schema's append rules; silent no-op when unconfigured; stdout untouched.
  - **Wiring**: `_run_verify_gates` consults the module first; on `delegated` it prints an unconditional `GATES DELEGATED` stdout marker naming `KIT_GATE_RESULTS_FILE` (a delegated — possibly forged — run must never be byte-indistinguishable from a real gate run; review hardening, PR #100), then feeds the synthesized `GateResult` list into its existing print/blocking loop; on `degraded` (or any exception in the delegation layer) it calls `verify_gates.run_applicable_gates` exactly as today. Degraded stdout is byte-identical (AC-1 — the byte-identity pin applies to the degraded path only).
  - `verify_gates.py` is not touched.
- **Pros**:
  - AC-3 lands in full: probe + telemetry + documented contract ship now; the delegation branch is explicitly dormant with its activation trigger named.
  - The ingestion contract is published and mechanically enforced before the runtime side exists — when the capability ships, activation is skill-prose wiring only, with zero consumer change (AC-2 already proven by unit tests against the mapper).
  - Fail-safe by construction: every error path converges on the degraded fallback, which is today's exact behavior.
- **Cons**:
  - Ships a branch that no production run exercises until the runtime capability appears (mitigated: the branch is fully unit-tested, and the degraded path — which *is* exercised on every run — is pinned byte-identical).
- **Trade-off**: +1 module (~180 LOC) + ~20 unit tests + 2 telemetry events + 2 documented env knobs; 0 stdout delta on the degraded path; activation cost when the capability ships drops to ~1 skill-prose step with 0 consumer change.

### Option D: Prose-only delegation — ship/review skill templates bypass `verify_gates.py` when the runtime capability is present
- **Approach**: No script changes. Skill prose probes, invokes the future runtime capability, and simply skips the checkpoint's gate step when satisfied.
- **Pros**:
  - Zero new scripts.
- **Cons**:
  - Breaks checkpoint discipline: whether gates ran — and which path ran them — becomes a model self-assertion, exactly the A-bucket pattern the evolution audit (SPEC-055) is deflating. The blocking ship-smoke gate would be bypassable by prose drift.
  - No schema enforcement anywhere; AC-2's "same per-gate schema" is unverifiable.
- **Trade-off**: +0 scripts; -1 script-enforced blocking gate; 100% of path-selection enforcement moves to model self-assertion; 0 unit-testable surface.

## Decision

**Chosen: Option C.**

The deciding line is Option C's "+1 module + ~20 unit tests; 0 stdout delta on the degraded path; activation cost drops to ~1 skill-prose step with 0 consumer change". The survey finding (no confirmed runtime test-execution capability, no documented result contract — see Context) rules out any design that pretends delegation can run today: Option B attempts it structurally in vain on every run and adds a failure mode to a blocking gate; Option D trades a script-enforced gate for prose. Option A defers even the cheap parts — but the probe, the telemetry that will *show* when degradation stops being the only path, and the published ingestion contract are precisely what make the eventual activation a small change instead of a re-design. This is the same shape SPEC-018 chose when it landed the degraded-path bundle behind a probe: the dormant branch is the honest cost of a graceful-activation promise.

Per ISSUE-058 AC-3, the delegation branch is **dormant** with its activation trigger named: *a Claude Code runtime build that exposes a test-execution skill emitting machine-readable per-gate results (expected name `/verify`, per the `has_skill.py` allowlist). On that build, the ship/review skill templates invoke the capability, persist its per-gate results JSON, and set `KIT_GATE_RESULTS_FILE` for the checkpoint run; `docs/cc_feature_matrix.md` gains a verified row first (ISSUE-014 rule).*

## Trade-offs Accepted

- **A dormant branch ships.** Code that production never executes until the runtime capability appears is a maintenance liability. Accepted because: the branch is small, pure, fully unit-tested, and the alternative (Option A) pays a full re-design later while collecting zero signal in the interim.
- **The ingestion contract is kit-defined, not runtime-defined.** The real capability may ship with a different result format, requiring a mapper revision. Accepted: the mapper is the single, unit-tested place where that revision lands; the `GateResult` consumer contract — the side the kit controls — stays fixed either way.
- **Probe exit 2 is permanently ambiguous for `verify`.** The filesystem probe can never confirm a runtime built-in; disambiguation comes only from the handoff artifact actually existing. This is why the env-var handoff, not the probe alone, is the activation switch.
- **Shape validation is not provenance.** A schema-valid artifact planted together with env control must not activate the delegated branch — the validation stack verifies shape, not authenticity. Mitigated in review (PR #100): the delegated path prints an unmistakable stdout marker, and containment is restricted to the gitignored `.claude/run/` so a committed artifact cannot be the handoff. The residual High finding was closed by ISSUE-065: provenance/freshness/one-shot binding (per-run ephemeral HMAC, mtime ≥ process start, consume-once) now gates the delegated branch — see the resolved Open Questions item below for the mechanism.
- **Telemetry is best-effort and usually silent.** Until a run-id convention is wired by an orchestrating skill (`KIT_RUN_ID`), degraded-path events are no-ops in most runs. Accepted per `docs/telemetry_schema.md`: never fail the parent on telemetry; the schema entry is the contract, emission volume grows when the pipeline is configured.
- **`_run_verify_gates` gains ~15 lines.** The one consumer-side edit is the fail-safe consult; its degraded path is pinned byte-identical by tests. Accepted as the minimum wiring that keeps `verify_gates.py` untouched (Scope Out).
- **Mixed mode is out of scope.** Review delegation supports per-dimension mixing; gate delegation is all-or-nothing per run (either the results file covers the run or the full degraded suite executes). Revisit only if the runtime capability ships with per-gate granularity worth exploiting.

## Migration

1. **Module**: `scripts/synthesize_gate_results.py` — constants (`RUNTIME_TEST_SKILL = "verify"`, `GATE_RESULTS_ENV = "KIT_GATE_RESULTS_FILE"`, `RUN_ID_ENV = "KIT_RUN_ID"`, size cap), `synthesize_gate_results(payload) -> list[verify_gates.GateResult]` (strict; raises `GateSynthesisError`), `decide_gate_path(project_path) -> (path, results, reason)` implementing the decision table (probe 1 → `skill_missing`; env unset → `capability_dormant`; invalid file → `invalid_results`; valid → `delegated`), and `_emit_telemetry` (schema-conformant, silent no-op, never raises).
2. **Wiring**: `verify_checkpoint.py::_run_verify_gates` — consult `decide_gate_path` before `verify_gates.run_applicable_gates`; any exception in the delegation layer → degraded fallback. No other call-site changes (both implement-test and ship-smoke flow through this helper).
3. **Telemetry schema**: add the ISSUE-058 event table (`gates_delegated_to_runtime`, `gates_degraded_path_used`) and the `KIT_RUN_ID` script-side run-id note to `docs/telemetry_schema.md`.
4. **Env-knob docs**: `KIT_GATE_RESULTS_FILE` and `KIT_RUN_ID` one-liners in the README environment-variable list and in the owning module docstring (review-lesson rule: knobs are documented at introduction).
5. **Tests**: `tests/test_gate_delegation.py` — mapper fidelity matrix (all four statuses, blocking preservation, defaults), strictness matrix (bad status/missing fields/non-list/empty list/etc.), decision table (probe-absent wins over a valid file; dormant; delegated), untrusted-results matrix (missing file, out-of-tree path, leading `-`, non-JSON, schema violation, oversize), telemetry emission + silent no-op, and `_run_verify_gates` seam tests: degraded path calls `verify_gates.run_applicable_gates` exactly once with byte-identical stdout; delegated path never calls it; a crashing delegation layer still falls back.
6. **No regeneration needed**: no SKILL.md.tmpl changes in this issue — skill-prose wiring is explicitly deferred to the activation trigger.
7. **Activation (future, out of this issue)**: when the capability ships — feature-matrix row first, then ship/review template edits that invoke it, persist results, and set `KIT_GATE_RESULTS_FILE`.

## Rollback

`git revert` of the ISSUE-058 PR removes `scripts/synthesize_gate_results.py`, the `_run_verify_gates` consult, the telemetry schema entries, the README env lines, and the tests. Because the delegation branch short-circuits to the degraded path on every production run today, reverting removes only dormant code — `verify_gates.py` behavior was never modified, so the blocking ship-smoke path is unaffected before and after.

Rollback signal: the runtime capability ships with a result model so different (e.g., streaming, no per-gate granularity) that the handoff-artifact design is the wrong shape — in that case revert and write a fresh SPEC rather than bend the mapper. Rollback time: < 10 minutes.

## Open Questions

- [ ] What is the actual name and result format of the runtime test-execution capability (`/verify`? `/run`? something else)? — owner: feature-matrix refresh (ISSUE-014 process), by: next targeted-runtime version bump probe.
- [ ] When the capability ships, should the implement-test (non-blocking) and ship-smoke (blocking) call sites activate delegation together or ship-smoke last? — owner: design, by: activation PR; default to activating the non-blocking site first for one sprint of telemetry.
- [ ] Should `KIT_GATE_RESULTS_FILE` support a per-gate partial mode (delegate `unit`, degrade `e2e-web`) once real granularity is known? — owner: design, by: first real runtime result observed (see mixed-mode trade-off).
- [x] Provenance/freshness/one-shot binding for the artifact (runtime-issued token or HMAC, mtime ≥ checkpoint start, unlink-after-ingest) — **required before activation on any blocking checkpoint** (security review, PR #100 finding 1). **Landed via ISSUE-065**: per-run ephemeral HMAC-SHA256 key (`generate_binding_key()` = `secrets.token_bytes(32)`, in-process only, never persisted or env-sourced — no new env knob) authenticates the artifact's raw bytes via a `<artifact>.sig` sidecar; artifact `st_mtime` must be ≥ the invoking checkpoint's process start (`verify_checkpoint._GATE_PROCESS_START`, captured at import); a successful ingest renames the artifact to `<artifact>.consumed` (consume-once, checked before parse). `decide_gate_path` takes the binding materials as REQUIRED keyword-only parameters, so **binding — not env-var presence — is now the enforced delegation precondition**; every binding refusal degrades with reason `binding-rejected` toward running the real gates. The delegated branch stays dormant (activation trigger above unchanged); the activation PR still owes the producer-side key-handoff design (how the runtime invoker obtains this run's key to sign the artifact).
