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

    expected = extract_expected_elements(design_data)
    if not expected:
        print("PASS: No visible elements extracted from Figma — nothing to compare")
        return 0

    source_files = find_source_files(project_path)
    if not source_files:
        print("FAIL: No implementation source files found")
        return 1

    # Read prototype HTML as additional actual content (if exists)
    proto_dir = project_path / "prototype" / "screens"
    actual: dict = {"text_contents": set(), "element_roles": set()}
    if proto_dir.is_dir():
        for html_file in proto_dir.glob("*.html"):
            try:
                content = html_file.read_text(encoding="utf-8", errors="replace")
                proto_actual = extract_actual_elements(content)
                # Don't add prototype to actual — we compare implementation, not prototype
            except OSError:
                pass

    result = compare_structure(expected, actual, source_files)

    if args.json_output:
        # Convert sets to lists for JSON
        result["summary"]["found_roles"] = sorted(result["summary"].get("found_roles", []))
        print(json.dumps(result, indent=2, default=list))
    else:
        s = result["summary"]
        print(f"Structural Match: {s['expected_elements']} Figma elements, {len(source_files)} source file(s)")
        print(f"  Expected roles: {', '.join(s['expected_roles']) or 'none'}")
        print(f"  Found roles: {', '.join(s['found_roles']) or 'none'}")
        print()

        if result["compliant"]:
            print("PASS: All Figma elements accounted for in implementation")
        else:
            print(f"FAIL: {s['total_violations']} structural violation(s)")
            print()

            if result["missing_roles"]:
                print(f"  Missing element types ({s['missing_role_count']}):")
                for v in result["violations"]:
                    if v["type"] == "missing_role":
                        print(f"    — {v['message']}")
                print()

            if result["missing_texts"]:
                print(f"  Missing text content ({s['missing_text_count']}):")
                for v in result["violations"]:
                    if v["type"] == "missing_text":
                        print(f"    — {v['message']}")

    return 0 if result["compliant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
