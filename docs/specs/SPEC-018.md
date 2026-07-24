# SPEC-018: Research grounding hardening — delegate to `/deep-research` + thin synthesis guard

> Linked Issue: ISSUE-018
> Status: `draft`
> Date: 2026-06-18
> Author: claude-dev-kit

## Problem

`/brainstorm` and `/bizanalysis` (and their backing `brainstormer` / `business-analyst` agents) instruct the model to `WebSearch`/`WebFetch` and "extract" market size, TAM/SAM/SOM, competitor pricing, and existing-landscape claims from parsed page text. `WebFetch` returns parsed text — not a structured numeric extraction — so the model is being prompted to write specific numeric and factual claims (e.g., "global TAM is $12.4B in 2025", "competitor X charges $29/seat/month") from descriptions that may or may not contain those specifics. This is the same fabrication shape that ISSUE-011 already removed from `/uiux`. Meanwhile, Claude Code ships a `/deep-research` skill ("fan-out web searches, fetch sources, adversarially verify claims, synthesize a cited report") that already solves the research-grounding problem better than the kit's bespoke `WebSearch + cite sources` instruction. The kit is re-implementing — poorly — a capability the runtime already provides.

## Context

- `skills/brainstorm/SKILL.md.tmpl` and `skills/bizanalysis/SKILL.md.tmpl` both declare `allowed-tools: Read, Glob, Grep, Write, Edit, WebSearch, WebFetch` and call them in free-form prose ("Use WebSearch/WebFetch to investigate market size, trends, TAM/SAM/SOM. Cite sources.").
- `agents/brainstormer.md` (model: opus) Existing Landscape: "When helpful, use WebSearch/WebFetch to research the existing landscape" — optional + paraphrased.
- `agents/business-analyst.md` (model: opus) Market Research / Competitive Landscape: same free-form web research with no verbatim-quote contract.
- `/deep-research` appears in the runtime's `available skills` list. It is **not a kit-bundled skill and not a user-installed plugin** (filesystem check shows it isn't under `~/.claude/plugins/` or under `agents/`/`skills/` in this repo); it is exposed by the Claude Code runtime itself. The kit can treat it the same way it treats `Task`, `AskUserQuestion`, or `Workflow` — a platform capability invokable through the standard skill mechanism.
- The kit already adopts "platform-first" elsewhere: it does not reinvent Task orchestration, agent invocation, hook events, or user prompts. Research should follow the same rule. (Memory: `feedback_platform_first.md`.)
- ISSUE-011 / SPEC-011 set a precedent — *when the platform doesn't provide the capability* (image-grounded reference reading), the kit ships a thin script (`capture_reference.py`) and a grounding contract. SPEC-018 inverts the question: for research grounding the platform DOES provide the capability, so the kit's job shrinks to "call it correctly + apply a thin synthesis guard so the cited report's claims aren't paraphrased away in our 5-section template".
- ISSUE-010 / SPEC-010's separate-context critic pattern still applies, but at a shrunken surface — `/deep-research` already runs internal adversarial verification, so the kit's auditor only checks the *synthesis step* (did our SWOT bullet preserve the upstream citation, or did we drop/distort it?).
- `requirement-analyst` does NOT use web tools and is out of scope here.
- "Absolute zero hallucination" is not achievable with an LLM. Delegating heavy research to `/deep-research` lowers the floor *for the research step* (because that skill already implements adversarial verification); the thin synthesis guard catches the *kit-side* paraphrase risk. A claim that is verbatim in `/deep-research`'s cited report but whose interpretation is wrong (conditional forecast cited as fact) still survives. The SPEC documents this honestly rather than promise zero.

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line.

### Option A: Build a kit-internal grounding pipeline (capture script + validator + auditor + claim schema)
- **Approach**: Ship `scripts/capture_source.py` (sibling to `capture_reference.py`), `scripts/validate_research_claim.py`, `agents/research-auditor.md`, and `templates/research_claim.md`. Every numeric or factual claim in `business_analysis.md` and `brainstorm_notes.md` carries `{quote, source_url, accessed_at, published_at?}`. Pre-save validator greps `quote` against the captured snapshot; missing → reject. `research-auditor` runs in a separate Task context with refute-first prompt. Sections with no source render as the literal `Data: not available …` line. Triangulation: TAM/SAM/SOM with only 1 distinct domain → `range … [single-source]`. Freshness: snapshots >12 months → `[stale]`.
- **Pros**:
  - Self-contained inside the kit; no runtime-capability dependency.
  - Mechanical grep validation is cheap and deterministic.
