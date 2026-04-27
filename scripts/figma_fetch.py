#!/usr/bin/env python3
"""Fetch design data from Figma API and output structured CSS properties.

Parses Figma URLs, fetches node trees via the REST API, and extracts
design properties (colors, typography, spacing, borders, shadows) into
a structured JSON format that the figma-converter agent can consume.

Requires FIGMA_TOKEN environment variable (Personal Access Token).

Usage:
    python3 scripts/figma_fetch.py [--platform web|mobile|desktop] <figma_url> [<figma_url> ...]
    python3 scripts/figma_fetch.py --help

Options:
    --platform   Target platform: web (default), mobile, desktop.
                 Affects output path and platform-specific metadata.

Output:
    Writes figma-export/design_data.json with extracted properties.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

FIGMA_API_BASE = "https://api.figma.com/v1"

# Node types and name patterns that indicate exportable assets
_VECTOR_TYPES = {"VECTOR", "BOOLEAN_OPERATION", "STAR", "LINE", "ELLIPSE", "REGULAR_POLYGON"}
_ASSET_NAME_PATTERN = re.compile(
    r"\b(?:icon|logo|image|img|illustration|asset|badge|avatar|thumbnail)\b",
    re.IGNORECASE,
)

# --- URL Parsing ---


def parse_figma_url(url: str) -> tuple[str, str]:
    """Extract file_key and node_id from a Figma URL.

    Supports formats:
        https://www.figma.com/design/FILE_KEY/Name?node-id=X-Y
        https://www.figma.com/file/FILE_KEY/Name?node-id=X-Y
        https://www.figma.com/design/FILE_KEY/Name?node-id=X%3AY  (URL-encoded)

    Returns (file_key, node_id) where node_id uses ':' separator.
    """
    # Extract file key: /design/<key>/ or /file/<key>/
    key_match = re.search(r"/(?:design|file)/([a-zA-Z0-9]+)", url)
    if not key_match:
        raise ValueError(f"Cannot extract file key from URL: {url}")
    file_key = key_match.group(1)

    # Extract node-id from query string
    node_match = re.search(r"node-id=([^&]+)", url)
    if not node_match:
        raise ValueError(f"Cannot extract node-id from URL: {url}")

    # Normalize: Figma uses X-Y in URLs but X:Y in API
    node_id = urllib.parse.unquote(node_match.group(1))
    # Only replace dash between digits (e.g., 42-1234 → 42:1234)
    node_id = re.sub(r"(\d)-(\d)", r"\1:\2", node_id)

    return file_key, node_id


# --- API Client ---


def figma_api_get(endpoint: str, token: str) -> dict[str, Any]:
    """Make a GET request to the Figma API."""
    url = f"{FIGMA_API_BASE}{endpoint}"
    req = urllib.request.Request(url, headers={"X-Figma-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(f"Error: Figma API returned {e.code}.", file=sys.stderr)
            print("Check your FIGMA_TOKEN is valid and not expired.", file=sys.stderr)
            sys.exit(1)
        if e.code == 404:
            print(f"Error: Node not found. URL: {url}", file=sys.stderr)
            sys.exit(1)
        raise


def fetch_node(file_key: str, node_id: str, token: str) -> dict[str, Any]:
    """Fetch a specific node and its children from Figma."""
    encoded_id = urllib.parse.quote(node_id, safe="")
    data = figma_api_get(f"/files/{file_key}/nodes?ids={encoded_id}", token)
    nodes = data.get("nodes", {})
    node_data = nodes.get(node_id)
    if not node_data:
        raise ValueError(f"Node {node_id} not found in response")
    return node_data["document"]


# --- Interactive State Detection ---

_STATE_KEYWORDS = re.compile(
    r"\b(hover|focus|active|disabled|pressed|selected|checked|error|loading)\b",
    re.IGNORECASE,
)


def collect_interaction_states(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect interactive states from Figma component variants.

    Figma component sets contain variants with properties like:
    - name: "State=Hover", "State=Active", "Type=Primary, State=Disabled"
    - componentPropertyDefinitions with variant options

    Also detects state-like names in non-component nodes (e.g., "Button / Hover").
    Returns list of {state, name, node_id, colors} for each detected state.
    """
    states: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _walk(n: dict[str, Any]) -> None:
        name = n.get("name", "")
        node_type = n.get("type", "")
        node_id = n.get("id", "")

        # Check component variant properties
        if node_type == "COMPONENT" and "variantProperties" in n:
            variant_props = n.get("variantProperties", {})
            for prop_name, prop_value in variant_props.items():
                if prop_name.lower() in ("state", "status", "interaction"):
                    state_key = f"{prop_value.lower()}:{node_id}"
                    if state_key not in seen:
                        seen.add(state_key)
                        # Extract colors from this variant node
                        variant_colors: list[str] = []
                        _collect_colors(n, variant_colors)
                        states.append({
                            "state": prop_value.lower(),
                            "name": name,
                            "node_id": node_id,
                            "colors": variant_colors,
                        })

        # Check node name for state keywords (e.g., "Button / Hover")
        state_match = _STATE_KEYWORDS.search(name)
        if state_match:
            state = state_match.group(1).lower()
            state_key = f"{state}:{node_id}"
            if state_key not in seen:
                seen.add(state_key)
                variant_colors_list: list[str] = []
                _collect_colors(n, variant_colors_list)
                states.append({
                    "state": state,
                    "name": name,
                    "node_id": node_id,
                    "colors": variant_colors_list,
                })

        for child in n.get("children", []):
            _walk(child)

    def _collect_colors(n: dict[str, Any], colors: list[str]) -> None:
        """Recursively collect all colors from a node subtree."""
        for fill in n.get("fills", []):
            if fill.get("visible", True) and fill.get("type") == "SOLID":
                c = fill.get("color", {})
                colors.append(rgba_to_hex(c))
        for child in n.get("children", []):
            _collect_colors(child, colors)

    _walk(node)
    return states


