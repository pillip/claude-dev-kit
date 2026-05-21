#!/usr/bin/env python3
"""Generate ready-to-use CSS from Figma design data.

Reads figma-export/design_data.json and produces:
1. figma-export/figma_styles.css — complete CSS rules per Figma node
2. figma-export/component_map.json — maps Figma node names to CSS class names + asset paths

The developer imports figma_styles.css directly instead of interpreting JSON.
This eliminates the translation gap between Figma data and CSS implementation.

Usage:
    python3 scripts/generate_figma_css.py [--project-path <path>]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _slugify_class(name: str) -> str:
    """Convert Figma node name to CSS class name."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_/]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-") or "element"


def _gradient_to_css(gradients: list[dict]) -> str | None:
    """Convert Figma gradient data to CSS gradient string."""
    if not gradients:
        return None
    grad = gradients[0]  # Use first gradient
    grad_type = grad.get("type", "linear")
    stops = grad.get("stops", [])
    if not stops:
        return None

    stop_strs = []
    for stop in stops:
        color = stop.get("color", "#000")
        pos = stop.get("position", 0)
        stop_strs.append(f"{color} {round(pos * 100)}%")

    if grad_type == "radial":
        return f"radial-gradient({', '.join(stop_strs)})"
    angle = grad.get("angle", 180)
    return f"linear-gradient({angle}deg, {', '.join(stop_strs)})"


def _shadow_to_css(effects: list[dict]) -> str | None:
    """Convert Figma shadow effects to CSS box-shadow."""
    shadows = []
    for effect in effects:
        if effect.get("type") != "box-shadow":
            continue
        inset = "inset " if effect.get("inset") else ""
        x = effect.get("offset_x", 0)
        y = effect.get("offset_y", 0)
        blur = effect.get("blur", 0)
        spread = effect.get("spread", 0)
        color = effect.get("color", "rgba(0,0,0,0.1)")
        shadows.append(f"{inset}{x}px {y}px {blur}px {spread}px {color}")
    return ", ".join(shadows) if shadows else None


