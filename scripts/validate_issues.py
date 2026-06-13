#!/usr/bin/env python3
"""Validate issues.md for structural quality.

Checks each issue for:
- Estimate ∈ {0.5d, 1d, 1.5d}
- AC ≥ 2 items
- PRD-Ref not empty
- Depends-On not empty ("none" is valid)
- No duplicate ISSUE numbers
- AC uses Given/When/Then format
- Depends-On references exist (no dangling references)
- No circular dependencies (DAG validation)
- Dependency chain depth ≤ 3 (warning if exceeded)

Exit code is always 0 (non-blocking). Violations are printed to stdout.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

VALID_ESTIMATES = {"0.5d", "1d", "1.5d"}
GWT_PATTERN = re.compile(r"given\s+.+,\s*when\s+.+,\s*then\s+", re.IGNORECASE)
SPEC_ENFORCED_STATUSES = {"doing", "waiting", "done"}


def parse_issues(text: str) -> list[dict]:
    """Parse issues.md into a list of issue dicts."""
    issues: list[dict] = []
    # Split on issue headers: ### ISSUE-NNN: ...
    parts = re.split(r"(?=^### ISSUE-\d+:)", text, flags=re.MULTILINE)

    for part in parts:
        header_match = re.match(r"^### (ISSUE-(\d+)):\s*(.+)", part)
        if not header_match:
            continue

        issue_id = header_match.group(1)
        issue_num = header_match.group(2)
        title = header_match.group(3).strip()

        # Extract metadata fields
        estimate = _extract_field(part, "Estimate")
        prd_ref = _extract_field(part, "PRD-Ref")
        depends_on = _extract_field(part, "Depends-On")
        status = _extract_field(part, "Status").lower()
        spec_required = _extract_field(part, "Spec-Required").lower()
        spec_path = _extract_field(part, "Spec")

        # Extract AC items
        ac_section = _extract_section(part, "Acceptance Criteria")
        ac_items = re.findall(r"^- \[[ x]\] (.+)$", ac_section, re.MULTILINE)

        issues.append(
            {
                "id": issue_id,
                "num": issue_num,
                "title": title,
                "estimate": estimate,
                "prd_ref": prd_ref,
                "depends_on": depends_on,
                "ac_items": ac_items,
                "status": status,
                "spec_required": spec_required,
                "spec_path": spec_path,
            }
        )

    return issues


def _extract_field(text: str, field_name: str) -> str:
    """Extract a metadata field value from issue text."""
    match = re.search(rf"^- {field_name}:[ \t]*(.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_section(text: str, section_name: str) -> str:
    """Extract content under a #### section header."""
    pattern = rf"#### {re.escape(section_name)}.*?\n(.*?)(?=\n####|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else ""


def _spec_path_satisfied(spec_path: str, issues_md_dir: Path | None) -> bool:
    """A spec_path is satisfied if it is non-empty, not 'none', and the file exists.

    When issues_md_dir is None (in-memory test paths), only the non-empty/non-none
    check applies — we trust the test to set realistic values.
    """
    if not spec_path or spec_path.strip().lower() == "none":
        return False
    if issues_md_dir is None:
        return True
    spec_file = (issues_md_dir / spec_path).resolve()
    return spec_file.exists()


