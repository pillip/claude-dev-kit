# Review Notes — PR #106

## Code Review
_Source: reviewer-degraded_

- **[Low] Confidence-ritual sweep did not cover the skills roster [fixed in review]**
  Evidence: tests/test_scaffolding_residue.py (pre-fix) test_confidence_rating_only_in_uiux_whitelist swept _agent_files() only; the ritual's third habitat was a skill (diagnose step 5.5), guarded only by the diagnose-specific marker — reintroduction into any OTHER skill would have passed the suite.
  Fix: Fixed in review: the test now also sweeps _skill_files() with an empty whitelist (no skill is excepted — the uiux exception set is agents-only). Mutation-verified: appending the marker to skills/refactor/SKILL.md fails the test.

- **[Low] Test comments perpetuated the old inline prompt's wrong text_style.segments path [fixed in review]**
  Evidence: tests/test_scaffolding_residue.py docstring and test_figma_converter_agent_owns_segments_instruction comment said `text_style.segments`; scripts/figma_fetch.py:371 emits `segments` at node level — the new agents/figma-converter.md line gets it right; the comments copied the old prompt's schema error.
  Fix: Fixed in review: both comments now say the node-level `segments` field and note the old path was a schema error the migration corrected.

- **[Low] Migrate persona clause 'clean up deprecated API usage or file follow-ups' was silently lost [fixed in review]**
  Evidence: skills/migrate/SKILL.md step 4 covers detection only; after the persona-block deletion no surviving line instructed cleanup-or-follow-up after the bump, and the drop was not in the PR's honest-drop list.
  Fix: Fixed in review: clause restored as a Guidelines contract line in skills/migrate/SKILL.md.tmpl (+ regenerated SKILL.md) and pinned via a new 'deprecated API usage' needle in test_scaffolding_residue.py pins['migrate'].

- **[Low] [debt] 3 pre-existing no-trigger KIT-DEBT markers (silent-rot risk) — harvester self-match noise outside this PR's diff**
  Evidence: checkpoint.sh --phase debt: scripts/debt_harvest.py:44 and tests/test_debt_harvest.py:27,59 flagged NO-TRIGGER — same harvester docstring/fixture self-matches recorded in the ISSUE-058 review. This PR introduces zero KIT-DEBT markers.
  Fix: No action in this PR. Standing candidate: teach the harvester to skip its own module and test fixtures.

## Security Findings
_Source: reviewer-degraded_

_No findings._

## Over-Engineering

- **[Low] [delete] test_integration.py diagnose-principles test is now a strict subset of the residue test [recorded, not fixed]**
  Evidence: tests/test_integration.py::test_diagnose_skill_carries_absorbed_diagnostician_principles pins the same two needles test_scaffolding_residue.py::test_diagnose_cognitive_checklist_deleted_invariants_survive pins on both md and tmpl (which additionally pins 'suppressing errors'). Net removable lines: ~12.
  Fix: Not fixed (Low, judgment call): the integration test carries the ISSUE-034 provenance comment and keeping a redundant passing pin is harmless. Candidate cleanup: delete it and move the provenance comment to the residue test.
