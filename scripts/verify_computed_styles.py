#!/usr/bin/env python3
"""Verify computed styles of rendered implementation against Figma tokens.

Unlike regex-based source code scanning, this script:
1. Renders the implementation in a REAL browser (Playwright/Chromium)
2. Extracts ACTUAL computed CSS values from rendered DOM elements
3. Compares against Figma design_data.json tokens

This catches CSS cascade conflicts, specificity overrides, inheritance,
calc() results, and browser defaults that static analysis misses.

Requires: playwright (pip install playwright && playwright install chromium)

Exit codes:
  0 — all computed styles match Figma tokens
  1 — mismatches found
  2 — usage error or missing dependency
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _playwright_importable() -> bool:
    """True iff `playwright.sync_api` imports (lazy — never at module load)."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _check_playwright() -> bool:
    """Report whether Playwright is available; auto-install only on opt-in.

    A review/CI gate must never mutate its environment or reach the network as a
    silent side effect (ISSUE-049). When Playwright is missing, the heavy
    `pip install playwright` + `playwright install chromium` provisioning runs
    ONLY when the operator sets ``KIT_ALLOW_BROWSER_INSTALL=1``. Otherwise the
    gate reports "browser unavailable" to stderr and returns False so the caller
    takes its existing skip/degrade path. The diagnostic goes to stderr; stdout
    stays clean for machine-readable output.
    """
    if _playwright_importable():
        return True

    if os.environ.get("KIT_ALLOW_BROWSER_INSTALL") != "1":
        print(
            "browser unavailable — skipping computed-style verification "
            "(set KIT_ALLOW_BROWSER_INSTALL=1 to auto-install Playwright + Chromium)",
            file=sys.stderr,
        )
        return False

    # Opted in: heavy provisioning (network + subprocess) is expected here.
    try:
        subprocess.run(["pip", "install", "playwright"], capture_output=True, timeout=60)
        subprocess.run(["playwright", "install", "chromium"], capture_output=True, timeout=120)
    except Exception:
        return False
    return _playwright_importable()


# ── Build Figma token reference ─────────────────────────────────────


def _normalize_color(c: str) -> str:
    """Normalize color to uppercase 6-digit hex."""
    c = c.strip().upper()
    if c.startswith("#"):
        if len(c) == 4:
            return f"#{c[1]*2}{c[2]*2}{c[3]*2}"
        return c[:7]  # Strip alpha if present
    return c


def build_figma_reference(design_data: dict) -> dict:
    """Build lookup sets from Figma design_data for comparison."""
    summary = design_data.get("summary", {})

    colors = set()
    for c in summary.get("colors", []):
        colors.add(_normalize_color(c))
    # Always allow black, white, transparent
    colors.update({"#000000", "#FFFFFF"})

    fonts = set()
    for ts in summary.get("text_styles", []):
        if ts.get("font_family"):
            fonts.add(ts["font_family"].lower())

    font_sizes = set()
    for ts in summary.get("text_styles", []):
        if ts.get("font_size_px"):
            font_sizes.add(float(ts["font_size_px"]))

    font_weights = {int(w) for w in summary.get("font_weights", [])}
    spacings = {float(s) for s in summary.get("spacings", [])}
    radii = {float(r) for r in summary.get("border_radii", [])}

    return {
        "colors": colors,
        "fonts": fonts,
        "font_sizes": font_sizes,
        "font_weights": font_weights,
        "spacings": spacings,
        "radii": radii,
    }


# ── Extract computed styles from rendered page ──────────────────────

# JavaScript to extract computed styles from all visible elements
_EXTRACT_JS = """
() => {
    const results = [];
    const elements = document.querySelectorAll('*');
    const bodyRect = document.body.getBoundingClientRect();

    for (const el of elements) {
        const rect = el.getBoundingClientRect();
        // Skip invisible/tiny elements
        if (rect.width < 2 || rect.height < 2) continue;
        // Skip elements outside viewport
        if (rect.bottom < 0 || rect.top > window.innerHeight * 3) continue;

        const cs = window.getComputedStyle(el);
        const tag = el.tagName.toLowerCase();

        // Skip script/style/meta
        if (['script', 'style', 'meta', 'link', 'head', 'html'].includes(tag)) continue;

        const entry = {
            tag: tag,
            className: el.className?.toString()?.slice(0, 100) || '',
            text: el.textContent?.trim()?.slice(0, 50) || '',
            x: Math.round(rect.x),
            y: Math.round(rect.y),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
            styles: {
                color: cs.color,
                backgroundColor: cs.backgroundColor,
                fontSize: cs.fontSize,
                fontFamily: cs.fontFamily,
                fontWeight: cs.fontWeight,
                lineHeight: cs.lineHeight,
                letterSpacing: cs.letterSpacing,
                padding: cs.padding,
                margin: cs.margin,
                borderRadius: cs.borderRadius,
                borderWidth: cs.borderWidth,
                borderColor: cs.borderColor,
                opacity: cs.opacity,
                display: cs.display,
                flexDirection: cs.flexDirection,
                justifyContent: cs.justifyContent,
                alignItems: cs.alignItems,
                position: cs.position,
                overflow: cs.overflow,
            }
        };
        results.push(entry);
    }
    return results;
}
"""