def generate_node_css(
    node: dict,
    assets_by_node: dict[str, str],
    parent_x: float = 0,
    parent_y: float = 0,
    assets_by_id: dict[str, str] | None = None,
) -> list[dict]:
    """Generate CSS rules for a Figma node and its children.

    Returns list of {class_name, node_name, css_rules, asset_path, children_classes}.
    """
    assets_by_id = assets_by_id or {}
    results: list[dict] = []
    name = node.get("name", "")
    node_type = node.get("type", "")

    # Lookup helper: prefer ID match (exact, even with duplicate names),
    # fall back to name match.
    def _lookup_asset(n: dict) -> str | None:
        return assets_by_id.get(n.get("node_id", "")) or assets_by_node.get(n.get("name", ""))

    # Skip decorative/structural nodes
    if not name or name.startswith("Group") or node_type in ("GROUP",):
        for child in node.get("children", []):
            results.extend(generate_node_css(child, assets_by_node, parent_x, parent_y, assets_by_id))
        return results

    class_name = _slugify_class(name)
    rules: list[str] = []

    # Background
    if node.get("gradients"):
        grad = _gradient_to_css(node["gradients"])
        if grad:
            rules.append(f"background: {grad}")
    elif node.get("background_color"):
        rules.append(f"background-color: {node['background_color']}")

    if node.get("has_background_image"):
        asset_path = _lookup_asset(node)
        if asset_path:
            rules.append(f"background-image: url('{asset_path}')")
            rules.append("background-size: cover")
            rules.append("background-position: center")

    # Dimensions — based on Figma sizing mode (Fill / Hug / Fixed)
    w = node.get("width")
    h = node.get("height")
    layout = node.get("layout")
    h_sizing = node.get("sizing_horizontal", "fixed")
    v_sizing = node.get("sizing_vertical", "fixed")

    if h_sizing == "fill":
        rules.append("width: 100%")
    elif h_sizing == "hug":
        rules.append("width: fit-content")
    elif w and w > 0 and not layout:
        rules.append(f"width: {w}px")

    if v_sizing == "fill":
        rules.append("height: 100%")
    elif v_sizing == "hug":
        rules.append("height: fit-content")
    elif h and h > 0 and not layout:
        rules.append(f"height: {h}px")

    # Border
    _has_gradient_border = False
    _gradient_border_css = ""
    if node.get("border_color"):
        bw = node.get("border_width", 1)
        bc = node["border_color"]
        if bc.startswith("linear-gradient") or bc.startswith("radial-gradient"):
            _has_gradient_border = True
            _gradient_border_css = bc
            has_radius = bool(node.get("border_radius"))
            if has_radius:
                # gradient border + radius → can't use border-image, will use ::before
                # Don't add border rules here — handled as pseudo-element class
                pass
            else:
                rules.append(f"border: {bw}px solid transparent")
                rules.append(f"border-image: {bc} 1")
        else:
            rules.append(f"border: {bw}px solid {bc}")
    if node.get("border_radius"):
        br = node["border_radius"]
        if isinstance(br, list):
            rules.append(f"border-radius: {br[0]}px {br[1]}px {br[2]}px {br[3]}px")
        else:
            rules.append(f"border-radius: {br}px")

    # Opacity
    if node.get("opacity") is not None:
        rules.append(f"opacity: {node['opacity']}")

    # Blend mode
    if node.get("mix_blend_mode"):
        rules.append(f"mix-blend-mode: {node['mix_blend_mode']}")

    # Overflow
    if node.get("overflow"):
        rules.append(f"overflow: {node['overflow']}")

    # Shadows
    if node.get("effects"):
        shadow_css = _shadow_to_css(node["effects"])
        if shadow_css:
            rules.append(f"box-shadow: {shadow_css}")

    # Layout (flexbox) or absolute positioning container
    children = node.get("children", [])
    if layout:
        rules.append("display: flex")
        rules.append(f"flex-direction: {layout.get('mode', 'column')}")
        if layout.get("gap"):
            rules.append(f"gap: {layout['gap']}px")
        if layout.get("justify_content"):
            rules.append(f"justify-content: {layout['justify_content']}")
        if layout.get("align_items"):
            rules.append(f"align-items: {layout['align_items']}")
        if layout.get("flex_wrap") and layout["flex_wrap"] != "nowrap":
            rules.append(f"flex-wrap: {layout['flex_wrap']}")

        # Padding
        pt = layout.get("padding_top", 0)
        pr = layout.get("padding_right", 0)
        pb = layout.get("padding_bottom", 0)
        pl = layout.get("padding_left", 0)
        if pt or pr or pb or pl:
            rules.append(f"padding: {pt}px {pr}px {pb}px {pl}px")
    elif children and node_type == "FRAME":
        # No auto-layout → children are absolutely positioned
        rules.append("position: relative")

    # Position — explicit absolute or inferred from parent without auto-layout
    if node.get("position") == "absolute":
        rules.append("position: absolute")
    # z-index from Figma layer order (set by parent during children iteration)
    z = node.get("_z_index")
    if z is not None:
        rules.append(f"z-index: {z}")
        x = node.get("x")
        y = node.get("y")
        if x is not None:
            # Use left/top relative to parent (parent_x/parent_y passed from caller)
            rules.append(f"left: {round(x - parent_x)}px")
        if y is not None:
            rules.append(f"top: {round(y - parent_y)}px")

    # Flex child properties
    if node.get("flex_grow"):
        rules.append(f"flex-grow: {node['flex_grow']}")
    if node.get("align_self"):
        rules.append(f"align-self: {node['align_self']}")

    # Typography
    ts = node.get("text_style")
    if ts:
        if ts.get("font_family"):
            rules.append(f"font-family: '{ts['font_family']}'")
        if ts.get("font_weight"):
            rules.append(f"font-weight: {ts['font_weight']}")
        if ts.get("font_size_px"):
            rules.append(f"font-size: {ts['font_size_px']}px")
        if ts.get("line_height_ratio"):
            rules.append(f"line-height: {ts['line_height_ratio']}")
        if ts.get("letter_spacing_em"):
            rules.append(f"letter-spacing: {ts['letter_spacing_em']}em")
        if ts.get("color"):
            rules.append(f"color: {ts['color']}")
        if ts.get("text_align") and ts["text_align"] != "left":
            rules.append(f"text-align: {ts['text_align']}")
        if ts.get("text_transform") and ts["text_transform"] != "none":
            rules.append(f"text-transform: {ts['text_transform']}")
        if ts.get("text_decoration") and ts["text_decoration"] != "none":
            rules.append(f"text-decoration: {ts['text_decoration']}")

    # Check for asset (icon/image) — add size only if not already set by dimensions section
    asset_path = _lookup_asset(node)
    if asset_path:
        asset_w = node.get("width", 0)
        asset_h = node.get("height", 0)
        has_width = any(r.startswith("width:") for r in rules)
        has_height = any(r.startswith("height:") for r in rules)
        if asset_w > 0 and not has_width:
            rules.append(f"width: {asset_w}px")
        if asset_h > 0 and not has_height:
            rules.append(f"height: {asset_h}px")

    children_results = []
    child_order: list[dict] = []
    # Pass this node's position as parent reference for children
    node_x = node.get("x", parent_x)
    node_y = node.get("y", parent_y)
    # If no auto-layout, children need absolute positioning
    children_need_absolute = not layout and children and node_type == "FRAME"
    for idx, child in enumerate(node.get("children", [])):
        if children_need_absolute and child.get("type") not in ("GROUP",):
            child.setdefault("position", "absolute")
            # z-index from Figma layer order: later children = on top
            child.setdefault("_z_index", idx + 1)
        child_results = generate_node_css(child, assets_by_node, node_x, node_y, assets_by_id)
        children_results.extend(child_results)
        child_name = child.get("name", "")
        if child_name:
            child_order.append({
                "index": idx,
                "name": child_name,
                "class": _slugify_class(child_name),
                "asset": _lookup_asset(child),
                "width": child.get("width", 0),
                "height": child.get("height", 0),
            })

    if rules:
        results.append({
            "class_name": class_name,
            "node_name": name,
            "css_rules": rules,
            "asset_path": asset_path,
            "asset_width": node.get("width", 0) if asset_path else None,
            "asset_height": node.get("height", 0) if asset_path else None,
            "children_classes": [c["class_name"] for c in children_results if c.get("css_rules")],
            "children_order": child_order if child_order else None,
            "gradient_border": _gradient_border_css if _has_gradient_border else None,
        })

    results.extend(children_results)
    return results


