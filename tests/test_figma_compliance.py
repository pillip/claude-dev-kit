"""Unit tests for scripts/verify_figma_compliance.py."""

from scripts.verify_figma_compliance import (
    check_compliance,
    color_matches,
    extract_border_radii,
    extract_border_widths,
    extract_box_shadows,
    extract_colors_from_source,
    extract_font_weights,
    extract_fonts_from_source,
    extract_letter_spacings,
    extract_line_heights,
    extract_opacities,
    extract_spacings_from_source,
    normalize_hex,
    value_close,
)


def _make_design_data(**overrides) -> dict:
    """Build a full design_data.json structure with all token types."""
    base = {
        "colors": ["#3B82F6", "#10B981", "#EF4444"],
        "text_styles": [
            {"font_family": "Inter", "font_weight": 400, "font_size_px": 16},
            {"font_family": "Inter", "font_weight": 700, "font_size_px": 24},
        ],
        "font_weights": [400, 700],
        "font_sizes": [16, 24],
        "line_heights": [1.5, 1.333],
        "letter_spacings": [0.03, -0.02],
        "spacings": [4, 8, 12, 16, 24, 32, 48],
        "border_radii": [4, 8, 12, 9999],
        "border_widths": [1, 2],
        "opacities": [0.5, 0.8],
        "shadows": [{"type": "box-shadow", "blur": 4, "color": "#000000"}],
    }
    base.update(overrides)
    return {"summary": base}


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
        colors = extract_colors_from_source("background: #3B82F6;")
        assert len(colors) == 1
        assert colors[0]["value"] == "#3B82F6"

    def test_rgb_color(self):
        colors = extract_colors_from_source("color: rgb(59, 130, 246);")
        assert len(colors) == 1

    def test_skips_css_variable_definition(self):
        assert extract_colors_from_source("  --color-primary: #3B82F6;") == []

    def test_skips_comments(self):
        assert extract_colors_from_source("// color: #FF0000;") == []

    def test_multiple_colors(self):
        assert len(extract_colors_from_source("border: #EF4444;\nbg: #10B981;")) == 2


# ── TestExtractFonts ────────────────────────────────────────────────


class TestExtractFonts:
    def test_css_font_family(self):
        families, _ = extract_fonts_from_source("font-family: 'Inter';")
        assert len(families) == 1

    def test_css_font_size(self):
        _, sizes = extract_fonts_from_source("font-size: 16px;")
        assert sizes[0]["value"] == 16.0

    def test_rn_font_family(self):
        families, _ = extract_fonts_from_source("fontFamily: 'Inter'")
        assert len(families) == 1

    def test_rn_font_size(self):
        _, sizes = extract_fonts_from_source("fontSize: 24")
        assert sizes[0]["value"] == 24.0


# ── TestExtractNewProperties ────────────────────────────────────────


class TestExtractFontWeights:
    def test_css(self):
        result = extract_font_weights("font-weight: 700;")
        assert result[0]["value"] == 700

    def test_rn(self):
        result = extract_font_weights("fontWeight: '400'")
        assert result[0]["value"] == 400


class TestExtractLineHeights:
    def test_css(self):
        result = extract_line_heights("line-height: 1.5;")
        assert result[0]["value"] == 1.5

    def test_rn(self):
        result = extract_line_heights("lineHeight: 24")
        assert result[0]["value"] == 24.0


class TestExtractLetterSpacings:
    def test_css_em(self):
        result = extract_letter_spacings("letter-spacing: 0.03em;")
        assert result[0]["value"] == 0.03

    def test_css_px(self):
        result = extract_letter_spacings("letter-spacing: 0.5px;")
        assert result[0]["value"] == 0.5

    def test_rn(self):
        result = extract_letter_spacings("letterSpacing: 0.5")
        assert result[0]["value"] == 0.5


class TestExtractBorderRadii:
    def test_css(self):
        result = extract_border_radii("border-radius: 8px;")
        assert result[0]["value"] == 8.0

    def test_rn(self):
        result = extract_border_radii("borderRadius: 12")
        assert result[0]["value"] == 12.0


class TestExtractBorderWidths:
    def test_css(self):
        result = extract_border_widths("border-width: 1px;")
        assert result[0]["value"] == 1.0

    def test_zero_ignored(self):
        assert extract_border_widths("border-width: 0px;") == []


