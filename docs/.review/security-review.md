# Security Review — ISSUE-041 (degraded-path, security dimension)

Surface: build-time codegen (`scripts/fragments.py`, `scripts/gen_skills.py`) plus
prompt/instruction text files. No network, no user-facing runtime, no data store.

Checks performed:
- `grep -nE 'eval\(|exec\(|os\.system|subprocess|shell=True|__import__|pickle'`
  over `scripts/fragments.py` and `scripts/gen_skills.py` → **none found**.
- Token resolution: `design_philosophy_fragment` / `design_philosophy_checkpoint`
  call `str.format()` on **constant** templates, filling only constant values
  (`_DESKTOP_EXTRA_QUESTION`, `_DESKTOP_EXTRA_DERIVE`, `_RESPONSE_STEP[...]`,
  `/shortcut`). No untrusted/user input flows into the format string or its args,
  so there is no format-string / injection vector.
- `skill_name` is validated by `_require_uiux_skill` (raises `ValueError` for any
  value outside the fixed `UIUX_SKILLS` tuple); `_RESPONSE_STEP[skill_name]` is
  therefore always a known key (no `KeyError`/lookup-of-attacker-string path).
- No file paths are constructed from input in `fragments.py` (no path traversal).
  `gen_skills.py` globs `skills/*/SKILL.md.tmpl` from a fixed `KIT_ROOT` and writes
  siblings — unchanged by this PR.
- No secrets, keys, or credentials introduced.

## Findings

_No findings._