# --- Color Helpers ---


def rgba_to_hex(color: dict[str, float]) -> str:
    """Convert Figma RGBA (0-1 floats) to hex string."""
    r = round(color.get("r", 0) * 255)
    g = round(color.get("g", 0) * 255)
    b = round(color.get("b", 0) * 255)
    a = color.get("a", 1)
    if a < 1:
        return f"rgba({r}, {g}, {b}, {a:.2f})"
    return f"#{r:02X}{g:02X}{b:02X}"


def extract_fill_color(fills: list[dict]) -> str | None:
    """Extract the primary visible fill color."""
    for fill in fills:
        if not fill.get("visible", True):
            continue
        if fill.get("type") == "SOLID":
            color = fill.get("color", {})
            opacity = fill.get("opacity", 1)
            if opacity < 1:
                color = {**color, "a": color.get("a", 1) * opacity}
            return rgba_to_hex(color)
        if fill.get("type") in ("GRADIENT_LINEAR", "GRADIENT_RADIAL",
                                 "GRADIENT_ANGULAR", "GRADIENT_DIAMOND"):
            stops = fill.get("gradientStops", [])
            if stops:
                colors = [rgba_to_hex(s["color"]) for s in stops]
                return f"linear-gradient({', '.join(colors)})"
    return None


def extract_fill_details(fills: list[dict]) -> dict[str, Any]:
    """Extract detailed fill information (gradients, image refs, all colors)."""
    details: dict[str, Any] = {"colors": [], "gradients": [], "has_image": False}
    for fill in fills:
        if not fill.get("visible", True):
            continue
        ftype = fill.get("type", "")
        if ftype == "SOLID":
            color = fill.get("color", {})
            opacity = fill.get("opacity", 1)
            if opacity < 1:
                color = {**color, "a": color.get("a", 1) * opacity}
            details["colors"].append(rgba_to_hex(color))
        elif ftype in ("GRADIENT_LINEAR", "GRADIENT_RADIAL",
                        "GRADIENT_ANGULAR", "GRADIENT_DIAMOND"):
            stops = fill.get("gradientStops", [])
            grad = {
                "type": ftype.lower().replace("gradient_", ""),
                "stops": [{"color": rgba_to_hex(s["color"]),
                           "position": s.get("position", 0)} for s in stops],
            }
            details["gradients"].append(grad)
            for s in stops:
                details["colors"].append(rgba_to_hex(s["color"]))
        elif ftype == "IMAGE":
            details["has_image"] = True
    return details


# --- Node Property Extraction ---


def extract_text_style(node: dict[str, Any]) -> dict[str, Any] | None:
    """Extract typography properties from a TEXT node."""
    style = node.get("style", {})
    if not style:
        return None

    font_size = style.get("fontSize", 16)
    line_height_px = style.get("lineHeightPx")

    # Map Figma text alignment to CSS
    _align_map = {"LEFT": "left", "CENTER": "center", "RIGHT": "right", "JUSTIFIED": "justify"}
    _case_map = {"UPPER": "uppercase", "LOWER": "lowercase", "TITLE": "capitalize",
                 "SMALL_CAPS": "small-caps", "SMALL_CAPS_FORCED": "small-caps"}

    result: dict[str, Any] = {
        "font_family": style.get("fontFamily", ""),
        "font_weight": style.get("fontWeight", 400),
        "font_size_px": font_size,
        "letter_spacing_px": style.get("letterSpacing", 0),
        "text_align": _align_map.get(style.get("textAlignHorizontal", "LEFT"), "left"),
        "text_transform": _case_map.get(style.get("textCase", "ORIGINAL"), "none"),
        "text_decoration": style.get("textDecoration", "NONE").lower(),
    }

    if line_height_px and font_size > 0:
        result["line_height_ratio"] = round(line_height_px / font_size, 3)
        result["line_height_px"] = round(line_height_px, 1)

    if font_size > 0 and result["letter_spacing_px"]:
        result["letter_spacing_em"] = round(
            result["letter_spacing_px"] / font_size, 4
        )

    # Text color
    fills = node.get("fills", [])
    color = extract_fill_color(fills)
    if color:
        result["color"] = color

    # Text content
    result["text_content"] = node.get("characters", "")

    return result


