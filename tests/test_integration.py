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
    "requirements.md": ["Goals", "User Stories"],
    "architecture.md": ["Overview", "Modules", "Data Model"],
    "test_plan.md": ["Strategy", "Critical Flows"],
    "ux_spec.md": ["Key Flows", "Accessibility"],
    "issues.md": ["Conventions", "Board"],
    "review_lessons.md": ["Patterns"],
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

    # Extract agent names referenced in the skill (e.g. "**Step 1: requirement-analyst → ...")
    referenced = re.findall(r"\*\*(?:Step \d+(?:\.\d+)?|[\w-]+):\s+([\w-]+)\s+→", content)
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

    # Extract subagent output files (e.g. "requirement-analyst → `docs/requirements.md`")
    output_refs = re.findall(r"→ `docs/(\w+\.md)`", content)
    assert output_refs, "No subagent output references found in kickoff"

    template_names = {p.name for p in TEMPLATE_DIR.glob("*.md")}
    for ref in output_refs:
        assert ref in template_names, (
            f"Kickoff references output docs/{ref} but templates/{ref} does not exist"
        )


# ── Test 8: validate_issues.py exists and is executable ──────────


def test_validate_issues_script_exists_and_executable():
    script = SCRIPTS_DIR / "validate_issues.py"
    assert script.exists(), "scripts/validate_issues.py not found"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/validate_issues.py is not executable (missing u+x)"


# ── Test 9: review_lessons template and agent references ──────────


def test_review_lessons_template_exists_and_has_patterns_header():
    path = TEMPLATE_DIR / "review_lessons.md"
    assert path.exists(), "Template review_lessons.md not found"
    content = path.read_text(encoding="utf-8")
    assert "Patterns" in content, "Template review_lessons.md missing section: Patterns"


@pytest.mark.parametrize(
    "agent_name",
    ["reviewer", "developer", "planner"],
    ids=["reviewer", "developer", "planner"],
)
def test_agent_references_review_lessons(agent_name):
    path = AGENT_DIR / f"{agent_name}.md"
    assert path.exists(), f"agents/{agent_name}.md not found"
    content = path.read_text(encoding="utf-8")
    assert "review_lessons" in content, (
        f"agents/{agent_name}.md does not reference review_lessons"
    )


# ── Test 10: sprint skill and team-lead agent ──────────────────────


def test_team_lead_agent_exists_and_has_task_tool():
    path = AGENT_DIR / "team-lead.md"
    assert path.exists(), "agents/team-lead.md not found"
    fm = _parse_frontmatter(path)
    assert "Task" in fm.get("tools", ""), "team-lead must have Task tool for agent orchestration"


def test_sprint_skill_exists():
    path = SKILL_DIR / "sprint" / "SKILL.md"
    assert path.exists(), "skills/sprint/SKILL.md not found"
    fm = _parse_frontmatter(path)
    assert fm.get("name") == "sprint"


def test_team_lead_references_skill_files():
    """team-lead should reference SKILL.md files it follows at runtime."""
    path = AGENT_DIR / "team-lead.md"
    content = path.read_text(encoding="utf-8")
    for skill in ["implement", "review", "ship"]:
        assert f"skills/{skill}/SKILL.md" in content, (
            f"team-lead.md should reference skills/{skill}/SKILL.md"
        )


# ── Test 11: verify_checkpoint.py exists and is executable ───────────


def test_verify_checkpoint_script_exists_and_executable():
    script = SCRIPTS_DIR / "verify_checkpoint.py"
    assert script.exists(), "scripts/verify_checkpoint.py not found"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/verify_checkpoint.py is not executable (missing u+x)"


# ── Test 12: SKILL.md files contain CHECKPOINT markers ───────────────


@pytest.mark.parametrize(
    "skill,min_checkpoints",
    [("implement", 7), ("review", 5), ("ship", 3)],
    ids=["implement", "review", "ship"],
)
def test_skill_has_checkpoint_markers(skill, min_checkpoints):
    path = SKILL_DIR / skill / "SKILL.md"
    assert path.exists(), f"skills/{skill}/SKILL.md not found"
    content = path.read_text(encoding="utf-8")
    count = content.count("CHECKPOINT — MANDATORY — NEVER SKIP")
    assert count >= min_checkpoints, (
        f"skills/{skill}/SKILL.md has {count} CHECKPOINT markers, expected >= {min_checkpoints}"
    )


