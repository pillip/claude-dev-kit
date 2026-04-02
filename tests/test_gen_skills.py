import subprocess
import sys
import tempfile
from pathlib import Path

# Add scripts/ to path for imports
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from gen_skills import (
    RESOLVERS,
    discover_templates,
    extract_skill_name,
    output_path,
    process_template,
)


class TestDiscovery:
    def test_finds_all_templates(self):
        templates = discover_templates()
        assert len(templates) >= 18

    def test_all_templates_have_skill_name(self):
        for tmpl in discover_templates():
            name = extract_skill_name(tmpl)
            assert name, f"Empty skill name for {tmpl}"

    def test_output_path_is_sibling(self):
        for tmpl in discover_templates():
            out = output_path(tmpl)
            assert out.parent == tmpl.parent
            assert out.name == "SKILL.md"


class TestResolvers:
    def test_all_resolvers_are_callable(self):
        for name, resolver in RESOLVERS.items():
            assert callable(resolver), f"Resolver {name} is not callable"

    def test_preamble_returns_string(self):
        result = RESOLVERS["PREAMBLE"]("brainstorm")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_checkpoint_cmd_returns_string(self):
        result = RESOLVERS["CHECKPOINT_CMD"]("implement")
        assert "verify_checkpoint.py" in result

    def test_worktree_setup_returns_string(self):
        result = RESOLVERS["WORKTREE_SETUP"]("implement")
        assert "worktree.sh create" in result

    def test_registry_update_returns_string(self):
        result = RESOLVERS["REGISTRY_UPDATE"]("implement")
        assert "flock_edit.sh" in result


class TestProcessTemplate:
    def test_generated_header_present(self):
        templates = discover_templates()
        assert templates, "No templates found"
        content = process_template(templates[0])
        assert content.startswith("<!-- AUTO-GENERATED")

    def test_no_unresolved_placeholders(self):
        import re

        for tmpl in discover_templates():
            content = process_template(tmpl)
            remaining = re.findall(r"\{\{(\w+)\}\}", content)
            assert not remaining, (
                f"Unresolved placeholders in {tmpl}: {remaining}"
            )

    def test_frontmatter_preserved(self):
        for tmpl in discover_templates():
            content = process_template(tmpl)
            # Should have opening and closing ---
            assert "---\n" in content
            parts = content.split("---", 2)
            assert len(parts) >= 3, f"Missing frontmatter in {tmpl}"

    def test_unknown_placeholder_raises(self):
        """A template with an unknown placeholder should raise ValueError."""
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tmpl", dir="/tmp", delete=False
        ) as f:
            f.write("---\nname: test\n---\n{{UNKNOWN_TOKEN}}\n")
            f.flush()
            tmpl_path = Path(f.name)

        try:
            process_template(tmpl_path)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "UNKNOWN_TOKEN" in str(e)
        finally:
            tmpl_path.unlink()


class TestDryRun:
    def test_dry_run_passes_when_fresh(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "gen_skills.py"), "--dry-run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_dry_run_detects_stale(self):
        # Tamper with a generated file
        templates = discover_templates()
        out = output_path(templates[0])
        original = out.read_text()
        try:
            out.write_text("tampered content")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "gen_skills.py"), "--dry-run"],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 1
            assert "stale" in result.stderr.lower() or "missing" in result.stderr.lower()
        finally:
            out.write_text(original)


class TestReport:
    def test_report_runs(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "gen_skills.py"), "--report"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "TOTAL" in result.stdout
