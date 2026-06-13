# SPEC-011: Kill WebFetch reference fabrication — image-grounded references only

> Linked Issue: ISSUE-011
> Status: `accepted`
> Date: 2026-06-14
> Author: claude-dev-kit

## Problem

The `/uiux`, `/mobile-uiux`, and `/desktop-uiux` skills' Phase 2 Reference Research step instructs the model to `WebFetch` a Dribbble / Mobbin / awwwards URL and "extract concrete visual specifics: exact hex colors, font pairings, layout choice, shadow style." `WebFetch` returns parsed text — not pixels. The model is therefore being prompted to write specific values (e.g., `#1A1A1A on #F5EFE6`, `Fraunces 96/0.92`) from text descriptions, which is fabrication regardless of the `(indirect)` disclaimer downstream.

## Context

- The three uiux skill templates each contain the same fabrication shape ("Step 2 — Visual fetching via WebFetch (CRITICAL — do not skip)").
- `scripts/screenshot_pilot.py` already implements headless capture (Playwright → Chrome/Chromium fallback) for pilot screens; this backend can be reused for reference URLs.
- The Reference Anchor section is downstream input to the Decision Matrix, design philosophy, and Signature Move — fabricated hex/font values propagate into every later phase.
- This is a correctness defect, not a quality improvement (per the reviewer who flagged it).

## Options

### Option A: Image-grounded only — Path (a/b/c) explicit selection
- **Approach**: Three paths. Path (a) user-provided image URLs/paths → Read directly. Path (b) page URL → `scripts/capture_reference.py` captures to PNG → Read. Path (c) no images available → skip Reference Anchors entirely with an explicit one-line warning. Remove `WebFetch` from each skill's `allowed-tools`.
- **Pros**:
  - Eliminates the fabrication affordance (structural, not advisory).
  - Reuses existing `screenshot_pilot.py` browser logic with no new dependencies.
  - Regression-guarded by 4 tests (grep + capture script + skip path + allowed-tools).
- **Cons**:
  - Users without a browser backend installed lose the URL-based path (must use Path a or c).
- **Trade-off**: +1 script (~150 LOC), +4 guard tests, -1 fabrication vector; 0 new runtime dependencies; -1 user code path for browser-less environments.

### Option B: Keep WebFetch but strengthen the disclaimer
- **Approach**: Leave the WebFetch instruction in place, replace `(indirect)` with a stronger marker (e.g., `[FABRICATED — verify]`), tell the model not to trust the extraction.
- **Pros**:
  - Zero code changes; zero new scripts.
- **Cons**:
  - Disclaimers do not change model behavior reliably; the fabrication is structural, not motivational.
  - Downstream consumers (Signature Move, design system) still receive fabricated hex/font values.
- **Trade-off**: -1 script vs A, 0 LOC delta; -100% correctness gain (the fabrication continues).

### Option C: User must always provide images, no skip path
- **Approach**: Hard-require image input; refuse to proceed without 1–3 image references.
- **Pros**:
  - Strongest grounding guarantee.
- **Cons**:
  - Breaks the no-reference flow (e.g., genuinely novel categories with no good reference). Phase 2 ships nothing if user can't supply images.
  - Existing kit philosophy is "skip gracefully with explicit warning, never silently fail" — this option violates it.
- **Trade-off**: vs A, -1 skip path; -100% novel-category coverage; +0 quality where Path (a) was already available.

## Decision

**Chosen: Option A.**

The trade-off line "+1 script, +4 guard tests, -1 fabrication vector; 0 new runtime dependencies" wins because (i) it makes the failure mode structurally impossible by removing `WebFetch` from `allowed-tools`, (ii) it reuses the already-installed Playwright/Chromium backend, and (iii) it preserves the kit's "skip-with-explicit-warning" idiom for environments without a browser. Option B keeps the disclaimer-fix antipattern; Option C breaks valid no-reference workflows.

## Trade-offs Accepted

- Users in browser-less environments (cloud sandboxes, CI without Playwright) lose the URL-based path and must either install a backend or supply images directly. Documented in the skip warning.
- Anti-reference research can still use WebSearch for *titles* of criticism articles — those are read by the model from its own knowledge of the pattern, not extracted from page text. This asymmetry is deliberate.
- The 5-cue / 3-5 anti-cue counts are unchanged in this spec — anchor tuning is ISSUE-012's scope.

## Migration

1. Land `scripts/capture_reference.py` + 10 unit tests (slug derivation, CLI argument errors, no-backend exit code, success path stub).
2. Rewrite Phase 2 step 6.5 / 7.5 in all three uiux SKILL.md.tmpl files: WebFetch instruction removed, three paths added, skip warning added.
3. Update the Reference Anchors output spec downstream in each template to cite image paths (not generic URLs).
4. Strengthen the Phase 2 CHECKPOINT to require either image-cited cues OR an explicit skip line.
5. Remove `WebFetch` from `allowed-tools` in all three uiux skills (the structural guarantee).
6. Regenerate SKILL.md files via `scripts/gen_skills.py`.
7. Land `tests/test_uiux_reference_fabrication_guard.py` with 4 guard cases (forbidden shape regex, capture script mention, skip path mention, no WebFetch in allowed-tools).
8. Create `docs/references/` with a `.gitkeep` explaining its purpose. No data migration needed — existing `design_philosophy.md` files keep their old anchors; they degrade quietly when this issue lands and can be re-run.

## Rollback

Revert the three SKILL.md.tmpl edits. Add `WebFetch` back to `allowed-tools`. Regenerate SKILL.md. Delete `scripts/capture_reference.py`, `tests/test_capture_reference.py`, `tests/test_uiux_reference_fabrication_guard.py`. `docs/references/` becomes a vestigial directory (harmless). Rollback time: < 5 minutes.

## Open Questions

- [ ] Should `scripts/capture_reference.py` support `--full-page` capture for long landing pages? — owner: design, by: first real Path (b) usage that requests it.
- [ ] Should the Phase 2 CHECKPOINT have a machine-verifiable check (parse design_philosophy.md, validate every cue cites an image path)? — owner: process, by: 3 sprints from now if cue-citation regressions appear in review_notes.
- [ ] Should anti-reference research also become image-grounded (capture criticism articles' screenshots)? — owner: design, by: when an anti-cue is observed to be fabricated.
