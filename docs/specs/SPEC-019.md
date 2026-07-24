# SPEC-019: Delegate `/review` to runtime `/code-review` + `/security-review` + thin kit-specific guard

> Linked Issue: ISSUE-019
> Status: `draft`
> Date: 2026-06-18
> Author: claude-dev-kit

## Problem

`agents/reviewer.md:9–24` declares "Code Quality (Correctness, edge cases, error handling; Maintainability and readability; Complexity and duplication; Test coverage adequacy)" and "Security Audit (Injection: SQL, command, template injection; Authentication / Authorization; Sensitive data: hardcoded secrets; Input validation; Dependencies: known CVEs; XSS; Misconfiguration)". These are verbatim the scopes Claude Code's runtime `/code-review` and `/security-review` skills advertise. `skills/review/SKILL.md` is the wrapper that drives the duplicated reviewer agent. Cross-file NIH audit 2026-06-18 confirmed the overlap is structural, not incidental — kit is maintaining ~78 lines of prompt + a full agent file + a self-review block + a severity rubric to do, in a single-agent inline pass, what runtime exposes as two dedicated cloud-backed skills with multi-agent ultra mode, `--comment` (post inline PR comments), and `--fix` (apply findings to working tree). This is the same NIH pattern ISSUE-018 closed for research; platform-first rule (memory: `feedback_platform_first`) demands the same treatment here.

## Context

- `agents/reviewer.md:9–24` and `skills/review/SKILL.md` are the duplicated surface. The skill template is `skills/review/SKILL.md.tmpl` (the rendered SKILL.md is auto-generated).
- Runtime `/code-review` advertises: "Review the current diff for correctness bugs and reuse/simplification/efficiency cleanups at the given effort level (low/medium/high/max/ultra). `--comment` to post findings as inline PR comments, `--fix` to apply findings to the working tree." Runtime `/security-review` advertises: "Complete a security review of the pending changes on the current branch."
- ISSUE-013 / SPEC-013 sharpened `ui-reviewer` (per-screen UI: state coverage, copy compliance, token usage in implementation, a11y at the implementation level) and `design-auditor` (system-level: tokens, components at the system level, cross-platform alignment, philosophy compliance) with explicit "owned by this agent / owned by the other" tables. This issue MUST preserve that scope split; the runtime delegation is orthogonal to it.
- ISSUE-018 established the platform-probe + synthesizer + merge-auditor pattern (`scripts/has_skill.py`, `agents/synthesizer-auditor.md`) — same building blocks reused here, scoped to review merge instead of research synthesis.
- ISSUE-014 (Claude Code feature/version support matrix spike) must confirm `/code-review` and `/security-review` are exposed on the targeted runtime version before this issue's primary path is enabled. Until then, fall back to today's reviewer-agent path.
- Downstream SSOT contract: `/ship` and `/sprint` consume `docs/review_notes.md` (and `docs/review_lessons.md`) in a specific 2-section shape. Any delegation must preserve that contract or it cascades into those skills.
- Kit-distinctive review value that runtime does NOT provide:
  - Figma compliance step 3.5–3.10 in `skills/review/SKILL.md.tmpl` (visual + design system alignment against the active Figma source).
  - `ui-reviewer` / `design-auditor` / `a11y-auditor` agent pipeline post-ISSUE-013 scope split.
  - `registry_edit.sh` mutation gating (kit-only — write attempts during review are blocked unless the registry is unfrozen).
  - `docs/review_lessons.md` learning loop — recurring preventable patterns get promoted with frequency + severity + observed-in PRs. ISSUE-003 will later promote this to a structured store; for now it is a markdown accumulator that `reviewer` reads on every run.
- "Absolute zero hallucination" is not achievable. `/code-review` and `/security-review`'s runtime verification + multi-agent ultra mode are stronger than kit's single-agent self-review, but a quote that runtime correctly produced and that kit's synthesizer correctly copied can still be misinterpreted by a downstream consumer. The SPEC documents this honestly rather than promise zero.

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line.

