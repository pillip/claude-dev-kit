"""Characterization tests for the Figma visual-diff verification family.

Covers the pure comparison / generation logic of:
  - scripts/verify_visual_diff.py       (diff-threshold math + pixel diff)
  - scripts/verify_computed_styles.py   (token vs computed-style comparison)
  - scripts/verify_structural_match.py  (element presence vs design_data)
  - scripts/verify_layout.py            (spatial-relationship assertions)
  - scripts/generate_figma_css.py       (CSS output from design data)

The DEFAULT suite runs WITHOUT launching Chromium or touching the network:
browser/screenshot boundaries are mocked, and a subprocess guard proves that
importing the browser-dependent scripts triggers no playwright import.

Threshold semantics are load-bearing and are asserted directly so silent drift
becomes a test failure: 1% same-renderer (DEFAULT_THRESHOLD) and 5% Figma-PNG
cross-renderer fallback.
"""

from __future__ import annotations

import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

from scripts import generate_figma_css as gfc
from scripts import verify_computed_styles as vcs
from scripts import verify_layout as vl
from scripts import verify_structural_match as vsm
from scripts import verify_visual_diff as vvd

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "figma" / "design_data.json"

# Snapshot taken when THIS test module is first imported (i.e. at collection
# time on the default path). If any script or test triggered a browser import
# during collection, playwright would already be in sys.modules here.
_PLAYWRIGHT_IMPORTED_AT_COLLECTION = any(
    m == "playwright" or m.startswith("playwright.") for m in sys.modules
)


@pytest.fixture(scope="module")
def design_data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ── Synthetic PNG helper (stdlib only — no Pillow required) ──────────


