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
        # CHECKPOINT_CMD now delegates to the checkpoint.sh wrapper, which
        # resolves the main repo root internally and runs verify_checkpoint.py.
        result = RESOLVERS["CHECKPOINT_CMD"]("implement")
        assert "bash scripts/checkpoint.sh" in result

    def test_worktree_setup_returns_string(self):
        # WORKTREE_SETUP now delegates to the wt_setup.sh wrapper, which
        # wraps `worktree.sh create` + the auto-freeze marker in one step.
        result = RESOLVERS["WORKTREE_SETUP"]("implement")
        assert "bash scripts/wt_setup.sh" in result

    def test_worktree_cleanup_returns_string(self):
        # WORKTREE_CLEANUP delegates to wt_cleanup.sh, which cd's to the
        # main root inside a subshell before running `worktree.sh remove`.
        result = RESOLVERS["WORKTREE_CLEANUP"]("implement")
        assert "bash scripts/wt_cleanup.sh" in result

    def test_registry_update_returns_string(self):
        # REGISTRY_UPDATE now delegates to registry_edit.sh, which resolves
        # the main repo root internally and wraps flock_edit.sh for concurrent-safe writes.
        result = RESOLVERS["REGISTRY_UPDATE"]("implement")
        assert "bash scripts/registry_edit.sh" in result


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

    def test_dry_run_detects_stale(self, tmp_path, monkeypatch, capsys):
        """Tampering with a generated SKILL.md should make dry_run return False.

        Runs against an isolated fake skills/ tree inside tmp_path so the
        real project files are never touched. A previous version of this
        test wrote ``"tampered content"`` directly to the first skill's
        SKILL.md (alphabetically ``skills/bizanalysis/SKILL.md``) and
        restored it in a ``finally`` block — if the test was interrupted
        before ``finally`` ran, the real source file was left corrupted.
        """
        import gen_skills

        # Build a fake kit layout: <tmp>/skills/fake-skill/SKILL.md.tmpl
        fake_kit_root = tmp_path
        fake_skills = fake_kit_root / "skills"
        fake_skill_dir = fake_skills / "fake-skill"
        fake_skill_dir.mkdir(parents=True)

        tmpl = fake_skill_dir / "SKILL.md.tmpl"
        tmpl.write_text(
            "---\nname: fake-skill\ndescription: test\n---\n\nHello world.\n",
            encoding="utf-8",
        )

        # Point gen_skills module-level globals at the fake tree
        monkeypatch.setattr(gen_skills, "KIT_ROOT", fake_kit_root)
        monkeypatch.setattr(gen_skills, "SKILLS_DIR", fake_skills)

        # Generate fresh content from the fake template
        gen_skills.generate_all()

        # Sanity check: dry_run should now report fresh against the fake tree
        assert gen_skills.dry_run() is True

        # Tamper with the generated file inside the fake tree only
        out = fake_skill_dir / "SKILL.md"
        assert out.exists(), "generate_all should have produced SKILL.md"
        out.write_text("tampered content", encoding="utf-8")

        # dry_run should now detect the mismatch
        assert gen_skills.dry_run() is False

        # Drain captured stdout/stderr so it doesn't pollute test output
        capsys.readouterr()


class TestReport:
    def test_report_runs(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "gen_skills.py"), "--report"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "TOTAL" in result.stdout
