"""Lint tests for ISSUE-015: agent effort tiers + model reference hygiene.

Enforces the support matrix (docs/cc_feature_matrix.md):
- every agent declares a valid `effort` for its `model`
- `xhigh` only on opus (sonnet caps at `high`); `max` is session-only (never frontmatter)
- the heavy/light split matches the issue scope
- no retired model id is presented as current in the README
- the settings snippet parses and its fallbackModel is a list of <=3
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = sorted((ROOT / "agents").glob("*.md"))

# Valid persisted effort values per model. `max` is session-only (excluded).
VALID_BY_MODEL = {
    "opus": {"low", "medium", "high", "xhigh"},
    "sonnet": {"low", "medium", "high"},
    "haiku": {"low", "medium", "high"},
    "fable": {"low", "medium", "high", "xhigh"},
}

# Agents the issue scope names as heavy (deep reasoning) and light (extraction).
HEAVY = {"architect", "developer", "reviewer", "diagnostician", "refactorer",
         "planner", "desktop-uiux-developer", "mobile-uiux-developer", "uiux-developer"}
LIGHT = {"scan-analyst", "scan-architect", "scan-data-modeler", "scan-qa-designer",
         "documenter", "issue-writer", "requirement-analyst", "a11y-auditor",
         "codebase-scanner"}


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---")
    assert len(parts) >= 3, f"{path.name}: no frontmatter block"
    fm = {}
    for line in parts[1].splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm


def test_all_agents_present():
    assert len(AGENTS) == 33


def test_every_agent_has_valid_effort_for_its_model():
    for a in AGENTS:
        fm = _frontmatter(a)
        assert "model" in fm, f"{a.name}: missing model"
        assert "effort" in fm, f"{a.name}: missing effort"
        model, effort = fm["model"], fm["effort"]
        assert model in VALID_BY_MODEL, f"{a.name}: unexpected model {model!r}"
        assert effort in VALID_BY_MODEL[model], (
            f"{a.name}: effort {effort!r} invalid for model {model!r} "
            f"(allowed: {sorted(VALID_BY_MODEL[model])})"
        )


def test_no_xhigh_on_non_opus_capable_models():
    for a in AGENTS:
        fm = _frontmatter(a)
        if fm.get("effort") == "xhigh":
            assert fm.get("model") in {"opus", "fable"}, (
                f"{a.name}: xhigh requires opus/fable, got {fm.get('model')!r}"
            )


def test_no_session_only_effort_in_frontmatter():
    for a in AGENTS:
        fm = _frontmatter(a)
        assert fm.get("effort") not in {"max", "ultracode"}, (
            f"{a.name}: {fm.get('effort')!r} is session-only, not valid in frontmatter"
        )


def test_heavy_agents_run_high_or_above():
    for a in AGENTS:
        if a.stem in HEAVY:
            fm = _frontmatter(a)
            assert fm["effort"] in {"high", "xhigh"}, (
                f"{a.stem} is a heavy agent but effort={fm['effort']!r}"
            )


def test_light_agents_run_low_or_medium():
    for a in AGENTS:
        if a.stem in LIGHT:
            fm = _frontmatter(a)
            assert fm["effort"] in {"low", "medium"}, (
                f"{a.stem} is an extraction agent but effort={fm['effort']!r}"
            )


def test_readme_has_no_retired_model_id():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "claude-opus-4-6" not in readme, "retired model id claude-opus-4-6 still in README"


def test_settings_snippet_fallback_model_valid():
    snippet = json.loads((ROOT / "project/.claude/settings.snippet.json").read_text(encoding="utf-8"))
    fb = snippet.get("fallbackModel")
    assert isinstance(fb, list) and fb, "fallbackModel must be a non-empty list"
    assert len(fb) <= 3, "fallbackModel accepts at most 3 entries"
