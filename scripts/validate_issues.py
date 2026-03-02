#!/usr/bin/env python3
"""Validate issues.md for structural quality.

Checks each issue for:
- Estimate ∈ {0.5d, 1d, 1.5d}
- AC ≥ 2 items
- PRD-Ref not empty
- Depends-On not empty ("none" is valid)
- No duplicate ISSUE numbers
- AC uses Given/When/Then format

Exit code is always 0 (non-blocking). Violations are printed to stdout.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

VALID_ESTIMATES = {"0.5d", "1d", "1.5d"}
GWT_PATTERN = re.compile(r"given\s+.+,\s*when\s+.+,\s*then\s+", re.IGNORECASE)


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


def validate(issues: list[dict]) -> list[str]:
    """Return a list of violation messages."""
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

    return warnings


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

    warnings = validate(issues)

    if warnings:
        print(f"Found {len(warnings)} violation(s):")
        for w in warnings:
            print(f"  - {w}")
    else:
        print(f"All {len(issues)} issue(s) passed validation.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
