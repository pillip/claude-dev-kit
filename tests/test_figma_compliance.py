"""Unit tests for scripts/verify_figma_compliance.py."""

from scripts.verify_figma_compliance import (
    check_compliance,
    color_matches,
    extract_colors_from_source,
    extract_fonts_from_source,
    extract_spacings_from_source,
    normalize_hex,
    value_close,
)


def _make_design_data(
    colors: list[str] | None = None,
    text_styles: list[dict] | None = None,
    spacings: list[int] | None = None,
) -> dict:
    """Build a minimal design_data.json structure."""
    return {
        "summary": {
            "colors": colors or ["#3B82F6", "#10B981", "#EF4444"],
            "text_styles": text_styles or [
                {"font_family": "Inter", "font_weight": 400, "font_size_px": 16},
                {"font_family": "Inter", "font_weight": 700, "font_size_px": 24},
            ],
            "spacings": spacings or [4, 8, 12, 16, 24, 32, 48],
        },
    }


# ── TestNormalizeHex ────────────────────────────────────────────────


class TestNormalizeHex:
    def test_six_digit(self):
        assert normalize_hex("#3b82f6") == "#3B82F6"

    def test_three_digit(self):
        assert normalize_hex("#fff") == "#FFFFFF"

    def test_already_uppercase(self):
        assert normalize_hex("#3B82F6") == "#3B82F6"


# ── TestExtractColors ───────────────────────────────────────────────


class TestExtractColors:
    def test_hex_color(self):
        src = "background: #3B82F6;"
        colors = extract_colors_from_source(src)
        assert len(colors) == 1
        assert colors[0]["value"] == "#3B82F6"
        assert colors[0]["line"] == 1

    def test_rgb_color(self):
        src = "color: rgb(59, 130, 246);"
        colors = extract_colors_from_source(src)
        assert len(colors) == 1

    def test_skips_css_variable_definition(self):
        src = "  --color-primary: #3B82F6;"
        colors = extract_colors_from_source(src)
        assert len(colors) == 0

    def test_skips_comments(self):
        src = "// color: #FF0000;\n/* background: #00FF00; */"
        colors = extract_colors_from_source(src)
        assert len(colors) == 0

    def test_multiple_colors(self):
        src = "border: 1px solid #EF4444;\nbackground: #10B981;"
        colors = extract_colors_from_source(src)
        assert len(colors) == 2


# ── TestExtractFonts ────────────────────────────────────────────────


class TestExtractFonts:
    def test_css_font_family(self):
        src = "font-family: 'Inter';"
        families, _ = extract_fonts_from_source(src)
        assert len(families) == 1
        assert "Inter" in families[0]["value"]

    def test_css_font_size(self):
        src = "font-size: 16px;"
        _, sizes = extract_fonts_from_source(src)
        assert len(sizes) == 1
        assert sizes[0]["value"] == 16.0

    def test_rn_font_family(self):
        src = "fontFamily: 'Inter'"
        families, _ = extract_fonts_from_source(src)
        assert len(families) == 1

    def test_rn_font_size(self):
        src = "fontSize: 24"
        _, sizes = extract_fonts_from_source(src)
        assert len(sizes) == 1
        assert sizes[0]["value"] == 24.0


# ── TestExtractSpacings ─────────────────────────────────────────────


class TestExtractSpacings:
    def test_padding(self):
        src = "padding: 16px;"
        spacings = extract_spacings_from_source(src)
        assert len(spacings) == 1
        assert spacings[0]["value"] == 16.0

    def test_margin(self):
        src = "margin-top: 8px;"
        spacings = extract_spacings_from_source(src)
        assert len(spacings) == 1

    def test_gap(self):
        src = "gap: 12px;"
        spacings = extract_spacings_from_source(src)
        assert len(spacings) == 1

    def test_zero_ignored(self):
        src = "margin: 0px;"
        spacings = extract_spacings_from_source(src)
        assert len(spacings) == 0


# ── TestColorMatches ────────────────────────────────────────────────


class TestColorMatches:
    def test_exact_match(self):
        assert color_matches("#3B82F6", {"#3B82F6"}) is True

    def test_case_insensitive(self):
        assert color_matches("#3b82f6", {"#3B82F6"}) is True

    def test_no_match(self):
        assert color_matches("#FF0000", {"#3B82F6", "#10B981"}) is False

    def test_common_colors_pass(self):
        assert color_matches("#000000", set()) is True
        assert color_matches("#FFFFFF", set()) is True

    def test_close_match_within_tolerance(self):
        # #3B82F6 vs #3B83F5 — very close
        assert color_matches("#3B83F5", {"#3B82F6"}) is True

    def test_distant_color_fails(self):
        assert color_matches("#FF0000", {"#3B82F6"}) is False


# ── TestValueClose ──────────────────────────────────────────────────


class TestValueClose:
    def test_exact(self):
        assert value_close(16, {16, 24, 32}) is True

    def test_within_tolerance(self):
        assert value_close(17, {16, 24, 32}) is True

    def test_outside_tolerance(self):
        assert value_close(20, {16, 24, 32}) is False


# ── TestCheckCompliance ─────────────────────────────────────────────


class TestCheckCompliance:
    def test_compliant_code(self):
        design = _make_design_data()
        src = "background: #3B82F6;\nfont-size: 16px;\npadding: 8px;"
        result = check_compliance(design, [("app.css", src)])
        assert result["compliant"] is True
        assert result["summary"]["total_violations"] == 0

    def test_color_violation(self):
        design = _make_design_data()
        src = "background: #FF9900;"
        result = check_compliance(design, [("app.css", src)])
        assert result["compliant"] is False
        assert result["summary"]["color_violation_count"] > 0

    def test_font_violation(self):
        design = _make_design_data()
        src = "font-family: 'Comic Sans MS';"
        result = check_compliance(design, [("app.css", src)])
        assert result["compliant"] is False
        assert result["summary"]["font_violation_count"] > 0

    def test_spacing_violation(self):
        design = _make_design_data()
        src = "padding: 20px;"  # Not close to any of [4, 8, 12, 16, 24, 32, 48]
        result = check_compliance(design, [("app.css", src)])
        assert result["compliant"] is False
        assert result["summary"]["spacing_violation_count"] > 0

    def test_css_var_definitions_ignored(self):
        design = _make_design_data()
        src = "  --color-primary: #FF9900;\nbackground: var(--color-primary);"
        result = check_compliance(design, [("tokens.css", src)])
        assert result["compliant"] is True

    def test_generic_fonts_ignored(self):
        design = _make_design_data()
        src = "font-family: sans-serif;"
        result = check_compliance(design, [("app.css", src)])
        assert result["compliant"] is True

    def test_no_figma_data_is_compliant(self):
        design = {"summary": {}}
        src = "background: #FF9900; font-size: 99px; padding: 99px;"
        result = check_compliance(design, [("app.css", src)])
        assert result["compliant"] is True

    def test_multiple_files(self):
        design = _make_design_data()
        files = [
            ("a.css", "background: #3B82F6;"),
            ("b.css", "background: #FF9900;"),
        ]
        result = check_compliance(design, files)
        assert result["compliant"] is False
        assert result["summary"]["files_checked"] == 2
