"""Integration tests validating skill/agent definitions, templates, scripts, and settings."""

import json
import os
import re
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _parse_frontmatter(path: Path) -> dict:
    """Parse YAML-like frontmatter between --- delimiters into a dict."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, f"No frontmatter found in {path}"
    fm = {}
    for line in match.group(1).strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm


# ── Test 1: Agent frontmatter ──────────────────────────────────────


AGENT_DIR = ROOT / "agents"
AGENT_REQUIRED_KEYS = {"name", "description", "tools", "model"}


def _agent_files():
    return sorted(AGENT_DIR.glob("*.md"))


@pytest.mark.parametrize("agent_path", _agent_files(), ids=lambda p: p.name)
def test_agent_has_required_frontmatter(agent_path):
    fm = _parse_frontmatter(agent_path)
    missing = AGENT_REQUIRED_KEYS - fm.keys()
    assert not missing, f"{agent_path.name} missing frontmatter keys: {missing}"


# ── Test 2: Skill frontmatter ──────────────────────────────────────


SKILL_DIR = ROOT / "skills"
SKILL_REQUIRED_KEYS = {"name", "description", "allowed-tools"}


def _skill_files():
    return sorted(SKILL_DIR.rglob("SKILL.md"))


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_skill_has_required_frontmatter(skill_path):
    fm = _parse_frontmatter(skill_path)
    missing = SKILL_REQUIRED_KEYS - fm.keys()
    assert not missing, f"{skill_path.parent.name} missing frontmatter keys: {missing}"


# ── Test 3: Templates exist and have expected section headers ──────


TEMPLATE_DIR = ROOT / "templates"
EXPECTED_TEMPLATES = {
    "requirements.md": ["Goals", "User stories"],
    "architecture.md": ["Overview", "Modules", "Data model"],
    "test_plan.md": ["Strategy", "Test cases"],
    "ux_spec.md": ["Key flows", "Accessibility"],
    "issues.md": ["Conventions", "Board"],
}


@pytest.mark.parametrize(
    "name,headers",
    EXPECTED_TEMPLATES.items(),
    ids=EXPECTED_TEMPLATES.keys(),
)
def test_template_exists_and_has_headers(name, headers):
    path = TEMPLATE_DIR / name
    assert path.exists(), f"Template {name} not found"
    content = path.read_text(encoding="utf-8")
    for header in headers:
        assert header in content, f"Template {name} missing section: {header}"


# ── Test 4: Kickoff skill references valid agents ──────────────────


def test_kickoff_references_valid_agents():
    kickoff = SKILL_DIR / "kickoff" / "SKILL.md"
    content = kickoff.read_text(encoding="utf-8")

    # Extract agent names referenced in the skill (e.g. "requirement-analyst ->")
    referenced = re.findall(r"- (\S+) ->", content)
    assert referenced, "No agent references found in kickoff SKILL.md"

    existing = {p.stem for p in AGENT_DIR.glob("*.md")}
    for agent_name in referenced:
        assert agent_name in existing, (
            f"Kickoff references agent '{agent_name}' but agents/{agent_name}.md does not exist"
        )


# ── Test 5: Install scripts are executable with correct shebangs ───


SCRIPTS_DIR = ROOT / "scripts"


def _shell_scripts():
    return sorted(SCRIPTS_DIR.glob("*.sh"))


@pytest.mark.parametrize("script", _shell_scripts(), ids=lambda p: p.name)
def test_script_executable_and_shebang(script):
    # Check shebang
    first_line = script.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("#!"), f"{script.name} missing shebang"
    assert "bash" in first_line or "sh" in first_line, (
        f"{script.name} shebang does not reference bash/sh: {first_line}"
    )

    # Check executable bit
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, f"{script.name} is not executable (missing u+x)"


# ── Test 6: Settings snippet is valid JSON with required keys ──────


def test_settings_snippet_valid():
    snippet_path = ROOT / "project" / ".claude" / "settings.snippet.json"
    assert snippet_path.exists(), "settings.snippet.json not found"

    data = json.loads(snippet_path.read_text(encoding="utf-8"))

    assert "statusLine" in data, "settings.snippet.json missing 'statusLine' key"
    assert "hooks" in data, "settings.snippet.json missing 'hooks' key"
    assert isinstance(data["hooks"], dict), "'hooks' should be a dict"
    assert isinstance(data["statusLine"], dict), "'statusLine' should be a dict"


# ── Test 7: Kickoff outputs match template names ───────────────────


def test_kickoff_outputs_match_templates():
    """Kickoff subagent outputs (requirement, ux, architecture, test_plan) must have templates."""
    kickoff = SKILL_DIR / "kickoff" / "SKILL.md"
    content = kickoff.read_text(encoding="utf-8")

    # Extract subagent output files (e.g. "requirement-analyst -> docs/requirements.md")
    output_refs = re.findall(r"-> docs/(\w+\.md)", content)
    assert output_refs, "No subagent output references found in kickoff"

    template_names = {p.name for p in TEMPLATE_DIR.glob("*.md")}
    for ref in output_refs:
        assert ref in template_names, (
            f"Kickoff references output docs/{ref} but templates/{ref} does not exist"
        )