def extract_effects(effects: list[dict]) -> list[dict[str, Any]]:
    """Extract shadow and blur effects."""
    result = []
    for effect in effects:
        if not effect.get("visible", True):
            continue
        etype = effect.get("type", "")
        if etype in ("DROP_SHADOW", "INNER_SHADOW"):
            color = effect.get("color", {})
            result.append(
                {
                    "type": "box-shadow",
                    "inset": etype == "INNER_SHADOW",
                    "offset_x": effect.get("offset", {}).get("x", 0),
                    "offset_y": effect.get("offset", {}).get("y", 0),
                    "blur": effect.get("radius", 0),
                    "spread": effect.get("spread", 0),
                    "color": rgba_to_hex(color),
                }
            )
    return result


def _figma_align_to_css(value: str) -> str:
    """Map Figma alignment value to CSS equivalent."""
    return {"MIN": "flex-start", "CENTER": "center", "MAX": "flex-end",
            "SPACE_BETWEEN": "space-between", "BASELINE": "baseline",
            "STRETCH": "stretch"}.get(value, value.lower())


def extract_node_properties(node: dict[str, Any]) -> dict[str, Any]:
    """Extract ALL CSS-relevant properties from a single Figma node."""
    props: dict[str, Any] = {
        "name": node.get("name", ""),
        "type": node.get("type", ""),
    }

    # ── Dimensions & Position ──
    bbox = node.get("absoluteBoundingBox", {})
    if bbox:
        props["x"] = round(bbox.get("x", 0), 1)
        props["y"] = round(bbox.get("y", 0), 1)
        props["width"] = round(bbox.get("width", 0), 1)
        props["height"] = round(bbox.get("height", 0), 1)

    # Min/max dimensions
    for dim in ("minWidth", "maxWidth", "minHeight", "maxHeight"):
        val = node.get(dim)
        if val is not None and val > 0:
            props[dim] = round(val, 1)

    # ── Fills (background: color, gradient, image) ──
    fills = node.get("fills", [])
    bg = extract_fill_color(fills)
    if bg:
        props["background_color"] = bg
    fill_details = extract_fill_details(fills)
    if fill_details["gradients"]:
        props["gradients"] = fill_details["gradients"]
    if fill_details["has_image"]:
        props["has_background_image"] = True

    # ── Strokes (borders) ──
    strokes = node.get("strokes", [])
    stroke_color = extract_fill_color(strokes)
    if stroke_color:
        props["border_color"] = stroke_color
        props["border_width"] = node.get("strokeWeight", 1)
        props["border_style"] = "solid"  # Figma strokes are always solid

    # ── Corner radius ──
    cr = node.get("cornerRadius")
    if cr:
        props["border_radius"] = cr
    else:
        radii = node.get("rectangleCornerRadii")
        if radii and any(r > 0 for r in radii):
            props["border_radius"] = radii  # [TL, TR, BR, BL]

    # ── Effects (shadows, blurs) ──
    effects = extract_effects(node.get("effects", []))
    if effects:
        props["effects"] = effects

    # ── Opacity ──
    opacity = node.get("opacity")
    if opacity is not None and opacity < 1:
        props["opacity"] = round(opacity, 2)

    # ── Blend mode ──
    blend = node.get("blendMode")
    if blend and blend not in ("PASS_THROUGH", "NORMAL"):
        _blend_map = {
            "MULTIPLY": "multiply", "SCREEN": "screen", "OVERLAY": "overlay",
            "DARKEN": "darken", "LIGHTEN": "lighten", "COLOR_DODGE": "color-dodge",
            "COLOR_BURN": "color-burn", "HARD_LIGHT": "hard-light",
            "SOFT_LIGHT": "soft-light", "DIFFERENCE": "difference",
            "EXCLUSION": "exclusion", "HUE": "hue", "SATURATION": "saturation",
            "COLOR": "color", "LUMINOSITY": "luminosity",
        }
        props["mix_blend_mode"] = _blend_map.get(blend, blend.lower())

    # ── Overflow / clipping ──
    if node.get("clipsContent"):
        props["overflow"] = "hidden"
    overflow_dir = node.get("overflowDirection")
    if overflow_dir and overflow_dir != "NONE":
        _overflow_map = {"HORIZONTAL": "overflow-x: auto", "VERTICAL": "overflow-y: auto",
                         "BOTH": "overflow: auto"}
        props["overflow"] = _overflow_map.get(overflow_dir, "auto")

    # ── Auto-layout → flexbox ──
    layout_mode = node.get("layoutMode")
    if layout_mode and layout_mode != "NONE":
        props["display"] = "flex"
        props["layout"] = {
            "mode": "row" if layout_mode == "HORIZONTAL" else "column",
            "gap": node.get("itemSpacing", 0),
            "padding_top": node.get("paddingTop", 0),
            "padding_right": node.get("paddingRight", 0),
            "padding_bottom": node.get("paddingBottom", 0),
            "padding_left": node.get("paddingLeft", 0),
            "justify_content": _figma_align_to_css(node.get("primaryAxisAlignItems", "MIN")),
            "align_items": _figma_align_to_css(node.get("counterAxisAlignItems", "MIN")),
            "flex_wrap": "wrap" if node.get("layoutWrap") == "WRAP" else "nowrap",
        }

    # ── Sizing mode (Fill / Hug / Fixed) ──
    h_sizing = node.get("layoutSizingHorizontal", "")
    v_sizing = node.get("layoutSizingVertical", "")
    if h_sizing:
        props["sizing_horizontal"] = h_sizing.lower()  # "fixed", "hug", "fill"
    if v_sizing:
        props["sizing_vertical"] = v_sizing.lower()

    # ── Child layout properties (position within parent auto-layout) ──
    layout_positioning = node.get("layoutPositioning")
    if layout_positioning == "ABSOLUTE":
        props["position"] = "absolute"

    layout_align = node.get("layoutAlign")
    if layout_align == "STRETCH":
        props["align_self"] = "stretch"

    layout_grow = node.get("layoutGrow")
    if layout_grow and layout_grow > 0:
        props["flex_grow"] = layout_grow

    # ── Text-specific ──
    if node.get("type") == "TEXT":
        text_style = extract_text_style(node)
        if text_style:
            props["text_style"] = text_style

    return props


