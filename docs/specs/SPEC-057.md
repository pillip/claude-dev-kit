# SPEC-057: Script checkpoints for the five zero-checkpoint skills

> Linked Issue: ISSUE-057
> Status: `accepted`
> Date: 2026-10-09
> Author: pillip + Claude

## Problem

`checkpoint.sh` (→ `verify_checkpoint.py`) is invoked by only 8 of 23 skills. The five skills with the longest prose — kickoff, scan, uiux, mobile-uiux, desktop-uiux — have zero script checkpoints: every one of their "CHECKPOINT — MANDATORY" blocks is a model self-assertion, so the skills with the longest free-generation runs are exactly the ones where nothing outside the model verifies that phase artifacts exist (docs/evolution_audit.md finding 2). A kickoff that silently skipped the data-modeler, or a uiux run whose design_philosophy.md lacks a Signature Move, passes its own "checkpoint" because the generator grades itself.

## Context

- `verify_checkpoint.py` (~1,870 lines) already encodes per-skill/phase expectations for 8 skills with a `VERIFIERS` registry and an `ADVISORY_PHASES` tier set (ISSUE-031 two-tier convention), both pinned by `tests/test_verify_checkpoint_contract.py`. Dormant `uiux`/`mobile-uiux` verifiers (`context`, `philosophy`, `system`) exist in the registry but no SKILL.md ever invokes them.
- The engine's CLI requires `--issue`, but kickoff/scan/uiux runs have no issue ID — their verifiers ignore it.
- Two phases are conditional by contract: scan's data-model step runs only when database usage is detected, and the uiux-family extend mode (SPEC-054) may legitimately write `docs/design_system*.extracted.md` ("write alongside") instead of the canonical system doc.
- One asserted artifact is in-memory by design: scan's Phase 1 `scan_context` is explicitly never written to disk ("do NOT write it to disk — it is an internal intermediate artifact"), so no script can verify it without changing the phase contract — which ISSUE-057 scopes out.
- ISSUE-056 (design sweeps: literal_quote verbatim render, Signature Move per-screen, AI Tell, contrast) is unmerged; wiring sweeps into uiux phases follows in ISSUE-060. This SPEC must only script the assertions the prose checkpoints already make.
- SKILL.md files are generated: edits go to `SKILL.md.tmpl` + `scripts/fragments.py` (the Phase 2 philosophy checkpoint is a shared fragment), regenerated via `scripts/gen_skills.py`.

## Options

### Option A: Presence-level verifiers in the existing engine, blocking tier, honest conditionals
- **Approach**: Extend `verify_checkpoint.py` with new phases — kickoff (`prd-digest`, `requirements`, `ux-architecture`, `data-model`, `planning`), scan (`prd-digest`, `requirements`, `architecture`, `data-model`, `test-plan`, `issues`), desktop-uiux (`context`, `philosophy`, `system`) — all artifact-existence + required-section/term presence, failure messages naming the missing file/section. Rewrite the dormant `philosophy` verifier to mirror the current fragment checkpoint (Signature Move + Reference Anchors-or-skip-line + `literal_quote:` field presence) instead of the stale "Decision Matrix" check. `system` verifiers accept the extend-mode `*.extracted.md` alternate. Scan `data-model` skips (exit 0 with a SKIP line) when no DB indicators are found in manifests/migration dirs, and fails naming `docs/data_model.md` when DB usage is detected but the doc is missing. Make `--issue` optional (these skills have none). All new phases are blocking (artifact presence); cross-document consistency assertions stay as model-side prose. Scan's in-memory `scan_context` block is demoted from a CHECKPOINT block to plain step instructions — it keeps the retry rule but stops claiming to be a checkpoint it cannot be.
- **Pros**:
  - Reuses the proven registry + contract-test machinery; every new phase lands under the existing tier partition guard.
  - Honest conditional handling: skip is a stated outcome, not a silent pass; the unscriptable assertion is visibly not a checkpoint rather than a fake one.
- **Cons**:
  - Presence/term checks cannot catch a section that exists but is hollow — depth stays model-side until ISSUE-060.
- **Trade-off**: +14 scripted phases across 5 skills (8 → 13 skills covered), ~0 new judgment encoded; 1 prose block demoted; depth checks deferred (−4 sweep classes vs Option C).

### Option B: Stub every block — register always-pass verifiers for unscriptable assertions
- **Approach**: Same as A, but also register a `scan/context` phase whose verifier always returns PASS ("in-memory artifact — model-verified") so that literally every existing CHECKPOINT block, including the unscriptable one, carries a `checkpoint.sh` invocation.
- **Pros**:
  - Satisfies the "every CHECKPOINT block has an invocation" AC with zero prose restructuring.