- **Cons**:
  - Re-implements (poorly) what `/deep-research` already does — fan-out, multi-source verification, adversarial check, cited synthesis.
  - NIH anti-pattern: kit grows scripts + agents + tests that need maintenance, while the platform improves `/deep-research` independently and the kit must track that improvement manually.
  - Adversarial verification in a single new agent is weaker than `/deep-research`'s multi-agent perspective-diverse verify.
- **Trade-off**: +1 capture script (~120 LOC), +1 validator (~150 LOC), +1 new agent, +~10 guard tests; +~2s capture latency per source; -1 fabrication vector; **+ permanent maintenance surface that overlaps a runtime capability the kit can't influence**.

### Option C: Strengthen prompt language, keep WebFetch and free-form extraction
- **Approach**: Leave `allowed-tools` and free-form extraction intact. Replace `cite sources` with a stronger marker (`[QUOTE-REQUIRED]`) and add Self-Review checkboxes asking the model to confirm every number has a source.
- **Pros**:
  - Zero new code.
- **Cons**:
  - Same disclaimer-antipattern SPEC-011 already rejected. Bold markers do not change model behavior reliably; the affordance to fabricate remains.
  - Self-Review runs in the same context as generation → ISSUE-010's sycophancy critique applies.
- **Trade-off**: 0 LOC, 0 new tests, -0% fabrication (no structural change); -0 capture latency vs A and D (the cost they pay buys the correctness they deliver).

### Option D: Delegate research to `/deep-research`, apply a thin synthesis guard, degrade gracefully when unavailable
- **Approach**:
  - **Heavy research** (Market / Competitive / Pricing dimensions in `/bizanalysis`, Existing Landscape in `/brainstorm`) is delegated to the runtime's `/deep-research` skill. Each dimension is sent as a refined research question; `/deep-research` returns a cited report with verbatim source quotes.
  - **Synthesis step** in the kit ingests the cited report and folds its claims into the fixed 5-section template (Executive Summary, Market Analysis, Competitive Landscape, Business Model, Risks & Mitigations). The synthesis step is *mechanical mapping*, not paraphrase: every claim copied into the kit's template must preserve the upstream `{quote, source_url}` triple verbatim. A small validator confirms each claim in the saved output appears verbatim in the `/deep-research` report it came from. Sections that the report covers thinly render `Data: not available — re-run /deep-research with a sharper question or accept "no data".`
  - **Thin synthesis-side critic** (Task tool, `subagent_type: synthesizer-auditor`) runs once over (kit template draft + `/deep-research` report) with a refute-first prompt: "for each claim in the draft, does the same claim — same numbers, same direction — appear in the report? Flag drops, distortions, scope changes."
  - **No internal triangulation logic** — `/deep-research` already runs multi-source verification; the kit reads its verdict and honors any flags it carries (`[single-source]`, `[contested]`, etc.) into the kit's output.
  - **Graceful degrade** when `/deep-research` is not exposed by the runtime: fall back to Option A's lighter in-kit pipeline (capture script + grep validator + research-auditor agent). Skill prefamble probes for the skill's availability and picks the path.
  - `allowed-tools` keeps `WebSearch` for sanity-checking (and for the degraded path); `WebFetch` is removed from free-form claim extraction in both skill templates.
- **Pros**:
  - Uses a runtime capability that already implements fan-out + adversarial verify + cited synthesis — orders of magnitude more thorough than anything the kit would build inline.
  - Kit's responsibility shrinks to two things: (i) call `/deep-research` with well-scoped questions, (ii) guard the synthesis step against paraphrase. Maintenance surface drops.
  - Future `/deep-research` improvements (better verifiers, broader source coverage) propagate to the kit's `/bizanalysis` automatically.
  - The degraded path preserves a usable in-kit pipeline (Option A) so the skills don't hard-fail on environments without `/deep-research`.
- **Cons**:
  - Each bizanalysis run is heavier (`/deep-research` wall-clock can be tens of seconds to minutes for thorough mode). Acceptable: research correctness > research speed.
  - Synthesis-side validator depends on `/deep-research`'s report format being stable. Format probe at invocation time lets the synthesizer degrade gracefully on format drift.
  - Two execution paths (primary + degraded) double the test matrix.
