# SPEC-010: Pilot Gate hardening — observation, separate-context critic, specificity, auto-cycle

> Linked Issue: ISSUE-010
> Status: `accepted`
> Date: 2026-06-14
> Author: claude-dev-kit

## Problem

Phase 5A's single-pass pilot critique had four structural defects that compounded:
1. **Self-grading sycophancy** — the same agent context that generated the pilot scored it. Six-axis scores trended `P5 H4 E5 S4 R5 V5`-shaped regardless of the actual output.
2. **Leading questions** — prompts that name the Signature Move and aesthetic prime the agent to confirm them ("Is the Signature Move visible at the expected location?" almost always returned Yes).
3. **No automatic correction loop** — after self-critique, control passed straight to the user. If the critique flagged anything, the user was the only fixer.
4. **Missing product specificity check** — the gate verified the *system* (Signature Move applied, aesthetic readable) but not whether the pilot showed anything that would be wrong for a different product. Generic-but-Signature-Move-compliant slop passed.

## Context

- ISSUE-011 (image-grounded references) and ISSUE-012 (2-3 cues + literal_quote) landed earlier this session. The literal_quote is a natural anchor for a specificity check.
- ISSUE-013 (design-auditor / ui-reviewer scope split) preserved the `design-auditor` agent name — this gate now invokes it from a separate Task context.
- The three uiux templates (`/uiux`, `/mobile-uiux`, `/desktop-uiux`) all carry the same Phase 5A shape but with platform-specific render paths:
  - web: PNG screenshot via `screenshot_pilot.py`
  - mobile: Expo runs live in simulator — no in-skill PNG path → degraded mode is the default
  - desktop: Electron runs live — Playwright+Electron can capture; otherwise degraded mode
- The kit's failure mode budget for runaway loops is "small but not zero." A 3-cycle hard cap is the agreed backstop.

## Options

### Option A: 4-substep gate — observe → separate critic → specificity → auto-cycle (≤3)
- **Approach**:
  - **Step 2.x.0 — Neutral observation**: 5 plain factual statements about what renders, with banned vocabulary (`signature move`, `aesthetic`, `philosophy`, …) so the observer cannot use the generator's framing.
  - **Step 2.x.1 — Separate-context critique**: invoke `design-auditor` via the Task tool (and `ui-reviewer` where its scope applies) with the observations + PNG/source + system docs as inputs. Sub-agent returns 6-axis scores with cited evidence per axis.
  - **Step 2.x.2 — Specificity check**: sub-agent must name 3 details that ONLY make sense for THIS product. literal_quote (ISSUE-012) counts as exactly 1; the other 2 are independent. Fewer than 3 → FAIL.
  - **Step 2.x.3 — Auto-correction cycle** (hard cap N=3): on any axis < 3, specificity FAIL, or flagged slop signals, identify the patch layer (philosophy / system / layout / pilot-only), patch, re-render, re-observe, re-critique, re-specificity. After cycle 3, freeze and surface to the user with the cycle log.
  - **Degraded mode**: when screenshot backend (web) or Playwright+Electron (desktop) is unavailable, or Expo is the runtime (mobile), critique runs against pilot source. **Never silently skip** — record `pilot_degraded: <reason>` in the log.
- **Pros**:
  - Breaks the generator-as-judge loop (Step 2.x.1).
  - Specificity check (Step 2.x.2) catches "signature-move-compliant slop" — the failure mode the previous gate missed.
  - Auto-cycle reduces "everything escalates to the user" load.
  - 14 declarative tests parse the markdown and catch any future drift.
- **Cons**:
  - Each pilot now does up to 3 critique rounds — significant token cost on the worst case.
  - Sub-agent invocations add latency (Task tool round trip).
  - The 6-axis rubric and specificity question live in the skill body, not in a separate machine-checked artifact.
- **Trade-off**: +3 substeps per skill (~80 lines × 3 templates), +14 guard tests; +3 cycles maximum per pilot (worst case +3x token cost on the critique loop); -1 sycophancy vector, -1 leading-question vector, -1 missing-specificity vector; -100% silent-skip behavior under degraded mode.

### Option B: Add only the separate-context critic (no observation, no cycle, no specificity)
- **Approach**: Keep the existing self-critique structure; replace the inline critique with a single Task call to design-auditor.
- **Pros**:
  - Smallest patch; lowest token cost.