- **Cons**:
  - A checkpoint that cannot fail is checkpoint theater — it converts the audit's finding ("self-assertion dressed as a gate") into a worse form (script-assertion that asserts nothing) and pollutes the contract test's blocking set with a phase that can never block.
- **Trade-off**: +1 phase over A, but that phase has a 0% possible failure rate — the engine's blocking tier gains its first unfalsifiable gate.

### Option C: Deep validators now — section counts, cue counts, cross-document checks
- **Approach**: Script not just presence but depth: 2–3 Reference-Anchor cue counting, numeric Signature-Move pattern matching, wireframes↔design_system component cross-reference, kickoff cross-document validation (Phase 4 step 6.5) as advisory phases.
- **Pros**:
  - Catches hollow sections immediately; closes more of the audit's finding 3 in one PR.
- **Cons**:
  - Strengthens the phases beyond their current prose assertions (explicitly out of ISSUE-057's scope) and collides head-on with ISSUE-056's sweep validators landing in parallel — two unmerged branches encoding overlapping judgment.
- **Trade-off**: ~4 additional deep checks now, but +1 scope violation, a likely merge conflict with ISSUE-056, and cross-doc checks are judgment-shaped — est. false-positive rate high enough to need an advisory tier escape hatch from day one.

## Decision

**Chosen: Option A**

The issue's contract is "script the existing assertions, do not strengthen them." Option A is the only one that scripts exactly what the prose asserts while keeping every gate falsifiable: Option B's always-pass stub recreates the audited failure mode inside the engine, and Option C both exceeds scope and races ISSUE-056. Demoting scan's in-memory `scan_context` block is the honest reading of AC-2: "no bare prose self-assertion remains" is satisfied by removing the false CHECKPOINT label from the one assertion no script can check, not by faking a script for it. Conservative tiering follows the implementation note verbatim: artifact presence = blocking; cross-document consistency stays model-side prose.

## Trade-offs Accepted

- Presence-level checks pass hollow-but-present sections; depth verification (cue counts, verbatim renders, component cross-refs) is deferred to ISSUE-056/060 by design.
- Scan's DB detection is a manifest/migration-dir heuristic; a project using a DB through an undetected driver would get SKIP instead of FAIL on a missing data_model.md. The skip line names the heuristic so the gap is visible in logs.
- The dormant `philosophy` verifier's "Decision Matrix" requirement is replaced, not preserved — the fragment checkpoint it now mirrors never asserted it, and no caller or test depended on the old behavior.
- `uiux/context` stays blocking even though the skill has a user-approved "skip kickoff, proceed with PRD only" exception path; that run would need the existing prose exception handling before the checkpoint (unchanged from today's prose contract).

## Migration

1. Land ISSUE-057's bundled PR: engine phases + `--issue` optional, `.tmpl`/fragment edits adding `Run:` lines to every surviving CHECKPOINT block, `gen_skills.py` regeneration, contract-test table update, team-lead coverage table update, unit tests.
2. kickoff's frontmatter gains scoped `Bash(bash scripts/checkpoint.sh *)` / plugin-root allowances (it previously had no Bash at all); scan/uiux/mobile-uiux/desktop-uiux already allow Bash.
3. No data migration: existing repos see new behavior only on their next kickoff/scan/uiux run. The 8 previously covered skills are untouched.
4. ISSUE-060 later upgrades the uiux-family phases from presence checks to ISSUE-056's sweep validators.

## Rollback

`git revert` of the single PR restores the prose-only blocks and the 8-skill engine coverage; phase additions are independent per skill, so a single skill's phase set can also be reverted alone (<30 min). Trigger signals: false-positive blocking failures on legitimate kickoff/scan/uiux runs (e.g., section-term matching too strict for a subagent's heading style), or the DB heuristic mis-firing FAIL on DB-less fixtures.

## Open Questions

- [ ] Should the section-term matching move from case-insensitive substring to heading-anchored regex once subagent output formats are pinned? — owner: pillip, by: first false-positive report.
- [ ] Does `scan_context` deserve a persisted (schema-validated) artifact so Phase 1 becomes scriptable, or is in-memory the right contract? — owner: pillip, by: ISSUE-060 scoping.
- [ ] Should extend-mode runs get their own `--phase system-extend` instead of the alternate-path acceptance inside `system`? — owner: pillip, by: next extend-mode field report.