class TestExtractOpacities:
    def test_decimal(self):
        result = extract_opacities("opacity: 0.5;")
        assert result[0]["value"] == 0.5

    def test_zero_and_one_ignored(self):
        assert extract_opacities("opacity: 0;") == []
        assert extract_opacities("opacity: 1;") == []


class TestExtractBoxShadows:
    def test_box_shadow(self):
        result = extract_box_shadows("box-shadow: 0 2px 4px rgba(0,0,0,0.1);")
        assert len(result) == 1

    def test_none_ignored(self):
        assert extract_box_shadows("box-shadow: none;") == []


# ── TestExtractSpacings ─────────────────────────────────────────────


class TestExtractSpacings:
    def test_padding(self):
        spacings = extract_spacings_from_source("padding: 16px;")
        assert len(spacings) == 1
        assert spacings[0]["value"] == 16.0

    def test_gap(self):
        spacings = extract_spacings_from_source("gap: 12px;")
        assert len(spacings) == 1

    def test_zero_ignored(self):
        assert extract_spacings_from_source("margin: 0px;") == []


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


# ── TestCheckCompliance (full property coverage) ────────────────────


class TestCheckCompliance:
    def test_fully_compliant(self):
        design = _make_design_data()
        src = "background: #3B82F6;\nfont-size: 16px;\nfont-weight: 700;\nline-height: 1.5;\nborder-radius: 8px;\npadding: 8px;\nopacity: 0.5;"
        result = check_compliance(design, [("app.css", src)])
        assert result["compliant"] is True

    def test_color_violation(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "background: #FF9900;")])
        assert result["compliant"] is False
        assert result["summary"]["color_count"] > 0

    def test_font_family_violation(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "font-family: 'Comic Sans MS';")])
        assert result["compliant"] is False
        assert result["summary"]["font_family_count"] > 0

    def test_font_size_violation(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "font-size: 99px;")])
        assert result["compliant"] is False
        assert result["summary"]["font_size_count"] > 0

    def test_font_weight_violation(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "font-weight: 300;")])
        assert result["compliant"] is False
        assert result["summary"]["font_weight_count"] > 0

    def test_line_height_violation(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "line-height: 2.5;")])
        assert result["compliant"] is False
        assert result["summary"]["line_height_count"] > 0

    def test_letter_spacing_violation(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "letter-spacing: 0.5em;")])
        assert result["compliant"] is False
        assert result["summary"]["letter_spacing_count"] > 0

    def test_spacing_violation(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "padding: 20px;")])
        assert result["compliant"] is False
        assert result["summary"]["spacing_count"] > 0

    def test_border_radius_violation(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "border-radius: 99px;")])
        assert result["compliant"] is False
        assert result["summary"]["border_radius_count"] > 0

    def test_border_width_violation(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "border-width: 5px;")])
        assert result["compliant"] is False
        assert result["summary"]["border_width_count"] > 0

    def test_opacity_violation(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "opacity: 0.3;")])
        assert result["compliant"] is False
        assert result["summary"]["opacity_count"] > 0

    def test_box_shadow_without_figma_shadows(self):
        design = _make_design_data(shadows=[])
        result = check_compliance(design, [("a.css", "box-shadow: 0 2px 4px #000;")])
        assert result["compliant"] is False
        assert result["summary"]["box_shadow_count"] > 0

    def test_box_shadow_allowed_when_figma_has_shadows(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "box-shadow: 0 2px 4px #000;")])
        # box_shadow should not be flagged since Figma has shadows
        assert result["summary"]["box_shadow_count"] == 0

    def test_css_var_definitions_ignored(self):
        design = _make_design_data()
        result = check_compliance(design, [("t.css", "  --color-primary: #FF9900;")])
        assert result["compliant"] is True

    def test_generic_fonts_ignored(self):
        design = _make_design_data()
        result = check_compliance(design, [("a.css", "font-family: sans-serif;")])
        assert result["compliant"] is True

    def test_no_figma_data_is_compliant(self):
        design = {"summary": {}}
        result = check_compliance(design, [("a.css", "background: #FF9900; font-size: 99px;")])
        assert result["compliant"] is True
