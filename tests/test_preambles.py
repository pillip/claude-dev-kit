import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from preambles import (
    SKILL_TIERS,
    generate_preamble,
    preamble_tier1,
    preamble_tier2,
    preamble_tier3,
)


class TestTier1:
    def test_contains_project_context(self):
        result = preamble_tier1("brainstorm")
        assert "Project Context Detection" in result

    def test_contains_behavioral_rules(self):
        result = preamble_tier1("brainstorm")
        assert "Behavioral Rules" in result

    def test_contains_contributor_mode(self):
        result = preamble_tier1("brainstorm")
        assert "Contributor Mode" in result

    def test_contains_skill_name(self):
        result = preamble_tier1("brainstorm")
        assert "brainstorm" in result

    def test_does_not_contain_tier2_sections(self):
        result = preamble_tier1("brainstorm")
        assert "Checkpoint Verification" not in result
        assert "Worktree Setup" not in result


class TestTier2:
    def test_contains_checkpoint_pattern(self):
        result = preamble_tier2("implement")
        assert "Checkpoint Verification Pattern" in result

    def test_contains_worktree_pattern(self):
        result = preamble_tier2("implement")
        assert "Worktree Setup Pattern" in result

    def test_contains_registry_pattern(self):
        result = preamble_tier2("implement")
        assert "Registry Update Pattern" in result

    def test_contains_self_review(self):
        result = preamble_tier2("implement")
        assert "Self-Review Requirements" in result

    def test_includes_tier1_sections(self):
        result = preamble_tier2("implement")
        assert "Project Context Detection" in result
        assert "Behavioral Rules" in result
        assert "Contributor Mode" in result

    def test_does_not_contain_tier3_sections(self):
        result = preamble_tier2("implement")
        assert "Parallel Management" not in result
        assert "Escalation and Retry" not in result


class TestTier3:
    def test_contains_parallel_rules(self):
        result = preamble_tier3("sprint")
        assert "Parallel Management Rules" in result

    def test_contains_escalation(self):
        result = preamble_tier3("sprint")
        assert "Escalation and Retry Logic" in result

    def test_includes_tier2_sections(self):
        result = preamble_tier3("sprint")
        assert "Checkpoint Verification Pattern" in result
        assert "Worktree Setup Pattern" in result
        assert "Self-Review Requirements" in result

    def test_includes_tier1_sections(self):
        result = preamble_tier3("sprint")
        assert "Project Context Detection" in result
        assert "Behavioral Rules" in result


class TestGeneratePreamble:
    def test_tier1_skills(self):
        for skill in ["brainstorm", "prd", "bizanalysis", "issue"]:
            result = generate_preamble(skill)
            assert "Checkpoint Verification" not in result

    def test_tier2_skills(self):
        for skill in ["implement", "review", "ship", "kickoff", "diagnose"]:
            result = generate_preamble(skill)
            assert "Checkpoint Verification Pattern" in result
            assert "Parallel Management" not in result

    def test_tier3_skills(self):
        result = generate_preamble("sprint")
        assert "Parallel Management Rules" in result
        assert "Escalation and Retry" in result

    def test_unknown_skill_defaults_to_tier1(self):
        result = generate_preamble("unknown_skill")
        assert "Project Context Detection" in result
        assert "Checkpoint Verification" not in result

    def test_all_registered_skills_have_tiers(self):
        expected_skills = {
            "brainstorm", "prd", "bizanalysis", "issue",
            "uiux", "mobile-uiux", "desktop-uiux", "testgen",
            "devops", "migrate", "refactor",
            "implement", "review", "ship", "kickoff", "diagnose",
            "sprint",
        }
        assert expected_skills == set(SKILL_TIERS.keys())
