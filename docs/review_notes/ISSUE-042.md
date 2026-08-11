# Review Notes — PR #64

## Code Review
_Source: degraded path — claude-dev-kit:reviewer agent, code dimension (runtime /code-review unavailable to sub-agents); raw output: docs/.review/code-review.md_

- **[Low] Frontmatter helper misses closing-fence check; scans body when fence absent (diverges from validate_frontmatter.py oracle)**
  Evidence: tests/test_orchestrator_disable_model_invocation.py:27 — text.split("---", 2)[1] returns entire file remainder when no closing --- exists; empirically false-passes with key only in body. Oracle guards this at scripts/validate_frontmatter.py:39-40.
  Fix: Assert len(text.split("---", 2)) >= 3 in _frontmatter_lines with a named failure message before indexing [1].

- **[Low] First-match-wins on duplicate disable-model-invocation keys; YAML last-wins would yield false while guard passes**
  Evidence: tests/test_orchestrator_disable_model_invocation.py:42 — early return on first match; empirically passes on 'true' followed by 'false', which safe_load resolves to false.
  Fix: Collect all matching values and assert the list equals ["true"] (catches duplicates and wrong values together).

- **[Low] [design] Frozen ORCHESTRATOR_SKILLS allowlist cannot self-detect future orchestrators — accepted as conscious-decision registry**
  Evidence: tests/test_orchestrator_disable_model_invocation.py:17-21 — explicit comment directs future orchestrators to be added deliberately.
  Fix: No change requested; optionally add a heuristic companion check (skills granting Bash(git *) must set the flag) if orchestrators proliferate.

- **[Low] [debt] Pre-existing KIT-DEBT no-trigger markers surfaced by the debt checkpoint (none introduced by this diff)**
  Evidence: debt checkpoint advisory for ISSUE-042: 3 no-trigger (silent-rot risk) + 1 malformed marker, all pre-existing in scripts/debt_harvest.py:44 (docstring example) and tests/test_debt_harvest.py:27,:35,:59 (harvester test fixtures). The ISSUE-042 diff adds zero KIT-DEBT markers.
  Fix: No action for this PR; markers are debt-harvester self-referential docs/fixtures. If the harvester later excludes its own docstring/fixtures, these disappear from the ledger.

## Security Findings
_Source: degraded path — claude-dev-kit:reviewer agent, security dimension (runtime /security-review unavailable to sub-agents); raw output: docs/.review/security-review.md_

- **[Low] Guard test's first-match frontmatter parse can disagree with the runtime YAML parser on duplicate keys**
  Evidence: tests/test_orchestrator_disable_model_invocation.py:34-42 — loop returns on the FIRST unindented 'disable-model-invocation:' line and never inspects the rest of the frontmatter; scripts/validate_frontmatter.py:32 limits pattern checks to SCALAR_KEYS={name, description, argument-hint} and its PyYAML path (line 84) accepts duplicate keys (last-wins), so a later duplicate 'disable-model-invocation: false' would pass both the guard and the oracle while the runtime either takes last-wins (flag becomes false) or rejects the block (all frontmatter dropped) — both fail-open, re-enabling autonomous invocation while the guard stays green
  Fix: Collect ALL top-level disable-model-invocation occurrences; assert exactly one exists and its value is 'true' (gather matches into a list, assert len(matches) == 1, then assert the value) instead of returning on the first hit. Two-line change; keeps the no-PyYAML constraint (ISSUE-021).

## Over-Engineering

- **[Low] [shrink] _frontmatter_lines duplicated from tests/test_skill_frontmatter_yaml.py (both copies share the fence weakness)**
  Evidence: tests/test_orchestrator_disable_model_invocation.py:24-27 vs tests/test_skill_frontmatter_yaml.py:21-24 — logic-identical helpers. Net removable lines: ~4; everything else load-bearing per the minimality axis.
  Fix: Extract one shared helper (tests/conftest.py) with the closing-fence assert; one change fixes both files.
