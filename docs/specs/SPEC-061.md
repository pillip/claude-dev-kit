# SPEC-061: Consolidate the scan-*/greenfield sibling agent pairs behind an evidence-mode flag

> Linked Issue: ISSUE-061
> Status: `accepted`
> Date: 2026-10-09
> Author: team-lead (sprint auto-spec, KIT_SPRINT_MODE=1)

## Problem

Five agent pairs are near-duplicates by design: `planner`/`scan-planner`, `qa-designer`/`scan-qa-designer`, `architect`/`scan-architect`, `data-modeler`/`scan-data-modeler`, `requirement-analyst`/`scan-analyst`. Each scan twin mirrors its greenfield sibling's output document "for downstream compatibility" (the twins say so verbatim — e.g., `agents/scan-analyst.md` "Keep the same section structure as the standard requirements template for downstream compatibility"), so every template change must be hand-mirrored across two files with zero enforcement. Evolution audit roadmap item 5 (docs/evolution_audit.md) directs consolidation; the risk to control is losing the scan twins' forensic posture (CONFIRMED/INFERRED tags, Evidence fields, audit-not-redesign stance), which must survive as an explicit mode.

## Context

- ISSUE-034 (done 2026-07-24) kept the scan family with the rationale "real 4-pass per-domain pipeline; merging loses separate context" — that rationale addressed collapsing the pipeline's *passes into one agent invocation*. This SPEC does NOT touch the pipeline shape: `/scan` keeps one Task invocation per domain, each with a fresh context. Twin-merging shares a prompt *file*, never a runtime context.
- ISSUE-034's kept-agent criteria (restated by SPEC-055 as predecessor): (a) separate-context self-grading guard, (b) differentiated methodology, (c) predictability guard. AC3 of ISSUE-061 requires any kept pair to cite one of these — not cost, not "felt safer".
- SPEC-055 / CONTRIBUTING.md Kept-Surface Criterion: the scan twins are B-bucket — their keepable value is the evidence *contract*; their reading-technique HOW steps are native capability (evolution_audit B-table row for scan-*).
- Callers today: `/scan` (skills/scan/SKILL.md.tmpl Steps 1–6) invokes the five twins by name; `/kickoff` (skills/kickoff/SKILL.md.tmpl Phase 2) invokes the five greenfield siblings by name. `planner` additionally serves `/issue` (Append Mode) and team-lead finding-to-issue — callers that must remain byte-identical in behavior (review lesson: scope new contract leniency to the new caller class only; ISSUE-057 regression precedent).
- ISSUE-057 just landed scripted checkpoints for kickoff/scan phases (`verify_checkpoint.py` scan: prd-digest/requirements/architecture/data-model/test-plan/issues). These verify *output documents*, not agent filenames — they stay green iff both modes' output templates are unchanged. Output-template changes are explicitly Scope Out.
- Effort tiers today (tests/test_agent_effort.py pins HEAVY ⊇ {planner, architect}, LIGHT ⊇ {scan-analyst, scan-architect, scan-data-modeler, scan-qa-designer, requirement-analyst}): planner xhigh / scan-planner medium; qa-designer high / scan-qa-designer medium; architect xhigh / scan-architect medium; data-modeler xhigh / scan-data-modeler medium; requirement-analyst medium / scan-analyst low. A merged agent has ONE frontmatter effort — the Task tool has no per-invocation effort override — so scan-mode invocations inherit the greenfield tier.
- Prompt-length budget, measured on current main (bytes):

  | Pair | Greenfield | Scan twin | Projected merged* | Headroom reference |
  |------|-----------|-----------|-------------------|--------------------|
  | planner / scan-planner | 10,286 | 6,204 | ~14,600 | team-lead 17,021; figma-converter 24,142 |
  | qa-designer / scan-qa-designer | 9,771 | 4,216 | ~13,000 | — |
  | architect / scan-architect | 5,769 | 4,291 | ~9,100 | — |
  | data-modeler / scan-data-modeler | 5,751 | 4,158 | ~8,900 | — |
  | requirement-analyst / scan-analyst | 3,644 | 4,162 | ~6,800 | — |
  | **Total** | 35,221 | 23,031 | **~52,400 (5 files)** | vs 58,252 (10 files) |

  *merged = greenfield + evidence-mode section carrying the twin's output template verbatim plus its evidence rules, minus duplicated frontmatter/role/shared quality criteria (~25–35% of twin bytes dedupe). Every merged agent stays below the two largest existing agents — no budget ceiling is broken.

## Options

> Per ISSUE-061 Scope-In, the decision is argued **per pair** below (inside the Decision section), not blanket-merged. The options define the decision *rule* applied to each pair.

### Option A: Merge every pair whose keep-case implicates no ISSUE-034 criterion (evidence-mode section + explicit sentinel)