def extract_computed_styles(url: str, viewport_width: int = 1440) -> list[dict]:
    """Render a page and extract computed styles from all visible elements."""
    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": viewport_width, "height": 900},
            device_scale_factor=2,
        )
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.evaluate("() => document.fonts.ready")
        page.wait_for_timeout(300)

        results = page.evaluate(_EXTRACT_JS)

        page.close()
        browser.close()

    return results


# ── Compare computed styles against Figma ───────────────────────────


def _parse_px(value: str) -> float | None:
    """Parse '16px' → 16.0."""
    m = re.match(r"([\d.]+)px", value)
    return float(m.group(1)) if m else None


def _rgb_to_hex(rgb_str: str) -> str | None:
    """Convert 'rgb(59, 130, 246)' or 'rgba(...)' to '#3B82F6'."""
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", rgb_str)
    if not m:
        return None
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"#{r:02X}{g:02X}{b:02X}"


def _value_close(val: float, allowed: set[float], tolerance: float = 2.0) -> bool:
    return any(abs(val - a) <= tolerance for a in allowed)


def _color_close(hex1: str, hex2_set: set[str], tolerance: int = 15) -> bool:
    """Check if hex color is close to any in the set."""
    if hex1 in hex2_set:
        return True
    try:
        r1 = int(hex1[1:3], 16)
        g1 = int(hex1[3:5], 16)
        b1 = int(hex1[5:7], 16)
    except (ValueError, IndexError):
        return True  # Can't parse, skip

    for h2 in hex2_set:
        try:
            r2 = int(h2[1:3], 16)
            g2 = int(h2[3:5], 16)
            b2 = int(h2[5:7], 16)
            if abs(r1 - r2) <= tolerance and abs(g1 - g2) <= tolerance and abs(b1 - b2) <= tolerance:
                return True
        except (ValueError, IndexError):
            continue
    return False


def compare_computed_vs_figma(
    elements: list[dict],
    figma_ref: dict,
) -> dict:
    """Compare rendered computed styles against Figma tokens."""
    violations: list[dict] = []

    # Skip common transparent/default colors
    transparent = {"rgba(0, 0, 0, 0)", "transparent", "rgb(0, 0, 0)"}

    for el in elements:
        styles = el.get("styles", {})
        tag = el.get("tag", "")
        identifier = el.get("className", "") or el.get("text", "")[:30] or tag

        # Color check
        for prop in ("color", "backgroundColor", "borderColor"):
            val = styles.get(prop, "")
            if not val or val in transparent:
                continue
            hex_val = _rgb_to_hex(val)
            if hex_val and figma_ref["colors"] and not _color_close(hex_val, figma_ref["colors"]):
                violations.append({
                    "element": f"<{tag}> .{identifier}",
                    "property": prop,
                    "computed": val,
                    "hex": hex_val,
                    "message": f"Computed {prop} {hex_val} not in Figma palette",
                })

        # Font family
        font = styles.get("fontFamily", "")
        if font and figma_ref["fonts"]:
            # Extract first font from the font stack
            first_font = font.split(",")[0].strip().strip("'\"").lower()
            generic = {"sans-serif", "serif", "monospace", "system-ui", "arial", "helvetica", "times new roman"}
            if first_font not in generic and first_font not in figma_ref["fonts"]:
                violations.append({
                    "element": f"<{tag}> .{identifier}",
                    "property": "fontFamily",
                    "computed": first_font,
                    "message": f"Computed font '{first_font}' not in Figma",
                })

        # Font size
        fs = _parse_px(styles.get("fontSize", ""))
        if fs and figma_ref["font_sizes"] and not _value_close(fs, figma_ref["font_sizes"]):
            violations.append({
                "element": f"<{tag}> .{identifier}",
                "property": "fontSize",
                "computed": f"{fs}px",
                "message": f"Computed font-size {fs}px not in Figma (allowed: {sorted(figma_ref['font_sizes'])})",
            })

        # Font weight
        fw = styles.get("fontWeight", "")
        if fw and figma_ref["font_weights"]:
            try:
                fw_int = int(fw)
                if fw_int not in figma_ref["font_weights"]:
                    violations.append({
                        "element": f"<{tag}> .{identifier}",
                        "property": "fontWeight",
                        "computed": str(fw_int),
                        "message": f"Computed font-weight {fw_int} not in Figma",
                    })
            except ValueError:
                pass

        # Border radius
        br = _parse_px(styles.get("borderRadius", ""))
        if br and br > 0 and figma_ref["radii"] and not _value_close(br, figma_ref["radii"]):
            violations.append({
                "element": f"<{tag}> .{identifier}",
                "property": "borderRadius",
                "computed": f"{br}px",
                "message": f"Computed border-radius {br}px not in Figma",
            })

    # Deduplicate (same property+value across many elements → report once)
    seen: set[str] = set()
    unique_violations: list[dict] = []
    for v in violations:
        key = f"{v['property']}:{v.get('hex', v.get('computed', ''))}"
        if key not in seen:
            seen.add(key)
            unique_violations.append(v)

    return {
        "violations": unique_violations,
        "summary": {
            "elements_checked": len(elements),
            "total_violations": len(unique_violations),
            "color_violations": sum(1 for v in unique_violations if v["property"] in ("color", "backgroundColor", "borderColor")),
            "font_violations": sum(1 for v in unique_violations if "font" in v["property"].lower()),
            "spacing_violations": sum(1 for v in unique_violations if v["property"] in ("borderRadius",)),
        },
        "compliant": len(unique_violations) == 0,
    }