def generate_css_file(design_data: dict, out_dir: Path) -> tuple[str, list[dict]]:
    """Generate figma_styles.css and component_map.json.

    Returns (css_content, component_map).
    """
    # Build asset lookup: node_name → relative path
    # Paths in design_data.json are relative to project root (e.g., "figma-export/assets/icon.svg")
    # But skeleton.html and figma_styles.css live inside figma-export/,
    # so we strip the "figma-export/" prefix for correct relative references.
    assets_by_node: dict[str, str] = {}
    for asset in design_data.get("assets", []):
        path = asset["path"]
        if path.startswith("figma-export/"):
            path = path[len("figma-export/"):]
        assets_by_node[asset["name"]] = path

    # Also map by node_id
    assets_by_id: dict[str, str] = {}
    for asset in design_data.get("assets", []):
        path = asset.get("path", "")
        if path.startswith("figma-export/"):
            path = path[len("figma-export/"):]
        assets_by_id[asset.get("node_id", "")] = path

    all_rules: list[dict] = []
    for frame in design_data.get("frames", []):
        tree = frame.get("tree", {})
        all_rules.extend(generate_node_css(tree, assets_by_node, assets_by_id=assets_by_id))

    # Deduplicate class names
    seen_classes: dict[str, int] = {}
    for rule in all_rules:
        cn = rule["class_name"]
        if cn in seen_classes:
            seen_classes[cn] += 1
            rule["class_name"] = f"{cn}-{seen_classes[cn]}"
        else:
            seen_classes[cn] = 1

    # Collect all font families for Google Fonts
    all_fonts: set[str] = set()
    for rule in all_rules:
        for css_rule in rule.get("css_rules", []):
            if css_rule.startswith("font-family:"):
                font = css_rule.split(":", 1)[1].strip().strip("'\"").rstrip(";")
                if font and font.lower() not in ("sans-serif", "serif", "monospace", "system-ui"):
                    all_fonts.add(font)

    # Generate Google Fonts import
    font_imports = []
    if all_fonts:
        family_params = []
        for font_name in sorted(all_fonts):
            encoded = font_name.replace(" ", "+")
            family_params.append(f"family={encoded}:wght@100;200;300;400;500;600;700;800;900")
        params = "&".join(family_params)
        font_imports.append(f"@import url('https://fonts.googleapis.com/css2?{params}&display=swap');")

    # Generate CSS with @layer for framework conflict prevention
    lines = [
        "/* ==========================================================",
        "   AUTO-GENERATED from Figma design data — DO NOT EDIT",
        "   Source: figma-export/design_data.json",
        "   Import this file in your implementation to use Figma styles.",
        "   ========================================================== */",
        "",
    ]

    # Font imports (must be at top)
    for imp in font_imports:
        lines.append(imp)
    if font_imports:
        lines.append("")

    # Use @layer to ensure Figma styles take priority over framework resets
    lines.append("@layer base, framework, figma;")
    lines.append("")
    lines.append("@layer figma {")
    lines.append("")

    for rule in all_rules:
        if not rule["css_rules"]:
            continue
        lines.append(f"  /* Figma: {rule['node_name']} */")
        lines.append(f"  .{rule['class_name']} {{")
        for css_rule in rule["css_rules"]:
            lines.append(f"    {css_rule};")

        # Auto-generate ::before for gradient border + border-radius
        if rule.get("gradient_border"):
            br_val = None
            for r in rule["css_rules"]:
                if r.startswith("border-radius:"):
                    br_val = r.split(":")[1].strip()
                    break
            if br_val:
                lines.append("  }")
                lines.append(f"  .{rule['class_name']}::before {{")
                lines.append("    content: '';")
                lines.append("    position: absolute;")
                lines.append("    inset: 0;")
                lines.append(f"    border-radius: {br_val};")
                lines.append("    padding: 2px;")
                lines.append(f"    background: {rule['gradient_border']};")
                lines.append("    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);")
                lines.append("    -webkit-mask-composite: xor;")
                lines.append("    mask-composite: exclude;")
                lines.append("    pointer-events: none;")
        lines.append("  }")
        lines.append("")

    lines.append("} /* end @layer figma */")
    lines.append("")

    css_content = "\n".join(lines)

    # Write CSS file
    css_path = out_dir / "figma_styles.css"
    css_path.write_text(css_content, encoding="utf-8")

    # Generate component map with full asset/structure info
    component_map = []
    for rule in all_rules:
        entry: dict = {
            "figma_name": rule["node_name"],
            "css_class": rule["class_name"],
        }
        if rule.get("asset_path"):
            entry["asset_path"] = rule["asset_path"]
            entry["asset_width"] = rule.get("asset_width")
            entry["asset_height"] = rule.get("asset_height")
            entry["html_hint"] = f'<img src="{rule["asset_path"]}" alt="{rule["node_name"]}" width="{rule.get("asset_width", "")}" height="{rule.get("asset_height", "")}" class="{rule["class_name"]}">'
        if rule.get("children_order"):
            entry["children_order"] = rule["children_order"]
        elif rule.get("children_classes"):
            entry["children"] = rule["children_classes"]
        component_map.append(entry)

    map_path = out_dir / "component_map.json"
    map_path.write_text(json.dumps(component_map, indent=2, ensure_ascii=False), encoding="utf-8")

    # NOTE: skeleton.html is NOT generated here. The figma-converter LLM agent
    # generates proper semantic HTML by interpreting the render PNGs visually.
    # Programmatic tree-walking cannot reproduce complex design layouts.

    # Generate responsive CSS (if multiple viewports)
    responsive_css = generate_responsive_css(design_data, assets_by_node, assets_by_id)
    if responsive_css:
        responsive_path = out_dir / "figma_responsive.css"
        responsive_path.write_text(responsive_css, encoding="utf-8")
        lines.append("")
        lines.append(responsive_css)
        css_content = "\n".join(lines)
        css_path.write_text(css_content, encoding="utf-8")

    # Generate interaction state CSS
    state_css = generate_state_css(design_data)
    if state_css:
        lines.append("")
        lines.append(state_css)
        css_content = "\n".join(lines)
        css_path.write_text(css_content, encoding="utf-8")

    return css_content, component_map


