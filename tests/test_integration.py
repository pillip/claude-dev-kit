"""Integration tests validating skill/agent definitions, templates, scripts, and settings."""

import json
import os
import re
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _parse_frontmatter(path: Path) -> dict:
    """Parse YAML-like frontmatter between --- delimiters into a dict."""
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^---\n(.*?)\n---", text, re.DOTALL | re.MULTILINE)
    assert match, f"No frontmatter found in {path}"
    fm = {}
    for line in match.group(1).strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm


# ── Test 1: Agent frontmatter ──────────────────────────────────────


AGENT_DIR = ROOT / "agents"
# `model` is deliberately NOT required: agents inherit the session model
# (ISSUE-030); a pin needs a `# pin:` rationale (see test_agent_effort.py).
AGENT_REQUIRED_KEYS = {"name", "description", "tools"}


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
    "test_plan.md": ["Strategy", "Critical Flows", "E2E Testing Strategy", "Backend Robustness"],
    "prd_digest.md": ["Goals", "Target User", "Must-have Features"],
    "ux_spec.md": ["Key Flows", "Accessibility"],
    "issues.md": ["Conventions", "Board"],
    # review_lessons.md retired in ISSUE-033 — review lessons now live in
    # Claude Code native memory (see test_agents_reference_native_review_lessons).
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


# ── Test 9: native-memory review-lessons learning loop (ISSUE-033) ──


def test_review_lessons_template_is_retired():
    # ISSUE-033: review lessons moved to Claude Code native memory; the bespoke
    # docs/review_lessons.md registry + template are retired (0 entries ever).
    assert not (TEMPLATE_DIR / "review_lessons.md").exists(), (
        "templates/review_lessons.md should be removed — lessons live in native memory now"
    )


def test_no_active_surface_writes_legacy_review_lessons():
    """No skill/agent may write docs/review_lessons.md or use the RL-NNN registry."""
    offenders = []
    for base in (AGENT_DIR, SKILL_DIR):
        for md in base.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            # A retired-mention ("do not write", "retired") is allowed; a live
            # registry_edit against review_lessons is not.
            if "registry_edit.sh docs/review_lessons" in text or "[RL-NNN]" in text:
                offenders.append(str(md.relative_to(ROOT)))
    assert not offenders, f"legacy review_lessons registry still wired in: {offenders}"


