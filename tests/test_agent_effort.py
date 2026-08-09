"""Lint tests for agent model/effort hygiene (ISSUE-015 effort tiers, ISSUE-030 inherit).

Enforces the support matrix (docs/cc_feature_matrix.md) after ISSUE-030:
- agents do NOT pin a model — they inherit the session model; any surviving pin
  must carry an adjacent `# pin:` rationale comment in the frontmatter
- every agent declares a valid `effort` (`max` is session-only, never frontmatter)
- `xhigh` is safe everywhere under inherit (auto-fallback on models capping at
  `high`), but a *pinned* sonnet/haiku must not claim it
- the heavy/light split matches the ISSUE-015 scope
- no retired model id is presented as current in the README
- the settings snippet parses and its fallbackModel is a list of <=3
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = sorted((ROOT / "agents").glob("*.md"))

VALID_EFFORT = {"low", "medium", "high", "xhigh"}

# Persisted effort values per *pinned* model (only relevant if a pin survives).
VALID_BY_MODEL = {
    "opus": {"low", "medium", "high", "xhigh"},
    "sonnet": {"low", "medium", "high"},
    "haiku": {"low", "medium", "high"},
    "fable": {"low", "medium", "high", "xhigh"},
    "inherit": VALID_EFFORT,  # auto-fallback applies (matrix row 1)
}

# Agents the ISSUE-015 scope names as heavy (deep reasoning) and light (extraction).
HEAVY = {"architect", "developer", "reviewer",
         "planner", "desktop-uiux-developer", "mobile-uiux-developer", "uiux-developer"}
LIGHT = {"scan-analyst", "scan-architect", "scan-data-modeler", "scan-qa-designer",
         "documenter", "issue-writer", "requirement-analyst", "a11y-auditor",
         "codebase-scanner"}


def _frontmatter_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---")
    assert len(parts) >= 3, f"{path.name}: no frontmatter block"
    return parts[1]


def _frontmatter(path: Path) -> dict:
    fm = {}
    for line in _frontmatter_block(path).splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm


def test_all_agents_present():
    # 29 core + 3 delegation auditors (ISSUE-029). ISSUE-034 absorbed 4 dead
    # persona files (diagnostician, migrator, refactorer, prd-writer) into their
    # skills — they were never invoked (no Task/subagent_type spawn).
    assert len(AGENTS) == 32


def test_agents_inherit_session_model():
    # ISSUE-030: no model pins. A pin may survive only as a deliberate,
    # documented decision — flagged by a `# pin:` rationale comment in the
    # frontmatter block. Today the roster has zero pins.
    for a in AGENTS:
        fm = _frontmatter(a)
        if "model" in fm and fm["model"] != "inherit":
            block = _frontmatter_block(a)
            assert re.search(r"^#\s*pin:", block, flags=re.M), (
                f"{a.name}: pins model={fm['model']!r} without an adjacent "
                f"'# pin: <rationale>' comment (ISSUE-030)"
            )
            assert fm["model"] in VALID_BY_MODEL, f"{a.name}: unknown model {fm['model']!r}"


def test_every_core_agent_has_valid_effort():
    for a in AGENTS:
        fm = _frontmatter(a)
        assert "effort" in fm, f"{a.name}: missing effort"
        model = fm.get("model", "inherit")
        allowed = VALID_BY_MODEL.get(model, VALID_EFFORT)
        assert fm["effort"] in allowed, (
            f"{a.name}: effort {fm['effort']!r} invalid for model {model!r} "
            f"(allowed: {sorted(allowed)})"
        )


def test_no_xhigh_on_pinned_incapable_models():
    for a in AGENTS:
        fm = _frontmatter(a)
        if fm.get("effort") == "xhigh" and "model" in fm:
            assert fm["model"] in {"opus", "fable", "inherit"}, (
                f"{a.name}: xhigh with pinned model {fm['model']!r} (caps at high)"
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


def test_readme_agent_table_shows_effort_not_model():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "| Agent | Effort | Role | Tools |" in readme
    assert "| Agent | Model |" not in readme


def test_settings_snippet_fallback_model_valid():
    snippet = json.loads((ROOT / "project/.claude/settings.snippet.json").read_text(encoding="utf-8"))
    fb = snippet.get("fallbackModel")
    assert isinstance(fb, list) and fb, "fallbackModel must be a non-empty list"
    assert len(fb) <= 3, "fallbackModel accepts at most 3 entries"