# ── HTML Skeleton Generator ─────────────────────────────────────────


def generate_html_skeleton(
    design_data: dict,
    rules: list[dict],
    assets_by_node: dict[str, str],
) -> str:
    """Generate a complete HTML skeleton from the Figma node tree.

    Includes all text content, asset references, CSS class names,
    and Google Fonts links.
    """
    # Collect fonts for Google Fonts link
    fonts: set[str] = set()
    for rule in rules:
        for css_rule in rule.get("css_rules", []):
            if css_rule.startswith("font-family:"):
                font = css_rule.split(":", 1)[1].strip().strip("'\"").rstrip(";")
                if font and font.lower() not in ("sans-serif", "serif", "monospace"):
                    fonts.add(font)

    font_link = ""
    if fonts:
        family_params = []
        for f in sorted(fonts):
            family_params.append(f"family={f.replace(' ', '+')}:wght@100;200;300;400;500;600;700;800;900")
        font_link = f'  <link rel="preconnect" href="https://fonts.googleapis.com">\n' \
                    f'  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n' \
                    f'  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?{"&".join(family_params)}&display=swap">'

    html_lines = [
        "<!DOCTYPE html>",
        '<!-- AUTO-GENERATED from Figma — copy this structure to your implementation -->',
        '<html lang="en">',
        "<head>",
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
    ]
    if font_link:
        html_lines.append(font_link)
    html_lines.extend([
        '  <link rel="stylesheet" href="figma_styles.css">',
        "  <title>Figma Skeleton</title>",
        "</head>",
        "<body>",
    ])

    # Build a class lookup
    rules_by_name: dict[str, dict] = {r["node_name"]: r for r in rules}

    def _node_to_html(node: dict, indent: int = 1) -> None:
        name = node.get("name", "")
        node_type = node.get("type", "")
        prefix = "  " * indent

        if not name or node_type in ("GROUP",):
            for child in node.get("children", []):
                _node_to_html(child, indent)
            return

        rule = rules_by_name.get(name)
        class_name = rule["class_name"] if rule else _slugify_class(name)
        asset_path = assets_by_node.get(name)
        ts = node.get("text_style", {})
        text = ts.get("text_content", "") if ts else ""
        children = node.get("children", [])

        # Determine HTML tag
        # Assets without children → <img>. Assets WITH children → container (decompose).
        if asset_path and not children:
            w = node.get("width", "")
            h = node.get("height", "")
            html_lines.append(f'{prefix}<img src="{asset_path}" alt="{name}" '
                              f'width="{w}" height="{h}" class="{class_name}">')
            return

        if node_type == "TEXT" and text:
            # Choose tag based on font size
            fs = ts.get("font_size_px", 16) if ts else 16
            if fs >= 32:
                tag = "h1"
            elif fs >= 24:
                tag = "h2"
            elif fs >= 20:
                tag = "h3"
            elif fs >= 14:
                tag = "p"
            else:
                tag = "span"
            html_lines.append(f'{prefix}<{tag} class="{class_name}">{text}</{tag}>')
            return

        # Container elements
        name_lower = name.lower()
        if "nav" in name_lower or "header" in name_lower:
            tag = "nav"
        elif "footer" in name_lower:
            tag = "footer"
        elif "main" in name_lower or "content" in name_lower:
            tag = "main"
        elif "section" in name_lower:
            tag = "section"
        elif "button" in name_lower or "btn" in name_lower:
            tag = "button"
        elif "input" in name_lower or "field" in name_lower:
            tag = "input"
        elif "link" in name_lower or "anchor" in name_lower:
            tag = "a"
        else:
            tag = "div"

        if tag == "input":
            html_lines.append(f'{prefix}<input class="{class_name}" placeholder="{name}">')
            return

        if children:
            html_lines.append(f'{prefix}<{tag} class="{class_name}">')
            for child in children:
                _node_to_html(child, indent + 1)
            html_lines.append(f'{prefix}</{tag}>')
        else:
            content = text or name
            html_lines.append(f'{prefix}<{tag} class="{class_name}">{content}</{tag}>')

    for frame in design_data.get("frames", []):
        tree = frame.get("tree", {})
        breakpoint = frame.get("breakpoint", "desktop")
        html_lines.append(f'  <!-- Frame: {tree.get("name", "")} ({breakpoint}) -->')
        _node_to_html(tree)

    html_lines.extend(["</body>", "</html>", ""])
    return "\n".join(html_lines)


