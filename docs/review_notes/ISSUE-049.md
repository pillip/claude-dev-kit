# Review Notes — PR #78

## Code Review
_Source: reviewer-degraded_

- **[Low] New env-var knob KIT_ALLOW_BROWSER_INSTALL is not documented in a user-facing doc**
  Evidence: scripts/verify_visual_diff.py / verify_computed_styles.py introduce the knob; it appears only in docstrings + the runtime stderr hint. grep of README.md/docs returns nothing.
  Fix: Add a one-line entry to docs/troubleshooting.md (and/or README) documenting KIT_ALLOW_BROWSER_INSTALL=1 and that unset = the visual-diff/computed-style gates skip cleanly. Matches the recalled env-knob-documentation lesson (ISSUE-046/047 precedent — recorded there as an open Low). Recorded here + logged as a sprint Discovered follow-up; deferred off-branch to avoid a merge conflict with the in-flight main-side troubleshooting/README edits.

- **[Low] Unset-flag test pins the stderr diagnostic but not that stdout stays empty**
  Evidence: tests/test_figma_verify_family.py test_flag_unset_and_missing_does_not_install asserts 'browser unavailable' in err but never asserts stdout=='' — the issue note explicitly requires stdout stays machine-clean.
  Fix: Assert capsys.readouterr().out == '' on the unset path (capture out+err in one readouterr()).

## Security Findings
_Source: reviewer-degraded_

_No findings._

## Over-Engineering

_No findings._
