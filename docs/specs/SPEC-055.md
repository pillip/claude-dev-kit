# SPEC-055: Reposition the kit's identity to "verification & delegation control plane"

> Linked Issue: none (ad-hoc)
> Status: `accepted`
> Date: 2026-10-09
> Author: pillip + Claude

## Problem

The kit's official identity (README.md:6 "Specialized engineering agents and skills handle the entire development lifecycle", README.md:14-15 pipeline + agent-roster claims) no longer matches how the kit actually earns its keep: SPEC-018/019 moved research and review to runtime delegation guarded by deterministic synthesizers and refute-first auditors, and the 2026-10-08 surface audit (docs/evolution_audit.md) found the verification layer is already the kit's largest asset while ~40% of the prompt surface is fast-depreciating HOW scaffolding. Contributors deciding what to build next have no current criterion — the last normative one is ISSUE-034's kept-agent rule — so HOW-heavy surface keeps growing under the old story (the three uiux skills reached 1,806 lines with zero script checkpoints).

## Context

- README.md never mentions `/deep-research`, `/code-review`, `/security-review`, or the delegation idiom; its architecture block (README.md:14-21) leads with "Structured pipeline" and "Specialized agents". The Roadmap (README.md:553) frames the next layer as "AI dev team control plane — telemetry → eval → cumulative learning memory".
- SPEC-019 names the probe → delegate → synthesize → audit → degrade pattern "a reusable kit idiom worth investing in" and already flags the next candidate (test execution). The idiom is implemented in exactly 3 of 23 skills (review, brainstorm, bizanalysis) via `scripts/has_skill.py`, `scripts/synthesize_review_notes.py`, `scripts/synthesize_from_deep_research.py`, and the research-auditor / synthesizer-auditor agents.
- docs/evolution_audit.md (2026-10-08) classifies the full surface: skills C4/B16/A3, agents C6/B15/A11, scripts 17-of-37 already verification/provenance/synthesis. Its six structural findings are the evidence base for this SPEC.
- ISSUE-034 (done 2026-07-24) established the kept-agent criterion ("differentiated methodology / separate-context self-grading guard"); this SPEC's three-bucket rule is its successor at full-surface scope.
- Constraint — record-tests lesson (memory: feedback_record_tests_manufacture_issues, ISSUE-092 "gate record-only findings"): the README rewrite must not add new derived-fact assertions (counts, line numbers) that consistency tests would lint; derived facts are generated or not stated.
- Constraint — honesty: delegation covers 3/23 skills today. The new story must label current coverage vs flagged candidates, the same discipline as the `## Limits` sections in brainstorm/bizanalysis.
- Memory: feedback_platform_first ("don't reinvent what Claude Code native capability does better") is the standing design principle this repositioning makes official.

## Options

### Option A: Full repositioning now, with honest status labels
- **Approach**: Rewrite README's identity surface (positioning line, the 6-claim architecture block, skill descriptions for review/brainstorm/bizanalysis, Roadmap framing) to lead with verification & delegation; add an "Architecture: the delegation idiom" section documenting the 5-stage pattern with its current 3-skill coverage and flagged next candidates explicitly labeled. Codify the three-bucket classification (fast-depreciation / contract / verification-core) as the normative kept-surface criterion in CONTRIBUTING.md, linking docs/evolution_audit.md as evidence. No runtime behavior changes.
- **Pros**:
  - The deletion-heavy roadmap items (HOW deflation, A-bucket agent dissolution) land under a criterion that pre-justifies them, instead of each PR re-litigating its own deletions.
  - New contributions get a bucket test at review time, stopping further A-bucket growth immediately.
- **Cons**:
  - README temporarily describes a destination: the idiom covers 3 skills while the story makes it the architecture.
- **Trade-off**: ~120 lines README churn + ~40 lines CONTRIBUTING, +1 normative criterion, 0 runtime changes; story leads implementation by ~20 skills until delegation expansion lands.

### Option B: Additive section only
- **Approach**: Leave the existing pipeline/roster story untouched; append a standalone "Platform Delegation" README section describing SPEC-018/019; keep the audit advisory (no CONTRIBUTING criterion).
- **Pros**:
  - Zero churn to existing claims; no overstatement risk.