# ── Responsive CSS Generator ────────────────────────────────────────


def generate_responsive_css(
    design_data: dict,
    assets_by_node: dict[str, str],
    assets_by_id: dict[str, str] | None = None,
) -> str:
    """Generate @media queries for different Figma viewport frames."""
    frames = design_data.get("frames", [])
    if len(frames) <= 1:
        return ""

    breakpoint_map = {
        "mobile": "@media (max-width: 767px)",
        "tablet": "@media (min-width: 768px) and (max-width: 1023px)",
        "desktop": "@media (min-width: 1024px)",
    }

    lines = [
        "",
        "/* ── Responsive overrides (per-viewport) ────────────────── */",
        "",
    ]

    for frame in frames:
        bp = frame.get("breakpoint", "desktop")
        media = breakpoint_map.get(bp)
        if not media:
            continue

        tree = frame.get("tree", {})
        frame_rules = generate_node_css(tree, assets_by_node, assets_by_id=assets_by_id)

        if not frame_rules:
            continue

        lines.append(f"/* {bp} viewport */")
        lines.append(f"{media} {{")
        for rule in frame_rules:
            if not rule["css_rules"]:
                continue
            lines.append(f"  .{rule['class_name']} {{")
            for css_rule in rule["css_rules"]:
                lines.append(f"    {css_rule};")
            lines.append("  }")
        lines.append("}")
        lines.append("")

    return "\n".join(lines)