# --- Tree Walker ---


def walk_node_tree(
    node: dict[str, Any], depth: int = 0
) -> dict[str, Any]:
    """Recursively walk the node tree and extract properties."""
    result = extract_node_properties(node)
    result["depth"] = depth

    children_data = []
    for child in node.get("children", []):
        children_data.append(walk_node_tree(child, depth + 1))

    if children_data:
        result["children"] = children_data

    return result


# --- Asset Detection & Export ---


def _has_image_fill(node: dict[str, Any]) -> bool:
    """Check if a node has an IMAGE type fill."""
    for fill in node.get("fills", []):
        if fill.get("type") == "IMAGE" and fill.get("visible", True):
            return True
    return False


def _is_exportable_asset(node: dict[str, Any]) -> bool:
    """Determine if a Figma node should be exported as an image asset.

    Criteria (any of):
    - Vector type nodes (VECTOR, BOOLEAN_OPERATION, STAR, LINE, ELLIPSE, etc.)
    - Nodes with IMAGE fills (raster images)
    - Nodes whose name matches asset patterns (icon, logo, image, etc.)
    - Nodes with explicit exportSettings in Figma
    """
    node_type = node.get("type", "")
    name = node.get("name", "")

    if node_type in _VECTOR_TYPES:
        return True
    if _has_image_fill(node):
        return True
    if _ASSET_NAME_PATTERN.search(name):
        return True
    if node.get("exportSettings"):
        return True
    return False


def collect_exportable_nodes(
    node: dict[str, Any], file_key: str,
) -> list[dict[str, str]]:
    """Walk the raw Figma API node tree and collect exportable asset nodes.

    Returns list of dicts: {node_id, name, type, format}.
    - Vector nodes → SVG
    - Image fills → PNG @2x
    - Named assets → SVG (vectors) or PNG (rasters)

    Excludes top-level frames (containers with children) — those are
    page structure, not assets.
    """
    assets: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    # Track the root node ID to skip it
    root_id = node.get("id", "")

    def _walk(n: dict[str, Any]) -> None:
        node_id = n.get("id", "")
        if node_id in seen_ids:
            return

        # Skip top-level frame (it's a container, not an asset)
        # A FRAME with many children is a page/section, not an exportable image
        is_container = (n.get("type") == "FRAME"
                        and len(n.get("children", [])) > 2
                        and node_id == root_id)
        if is_container:
            for child in n.get("children", []):
                _walk(child)
            return

        if _is_exportable_asset(n):
            seen_ids.add(node_id)
            node_type = n.get("type", "")
            # Choose format: vectors → SVG, rasters → PNG
            if node_type in _VECTOR_TYPES:
                fmt = "svg"
            elif _has_image_fill(n):
                fmt = "png"
            else:
                # Named assets: try SVG for small elements, PNG for larger
                bbox = n.get("absoluteBoundingBox", {})
                w = bbox.get("width", 0)
                h = bbox.get("height", 0)
                fmt = "svg" if w <= 128 and h <= 128 else "png"
            assets.append({
                "node_id": node_id,
                "name": n.get("name", "untitled"),
                "type": node_type,
                "format": fmt,
                "file_key": file_key,
            })
        for child in n.get("children", []):
            _walk(child)

    _walk(node)
    return assets