def _png_bytes(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    """Encode a solid-color RGBA PNG using only zlib + struct."""

    def _chunk(typ: bytes, data: bytes) -> bytes:
        body = typ + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    row = b"\x00" + bytes(rgba) * width  # filter byte 0 + pixels
    raw = row * height
    idat = zlib.compress(raw)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


# ════════════════════════════════════════════════════════════════════
# No-browser / no-network guarantee
# ════════════════════════════════════════════════════════════════════


class TestNoBrowserAtCollection:
    def test_playwright_not_imported_at_collection(self):
        assert _PLAYWRIGHT_IMPORTED_AT_COLLECTION is False
        assert not any(m.startswith("playwright") for m in sys.modules)

    def test_importing_browser_scripts_does_not_import_playwright(self):
        # Isolated subprocess so the assertion is immune to suite pollution:
        # importing these modules must not pull in playwright (lazy imports only).
        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys;"
            "import scripts.verify_visual_diff, scripts.verify_computed_styles;"
            "assert not any(m.startswith('playwright') for m in sys.modules), sorted(sys.modules);"
            "print('clean')"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        assert "clean" in proc.stdout


# ════════════════════════════════════════════════════════════════════
# verify_visual_diff — threshold math + pixel diff
# ════════════════════════════════════════════════════════════════════


class TestVisualDiffThresholds:
    def test_same_renderer_threshold_is_one_percent(self):
        # 1% same-renderer precision target. Drift here should fail the suite.
        assert vvd.DEFAULT_THRESHOLD == 1.0

    def test_main_same_renderer_uses_one_percent(self, tmp_path, monkeypatch):
        # A prototype exists → same-renderer path → visual_diff called at 1.0.
        fig = tmp_path / "figma-export"
        fig.mkdir(parents=True)
        (fig / "design_data.json").write_text(FIXTURE.read_text(), encoding="utf-8")
        proto = tmp_path / "prototype" / "screens"
        proto.mkdir(parents=True)
        (proto / "home.html").write_text("<html></html>", encoding="utf-8")

        captured = {}

        def _fake_visual_diff(proto_path, impl_path, viewports, threshold, output_dir):
            captured["threshold"] = threshold
            return {"results": [], "all_pass": True, "viewports_tested": 0}

        monkeypatch.setattr(vvd, "_check_playwright", lambda: True)
        monkeypatch.setattr(vvd, "visual_diff", _fake_visual_diff)

        rc = vvd.main([
            "--project-path", str(tmp_path),
            "--implementation", str(tmp_path / "impl.html"),
        ])
        assert rc == 0
        assert captured["threshold"] == 1.0

    def test_main_figma_render_fallback_uses_five_percent(self, tmp_path, monkeypatch):
        # No prototype, but Figma render PNGs exist → cross-renderer fallback at 5%.
        fig = tmp_path / "figma-export"
        renders = fig / "renders"
        renders.mkdir(parents=True)
        (fig / "design_data.json").write_text(FIXTURE.read_text(), encoding="utf-8")
        (renders / "home@2x.png").write_bytes(_png_bytes(4, 4, (0, 0, 0, 255)))

        captured = {}

        def _fake_against_renders(impl_path, figma_renders, threshold, output_dir):
            captured["threshold"] = threshold
            return {"results": [], "all_pass": True, "viewports_tested": 0, "source": "figma-render"}

        monkeypatch.setattr(vvd, "_check_playwright", lambda: True)
        monkeypatch.setattr(vvd, "visual_diff_against_renders", _fake_against_renders)

        rc = vvd.main([
            "--project-path", str(tmp_path),
            "--implementation", str(tmp_path / "impl.html"),
        ])
        assert rc == 0
        assert captured["threshold"] == 5.0


class TestPixelDiff:
    def test_identical_images_report_zero_diff(self):
        png = _png_bytes(4, 4, (255, 0, 0, 255))
        result = vvd._pixel_diff(png, png)
        assert result["diff_percent"] == 0.0
        assert result["diff_pixels"] == 0

    def test_different_images_report_nonzero_diff(self):
        black = _png_bytes(4, 4, (0, 0, 0, 255))
        white = _png_bytes(4, 4, (255, 255, 255, 255))
        result = vvd._pixel_diff(black, white)
        assert result["diff_percent"] > 0
        assert result["total_pixels"] > 0

    def test_color_distance_sq_is_squared_euclidean(self):
        assert vvd._color_distance_sq((0, 0, 0), (0, 0, 0)) == 0
        assert vvd._color_distance_sq((0, 0, 0), (1, 2, 2)) == 1 + 4 + 4

    def test_isolated_pixel_is_not_flagged_antialiased(self):
        # Uniform same-image neighbors (none differ) AND wholly-different other
        # image (none similar) → neither AA condition met → not anti-aliased.
        same = {(x, y): (10, 10, 10) for x in range(3) for y in range(3)}
        other = {(x, y): (200, 200, 200) for x in range(3) for y in range(3)}
        threshold_sq = 20 * 20 * 3
        assert vvd._is_antialiased(same, 1, 1, 3, 3, other, threshold_sq) is False

    def test_edge_pixel_is_flagged_antialiased(self):
        # Center differs sharply from >=2 same-image neighbors → edge → AA.
        same = {(x, y): (10, 10, 10) for x in range(3) for y in range(3)}
        for y in range(3):
            same[(2, y)] = (255, 255, 255)
        other = {(x, y): (200, 200, 200) for x in range(3) for y in range(3)}
        threshold_sq = 20 * 20 * 3
        assert vvd._is_antialiased(same, 1, 1, 3, 3, other, threshold_sq) is True


class TestVisualDiffOrchestration:
    def _shots(self, png):
        return [{"viewport_name": "desktop", "width": 1440, "height": 900, "screenshot": png}]

    def test_passes_at_exactly_threshold(self, monkeypatch):
        png = _png_bytes(4, 4, (0, 0, 0, 255))
        monkeypatch.setattr(vvd, "take_screenshots", lambda target, vp=None: self._shots(png))
        monkeypatch.setattr(vvd, "_pixel_diff", lambda a, b, out=None: {
            "diff_percent": 1.0, "total_pixels": 16, "diff_pixels": 0, "aa_aware": True})
        result = vvd.visual_diff("proto.html", "impl.html", threshold=1.0)
        assert result["all_pass"] is True
        assert result["results"][0]["threshold"] == 1.0

    def test_fails_above_threshold(self, monkeypatch):
        png = _png_bytes(4, 4, (0, 0, 0, 255))
        monkeypatch.setattr(vvd, "take_screenshots", lambda target, vp=None: self._shots(png))
        monkeypatch.setattr(vvd, "_pixel_diff", lambda a, b, out=None: {
            "diff_percent": 1.5, "total_pixels": 16, "diff_pixels": 1, "aa_aware": True})
        result = vvd.visual_diff("proto.html", "impl.html", threshold=1.0)
        assert result["all_pass"] is False


class TestVisualDiffDiscovery:
    def test_find_figma_renders_reads_render_pngs(self, tmp_path):
        renders = tmp_path / "figma-export" / "renders"
        renders.mkdir(parents=True)
        (renders / "home@2x.png").write_bytes(_png_bytes(4, 4, (1, 2, 3, 255)))
        found = vvd.find_figma_renders(tmp_path)
        assert len(found) == 1
        assert found[0]["name"] == "home"

    def test_find_figma_renders_absent_dir_returns_empty(self, tmp_path):
        assert vvd.find_figma_renders(tmp_path) == []

    def test_find_prototype_html_locates_screen(self, tmp_path):
        screens = tmp_path / "prototype" / "screens"
        screens.mkdir(parents=True)
        target = screens / "home.html"
        target.write_text("<html></html>", encoding="utf-8")
        assert vvd.find_prototype_html(tmp_path) == str(target.resolve())


# ════════════════════════════════════════════════════════════════════
# verify_computed_styles — token vs computed-style comparison
# ════════════════════════════════════════════════════════════════════


class TestComputedStyleHelpers:
    def test_normalize_color_expands_shorthand_and_uppercases(self):
        assert vcs._normalize_color("#3b82f6") == "#3B82F6"
        assert vcs._normalize_color("#abc") == "#AABBCC"

    def test_normalize_color_strips_alpha(self):
        assert vcs._normalize_color("#3B82F6FF") == "#3B82F6"

    def test_parse_px(self):
        assert vcs._parse_px("16px") == 16.0
        assert vcs._parse_px("not-a-px") is None

    def test_rgb_to_hex(self):
        assert vcs._rgb_to_hex("rgb(59, 130, 246)") == "#3B82F6"
        assert vcs._rgb_to_hex("rgba(17, 24, 39, 1)") == "#111827"
        assert vcs._rgb_to_hex("nope") is None

    def test_value_close_respects_tolerance(self):
        assert vcs._value_close(16.0, {16.0}) is True
        assert vcs._value_close(17.5, {16.0}, tolerance=2.0) is True
        assert vcs._value_close(20.0, {16.0}, tolerance=2.0) is False

    def test_color_close(self):
        assert vcs._color_close("#3B82F6", {"#3B82F6"}) is True
        assert vcs._color_close("#3B82F7", {"#3B82F6"}, tolerance=15) is True
        assert vcs._color_close("#FF0000", {"#3B82F6"}, tolerance=15) is False


class TestBuildFigmaReference:
    def test_reference_sets_from_summary(self, design_data):
        ref = vcs.build_figma_reference(design_data)
        assert "#3B82F6" in ref["colors"]
        assert "#000000" in ref["colors"] and "#FFFFFF" in ref["colors"]
        assert "inter" in ref["fonts"]
        assert ref["font_sizes"] == {16.0, 32.0}
        assert ref["font_weights"] == {400, 700}
        assert 8.0 in ref["radii"]


class TestCompareComputedVsFigma:
    def test_compliant_when_styles_match(self, design_data):
        ref = vcs.build_figma_reference(design_data)
        elements = [{
            "tag": "h1", "className": "hero", "text": "Welcome",
            "styles": {"color": "rgb(59, 130, 246)", "fontSize": "32px", "fontWeight": "700"},
        }]
        result = vcs.compare_computed_vs_figma(elements, ref)
        assert result["compliant"] is True
        assert result["summary"]["total_violations"] == 0

    def test_off_palette_color_is_a_violation(self, design_data):
        ref = vcs.build_figma_reference(design_data)
        elements = [{
            "tag": "div", "className": "rogue", "text": "",
            "styles": {"color": "rgb(200, 10, 10)"},
        }]
        result = vcs.compare_computed_vs_figma(elements, ref)
        assert result["compliant"] is False
        assert any(v["property"] == "color" for v in result["violations"])


class TestPerNodeMatching:
    def test_extract_figma_text_nodes(self, design_data):
        nodes = vcs.extract_figma_text_nodes(design_data)
        texts = {n["text"] for n in nodes}
        assert "Welcome to the Dashboard" in texts
        hero = next(n for n in nodes if n["text"] == "Welcome to the Dashboard")
        assert hero["font_size"] == 32.0
        assert hero["font_weight"] == 700
        assert hero["color"] == "#3B82F6"

    def test_matching_nodes_with_correct_styles_have_no_violations(self, design_data):
        nodes = vcs.extract_figma_text_nodes(design_data)
        dom = [{
            "text": "Welcome to the Dashboard",
            "styles": {"color": "rgb(59, 130, 246)", "fontSize": "32px", "fontWeight": "700"},
        }]
        violations = vcs.match_and_compare_per_node(nodes, dom)
        assert violations == []

    def test_font_size_mismatch_is_reported(self, design_data):
        nodes = vcs.extract_figma_text_nodes(design_data)
        dom = [{
            "text": "Welcome to the Dashboard",
            "styles": {"color": "rgb(59, 130, 246)", "fontSize": "18px", "fontWeight": "700"},
        }]
        violations = vcs.match_and_compare_per_node(nodes, dom)
        assert any(v["property"] == "fontSize" for v in violations)


class TestComputedStylesMain:
    def test_main_no_design_data_passes(self, tmp_path, capsys):
        rc = vcs.main(["--project-path", str(tmp_path)])
        assert rc == 0
        assert "skipped" in capsys.readouterr().out.lower()

    def test_main_compliant_with_mocked_browser(self, tmp_path, monkeypatch):
        fig = tmp_path / "figma-export"
        fig.mkdir(parents=True)
        (fig / "design_data.json").write_text(FIXTURE.read_text(), encoding="utf-8")
        monkeypatch.setattr(vcs, "_check_playwright", lambda: True)
        monkeypatch.setattr(vcs, "extract_computed_styles", lambda url, vw=1440: [{
            "tag": "h1", "className": "hero", "text": "Welcome to the Dashboard",
            "styles": {"color": "rgb(59, 130, 246)", "fontSize": "32px", "fontWeight": "700"},
        }])
        rc = vcs.main([
            "--project-path", str(tmp_path),
            "--url", "file:///fake.html",
        ])
        assert rc == 0


# ════════════════════════════════════════════════════════════════════
# verify_structural_match — element presence vs design_data
# ════════════════════════════════════════════════════════════════════


class TestStructuralExtraction:
    def test_expected_elements_capture_roles_and_text(self, design_data):
        elements = vsm.extract_expected_elements(design_data)
        roles = {e["role"] for e in elements}
        assert "button" in roles
        assert "navigation" in roles
        assert "text" in roles
        texts = {e.get("text_content") for e in elements}
        assert "Welcome to the Dashboard" in texts

    def test_per_viewport_grouping(self, design_data):
        per_vp = vsm.extract_expected_elements_per_viewport(design_data)
        assert "desktop" in per_vp
        assert len(per_vp["desktop"]) > 0

    def test_extract_actual_elements_detects_roles_and_text(self):
        html = "<nav><button>Get Started</button></nav><img src='logo.svg'>"
        actual = vsm.extract_actual_elements(html)
        assert "button" in actual["element_roles"]
        assert "navigation" in actual["element_roles"]
        assert "image" in actual["element_roles"]
        assert "Get Started" in actual["text_contents"]


class TestCompareStructure:
    def test_all_present_is_compliant(self, design_data):
        expected = vsm.extract_expected_elements(design_data)
        html = (
            "<nav class='header'><img src='logo.svg' class='logo'>"
            "<a href='#'>Home</a><a href='#'>About</a></nav>"
            "<h1>Welcome to the Dashboard</h1>"
            "<button>Get Started</button>"
            "<svg class='icon'></svg>"
        )
        result = vsm.compare_structure(expected, {}, [("index.html", html)])
        assert result["compliant"] is True

    def test_missing_text_is_a_violation(self, design_data):
        expected = vsm.extract_expected_elements(design_data)
        html = "<div>totally different content</div>"
        result = vsm.compare_structure(expected, {}, [("index.html", html)])
        assert result["compliant"] is False
        assert any(v["type"] == "missing_text" for v in result["violations"])


class TestResponsiveCoverage:
    def test_single_viewport_needs_no_media_query(self):
        assert vsm.check_responsive_coverage(["desktop"], [("a.css", "body{}")]) == []

    def test_multiple_viewports_without_media_query_flagged(self):
        violations = vsm.check_responsive_coverage(
            ["desktop", "mobile"], [("a.css", "body{color:red}")]
        )
        assert any(v["type"] == "no_responsive" for v in violations)


class TestStructuralMain:
    def test_main_no_design_data_passes(self, tmp_path):
        assert vsm.main(["--project-path", str(tmp_path)]) == 0

    def test_main_no_source_files_fails(self, tmp_path):
        fig = tmp_path / "figma-export"
        fig.mkdir(parents=True)
        (fig / "design_data.json").write_text(FIXTURE.read_text(), encoding="utf-8")
        assert vsm.main(["--project-path", str(tmp_path)]) == 1

    def test_main_complete_source_passes(self, tmp_path):
        fig = tmp_path / "figma-export"
        fig.mkdir(parents=True)
        (fig / "design_data.json").write_text(FIXTURE.read_text(), encoding="utf-8")
        (tmp_path / "index.html").write_text(
            "<nav class='header'><img src='logo.svg' class='logo'>"
            "<a href='#'>Home</a><a href='#'>About</a></nav>"
            "<h1>Welcome to the Dashboard</h1>"
            "<button>Get Started</button>"
            "<svg class='icon'></svg>",
            encoding="utf-8",
        )
        assert vsm.main(["--project-path", str(tmp_path)]) == 0


# ════════════════════════════════════════════════════════════════════
# verify_layout — spatial relationships
# ════════════════════════════════════════════════════════════════════


class TestLayoutExtraction:
    def test_detects_row_and_column_containers(self, design_data):
        rels = vl.extract_layout_relationships(design_data)
        directions = {
            r["container"]: r["direction"]
            for r in rels
            if r["type"] == "container_direction"
        }
        assert directions.get("Home") == "column"
        assert directions.get("Header") == "row"

    def test_sibling_order_recorded(self, design_data):
        rels = vl.extract_layout_relationships(design_data)
        orders = [r for r in rels if r["type"] == "sibling_order"]
        assert orders
        assert all("first" in r and "second" in r for r in orders)


class TestLayoutSourceCheck:
    def test_correct_direction_no_violation(self, design_data):
        rels = vl.extract_layout_relationships(design_data)
        source = ".header { display: flex; flex-direction: row; }"
        result = vl.check_layout_in_source(rels, [("styles.css", source)])
        assert not any(v["type"] == "wrong_direction" for v in result["violations"])

    def test_wrong_direction_flagged(self, design_data):
        rels = vl.extract_layout_relationships(design_data)
        # Figma says Header is a row; source declares column → violation.
        source = ".header { display: flex; flex-direction: column; }"
        result = vl.check_layout_in_source(rels, [("styles.css", source)])
        assert any(v["type"] == "wrong_direction" for v in result["violations"])


class TestLayoutMain:
    def test_main_no_design_data_passes(self, tmp_path):
        assert vl.main(["--project-path", str(tmp_path)]) == 0

    def test_main_no_source_files_fails(self, tmp_path):
        fig = tmp_path / "figma-export"
        fig.mkdir(parents=True)
        (fig / "design_data.json").write_text(FIXTURE.read_text(), encoding="utf-8")
        assert vl.main(["--project-path", str(tmp_path)]) == 1

    def test_main_matching_source_passes(self, tmp_path):
        fig = tmp_path / "figma-export"
        fig.mkdir(parents=True)
        (fig / "design_data.json").write_text(FIXTURE.read_text(), encoding="utf-8")
        (tmp_path / "styles.css").write_text(
            ".header { display: flex; flex-direction: row; }\n"
            ".home { display: flex; flex-direction: column; }\n",
            encoding="utf-8",
        )
        assert vl.main(["--project-path", str(tmp_path)]) == 0


# ════════════════════════════════════════════════════════════════════
# generate_figma_css — CSS output from design data
# ════════════════════════════════════════════════════════════════════


class TestCssHelpers:
    def test_slugify_class(self):
        assert gfc._slugify_class("Primary Button") == "primary-button"
        # spaces/underscores collapse to a single hyphen
        assert gfc._slugify_class("Card__Item List") == "card-item-list"
        assert gfc._slugify_class("") == "element"

    def test_gradient_to_css_linear(self):
        css = gfc._gradient_to_css([{
            "type": "linear", "angle": 90,
            "stops": [{"color": "#fff", "position": 0}, {"color": "#000", "position": 1}],
        }])
        assert css == "linear-gradient(90deg, #fff 0%, #000 100%)"

    def test_gradient_to_css_empty(self):
        assert gfc._gradient_to_css([]) is None

    def test_shadow_to_css(self):
        css = gfc._shadow_to_css([
            {"type": "box-shadow", "offset_x": 0, "offset_y": 2, "blur": 4, "spread": 0, "color": "#0003"},
        ])
        assert "0px 2px 4px 0px #0003" == css

    def test_shadow_to_css_none(self):
        assert gfc._shadow_to_css([{"type": "blur"}]) is None


class TestGenerateNodeCss:
    def test_button_node_gets_background_and_radius(self, design_data):
        tree = design_data["frames"][0]["tree"]
        rules = gfc.generate_node_css(tree, {"Logo": "assets/logo.svg"}, assets_by_id={"10:1": "assets/logo.svg"})
        by_class = {r["class_name"]: r["css_rules"] for r in rules}
        assert "primary-button" in by_class
        btn = " ".join(by_class["primary-button"])
        assert "background-color: #3B82F6" in btn
        assert "border-radius: 8px" in btn

    def test_text_node_gets_typography(self, design_data):
        tree = design_data["frames"][0]["tree"]
        rules = gfc.generate_node_css(tree, {})
        by_class = {r["class_name"]: " ".join(r["css_rules"]) for r in rules}
        assert "hero-title" in by_class
        assert "font-size: 32px" in by_class["hero-title"]
        assert "color: #3B82F6" in by_class["hero-title"]


class TestGenerateCssFile:
    def test_writes_css_and_component_map(self, design_data, tmp_path):
        css, component_map = gfc.generate_css_file(design_data, tmp_path)
        assert (tmp_path / "figma_styles.css").exists()
        assert (tmp_path / "component_map.json").exists()
        assert "@layer figma" in css
        assert ".primary-button" in css
        # interaction_states in the fixture → :hover rule appended.
        assert ":hover" in css
        assert any(e["css_class"] == "primary-button" for e in component_map)


class TestGenerateStateCss:
    def test_hover_rule_from_interaction_states(self, design_data):
        css = gfc.generate_state_css(design_data)
        assert ".primary-button:hover" in css
        assert "background-color: #2563EB" in css

    def test_no_states_returns_empty(self):
        assert gfc.generate_state_css({"summary": {}}) == ""


class TestGenerateResponsiveCss:
    def test_single_frame_returns_empty(self, design_data):
        assert gfc.generate_responsive_css(design_data, {}) == ""

    def test_multiple_frames_emit_media_queries(self, design_data):
        two = json.loads(json.dumps(design_data))
        mobile = json.loads(json.dumps(design_data["frames"][0]))
        mobile["breakpoint"] = "mobile"
        two["frames"].append(mobile)
        css = gfc.generate_responsive_css(two, {})
        assert "@media (max-width: 767px)" in css


class TestGenerateHtmlSkeleton:
    def test_skeleton_contains_text_and_doctype(self, design_data):
        rules = gfc.generate_node_css(design_data["frames"][0]["tree"], {})
        html = gfc.generate_html_skeleton(design_data, rules, {})
        assert html.startswith("<!DOCTYPE html>")
        assert "Welcome to the Dashboard" in html


class TestGenerateCssMain:
    def test_main_generates_files(self, tmp_path):
        fig = tmp_path / "figma-export"
        fig.mkdir(parents=True)
        (fig / "design_data.json").write_text(FIXTURE.read_text(), encoding="utf-8")
        rc = gfc.main(["--project-path", str(tmp_path)])
        assert rc == 0
        assert (fig / "figma_styles.css").exists()
        assert (fig / "component_map.json").exists()

    def test_main_missing_design_data_returns_one(self, tmp_path):
        assert gfc.main(["--project-path", str(tmp_path)]) == 1


# ════════════════════════════════════════════════════════════════════
# Browser auto-install is gated behind an explicit opt-in (ISSUE-049)
# ════════════════════════════════════════════════════════════════════
#
# The visual-diff family must NEVER `pip install playwright` /
# `playwright install chromium` (network + env mutation) as a silent side
# effect. The heavy provisioning path runs only when KIT_ALLOW_BROWSER_INSTALL=1
# is set; otherwise the gate reports "browser unavailable" to stderr and returns
# False so the caller takes its existing skip/degrade path. The subprocess
# boundary is mocked here — the suite never actually installs anything.


@pytest.mark.parametrize("mod", [vvd, vcs], ids=["visual_diff", "computed_styles"])
class TestBrowserInstallOptIn:
    def test_flag_unset_and_missing_does_not_install(self, mod, monkeypatch, capsys):
        # Opt-in flag unset + Playwright missing → NO install subprocess, no
        # network; report unavailable and return False (skip/degrade path).
        monkeypatch.delenv("KIT_ALLOW_BROWSER_INSTALL", raising=False)
        monkeypatch.setattr(mod, "_playwright_importable", lambda: False)
        calls = []
        monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: calls.append(a))

        assert mod._check_playwright() is False
        assert calls == [], "install subprocess must NOT be spawned when opt-in is unset"
        err = capsys.readouterr().err
        assert "browser unavailable" in err.lower()

    def test_flag_set_and_missing_runs_install_once(self, mod, monkeypatch):
        # Opt-in flag set + Playwright missing → auto-install path runs as today
        # (pip install playwright + playwright install chromium), each once.
        monkeypatch.setenv("KIT_ALLOW_BROWSER_INSTALL", "1")
        monkeypatch.setattr(mod, "_playwright_importable", lambda: False)
        commands = []

        def _spy(cmd, *a, **k):
            commands.append(cmd)
            return None

        monkeypatch.setattr(mod.subprocess, "run", _spy)

        mod._check_playwright()  # return value depends on post-install import
        assert ["pip", "install", "playwright"] in commands
        assert ["playwright", "install", "chromium"] in commands
        assert len(commands) == 2, "install path should issue exactly the two install commands"

    def test_present_playwright_never_installs_regardless_of_flag(self, mod, monkeypatch):
        # Playwright present → True and no install, whether the flag is set or not.
        monkeypatch.setattr(mod, "_playwright_importable", lambda: True)
        calls = []
        monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: calls.append(a))

        monkeypatch.delenv("KIT_ALLOW_BROWSER_INSTALL", raising=False)
        assert mod._check_playwright() is True
        monkeypatch.setenv("KIT_ALLOW_BROWSER_INSTALL", "1")
        assert mod._check_playwright() is True
        assert calls == [], "present Playwright must never trigger an install"
