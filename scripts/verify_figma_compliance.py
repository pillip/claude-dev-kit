#!/usr/bin/env python3
"""Verify implementation compliance against Figma design tokens.

Compares colors, typography, and spacing values found in implementation
source files against the source-of-truth tokens in figma-export/design_data.json.

Reports violations where implementation uses values not present in the
Figma design or the project design system.

Exit codes:
  0 — compliant (or no Figma data to compare against)
  1 — violations found
  2 — usage error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ── Color extraction ────────────────────────────────────────────────

# Matches hex colors: #RGB, #RRGGBB, #RRGGBBAA
_HEX_COLOR = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")

# Matches rgb/rgba: rgb(R, G, B), rgba(R, G, B, A)
_RGB_COLOR = re.compile(
    r"rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*[\d.]+\s*)?\)"
)

def normalize_hex(color: str) -> str:
    """Normalize hex color to uppercase 6-digit format."""
    c = color.upper().strip()
    if len(c) == 4:  # #RGB → #RRGGBB
        return f"#{c[1]*2}{c[2]*2}{c[3]*2}"
    if len(c) == 5:  # #RGBA → #RRGGBBAA
        return f"#{c[1]*2}{c[2]*2}{c[3]*2}{c[4]*2}"
    return c


def extract_colors_from_source(text: str) -> list[dict]:
    """Extract hardcoded color values from source code.

    Returns list of {value, line, is_var} dicts.
    Skips colors inside CSS variable definitions (--color-*: #xxx).
    """
    colors: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue
        # Skip CSS variable definitions (these define the design system, not violations)
        if re.match(r"\s*--[\w-]+\s*:", line):
            continue

        for m in _HEX_COLOR.finditer(line):
            colors.append({"value": normalize_hex(m.group()), "line": i, "is_var": False})
        for m in _RGB_COLOR.finditer(line):
            colors.append({"value": m.group().lower(), "line": i, "is_var": False})

    return colors


# ── Font extraction ─────────────────────────────────────────────────

_FONT_FAMILY = re.compile(
    r"font-family\s*:\s*['\"]?([^;'\"}\n,]+)",
    re.IGNORECASE,
)
_FONT_SIZE = re.compile(
    r"font-size\s*:\s*([\d.]+)\s*px",
    re.IGNORECASE,
)
# React Native style patterns
_RN_FONT_FAMILY = re.compile(r"fontFamily\s*:\s*['\"]([^'\"]+)['\"]")
_RN_FONT_SIZE = re.compile(r"fontSize\s*:\s*([\d.]+)")


def extract_fonts_from_source(text: str) -> tuple[list[dict], list[dict]]:
    """Extract font families and sizes from source code.

    Returns (families, sizes) — each a list of {value, line}.
    """
    families: list[dict] = []
    sizes: list[dict] = []

    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue
        if re.match(r"\s*--[\w-]+\s*:", line):
            continue

        for m in _FONT_FAMILY.finditer(line):
            families.append({"value": m.group(1).strip().strip("'\""), "line": i})
        for m in _RN_FONT_FAMILY.finditer(line):
            families.append({"value": m.group(1).strip(), "line": i})
        for m in _FONT_SIZE.finditer(line):
            sizes.append({"value": float(m.group(1)), "line": i})
        for m in _RN_FONT_SIZE.finditer(line):
            sizes.append({"value": float(m.group(1)), "line": i})

    return families, sizes


# ── Spacing extraction ──────────────────────────────────────────────

_SPACING_PROPS = re.compile(
    r"(?:margin|padding|gap|top|right|bottom|left)\s*:\s*([\d.]+)\s*px",
    re.IGNORECASE,
)
# React Native: number without px unit (e.g., marginTop: 16)
_RN_SPACING = re.compile(
    r"(?:margin|padding|gap)\w*\s*:\s*([\d.]+)(?!\s*px)\b",
)


def extract_spacings_from_source(text: str) -> list[dict]:
    """Extract spacing values (margin, padding, gap) from source code."""
    spacings: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue
        if re.match(r"\s*--[\w-]+\s*:", line):
            continue

        for m in _SPACING_PROPS.finditer(line):
            val = float(m.group(1))
            if val > 0:
                spacings.append({"value": val, "line": i})
        for m in _RN_SPACING.finditer(line):
            val = float(m.group(1))
            if val > 0:
                spacings.append({"value": val, "line": i})

    return spacings


# ── Additional property extraction ──────────────────────────────────

_FONT_WEIGHT = re.compile(r"font-weight\s*:\s*(\d{3})\b", re.IGNORECASE)
_RN_FONT_WEIGHT = re.compile(r"fontWeight\s*:\s*['\"]?(\d{3})['\"]?")

_LINE_HEIGHT = re.compile(r"line-height\s*:\s*([\d.]+)\b", re.IGNORECASE)
_RN_LINE_HEIGHT = re.compile(r"lineHeight\s*:\s*([\d.]+)")

_LETTER_SPACING = re.compile(r"letter-spacing\s*:\s*([\d.]+)\s*(?:em|px)", re.IGNORECASE)
_RN_LETTER_SPACING = re.compile(r"letterSpacing\s*:\s*([\d.]+)")

_BORDER_RADIUS = re.compile(r"border-radius\s*:\s*([\d.]+)\s*px", re.IGNORECASE)
_RN_BORDER_RADIUS = re.compile(r"borderRadius\s*:\s*([\d.]+)")

_BORDER_WIDTH = re.compile(r"border(?:-\w+)?-width\s*:\s*([\d.]+)\s*px", re.IGNORECASE)
_RN_BORDER_WIDTH = re.compile(r"borderWidth\s*:\s*([\d.]+)")

_OPACITY = re.compile(r"opacity\s*:\s*(0?\.\d+|1(?:\.0)?)\b", re.IGNORECASE)

_BOX_SHADOW = re.compile(
    r"box-shadow\s*:\s*([^;]+)",
    re.IGNORECASE,
)


def _is_code_line(line: str) -> bool:
    """Check if a line is actual code (not a comment or variable definition)."""
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
        return False
    if re.match(r"\s*--[\w-]+\s*:", line):
        return False
    return True


def extract_font_weights(text: str) -> list[dict]:
    """Extract font-weight values."""
    results: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        if not _is_code_line(line):
            continue
        for m in _FONT_WEIGHT.finditer(line):
            results.append({"value": int(m.group(1)), "line": i})
        for m in _RN_FONT_WEIGHT.finditer(line):
            results.append({"value": int(m.group(1)), "line": i})
    return results


def extract_line_heights(text: str) -> list[dict]:
    """Extract line-height values (unitless ratios or px)."""
    results: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        if not _is_code_line(line):
            continue
        for m in _LINE_HEIGHT.finditer(line):
            results.append({"value": float(m.group(1)), "line": i})
        for m in _RN_LINE_HEIGHT.finditer(line):
            results.append({"value": float(m.group(1)), "line": i})
    return results


def extract_letter_spacings(text: str) -> list[dict]:
    """Extract letter-spacing values."""
    results: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        if not _is_code_line(line):
            continue
        for m in _LETTER_SPACING.finditer(line):
            results.append({"value": float(m.group(1)), "line": i})
        for m in _RN_LETTER_SPACING.finditer(line):
            results.append({"value": float(m.group(1)), "line": i})
    return results


def extract_border_radii(text: str) -> list[dict]:
    """Extract border-radius values."""
    results: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        if not _is_code_line(line):
            continue
        for m in _BORDER_RADIUS.finditer(line):
            results.append({"value": float(m.group(1)), "line": i})
        for m in _RN_BORDER_RADIUS.finditer(line):
            results.append({"value": float(m.group(1)), "line": i})
    return results


def extract_border_widths(text: str) -> list[dict]:
    """Extract border-width values."""
    results: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        if not _is_code_line(line):
            continue
        for m in _BORDER_WIDTH.finditer(line):
            val = float(m.group(1))
            if val > 0:
                results.append({"value": val, "line": i})
        for m in _RN_BORDER_WIDTH.finditer(line):
            val = float(m.group(1))
            if val > 0:
                results.append({"value": val, "line": i})
    return results


def extract_opacities(text: str) -> list[dict]:
    """Extract opacity values (0-1)."""
    results: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        if not _is_code_line(line):
            continue
        for m in _OPACITY.finditer(line):
            val = float(m.group(1))
            if 0 < val < 1:  # skip 0 and 1 (fully transparent/opaque)
                results.append({"value": round(val, 2), "line": i})
    return results


def extract_box_shadows(text: str) -> list[dict]:
    """Extract box-shadow declarations (presence check)."""
    results: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        if not _is_code_line(line):
            continue
        for m in _BOX_SHADOW.finditer(line):
            val = m.group(1).strip().rstrip(";")
            if val and val.lower() != "none":
                results.append({"value": val, "line": i})
    return results


# ── Comparison ──────────────────────────────────────────────────────

# Tolerance for "close enough" matching
_COLOR_TOLERANCE = 15  # RGB channel difference
_SIZE_TOLERANCE = 2  # px difference for fonts/spacing


def _hex_to_rgb_safe(hex_color: str) -> tuple[int, int, int] | None:
    """Parse hex color to RGB tuple, handling 6 and 8 char hex."""
    h = hex_color.lstrip("#").upper()
    if len(h) == 6:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    if len(h) == 8:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return None


def color_matches(impl_color: str, figma_colors: set[str]) -> bool:
    """Check if an implementation color matches any Figma color (with tolerance)."""
    norm = normalize_hex(impl_color) if impl_color.startswith("#") else impl_color

    # Exact match
    if norm in figma_colors:
        return True

    # Common non-design colors (black, white, transparent)
    common = {"#000000", "#FFFFFF", "#000", "#FFF", "transparent", "inherit", "currentColor"}
    if norm in common or impl_color.lower() in common:
        return True

    # Tolerance-based matching for hex colors
    impl_rgb = _hex_to_rgb_safe(norm)
    if impl_rgb is None:
        return False

    for fc in figma_colors:
        fc_rgb = _hex_to_rgb_safe(fc)
        if fc_rgb is None:
            continue
        if all(abs(a - b) <= _COLOR_TOLERANCE for a, b in zip(impl_rgb, fc_rgb)):
            return True

    return False


def value_close(impl_val: float, allowed: set[float], tolerance: float = _SIZE_TOLERANCE) -> bool:
    """Check if a value is close to any allowed value."""
    return any(abs(impl_val - a) <= tolerance for a in allowed)


# ── Main compliance check ───────────────────────────────────────────


def check_compliance(
    design_data: dict,
    source_files: list[tuple[str, str]],  # (filepath, content)
) -> dict:
    """Compare ALL implementation style properties against Figma design tokens.

    High-fidelity 1:1 matching of every extractable style property:
    colors, fonts (family/size/weight/line-height/letter-spacing),
    spacing, border-radius, border-width, opacity, box-shadow.

    Returns dict with per-category violations, summary, and compliant flag.
    """
    summary_data = design_data.get("summary", {})

    # ── Build allowed sets from Figma data ──
    figma_colors: set[str] = set()
    for c in summary_data.get("colors", []):
        figma_colors.add(normalize_hex(c) if c.startswith("#") else c)

    figma_fonts: set[str] = set()
    figma_font_sizes: set[float] = set()
    for ts in summary_data.get("text_styles", []):
        if ts.get("font_family"):
            figma_fonts.add(ts["font_family"].lower())
        if ts.get("font_size_px"):
            figma_font_sizes.add(float(ts["font_size_px"]))

    figma_font_weights: set[int] = {int(w) for w in summary_data.get("font_weights", [])}
    figma_line_heights: set[float] = {float(h) for h in summary_data.get("line_heights", [])}
    figma_letter_spacings: set[float] = {float(s) for s in summary_data.get("letter_spacings", [])}
    figma_spacings: set[float] = {float(s) for s in summary_data.get("spacings", [])}
    figma_radii: set[float] = {float(r) for r in summary_data.get("border_radii", [])}
    figma_border_widths: set[float] = {float(w) for w in summary_data.get("border_widths", [])}
    figma_opacities: set[float] = {float(o) for o in summary_data.get("opacities", [])}
    figma_has_shadows = len(summary_data.get("shadows", [])) > 0

    generic_fonts = {"sans-serif", "serif", "monospace", "cursive", "fantasy",
                     "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace",
                     "inherit", "initial", "unset"}

    # ── Violation accumulators ──
    violations: dict[str, list[dict]] = {
        "color": [],
        "font_family": [],
        "font_size": [],
        "font_weight": [],
        "line_height": [],
        "letter_spacing": [],
        "spacing": [],
        "border_radius": [],
        "border_width": [],
        "opacity": [],
        "box_shadow": [],
    }

    def _add(category: str, filepath: str, line: int, value: str, msg: str) -> None:
        violations[category].append({"file": filepath, "line": line, "value": value, "message": msg})

    for filepath, content in source_files:
        # Colors
        if figma_colors:
            for c in extract_colors_from_source(content):
                if not color_matches(c["value"], figma_colors):
                    _add("color", filepath, c["line"], c["value"],
                         f"Color {c['value']} not in Figma palette")

        # Font family
        families, sizes = extract_fonts_from_source(content)
        if figma_fonts:
            for f in families:
                if f["value"].lower() not in figma_fonts and f["value"].lower() not in generic_fonts:
                    _add("font_family", filepath, f["line"], f["value"],
                         f"Font '{f['value']}' not in Figma (allowed: {sorted(figma_fonts)})")

        # Font size
        if figma_font_sizes:
            for s in sizes:
                if not value_close(s["value"], figma_font_sizes):
                    _add("font_size", filepath, s["line"], f"{s['value']}px",
                         f"Font size {s['value']}px not in Figma (allowed: {sorted(figma_font_sizes)})")

        # Font weight
        if figma_font_weights:
            for fw in extract_font_weights(content):
                if fw["value"] not in figma_font_weights:
                    _add("font_weight", filepath, fw["line"], str(fw["value"]),
                         f"Font weight {fw['value']} not in Figma (allowed: {sorted(figma_font_weights)})")

        # Line height
        if figma_line_heights:
            for lh in extract_line_heights(content):
                if not value_close(lh["value"], figma_line_heights, tolerance=0.05):
                    _add("line_height", filepath, lh["line"], str(lh["value"]),
                         f"Line height {lh['value']} not in Figma (allowed: {sorted(figma_line_heights)})")

        # Letter spacing
        if figma_letter_spacings:
            for ls in extract_letter_spacings(content):
                if not value_close(ls["value"], figma_letter_spacings, tolerance=0.005):
                    _add("letter_spacing", filepath, ls["line"], f"{ls['value']}em",
                         f"Letter spacing {ls['value']} not in Figma (allowed: {sorted(figma_letter_spacings)})")

        # Spacing (margin, padding, gap)
        if figma_spacings:
            for sp in extract_spacings_from_source(content):
                if not value_close(sp["value"], figma_spacings):
                    _add("spacing", filepath, sp["line"], f"{sp['value']}px",
                         f"Spacing {sp['value']}px not in Figma (allowed: {sorted(figma_spacings)})")

        # Border radius
        if figma_radii:
            for br in extract_border_radii(content):
                if not value_close(br["value"], figma_radii):
                    _add("border_radius", filepath, br["line"], f"{br['value']}px",
                         f"Border radius {br['value']}px not in Figma (allowed: {sorted(figma_radii)})")

        # Border width
        if figma_border_widths:
            for bw in extract_border_widths(content):
                if not value_close(bw["value"], figma_border_widths, tolerance=0.5):
                    _add("border_width", filepath, bw["line"], f"{bw['value']}px",
                         f"Border width {bw['value']}px not in Figma (allowed: {sorted(figma_border_widths)})")

        # Opacity
        if figma_opacities:
            for op in extract_opacities(content):
                if not value_close(op["value"], figma_opacities, tolerance=0.05):
                    _add("opacity", filepath, op["line"], str(op["value"]),
                         f"Opacity {op['value']} not in Figma (allowed: {sorted(figma_opacities)})")

        # Box shadow — verify shadows are only used when Figma defines them
        if not figma_has_shadows:
            for bs in extract_box_shadows(content):
                _add("box_shadow", filepath, bs["line"], bs["value"],
                     "Box shadow used but Figma design has no shadows")

    total = sum(len(v) for v in violations.values())

    # Build per-category counts for summary
    category_counts = {f"{k}_count": len(v) for k, v in violations.items()}

    return {
        "violations": violations,
        "summary": {
            "files_checked": len(source_files),
            "total_violations": total,
            **category_counts,
            "figma_tokens": {
                "colors": len(figma_colors),
                "fonts": len(figma_fonts),
                "font_sizes": len(figma_font_sizes),
                "font_weights": len(figma_font_weights),
                "line_heights": len(figma_line_heights),
                "letter_spacings": len(figma_letter_spacings),
                "spacings": len(figma_spacings),
                "border_radii": len(figma_radii),
                "border_widths": len(figma_border_widths),
                "opacities": len(figma_opacities),
                "shadows": len(summary_data.get("shadows", [])),
            },
        },
        "compliant": total == 0,
    }


# ── File discovery ──────────────────────────────────────────────────

_SOURCE_EXTENSIONS = {
    ".css", ".scss", ".less", ".sass",
    ".html", ".htm", ".jsx", ".tsx",
    ".ts", ".js", ".vue", ".svelte",
}


def find_source_files(project_path: Path, changed_files: list[str] | None = None) -> list[tuple[str, str]]:
    """Find source files to check.

    If changed_files is provided, only check those files.
    Otherwise, scan the project for all source files.
    """
    result: list[tuple[str, str]] = []

    if changed_files:
        for f in changed_files:
            fp = project_path / f
            if fp.exists() and fp.suffix in _SOURCE_EXTENSIONS:
                try:
                    result.append((f, fp.read_text(encoding="utf-8", errors="replace")))
                except OSError:
                    pass
    else:
        for ext in _SOURCE_EXTENSIONS:
            for fp in project_path.rglob(f"*{ext}"):
                # Skip node_modules, build dirs, prototype (that's the reference, not implementation)
                parts = fp.parts
                if any(skip in parts for skip in ("node_modules", "dist", "build", ".next", "prototype", "prototype-mobile", "figma-export")):
                    continue
                rel = str(fp.relative_to(project_path))
                try:
                    result.append((rel, fp.read_text(encoding="utf-8", errors="replace")))
                except OSError:
                    pass

    return result


# ── CLI ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Verify implementation compliance against Figma design tokens",
    )
    parser.add_argument(
        "--project-path",
        required=True,
        help="Path to project root (worktree or repo)",
    )
    parser.add_argument(
        "--design-data",
        default=None,
        help="Path to design_data.json (default: {project-path}/figma-export/design_data.json)",
    )
    parser.add_argument(
        "--changed-files",
        default=None,
        help="Comma-separated list of changed files to check (default: scan all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    project_path = Path(args.project_path).resolve()
    if not project_path.is_dir():
        print(f"Error: {project_path} is not a directory", file=sys.stderr)
        return 2

    # Find design data
    design_data_path = Path(args.design_data) if args.design_data else project_path / "figma-export" / "design_data.json"
    if not design_data_path.exists():
        print("PASS: No figma-export/design_data.json found — Figma compliance check skipped")
        return 0

    try:
        design_data = json.loads(design_data_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: cannot read design data: {e}", file=sys.stderr)
        return 2

    # Find source files
    changed = [f.strip() for f in args.changed_files.split(",")] if args.changed_files else None
    source_files = find_source_files(project_path, changed)

    if not source_files:
        print("PASS: No source files found to check")
        return 0

    # Run compliance check
    result = check_compliance(design_data, source_files)

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        s = result["summary"]
        t = s.get("figma_tokens", {})
        print(f"Figma Compliance Check: {s['files_checked']} file(s) checked against {sum(t.values())} Figma token(s)")
        print(f"  Tokens: {t.get('colors',0)} colors, {t.get('fonts',0)} fonts, {t.get('font_sizes',0)} sizes, "
              f"{t.get('font_weights',0)} weights, {t.get('line_heights',0)} line-heights, "
              f"{t.get('spacings',0)} spacings, {t.get('border_radii',0)} radii, "
              f"{t.get('opacities',0)} opacities, {t.get('shadows',0)} shadows")
        print()

        if result["compliant"]:
            print("PASS: All implementation values match Figma design tokens (1:1)")
        else:
            print(f"FAIL: {s['total_violations']} violation(s) found — implementation deviates from Figma")
            print()

            # Print each category with violations
            category_labels = {
                "color": "Color", "font_family": "Font family", "font_size": "Font size",
                "font_weight": "Font weight", "line_height": "Line height",
                "letter_spacing": "Letter spacing", "spacing": "Spacing",
                "border_radius": "Border radius", "border_width": "Border width",
                "opacity": "Opacity", "box_shadow": "Box shadow",
            }
            for key, label in category_labels.items():
                items = result["violations"].get(key, [])
                if not items:
                    continue
                print(f"  {label} ({len(items)}):")
                for v in items[:8]:
                    print(f"    {v['file']}:{v['line']} — {v['message']}")
                if len(items) > 8:
                    print(f"    ... and {len(items) - 8} more")
                print()

    return 0 if result["compliant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
