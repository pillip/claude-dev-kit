# SPEC-006: Introduce /spec skill as the RFC layer between PRD and implement

> Linked Issue: ISSUE-006
> Status: `accepted`
> Date: 2026-06-13
> Author: claude-dev-kit

## Problem

PRD captures product intent and `/implement` codes against an issue, but the kit has no first-class artifact for the *engineering decision* behind a non-trivial issue. Real teams answer this question in a tech spec / RFC; the kit forces ad-hoc capture in PR descriptions or `Implementation Notes`, which decays and is not reviewable in isolation.

## Context

- Existing skill chain: `/prd → /kickoff → /uiux → /sprint → /implement → /review → /ship`.
- Issue model: **1 Issue = 1 PR** (kit-wide rule, see `templates/issues.md`).
- `validate_issues.py` already gates issue-level invariants; SPEC enforcement can extend that surface.
- Sprint mode must remain automated end-to-end (no human prompts mid-sprint); non-sprint mode is interactive and tolerates human gates.

## Options

### Option A: New `/spec` skill + per-issue `Spec-Required` metadata
- **Approach**: Add a dedicated skill writing `docs/specs/SPEC-NNN.md`, two new issue fields (`Spec-Required`, `Spec`), a SPEC template validator, and enforcement in `validate_issues.py`. `/implement` reads metadata and gates separately (SPEC-007).
- **Pros**:
  - Spec is a separately reviewable artifact (single source of decision history).
  - Optional by default — existing issues stay unaffected (`Spec-Required: false`).
  - Validator catches vague trade-offs at draft time.
- **Cons**:
  - Adds 1 skill + 2 metadata fields + 1 new script — surface area grows.
- **Trade-off**: +1 skill, +2 issue fields, +1 validator (~250 LOC); +0 risk to existing flows (additive only); reviewers gain a standalone artifact at the cost of 1 extra file per Spec-Required issue.

### Option B: Bundle spec into `/implement` Phase 0 directly
- **Approach**: Skip a separate skill; have `/implement`'s first phase write SPEC inline as part of the implementation flow.
- **Pros**:
  - One fewer skill to learn.
- **Cons**:
  - Spec and code share the same context → loses the "review before code" property that gives RFCs their value.
  - Direct invocation `/spec ISSUE-NNN` (without intent to implement) is impossible.
- **Trade-off**: -1 skill, -1 entry point; -100% spec-isolated-review (the property we want most).

### Option C: External RFC tool (Notion/Google Doc/HackMD)
- **Approach**: Leave SPECs entirely outside the kit; link from issue body.
- **Pros**:
  - Zero kit changes.
- **Cons**:
  - Cannot validate trade-off quality or `Spec-Required` consistency programmatically.
  - Spec/code synchronization is lost at every renaming or external-tool migration.
- **Trade-off**: +0 kit LOC, -100% tool-enforced quality; +N external dependencies, -1 SSOT.

## Decision

**Chosen: Option A.**

The trade-off line "+1 skill, +2 fields, +0 risk to existing flows" wins because the only meaningful cost (surface area) is bounded and additive, while Option B sacrifices the property that motivated the work (independent spec review) and Option C abandons mechanical quality enforcement.

## Trade-offs Accepted

- New contributors must learn 1 additional skill and 2 issue fields.
- `validate_spec.py` enforces "measurable trade-off" lines, which can feel pedantic but is the slop-prevention guarantee.
- SPEC numbering aligns with issue numbering only when linked (`SPEC-NNN` ↔ `ISSUE-NNN`); ad-hoc SPECs use their own monotonic counter — two namespaces share the `SPEC-` prefix.

## Migration

1. Land the move: `templates/spec.md`, `skills/spec/SKILL.md(.tmpl)`, `scripts/validate_spec.py`, `templates/issues.md` field additions, `scripts/validate_issues.py` enforcement.
2. Existing issues default to `Spec-Required: false` (field absence treated as false) — no backfill needed.
3. Update root `issues.md` Conventions block to document the spec PR exception (2 PRs non-sprint / 1 bundled sprint).
4. No data migration required: SPEC files are new artifacts under `docs/specs/`.

## Rollback

Delete `skills/spec/`, `templates/spec.md`, `scripts/validate_spec.py`. Revert the `validate_issues.py` Spec-Required block (and the parser bug fix can stay — it's strictly correct). Revert the `templates/issues.md` field additions. Existing SPECs under `docs/specs/` become orphaned but harmless. Rollback time: < 5 minutes; no production state to migrate.

## Open Questions

- [ ] Should `/spec` ad-hoc invocation be allowed in sprint mode? — owner: design, by: first real sprint run that triggers auto_spec.
- [ ] Should `Spec-Required: true` issues auto-bump to a higher estimate cap (currently the work bundles spec + impl in 1.5d)? — owner: process, by: after 3 sprints of real usage.
