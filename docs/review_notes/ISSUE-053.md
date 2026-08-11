# Review Notes — PR #85

## Code Review
_Source: reviewer-degraded_

- **[Low] Drift guard only validates the README occurrence, not docs/troubleshooting.md**
  Evidence: tests/test_env_knob_docs.py:77 combined.find("KIT_SPRINT_QUEUE_GH_TIMEOUT") returns the first occurrence (README, concatenated first at line 72), so the 240-char window at line 83 only ever covers the README mention. troubleshooting.md:30 ("defaults to `10` seconds") could drift independently and no test would catch it — test_troubleshooting_documents_both_new_env_knobs asserts only the knob NAME is present, not its value.
  Fix: Iterate over all KIT_SPRINT_QUEUE_GH_TIMEOUT occurrences (or check the README and TROUBLESHOOTING windows separately) and assert the parsed default appears in each.

- **[Low] Bare-substring `default in window` can mask drift for substring-numbers**
  Evidence: tests/test_env_knob_docs.py:84 `default in window` is a substring test; if the code default ever changed to a value that is a substring of the stale documented number (e.g. a new `1` still found inside a stale `10`), the guard would pass despite real drift. Not exploitable at the current value (10), but brittle.
  Fix: Match the documented value with a word boundary, e.g. re.search(rf"\b{re.escape(default)}\b", window).

- **[Low] [info] Documented KIT_CHECKPOINT_TEST_TIMEOUT default 600 has no drift guard**
  Evidence: README.md:653 documents default `600`, which matches verify_checkpoint.py:55 (_DEFAULT_TEST_TIMEOUT = 600) today, so there is no drift now. This third documented number is outside the test's coverage and could silently drift later. Out of ISSUE-053 AC scope (AC only covers the two new knobs).
  Fix: Optional future hardening: extend the drift guard to also parse _DEFAULT_TEST_TIMEOUT out of verify_checkpoint.py. No action required for this issue.

## Security Findings
_Source: reviewer-degraded_

_No findings._

## Over-Engineering

- **[Low] [shrink] Two near-identical doc-presence tests could collapse into one loop**
  Evidence: tests/test_env_knob_docs.py:51-66 test_readme_documents_both_new_env_knobs and test_troubleshooting_documents_both_new_env_knobs differ only by the target file. Net removable ~7 lines.
  Fix: Optional: loop over ((README, "README.md"), (TROUBLESHOOTING, "docs/troubleshooting.md")). Judgment call, not a clear win — splitting preserves independent pass/fail and per-file failure messages. Otherwise lean; ship.