### Option A: Keep today's `reviewer` agent as the sole reviewer; do nothing
- **Approach**: Leave `skills/review/SKILL.md.tmpl` and `agents/reviewer.md` as they are. Runtime `/code-review` and `/security-review` remain available for ad-hoc use but are not wired in.
- **Pros**:
  - Zero new code.
  - Zero risk of breaking the downstream SSOT contract (`/ship`, `/sprint`).
- **Cons**:
  - NIH continues: ~78 lines of duplicated checklist + full agent file + self-review block + severity rubric must be maintained against drift, while runtime skills evolve independently and kit's review falls progressively behind on coverage and ergonomics (`--comment`, `--fix`, ultra mode).
  - Single-agent inline review is structurally weaker than runtime's multi-agent ultra mode for security and correctness depth.
- **Trade-off**: 0 LOC delta now; **+permanent maintenance surface that overlaps a runtime capability**; -1 quality lever (kit's review can never match runtime's multi-agent depth without re-implementing it).

### Option B: Pure delegation — drop `agents/reviewer.md`, replace `/review` with thin wrapper over `/code-review` + `/security-review`
- **Approach**: `skills/review/SKILL.md.tmpl` invokes the two runtime skills, concatenates their outputs into `docs/review_notes.md`, deletes `agents/reviewer.md`. Kit-distinctive checks (Figma 3.5–3.10, ui-reviewer / design-auditor / a11y-auditor, registry_edit gating, `review_lessons.md` extraction) are removed or pushed to separate skills.
- **Pros**:
  - Maximum surface reduction.
  - Future runtime improvements propagate automatically.
- **Cons**:
  - Loses Figma compliance, ui-reviewer / design-auditor / a11y-auditor wiring, registry_edit gating, and the `review_lessons.md` learning loop. These are real kit value that runtime does NOT provide.
  - Breaks downstream SSOT contract: `/ship` and `/sprint` rely on the merged 2-section format. Raw runtime outputs are not drop-in compatible.
  - No graceful behavior when `/code-review` / `/security-review` aren't exposed by the runtime — `/review` would hard-fail.
- **Trade-off**: **-1 agent file, -78 lines of duplicated checklist, -1 self-review block; -all kit-distinctive review value; -1 graceful-degrade branch; +1 breaking change to `/ship` and `/sprint` SSOT contract**.

### Option C: Strengthen the reviewer agent's prompt language, keep the duplication
- **Approach**: Tighten `agents/reviewer.md`'s self-review + add more explicit security categories + reword to claim "cloud-runtime-equivalent depth in a single pass." No delegation.
- **Pros**:
  - Zero new architecture.
- **Cons**:
  - Same disclaimer-antipattern SPEC-011 already rejected for uiux's WebFetch fabrication. Wording improvements do not change the single-agent inline structural ceiling.
  - The duplication still has to be maintained against runtime drift; only the cost grows.
- **Trade-off**: 0 LOC delta on agent count, ~+30 LOC prompt growth; -0% quality gain (no structural change vs A); +0 maintenance reduction.