def validate(issues: list[dict], issues_md_dir: Path | None = None) -> list[str]:
    """Return a list of violation messages.

    issues_md_dir: directory containing issues.md. Used to resolve Spec: paths
    when checking existence. Pass None to skip file-existence checks (unit tests).
    """
    warnings: list[str] = []
    seen_nums: dict[str, str] = {}

    for issue in issues:
        iid = issue["id"]

        # Duplicate check
        if issue["num"] in seen_nums:
            warnings.append(
                f"{iid}: duplicate number (also used by {seen_nums[issue['num']]})"
            )
        seen_nums[issue["num"]] = iid

        # Estimate
        if issue["estimate"] not in VALID_ESTIMATES:
            warnings.append(
                f"{iid}: invalid estimate '{issue['estimate']}' "
                f"(must be one of {sorted(VALID_ESTIMATES)})"
            )

        # AC count
        if len(issue["ac_items"]) < 2:
            warnings.append(
                f"{iid}: only {len(issue['ac_items'])} AC item(s) (minimum 2)"
            )

        # AC format (Given/When/Then)
        for i, ac in enumerate(issue["ac_items"], 1):
            if not GWT_PATTERN.search(ac):
                warnings.append(f"{iid}: AC #{i} not in Given/When/Then format")

        # PRD-Ref
        if not issue["prd_ref"]:
            warnings.append(f"{iid}: PRD-Ref is empty")

        # Depends-On
        if not issue["depends_on"]:
            warnings.append(f"{iid}: Depends-On is empty")

        # Spec-Required enforcement
        spec_required = issue.get("spec_required", "")
        status = issue.get("status", "")
        spec_path = issue.get("spec_path", "")
        if spec_required == "true" and status in SPEC_ENFORCED_STATUSES:
            if not _spec_path_satisfied(spec_path, issues_md_dir):
                warnings.append(
                    f"{iid}: Spec-Required=true and Status={status}, "
                    f"but Spec: '{spec_path or '<empty>'}' is missing or unreadable"
                )

    # Cross-issue validations
    all_ids = {issue["id"] for issue in issues}
    dep_graph = _build_dependency_graph(issues)

    # Check for dangling references
    for issue in issues:
        deps = _parse_depends_on(issue["depends_on"])
        for dep in deps:
            if dep not in all_ids:
                warnings.append(f"{issue['id']}: Depends-On references {dep} which does not exist")

    # Check for cycles
    cycles = _detect_cycles(dep_graph)
    for cycle in cycles:
        warnings.append(f"circular dependency detected: {' → '.join(cycle)}")

    # Check for deep dependency chains
    for issue in issues:
        depth = _max_chain_depth(issue["id"], dep_graph, all_ids)
        if depth > 3:
            warnings.append(
                f"{issue['id']}: dependency chain depth is {depth} (warning: > 3)"
            )

    return warnings


def _parse_depends_on(depends_on: str) -> list[str]:
    """Parse Depends-On field into a list of issue IDs.

    Tolerates inline notes like `ISSUE-002 (eval reports feed pattern extraction)` —
    extracts the bare `ISSUE-NNN` token from each comma-separated entry.
    """
    if not depends_on or depends_on.strip().lower() == "none":
        return []
    ids: list[str] = []
    for piece in depends_on.split(","):
        match = re.search(r"\bISSUE-\d+\b", piece)
        if match:
            ids.append(match.group(0))
    return ids


def _build_dependency_graph(issues: list[dict]) -> dict[str, list[str]]:
    """Build adjacency list: issue -> list of issues it depends on."""
    graph: dict[str, list[str]] = {}
    for issue in issues:
        graph[issue["id"]] = _parse_depends_on(issue["depends_on"])
    return graph


def _detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Detect cycles in the dependency graph using DFS."""
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def _dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                _dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Found cycle: extract the cycle from path
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)

        path.pop()
        rec_stack.discard(node)

    for node in graph:
        if node not in visited:
            _dfs(node, [])

    return cycles


def _max_chain_depth(
    issue_id: str, graph: dict[str, list[str]], all_ids: set[str]
) -> int:
    """Calculate the maximum dependency chain depth for an issue."""
    visited: set[str] = set()

    def _depth(node: str) -> int:
        if node in visited or node not in all_ids:
            return 0
        visited.add(node)
        deps = graph.get(node, [])
        if not deps:
            return 0
        return 1 + max(_depth(d) for d in deps)

    return _depth(issue_id)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 always (non-blocking)."""
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: validate_issues.py <issues.md>", file=sys.stderr)
        return 1

    path = Path(args[0])
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    issues = parse_issues(text)

    if not issues:
        print("Warning: no issues found in file")
        return 0

    warnings = validate(issues, issues_md_dir=path.resolve().parent)

    if warnings:
        print(f"Found {len(warnings)} violation(s):")
        for w in warnings:
            print(f"  - {w}")
    else:
        print(f"All {len(issues)} issue(s) passed validation.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