# ── Per-node matching: Figma text node ↔ DOM element ────────────────


def extract_figma_text_nodes(design_data: dict) -> list[dict]:
    """Extract all TEXT nodes from Figma design_data with their expected styles.

    Returns list of {text, color, font_size, font_weight, font_family}.
    """
    nodes: list[dict] = []

    def _walk(node: dict) -> None:
        ts = node.get("text_style")
        if ts and ts.get("text_content"):
            text = ts["text_content"].strip()
            if len(text) >= 2:  # skip single chars
                nodes.append({
                    "text": text,
                    "color": _normalize_color(ts["color"]) if ts.get("color") else None,
                    "font_size": float(ts["font_size_px"]) if ts.get("font_size_px") else None,
                    "font_weight": int(ts["font_weight"]) if ts.get("font_weight") else None,
                    "font_family": ts.get("font_family", "").lower() if ts.get("font_family") else None,
                    "text_align": ts.get("text_align"),
                })
        for child in node.get("children", []):
            _walk(child)

    for frame in design_data.get("frames", []):
        _walk(frame.get("tree", {}))

    return nodes


def match_and_compare_per_node(
    figma_nodes: list[dict],
    dom_elements: list[dict],
) -> list[dict]:
    """Match Figma text nodes to DOM elements by text content, then compare styles.

    For each Figma text node, find the DOM element whose text matches,
    then compare color, font-size, font-weight per node.
    """
    violations: list[dict] = []

    # Build DOM lookup by text content (first 30 chars → element)
    dom_by_text: dict[str, dict] = {}
    for el in dom_elements:
        text = (el.get("text") or "").strip()
        if text and len(text) >= 2:
            # Use first 30 chars as key (text might be truncated in JS extraction)
            key = text[:30].lower()
            if key not in dom_by_text:
                dom_by_text[key] = el

    for fnode in figma_nodes:
        ftext = fnode["text"]
        # Try to find matching DOM element
        key = ftext[:30].lower()
        # Also try without line breaks
        key_noline = ftext.replace("\n", "").replace("\r", "")[:30].lower()

        dom_el = dom_by_text.get(key) or dom_by_text.get(key_noline)
        if not dom_el:
            continue

        styles = dom_el.get("styles", {})
        label = f'"{ftext[:40]}"'

        # Color comparison
        if fnode["color"]:
            dom_color_raw = styles.get("color", "")
            dom_color = _rgb_to_hex(dom_color_raw)
            if dom_color and not _color_close(dom_color, {fnode["color"]}, tolerance=10):
                violations.append({
                    "element": label,
                    "property": "color",
                    "expected": fnode["color"],
                    "computed": dom_color,
                    "message": f'{label} color: expected {fnode["color"]}, got {dom_color}',
                })

        # Font size comparison
        if fnode["font_size"]:
            dom_fs = _parse_px(styles.get("fontSize", ""))
            if dom_fs and abs(dom_fs - fnode["font_size"]) > 2:
                violations.append({
                    "element": label,
                    "property": "fontSize",
                    "expected": f'{fnode["font_size"]}px',
                    "computed": f'{dom_fs}px',
                    "message": f'{label} font-size: expected {fnode["font_size"]}px, got {dom_fs}px',
                })

        # Font weight comparison
        if fnode["font_weight"]:
            dom_fw = styles.get("fontWeight", "")
            try:
                dom_fw_int = int(dom_fw)
                if dom_fw_int != fnode["font_weight"]:
                    violations.append({
                        "element": label,
                        "property": "fontWeight",
                        "expected": str(fnode["font_weight"]),
                        "computed": str(dom_fw_int),
                        "message": f'{label} font-weight: expected {fnode["font_weight"]}, got {dom_fw_int}',
                    })
            except (ValueError, TypeError):
                pass

    return violations


