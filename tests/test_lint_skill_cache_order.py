import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lint_skill_cache_order import check_template  # noqa: E402


def _write_tmpl(content: str) -> Path:
    fd, path = tempfile.mkstemp(suffix=".tmpl")
    import os
    os.close(fd)
    p = Path(path)
    p.write_text(content, encoding="utf-8")
    return p


class TestCacheOrderLint:
    def test_valid_placement_passes(self):
        tmpl = _write_tmpl(
            "---\n"
            "name: x\n"
            "description: y\n"
            "---\n"
            "\n"
            "{{PREAMBLE}}\n"
            "Steps:\n"
        )
        ok, msg = check_template(tmpl)
        assert ok, f"Expected pass, got: {msg}"

    def test_preamble_missing_fails(self):
        tmpl = _write_tmpl(
            "---\n"
            "name: x\n"
            "---\n"
            "\n"
            "Steps:\n"
        )
        ok, msg = check_template(tmpl)
        assert not ok
        assert "{{PREAMBLE}}" in msg

    def test_preamble_mid_template_fails_with_line_number(self):
        tmpl = _write_tmpl(
            "---\n"          # line 1
            "name: x\n"      # line 2
            "---\n"          # line 3
            "\n"             # line 4
            "Intro line.\n"  # line 5  <- offending
            "{{PREAMBLE}}\n" # line 6
            "Steps:\n"       # line 7
        )
        ok, msg = check_template(tmpl)
        assert not ok
        assert ":5:" in msg, f"Expected line 5 in message, got: {msg}"
        assert "Intro line." in msg

    def test_missing_opening_frontmatter_fails(self):
        tmpl = _write_tmpl("name: x\n{{PREAMBLE}}\nSteps:\n")
        ok, msg = check_template(tmpl)
        assert not ok
        assert "missing opening" in msg

    def test_missing_closing_frontmatter_fails(self):
        tmpl = _write_tmpl("---\nname: x\n{{PREAMBLE}}\nSteps:\n")
        ok, msg = check_template(tmpl)
        assert not ok
        assert "missing closing" in msg

    def test_html_comment_after_frontmatter_is_skipped(self):
        # gen_skills.py prepends an HTML AUTO-GENERATED comment to the rendered
        # SKILL.md (not the .tmpl), but a contributor might add an HTML comment
        # in the template. The lint should skip HTML comment lines before
        # looking for PREAMBLE.
        tmpl = _write_tmpl(
            "---\n"
            "name: x\n"
            "---\n"
            "<!-- internal note -->\n"
            "{{PREAMBLE}}\n"
            "Steps:\n"
        )
        ok, msg = check_template(tmpl)
        assert ok, f"Expected pass, got: {msg}"


class TestAllCurrentTemplatesPass:
    """Regression guard: every current skill template (core + packs) must
    satisfy the cache-order rule. If this test fails after a template edit,
    the edit broke cache-friendliness — fix the template, not this test.
    """

    def test_every_current_template_passes(self):
        from gen_skills import discover_templates

        templates = discover_templates()
        assert templates, "discover_templates() returned no templates"

        failures: list[str] = []
        for tmpl in templates:
            ok, msg = check_template(tmpl)
            if not ok:
                failures.append(msg)

        assert not failures, (
            "Cache-order lint failed on current templates:\n  "
            + "\n  ".join(failures)
        )