# ── Test 13: ui-reviewer agent ─────────────────────────────────────────


def test_ui_reviewer_agent_exists_and_has_required_frontmatter():
    path = AGENT_DIR / "ui-reviewer.md"
    assert path.exists(), "agents/ui-reviewer.md not found"
    fm = _parse_frontmatter(path)
    missing = AGENT_REQUIRED_KEYS - fm.keys()
    assert not missing, f"ui-reviewer.md missing frontmatter keys: {missing}"


def test_review_skill_references_ui_reviewer():
    path = SKILL_DIR / "review" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "ui-reviewer" in content, (
        "skills/review/SKILL.md does not reference ui-reviewer"
    )


def test_ui_reviewer_references_review_lessons():
    path = AGENT_DIR / "ui-reviewer.md"
    content = path.read_text(encoding="utf-8")
    assert "review_lessons" in content, (
        "agents/ui-reviewer.md does not reference review_lessons"
    )


def test_team_lead_has_checkpoint_enforcement_protocol():
    path = AGENT_DIR / "team-lead.md"
    content = path.read_text(encoding="utf-8")
    assert "Checkpoint Enforcement Protocol" in content, (
        "team-lead.md missing 'Checkpoint Enforcement Protocol' section"
    )
    assert "verify_checkpoint.py" in content, (
        "team-lead.md should reference verify_checkpoint.py"
    )


# ── Test 14: brainstormer agent and brainstorm skill ─────────────────


def test_brainstormer_agent_exists_and_has_required_frontmatter():
    path = AGENT_DIR / "brainstormer.md"
    assert path.exists(), "agents/brainstormer.md not found"
    fm = _parse_frontmatter(path)
    missing = AGENT_REQUIRED_KEYS - fm.keys()
    assert not missing, f"brainstormer.md missing frontmatter keys: {missing}"


def test_brainstorm_skill_exists_and_has_required_frontmatter():
    path = SKILL_DIR / "brainstorm" / "SKILL.md"
    assert path.exists(), "skills/brainstorm/SKILL.md not found"
    fm = _parse_frontmatter(path)
    missing = SKILL_REQUIRED_KEYS - fm.keys()
    assert not missing, f"brainstorm SKILL.md missing frontmatter keys: {missing}"


def test_prd_skill_references_brainstorm_notes():
    path = SKILL_DIR / "prd" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "brainstorm_notes" in content, (
        "skills/prd/SKILL.md does not reference brainstorm_notes"
    )


# ── Test 15: business-analyst agent and bizanalysis skill ──────────────


def test_business_analyst_agent_exists_and_has_required_frontmatter():
    path = AGENT_DIR / "business-analyst.md"
    assert path.exists(), "agents/business-analyst.md not found"
    fm = _parse_frontmatter(path)
    missing = AGENT_REQUIRED_KEYS - fm.keys()
    assert not missing, f"business-analyst.md missing frontmatter keys: {missing}"


def test_bizanalysis_skill_exists_and_has_required_frontmatter():
    path = SKILL_DIR / "bizanalysis" / "SKILL.md"
    assert path.exists(), "skills/bizanalysis/SKILL.md not found"
    fm = _parse_frontmatter(path)
    missing = SKILL_REQUIRED_KEYS - fm.keys()
    assert not missing, f"bizanalysis SKILL.md missing frontmatter keys: {missing}"


def test_prd_skill_references_business_analysis():
    path = SKILL_DIR / "prd" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "business_analysis" in content, (
        "skills/prd/SKILL.md does not reference business_analysis"
    )


def test_brainstorm_skill_references_bizanalysis():
    path = SKILL_DIR / "brainstorm" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "bizanalysis" in content, (
        "skills/brainstorm/SKILL.md does not reference bizanalysis"
    )


# ── Test 16: ship skill references documenter subagent ───────────────


def test_ship_skill_references_documenter():
    path = SKILL_DIR / "ship" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "documenter" in content, (
        "skills/ship/SKILL.md does not reference documenter subagent"
    )


# ── Test 17: debugger self-review ────────────────────────────────────


def test_debugger_agent_has_self_review():
    path = AGENT_DIR / "debugger.md"
    content = path.read_text(encoding="utf-8")
    assert "Self-Review" in content, (
        "agents/debugger.md does not contain Self-Review section"
    )