# ── CLI ─────────────────────────────────────────────────────────────


def _check_dev_server(port: int) -> bool:
    import urllib.request
    import urllib.error
    try:
        urllib.request.urlopen(f"http://localhost:{port}", timeout=3)
        return True
    except (urllib.error.URLError, OSError):
        return False


def find_implementation_url(project_path: Path) -> str | None:
    """Find implementation URL (dev server or static file)."""
    for port in [3000, 5173, 8080, 4200, 3001, 5174]:
        if _check_dev_server(port):
            return f"http://localhost:{port}"
    for candidate in ["dist/index.html", "build/index.html", "out/index.html", "public/index.html", "index.html"]:
        fp = project_path / candidate
        if fp.exists():
            return f"file://{fp.resolve()}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify computed styles against Figma tokens")
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--design-data", default=None)
    parser.add_argument("--url", default=None, help="Implementation URL (auto-detected if omitted)")
    parser.add_argument("--viewport", type=int, default=1440)
    parser.add_argument("--json", action="store_true", dest="json_output")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    project_path = Path(args.project_path).resolve()
    dd_path = Path(args.design_data) if args.design_data else project_path / "figma-export" / "design_data.json"

    if not dd_path.exists():
        print("PASS: No design_data.json — computed style check skipped")
        return 0

    if not _check_playwright():
        has_figma = dd_path.exists()
        if has_figma:
            print("FAIL: Playwright required for computed style verification but not installable")
            return 1
        print("SKIP: Playwright not available")
        return 0

    try:
        design_data = json.loads(dd_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: cannot read design data: {e}", file=sys.stderr)
        return 2

    url = args.url or find_implementation_url(project_path)
    if not url:
        print("FAIL: No implementation URL found — build the project or start dev server")
        return 1

    figma_ref = build_figma_reference(design_data)
    print(f"Extracting computed styles from {url} at {args.viewport}px...")

    elements = extract_computed_styles(url, args.viewport)
    print(f"  Extracted {len(elements)} visible element(s)")

    # Phase 1: Palette-level check (existing)
    result = compare_computed_vs_figma(elements, figma_ref)

    # Phase 2: Per-node matching (NEW — catches per-element style mismatches)
    figma_nodes = extract_figma_text_nodes(design_data)
    node_violations = match_and_compare_per_node(figma_nodes, elements)

    # Merge results
    all_violations = result["violations"] + node_violations
    total = len(all_violations)
    compliant = total == 0

    if args.json_output:
        print(json.dumps({
            "palette_violations": result["violations"],
            "node_violations": node_violations,
            "summary": {**result["summary"], "node_violations": len(node_violations), "total_violations": total},
            "compliant": compliant,
        }, indent=2))
    else:
        s = result["summary"]
        print(f"  Compared against {len(figma_ref['colors'])} colors, {len(figma_ref['fonts'])} fonts, {len(figma_ref['font_sizes'])} sizes")
        print(f"  Matched {len(figma_nodes)} Figma text nodes against DOM")
        print()

        if compliant:
            print("PASS: All computed styles match Figma (palette + per-node)")
        else:
            if result["violations"]:
                print(f"  Palette violations ({s['total_violations']}):")
                for v in result["violations"][:10]:
                    print(f"    {v['element']} → {v['message']}")
            if node_violations:
                print(f"  Per-node violations ({len(node_violations)}):")
                for v in node_violations[:15]:
                    print(f"    {v['message']}")
                if len(node_violations) > 15:
                    print(f"    ... and {len(node_violations) - 15} more")
            print(f"\n  FAIL: {total} total violation(s)")

    return 0 if compliant else 1


if __name__ == "__main__":
    raise SystemExit(main())
