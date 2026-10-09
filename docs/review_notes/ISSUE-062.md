# Review Notes — PR #108

## Code Review
_Source: reviewer-degraded_

- **[Medium] Review-lessons consumption silently dropped from all five dissolved flows; functional gap at the two surviving subagent call sites [FIXED IN REVIEW]**
  Evidence: All five deleted agents carried 'Check recalled review lessons (native memory; passed in your prompt when you run as a subagent)' (e.g. origin/main:agents/copywriter.md step 1), and test_integration.py's test_agent_references_review_lessons_extended pinned it for all five — the PR removes them from that param list without relocating the requirement. Post-diff grep: zero 'review lessons' mentions in the ship 3.5 or uiux Phase 4.5 inline contracts; subagents only see what the caller passes.
  Fix: APPLIED during review: added 'Pass any recalled review lessons about recurring copy issues into the subagent prompt' to the three uiux Phase 4.5 blocks and folded recalled documentation lessons into the ship 3.5 context-passing line; regenerated SKILL.md via gen_skills.py; pinned 'recalled review lessons' in tests/test_agent_dissolution.py for both call sites.

- **[Low] Copywriter's rule-shaped NEVERs and three of four copy formulas not absorbed and not given an explicit SPEC disposition**
  Evidence: origin/main:agents/copywriter.md NEVER list (no dev jargon like 'null'/'422', no passive-voice error copy, no exclamation marks for errors, no divergent labels for the same action) and the empty-state/confirmation/toast formulas. The uiux x3 inline contract absorbs only the error formula + inventory/glossary/voice lines; the pre-existing 'Banned copy tells' block covers AI-slop tells, not these. SPEC-062 scopes kept value to 'the inventory contract (WHAT)' but never lists these checkable banned-pattern-shaped rules in either bucket.
  Fix: Fold the three NEVERs into the existing 'Banned copy tells' line (same enforcement genre), or note in SPEC-062 that they were assessed as native-competence craft and dropped deliberately. Left unresolved (Low): the ISSUE-060 fragments-SSOT extraction of the triplicated copy contract is the natural landing site.

- **[Low] Two of four brainstorm invariant pins are satisfiable by the frontmatter allowed-tools line alone [FIXED IN REVIEW]**
  Evidence: tests/test_agent_dissolution.py asserted 'has_skill.py' in text and 'deep-research' in text; both substrings appear in skills/brainstorm/SKILL.md.tmpl:6 allowed-tools, so deleting the entire step 5a research path would not fail these two pins.
  Fix: APPLIED during review: pins hardened to body-level strings 'python3 scripts/has_skill.py deep-research' and 'invoke `/deep-research`' which only exist in the routing body.

- **[Low] SPEC-062 Migration step 8 requires docs/test_plan.md TC entries, but the file is untracked and absent from this PR**
  Evidence: docs/specs/SPEC-062.md:90 — 'update docs/test_plan.md TC entries for the new invariant tests.' The file is an untracked main-root registry artifact, so the step is unverifiable inside the PR diff.
  Fix: Handled operationally: the review's test-plan update step (review skill 5.7) applies the TC entries to the main-root docs/test_plan.md via registry_edit.sh, outside the PR diff — consistent with how this repo batches registry-sync changes on main.

- **[Low] [debt] Three no-trigger KIT-DEBT markers flagged by the ledger are all pre-existing debt-harvest fixtures/docstring examples, none introduced by this PR**
  Evidence: scripts/debt_harvest.py:44 (usage docstring example), tests/test_debt_harvest.py:27 and :59 (intentional test fixtures exercising the no-trigger detection). Ledger total 14, no-trigger 3, malformed 1 — identical before and after this diff.
  Fix: No action in this PR. If the ledger noise recurs, teach debt_harvest.py to skip its own docstring and test fixture files.

## Security Findings
_Source: reviewer-degraded_

- **[Medium] Dissolved documenter/copywriter subagent calls drop the roster tool-grant restriction: inline contracts constrain output scope but not toolset, widening the prompt-injection blast radius [FIXED IN REVIEW]**
  Evidence: skills/ship/SKILL.md step 3.5 'launch a general-purpose documentation subagent' (was agents/documenter.md with 'tools: Read, Glob, Grep, Write, Edit' — no Bash/web) under a session pre-approving Bash(git *), Bash(gh *); same pattern in the three uiux Phase 4.5 blocks ('launch a copy subagent', was copywriter with the same restricted grant) under sessions pre-approving unscoped Bash + WebSearch. The subagents ingest PR diff summaries / PRD-docs content; an injection in that content would reach a context where Bash and web exfiltration are available, which the deleted agents' tools frontmatter made structurally impossible.
  Fix: APPLIED during review: added a toolset-restriction contract line to all four call sites in the .tmpl files — 'Read, Glob, Grep, Write, Edit only — must not run Bash or fetch web content (preserves the dissolved roster agent's tool grant)' — regenerated via gen_skills.py and pinned in tests/test_agent_dissolution.py alongside the existing contract assertions.

## Over-Engineering

- **[Low] [delete] test_integration.py test_ship_skill_carries_absorbed_documenter_contract duplicates the stricter dissolution test**
  Evidence: tests/test_integration.py Test 16 asserts 'no updates needed' and 'must exist in the codebase' in skills/ship/SKILL.md only; tests/test_agent_dissolution.py asserts the same two strings plus more pins on BOTH tmpl and generated SKILL.md — a strict superset. Net removable lines: ~12.
  Fix: Intentional per SPEC-062 Migration step 5 ('repurpose' the old test, Test-16 numbering continuity). Recorded, not applied — acceptable duplicate; candidate for cleanup if test_integration is ever restructured.