- **Trade-off**: +1 synthesizer module (~80 LOC) + 1 thin synthesis-side critic agent + ~8 guard tests; **-3 scripts vs Option A** (no `capture_source.py` / `validate_research_claim.py` / standalone research-auditor on the primary path); -1 fabrication vector AND -1 maintenance surface that overlapped the runtime; +tens of seconds–minutes per run for heavy research; +1 graceful-degrade branch (kept compact by reusing Option A's pieces only on the degraded path).

## Decision

**Chosen: Option D.**

The "+1 synthesizer, +1 thin critic, -3 scripts vs Option A, +1 graceful-degrade branch" line wins because (i) `/deep-research` is a runtime capability the kit can invoke the same way it already invokes Task / Workflow / AskUserQuestion — re-implementing it inside the kit is NIH, (ii) the kit's responsibility properly shrinks to what only the kit can do (mapping a cited research report into the kit's fixed 5-section template + guarding the mapping against paraphrase), and (iii) Option A's grounding pieces are not wasted — they survive as the degraded-path fallback when `/deep-research` is unavailable. Option C is the same disclaimer-antipattern SPEC-011 already rejected.

This decision reverses the SPEC's earlier draft (which had chosen Option A). The earlier rejection of "use `/deep-research`" rested on a weak premise — that the skill was user-supplied and unguaranteed. It is a runtime-exposed capability, on par with Task. The kit's "stand-alone" rule is about not depending on third-party plugins; it does not extend to refusing to use the runtime itself.

## Trade-offs Accepted

- **Residual hallucination is still non-zero.** `/deep-research`'s adversarial verification pushes the floor down for the research step; the synthesis-side critic catches kit-side paraphrase distortion. A claim that is verbatim in the upstream report but interpreted wrong in the kit's template (e.g., a conditional forecast quoted as fact, scope mismatch) survives both. Documented in `skills/bizanalysis/SKILL.md` rather than promised away.
- **Heavy research costs wall-clock time and tokens.** `/deep-research` fan-outs across multiple agents per dimension. Accepted: bizanalysis is a pre-PRD checkpoint, not a hot path; correctness > latency.
- **Synthesis-side critic catches a narrow class of failures.** It only checks "did the kit preserve what the report said?", not "is the report correct?". Correctness of the report is delegated to `/deep-research`'s own verification. If `/deep-research` itself fabricates, the kit's critic will not notice; treat this as the platform's responsibility, surface a one-line caveat in skill docs.
- **Degraded path is a real fallback, not a façade.** When `/deep-research` is absent we DO ship the Option A pieces (`capture_source.py`, `validate_research_claim.py`, `agents/research-auditor.md`, `templates/research_claim.md`) so the skill remains usable. This means Option A's code does land — just gated behind a runtime probe, not as the primary path. The double-path is the cost of "graceful degrade" being honest.
- **`/deep-research` report format may drift across Claude Code versions.** Synthesizer reads the report through a format probe that recognizes both structured (citations as records) and prose (citations inline) modes, and falls back to passing the whole report to the synthesis-side critic if probe fails.
- **No internal triangulation rule.** The kit honors flags `/deep-research` puts on its claims rather than re-implementing the rule. If a user complains that `/deep-research`'s triangulation policy is wrong for a dimension, the right fix lives upstream, not in the kit.
- **`requirement-analyst` deliberately untouched.** If a need surfaces, a follow-up SPEC re-applies this delegation pattern there.
- **`/brainstorm` Discovery phase is unchanged.** Only the Existing Landscape section delegates to `/deep-research`. Discovery's Socratic questioning is a kit-distinctive interaction shape, not research; no platform skill subsumes it.

## Migration

1. **Probe primitive**: a tiny `scripts/has_skill.py <name>` (or inline Bash check in the skill preamble) detects whether `/deep-research` is exposed by the runtime. Used by both `/brainstorm` and `/bizanalysis` at start.
2. **Synthesizer module**: `scripts/synthesize_from_deep_research.py` — pure function. Inputs: `/deep-research` cited report + section template. Output: kit-shaped section with each claim carrying `{quote, source_url}` copied verbatim from the report. Unit tests: structured-report mode, prose-report mode, missing-citation handling, "Data: not available" fallback.
3. **Synthesis-side critic agent**: `agents/synthesizer-auditor.md` (tools: `Read`, `Grep`; model: sonnet — light task, cheap critic). Refute-first prompt: "for each claim in the draft, does the same claim — same numbers, same direction — appear in the `/deep-research` report? Flag drops, distortions, scope changes."
4. **Skill template rewrites**:
   - `skills/bizanalysis/SKILL.md.tmpl`: Market / Competitive / Pricing / Risks each invoke `/deep-research` with a refined per-dimension question. After all dimensions return, run synthesizer + synthesizer-auditor; audit findings of type `claim_dropped` / `claim_distorted` block save.
   - `skills/brainstorm/SKILL.md.tmpl`: Existing Landscape invokes `/deep-research` (scoped, lighter question). Discovery and Ideation phases unchanged.
   - Both: remove `WebFetch` from `allowed-tools` (the structural guarantee that free-form extraction is gone on the primary path). Keep `WebSearch` for sanity-check usage.