### Option D: Delegate runtime-owned scopes (correctness/complexity/coverage + security audit) + keep kit-distinctive checks as thin post-processing + separate-context merge auditor + degraded fallback
- **Approach**:
  - **Runtime probe** (reuse `scripts/has_skill.py` from ISSUE-018) detects `/code-review` and `/security-review` independently (one may exist on older runtimes without the other).
  - **Primary path**: invoke `/code-review` over the diff (correctness/complexity/coverage); invoke `/security-review` over the same diff (security audit). Capture each skill's output verbatim into intermediate artifacts under `docs/.review/`.
  - **Kit-distinctive checks** stay in `skills/review/SKILL.md.tmpl` and run on every path: Figma compliance 3.5–3.10, ui-reviewer per-screen pass (post-ISSUE-013), design-auditor system-level pass (post-ISSUE-013), a11y-auditor implementation-level pass, registry_edit gating, `review_lessons.md` extraction.
  - **Synthesizer module** (`scripts/synthesize_review_notes.py`) merges runtime outputs + kit-distinctive findings into `docs/review_notes.md` with the existing 2-section format (Code Review + Security Findings). Findings from runtime are copied with verbatim text + severity preserved; kit-distinctive findings are appended to the appropriate section with stable ordering.
  - **Review-merge auditor agent** (`agents/review-merge-auditor.md`, separate-context Task, `tools: Read, Grep`, model: sonnet, refute-first prompt): "for each finding in the merged notes, does it appear in the upstream runtime output (or kit-distinctive output) with the same severity and the same evidence? Flag drops, severity changes, evidence distortions."
  - **Degraded path**: when `/code-review` and/or `/security-review` are not exposed, the missing dimension(s) fall back to today's `agents/reviewer.md` invocation. Mixed mode (one runtime + one degraded) is supported per dimension.
  - **`agents/reviewer.md` revision**: retitle and re-scope to be the degraded-path agent only. Remove the checklist categories that overlap with runtime (correctness/complexity/coverage + security audit) from the agent's prompt so that, on the primary path, there is no ambiguity about canonical authority; on the degraded path, the agent's prompt is restored to today's scope through a degraded-only block.
  - `WebFetch` is not relevant to this issue; `Task` invocation of runtime skills is the primary mechanism (same pattern as ISSUE-018's `/deep-research` invocation).
- **Pros**:
  - Uses runtime capability where it exists; preserves kit-distinctive value where the runtime doesn't.
  - Future runtime improvements (multi-agent depth, `--comment`, `--fix`) become accessible to kit `/review` without code change.
  - Downstream SSOT contract (`/ship`, `/sprint`) is preserved by the synthesizer.
  - Graceful degrade keeps `/review` usable on older runtimes or partial-exposure environments.
- **Cons**:
  - Two execution paths (primary + degraded) roughly double the test matrix.
  - Synthesizer + merge auditor add new components to maintain (mitigated by reusing ISSUE-018's pattern + modules).
- **Trade-off**: +1 synthesizer module (~120 LOC), +1 thin merge-auditor agent, +1 runtime-probe call (already exists from ISSUE-018), +~12 guard tests; **-78 lines of duplicated checklist in `agents/reviewer.md`** (moved to degraded-only block), -1 maintenance surface that overlapped runtime; +1 graceful-degrade branch; runtime path adds `/code-review`+`/security-review` wall-clock (typically tens of seconds for non-ultra effort).

## Decision

**Chosen: Option D.**

The "+1 synthesizer, +1 merge-auditor, -78 duplicated lines, -1 maintenance surface, +1 graceful-degrade branch" line wins because (i) it applies the same platform-first rule ISSUE-018 / SPEC-018 already established (memory: `feedback_platform_first`) — `/code-review` and `/security-review` are runtime capabilities, kit invokes them like Task/Workflow rather than re-implementing them, (ii) kit-distinctive value (Figma, ui-reviewer / design-auditor / a11y-auditor, registry_edit, `review_lessons.md`) survives because only kit can offer it, and (iii) the downstream SSOT contract with `/ship` and `/sprint` stays intact through the synthesizer. Option A keeps the NIH duplication; Option B is throwing the baby out with the bathwater; Option C is the same disclaimer-antipattern SPEC-011 already rejected.

The audit that surfaced this NIH happened only because ISSUE-018 forced the platform-first framing on a different surface. SPEC-019 explicitly anticipates that the same rule will surface MORE candidates over time (test execution → `/verify` — flagged as a follow-up signal in ISSUE-014's Implementation Notes) and that the pattern (probe → primary path runtime delegation → synthesizer → merge-auditor → degraded fallback) is a reusable kit idiom worth investing in.

## Trade-offs Accepted

- **Residual hallucination is still non-zero.** Runtime verification + multi-agent ultra mode push the floor down for the review step; the merge-auditor catches drop/distortion/severity-change in the kit-side merge. A correctly-quoted runtime finding that a downstream consumer misinterprets still survives.
- **Wall-clock cost.** Primary path invokes two runtime skills serially (or concurrently if the harness allows); both can take tens of seconds at default effort and minutes at ultra. Accepted: review correctness > review speed; users opting into `/review` already accept a non-trivial wait.
- **Test matrix doubles.** Primary path, degraded path, and mixed-mode (one runtime + one degraded) each need coverage. Mitigated by reusing ISSUE-018's probe pattern and keeping the synthesizer pure (table-tested).
- **`agents/reviewer.md` becomes a degraded-only agent.** Future contributors might be confused why the checklist there is reduced. The agent's open section will state explicitly: "This agent is the degraded-path fallback. The canonical correctness/security review is `/code-review` + `/security-review`; this agent runs only when those are not exposed by the runtime." Documented in `docs/architecture.md` if present, otherwise inline.
- **Kit-distinctive value remains the kit's responsibility.** Runtime improvements to `/code-review` and `/security-review` propagate automatically, but Figma / ui-reviewer / design-auditor / a11y-auditor / registry_edit / `review_lessons.md` improvements are kit work. This is the right partition — those are kit-specific value, not runtime-equivalent capabilities.
- **`--comment` and `--fix` ergonomics from runtime `/code-review` are out of scope here.** A follow-up issue can decide whether `/review` exposes those flags to users when running on the primary path. For now, kit `/review` consumes the runtime output as text only.
- **Severity vocabulary is propagated verbatim.** If runtime returns `Critical`, kit's merged notes also show `Critical`. If runtime ever changes its severity vocabulary, the merge-auditor's `severity_changed` finding type catches the drift at the next review.
- **No re-implementation of multi-agent verification.** Runtime ultra mode already runs perspective-diverse verification; kit does not add its own. If a kit user wants depth beyond the runtime default, they invoke `/code-review` with `ultra` explicitly (or kit `/review` passes the effort through — Open Question).
- **`ui-reviewer` / `design-auditor` / `a11y-auditor` scope split from ISSUE-013 is preserved untouched.** This issue does not re-partition those agents; it only adds the runtime delegation upstream of them.
- **ISSUE-014 dependency is real.** If the spike confirms `/code-review` or `/security-review` is NOT exposed on the targeted runtime, the primary path is dead code on that version and only the degraded path runs. The probe handles this automatically; no separate guard needed.

## Migration

1. **Reuse `scripts/has_skill.py`** (lands first in ISSUE-018 migration). Add per-skill probes for `/code-review` and `/security-review`. No new script; just new probe calls.
2. **Synthesizer module**: `scripts/synthesize_review_notes.py` — pure function. Inputs: `/code-review` output + `/security-review` output + kit-distinctive findings (Figma, ui-reviewer, design-auditor, a11y-auditor outputs) + the existing review-notes template. Output: `docs/review_notes.md` in the existing 2-section format, with findings copied verbatim + severity preserved + kit-distinctive findings appended in stable order. Unit tests: structured-runtime-output mode, mixed-mode (one runtime missing), kit-distinctive-only mode (both runtime missing), severity-preservation regression.
3. **Merge-auditor agent**: `agents/review-merge-auditor.md` (tools: `Read, Grep`; model: sonnet; refute-first prompt; structured findings: `claim_dropped` | `severity_changed` | `evidence_distorted` | `ok`). Task invocation only — same pattern as ISSUE-010's separate-context critic and ISSUE-018's synthesizer-auditor.
4. **`agents/reviewer.md` refactor**:
   - Open section: state explicitly the degraded-path role.
   - Remove the verbatim runtime-overlap checklist categories (correctness/complexity/coverage in `Code Quality`; injection/auth/secrets/XSS/misconfig in `Security Audit`) from the canonical body.
   - Add a degraded-only block at the bottom that restores those categories for use only when the runtime skills are unavailable. Document in the open section how the kit decides which block to use.
   - `Self-Review` block stays but is now scoped to degraded-only.
   - `Learning Extraction` block (review_lessons.md) stays on every path — it operates on the merged notes, not the runtime outputs.
5. **Skill template rewrite**: `skills/review/SKILL.md.tmpl` —
   - Probe runtime skills at start; emit `review_delegated_to_code_review` / `review_delegated_to_security_review` / `review_degraded_path_used` telemetry events.
   - On primary path: invoke `/code-review` + `/security-review` (concurrent if harness allows). Capture outputs under `docs/.review/`.
   - On degraded path (per dimension): invoke `agents/reviewer.md` with the dimension-specific degraded-only block selected.
   - Kit-distinctive checks (Figma 3.5–3.10, ui-reviewer, design-auditor, a11y-auditor, registry_edit gating) run after both dimensions are captured.
   - Synthesizer merges everything into `docs/review_notes.md`.
   - Merge-auditor runs via Task tool; `claim_dropped` / `severity_changed` / `evidence_distorted` findings block save.
   - `review_lessons.md` extraction runs on the merged notes (unchanged from today's contract).
6. **Telemetry schema entries** in `docs/telemetry_schema.md`: `review_delegated_to_code_review`, `review_delegated_to_security_review`, `review_degraded_path_used`, `review_finding_dropped`, `review_severity_changed`, `review_merge_audit_finding`.
7. **Tests** in `tests/test_review_delegation.py`: dual-path matrix (primary / mixed / fully degraded), synthesizer claim-preservation, severity-preservation regression, merge-auditor drop/severity-change/evidence-distortion blocking, kit-distinctive checks survive on every path, grep guard ensuring `agents/reviewer.md` canonical body does not duplicate runtime-owned categories.
8. **Regenerate** `skills/review/SKILL.md` via `scripts/gen_skills.py`.
9. **Downstream sanity**: confirm `/ship` and `/sprint` consume the merged `review_notes.md` without schema change. No edits to those skills should be required; if they are, that is a sign the synthesizer drifted from the SSOT contract — fix the synthesizer.
10. **README touch (optional)**: if the kit's main README documents `/review`, add a one-line note that on supported runtimes `/review` delegates correctness + security to runtime skills + layers kit-distinctive checks on top. Out of scope to do a full README sync — that is its own issue (ISSUE-005 pattern).

## Rollback

Revert `skills/review/SKILL.md.tmpl` to the pre-issue form; restore the full canonical `agents/reviewer.md` body; delete `agents/review-merge-auditor.md`, `scripts/synthesize_review_notes.py`, the per-skill probe additions to `has_skill.py`, the telemetry schema entries, and `tests/test_review_delegation.py`. Regenerate `skills/review/SKILL.md`. `/review` returns to today's single-agent inline pass. The runtime skills (`/code-review`, `/security-review`) remain available for ad-hoc use but are no longer wired into `/review`.

Rollback signal that would trigger this:
- merge-auditor false-positive rate exceeds ~30% (telemetry-measured) such that save-blocks become more annoying than the duplication-reduction is worth; OR
- runtime `/code-review` or `/security-review` is removed or significantly degraded upstream AND the degraded-path single-agent path is found to be undermaintained because its checklist drifted while no one was paying attention.

Rollback time: < 15 minutes (similar surface to SPEC-018).

## Open Questions

- [ ] Should kit `/review` expose `--comment` (post findings as inline PR comments) and `--fix` (apply findings to working tree) flags by passing them through to the primary-path `/code-review` invocation? — owner: design, by: first user request for either flag.
- [ ] Should the kit's effort level (default / `ultra`) be configurable per-skill or per-issue? Runtime `/code-review` supports low/medium/high/max/ultra; kit could either pick one default or pass through user choice. — owner: design, by: first time a user explicitly wants ultra depth via kit `/review`.
- [ ] When `/code-review` and `/security-review` produce overlapping findings (a single bug flagged by both), should the synthesizer dedupe by file+line+rule or keep both with a cross-reference? — owner: design, by: first observed duplicate in real review output; pick whichever produces fewer merge-auditor false positives.
- [ ] Should `agents/reviewer.md`'s degraded-only block be split into two separate agents (`reviewer-code` / `reviewer-security`) so each can degrade independently per dimension, instead of one agent that toggles internal blocks? — owner: design, by: first time mixed-mode (one runtime present, one absent) ships and produces awkward output.
- [ ] Should the merge-auditor's "severity_changed" finding type allow ↑-only changes (kit upgrading runtime's High to Critical because of kit-specific context) and only block ↓ changes? — owner: process, by: first observed legitimate upgrade case.
- [ ] How should this issue interact with the future ISSUE-002 eval gate (when un-deferred)? Eval-as-judge over `review_notes.md` could either consume the merged notes directly or score the runtime outputs and kit-distinctive findings separately. — owner: design, by: ISSUE-002 un-defer event.
