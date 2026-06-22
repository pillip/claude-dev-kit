"""Tests for ISSUE-022: plugin manifests + skill-hook path hygiene.

- `.claude-plugin/plugin.json` is valid and its version matches VERSION.
- `hooks/hooks.json` parses and declares the kit's always-on hook events.
- The `/freeze`,`/careful`,`/guard` skill hooks stay in frontmatter (supported for
  plugin skills) but no longer depend solely on the undocumented `${CLAUDE_SKILL_DIR}`:
  they prefer `${CLAUDE_PLUGIN_ROOT}` and fall back across documented vars, and the
  guard scripts they point at exist.
"""

import json
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML not installed — run dev extras")

ROOT = Path(__file__).resolve().parents[1]


def test_plugin_json_valid_and_versioned():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    for field in ("name", "version", "description"):
        assert manifest.get(field), f"plugin.json missing {field}"
    assert manifest["version"] == (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_sales_pack_is_a_dependent_plugin():
    # ISSUE-025: optional packs can't be in-plugin components (plugins are
    # all-or-nothing), so the sales pack is its own plugin depending on core.
    sales = ROOT / "packs" / "sales" / ".claude-plugin" / "plugin.json"
    manifest = json.loads(sales.read_text(encoding="utf-8"))
    assert manifest["name"] == "claude-dev-kit-sales"
    for field in ("version", "description"):
        assert manifest.get(field), f"sales plugin.json missing {field}"
    core_name = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["name"]
    deps = manifest.get("dependencies") or []
    dep_names = [d if isinstance(d, str) else d.get("name") for d in deps]
    assert core_name in dep_names, f"sales pack must depend on core plugin {core_name!r}"


def test_hooks_json_parses_and_declares_events():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    # The always-on hooks ported from settings.snippet.json (+ ISSUE-016 events).
    for event in ("WorktreeCreate", "SessionEnd", "Stop", "SubagentStart",
                  "SubagentStop", "PreToolUse", "PostToolUse", "PostToolUseFailure"):
        assert event in hooks, f"hooks.json missing {event}"
    # Plugin hooks resolve scripts via the documented ${CLAUDE_PLUGIN_ROOT}.
    blob = json.dumps(hooks)
    assert "CLAUDE_PLUGIN_ROOT" in blob


def _skill_hook_commands(skill: str) -> list[str]:
    fm = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8").split("---")[1]
    data = yaml.safe_load(fm)
    return [h["command"] for group in data["hooks"]["PreToolUse"] for h in group["hooks"]]


@pytest.mark.parametrize("skill", ["freeze", "careful", "guard"])
def test_skill_hooks_prefer_documented_vars(skill):
    cmds = _skill_hook_commands(skill)
    assert cmds, f"{skill} has no PreToolUse hook commands"
    for c in cmds:
        # Prefer the documented plugin var, keep the project-dir fallback.
        assert "CLAUDE_PLUGIN_ROOT" in c, f"{skill}: hook does not try ${{CLAUDE_PLUGIN_ROOT}}"
        assert "CLAUDE_PROJECT_DIR" in c, f"{skill}: hook lacks project-dir fallback"


def test_guard_scripts_exist_where_referenced():
    assert (ROOT / "skills" / "freeze" / "freeze_guard.py").exists()
    assert (ROOT / "skills" / "careful" / "careful_guard.py").exists()


def test_skills_keep_frontmatter_hooks_not_moved_to_hooks_json():
    # Per the corrected SPEC-017: skill hooks stay in frontmatter (supported for
    # plugin skills), they are NOT moved into the plugin hooks.json.
    plugin_hooks = json.dumps(json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")))
    assert "freeze_guard.py" not in plugin_hooks
    assert "careful_guard.py" not in plugin_hooks