- **Cons**:
  - Doesn't fix leading questions — the user-facing prompts still name the Signature Move and aesthetic upfront.
  - Doesn't add specificity check — same blind spot.
  - No auto-cycle — every failure still hits the user.
- **Trade-off**: vs A, -3 substeps; -0 cycles overhead; -3 of the 4 defects unaddressed; +0% improvement on the specificity blind spot.

### Option C: Run N parallel critics + vote (no observation, no cycle)
- **Approach**: Spawn 3 parallel design-auditor calls and take the majority verdict.
- **Pros**:
  - Reduces single-judge variance.
- **Cons**:
  - Three judges sharing the same priming still produce three sycophantic answers — variance reduction without root-cause fix.
  - 3× token cost without the specificity or cycle benefit.
- **Trade-off**: vs A, +2 redundant judge calls, -1 observation step, -1 cycle, -1 specificity check; net cost similar, defect coverage strictly worse.

## Decision

**Chosen: Option A.**

The trade-off "+3 substeps, +14 guard tests, +3 worst-case cycles" wins because each substep targets a *named* failure mode from the reviewer's diagnosis: observation breaks priming, separate context breaks sycophancy, specificity breaks signature-compliant-slop, the cycle replaces "everything to the user" with "everything tried first, escalated with history." Options B and C address ≤1 of the 4 defects.

## Trade-offs Accepted

- Up to 3 cycles of patch → re-render → re-critique per pilot is significant compute. The N=3 hard cap is the backstop — past cycle 3 the gate surfaces to the user with the full history instead of looping forever.
- Each cycle records a one-line entry in `prototype/screens/<pilot>.cycles.log` (web) or the platform equivalent. This log is part of the user-facing artifact at Step 3, so the user can see what the gate already tried.
- The "banned vocabulary" list in Step 2.x.0 is explicit (`signature move`, `aesthetic`, `philosophy`, …). If a future template adds a new framing word, the observation step's anti-priming protection drops. Documented in the skill body; the guard test catches missing core terms.
- Mobile runs live in Expo with no PNG capture in-skill — degraded mode is the default. The critique runs against source. This is documented (`pilot_degraded: no_screenshot_input`) so users see the limitation and can opt to install a separate screenshot tooling later.
- Sub-agent invocations require the `Task` tool to be in `allowed-tools` (already present in all three uiux skills).

## Migration

1. Edit `skills/uiux/SKILL.md.tmpl`, `skills/mobile-uiux/SKILL.md.tmpl`, `skills/desktop-uiux/SKILL.md.tmpl`:
   - Replace the existing single-pass self-critique block in step 14.6 / 2.5 / 2.5 with the 4-substep structure (web uses 2.0/2.1/2.2/2.3; mobile/desktop use 2.5.0/2.5.1/2.5.2/2.5.3 to slot into the existing numbering).
   - Update Step 3 (user gate) to share `<pilot>.critique.md` + `<pilot>.cycles.log` artifacts.
   - Add explicit "Do NOT silently skip" + `pilot_degraded` language in each template.
2. Regenerate SKILL.md via `scripts/gen_skills.py`.
3. Land `tests/test_pilot_gate_hardening.py` with 14 cases covering: Neutral observation declared, banned vocabulary listed, design-auditor invoked via Task, separate-context noted, specificity check present with 3 details + literal_quote counts as 1, auto-correction cycle present with N=3 cap, cycles.log documented, degraded mode declared with no-silent-skip, user gate shares critique artifact and asks about specificity details.
4. No backwards-compat shim — past `/uiux` runs that completed under the old gate are not invalidated. Future runs land the new gate.

## Rollback

Revert the three SKILL.md.tmpl edits. Regenerate SKILL.md. Delete `tests/test_pilot_gate_hardening.py`. The previous single-pass critique resumes. Rollback time: < 5 minutes. No data migration.

## Open Questions

- [ ] Should the 6-axis rubric live in a separate `templates/pilot_critique_rubric.md` instead of inline in the skill body, so it can be tuned without touching the skill? — owner: design, by: after 3 real pilot runs to see how often the rubric needs adjustment.
- [ ] Should the cycle history (`cycles.log`) feed into ISSUE-001's telemetry schema so we can measure "how often does cycle 1 → cycle 3 actually shift scores"? — owner: telemetry, by: ISSUE-001 implementation kickoff.
- [ ] Should the specificity check require *named* details (e.g., a list of 3 concrete strings) so the verification can be mechanical instead of agent-reasoned? — owner: process, by: when a real pilot run shows specificity FAIL despite the literal_quote being present.