# ── Interaction State CSS Generator ─────────────────────────────────


def generate_state_css(design_data: dict) -> str:
    """Generate CSS pseudo-class rules from Figma interaction states."""
    summary = design_data.get("summary", {})
    states = summary.get("interaction_states", [])
    if not states:
        return ""

    state_to_pseudo = {
        "hover": ":hover",
        "focus": ":focus",
        "active": ":active",
        "pressed": ":active",
        "disabled": ":disabled",
        "selected": "[aria-selected='true']",
        "checked": ":checked",
    }

    lines = [
        "",
        "/* ── Interaction states (from Figma variants) ────────────── */",
        "",
    ]

    for state in states:
        state_name = state.get("state", "")
        pseudo = state_to_pseudo.get(state_name)
        if not pseudo:
            continue

        element_name = state.get("name", "")
        # Derive base class from element name (remove state part)
        base_name = re.sub(r"[\s/]*(?:hover|focus|active|pressed|disabled|selected|checked)[\s/]*",
                           "", element_name, flags=re.IGNORECASE).strip(" /")
        if not base_name:
            continue

        class_name = _slugify_class(base_name)
        colors = state.get("colors", [])

        if colors:
            lines.append(f"/* Figma: {element_name} */")
            lines.append(f".{class_name}{pseudo} {{")
            # Use first color as background, second as text if available
            if len(colors) >= 1:
                lines.append(f"  background-color: {colors[0]};")
            if len(colors) >= 2:
                lines.append(f"  color: {colors[1]};")
            lines.append("}")
            lines.append("")

    return "\n".join(lines) if len(lines) > 3 else ""


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Generate CSS from Figma design data")
    parser.add_argument("--project-path", default=".", help="Project root")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    project_path = Path(args.project_path).resolve()
    dd_path = project_path / "figma-export" / "design_data.json"

    if not dd_path.exists():
        print("No figma-export/design_data.json found", file=sys.stderr)
        return 1

    try:
        design_data = json.loads(dd_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading design data: {e}", file=sys.stderr)
        return 2

    out_dir = project_path / "figma-export"
    css_content, component_map = generate_css_file(design_data, out_dir)

    print(f"Generated figma-export/figma_styles.css ({len(component_map)} rules)", file=sys.stderr)
    print(f"Generated figma-export/component_map.json", file=sys.stderr)

    # Print summary
    assets = [c for c in component_map if c.get("asset_path")]
    gradients = sum(1 for line in css_content.splitlines() if "gradient(" in line)
    shadows = sum(1 for line in css_content.splitlines() if "box-shadow:" in line)
    print(f"  Components: {len(component_map)}", file=sys.stderr)
    print(f"  With assets: {len(assets)}", file=sys.stderr)
    print(f"  Gradients: {gradients}", file=sys.stderr)
    print(f"  Shadows: {shadows}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
