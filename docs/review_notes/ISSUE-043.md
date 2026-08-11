# Review Notes — PR #68

## Code Review
_Source: reviewer-degraded_

- **[Low] TC-043b reference scan excludes the tests/ tree**
  Evidence: tests/test_dead_script_removal.py:37-48 ACTIVE_SURFACES omits tests/ (necessary — the guard file itself contains the BANNED tokens in REMOVED_FILES/BANNED/docstring). A dead-script name re-introduced in a DIFFERENT test file would not be caught by TC-043b.
  Fix: No change recommended. Impact is minimal and largely self-covering: a test that actually imports/calls a deleted script fails at runtime. If tightening ever matters, scan tests/ too while excluding this one guard module by name.

- **[Low] Extension-less BANNED substring tokens are broader than the kit_root.sh token**
  Evidence: tests/test_dead_script_removal.py:35 BANNED = ('ensure_permissions','ensure_gh','kit_root.sh','lint_skill_cache_order'). Three tokens are bare identifiers; a future live identifier like ensure_github_token would false-positive. kit_root.sh deliberately keeps its .sh suffix so it is NOT a substring of the live find_kit_root in session_start.py (verified no collision today).
  Fix: Acceptable as-is: the broader direction favors catching regressions and a false positive would be loud + trivially fixed (matches the occurrence-whitelist-over-blacklist lesson). Optional future tightening: prefix scripts/ or add extensions to the three bare tokens if a real collision appears.

## Security Findings
_Source: reviewer-degraded_

_No findings._

## Over-Engineering

_No findings._
