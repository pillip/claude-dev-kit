# SPEC-NNN: [Imperative verb + object]

> Linked Issue: ISSUE-NNN (or `none` for ad-hoc)
> Status: `draft` | `under-review` | `accepted` | `superseded`
> Date: YYYY-MM-DD
> Author:

## Problem

[1–3 sentences. What concrete situation forces a decision? Why now? Who is affected if this is wrong?]

## Context

[Constraints that bound the choice: prior decisions, data shape, deadlines, team capacity, external dependencies. Quote specifics — file paths, schema versions, API contracts — not vibes.]

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line (numeric or +/- comparator). Vague trade-offs ("more flexible") are rejected by the validator.

### Option A: [Short name]
- **Approach**: [2–4 sentences on how this works.]
- **Pros**:
  - [Concrete benefit]
  - [Concrete benefit]
- **Cons**:
  - [Concrete cost]
- **Trade-off**: [REQUIRED measurable line, e.g., "+20% write latency, -1 service dependency, +3 days impl"]

### Option B: [Short name]
- **Approach**: [2–4 sentences.]
- **Pros**:
  - [Concrete benefit]
- **Cons**:
  - [Concrete cost]
- **Trade-off**: [REQUIRED measurable line]

### Option C: [Short name — optional]
- **Approach**: [...]
- **Trade-off**: [...]

## Decision

**Chosen: Option [A | B | C]**

[1–3 sentences: why this option wins given the context. Cite the specific trade-off line that tipped the choice.]

## Trade-offs Accepted

[Bullet list of what we are explicitly giving up. Future-you reads this to remember why a "limitation" was deliberate, not an oversight.]

## Migration

[Concrete steps to get from the current state to the target state. If schema/API changes are involved, list them with order. If no migration is needed, state that explicitly.]

## Rollback

[How to undo this decision if it turns out wrong. What signal would trigger rollback? How long does rollback take?]

## Open Questions

[Things we deliberately did NOT decide here. Each item should name who/when will decide.]

- [ ] [Question] — owner: [name], by: [date or milestone]
- [ ] [Question] — owner: [name], by: [date or milestone]