def test_debug_skill_has_self_review():
    path = SKILL_DIR / "debug" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "Self-Review" in content, (
        "skills/debug/SKILL.md does not contain Self-Review step"
    )


# ── Test 18: self-review in other agents ─────────────────────────────


@pytest.mark.parametrize(
    "agent_name",
    ["developer", "reviewer", "architect", "migrator", "data-modeler", "planner"],
    ids=["developer", "reviewer", "architect", "migrator", "data-modeler", "planner"],
)
def test_agent_has_self_review(agent_name):
    path = AGENT_DIR / f"{agent_name}.md"
    assert path.exists(), f"agents/{agent_name}.md not found"
    content = path.read_text(encoding="utf-8")
    assert "Self-Review" in content, (
        f"agents/{agent_name}.md does not contain Self-Review section"
    )


# ── Test 19: review_lessons references in agents ────────────────────


@pytest.mark.parametrize(
    "agent_name",
    ["debugger", "refactorer", "devops", "migrator"],
    ids=["debugger", "refactorer", "devops", "migrator"],
)
def test_agent_references_review_lessons_extended(agent_name):
    path = AGENT_DIR / f"{agent_name}.md"
    assert path.exists(), f"agents/{agent_name}.md not found"
    content = path.read_text(encoding="utf-8")
    assert "review_lessons" in content, (
        f"agents/{agent_name}.md does not reference review_lessons"
    )


# ── Test 20: new templates exist with expected sections ──────────────


EXPECTED_NEW_TEMPLATES = {
    "brainstorm_notes.md": ["Problem Space", "Existing Landscape", "Idea Candidates", "Decisions"],
    "business_analysis.md": ["Executive Summary", "Market Analysis", "Competitive Landscape", "Risks"],
    "review_notes.md": ["Code Review", "Security Findings"],
    "ui_review_notes.md": ["State Coverage", "Copy Compliance", "Design Token Compliance", "Accessibility"],
}


@pytest.mark.parametrize(
    "name,headers",
    EXPECTED_NEW_TEMPLATES.items(),
    ids=EXPECTED_NEW_TEMPLATES.keys(),
)
def test_new_template_exists_and_has_headers(name, headers):
    path = TEMPLATE_DIR / name
    assert path.exists(), f"Template {name} not found"
    content = path.read_text(encoding="utf-8")
    for header in headers:
        assert header in content, f"Template {name} missing section: {header}"


# ── Test 21: additional agent existence checks ───────────────────────


@pytest.mark.parametrize(
    "agent_name",
    ["data-modeler", "copywriter", "mobile-uiux-developer"],
    ids=["data-modeler", "copywriter", "mobile-uiux-developer"],
)
def test_additional_agent_exists_and_has_required_frontmatter(agent_name):
    path = AGENT_DIR / f"{agent_name}.md"
    assert path.exists(), f"agents/{agent_name}.md not found"
    fm = _parse_frontmatter(path)
    missing = AGENT_REQUIRED_KEYS - fm.keys()
    assert not missing, f"{agent_name}.md missing frontmatter keys: {missing}"


# ── Test 22: checkpoint markers in secondary skills ──────────────────


@pytest.mark.parametrize(
    "skill,min_checkpoints",
    [("debug", 3), ("refactor", 3), ("devops", 3), ("migrate", 3)],
    ids=["debug", "refactor", "devops", "migrate"],
)
def test_secondary_skill_has_checkpoint_markers(skill, min_checkpoints):
    path = SKILL_DIR / skill / "SKILL.md"
    assert path.exists(), f"skills/{skill}/SKILL.md not found"
    content = path.read_text(encoding="utf-8")
    count = content.count("CHECKPOINT — MANDATORY — NEVER SKIP")
    assert count >= min_checkpoints, (
        f"skills/{skill}/SKILL.md has {count} CHECKPOINT markers, expected >= {min_checkpoints}"
    )


# ── Test 23: verify_checkpoint.py supports new skills ────────────────


def test_verify_checkpoint_supports_all_skills():
    script = SCRIPTS_DIR / "verify_checkpoint.py"
    content = script.read_text(encoding="utf-8")
    for skill in ["implement", "review", "ship", "debug", "refactor", "devops", "migrate"]:
        assert f'"{skill}"' in content, (
            f"verify_checkpoint.py does not support skill: {skill}"
        )
