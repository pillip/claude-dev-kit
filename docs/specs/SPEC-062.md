# SPEC-062: Dissolve the five A-bucket conversational agents into their skill contracts

> Linked Issue: ISSUE-062
> Status: `draft`
> Date: 2026-10-09
> Author: pillip + Claude

## Problem

docs/evolution_audit.md (roadmap item 6, evidence snapshot for SPEC-055) classifies five roster agents — brainstormer, business-analyst, devops, documenter, copywriter — as A-bucket: their remaining prose teaches the model HOW to converse, write, or follow best practices, which is native capability, while every load-bearing invariant they state already lives (or trivially fits) in the calling skill's contract. Each file costs frontmatter/effort/test maintenance and, for the two research agents, keeps alive a Task-invocation bypass around the skill-level delegation gate that test_research_fabrication_guard.py exists to patrol. ISSUE-034's precedent warns that blanket audits over-count dissolutions, so each agent needs its own caller-level analysis and verdict.

## Context

- **SPEC-055 kept-surface criterion** (CONTRIBUTING.md "Kept-Surface Criterion"): conversation-shaping prompts are A-bucket; only invariants (B) and deterministic checks (C) survive model improvement. This SPEC applies that criterion per agent.
- **ISSUE-034 prior verdict**: brainstormer/business-analyst were explicitly KEPT as "029 degraded-path research agents, freshly guard-tested". That keep must be re-litigated, not silently overridden (see Decision Table).
- **SPEC-018 landing changed the premise**: `skills/brainstorm/SKILL.md.tmpl:20-24` and `skills/bizanalysis/SKILL.md.tmpl:14-33` now own the entire research path — `has_skill.py` probe, primary `/deep-research` + synthesizer + synthesizer-auditor, degraded `capture_source.py` + `validate_research_claim.py` + research-auditor, the no-data literal, and the `range: <low–high> [single-source]` rule. The agents' own text concedes the inversion: `agents/business-analyst.md:15` — "This agent receives the rendered sections as INPUT"; `agents/brainstormer.md:24` — same. Repo-wide grep (2026-10-09) finds **zero callers** that Task-dispatch either agent: `/kickoff` runs 6 other subagents; `/brainstorm` and `/bizanalysis` run their flows inline.
- **Guard tests pin both layers**: tests/test_research_fabrication_guard.py checks WebFetch absence in the two skill tmpls AND the two agent files. The agent-file checks exist solely because "the skill-level delegation gate is bypassable via direct Task invocation of the agent" (SPEC-018 Migration step 5). Deleting the agents removes the bypass vector itself — strictly stronger than guarding it.
- **devops**: sole dispatch route is the `/sprint` Agent Selection table (`skills/sprint/SKILL.md.tmpl:155`). `skills/devops/SKILL.md.tmpl:73-80` Guidelines already carry the agent's checkable invariants (pin versions, no hardcoded secrets, least privilege, multi-stage builds, caching, health checks, local validation) and `verify_checkpoint.py` enforces worktree/validate/push deterministically. The table already has a no-agent idiom: "(run the diagnose skill)" / "(run the refactor skill)" / "(run the migrate skill)".
- **documenter**: sole caller is `/ship` step 3.5 (`skills/ship/SKILL.md.tmpl:19-24`) — a context-isolation use (docs side-quest kept out of the ship context), not an expertise use. Per ISSUE-062 scope, separate-context needs survive dissolution as an inline-contract subagent call.
- **copywriter**: sole callers are the three uiux skills' Phase 4.5 (`skills/uiux/SKILL.md.tmpl:150`, `skills/mobile-uiux/SKILL.md.tmpl:169`, `skills/desktop-uiux/SKILL.md.tmpl:180`). The deterministic `--phase system` checkpoint already verifies `docs/copy_guide.md` exists; the skills already enforce banned-copy-tells inline. The agent's surviving value is the per-screen × per-state inventory contract (WHAT), not the copywriting craft (HOW, native).
- **Roster sync is test-enforced**: tests/test_readme_consistency.py requires the README agents table to match `agents/*.md` bidirectionally; tests/test_integration.py parametrizes the five by name; tests/test_agent_effort.py iterates the glob (deletion-safe) but lists documenter in its LIGHT set.
- **Parallel work**: ISSUE-059 (boilerplate deflation across agents/) and ISSUE-061 (scan-sibling consolidation) edit overlapping roster tests in sibling worktrees. This SPEC's changes are authored against main@776ac73; ship-time rebase resolves collisions.

