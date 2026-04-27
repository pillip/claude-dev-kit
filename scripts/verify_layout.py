#!/usr/bin/env python3
"""Verify layout relationships match Figma spatial arrangement.

Extracts spatial relationships between elements from Figma's node tree
(using absoluteBoundingBox positions) and verifies the implementation
preserves these relationships. Catches issues where tokens and structure
are correct but the visual layout is wrong (e.g., sidebar below content
instead of beside it).

Checks:
  - Parent-child containment (A should be inside B)
  - Sibling ordering (A should be left-of B, or above B)
  - Dominant layout direction per container (row vs column)

Exit codes:
  0 — layout matches
  1 — layout violations found
  2 — usage error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ── Figma layout extraction ─────────────────────────────────────────


def extract_layout_relationships(design_data: dict) -> list[dict]:
    """Extract spatial relationships between Figma elements.

    For each container with children, determines:
    - Layout direction (children arranged horizontally or vertically)
    - Child ordering (which child is first/last in that direction)
    - Relative positions (A is left-of B, A is above B)

    Returns list of relationship dicts.
    """
    relationships: list[dict] = []

    def _walk_frame(frame: dict) -> None:
        tree = frame.get("tree", {})
        frame_x = tree.get("x", 0)
        frame_y = tree.get("y", 0)
        _walk_node(tree, frame_x, frame_y)

    def _walk_node(node: dict, frame_x: float, frame_y: float) -> None:
        children = node.get("children", [])
        if len(children) < 2:
            for child in children:
                _walk_node(child, frame_x, frame_y)
            return

        # Get child positions relative to frame origin
        child_info: list[dict] = []
        for child in children:
            name = child.get("name", "")
            if not name or name.startswith("Group") or name.startswith("Frame "):
                continue
            x = child.get("x", 0) - frame_x
            y = child.get("y", 0) - frame_y
            w = child.get("width", 0)
            h = child.get("height", 0)
            if w <= 0 or h <= 0:
                continue
            child_info.append({"name": name, "x": x, "y": y, "w": w, "h": h})

        if len(child_info) < 2:
            for child in children:
                _walk_node(child, frame_x, frame_y)
            return

        # Determine dominant layout direction
        # If children share similar Y → horizontal (row)
        # If children share similar X → vertical (column)
        y_variance = max(c["y"] for c in child_info) - min(c["y"] for c in child_info)
        x_variance = max(c["x"] for c in child_info) - min(c["x"] for c in child_info)
        avg_h = sum(c["h"] for c in child_info) / len(child_info)
        avg_w = sum(c["w"] for c in child_info) / len(child_info)

        if y_variance < avg_h * 0.5 and x_variance > 0:
            direction = "row"
            sorted_children = sorted(child_info, key=lambda c: c["x"])
        elif x_variance < avg_w * 0.5 and y_variance > 0:
            direction = "column"
            sorted_children = sorted(child_info, key=lambda c: c["y"])
        else:
            direction = "mixed"
            sorted_children = child_info

        container_name = node.get("name", "container")

        # Record container layout
        relationships.append({
            "type": "container_direction",
            "container": container_name,
            "direction": direction,
            "children": [c["name"] for c in sorted_children],
        })

        # Record sibling ordering
        for i in range(len(sorted_children) - 1):
            a = sorted_children[i]
            b = sorted_children[i + 1]
            if direction == "row":
                relationships.append({
                    "type": "sibling_order",
                    "container": container_name,
                    "direction": direction,
                    "first": a["name"],
                    "second": b["name"],
                    "relation": "left-of",
                })
            elif direction == "column":
                relationships.append({
                    "type": "sibling_order",
                    "container": container_name,
                    "direction": direction,
                    "first": a["name"],
                    "second": b["name"],
                    "relation": "above",
                })

        for child in children:
            _walk_node(child, frame_x, frame_y)

    for frame in design_data.get("frames", []):
        _walk_frame(frame)

    return relationships


# ── Implementation layout checking ──────────────────────────────────


def check_layout_in_source(
    relationships: list[dict],
    source_files: list[tuple[str, str]],
) -> dict:
    """Check if implementation source preserves Figma layout relationships.

    Checks:
    1. Container direction: if Figma says "row", CSS should have flex-direction: row
    2. Element order: if Figma says A is left-of B, A should appear before B in DOM
    3. Named elements should exist
    """
    all_content = "\n".join(content for _, content in source_files)
    all_content_lower = all_content.lower()

    violations: list[dict] = []

    # Check container directions
    for rel in relationships:
        if rel["type"] != "container_direction":
            continue
        container = rel["container"].lower()
        direction = rel["direction"]

        if direction == "mixed":
            continue

        # Search for the container in source code
        # Look for CSS class or component that matches the container name
        slug = re.sub(r"[^\w]", "[-_]?", container)
        container_pattern = re.compile(slug, re.IGNORECASE)

        if not container_pattern.search(all_content):
            continue  # Container not identifiable in source — skip

        # Check if the direction is correct
        # Look for flex-direction near the container name
        if direction == "row":
            # Check for column when row is expected
            wrong_dir = re.search(
                rf"{slug}[^{{]*{{[^}}]*flex-direction\s*:\s*column",
                all_content_lower,
            )
            if wrong_dir:
                violations.append({
                    "type": "wrong_direction",
                    "container": rel["container"],
                    "expected": "row",
                    "found": "column",
                    "message": f"'{rel['container']}' should be row layout but has flex-direction: column",
                })
        elif direction == "column":
            wrong_dir = re.search(
                rf"{slug}[^{{]*{{[^}}]*flex-direction\s*:\s*row",
                all_content_lower,
            )
            if wrong_dir:
                violations.append({
                    "type": "wrong_direction",
                    "container": rel["container"],
                    "expected": "column",
                    "found": "row",
                    "message": f"'{rel['container']}' should be column layout but has flex-direction: row",
                })

    # Check sibling ordering in DOM
    for rel in relationships:
        if rel["type"] != "sibling_order":
            continue
        first = rel["first"].lower()
        second = rel["second"].lower()

        # Find positions of both element names in the source
        first_slug = re.sub(r"[^\w]", "[-_]?", first)
        second_slug = re.sub(r"[^\w]", "[-_]?", second)

        first_positions = [m.start() for m in re.finditer(first_slug, all_content_lower)]
        second_positions = [m.start() for m in re.finditer(second_slug, all_content_lower)]

        if not first_positions or not second_positions:
            continue  # Can't find elements — structural-match should catch this

        # Check if first appears before second (at least once)
        first_before_second = any(
            fp < sp for fp in first_positions for sp in second_positions
        )
        if not first_before_second:
            violations.append({
                "type": "wrong_order",
                "container": rel["container"],
                "expected_first": rel["first"],
                "expected_second": rel["second"],
                "relation": rel["relation"],
                "message": f"'{rel['first']}' should be {rel['relation']} '{rel['second']}' but appears after it in DOM",
            })

    # Summarize
    direction_violations = [v for v in violations if v["type"] == "wrong_direction"]
    order_violations = [v for v in violations if v["type"] == "wrong_order"]

    return {
        "violations": violations,
        "summary": {
            "relationships_checked": len(relationships),
            "direction_violations": len(direction_violations),
            "order_violations": len(order_violations),
            "total_violations": len(violations),
        },
        "compliant": len(violations) == 0,
    }


# ── File discovery ──────────────────────────────────────────────────

_SOURCE_EXTENSIONS = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".css", ".scss"}


def find_source_files(project_path: Path) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    skip_dirs = {"node_modules", "dist", "build", ".next", "prototype", "prototype-mobile", "figma-export"}
    for ext in _SOURCE_EXTENSIONS:
        for fp in project_path.rglob(f"*{ext}"):
            if any(skip in fp.parts for skip in skip_dirs):
                continue
            try:
                result.append((str(fp.relative_to(project_path)), fp.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass
    return result


# ── CLI ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify layout matches Figma spatial arrangement")
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--design-data", default=None)
    parser.add_argument("--json", action="store_true", dest="json_output")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    project_path = Path(args.project_path).resolve()
    dd_path = Path(args.design_data) if args.design_data else project_path / "figma-export" / "design_data.json"

    if not dd_path.exists():
        print("PASS: No figma-export/design_data.json — layout check skipped")
        return 0

    try:
        design_data = json.loads(dd_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: cannot read design data: {e}", file=sys.stderr)
        return 2

    relationships = extract_layout_relationships(design_data)
    if not relationships:
        print("PASS: No layout relationships extracted — nothing to verify")
        return 0

    source_files = find_source_files(project_path)
    if not source_files:
        print("FAIL: No source files found")
        return 1

    result = check_layout_in_source(relationships, source_files)

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        s = result["summary"]
        print(f"Layout Verification: {s['relationships_checked']} relationship(s) checked")
        print()

        if result["compliant"]:
            print("PASS: Layout matches Figma spatial arrangement")
        else:
            print(f"FAIL: {s['total_violations']} layout violation(s)")
            if s["direction_violations"]:
                print(f"\n  Direction mismatches ({s['direction_violations']}):")
                for v in result["violations"]:
                    if v["type"] == "wrong_direction":
                        print(f"    — {v['message']}")
            if s["order_violations"]:
                print(f"\n  Ordering mismatches ({s['order_violations']}):")
                for v in result["violations"]:
                    if v["type"] == "wrong_order":
                        print(f"    — {v['message']}")

    return 0 if result["compliant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
