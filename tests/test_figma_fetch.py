"""Unit tests for scripts/figma_fetch.py — asset detection and export."""

from scripts.figma_fetch import (
    _has_image_fill,
    _is_exportable_asset,
    _slugify,
    collect_exportable_nodes,
)


# ── Fixtures ────────────────────────────────────────────────────────


def _make_node(
    *,
    name: str = "Rectangle",
    node_type: str = "RECTANGLE",
    node_id: str = "1:1",
    fills: list | None = None,
    export_settings: list | None = None,
    children: list | None = None,
) -> dict:
    """Build a minimal Figma API node."""
    node: dict = {"id": node_id, "name": name, "type": node_type}
    if fills is not None:
        node["fills"] = fills
    if export_settings is not None:
        node["exportSettings"] = export_settings
    if children is not None:
        node["children"] = children
    return node


# ── TestHasImageFill ────────────────────────────────────────────────


class TestHasImageFill:
    def test_solid_fill_is_not_image(self):
        node = _make_node(fills=[{"type": "SOLID", "visible": True}])
        assert _has_image_fill(node) is False

    def test_image_fill_detected(self):
        node = _make_node(fills=[{"type": "IMAGE", "visible": True}])
        assert _has_image_fill(node) is True

    def test_hidden_image_fill_ignored(self):
        node = _make_node(fills=[{"type": "IMAGE", "visible": False}])
        assert _has_image_fill(node) is False

    def test_no_fills(self):
        node = _make_node(fills=[])
        assert _has_image_fill(node) is False

    def test_missing_fills_key(self):
        node = _make_node()
        assert _has_image_fill(node) is False


# ── TestIsExportableAsset ───────────────────────────────────────────


class TestIsExportableAsset:
    def test_vector_type(self):
        node = _make_node(node_type="VECTOR")
        assert _is_exportable_asset(node) is True

    def test_boolean_operation(self):
        node = _make_node(node_type="BOOLEAN_OPERATION")
        assert _is_exportable_asset(node) is True

    def test_star_type(self):
        node = _make_node(node_type="STAR")
        assert _is_exportable_asset(node) is True

    def test_image_fill(self):
        node = _make_node(
            node_type="RECTANGLE",
            fills=[{"type": "IMAGE", "visible": True}],
        )
        assert _is_exportable_asset(node) is True

    def test_icon_name(self):
        node = _make_node(name="close-icon", node_type="FRAME")
        assert _is_exportable_asset(node) is True

    def test_logo_name(self):
        node = _make_node(name="Company Logo", node_type="GROUP")
        assert _is_exportable_asset(node) is True

    def test_illustration_name(self):
        node = _make_node(name="hero-illustration", node_type="FRAME")
        assert _is_exportable_asset(node) is True

    def test_export_settings(self):
        node = _make_node(
            node_type="FRAME",
            export_settings=[{"suffix": "", "format": "SVG", "constraint": {}}],
        )
        assert _is_exportable_asset(node) is True

    def test_regular_frame_not_exportable(self):
        node = _make_node(name="Main Content", node_type="FRAME")
        assert _is_exportable_asset(node) is False

    def test_text_node_not_exportable(self):
        node = _make_node(name="Heading", node_type="TEXT")
        assert _is_exportable_asset(node) is False


# ── TestCollectExportableNodes ──────────────────────────────────────


class TestCollectExportableNodes:
    def test_collects_vector_children(self):
        root = _make_node(
            name="Frame",
            node_type="FRAME",
            node_id="0:1",
            children=[
                _make_node(name="icon-search", node_type="VECTOR", node_id="1:1"),
                _make_node(name="Some text", node_type="TEXT", node_id="1:2"),
            ],
        )
        assets = collect_exportable_nodes(root, "abc123")
        assert len(assets) == 1
        assert assets[0]["name"] == "icon-search"
        assert assets[0]["format"] == "svg"
        assert assets[0]["file_key"] == "abc123"

    def test_collects_image_fills(self):
        root = _make_node(
            name="Frame",
            node_type="FRAME",
            node_id="0:1",
            children=[
                _make_node(
                    name="hero-image",
                    node_type="RECTANGLE",
                    node_id="1:1",
                    fills=[{"type": "IMAGE", "visible": True}],
                ),
            ],
        )
        assets = collect_exportable_nodes(root, "abc123")
        assert len(assets) == 1
        assert assets[0]["format"] == "png"

    def test_deduplicates_by_node_id(self):
        child = _make_node(name="icon", node_type="VECTOR", node_id="1:1")
        root = _make_node(
            name="Frame",
            node_type="FRAME",
            node_id="0:1",
            children=[child, child],  # same node_id
        )
        assets = collect_exportable_nodes(root, "abc123")
        assert len(assets) == 1

    def test_empty_tree(self):
        root = _make_node(name="Frame", node_type="FRAME", node_id="0:1")
        assets = collect_exportable_nodes(root, "abc123")
        assert assets == []

    def test_nested_assets(self):
        root = _make_node(
            name="Frame",
            node_type="FRAME",
            node_id="0:1",
            children=[
                _make_node(
                    name="toolbar",
                    node_type="FRAME",
                    node_id="1:1",
                    children=[
                        _make_node(name="icon-home", node_type="VECTOR", node_id="2:1"),
                        _make_node(name="icon-settings", node_type="VECTOR", node_id="2:2"),
                    ],
                ),
            ],
        )
        assets = collect_exportable_nodes(root, "abc123")
        assert len(assets) == 2
        names = {a["name"] for a in assets}
        assert names == {"icon-home", "icon-settings"}

    def test_named_asset_small_is_svg(self):
        root = _make_node(
            name="badge-icon",
            node_type="FRAME",
            node_id="0:1",
        )
        root["absoluteBoundingBox"] = {"width": 24, "height": 24}
        assets = collect_exportable_nodes(root, "abc123")
        assert len(assets) == 1
        assert assets[0]["format"] == "svg"

    def test_named_asset_large_is_png(self):
        root = _make_node(
            name="hero-image",
            node_type="FRAME",
            node_id="0:1",
        )
        root["absoluteBoundingBox"] = {"width": 800, "height": 600}
        assets = collect_exportable_nodes(root, "abc123")
        assert len(assets) == 1
        assert assets[0]["format"] == "png"


# ── TestSlugify ─────────────────────────────────────────────────────


class TestSlugify:
    def test_basic(self):
        assert _slugify("Close Icon") == "close-icon"

    def test_special_chars(self):
        assert _slugify("icon/arrow-right (24px)") == "iconarrow-right-24px"

    def test_multiple_spaces(self):
        assert _slugify("  hero   image  ") == "hero-image"

    def test_empty(self):
        assert _slugify("") == "untitled"

    def test_underscores(self):
        assert _slugify("search_icon_large") == "search-icon-large"
