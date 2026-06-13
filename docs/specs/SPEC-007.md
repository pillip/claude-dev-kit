# SPEC-007: /implement spec gate with mode-aware decision table

> Linked Issue: ISSUE-007
> Status: `accepted`
> Date: 2026-06-13
> Author: claude-dev-kit

## Problem

After SPEC-006 lands, `/spec` exists as a skill but nothing prevents `/implement` from coding without a SPEC even when the issue is flagged `Spec-Required: true`. The gate logic must also distinguish sprint (automated, no human in the loop) from non-sprint (interactive, human decision welcome), and surface keyword-based recommendations without blocking on heuristics.

## Context

- SPEC-006 added `Spec-Required` and `Spec:` issue metadata; `validate_issues.py` enforces them only at `done`/`waiting`/`doing` — not at `/implement` entry.
- `/implement` is `disable-model-invocation: true` (sprint-callable; not auto-discoverable).
- `KIT_SPRINT_MODE=1` is the canonical signal that `/sprint` is the caller.
- Signal keywords (`api`, `schema`, `migration`, `breaking`, `protocol`, `데이터모델`, new-dependency, estimate-at-cap) are heuristic — high false-positive rate would break sprint automation if they auto-blocked.

## Options

### Option A: `Phase 0` gate inside `/implement` SKILL.md.tmpl + standalone `spec_gate.py` script
- **Approach**: A new Phase 0 in `/implement` calls `scripts/spec_gate.py ISSUE-NNN`, which returns a JSON decision (`proceed | auto_spec | hold | bypassed`). The skill branches: `auto_spec` invokes `/spec` inline; `hold` raises an `AskUserQuestion` 3-way prompt; `proceed` continues; `bypassed` logs a telemetry note.
- **Pros**:
  - Decision logic is pure Python and unit-testable (one test per decision-table row).
  - Skill becomes a thin orchestrator over a deterministic script.
  - Sprint mode never prompts; non-sprint mode always gets explicit user choice.
- **Cons**:
  - Two artifacts to keep in sync (script + skill).
- **Trade-off**: +1 script (~180 LOC), +1 skill phase block (~50 lines markdown), +16 unit tests; +0 changes to existing skills (additive); coverage of all 9 decision-table rows.

### Option B: Pre-commit hook enforcement
- **Approach**: Move enforcement to a `.githooks/pre-commit` hook that refuses commits on a `Spec-Required: true` branch without a matching SPEC file.
- **Pros**:
  - Mode-agnostic — same enforcement regardless of how implementation started.
- **Cons**:
  - Fires after work is done — defeats the purpose of "review the decision before code".
  - No path for sprint mode to auto-fix (hooks block, they don't recover).
  - Cannot scan keyword signals to surface recommendations.
- **Trade-off**: -1 script vs A, +1 hook; -100% pre-coding review opportunity (the property that matters most); +0 sprint automation compatibility.

### Option C: Sprint orchestrator handles it before invoking `/implement`
- **Approach**: Push the gate up into `/sprint`; `/implement` stays unchanged. Non-sprint users invoke `/spec` manually.
- **Pros**:
  - Cleaner separation — `/implement` stays focused on one thing.
- **Cons**:
  - Non-sprint mode has zero enforcement (relies on user discipline).
  - Inconsistent behavior between sprint and direct invocation paths.
- **Trade-off**: +0 to `/implement`, +1 phase in `/sprint`; -1 enforcement surface for non-sprint mode (= 100% of ad-hoc users have no gate).

## Decision

**Chosen: Option A.**

The trade-off "+1 script, +1 phase block, 16 tests covering every decision-table row" is bounded and verifiable; Option B fires too late to provide the value the gate exists for; Option C abandons non-sprint enforcement entirely. The pure-Python decision logic also gives us a clean telemetry surface for the eventual ISSUE-001 (run telemetry MVP).

## Trade-offs Accepted

- `/implement` gains a Phase 0 block — the skill is no longer trivially short.
- `--skip-spec-gate` exists as an escape hatch; users can bypass at the cost of a telemetry log.
- Sprint mode bundles SPEC + impl commits in a single PR (vs non-sprint's 2 PRs), an exception to "1 Issue = 1 PR" that lives in the `Conventions` block.
- The 9-row decision table grows the cognitive surface for first-time users; mitigated by JSON output that makes the gate's reasoning visible.

## Migration

1. Land `scripts/spec_gate.py` and 16 unit tests covering each decision-table row + CLI behavior.
2. Land the Phase 0 block in `skills/implement/SKILL.md.tmpl`; regenerate `SKILL.md` via `gen_skills.py`.
3. Existing issues default to `Spec-Required: false` → gate returns `proceed` silently. No backfill required.
4. Document the `--skip-spec-gate` escape hatch in the implement skill so contributors know it exists.

## Rollback

Delete `scripts/spec_gate.py`, revert the Phase 0 block in `skills/implement/SKILL.md.tmpl`, regenerate `SKILL.md`. SPEC-006's `/spec` skill keeps working standalone (`/spec ISSUE-NNN` still callable). No data migration. Rollback time: < 3 minutes.

## Open Questions

- [ ] Should `auto_spec` runs in sprint mode bundle or split commits? Currently bundled — re-evaluate after 3 real sprint runs. — owner: process, by: 3 sprints from first use.
- [ ] Should the signal scanner emit per-signal recommendations to `validate_issues.py` so backlog issues get pre-flagged? — owner: design, by: ISSUE-001 telemetry landing.
- [ ] Should `--skip-spec-gate` require a written reason (forced telemetry tag)? — owner: process, by: first time the bypass is used "in anger".
