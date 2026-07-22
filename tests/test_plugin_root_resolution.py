"""ISSUE-035: plugin-resolved skill entry commands.

Under a plugin install the consuming project has no `scripts/` dir and
`$CLAUDE_PLUGIN_ROOT` is NOT exported to the model's shell — but Claude Code
substitutes the literal text `${CLAUDE_PLUGIN_ROOT}` inside plugin skill
bodies at load time (verified live 2026-07-22). These tests pin the three
mechanisms that make kit scripts reachable in both layouts:

1. every generated skill that instructs `scripts/...` commands carries the
   Kit Script Root preamble section (the substitution-based resolution rule);
2. every allowed-tools list that allowlists kit scripts also allowlists the
   plugin-root-prefixed form;
3. generated files open with frontmatter at byte 0 (CC ignores frontmatter
   otherwise) — the AUTO-GENERATED header sits below it;
4. checkpoint.sh resolves verify_checkpoint.py via CLAUDE_PLUGIN_ROOT when
   set, falling back to its own location when not.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GENERATED = sorted(
    list(ROOT.glob("skills/*/SKILL.md")) + list(ROOT.glob("packs/*/skills/*/SKILL.md"))
)

SCRIPT_CMD_RE = re.compile(r"(?:bash|python3) scripts/")


def _has_tmpl(skill_md: Path) -> bool:
    return (skill_md.parent / "SKILL.md.tmpl").exists()


def test_generated_skills_discovered():
    assert len(GENERATED) >= 25


def test_script_using_skills_carry_kit_script_root_section():
    for md in GENERATED:
        if not _has_tmpl(md):
            continue  # hand-written (freeze/careful/guard) — no kit scripts
        text = md.read_text(encoding="utf-8")
        if SCRIPT_CMD_RE.search(text):
            assert "### Kit Script Root" in text, (
                f"{md}: instructs scripts/ commands without the Kit Script Root rule"
            )
            assert "${CLAUDE_PLUGIN_ROOT}" in text, (
                f"{md}: Kit Script Root section lost its substitution placeholder"
            )


def test_allowed_tools_include_plugin_root_patterns():
    for md in GENERATED:
        text = md.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("allowed-tools:") and "scripts/" in line:
                assert "Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/*)" in line, (
                    f"{md}: allowlists kit scripts without the plugin-root bash form"
                )
                assert "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)" in line, (
                    f"{md}: allowlists kit scripts without the plugin-root python3 form"
                )


def test_frontmatter_at_byte_zero_in_generated_files():
    for md in GENERATED:
        if not _has_tmpl(md):
            continue
        text = md.read_text(encoding="utf-8")
        tmpl = (md.parent / "SKILL.md.tmpl").read_text(encoding="utf-8")
        if tmpl.startswith("---\n"):
            assert text.startswith("---\n"), (
                f"{md}: frontmatter must start at byte 0 or CC drops it"
            )


def test_checkpoint_resolves_via_plugin_root_env(tmp_path):
    # Simulate a plugin layout: checkpoint.sh + verify_checkpoint.py live under
    # a "plugin root" that is not the CWD, and CLAUDE_PLUGIN_ROOT points there.
    plugin_root = tmp_path / "plugroot"
    (plugin_root / "scripts").mkdir(parents=True)
    (plugin_root / "scripts" / "checkpoint.sh").write_text(
        (ROOT / "scripts" / "checkpoint.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    probe = plugin_root / "scripts" / "verify_checkpoint.py"
    probe.write_text("import sys; print('RESOLVED-VIA-PLUGIN-ROOT'); sys.exit(0)\n")

    workdir = tmp_path / "project"
    workdir.mkdir()
    result = subprocess.run(
        ["bash", str(plugin_root / "scripts" / "checkpoint.sh")],
        cwd=workdir,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": str(plugin_root)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "RESOLVED-VIA-PLUGIN-ROOT" in result.stdout


def test_checkpoint_falls_back_to_script_dir_without_env(tmp_path):
    kit_root = tmp_path / "kit"
    (kit_root / "scripts").mkdir(parents=True)
    (kit_root / "scripts" / "checkpoint.sh").write_text(
        (ROOT / "scripts" / "checkpoint.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    probe = kit_root / "scripts" / "verify_checkpoint.py"
    probe.write_text("import sys; print('RESOLVED-VIA-SCRIPT-DIR'); sys.exit(0)\n")

    result = subprocess.run(
        ["bash", str(kit_root / "scripts" / "checkpoint.sh")],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "RESOLVED-VIA-SCRIPT-DIR" in result.stdout
