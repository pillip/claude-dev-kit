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
        if fill.get("type") in ("GRADIENT_LINEAR", "GRADIENT_RADIAL"):
            stops = fill.get("gradientStops", [])
            if stops:
                colors = [rgba_to_hex(s["color"]) for s in stops]
                return f"linear-gradient({', '.join(colors)})"
    return None


# --- Node Property Extraction ---


def extract_text_style(node: dict[str, Any]) -> dict[str, Any] | None:
    """Extract typography properties from a TEXT node."""
    style = node.get("style", {})
    if not style:
        return None

    font_size = style.get("fontSize", 16)
    line_height_px = style.get("lineHeightPx")

    result: dict[str, Any] = {
        "font_family": style.get("fontFamily", ""),
        "font_weight": style.get("fontWeight", 400),
        "font_size_px": font_size,
        "letter_spacing_px": style.get("letterSpacing", 0),
        "text_transform": "uppercase"
        if style.get("textCase") == "UPPER"
        else "none",
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


def extract_node_properties(node: dict[str, Any]) -> dict[str, Any]:
    """Extract CSS-relevant properties from a single Figma node."""
    props: dict[str, Any] = {
        "name": node.get("name", ""),
        "type": node.get("type", ""),
    }

    # Size
    bbox = node.get("absoluteBoundingBox", {})
    if bbox:
        props["width"] = round(bbox.get("width", 0), 1)
        props["height"] = round(bbox.get("height", 0), 1)

    # Fills (background color)
    fills = node.get("fills", [])
    bg = extract_fill_color(fills)
    if bg:
        props["background_color"] = bg

    # Strokes (borders)
    strokes = node.get("strokes", [])
    stroke_color = extract_fill_color(strokes)
    if stroke_color:
        props["border_color"] = stroke_color
        props["border_width"] = node.get("strokeWeight", 1)

    # Corner radius
    cr = node.get("cornerRadius")
    if cr:
        props["border_radius"] = cr
    else:
        radii = node.get("rectangleCornerRadii")
        if radii and any(r > 0 for r in radii):
            props["border_radius"] = radii  # [TL, TR, BR, BL]

    # Effects (shadows)
    effects = extract_effects(node.get("effects", []))
    if effects:
        props["effects"] = effects

    # Opacity
    opacity = node.get("opacity")
    if opacity is not None and opacity < 1:
        props["opacity"] = round(opacity, 2)

    # Auto-layout (spacing, padding)
    layout_mode = node.get("layoutMode")
    if layout_mode and layout_mode != "NONE":
        props["layout"] = {
            "mode": "row" if layout_mode == "HORIZONTAL" else "column",
            "gap": node.get("itemSpacing", 0),
            "padding_top": node.get("paddingTop", 0),
            "padding_right": node.get("paddingRight", 0),
            "padding_bottom": node.get("paddingBottom", 0),
            "padding_left": node.get("paddingLeft", 0),
            "align": node.get("primaryAxisAlignItems", "MIN"),
            "cross_align": node.get("counterAxisAlignItems", "MIN"),
        }

    # Text-specific
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


# --- Aggregation ---


def collect_unique_values(
    tree: dict[str, Any],
) -> dict[str, Any]:
    """Walk the extracted tree and collect unique design values."""
    colors: set[str] = set()
    text_styles: list[dict] = []
    spacings: set[int] = set()
    radii: set[Any] = set()
    shadows: list[dict] = []
    seen_text_keys: set[str] = set()

    def _walk(node: dict[str, Any]) -> None:
        # Colors
        if "background_color" in node:
            colors.add(node["background_color"])
        if "border_color" in node:
            colors.add(node["border_color"])

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

        # Spacing
        layout = node.get("layout")
        if layout:
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

        # Shadows
        for effect in node.get("effects", []):
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
        "spacings": sorted(spacings),
        "border_radii": sorted(radii),
        "shadows": shadows,
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

    for url in urls:
        try:
            file_key, node_id = parse_figma_url(url)
        except ValueError as e:
            print(f"WARN: Skipping URL — {e}", file=sys.stderr)
            continue
        print(f"Fetching: file={file_key}, node={node_id}...", file=sys.stderr)
        node = fetch_node(file_key, node_id, token)
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
    seen_keys: set[str] = set()

    for f in frames:
        uv = f["unique_values"]
        all_colors.update(uv["colors"])
        all_spacings.update(uv["spacings"])
        all_radii.update(uv["border_radii"])
        all_shadows.extend(uv["shadows"])
        for ts in uv["text_styles"]:
            key = (
                f"{ts.get('font_family')}|{ts.get('font_weight')}|"
                f"{ts.get('font_size_px')}"
            )
            if key not in seen_keys:
                seen_keys.add(key)
                all_text_styles.append(ts)

    output = {
        "platform": platform,
        "platform_config": PLATFORM_CONFIG[platform],
        "frames": frames,
        "summary": {
            "frame_count": len(frames),
            "breakpoints": [f["breakpoint"] for f in frames],
            "colors": sorted(all_colors),
            "text_styles": sorted(
                all_text_styles, key=lambda t: -t.get("font_size_px", 0)
            ),
            "spacings": sorted(all_spacings),
            "border_radii": sorted(all_radii),
            "shadow_count": len(all_shadows),
        },
    }

    # Write output — resolve repo root so the file lands in a predictable place
    # regardless of CWD
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    out_dir = repo_root / "figma-export"
    out_dir.mkdir(exist_ok=True)
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

    # Also print to stdout for skill to capture
    print(json.dumps(output["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