def _slugify(name: str) -> str:
    """Convert a node name to a filesystem-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-") or "untitled"


def export_assets(
    assets: list[dict[str, str]], token: str, out_dir: Path,
) -> list[dict[str, str]]:
    """Download exportable assets from Figma Image Export API.

    Groups assets by (file_key, format) to minimize API calls.
    Saves to out_dir/assets/{slug}.{format}.

    Returns list of dicts: {name, path, format, node_id}.
    """
    if not assets:
        return []

    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Group by (file_key, format) for batch API calls
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for asset in assets:
        key = (asset["file_key"], asset["format"])
        groups.setdefault(key, []).append(asset)

    exported: list[dict[str, str]] = []

    for (file_key, fmt), group in groups.items():
        node_ids = [a["node_id"] for a in group]
        ids_param = ",".join(urllib.parse.quote(nid, safe="") for nid in node_ids)
        scale = "2" if fmt == "png" else "1"

        endpoint = f"/images/{file_key}?ids={ids_param}&format={fmt}&scale={scale}"
        try:
            data = figma_api_get(endpoint, token)
        except Exception as e:
            print(f"WARN: Image export API failed: {e}", file=sys.stderr)
            continue

        images = data.get("images", {})

        for asset in group:
            image_url = images.get(asset["node_id"])
            if not image_url:
                print(f"WARN: No image URL for {asset['name']} ({asset['node_id']})", file=sys.stderr)
                continue

            slug = _slugify(asset["name"])
            suffix = "@2x" if fmt == "png" else ""
            filename = f"{slug}{suffix}.{fmt}"
            filepath = assets_dir / filename

            # Avoid duplicate filenames
            counter = 1
            while filepath.exists():
                filename = f"{slug}-{counter}{suffix}.{fmt}"
                filepath = assets_dir / filename
                counter += 1

            try:
                req = urllib.request.Request(image_url)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    filepath.write_bytes(resp.read())
                exported.append({
                    "name": asset["name"],
                    "path": str(filepath.relative_to(out_dir.parent)),
                    "format": fmt,
                    "node_id": asset["node_id"],
                })
            except Exception as e:
                print(f"WARN: Failed to download {asset['name']}: {e}", file=sys.stderr)

    return exported


def export_frame_renders(
    frames: list[dict[str, Any]], token: str, out_dir: Path,
) -> list[dict[str, str]]:
    """Download full-frame PNG renders from Figma Image Export API.

    These are the Figma-rendered images — the absolute visual source of truth.
    Used for pixel-level comparison against the implementation.

    Returns list of {name, path, width, height, file_key, node_id}.
    """
    if not frames:
        return []

    renders_dir = out_dir / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)

    # Group by file_key for batch API calls
    groups: dict[str, list[dict]] = {}
    for f in frames:
        groups.setdefault(f["file_key"], []).append(f)

    exported: list[dict[str, str]] = []

    for file_key, group in groups.items():
        node_ids = [f["node_id"] for f in group]
        ids_param = ",".join(urllib.parse.quote(nid, safe="") for nid in node_ids)

        # Export at 2x scale for high-fidelity comparison
        endpoint = f"/images/{file_key}?ids={ids_param}&format=png&scale=2"
        try:
            data = figma_api_get(endpoint, token)
        except Exception as e:
            print(f"WARN: Frame render export failed: {e}", file=sys.stderr)
            continue

        images = data.get("images", {})

        for frame in group:
            image_url = images.get(frame["node_id"])
            if not image_url:
                print(f"WARN: No render URL for frame '{frame['frame_name']}'", file=sys.stderr)
                continue

            slug = _slugify(frame["frame_name"])
            filename = f"{slug}@2x.png"
            filepath = renders_dir / filename

            try:
                req = urllib.request.Request(image_url)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    filepath.write_bytes(resp.read())
                exported.append({
                    "name": frame["frame_name"],
                    "path": str(filepath.relative_to(out_dir.parent)),
                    "width": frame.get("width", 0),
                    "height": frame.get("height", 0),
                    "file_key": file_key,
                    "node_id": frame["node_id"],
                    "breakpoint": frame.get("breakpoint", "desktop"),
                })
            except Exception as e:
                print(f"WARN: Failed to download render for '{frame['frame_name']}': {e}", file=sys.stderr)

    return exported


# --- Aggregation ---


def collect_unique_values(
    tree: dict[str, Any],
) -> dict[str, Any]:
    """Walk the extracted tree and collect ALL unique design values.

    Comprehensive extraction for high-fidelity 1:1 compliance checking.
    Covers every style property Figma can express.
    """
    colors: set[str] = set()
    text_styles: list[dict] = []
    spacings: set[int] = set()
    radii: set[Any] = set()
    shadows: list[dict] = []
    font_weights: set[int] = set()
    font_sizes: set[float] = set()
    line_heights: set[float] = set()
    letter_spacings: set[float] = set()
    opacities: set[float] = set()
    border_widths: set[float] = set()
    # New: layout, position, text, visual properties
    gradients: list[dict] = []
    flex_directions: set[str] = set()
    justify_contents: set[str] = set()
    align_items_vals: set[str] = set()
    flex_wraps: set[str] = set()
    text_aligns: set[str] = set()
    text_transforms: set[str] = set()
    text_decorations: set[str] = set()
    overflow_values: set[str] = set()
    blend_modes: set[str] = set()
    has_absolute_position = False
    has_background_image = False

    seen_text_keys: set[str] = set()
    seen_shadow_keys: set[str] = set()
    seen_gradient_keys: set[str] = set()

    def _walk(node: dict[str, Any]) -> None:
        nonlocal has_absolute_position, has_background_image

        # Colors
        if "background_color" in node:
            colors.add(node["background_color"])
        if "border_color" in node:
            colors.add(node["border_color"])

        # Gradients
        for grad in node.get("gradients", []):
            gkey = json.dumps(grad, sort_keys=True)
            if gkey not in seen_gradient_keys:
                seen_gradient_keys.add(gkey)
                gradients.append(grad)
            for stop in grad.get("stops", []):
                colors.add(stop["color"])

        # Background image
        if node.get("has_background_image"):
            has_background_image = True

        # Border width
        bw = node.get("border_width")
        if bw and bw > 0:
            border_widths.add(float(bw))

        # Opacity
        op = node.get("opacity")
        if op is not None and op < 1:
            opacities.add(round(op, 2))

        # Blend mode
        bm = node.get("mix_blend_mode")
        if bm:
            blend_modes.add(bm)

        # Overflow
        ov = node.get("overflow")
        if ov:
            overflow_values.add(ov)

        # Position
        pos = node.get("position")
        if pos == "absolute":
            has_absolute_position = True

        # Text
        ts = node.get("text_style")
        if ts:
            key = (
                f"{ts.get('font_family')}|{ts.get('font_weight')}|"
                f"{ts.get('font_size_px')}|{ts.get('line_height_ratio', '')}|"
                f"{ts.get('letter_spacing_em', '')}"
            )
            if key not in seen_text_keys:
                seen_text_keys.add(key)
                text_styles.append(ts)
            if ts.get("color"):
                colors.add(ts["color"])
            # Individual typography tokens
            fw = ts.get("font_weight")
            if fw:
                font_weights.add(int(fw))
            fs = ts.get("font_size_px")
            if fs:
                font_sizes.add(float(fs))
            lh = ts.get("line_height_ratio")
            if lh:
                line_heights.add(round(float(lh), 3))
            ls = ts.get("letter_spacing_em")
            if ls:
                letter_spacings.add(round(float(ls), 4))
            # Text properties
            ta = ts.get("text_align")
            if ta and ta != "left":  # left is default
                text_aligns.add(ta)
            tt = ts.get("text_transform")
            if tt and tt != "none":
                text_transforms.add(tt)
            td = ts.get("text_decoration")
            if td and td != "none":
                text_decorations.add(td)

        # Layout (flex properties)
        layout = node.get("layout")
        if layout:
            fd = layout.get("mode")
            if fd:
                flex_directions.add(fd)
            jc = layout.get("justify_content")
            if jc:
                justify_contents.add(jc)
            ai = layout.get("align_items")
            if ai:
                align_items_vals.add(ai)
            fw_val = layout.get("flex_wrap")
            if fw_val:
                flex_wraps.add(fw_val)
            for val in [
                layout.get("gap"),
                layout.get("padding_top"),
                layout.get("padding_right"),
                layout.get("padding_bottom"),
                layout.get("padding_left"),
            ]:
                if val and val > 0:
                    spacings.add(int(val))

        # Radius
        r = node.get("border_radius")
        if r:
            if isinstance(r, list):
                for v in r:
                    if v > 0:
                        radii.add(int(v))
            else:
                radii.add(int(r))

        # Shadows — deduplicated
        for effect in node.get("effects", []):
            skey = json.dumps(effect, sort_keys=True)
            if skey not in seen_shadow_keys:
                seen_shadow_keys.add(skey)
                shadows.append(effect)

        # Recurse
        for child in node.get("children", []):
            _walk(child)

    _walk(tree)

    return {
        "colors": sorted(colors),
        "text_styles": sorted(
            text_styles, key=lambda t: -t.get("font_size_px", 0)
        ),
        "font_weights": sorted(font_weights),
        "font_sizes": sorted(font_sizes),
        "line_heights": sorted(line_heights),
        "letter_spacings": sorted(letter_spacings),
        "spacings": sorted(spacings),
        "border_radii": sorted(radii),
        "border_widths": sorted(border_widths),
        "opacities": sorted(opacities),
        "shadows": shadows,
        "gradients": gradients,
        "flex_directions": sorted(flex_directions),
        "justify_contents": sorted(justify_contents),
        "align_items": sorted(align_items_vals),
        "flex_wraps": sorted(flex_wraps),
        "text_aligns": sorted(text_aligns),
        "text_transforms": sorted(text_transforms),
        "text_decorations": sorted(text_decorations),
        "overflow_values": sorted(overflow_values),
        "blend_modes": sorted(blend_modes),
        "has_absolute_position": has_absolute_position,
        "has_background_image": has_background_image,
    }


# --- Main ---


PLATFORM_CONFIG = {
    "web": {
        "prototype_dir": "prototype",
        "design_system_file": "design_system.md",
        "wireframes_file": "wireframes.md",
        "interactions_file": "interactions.md",
    },
    "mobile": {
        "prototype_dir": "prototype-mobile",
        "design_system_file": "design_system_mobile.md",
        "wireframes_file": "wireframes_mobile.md",
        "interactions_file": "interactions_mobile.md",
    },
    "desktop": {
        "prototype_dir": "prototype-desktop",
        "design_system_file": "design_system_desktop.md",
        "wireframes_file": "wireframes_desktop.md",
        "interactions_file": "interactions_desktop.md",
    },
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    token = os.environ.get("FIGMA_TOKEN")
    if not token:
        print(
            "Error: FIGMA_TOKEN environment variable not set.", file=sys.stderr
        )
        print(
            "Get a token: Figma → Settings → Account → Personal access tokens",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse --platform flag
    args = sys.argv[1:]
    platform = "web"
    if "--platform" in args:
        idx = args.index("--platform")
        if idx + 1 >= len(args):
            print("Error: --platform requires a value (web, mobile, desktop)", file=sys.stderr)
            sys.exit(2)
        platform = args[idx + 1]
        if platform not in PLATFORM_CONFIG:
            print(f"Error: invalid platform '{platform}'. Use: web, mobile, desktop", file=sys.stderr)
            sys.exit(2)
        args = args[:idx] + args[idx + 2:]

    # Also support shorthand flags
    for flag, plat in [("--mobile", "mobile"), ("--desktop", "desktop"), ("--web", "web")]:
        if flag in args:
            platform = plat
            args.remove(flag)

    urls = args
    if not urls:
        print("Error: no Figma URLs provided.", file=sys.stderr)
        sys.exit(2)

    frames: list[dict[str, Any]] = []
    all_raw_nodes: list[tuple[dict[str, Any], str]] = []  # (raw_node, file_key)

    for url in urls:
        try:
            file_key, node_id = parse_figma_url(url)
        except ValueError as e:
            print(f"WARN: Skipping URL — {e}", file=sys.stderr)
            continue
        print(f"Fetching: file={file_key}, node={node_id}...", file=sys.stderr)
        node = fetch_node(file_key, node_id, token)
        all_raw_nodes.append((node, file_key))
        tree = walk_node_tree(node)

        # Detect breakpoint from frame width
        width = tree.get("width", 0)
        if width >= 1200:
            breakpoint = "desktop"
        elif width >= 700:
            breakpoint = "tablet"
        else:
            breakpoint = "mobile"

        unique = collect_unique_values(tree)

        frames.append(
            {
                "source_url": url,
                "file_key": file_key,
                "node_id": node_id,
                "frame_name": tree.get("name", "untitled"),
                "breakpoint": breakpoint,
                "width": width,
                "height": tree.get("height", 0),
                "tree": tree,
                "unique_values": unique,
            }
        )

    if not frames:
        print("Error: no valid frames fetched from any URL.", file=sys.stderr)
        sys.exit(1)

    # Merge unique values across all frames
    all_colors: set[str] = set()
    all_text_styles: list[dict] = []
    all_spacings: set[int] = set()
    all_radii: set[int] = set()
    all_shadows: list[dict] = []
    all_font_weights: set[int] = set()
    all_font_sizes: set[float] = set()
    all_line_heights: set[float] = set()
    all_letter_spacings: set[float] = set()
    all_opacities: set[float] = set()
    all_border_widths: set[float] = set()
    all_gradients: list[dict] = []
    all_flex_directions: set[str] = set()
    all_justify_contents: set[str] = set()
    all_align_items: set[str] = set()
    all_flex_wraps: set[str] = set()
    all_text_aligns: set[str] = set()
    all_text_transforms: set[str] = set()
    all_text_decorations: set[str] = set()
    all_overflow_values: set[str] = set()
    all_blend_modes: set[str] = set()
    any_absolute_position = False
    any_background_image = False
    seen_keys: set[str] = set()
    seen_shadow_keys: set[str] = set()
    seen_gradient_keys: set[str] = set()

    for f in frames:
        uv = f["unique_values"]
        all_colors.update(uv["colors"])
        all_spacings.update(uv["spacings"])
        all_radii.update(uv["border_radii"])
        all_font_weights.update(uv.get("font_weights", []))
        all_font_sizes.update(uv.get("font_sizes", []))
        all_line_heights.update(uv.get("line_heights", []))
        all_letter_spacings.update(uv.get("letter_spacings", []))
        all_opacities.update(uv.get("opacities", []))
        all_border_widths.update(uv.get("border_widths", []))
        all_flex_directions.update(uv.get("flex_directions", []))
        all_justify_contents.update(uv.get("justify_contents", []))
        all_align_items.update(uv.get("align_items", []))
        all_flex_wraps.update(uv.get("flex_wraps", []))
        all_text_aligns.update(uv.get("text_aligns", []))
        all_text_transforms.update(uv.get("text_transforms", []))
        all_text_decorations.update(uv.get("text_decorations", []))
        all_overflow_values.update(uv.get("overflow_values", []))
        all_blend_modes.update(uv.get("blend_modes", []))
        if uv.get("has_absolute_position"):
            any_absolute_position = True
        if uv.get("has_background_image"):
            any_background_image = True
        for grad in uv.get("gradients", []):
            gkey = json.dumps(grad, sort_keys=True)
            if gkey not in seen_gradient_keys:
                seen_gradient_keys.add(gkey)
                all_gradients.append(grad)
        for shadow in uv["shadows"]:
            skey = json.dumps(shadow, sort_keys=True)
            if skey not in seen_shadow_keys:
                seen_shadow_keys.add(skey)
                all_shadows.append(shadow)
        for ts in uv["text_styles"]:
            key = (
                f"{ts.get('font_family')}|{ts.get('font_weight')}|"
                f"{ts.get('font_size_px')}"
            )
            if key not in seen_keys:
                seen_keys.add(key)
                all_text_styles.append(ts)

    # --- Interactive state detection ---
    all_interaction_states: list[dict] = []
    seen_state_keys: set[str] = set()
    for raw_node, _ in all_raw_nodes:
        for state in collect_interaction_states(raw_node):
            skey = f"{state['state']}:{state['name']}"
            if skey not in seen_state_keys:
                seen_state_keys.add(skey)
                all_interaction_states.append(state)

    if all_interaction_states:
        state_names = sorted({s["state"] for s in all_interaction_states})
        print(f"\nDetected {len(all_interaction_states)} interactive state(s): {', '.join(state_names)}", file=sys.stderr)

    # --- Asset detection & export ---
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    out_dir = repo_root / "figma-export"
    out_dir.mkdir(exist_ok=True)

    all_exportable: list[dict[str, str]] = []
    for raw_node, fk in all_raw_nodes:
        all_exportable.extend(collect_exportable_nodes(raw_node, fk))

    exported_assets: list[dict[str, str]] = []
    if all_exportable:
        print(f"\nDetected {len(all_exportable)} exportable asset(s)...", file=sys.stderr)
        exported_assets = export_assets(all_exportable, token, out_dir)
        print(f"  Downloaded {len(exported_assets)} asset(s)", file=sys.stderr)

    else:
        print("\nNo exportable assets detected in the fetched frames.", file=sys.stderr)

    # --- Frame render export (Figma-rendered PNGs = absolute visual source of truth) ---
    print(f"\nExporting {len(frames)} frame render(s) from Figma...", file=sys.stderr)
    frame_renders = export_frame_renders(frames, token, out_dir)
    print(f"  Downloaded {len(frame_renders)} render(s) to figma-export/renders/", file=sys.stderr)

    output = {
        "platform": platform,
        "platform_config": PLATFORM_CONFIG[platform],
        "frames": frames,
        "assets": exported_assets,
        "summary": {
            "frame_count": len(frames),
            "breakpoints": [f["breakpoint"] for f in frames],
            # Token values
            "colors": sorted(all_colors),
            "text_styles": sorted(
                all_text_styles, key=lambda t: -t.get("font_size_px", 0)
            ),
            "font_weights": sorted(all_font_weights),
            "font_sizes": sorted(all_font_sizes),
            "line_heights": sorted(all_line_heights),
            "letter_spacings": sorted(all_letter_spacings),
            "spacings": sorted(all_spacings),
            "border_radii": sorted(all_radii),
            "border_widths": sorted(all_border_widths),
            "opacities": sorted(all_opacities),
            "shadows": all_shadows,
            "shadow_count": len(all_shadows),
            # Layout & position values
            "gradients": all_gradients,
            "flex_directions": sorted(all_flex_directions),
            "justify_contents": sorted(all_justify_contents),
            "align_items": sorted(all_align_items),
            "flex_wraps": sorted(all_flex_wraps),
            "text_aligns": sorted(all_text_aligns),
            "text_transforms": sorted(all_text_transforms),
            "text_decorations": sorted(all_text_decorations),
            "overflow_values": sorted(all_overflow_values),
            "blend_modes": sorted(all_blend_modes),
            "has_absolute_position": any_absolute_position,
            "has_background_image": any_background_image,
            "interaction_states": all_interaction_states,
            "interaction_state_names": sorted({s["state"] for s in all_interaction_states}),
            "frame_renders": frame_renders,
            "asset_count": len(exported_assets),
        },
    }

    # Write output
    out_file = out_dir / "design_data.json"
    out_file.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    # Print summary
    s = output["summary"]
    print(f"\nFigma data fetched successfully → {out_file}", file=sys.stderr)
    print(f"  Platform: {platform}", file=sys.stderr)
    print(f"  Frames: {s['frame_count']} ({', '.join(s['breakpoints'])})", file=sys.stderr)
    print(f"  Colors: {len(s['colors'])}", file=sys.stderr)
    print(f"  Text styles: {len(s['text_styles'])}", file=sys.stderr)
    print(f"  Spacing values: {len(s['spacings'])}", file=sys.stderr)
    print(f"  Border radii: {len(s['border_radii'])}", file=sys.stderr)
    print(f"  Shadows: {s['shadow_count']}", file=sys.stderr)
    print(f"  Assets: {s['asset_count']}", file=sys.stderr)

    # --- Generate ready-to-use CSS from node tree ---
    try:
        from generate_figma_css import generate_css_file
        _, component_map = generate_css_file(output, out_dir)
        print(f"\n  Generated figma_styles.css ({len(component_map)} components)", file=sys.stderr)
        print(f"  Generated component_map.json", file=sys.stderr)
    except Exception as e:
        # Try with full path
        try:
            scripts_dir = Path(__file__).resolve().parent
            sys.path.insert(0, str(scripts_dir))
            from generate_figma_css import generate_css_file as gen_css
            _, component_map = gen_css(output, out_dir)
            print(f"\n  Generated figma_styles.css ({len(component_map)} components)", file=sys.stderr)
            print(f"  Generated component_map.json", file=sys.stderr)
        except Exception as e2:
            print(f"\n  WARN: Could not generate figma_styles.css: {e2}", file=sys.stderr)

    # Also print to stdout for skill to capture
    print(json.dumps(output["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