5. **Agent updates**: `agents/business-analyst.md` and `agents/brainstormer.md` rewrite Market Research / Existing Landscape steps to call `/deep-research`; remove "When helpful, use WebFetch" language. **`tools:` frontmatter drops `WebSearch, WebFetch`** — without this the delegation gate at the skill layer is bypassable by direct Task invocation of the agent (e.g., from `/kickoff` or sprint), which would void the fabrication-prevention guarantee. Audit found via cross-file NIH review 2026-06-18.
6. **Degraded-path bundle** (Option A pieces): land `scripts/capture_source.py`, `scripts/validate_research_claim.py`, `agents/research-auditor.md`, `templates/research_claim.md` — all gated behind the runtime probe. Document explicitly in skill docs that the degraded path is functionally similar to ISSUE-011's `capture_reference.py` flow but text-domain.
7. **Telemetry**: add `research_delegated_to_deep_research`, `research_degraded_path_used`, `synthesis_claim_dropped`, `synthesis_claim_distorted`, `synthesis_audit_finding` to `docs/telemetry_schema.md`. Degrade to local JSONL append if ISSUE-001 pipeline is unshipped.
8. **Grep guard test**: `tests/test_research_fabrication_guard.py` confirms no WebFetch call in brainstorm/bizanalysis is used for free-form claim extraction; only `/deep-research` invocation OR degraded-path `capture_source.py` usage is allowed.
9. **Honest framing in skill docs**: `skills/bizanalysis/SKILL.md` (post-regen) carries a short "Limits" subsection: `/deep-research` lowers the research-correctness floor; the synthesis-side critic catches paraphrase distortion; misinterpretation of correctly-quoted material remains a residual risk.
10. **Regenerate** SKILL.md files via `scripts/gen_skills.py`.

## Rollback

Revert the two SKILL.md.tmpl edits + two agent edits + `has_skill.py` + `synthesize_from_deep_research.py` + `agents/synthesizer-auditor.md` + telemetry entries + the grep guard test. Delete the degraded-path bundle (`capture_source.py`, `validate_research_claim.py`, `agents/research-auditor.md`, `templates/research_claim.md`). Regenerate SKILL.md. Skills return to today's WebFetch-paraphrase behavior — restores the fabrication issue, so rollback is a last resort. Signal that would trigger rollback: `/deep-research` is removed or significantly degraded by an upstream Claude Code change AND the in-kit degraded path's audit findings exceed ~30% false-positive rate (telemetry-measured) making save-blocks more annoying than fabrication.

Rollback time: < 15 minutes.

## Open Questions

- [ ] How should the per-dimension question to `/deep-research` be structured — one call per dimension (Market / Competitive / Pricing / Risks) or one call with multi-question fan-out internal to `/deep-research`? — owner: design, by: first three bizanalysis runs after landing; pick whichever produces fewer dropped claims in synthesis audit.
- [ ] When `/deep-research` flags a claim `[contested]` or `[single-source]`, should the kit propagate the flag verbatim into the kit's output or translate to its own vocabulary? — owner: design, by: first contested claim observed.
- [ ] Should `/brainstorm` Discovery phase optionally call `/deep-research` for the "What exists today?" Socratic question, or is that overkill at the discovery stage? — owner: design, by: first brainstorm run that hits a target user explicitly asking for a competitive scan during discovery.
- [ ] Should the degraded-path Option A pieces be split out into a separate dependent issue (so this issue ships the delegation cleanly first, degraded path follows)? — owner: process, by: estimate review; if combined scope exceeds 1d, split.
- [ ] Should `requirement-analyst` adopt the same delegation when its PRD source documents include external citations? — owner: process, by: when a fabricated PRD-cited number is observed downstream.
