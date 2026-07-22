"""Tests for the /scan skill — template generation, frontmatter, and tier registration."""

import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from gen_skills import discover_templates, extract_skill_name, output_path, process_template
from preambles import SKILL_TIERS, generate_preamble


class TestScanTierRegistration:
    def test_scan_in_skill_tiers(self):
        assert "scan" in SKILL_TIERS

    def test_scan_is_tier1(self):
        assert SKILL_TIERS["scan"] == 1

    def test_scan_preamble_is_tier1(self):
        result = generate_preamble("scan")
        assert "Project Context Detection" in result
        assert "Behavioral Rules" in result
        # Tier 1 should NOT have Tier 2 sections
        assert "Checkpoint Verification Pattern" not in result
        assert "Worktree Setup Pattern" not in result


class TestScanTemplate:
    def _find_scan_template(self):
        for tmpl in discover_templates():
            if extract_skill_name(tmpl) == "scan":
                return tmpl
        return None

    def test_scan_template_exists(self):
        tmpl = self._find_scan_template()
        assert tmpl is not None, "skills/scan/SKILL.md.tmpl not found"

    def test_scan_template_generates_skill_md(self):
        tmpl = self._find_scan_template()
        assert tmpl is not None
        content = process_template(tmpl)
        # Header sits below the frontmatter block (ISSUE-035: frontmatter must
        # start at byte 0 or Claude Code drops it).
        assert "<!-- AUTO-GENERATED" in content
        assert content.startswith("---\n")

    def test_no_unresolved_placeholders(self):
        tmpl = self._find_scan_template()
        assert tmpl is not None
        content = process_template(tmpl)
        remaining = re.findall(r"\{\{(\w+)\}\}", content)
        assert not remaining, f"Unresolved placeholders: {remaining}"

    def test_frontmatter_valid(self):
        tmpl = self._find_scan_template()
        assert tmpl is not None
        content = process_template(tmpl)
        # Extract frontmatter between --- markers (skip auto-gen header)
        lines = content.split("\n")
        # Find first and second --- lines
        dash_indices = [i for i, line in enumerate(lines) if line.strip() == "---"]
        assert len(dash_indices) >= 2, "Missing frontmatter delimiters"
        frontmatter = "\n".join(lines[dash_indices[0] + 1 : dash_indices[1]])
        assert "name: scan" in frontmatter
        assert "description:" in frontmatter
        assert "allowed-tools:" in frontmatter

    def test_frontmatter_has_required_tools(self):
        tmpl = self._find_scan_template()
        assert tmpl is not None
        content = process_template(tmpl)
        # Check allowed-tools line contains expected tools
        for tool in ["Task", "Read", "Glob", "Grep", "Write", "Edit"]:
            assert tool in content, f"Missing tool '{tool}' in SKILL.md"

    def test_algorithm_phases_present(self):
        tmpl = self._find_scan_template()
        assert tmpl is not None
        content = process_template(tmpl)
        assert "Phase 1" in content
        assert "Phase 2" in content
        assert "Phase 3" in content
        assert "Phase 4" in content

    def test_subagent_references(self):
        tmpl = self._find_scan_template()
        assert tmpl is not None
        content = process_template(tmpl)
        assert "codebase-scanner" in content
        assert "scan-analyst" in content
        assert "scan-architect" in content
        assert "scan-qa-designer" in content
        assert "scan-data-modeler" in content
        assert "scan-planner" in content

    def test_issues_md_in_output(self):
        tmpl = self._find_scan_template()
        assert tmpl is not None
        content = process_template(tmpl)
        assert "issues.md" in content

    def test_confidence_tagging_mentioned(self):
        tmpl = self._find_scan_template()
        assert tmpl is not None
        content = process_template(tmpl)
        assert "[CONFIRMED]" in content
        assert "[INFERRED]" in content


class TestScanAgentsExist:
    """Verify all scan-related agent files exist."""

    AGENTS_DIR = KIT_ROOT / "agents"

    def test_codebase_scanner_exists(self):
        assert (self.AGENTS_DIR / "codebase-scanner.md").is_file()

    def test_scan_architect_exists(self):
        assert (self.AGENTS_DIR / "scan-architect.md").is_file()

    def test_scan_analyst_exists(self):
        assert (self.AGENTS_DIR / "scan-analyst.md").is_file()

    def test_scan_qa_designer_exists(self):
        assert (self.AGENTS_DIR / "scan-qa-designer.md").is_file()

    def test_scan_data_modeler_exists(self):
        assert (self.AGENTS_DIR / "scan-data-modeler.md").is_file()

    def test_scan_planner_exists(self):
        assert (self.AGENTS_DIR / "scan-planner.md").is_file()

    def test_ux_designer_exists(self):
        assert (self.AGENTS_DIR / "ux-designer.md").is_file()