## Decision Table (per-agent verdicts — AC #2)

| Agent | Verdict | Deciding criterion (ISSUE-034 / SPEC-055) | Where the invariants land |
|---|---|---|---|
| brainstormer | **Dissolve** | Zero callers since SPEC-018 moved routing into the skill; conversational technique (Socratic cadence, 1–2 questions) is native. ISSUE-034's keep premise — "degraded-path research agent" — no longer holds: the skill owns both paths and the agent only receives rendered output. The file's only live function is an ungated Task entry that bypasses the skill's probe/audit wiring. | Already present in `skills/brainstorm/SKILL.md.tmpl` (research-path routing :20-24, no-training-data NEVER :50, no-data literal :24, auditor gates :22-23). No absorption needed — deletion is pure. |
| business-analyst | **Dissolve** | Same zero-caller + premise-inversion argument. Its two signature invariants are already skill/script contract: no-data literal (`bizanalysis` tmpl :25,:31 — test-pinned by `test_bizanalysis_template_references_no_data_literal`), single-source range rendering (tmpl :29), 5-section canonical order (tmpl :45 + enforced mechanically by `synthesize_from_deep_research.py`). | Already in `skills/bizanalysis/SKILL.md.tmpl`; repoint the section-order comment in `scripts/synthesize_from_deep_research.py:60` from the agent file to the skill. |
| devops | **Dissolve** | Generic best-practice checklist is native knowledge (A-bucket); every checkable invariant is duplicated in the `/devops` skill Guidelines, which also has what the agent lacks — deterministic checkpoints. | `skills/devops/SKILL.md.tmpl` Guidelines (already there), plus absorb the one missing line: basic PR-check CI pipelines stay under ~10 minutes (cache/parallelize). Rewire `skills/sprint/SKILL.md.tmpl:155` to "(run the devops skill)". |
| documenter | **Dissolve** (separate-context call survives) | Writing-for-the-reader craft is native; the ship call site is context isolation, not expertise — so the Task call stays, backed by an inline contract instead of a roster file. | `skills/ship/SKILL.md.tmpl` step 3.5 inline contract: (1) every command/path the docs reference must exist in the codebase, (2) scope limited to docs affected by the PR diff — no unrelated restructuring, (3) "no updates needed" is a valid early exit. |
| copywriter | **Dissolve** (separate-context call survives) | Copywriting is native; the kept value is the inventory contract (WHAT). The three uiux call sites keep their Task call with the contract inlined. | uiux/mobile-uiux/desktop-uiux Phase 4.5 inline contract: per-screen coverage cross-checked against wireframes; per-state coverage (empty/loading/error/success + confirmations/toasts); voice derived from design_philosophy; glossary one-concept-one-word; error copy = [what happened] + [what to do]; a11y label coverage (mobile/desktop 16-a already mandates it). |

All five verdicts are **dissolve** — but each on its own caller-level evidence, not the blanket audit: the two research agents fall because their keep-premise inverted (zero callers, skills own the paths), devops because its sole dispatch route has a proven no-agent idiom, and documenter/copywriter because their only kept property (separate context) does not require a roster file. No agent among the five carries the separate-context *judgment* guarantee that saved the auditor family in ISSUE-034.

## Options