- **Cons**:
  - One README carries two contradictory architecture stories (agent-roster pitch at README.md:15 vs platform-first practice), and contributors still have no binding criterion — the growth pattern that produced 1,806 lines of uncheckpointed uiux prose continues.
- **Trade-off**: +40 lines only, 0 churn, but +2 coexisting identity narratives and −1 enforceable criterion; A-bucket growth rate unchanged.

### Option C: Defer repositioning until the surface matches the story
- **Approach**: Execute audit roadmap items 2–3 first (close the verification asymmetry, deflate the HOW layer), then rewrite the README last so it only describes what already exists.
- **Pros**:
  - The story never leads reality; no status labels to maintain.
- **Cons**:
  - The deflation PRs are exactly the ones that need the criterion as justification; doing them under the old identity means every deletion argues from scratch, and new HOW-heavy surface keeps landing meanwhile.
- **Trade-off**: 0 doc changes now, −1 overstatement risk, but an estimated +4–6 PR cycles (~2 months at current cadence) during which contributions are still evaluated against the stale criterion.

## Decision

**Chosen: Option A**

The criterion is needed *before* the deflation work, not after it — the classification is what justifies the deletions. Option C's trade-off line (+4–6 PR cycles building against the stale criterion) is the decisive cost: it converts every roadmap-item PR into its own identity debate. Option A's overstatement risk is bounded by the honesty constraint already practiced in the kit (`## Limits` sections): coverage labels make "3 skills today, N flagged" a stated fact, not a claim to audit.

## Trade-offs Accepted

- README describes the target architecture with the idiom at 3-skill coverage; status labels must be maintained until delegation expansion (audit roadmap item 4) lands.
- The Roadmap phrase "AI dev team control plane" is subsumed, not deleted: telemetry → eval → memory becomes the measurement arm of the verification story rather than a separate identity.
- docs/evolution_audit.md becomes load-bearing (normative evidence) and must be dated/versioned as a snapshot — its classifications can be revised by later audits, but revisions need the same evidence discipline.
- No CI enforcement of buckets in this SPEC (deferred to Open Questions) — the criterion binds at review time only.

## Migration

1. Land this SPEC (`docs/specs/SPEC-055.md`) via spec-only PR.
2. README PR: rewrite README.md:6 and :10 (positioning), the :14-21 claim block (lead with "verification & delegation", keep pipeline/state claims as supporting), update the review/brainstorm/bizanalysis skill descriptions to name their runtime delegation, add the "Architecture: the delegation idiom" section (probe `has_skill.py` → runtime skill → deterministic synthesizer → separate-context auditor → degraded fallback, with telemetry event names), reframe the Roadmap paragraph. Coverage labels: "today: /review, /brainstorm, /bizanalysis; flagged next: test execution (SPEC-019)". No new derived-fact counts.
3. CONTRIBUTING PR: add "Kept-surface criterion" section — every new or substantially changed skill/agent states its bucket; A-bucket additions require explicit justification for why the HOW content cannot be a contract (B) or a deterministic check (C); cites ISSUE-034 as predecessor and docs/evolution_audit.md as evidence.
4. Cross-link: evolution_audit.md gains a header note marking it the evidence snapshot for SPEC-055.
5. File follow-up issues for audit roadmap items 2–6 (verification asymmetry, HOW deflation, delegation expansion, scan-family consolidation, A-bucket agent dissolution) — each its own SPEC/PR; none are in this SPEC's scope.

## Rollback

Revert the README and CONTRIBUTING PRs (two `git revert`s, <1 hour; no runtime surface is touched). Trigger signals: (a) contributor field reports or issues showing the new story confuses kit adoption, (b) Claude Code removing or breaking a runtime capability the story depends on (`/deep-research`, `/code-review`, `/security-review`), which would make the delegation narrative false — in that case the degraded-path architecture (already documented) becomes the primary story again.

## Open Questions

- [ ] Should the bucket criterion become CI-enforced (e.g., a frontmatter `bucket:` field on agents/skills validated by `validate_frontmatter.py`)? — owner: pillip, by: first release after the CONTRIBUTING PR.
- [ ] Does the telemetry→eval→memory roadmap track keep its own README section or fold entirely into the verification story? — owner: pillip, by: README PR review.
- [ ] Is scan-*/greenfield agent consolidation (audit item 5) part of the repositioning narrative or an independent refactor? — owner: pillip, by: backlog grooming after follow-up issues are filed.
