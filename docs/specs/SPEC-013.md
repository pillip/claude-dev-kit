# SPEC-013: Split design-auditor / ui-reviewer along system vs implementation boundary

> Linked Issue: ISSUE-013
> Status: `accepted`
> Date: 2026-06-14
> Author: claude-dev-kit

## Problem

`agents/design-auditor.md` and `agents/ui-reviewer.md` had overlapping checklists (Token Consistency vs Design Token Compliance, Accessibility Baseline vs Accessibility, Copy & Content vs Copy Compliance, Component Completeness in both). Two agents running on the same project flagged the same categories with different verdicts — wasted reviewer attention, ambiguous ownership, and no signal about which agent "should have" caught a given regression.

## Context

- Both agents are invoked from `skills/review/SKILL.md` Phase 3 (design-auditor) and Phase 2 (ui-reviewer) — see lines 85 / 96 of that template.
- `skills/sprint/SKILL.md` line 159 also references both by name on the routing matrix.
- ISSUE-010's planned Pilot Gate will invoke `design-auditor` by name from a separate Task context — the literal agent name must be preserved.
- The two failure modes that motivate keeping two agents are distinct: a malformed design system (system-level) and an implementation that drifts from a well-formed system (impl-level). Merging would lose this distinction.

## Options

### Option A: Partition along system vs implementation
- **Approach**: design-auditor owns 6 system-level categories (token consistency, token coverage, component **definitions**, cross-platform alignment, philosophy compliance, copy guide **internal** consistency). ui-reviewer owns 6 implementation-level categories (rendered state coverage, copy **usage**, token **usage** in code, interaction fidelity, in-code accessibility, component **existence**). Each agent file carries a mirrored 12-row scope table that explicitly disclaims the other 6.
- **Pros**:
  - Disjoint categories at the file level — verifiable by a unit test parsing the markdown tables.
  - Each agent's checklist explicitly forbids straying into the other's scope.
  - Preserves both agent names (zero downstream breakage in /review, /sprint, ISSUE-010).
  - Boundary mnemonic: "does this say the system *declares* X, or does the implementation *do* X?"
- **Cons**:
  - 12-row scope tables add file length (~50 lines per agent).
  - Some categories (e.g., accessibility) need careful splitting between "system spec requires" and "implementation provides".
- **Trade-off**: +2 mirrored scope tables (~100 lines total), +1 boundary test file (~150 LOC), -6 duplicated checklist categories; 0 downstream consumer changes (names preserved).

### Option B: Merge into a single agent
- **Approach**: Combine both files into a single `design-reviewer` agent with one consolidated checklist.
- **Pros**:
  - One fewer file to maintain.
- **Cons**:
  - Loses the system-vs-implementation distinction (the failure modes are genuinely different).
  - Breaks `/review` Phase 2 + Phase 3 separation (each currently feeds a different output document).
  - Breaks ISSUE-010 wiring (depends on `design-auditor` name specifically).
  - One reviewer agent reasoning about both layers at once dilutes attention.
- **Trade-off**: -1 agent file, -1 separation of concerns; -2 downstream wirings (review skill + ISSUE-010); -100% system/impl signal separation.

### Option C: Keep overlap, add a routing prompt at the top
- **Approach**: Leave both agent checklists as-is, prepend a "if you see X, defer to the other agent" rule at the top of each.
- **Pros**:
  - Zero changes to existing checklists.
- **Cons**:
  - Disclaimers do not reliably shift model behavior under conflict — same failure mode as ISSUE-011's `(indirect)` label.
  - Reviewers still receive overlapping verdicts and must arbitrate manually.
  - No mechanical way to verify the boundary holds.
- **Trade-off**: -100 LOC changes vs A, +0 mechanical guarantee, -100% testable boundary.

## Decision

**Chosen: Option A.**

The trade-off line "+2 mirrored tables (~100 lines), +1 boundary test, -6 duplicated categories, 0 downstream changes" wins because (i) the boundary is testable at file-parse time (no LLM run required), (ii) each agent file becomes self-documenting about what NOT to touch, and (iii) the names are preserved so `/review`, `/sprint`, and ISSUE-010's Pilot Gate continue to work unchanged. Option B abandons a real distinction; Option C ships a disclaimer instead of a structural guarantee.

## Trade-offs Accepted

- Mirroring the scope table in both files creates a synchronization burden — the boundary test (`test_design_review_role_boundary.py`) catches drift but contributors must remember to update both files together.
- Some accessibility checks are now split (system spec for "touch targets must be ≥48dp" vs implementation verification "buttons in code render ≥48dp"). Reviewers reading the audit + review notes side-by-side need to understand both halves.
- The boundary test does not run the agents — it verifies declarations. An agent that ignores its scope at runtime will not be caught here (only by reviewer attention or a follow-up eval like ISSUE-002).
- The kit's `review_lessons.md` classification taxonomy gains slightly more categories (Copy *Usage* vs Copy *Internal*, Token *Usage* vs Token *Consistency*) — small cost.

## Migration

1. Rewrite both agent markdown files with mirrored 12-row scope tables, owned-by tables, and exclusion lines.
2. Land `tests/test_design_review_role_boundary.py` with 11 cases verifying: tables exist, categories match, partition is exclusive (✓ in exactly one column per row), partition is mirrored across files, each file mentions the other by name, exclusion lines exist, names preserved.
3. No downstream changes — `skills/review/SKILL.md`, `skills/sprint/SKILL.md`, and ISSUE-010 all reference the agents by name only.
4. No data migration — `docs/design_audit.md` and `docs/ui_review_notes.md` template structures are unchanged (only category names tightened).

## Rollback

`git revert` the two agent file rewrites. Delete the boundary test. Both agents resume with overlapping checklists. `/review` continues to work because the names are preserved across both directions. Rollback time: < 5 minutes.

## Open Questions

- [ ] Should the boundary test be promoted to a CI block (currently runs in pytest)? — owner: process, by: after first contributor PR touches one of the two files.
- [ ] Should design-auditor gain a "system spec contract" section that ui-reviewer reads as input (instead of both reading raw `design_system.md`)? — owner: design, by: after 3 reviews show ui-reviewer re-deriving the spec.
- [ ] Should ISSUE-002 (eval gate) score *both* outputs as a paired artifact, or independently? — owner: eval, by: ISSUE-002 implementation kickoff.