### Option A: Dissolve all five; absorb invariants as skill contract lines; keep inline-contract subagent calls where the call site was context isolation
- **Approach**: Per the Decision Table. Rewire callers first (sprint table, ship 3.5, uiux×3 Phase 4.5, synthesizer comment), absorb the missing invariant lines into the skill `.tmpl`s, delete the five agent files last, one agent per commit. Sync README table rows, test_integration/test_agent_effort/test_research_fabrication_guard pins, and regenerate SKILL.md via `gen_skills.py`. Skill-level invariant tests assert the absorbed contract lines.
- **Pros**:
  - Removes the Task-bypass vector around the research delegation gate instead of guarding it (two agent-file guard tests become structurally unnecessary).
  - Ends the roster diet item with every surviving entry holding a stated bucket (evolution_audit classification + this table for the five).
- **Cons**:
  - The uiux×3 Phase 4.5 inline contract is temporarily triplicated across the three tmpls until ISSUE-060/fragments-SSOT work lands.
- **Trade-off**: -5 roster files (-382 prompt lines), +~35 absorbed contract lines across 5 skill tmpls, ~5 test files updated, -1 bypass vector, 0 runtime capability lost; +~25 lines of temporary triplication in the uiux tmpls.

### Option B: Dissolve devops/documenter/copywriter only; keep brainstormer/business-analyst per ISSUE-034
- **Approach**: Honor the prior keep verdict literally. Dissolve the three uncontested agents; leave the two research agents as direct-invocation entry points for users who Task-dispatch them outside the skills.
- **Pros**:
  - No re-litigation of a recorded ISSUE-034 decision; zero risk of losing an unnoticed research-agent caller.
- **Cons**:
  - Keeps two zero-caller files whose own text says they receive rendered sections as input — maintenance without function — and keeps the Task-bypass vector that forces the two agent-file guard tests to exist forever.
  - Leaves roadmap item 6 half-done; the remaining two still depreciate (A-bucket) with no path out.
- **Trade-off**: -3 files (-240 lines), but +142 permanently maintained zero-caller lines, +2 permanent guard tests, +1 permanent bypass vector.

### Option C: Keep all five; shrink in place (strip Self-Review/confidence boilerplate only)
- **Approach**: ISSUE-059-style deflation without dissolution: delete the confidence-rating blocks and craft prose, keep the five files as thin invariant stubs.
- **Pros**:
  - Zero caller rewiring; zero test-pin churn.
- **Cons**:
  - The stubs would duplicate invariants the skills already state — two sources of truth for the same contract lines, drifting independently (the exact failure the record-tests lesson warns about for derived facts).
  - The roster keeps 5 A-bucket entries, so the SPEC-055 criterion stays unapplied to the one surface the audit flagged for it.
- **Trade-off**: -~120 boilerplate lines, 0 rewiring, but +5 duplicated contract surfaces and 0 progress on roadmap item 6.

## Decision

**Chosen: Option A**

The deciding line is Option B's "+142 permanently maintained zero-caller lines, +2 permanent guard tests, +1 permanent bypass vector": the only argument for keeping brainstormer/business-analyst is deference to ISSUE-034, and that verdict's stated premise ("degraded-path research agents") was inverted by SPEC-018's landing — the skills own both research paths and are themselves guard-tested, so the keep now purchases only a bypass risk. Option C's duplicated contract surfaces violate the single-source rule the kit enforces everywhere else. Option A's sole real cost (uiux triplication of the copy contract) is bounded and already on the fragments-SSOT roadmap.

## Trade-offs Accepted

