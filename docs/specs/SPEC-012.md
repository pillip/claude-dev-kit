# SPEC-012: Reference Anchor tuning — 2–3 strong cues + 1 literal_quote

> Linked Issue: ISSUE-012
> Status: `accepted`
> Date: 2026-06-14
> Author: claude-dev-kit

## Problem

Phase 2 Reference Anchor required "5 specific visual cues to adopt." Reviewers observed that 5 cues create **averaging pressure** — the model picks safe, generic cues across the set and the chosen direction degrades to "generic premium SaaS." Separately, the kit lacks an anchor that forces the prototype to render **brand-specific verbatim content**, so a Signature Move can be implemented while the prototype still reads as a sample app for a generic SaaS product.

## Context

- ISSUE-011 just landed image-grounded references — anchors now cite real pixels, not WebFetch fabrications.
- The reviewer who flagged "averaging pressure" suggested 2–3 strong cues + 1 literal quote (a specific word, number, glyph, or shortcut drawn from the brand/domain).
- ISSUE-010 (Pilot Gate hardening) needs a specificity check: "3 details that ONLY make sense for THIS product." The literal_quote becomes one of those 3 details.
- The three uiux templates (`/uiux`, `/mobile-uiux`, `/desktop-uiux`) all carry the same Reference Anchor pattern.

## Options

### Option A: Reduce to 2–3 strong cues + mandatory literal_quote + verbatim render check
- **Approach**: Change "5 cues" → "2–3 strong cues" in all three templates. Add a `literal_quote:` field requirement (skippable only if Phase 1.5 interview was explicitly skipped). Phase 2 CHECKPOINT enforces the field is populated; Phase 5.x verification phase grep-checks the literal string appears verbatim in rendered output.
- **Pros**:
  - Fewer-and-deeper cues remove averaging pressure.
  - The literal_quote provides one of the 3 product-specific details ISSUE-010 will require.
  - The verbatim grep is mechanical — Phase 5 can verify without LLM reasoning.
- **Cons**:
  - Two changes (cue count + literal_quote) in one PR — slightly higher review surface.
- **Trade-off**: +1 mandatory field (literal_quote) per template, +1 verification step per template (~30 lines each), +1 guard test file (6 cases); -2 anchored cues per spec; -100% averaging pressure from 5-cue spec.

### Option B: Reduce cue count only, no literal_quote
- **Approach**: Change "5 cues" → "2–3 strong cues" but skip the literal_quote.
- **Pros**:
  - Smaller change, easier to review.
- **Cons**:
  - Loses the strongest specificity anchor — the prototype can still render generic copy/numbers.
  - ISSUE-010's specificity check has nothing concrete to anchor on.
- **Trade-off**: -1 mandatory field vs A, -1 verification step; -100% on the strongest specificity guarantee.

### Option C: Add literal_quote only, keep 5 cues
- **Approach**: Add literal_quote but leave cue count at 5.
- **Pros**:
  - No averaging-pressure debate.
- **Cons**:
  - The reviewer's "averaging pressure" diagnosis was the more cited concern.
  - 5 generic cues + 1 strong literal_quote still averages out in practice.
- **Trade-off**: vs A, +0 averaging-pressure relief; +100% on literal_quote anchor but lose the cue-density win.

## Decision

**Chosen: Option A.**

The trade-off line "+1 mandatory field, +1 verification step, +1 guard test, -2 anchored cues, -100% averaging pressure" wins because both changes work together — the smaller cue set forces deeper specificity per cue, and the literal_quote turns "specific" from a property of cue text into a property of rendered output. Doing one without the other (Option B or C) achieves less than half the value at almost the same cost.

## Trade-offs Accepted

- Some teams prefer the 5-cue ritual for thoroughness; this PR reframes it as a slop vector. Documented in the SPEC and skill body.
- The literal_quote MUST be concrete text — adjectives like "luxury", "trust", "premium" are rejected at the field level. This is a hard requirement; teams that want abstract "vibe" anchors will not have them.
- When Phase 1.5 interview is skipped (user opt-out), literal_quote becomes optional. The CHECKPOINT records this with `literal_quote: (skipped — interview not run)` so future readers know it was deliberate.
- The verbatim grep is exact-string only — no substring or normalization. A literal_quote `"47.2-A"` does NOT match `47-2-A`. This deliberate strictness prevents partial-match drift.

## Migration

1. Edit `skills/uiux/SKILL.md.tmpl`, `skills/mobile-uiux/SKILL.md.tmpl`, `skills/desktop-uiux/SKILL.md.tmpl`:
   - Phase 2 step 6.5 / 7.5 synthesis section: "5 specific visual cues" → "2–3 strong cues" + add the `literal_quote:` block with concrete examples per platform.
   - Downstream `design_philosophy.md` output spec: cue count updated, `literal_quote:` field declared.
   - Phase 2 CHECKPOINT block: enforces (a) Signature Move, (b) skip-or-present, (c) 2–3 cues + literal_quote populated (or `(skipped — interview not run)`).
   - Phase 5.x prototype verification: new "Literal quote verbatim render check" step grep-checks the literal string in `prototype/screens/*.html`, `prototype-mobile/src/screens/*.tsx`, or `prototype-desktop/src/screens/*.tsx`.
2. Regenerate SKILL.md via `scripts/gen_skills.py`.
3. Land `tests/test_reference_anchor_tuning.py` with 6 cases.
4. No data migration — existing `design_philosophy.md` files keep their old anchors and degrade quietly. Re-running `/uiux` (e.g., for new sprints) lands the new format.

## Rollback

Revert the three SKILL.md.tmpl edits. Regenerate SKILL.md. Delete `tests/test_reference_anchor_tuning.py`. Existing `design_philosophy.md` files with new-format anchors continue to work — the validator does not reject them, just no longer enforces them. Rollback time: < 5 minutes.

## Open Questions

- [ ] Should the literal_quote verbatim grep be a separate machine-checked script (e.g., `scripts/verify_literal_quote.py`) instead of an in-skill instruction? — owner: design, by: when a real /uiux run shows the instruction is being skipped.
- [ ] Should anti-cues also adopt fewer-and-deeper (currently 3–5)? — owner: design, by: when reviewers observe averaging pressure on the anti side too.
- [ ] Should the cue count vary by archetype (e.g., 2 cues for minimalist directions, 3 for maximalist)? — owner: design, by: after 5 real /uiux runs land enough data to calibrate.
