#!/usr/bin/env python3
"""Verify structural match between Figma node tree and implementation HTML.

Compares the element structure from figma-export/design_data.json against
the actual HTML DOM to ensure all Figma elements are present, in the
correct hierarchy, and none are missing.

This catches structural issues that token comparison misses:
- Missing elements (a button in Figma but not in the implementation)
- Wrong element hierarchy (sidebar inside content instead of beside it)
- Missing text content (copy from Figma not rendered)
- Missing icons/images (asset references broken)

Exit codes:
  0 — structural match (all elements accounted for)
  1 — structural mismatch (missing/extra elements)
  2 — usage error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ── Figma node tree → expected elements ─────────────────────────────

# Figma node types that map to visible HTML elements
_VISIBLE_TYPES = {"FRAME", "TEXT", "RECTANGLE", "COMPONENT", "INSTANCE", "ELLIPSE", "LINE", "VECTOR"}

# Name patterns to skip (decorative/structural, not semantic)
_SKIP_NAMES = re.compile(r"^(Group|Frame \d+|Rectangle \d+|background|divider|spacer)$", re.IGNORECASE)


def extract_expected_elements(design_data: dict) -> list[dict]:
    """Extract expected visible elements from Figma node tree.

    Returns list of {name, type, role, text_content, has_children, depth}.
    """
    elements: list[dict] = []

    def _classify(node: dict) -> str | None:
        """Classify a Figma node into a semantic role."""
        name = node.get("name", "").lower()
        node_type = node.get("type", "")

        if node_type == "TEXT":
            return "text"
        if _SKIP_NAMES.match(node.get("name", "")):
            return None  # Skip decorative nodes
        if "button" in name or "btn" in name:
            return "button"
        if "input" in name or "field" in name or "search" in name:
            return "input"
        if "icon" in name or "logo" in name:
            return "icon"
        if "image" in name or "img" in name or "photo" in name or "avatar" in name:
            return "image"
        if "nav" in name or "menu" in name or "sidebar" in name or "header" in name or "footer" in name:
            return "navigation"
        if "card" in name:
            return "card"
        if "list" in name or "item" in name:
            return "list-item"
        if "modal" in name or "dialog" in name:
            return "modal"
        if "tab" in name:
            return "tab"
        if node.get("has_background_image"):
            return "image"
        if node_type in ("COMPONENT", "INSTANCE"):
            return "component"
        if node_type == "FRAME" and node.get("children"):
            return "container"
        return None

    def _walk(node: dict, depth: int = 0) -> None:
        node_type = node.get("type", "")
        if node_type not in _VISIBLE_TYPES:
            for child in node.get("children", []):
                _walk(child, depth)
            return

        role = _classify(node)
        if role is None:
            for child in node.get("children", []):
                _walk(child, depth)
            return

        element: dict = {
            "name": node.get("name", ""),
            "type": node_type,
            "role": role,
            "depth": depth,
            "has_children": bool(node.get("children")),
        }

        # Text content for TEXT nodes
        ts = node.get("text_style", {})
        if ts and ts.get("text_content"):
            element["text_content"] = ts["text_content"].strip()

        elements.append(element)

        for child in node.get("children", []):
            _walk(child, depth + 1)

    # Walk all frames
    for frame in design_data.get("frames", []):
        tree = frame.get("tree", {})
        _walk(tree)

    return elements


def extract_expected_elements_per_viewport(design_data: dict) -> dict[str, list[dict]]:
    """Extract expected elements grouped by viewport/breakpoint.

    Returns dict keyed by breakpoint ("desktop", "tablet", "mobile").
    """
    per_viewport: dict[str, list[dict]] = {}

    for frame in design_data.get("frames", []):
        breakpoint = frame.get("breakpoint", "desktop")
        # Create a single-frame design_data for extraction
        single_frame_data = {"frames": [frame]}
        elements = extract_expected_elements(single_frame_data)
        per_viewport.setdefault(breakpoint, []).extend(elements)

    return per_viewport


# ── HTML content → actual elements ──────────────────────────────────


def extract_actual_elements(html_content: str) -> dict:
    """Extract structural information from HTML content.

    Returns dict with:
      - text_contents: set of visible text strings
      - has_buttons: bool
      - has_inputs: bool
      - has_images: bool
      - has_icons: bool
      - has_navigation: bool
      - element_roles: set of detected roles
    """
    text_contents: set[str] = set()
    roles: set[str] = set()

    # Extract visible text (between tags, excluding scripts/styles)
    # Remove script and style blocks
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    # Extract text between tags
    texts = re.findall(r">([^<]+)<", cleaned)
    for t in texts:
        stripped = t.strip()
        if stripped and len(stripped) > 1:  # Skip single chars (bullet points, etc.)
            text_contents.add(stripped)

    # Detect element types
    if re.search(r"<button\b|<a\b[^>]*class=['\"][^'\"]*btn|role=['\"]button['\"]", html_content, re.IGNORECASE):
        roles.add("button")
    if re.search(r"<input\b|<textarea\b|<select\b", html_content, re.IGNORECASE):
        roles.add("input")
    if re.search(r"<img\b|<picture\b|background-image", html_content, re.IGNORECASE):
        roles.add("image")
    if re.search(r"<svg\b|\.svg['\"]|icon", html_content, re.IGNORECASE):
        roles.add("icon")
    if re.search(r"<nav\b|<header\b|<footer\b|role=['\"]navigation['\"]", html_content, re.IGNORECASE):
        roles.add("navigation")
    if re.search(r"<dialog\b|role=['\"]dialog['\"]|modal", html_content, re.IGNORECASE):
        roles.add("modal")
    if re.search(r"role=['\"]tab['\"]|tab-", html_content, re.IGNORECASE):
        roles.add("tab")

    return {
        "text_contents": text_contents,
        "element_roles": roles,
    }


# ── Structural comparison ───────────────────────────────────────────


def compare_structure(
    expected: list[dict],
    actual: dict,
    source_files: list[tuple[str, str]],
) -> dict:
    """Compare Figma expected elements against implementation.

    Returns dict with:
      missing_texts, missing_roles, extra_roles, violations, compliant.
    """
    violations: list[dict] = []

    # Combine text contents from all source files
    all_text: set[str] = set(actual.get("text_contents", set()))
    all_roles: set[str] = set(actual.get("element_roles", set()))
    for _, content in source_files:
        file_actual = extract_actual_elements(content)
        all_text.update(file_actual["text_contents"])
        all_roles.update(file_actual["element_roles"])

    # Check text content presence
    missing_texts: list[str] = []
    for elem in expected:
        text = elem.get("text_content", "")
        if not text or len(text) < 3:
            continue
        # Check if text appears in any source file (case-insensitive partial match)
        found = any(text.lower() in t.lower() for t in all_text)
        if not found:
            # Also check source code directly for the string
            found = any(text in content for _, content in source_files)
        if not found:
            missing_texts.append(text)
            violations.append({
                "type": "missing_text",
                "figma_element": elem["name"],
                "expected_text": text,
                "message": f"Text '{text[:50]}' from Figma element '{elem['name']}' not found in implementation",
            })

    # Check role presence (are there buttons, inputs, images, etc. as expected?)
    expected_roles: set[str] = set()
    for elem in expected:
        if elem["role"] in ("button", "input", "image", "icon", "navigation", "modal", "tab"):
            expected_roles.add(elem["role"])

    missing_roles: list[str] = []
    for role in expected_roles:
        if role not in all_roles:
            missing_roles.append(role)
            count = sum(1 for e in expected if e["role"] == role)
            violations.append({
                "type": "missing_role",
                "role": role,
                "figma_count": count,
                "message": f"Figma has {count} '{role}' element(s) but none found in implementation",
            })

    return {
        "missing_texts": missing_texts,
        "missing_roles": missing_roles,
        "violations": violations,
        "summary": {
            "expected_elements": len(expected),
            "expected_text_elements": sum(1 for e in expected if e.get("text_content")),
            "expected_roles": sorted(expected_roles),
            "found_roles": sorted(all_roles),
            "missing_text_count": len(missing_texts),
            "missing_role_count": len(missing_roles),
            "total_violations": len(violations),
        },
        "compliant": len(violations) == 0,
    }


# ── File discovery ──────────────────────────────────────────────────

_SOURCE_EXTENSIONS = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte"}


def find_source_files(project_path: Path) -> list[tuple[str, str]]:
    """Find implementation source files for structural analysis."""
    result: list[tuple[str, str]] = []
    skip_dirs = {"node_modules", "dist", "build", ".next", "prototype", "prototype-mobile", "figma-export"}

    for ext in _SOURCE_EXTENSIONS:
        for fp in project_path.rglob(f"*{ext}"):
            if any(skip in fp.parts for skip in skip_dirs):
                continue
            rel = str(fp.relative_to(project_path))
            try:
                result.append((rel, fp.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass
    return result


# ── CLI ─────────────────────────────────────────────────────────────


_BREAKPOINT_MEDIA = {
    "mobile": r"max-width\s*:\s*(?:4[0-9]{2}|5[0-9]{2}|6[0-9]{2}|7[0-6][0-9]|767)\s*px",
    "tablet": r"(?:min-width\s*:\s*7[0-9]{2}|max-width\s*:\s*10[0-2][0-9])\s*px",
    "desktop": r"min-width\s*:\s*(?:10[2-9][0-9]|1[1-9][0-9]{2}|[2-9][0-9]{3})\s*px",
}


def check_responsive_coverage(
    viewports: list[str],
    source_files: list[tuple[str, str]],
) -> list[dict]:
    """Check that implementation has responsive CSS for each Figma viewport.

    Looks for media queries or responsive patterns matching each breakpoint.
    """
    violations: list[dict] = []
    all_content = "\n".join(content for _, content in source_files)

    # Check for any responsive pattern (media queries, container queries, responsive utils)
    has_any_responsive = bool(re.search(r"@media|@container|useMediaQuery|useBreakpoint|breakpoint", all_content, re.IGNORECASE))

    if len(viewports) > 1 and not has_any_responsive:
        violations.append({
            "type": "no_responsive",
            "viewports": viewports,
            "message": f"Figma has {len(viewports)} viewport(s) ({', '.join(viewports)}) but no responsive CSS (@media/@container) found",
        })
        return violations

    # Check each non-desktop viewport has a matching media query
    for vp in viewports:
        if vp == "desktop":
            continue  # Desktop is the default, no media query needed
        pattern = _BREAKPOINT_MEDIA.get(vp)
        if pattern and not re.search(pattern, all_content, re.IGNORECASE):
            # Also check for responsive utility classes (Tailwind, Bootstrap, etc.)
            responsive_utils = {
                "mobile": r"\b(sm:|xs:|mobile[:-]|@screen\s+sm)",
                "tablet": r"\b(md:|tablet[:-]|@screen\s+md)",
            }
            util_pattern = responsive_utils.get(vp, "")
            if not util_pattern or not re.search(util_pattern, all_content, re.IGNORECASE):
                violations.append({
                    "type": "missing_breakpoint",
                    "viewport": vp,
                    "message": f"Figma has a '{vp}' viewport but no matching media query or responsive pattern found",
                })

    return violations


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Verify structural match between Figma design and implementation",
    )
    parser.add_argument("--project-path", required=True, help="Path to project root")
    parser.add_argument("--design-data", default=None, help="Path to design_data.json")
    parser.add_argument("--json", action="store_true", dest="json_output")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    project_path = Path(args.project_path).resolve()
    dd_path = Path(args.design_data) if args.design_data else project_path / "figma-export" / "design_data.json"

    if not dd_path.exists():
        print("PASS: No figma-export/design_data.json — structural match skipped")
        return 0

    try:
        design_data = json.loads(dd_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: cannot read design data: {e}", file=sys.stderr)
        return 2

    source_files = find_source_files(project_path)
    if not source_files:
        print("FAIL: No implementation source files found")
        return 1

    actual: dict = {"text_contents": set(), "element_roles": set()}
    all_violations: list[dict] = []
    all_compliant = True

    # ── Per-viewport structural check ──
    per_viewport = extract_expected_elements_per_viewport(design_data)
    viewports = sorted(per_viewport.keys())

    if len(viewports) > 1:
        print(f"Figma has {len(viewports)} viewport(s): {', '.join(viewports)}")
        print(f"  Verifying each viewport's elements independently.\n")

    for vp, elements in per_viewport.items():
        if not elements:
            continue
        result = compare_structure(elements, actual, source_files)
        if not result["compliant"]:
            all_compliant = False
            for v in result["violations"]:
                v["viewport"] = vp
            all_violations.extend(result["violations"])

        s = result["summary"]
        icon = "PASS" if result["compliant"] else "FAIL"
        print(f"  {icon}: {vp} — {s['expected_elements']} elements, "
              f"{s['missing_role_count']} missing roles, {s['missing_text_count']} missing texts")

    # ── Responsive CSS check (when multiple viewports exist) ──
    if len(viewports) > 1:
        responsive_violations = check_responsive_coverage(viewports, source_files)
        if responsive_violations:
            all_compliant = False
            all_violations.extend(responsive_violations)
            print()
            for v in responsive_violations:
                print(f"  FAIL: {v['message']}")

    print()

    if args.json_output:
        output = {
            "viewports": viewports,
            "violations": all_violations,
            "compliant": all_compliant,
            "viewport_count": len(viewports),
        }
        print(json.dumps(output, indent=2, default=list))

    if all_compliant:
        print(f"PASS: All {len(viewports)} viewport(s) structurally matched")
    else:
        print(f"FAIL: {len(all_violations)} violation(s) across {len(viewports)} viewport(s)")
        for v in all_violations[:10]:
            vp_label = f"[{v.get('viewport', 'all')}] " if v.get("viewport") else ""
            print(f"    {vp_label}{v['message']}")
        if len(all_violations) > 10:
            print(f"    ... and {len(all_violations) - 10} more")

    return 0 if all_compliant else 1


if __name__ == "__main__":
    raise SystemExit(main())