- Direct `claude-dev-kit:brainstormer` / `business-analyst` / `copywriter` / `documenter` / `devops` Task invocation stops working. Accepted: for the research pair this is the point (the skills are the gated entry); for the other three the skills/`/ship`/uiux flows are the supported entries.
- The copy-inventory contract is triplicated across three uiux tmpls until a fragments.py SSOT extraction (ISSUE-060 territory) lands.
- test_research_fabrication_guard.py loses its two agent-file checks; the skill-template checks and the structural absence of the files carry the guarantee.
- One historical comment surface (`synthesize_from_deep_research.py:60`) changes its cited authority from agent file to skill — CHANGELOG/issues.md historical mentions stay as-is (historical records are exempt per the TC-043b convention).
- The issues.md header's "33 agents / 28 skills" line is a historical-baseline description, already stale before this SPEC; per the record-tests lesson (derived facts are generated or not written) it is not hand-updated here — flagged in Open Questions.

## Migration

Order: rewire callers first, delete files last, one agent per commit (each commit leaves the suite green and is independently revertable).

1. **Tests first (TDD red)**: add `tests/test_agent_dissolution.py` asserting per agent: (a) `agents/<name>.md` does not exist, (b) the absorbed/retained contract lines are present in the calling skill tmpl + generated SKILL.md (ship: command-existence + "no updates needed" early exit; uiux×3: per-screen × per-state inventory lines; devops skill: ≤10-min PR-check line; sprint table: "(run the devops skill)" and no `| devops |` agent dispatch), (c) brainstorm/bizanalysis tmpls still carry the research-path invariants (no-data literal, single-source range, probe) — these fail red against main.
2. **brainstormer commit**: delete `agents/brainstormer.md`; remove its README table row; drop its entries from test_integration param lists and its agent-file test; drop `test_no_webfetch_in_brainstormer_agent` + the agent path from SCOPED_FILES in test_research_fabrication_guard.py.
3. **business-analyst commit**: same mechanics; additionally repoint `scripts/synthesize_from_deep_research.py:60` comment to `skills/bizanalysis/SKILL.md.tmpl`.
4. **devops commit**: rewire `skills/sprint/SKILL.md.tmpl` (table row → "(run the devops skill)"; "How to determine" sentence → the devops skill); absorb the ≤10-min PR-check guideline into `skills/devops/SKILL.md.tmpl`; delete `agents/devops.md`; README row; test pins.
5. **documenter commit**: rewrite `skills/ship/SKILL.md.tmpl` step 3.5 as an inline-contract subagent call (keep Task); delete `agents/documenter.md`; README row; repurpose `test_ship_skill_references_documenter` to assert the inline contract; remove documenter from test_agent_effort LIGHT set and test_integration lists.
6. **copywriter commit**: rewrite Phase 4.5 in the three uiux tmpls as inline-contract subagent calls; delete `agents/copywriter.md`; README row; test pins (incl. test_integration Test 21 param).
7. Each commit that touches a `.tmpl` runs `python3 scripts/gen_skills.py` and commits the regenerated SKILL.md alongside (test_gen_skills `--dry-run` gate).
8. Full suite green via `uv run --extra dev pytest -q`; update docs/test_plan.md TC entries for the new invariant tests.

## Rollback

`git revert` of any single agent's commit restores that agent file, its README row, its test pins, and its caller wiring independently (rewire+delete share the commit, so the revert is self-consistent). Trigger: a discovered external caller (e.g., a user workflow Task-dispatching one of the five directly) that cannot be served by the calling skill. Rollback time: <10 minutes per agent.

## Open Questions

- [ ] Should the uiux×3 copy-inventory inline contract move into `scripts/fragments.py` as SSOT when ISSUE-060 shrinks the uiux developer agents? — owner: pillip, by: ISSUE-060 review.
- [ ] The issues.md header line "33 agents / 28 skills primitive set" is stale (pre-dates ISSUE-034); should planner reword it to drop the hand-maintained counts per the record-tests lesson? — owner: planner, by: next registry grooming pass.
- [ ] Do the remaining A-bucket agents (a11y-auditor, test-generator, architect, uiux developer trio) get their own dissolution SPECs, or does the ISSUE-060/061 line absorb them? — owner: pillip, by: backlog grooming after this PR ships.