- **Approach**: For each merged pair the greenfield file gains one self-contained `## Evidence Mode (scan invocations only)` section carrying the scan twin's output template verbatim, its CONFIRMED/INFERRED tagging rules, Evidence-field contract, and audit-not-redesign stance. Activation ONLY when the invoking prompt contains the literal line `Mode: evidence`; absence (or any other value) means greenfield behavior byte-identical to today, and the agent must never infer the mode from context (predictability guard — e.g., receiving scan_context does NOT activate evidence mode). `/scan` Steps 1–6 rewire to the merged agent names and pass the sentinel; `/kickoff` passes `Mode: greenfield` explicitly. Twin files are deleted; tests/README synced.
- **Pros**:
  - −5 agent files (roster 32→27) and −~5,900 prompt bytes overall; the dual-file template-mirroring liability (10 hand-aligned templates, zero enforcement) drops to 0.
  - The evidence contract becomes *more* testable: one gated section per agent, pinned by structure assertions against current-main golden fixtures for both modes.
  - Existing non-scan callers of planner/qa-designer/etc. (kickoff, /issue append, team-lead finding-to-issue) are untouched — new leniency scoped to the one new caller class (/scan), per the ISSUE-057 review lesson.
- **Cons**:
  - Scan-mode invocations inherit the greenfield effort tier: architect/data-modeler/planner domains run xhigh instead of medium during `/scan` (3 of ≤6 Task invocations in a one-shot onboarding flow; data-modeler conditional on DB detection).
  - Single-invocation mode-blending becomes possible in principle (a merged agent leaking evidence artifacts into greenfield output) — mitigated by the explicit-sentinel activation rule plus a leak test (greenfield portion of each merged agent must stay free of evidence-mode artifacts).
- **Trade-off**: −5 agent files, −10% roster prompt bytes (58,252→~52,400), +2 effort tiers on ≤3 scan-mode invocations per one-shot `/scan` run, +1 sentinel contract line per calling skill.

### Option B: Keep all ten files (status quo, re-litigating audit roadmap 5)

- **Approach**: Leave both rosters intact; optionally add a lint that diffs section structures between twins to contain drift.
- **Pros**:
  - Zero churn; effort tiers stay tuned per invocation (scan extraction stays medium/low).
- **Cons**:
  - The 10-template hand-mirroring liability persists; "downstream compatibility" remains an unenforced comment in five files.
  - Contradicts the accepted evolution audit roadmap (item 5) without any ISSUE-034 criterion to stand on — none of the five keep-cases implicates separate-context, self-grading, or differentiated-methodology (analysis per pair in Decision).
- **Trade-off**: 0 churn, +10 section-identical templates to keep aligned by hand indefinitely, +5 roster files vs Option A.

### Option C: Partial merge — merge only the 1-tier effort-gap pairs (requirement-analyst, qa-designer), keep the three xhigh-designer pairs split

- **Approach**: Merge requirement-analyst/scan-analyst (medium vs low) and qa-designer/scan-qa-designer (high vs medium); keep planner, architect, data-modeler twins to preserve medium-effort scan extraction.
- **Pros**:
  - Avoids the xhigh-on-extraction cost entirely.
- **Cons**:
  - The three keep-rationales cite *effort cost* — not an ISSUE-034 criterion — which AC3 explicitly rejects ("not 'felt safer'"); the cost avoided is confined to a one-shot onboarding flow.
  - Keeps 6 of the 10 hand-mirrored templates and a split-brain roster (two conventions for the same relationship).
- **Trade-off**: −2 agent files only, −2 effort tiers saved on ≤3 one-shot invocations, +6 hand-aligned templates retained, +2 keep-rationales that fail the AC3 criterion test.

## Decision

**Chosen: Option A** — merge all five pairs. The deciding line is Option A's trade-off: the only recurring cost (+2 effort tiers) applies to at most 3 Task invocations of a one-shot onboarding flow, while Options B/C retain a *permanent* hand-mirroring liability (10 and 6 templates respectively) and — decisively — every keep-case fails the AC3 test: no ISSUE-034 criterion is implicated by any pair, so a keep could only be justified by cost ("felt cheaper"), which the issue's AC rejects as a rationale.

Per-pair verdicts (each argued against the ISSUE-034 criteria — separate-context self-grading guard / differentiated methodology / predictability guard):