@pytest.mark.parametrize(
    "agent_name",
    ["reviewer", "developer", "planner"],
    ids=["reviewer", "developer", "planner"],
)
def test_agent_references_review_lessons(agent_name):
    path = AGENT_DIR / f"{agent_name}.md"
    assert path.exists(), f"agents/{agent_name}.md not found"
    content = path.read_text(encoding="utf-8")
    assert "review lessons" in content, (
        f"agents/{agent_name}.md no longer references review lessons (native memory)"
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
    # ISSUE-031: checkpoints are two-tier — blocking (MANDATORY — NEVER SKIP)
    # plus advisory (report & continue). Both count as checkpoint markers.
    count = (content.count("CHECKPOINT — MANDATORY — NEVER SKIP")
             + content.count("CHECKPOINT — ADVISORY"))
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
    assert "review lessons" in content, (
        "agents/ui-reviewer.md no longer references review lessons (native memory)"
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


# ── Test 17: diagnose self-review ────────────────────────────────────


def test_diagnose_skill_carries_absorbed_diagnostician_principles():
    # ISSUE-034: the diagnostician persona (never invoked) was absorbed into
    # /diagnose. Its root-cause discipline must survive in the skill body.
    content = (SKILL_DIR / "diagnose" / "SKILL.md").read_text(encoding="utf-8")
    assert "root cause" in content.lower(), "diagnose skill lost root-cause principle"
    assert "regression test" in content.lower(), "diagnose skill lost regression-test principle"


def test_diagnose_skill_has_self_review():
    path = SKILL_DIR / "diagnose" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "Self-Review" in content, (
        "skills/diagnose/SKILL.md does not contain Self-Review step"
    )


# ── Test 18: self-review in other agents ─────────────────────────────


@pytest.mark.parametrize(
    "agent_name",
    ["developer", "reviewer", "architect", "data-modeler", "planner", "qa-designer",
     "brainstormer", "business-analyst", "copywriter", "devops", "documenter",
     "mobile-uiux-developer", "requirement-analyst",
     "team-lead", "test-generator", "ui-reviewer", "uiux-developer", "ux-designer"],
    ids=["developer", "reviewer", "architect", "data-modeler", "planner", "qa-designer",
         "brainstormer", "business-analyst", "copywriter", "devops", "documenter",
         "mobile-uiux-developer", "requirement-analyst",
         "team-lead", "test-generator", "ui-reviewer", "uiux-developer", "ux-designer"],
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
    ["devops",
     "architect", "brainstormer", "business-analyst", "copywriter", "data-modeler",
     "documenter", "mobile-uiux-developer", "qa-designer",
     "requirement-analyst", "test-generator", "uiux-developer", "ux-designer"],
    ids=["devops",
         "architect", "brainstormer", "business-analyst", "copywriter", "data-modeler",
         "documenter", "mobile-uiux-developer", "qa-designer",
         "requirement-analyst", "test-generator", "uiux-developer", "ux-designer"],
)
def test_agent_references_review_lessons_extended(agent_name):
    path = AGENT_DIR / f"{agent_name}.md"
    assert path.exists(), f"agents/{agent_name}.md not found"
    content = path.read_text(encoding="utf-8")
    assert "review lessons" in content, (
        f"agents/{agent_name}.md no longer references review lessons (native memory)"
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
    [("diagnose", 3), ("refactor", 3), ("devops", 3), ("migrate", 3)],
    ids=["diagnose", "refactor", "devops", "migrate"],
)
def test_secondary_skill_has_checkpoint_markers(skill, min_checkpoints):
    path = SKILL_DIR / skill / "SKILL.md"
    assert path.exists(), f"skills/{skill}/SKILL.md not found"
    content = path.read_text(encoding="utf-8")
    count = (content.count("CHECKPOINT — MANDATORY — NEVER SKIP")
             + content.count("CHECKPOINT — ADVISORY"))
    assert count >= min_checkpoints, (
        f"skills/{skill}/SKILL.md has {count} CHECKPOINT markers, expected >= {min_checkpoints}"
    )


# ── Test 23: verify_checkpoint.py supports new skills ────────────────


def test_verify_checkpoint_supports_all_skills():
    script = SCRIPTS_DIR / "verify_checkpoint.py"
    content = script.read_text(encoding="utf-8")
    for skill in ["implement", "review", "ship", "diagnose", "refactor", "devops", "migrate", "testgen"]:
        assert f'"{skill}"' in content, (
            f"verify_checkpoint.py does not support skill: {skill}"
        )


# ── Test 24: design_philosophy template has Decision Matrix and Reference Anchors


# ── Test 25: issue-writer agent and issue skill ─────────────────────


def test_issue_writer_agent_exists_and_has_required_frontmatter():
    path = AGENT_DIR / "issue-writer.md"
    assert path.exists(), "agents/issue-writer.md not found"
    fm = _parse_frontmatter(path)
    missing = AGENT_REQUIRED_KEYS - fm.keys()
    assert not missing, f"issue-writer.md missing frontmatter keys: {missing}"


def test_issue_skill_exists_and_has_required_frontmatter():
    path = SKILL_DIR / "issue" / "SKILL.md"
    assert path.exists(), "skills/issue/SKILL.md not found"
    fm = _parse_frontmatter(path)
    missing = SKILL_REQUIRED_KEYS - fm.keys()
    assert not missing, f"issue SKILL.md missing frontmatter keys: {missing}"


def test_issue_skill_references_issue_writer():
    path = SKILL_DIR / "issue" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "issue-writer" in content, (
        "skills/issue/SKILL.md does not reference issue-writer agent"
    )


def test_issue_writer_has_self_review():
    path = AGENT_DIR / "issue-writer.md"
    content = path.read_text(encoding="utf-8")
    assert "Self-Review" in content, (
        "agents/issue-writer.md does not contain Self-Review section"
    )


def test_issue_skill_references_validate_issues():
    path = SKILL_DIR / "issue" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "validate_issues" in content, (
        "skills/issue/SKILL.md does not reference validate_issues"
    )


# ── Test 26: design_philosophy template has Decision Matrix and Reference Anchors


# ── Test 26: Manual setup field ───────────────────────────────────────


def test_planner_has_manual_setup_detection():
    path = AGENT_DIR / "planner.md"
    content = path.read_text(encoding="utf-8")
    assert "manual" in content.lower(), (
        "agents/planner.md does not contain manual setup detection logic"
    )
    assert "Manual" in content, (
        "agents/planner.md does not reference Manual field"
    )


def test_issue_template_has_manual_field():
    path = TEMPLATE_DIR / "issues.md"
    content = path.read_text(encoding="utf-8")
    assert "Manual" in content, (
        "templates/issues.md does not contain Manual field"
    )
    assert "Manual: true | false" in content, (
        "templates/issues.md missing 'Manual: true | false' in issue detail"
    )


def test_issue_writer_has_manual_field():
    path = AGENT_DIR / "issue-writer.md"
    content = path.read_text(encoding="utf-8")
    assert "Manual" in content, (
        "agents/issue-writer.md does not reference Manual field"
    )


def test_team_lead_skips_manual_issues():
    path = AGENT_DIR / "team-lead.md"
    content = path.read_text(encoding="utf-8")
    assert "Manual" in content, (
        "agents/team-lead.md does not handle Manual issues"
    )
    assert "skip" in content.lower(), (
        "agents/team-lead.md should skip Manual: true issues"
    )


# ── Test 27: design_philosophy template ──────────────────────────────


def test_design_philosophy_template_has_decision_matrix():
    path = TEMPLATE_DIR / "design_philosophy.md"
    assert path.exists(), "Template design_philosophy.md not found"
    content = path.read_text(encoding="utf-8")
    assert "Decision Matrix" in content, "design_philosophy.md missing Decision Matrix section"
    assert "Reference Anchors" in content, "design_philosophy.md missing Reference Anchors section"


# ── Test 28: qa-designer E2E & backend robustness ─────────────────────


def test_qa_designer_has_self_review():
    path = AGENT_DIR / "qa-designer.md"
    content = path.read_text(encoding="utf-8")
    assert "Self-Review" in content, (
        "agents/qa-designer.md does not contain Self-Review section"
    )


def test_qa_designer_has_e2e_strategy():
    path = AGENT_DIR / "qa-designer.md"
    content = path.read_text(encoding="utf-8")
    assert "E2E" in content, "agents/qa-designer.md does not mention E2E"
    for framework in ["Playwright", "Cypress", "Maestro", "Detox"]:
        assert framework in content, (
            f"agents/qa-designer.md does not mention {framework}"
        )


def test_test_plan_template_has_e2e_and_backend_sections():
    path = TEMPLATE_DIR / "test_plan.md"
    content = path.read_text(encoding="utf-8")
    assert "E2E Testing Strategy" in content, (
        "templates/test_plan.md missing E2E Testing Strategy section"
    )
    assert "Backend Robustness" in content, (
        "templates/test_plan.md missing Backend Robustness section"
    )
    assert "Platform" in content, (
        "templates/test_plan.md missing Platform column in test cases table"
    )


def test_developer_has_e2e_guidance():
    path = AGENT_DIR / "developer.md"
    content = path.read_text(encoding="utf-8")
    assert "E2E" in content, "agents/developer.md does not mention E2E"
    assert "test_plan.md" in content, (
        "agents/developer.md does not reference test_plan.md for E2E strategy"
    )


# ── Test 29: validate_issues.py dependency validation ─────────────────


def test_validate_issues_has_cycle_detection():
    script = SCRIPTS_DIR / "validate_issues.py"
    content = script.read_text(encoding="utf-8")
    assert "circular" in content.lower() or "cycle" in content.lower(), (
        "validate_issues.py does not contain cycle detection logic"
    )
    assert "_detect_cycles" in content or "detect_cycle" in content, (
        "validate_issues.py missing cycle detection function"
    )


def test_validate_issues_has_depth_warning():
    script = SCRIPTS_DIR / "validate_issues.py"
    content = script.read_text(encoding="utf-8")
    assert "depth" in content.lower(), (
        "validate_issues.py does not contain dependency depth check"
    )


def test_validate_issues_has_dangling_reference_check():
    script = SCRIPTS_DIR / "validate_issues.py"
    content = script.read_text(encoding="utf-8")
    assert "does not exist" in content, (
        "validate_issues.py does not check for dangling Depends-On references"
    )


# ── Test 30: implement skill Manual field check ───────────────────────


def test_implement_skill_checks_manual_field():
    path = SKILL_DIR / "implement" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "Manual" in content, (
        "skills/implement/SKILL.md does not check Manual field"
    )
    assert "Manual: true" in content, (
        "skills/implement/SKILL.md missing Manual: true stop condition"
    )


# ── Test 31: parallel context loading in skills ──────────────────────


@pytest.mark.parametrize(
    "skill",
    ["sprint", "review", "implement"],
    ids=["sprint", "review", "implement"],
)
def test_skill_specifies_parallel_context_loading(skill):
    path = SKILL_DIR / skill / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "parallel" in content.lower(), (
        f"skills/{skill}/SKILL.md does not specify parallel context loading"
    )


def test_kickoff_has_ux_architect_parallel():
    path = SKILL_DIR / "kickoff" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "ux-designer + architect" in content.lower() or "ux + architecture in parallel" in content.lower(), (
        "kickoff SKILL.md does not specify ux-designer + architect parallel execution"
    )


# ── Test 32: per-phase failure recovery in sprint ─────────────────────


def test_team_lead_has_per_phase_recovery():
    path = AGENT_DIR / "team-lead.md"
    content = path.read_text(encoding="utf-8")
    assert "per-phase" in content.lower() or "review-rework" in content.lower(), (
        "team-lead.md does not contain per-phase failure recovery logic"
    )


def test_sprint_skill_has_per_phase_recovery():
    path = SKILL_DIR / "sprint" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "per-phase" in content.lower(), (
        "sprint SKILL.md does not mention per-phase recovery"
    )


# ── Test 33: team-lead simplification ─────────────────────────────────


def test_team_lead_has_quick_summary():
    path = AGENT_DIR / "team-lead.md"
    content = path.read_text(encoding="utf-8")
    assert "Quick Summary" in content, (
        "team-lead.md missing Quick Summary section"
    )


def test_sprint_skill_has_agent_selection_table():
    path = SKILL_DIR / "sprint" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "Agent Selection" in content, (
        "sprint SKILL.md missing Agent Selection table"
    )
    assert "developer" in content and "diagnose" in content, (
        "sprint SKILL.md Agent Selection table is incomplete"
    )


# ── Test 34: checkpoints in design skills ─────────────────────────────


@pytest.mark.parametrize(
    "skill,min_checkpoints",
    [("uiux", 3), ("mobile-uiux", 3)],
    ids=["uiux", "mobile-uiux"],
)
def test_design_skill_has_checkpoint_markers(skill, min_checkpoints):
    path = SKILL_DIR / skill / "SKILL.md"
    assert path.exists(), f"skills/{skill}/SKILL.md not found"
    content = path.read_text(encoding="utf-8")
    count = (content.count("CHECKPOINT — MANDATORY — NEVER SKIP")
             + content.count("CHECKPOINT — ADVISORY"))  # two-tier since ISSUE-031
    assert count >= min_checkpoints, (
        f"skills/{skill}/SKILL.md has {count} CHECKPOINT markers, expected >= {min_checkpoints}"
    )


def test_verify_checkpoint_supports_design_skills():
    script = SCRIPTS_DIR / "verify_checkpoint.py"
    content = script.read_text(encoding="utf-8")
    for skill in ["uiux", "mobile-uiux"]:
        assert f'"{skill}"' in content, (
            f"verify_checkpoint.py does not support skill: {skill}"
        )


# ── Test 35: kickoff cross-document validation ────────────────────────


def test_kickoff_has_cross_document_validation():
    path = SKILL_DIR / "kickoff" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "Cross-document validation" in content or "cross-validation" in content.lower(), (
        "kickoff SKILL.md missing cross-document validation step"
    )
    for check in ["data_model", "architecture", "requirements"]:
        assert check in content, (
            f"kickoff cross-validation does not reference {check}"
        )


# ── Test 36: README Decision Tree ─────────────────────────────────────


def test_readme_has_decision_tree():
    """README should contain a Decision Tree guiding users to the right skill."""
    content = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Decision Tree" in content, "README missing Decision Tree section"
    for skill in ["/brainstorm", "/prd", "/kickoff", "/uiux", "/mobile-uiux",
                  "/sprint", "/implement", "/review", "/ship", "/diagnose",
                  "/migrate", "/refactor", "/devops", "/issue", "/testgen",
                  ]:
        assert skill in content, f"Decision Tree missing reference to {skill}"


# ── Test 37: kickoff CHECKPOINT markers ────────────────────────────────


def test_kickoff_has_checkpoint_markers():
    path = SKILL_DIR / "kickoff" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    count = (content.count("CHECKPOINT — MANDATORY — NEVER SKIP")
             + content.count("CHECKPOINT — ADVISORY"))  # two-tier since ISSUE-031
    assert count >= 5, (
        f"skills/kickoff/SKILL.md has {count} CHECKPOINT markers, expected >= 5"
    )


# ── Test 38: verify_checkpoint.py timeout and retry ────────────────────


def test_verify_checkpoint_has_timeout_and_retry():
    script = SCRIPTS_DIR / "verify_checkpoint.py"
    content = script.read_text(encoding="utf-8")
    assert "timeout" in content, (
        "verify_checkpoint.py does not contain timeout parameter"
    )
    assert "_run_with_retry" in content, (
        "verify_checkpoint.py does not contain _run_with_retry helper"
    )
    assert "TimeoutExpired" in content, (
        "verify_checkpoint.py does not handle TimeoutExpired"
    )


# ── Test 39: new templates (sprint_state, runbook, troubleshooting, contributing)


EXPECTED_PHASE2_TEMPLATES = {
    "sprint_state.md": ["Meta", "Issue Progress", "Discovered Issues", "Escalations"],
    "runbook.md": ["Health Checks", "Scaling", "Rollback", "Disaster Recovery"],
    "troubleshooting.md": ["Problem", "Solution"],
    "contributing.md": ["Branch", "Commit", "Pull Request", "Code Style"],
}


@pytest.mark.parametrize(
    "name,headers",
    EXPECTED_PHASE2_TEMPLATES.items(),
    ids=EXPECTED_PHASE2_TEMPLATES.keys(),
)
def test_phase2_template_exists_and_has_headers(name, headers):
    path = TEMPLATE_DIR / name
    assert path.exists(), f"Template {name} not found"
    content = path.read_text(encoding="utf-8")
    for header in headers:
        assert header in content, f"Template {name} missing section: {header}"


# ── Test 40: developer parallel context loading ────────────────────────


def test_developer_has_parallel_context_loading():
    path = AGENT_DIR / "developer.md"
    content = path.read_text(encoding="utf-8")
    assert "parallel Read" in content, (
        "agents/developer.md does not specify parallel Read tool calls"
    )


# ── Test 41: validate_issues negative test cases ──────────────────────


def test_validate_issues_rejects_malformed_input():
    """validate_issues.py should report violations for issues missing required fields."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import validate_issues as vi

    malformed = (
        "### ISSUE-001: Missing fields\n"
        "- Estimate: 5d\n"
        "- PRD-Ref:\n"
        "- Depends-On:\n"
        "#### Acceptance Criteria\n"
        "- [ ] Only one AC\n"
    )
    issues = vi.parse_issues(malformed)
    warnings = vi.validate(issues)
    assert len(warnings) >= 3, (
        f"Expected at least 3 violations for malformed input, got {len(warnings)}: {warnings}"
    )


def test_validate_issues_detects_cycles():
    """validate_issues.py should detect circular dependencies."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import validate_issues as vi

    cyclic = (
        "### ISSUE-001: First\n"
        "- Estimate: 1d\n"
        "- PRD-Ref: FR-001\n"
        "- Depends-On: ISSUE-002\n"
        "#### Acceptance Criteria\n"
        "- [ ] Given X, when Y, then Z\n"
        "- [ ] Given A, when B, then C\n"
        "\n"
        "### ISSUE-002: Second\n"
        "- Estimate: 1d\n"
        "- PRD-Ref: FR-002\n"
        "- Depends-On: ISSUE-001\n"
        "#### Acceptance Criteria\n"
        "- [ ] Given X, when Y, then Z\n"
        "- [ ] Given A, when B, then C\n"
    )
    issues = vi.parse_issues(cyclic)
    warnings = vi.validate(issues)
    cycle_warnings = [w for w in warnings if "circular" in w.lower()]
    assert len(cycle_warnings) >= 1, (
        f"Expected at least 1 cycle warning, got: {warnings}"
    )


# ── Test 42: skill prerequisite documentation ──────────────────────────


@pytest.mark.parametrize(
    "skill",
    ["implement", "review"],
    ids=["implement", "review"],
)
def test_skill_requires_prerequisites_documented(skill):
    path = SKILL_DIR / skill / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    has_pre = (
        "pre-condition" in content.lower()
        or "prerequisite" in content.lower()
        or "before" in content.lower()
        or "checkpoint rules" in content.lower()
        or "must exist" in content.lower()
        or "find pr" in content.lower()
    )
    assert has_pre, (
        f"skills/{skill}/SKILL.md does not document prerequisites or pre-conditions"
    )


# ── Test 43: test_plan.md E2E sub-sections ─────────────────────────────


def test_test_plan_has_e2e_subsections():
    path = TEMPLATE_DIR / "test_plan.md"
    content = path.read_text(encoding="utf-8")
    assert "Test Independence" in content, "test_plan.md missing Test Independence subsection"
    assert "Network Mocking" in content, "test_plan.md missing Network Mocking subsection"
    assert "Flaky Test Protocol" in content, "test_plan.md missing Flaky Test Protocol subsection"


# ── Test 44: skill argument validation ─────────────────────────────────


@pytest.mark.parametrize(
    "skill",
    ["sprint", "refactor", "diagnose", "migrate"],
    ids=["sprint", "refactor", "diagnose", "migrate"],
)
def test_skill_has_argument_validation(skill):
    path = SKILL_DIR / skill / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "Argument Validation" in content, (
        f"skills/{skill}/SKILL.md missing Argument Validation section"
    )


# ── Test 45: execution-model.md ────────────────────────────────────────


def test_execution_model_doc_exists():
    path = ROOT / "docs" / "execution-model.md"
    assert path.exists(), "docs/execution-model.md not found"
    content = path.read_text(encoding="utf-8")
    for section in ["Skill", "Agent", "Worktree", "flock_edit", "Checkpoint"]:
        assert section in content, f"docs/execution-model.md missing section about {section}"


# ── Test 46: kit troubleshooting doc ───────────────────────────────────


def test_kit_troubleshooting_doc_exists():
    path = ROOT / "docs" / "troubleshooting.md"
    assert path.exists(), "docs/troubleshooting.md not found"
    content = path.read_text(encoding="utf-8")
    for keyword in ["checkpoint", "gh auth", "worktree", "validate_issues"]:
        assert keyword in content, f"docs/troubleshooting.md missing keyword: {keyword}"


# ── Test 47: testgen skill and test-generator agent ─────────────────


def test_testgen_skill_exists_and_has_required_frontmatter():
    path = SKILL_DIR / "testgen" / "SKILL.md"
    assert path.exists(), "skills/testgen/SKILL.md not found"
    fm = _parse_frontmatter(path)
    missing = SKILL_REQUIRED_KEYS - fm.keys()
    assert not missing, f"testgen SKILL.md missing frontmatter keys: {missing}"


def test_test_generator_agent_exists_and_has_required_frontmatter():
    path = AGENT_DIR / "test-generator.md"
    assert path.exists(), "agents/test-generator.md not found"
    fm = _parse_frontmatter(path)
    missing = AGENT_REQUIRED_KEYS - fm.keys()
    assert not missing, f"test-generator.md missing frontmatter keys: {missing}"


def test_testgen_skill_references_test_generator():
    path = SKILL_DIR / "testgen" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "test-generator" in content, (
        "skills/testgen/SKILL.md does not reference test-generator agent"
    )


def test_test_generator_has_self_review():
    path = AGENT_DIR / "test-generator.md"
    content = path.read_text(encoding="utf-8")
    assert "Self-Review" in content, (
        "agents/test-generator.md does not contain Self-Review section"
    )


def test_testgen_skill_has_checkpoint_markers():
    path = SKILL_DIR / "testgen" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    count = (content.count("CHECKPOINT — MANDATORY — NEVER SKIP")
             + content.count("CHECKPOINT — ADVISORY"))  # two-tier since ISSUE-031
    assert count >= 3, (
        f"skills/testgen/SKILL.md has {count} CHECKPOINT markers, expected >= 3"
    )


def test_testgen_skill_has_gap_report():
    path = SKILL_DIR / "testgen" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "Gap Report" in content or "gap report" in content.lower(), (
        "skills/testgen/SKILL.md should present a gap report to the user"
    )


def test_testgen_skill_references_test_plan():
    path = SKILL_DIR / "testgen" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "test_plan.md" in content, (
        "skills/testgen/SKILL.md does not reference test_plan.md"
    )


def test_test_generator_references_review_lessons():
    path = AGENT_DIR / "test-generator.md"
    content = path.read_text(encoding="utf-8")
    assert "review lessons" in content, (
        "agents/test-generator.md no longer references review lessons (native memory)"
    )


def test_testgen_skill_has_e2e_support():
    path = SKILL_DIR / "testgen" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "E2E" in content, "skills/testgen/SKILL.md does not mention E2E"


def test_testgen_skill_has_argument_validation():
    path = SKILL_DIR / "testgen" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "Argument Validation" in content, (
        "skills/testgen/SKILL.md missing Argument Validation section"
    )


# ── Test 48: Implement skill TDD flow ──────────────────────────────────


def test_implement_skill_has_tdd_flow():
    """Implement skill should follow TDD: tests-written → red → code → test."""
    path = SKILL_DIR / "implement" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "TDD" in content, "skills/implement/SKILL.md does not mention TDD"
    assert "RED" in content or "red" in content, (
        "skills/implement/SKILL.md does not mention RED phase"
    )
    # Verify checkpoint order: tests-written before red before code before test
    tw_pos = content.find("--phase tests-written")
    red_pos = content.find("--phase red")
    code_pos = content.find("--phase code")
    # Use regex to find "--phase test " to avoid matching "--phase tests-written" or "--phase test-plan"
    import re as _re
    test_match = _re.search(r"--phase test(?:\s|$)", content)
    test_pos = test_match.start() if test_match else -1
    assert tw_pos < red_pos < code_pos < test_pos, (
        "Implement skill checkpoints not in TDD order: tests-written → red → code → test"
    )


def test_implement_skill_has_red_checkpoint():
    """Implement skill must have a RED checkpoint marker."""
    path = SKILL_DIR / "implement" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "--phase red" in content, (
        "skills/implement/SKILL.md missing --phase red checkpoint"
    )


def test_developer_has_tdd_workflow():
    """Developer agent should follow TDD workflow."""
    path = AGENT_DIR / "developer.md"
    content = path.read_text(encoding="utf-8")
    assert "TDD" in content, "agents/developer.md does not mention TDD"
    assert "RED" in content or "Verify RED" in content, (
        "agents/developer.md does not mention RED/Verify RED phase"
    )


# ── Test 49: Developer Detox support ───────────────────────────────────


def test_developer_has_detox_support():
    """Developer agent should mention Detox for mobile E2E testing."""
    path = AGENT_DIR / "developer.md"
    content = path.read_text(encoding="utf-8")
    assert "Detox" in content, "agents/developer.md does not mention Detox"


# ── Test 50: Review skill test-quality checkpoint ──────────────────────


def test_review_skill_has_test_quality_checkpoint():
    path = SKILL_DIR / "review" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "--phase test-quality" in content, (
        "skills/review/SKILL.md missing --phase test-quality checkpoint"
    )


def test_review_skill_has_qa_designer_recheck():
    """Review skill should re-invoke qa-designer to update test_plan.md."""
    path = SKILL_DIR / "review" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "qa-designer" in content, (
        "skills/review/SKILL.md does not reference qa-designer"
    )
    assert "test_plan.md" in content, (
        "skills/review/SKILL.md does not reference test_plan.md"
    )


# ── Test 51: Ship skill post-merge smoke ───────────────────────────────


def test_ship_skill_has_smoke_checkpoint():
    path = SKILL_DIR / "ship" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "--phase smoke" in content, (
        "skills/ship/SKILL.md missing --phase smoke checkpoint"
    )


def test_ship_skill_smoke_is_mandatory():
    """Post-merge smoke test should be MANDATORY, not optional."""
    path = SKILL_DIR / "ship" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "optional" not in content.lower() or "MANDATORY" in content, (
        "skills/ship/SKILL.md post-merge smoke should be mandatory"
    )


# ── Test 52: verify_checkpoint.py supports new phases ──────────────────


def test_verify_checkpoint_supports_red_phase():
    script = SCRIPTS_DIR / "verify_checkpoint.py"
    content = script.read_text(encoding="utf-8")
    assert '"red"' in content or "'red'" in content, (
        "verify_checkpoint.py does not support implement red phase"
    )


def test_verify_checkpoint_supports_test_quality_phase():
    script = SCRIPTS_DIR / "verify_checkpoint.py"
    content = script.read_text(encoding="utf-8")
    assert "test-quality" in content, (
        "verify_checkpoint.py does not support review test-quality phase"
    )


def test_verify_checkpoint_supports_smoke_phase():
    script = SCRIPTS_DIR / "verify_checkpoint.py"
    content = script.read_text(encoding="utf-8")
    assert '"smoke"' in content or "'smoke'" in content, (
        "verify_checkpoint.py does not support ship smoke phase"
    )


# ── Test 53: E2E auto-execution in autotest hook ──────────────────────


def test_autotest_has_e2e_support():
    """autotest.py should support E2E test detection and execution."""
    path = ROOT / "project" / ".claude" / "hooks" / "autotest.py"
    content = path.read_text(encoding="utf-8")
    for framework in ["playwright", "detox", "maestro", "cypress"]:
        assert framework in content.lower(), (
            f"autotest.py does not mention {framework}"
        )


def test_autotest_has_e2e_timeout():
    """autotest.py should have a longer timeout for E2E tests."""
    path = ROOT / "project" / ".claude" / "hooks" / "autotest.py"
    content = path.read_text(encoding="utf-8")
    assert "E2E_TIMEOUT" in content, "autotest.py missing E2E_TIMEOUT constant"


# ── Test 54: GitHub Actions CI workflow ────────────────────────────────


def test_ci_workflow_exists():
    path = ROOT / ".github" / "workflows" / "ci.yml"
    assert path.exists(), ".github/workflows/ci.yml not found"
    content = path.read_text(encoding="utf-8")
    assert "pytest" in content, "CI workflow does not run pytest"
    assert "cov-fail-under" in content, "CI workflow does not enforce coverage"


# ── Test 55: Implement skill checkpoint count updated ─────────────────


def test_implement_skill_has_enough_checkpoints():
    """Implement skill should have 8+ checkpoints after TDD conversion."""
    path = SKILL_DIR / "implement" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    count = (content.count("CHECKPOINT — MANDATORY — NEVER SKIP")
             + content.count("CHECKPOINT — ADVISORY"))  # two-tier since ISSUE-031
    assert count >= 8, (
        f"skills/implement/SKILL.md has {count} CHECKPOINT markers, expected >= 8 after TDD"
    )


# ── Test 56: Ship skill checkpoint count updated ─────────────────────


def test_ship_skill_has_enough_checkpoints():
    """Ship skill should have 4+ checkpoints after smoke addition."""
    path = SKILL_DIR / "ship" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    count = (content.count("CHECKPOINT — MANDATORY — NEVER SKIP")
             + content.count("CHECKPOINT — ADVISORY"))  # two-tier since ISSUE-031
    assert count >= 4, (
        f"skills/ship/SKILL.md has {count} CHECKPOINT markers, expected >= 4 after smoke"
    )


# ── Test 57: Review skill checkpoint count updated ───────────────────


def test_review_skill_has_enough_checkpoints():
    """Review skill should have 6+ checkpoints after test-quality addition."""
    path = SKILL_DIR / "review" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    count = (content.count("CHECKPOINT — MANDATORY — NEVER SKIP")
             + content.count("CHECKPOINT — ADVISORY"))  # two-tier since ISSUE-031
    assert count >= 6, (
        f"skills/review/SKILL.md has {count} CHECKPOINT markers, expected >= 6 after test-quality"
    )


# ── Test 58: design-auditor agent ─────────────────────────────────────


def test_design_auditor_agent_exists_and_has_required_frontmatter():
    path = AGENT_DIR / "design-auditor.md"
    assert path.exists(), "agents/design-auditor.md not found"
    fm = _parse_frontmatter(path)
    missing = AGENT_REQUIRED_KEYS - fm.keys()
    assert not missing, f"design-auditor.md missing frontmatter keys: {missing}"


def test_design_auditor_has_self_review():
    path = AGENT_DIR / "design-auditor.md"
    content = path.read_text(encoding="utf-8")
    assert "Self-Review" in content, (
        "agents/design-auditor.md does not contain Self-Review section"
    )


def test_design_auditor_checks_accessibility():
    path = AGENT_DIR / "design-auditor.md"
    content = path.read_text(encoding="utf-8")
    assert "Accessibility" in content or "accessibility" in content, (
        "agents/design-auditor.md does not check accessibility"
    )


# ── Test 59: a11y-auditor agent ──────────────────────────────────────


def test_a11y_auditor_agent_exists_and_has_required_frontmatter():
    path = AGENT_DIR / "a11y-auditor.md"
    assert path.exists(), "agents/a11y-auditor.md not found"
    fm = _parse_frontmatter(path)
    missing = AGENT_REQUIRED_KEYS - fm.keys()
    assert not missing, f"a11y-auditor.md missing frontmatter keys: {missing}"


def test_a11y_auditor_has_self_review():
    path = AGENT_DIR / "a11y-auditor.md"
    content = path.read_text(encoding="utf-8")
    assert "Self-Review" in content, (
        "agents/a11y-auditor.md does not contain Self-Review section"
    )


def test_a11y_auditor_covers_wcag():
    """A11y auditor should cover WCAG 2.1 criteria."""
    path = AGENT_DIR / "a11y-auditor.md"
    content = path.read_text(encoding="utf-8")
    assert "WCAG" in content, "agents/a11y-auditor.md does not mention WCAG"
    for criterion in ["Perceivable", "Operable", "Understandable", "Robust"]:
        assert criterion in content, (
            f"agents/a11y-auditor.md does not cover WCAG principle: {criterion}"
        )


# ── Test 60: review skill integrates design-auditor and a11y-auditor ─


def test_review_skill_invokes_design_auditor():
    """Review skill should invoke design-auditor subagent for UI issues."""
    path = SKILL_DIR / "review" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "design-auditor" in content, (
        "review SKILL.md does not invoke design-auditor subagent"
    )


def test_review_skill_invokes_a11y_auditor():
    """Review skill should invoke a11y-auditor subagent for UI issues."""
    path = SKILL_DIR / "review" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "a11y-auditor" in content, (
        "review SKILL.md does not invoke a11y-auditor subagent"
    )


def test_review_skill_outputs_design_audit():
    """Review skill should produce design_audit.md output."""
    path = SKILL_DIR / "review" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "design_audit.md" in content, (
        "review SKILL.md does not mention design_audit.md output"
    )


def test_review_skill_outputs_a11y_audit():
    """Review skill should produce a11y_audit.md output."""
    path = SKILL_DIR / "review" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "a11y_audit.md" in content, (
        "review SKILL.md does not mention a11y_audit.md output"
    )


def test_no_standalone_design_skills():
    """Standalone design skills should not exist (integrated into review)."""
    assert not (SKILL_DIR / "design-audit").exists(), "skills/design-audit should not exist"
    assert not (SKILL_DIR / "design-refactor").exists(), "skills/design-refactor should not exist"
    assert not (SKILL_DIR / "a11y-audit").exists(), "skills/a11y-audit should not exist"
    assert not (AGENT_DIR / "design-refactorer.md").exists(), "agents/design-refactorer.md should not exist"
