"""Lightweight docs-consistency assertion for the two operator env knobs (ISSUE-053).

Two env vars change runtime behavior and must be discoverable by operators, so
this small test module makes a docs-consistency assertion over the user-facing
docs: it verifies both knob names are documented and that the documented default
has not drifted from the code. It extends the existing docs-test coverage rather
than exercising runtime behavior. The two knobs are:
- KIT_ALLOW_BROWSER_INSTALL — opt-in for the Playwright browser install step
- KIT_SPRINT_QUEUE_GH_TIMEOUT — seconds for the sprint-queue `gh pr view`
  merge-state probe (scripts/sprint_queue.py)

The three tests assert:
- README.md documents both new knob names (test_readme_documents_both_new_env_knobs).
- docs/troubleshooting.md documents both new knob names
  (test_troubleshooting_documents_both_new_env_knobs).
- a drift guard that ties the documented KIT_SPRINT_QUEUE_GH_TIMEOUT default to
  the code constant (test_sprint_queue_timeout_default_matches_docs): the default
  is parsed out of sprint_queue.py at runtime (never hardcoded here), so a future
  default change forces the user-facing docs to be updated in lockstep
  (canonical-env-numbers lesson).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
TROUBLESHOOTING = ROOT / "docs" / "troubleshooting.md"
SPRINT_QUEUE = ROOT / "scripts" / "sprint_queue.py"

KNOBS = ("KIT_ALLOW_BROWSER_INSTALL", "KIT_SPRINT_QUEUE_GH_TIMEOUT")

# Parses the numeric default out of the exact expression in sprint_queue.py:
#     os.environ.get("KIT_SPRINT_QUEUE_GH_TIMEOUT", "10")
_DEFAULT_RE = re.compile(
    r'os\.environ\.get\(\s*["\']KIT_SPRINT_QUEUE_GH_TIMEOUT["\']\s*,\s*["\'](\d+)["\']\s*\)'
)


def _parsed_gh_timeout_default() -> str:
    """Return the KIT_SPRINT_QUEUE_GH_TIMEOUT default string parsed from code."""
    m = _DEFAULT_RE.search(SPRINT_QUEUE.read_text(encoding="utf-8"))
    assert m, (
        "could not parse the KIT_SPRINT_QUEUE_GH_TIMEOUT default out of "
        f"{SPRINT_QUEUE.name}; the os.environ.get(...) shape changed — update "
        "the regex (and this drift guard) alongside it"
    )
    return m.group(1)


def test_readme_documents_both_new_env_knobs():
    readme = README.read_text(encoding="utf-8")
    missing = [knob for knob in KNOBS if knob not in readme]
    assert not missing, (
        f"README.md does not document env knob(s): {missing}; "
        "operators cannot discover them"
    )


def test_troubleshooting_documents_both_new_env_knobs():
    text = TROUBLESHOOTING.read_text(encoding="utf-8")
    missing = [knob for knob in KNOBS if knob not in text]
    assert not missing, (
        f"docs/troubleshooting.md does not document env knob(s): {missing}; "
        "operators cannot discover them"
    )


def test_sprint_queue_timeout_default_matches_docs():
    default = _parsed_gh_timeout_default()
    combined = (
        README.read_text(encoding="utf-8")
        + "\n"
        + TROUBLESHOOTING.read_text(encoding="utf-8")
    )

    idx = combined.find("KIT_SPRINT_QUEUE_GH_TIMEOUT")
    assert idx != -1, (
        "KIT_SPRINT_QUEUE_GH_TIMEOUT is not documented in README.md or "
        "docs/troubleshooting.md, so its default cannot be verified"
    )

    window = combined[idx:idx + 240]
    assert default in window, (
        f"documented KIT_SPRINT_QUEUE_GH_TIMEOUT default should be {default!r} "
        f"(parsed from {SPRINT_QUEUE.name}) but that value does not appear near "
        "the knob's mention in the docs — the docs drifted from the code default"
    )