1. **requirement-analyst + scan-analyst → MERGE.** Same output doc (`docs/requirements.md`), same section skeleton; the twin's deltas (Confidence/Source columns, Coverage Summary, tagging rules) are a textbook self-contained evidence block. Separate context: not implicated — /kickoff and /scan invoke it as separate Tasks; neither mode grades the other's output. Methodology: differs only by input source (PRD vs code/tests) + the evidence contract itself, which survives verbatim in the gated section. Merged effort `medium` (stays LIGHT-compliant; scan runs gain one tier over `low`).
2. **qa-designer + scan-qa-designer → MERGE.** Largest template divergence of the five (Current State Assessment / Existing Test Inventory / Coverage Gaps / Automation Assessment vs E2E Strategy / Backend Robustness / Verify Gates Configuration) — but the divergence IS the audit posture, i.e., the evidence contract; both templates survive verbatim, one gated. Invariant preserved: evidence mode does NOT emit the machine-parsed `## Verify Gates Configuration` block (scan output never carried it; `verify_gates.py` falls back to defaults when absent — output-template change is Scope Out). No ISSUE-034 criterion implicated: the scan mode audits *the codebase's tests*, not qa-designer's own prior test plan.
3. **architect + scan-architect → MERGE.** The stance inversion (design-to-be vs document-as-is) is exactly the "audit-not-redesign stance" ISSUE-061 names as part of the evidence contract; the twin's forensic workflow is short and self-contained, and its reading-technique steps are native capability (evolution_audit B-row). Differentiated methodology is not a keep-reason here because the differentiated part *is* the gated mode and survives verbatim. Cost recorded: scan-mode runs inherit xhigh (was medium) — one invocation per /scan.
4. **data-modeler + scan-data-modeler → MERGE.** Same shape as pair 3 plus the conditional-invocation rule (only when DB detected), which stays in `/scan` Step 4 and is restated inside the evidence-mode section. Rarest invocation of the five (conditional), so the xhigh-inheritance cost is the smallest. No ISSUE-034 criterion implicated.
5. **planner + scan-planner → MERGE.** Riskiest by size (merged ~14.6KB — still under team-lead's 17KB) and by caller multiplicity (kickoff, /issue append mode, team-lead finding-to-issue, sprint flows). Precisely because of that multiplicity, the sentinel rule is load-bearing: only `/scan` passes `Mode: evidence`; every existing caller keeps today's byte-identical greenfield behavior with no prompt change required. The twin's distinctive content (Evidence field, Issue Sources & Types mapping, improvement-not-implementation stance, risk-impact ordering) is self-contained and survives verbatim. Separate context: not implicated — scan-planner never grades planner output; it derives issues from scan documents.

## Trade-offs Accepted

- `/scan` architect/data-modeler/planner passes run at the greenfield effort tier (xhigh vs the twins' medium): more reasoning tokens for extraction work, bounded to a one-shot onboarding flow (≤3 affected invocations per run; data-modeler conditional).
- The merged agent files are longer than any single predecessor (max ~14.6KB vs 10.3KB) — accepted against the headroom set by team-lead (17KB) and figma-converter (24.1KB).
- A single-file mode gate replaces physical file separation as the leak barrier; we rely on the explicit-sentinel contract plus structure tests (greenfield leak check + evidence-contract presence check) instead of filesystem isolation.
- `subagent_type` strings `scan-analyst`/`scan-architect`/`scan-data-modeler`/`scan-qa-designer`/`scan-planner` disappear from the roster; any external automation invoking those names directly (none known in-repo beyond /scan) must switch to the merged names + sentinel.

## Migration

Pairs are independent; each follows the same mechanical sequence (all five land in this one PR, but each pair's edits are revertible in isolation):

1. Graft `## Evidence Mode (scan invocations only)` into the greenfield agent: activation sentinel rule first (literal line `Mode: evidence`; never inferred; absence = greenfield, ignore the section entirely), then the twin's input swap (scan_context et al.), evidence rules (CONFIRMED/INFERRED, Evidence/Source fields), audit-not-redesign stance, and the twin's Output Structure verbatim where it differs from greenfield.
2. Rewire `skills/scan/SKILL.md.tmpl` Steps 1–6: invoke the merged agent name with `Mode: evidence` in the Task prompt; update the Subagent Invocation Pattern section accordingly. Add explicit `Mode: greenfield` to `skills/kickoff/SKILL.md.tmpl` Phase 2 invocation pattern. Regenerate both SKILL.md via `python3 scripts/gen_skills.py`.
3. Delete the twin file (`git rm agents/scan-<domain>.md`).
4. Sync derived surfaces: `tests/test_agent_effort.py` LIGHT set (drop retired names), `tests/test_scan_skill.py` (merged-name + sentinel assertions replace twin-file-exists assertions), README scan-flow lines and agents table (parity enforced by tests/test_readme_consistency.py), `scripts/verify_checkpoint.py` retry-hint strings naming scan twins.
5. New golden-structure tests pin both modes per domain against current-main fixtures (section-heading lists captured from the twin and sibling templates; template-structure assertions, not byte equality), plus the greenfield leak check and the sentinel/never-infer contract check.

No runtime data, schema, or output-document migration: both modes' output templates are unchanged by construction (Scope Out), so ISSUE-057's kickoff/scan checkpoints remain green without modification.

## Rollback

Per-pair revert: restore the twin file from git, revert that pair's hunk in `skills/scan/SKILL.md.tmpl` (+ regenerate), restore its LIGHT-set/test/README rows — no cross-pair coupling. Trigger signal: a /scan or /kickoff run producing mode-blended output (evidence tags in greenfield docs, or missing CONFIRMED/INFERRED coverage in scan docs) that the structure tests failed to catch, or a scan-quality regression attributable to effort-tier inheritance. Rollback time: < 0.5d per pair (file restore + template hunk revert + test sync).

## Open Questions

- [ ] Should agent effort become per-invocation overridable (calling skill requests a tier), removing the xhigh-inheritance cost class entirely? — owner: pillip, by: next evolution audit.
- [ ] Should the `Mode:` sentinel become a kit-wide convention for other mode-gated agents (e.g., design-extend flows)? — owner: pillip, by: first follow-up that needs a second mode-gated agent.
