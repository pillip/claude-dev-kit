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


def test_marketplace_lists_core():
    # ISSUE-026: the repo is a marketplace listing the core plugin (root).
    mkt = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert mkt.get("name"), "marketplace.json missing name"
    assert mkt.get("owner", {}).get("name"), "marketplace.json missing owner.name"
    entries = {p["name"]: p for p in mkt.get("plugins", [])}
    core_name = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["name"]
    assert core_name in entries, f"marketplace missing core plugin {core_name!r}"
    # Source points at the right location.
    assert entries[core_name]["source"] in ("./", "."), entries[core_name]["source"]


def test_hooks_json_parses_and_declares_events():
    doc = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    # Current plugin schema wraps events in a top-level "hooks" object — the
    # flat form loads zero hooks (found by the ISSUE-027 live parity run).
    assert set(doc.keys()) == {"hooks"}, "hooks.json must wrap events in a 'hooks' object"
    hooks = doc["hooks"]
    # The always-on hooks ported from settings.snippet.json (+ ISSUE-016 events).
    for event in ("SessionEnd", "Stop", "SubagentStart",
                  "SubagentStop", "PreToolUse", "PostToolUse", "PostToolUseFailure"):
        assert event in hooks, f"hooks.json missing {event}"
    # WorktreeCreate is a CREATOR contract on current builds (the hook must
    # create the worktree and print its path; no output aborts creation).
    # The kit must NOT register it — a passive hook breaks native worktree
    # creation for every plugin user (ISSUE-027 live probe, 2026-07-22).
    assert "WorktreeCreate" not in hooks, (
        "WorktreeCreate is a creator contract — do not re-add a passive hook"
    )
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
