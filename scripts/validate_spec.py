#!/usr/bin/env python3
"""Validate SPEC documents under docs/specs/.

Checks each SPEC for:
- Frontmatter fields: Linked Issue, Status, Date
- Required sections: Problem, Context, Options, Decision, Trade-offs Accepted,
  Migration, Rollback, Open Questions
- Options: minimum 2 named options
- Every option has a Trade-off line with a measurable comparator
  (numeric, +/-, %, or a token like "+1 day", "-3 services", "2x faster")
- Decision section names a chosen option that matches one of the options

Exit code:
- 0: all SPECs valid
- 1: one or more SPECs invalid (when called on a single file or `--strict`)

Usage:
    python3 scripts/validate_spec.py docs/specs/SPEC-007.md
    python3 scripts/validate_spec.py docs/specs/         # validate all SPECs
    python3 scripts/validate_spec.py --strict docs/specs/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    "Problem",
    "Context",
    "Options",
    "Decision",
    "Trade-offs Accepted",
    "Migration",
    "Rollback",
    "Open Questions",
]

# A "measurable" trade-off line must contain at least one of:
# - a digit (numeric quantity)
# - +/- sign followed by something
# - % sign
# - a comparator word like "x faster", "x slower", "fewer", "more"
MEASURABLE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?\s*(?:%|x|×|ms|s|min|hr|d|day|days|GB|MB|KB|req/s|qps))"
    r"|([+\-]\s*\d+)"
    r"|(\b\d+(?:\.\d+)?\s*(?:faster|slower|fewer|more|less)\b)"
    r"|([+\-]\s*\d+\s+\w+)",
    re.IGNORECASE,
)


def parse_spec(text: str) -> dict:
    """Parse a SPEC document into a structured dict."""
    spec = {
        "title": "",
        "linked_issue": "",
        "status": "",
        "date": "",
        "sections": {},
        "options": [],
        "chosen_option": "",
    }

    # Title: first line `# SPEC-NNN: ...`
    title_match = re.search(r"^# (SPEC-\d+):\s*(.+)$", text, re.MULTILINE)
    if title_match:
        spec["title"] = title_match.group(1)

    # Frontmatter lines (blockquote at top). Anchored to line end with
    # [ \t]* (NOT \s* — \s eats newlines and would silently capture the
    # next line when the value is empty).
    for field, pattern in [
        ("linked_issue", r"^>?[ \t]*Linked Issue:[ \t]*(.*?)[ \t]*$"),
        ("status", r"^>?[ \t]*Status:.*?(`?)(draft|under-review|accepted|superseded)\1"),
        ("date", r"^>?[ \t]*Date:[ \t]*(.*?)[ \t]*$"),
    ]:
        m = re.search(pattern, text, re.MULTILINE)
        if m:
            captured = m.group(2) if field == "status" else m.group(1)
            spec[field] = captured.strip()

    # Sections: ## SectionName ... up to next ## or end
    for name in REQUIRED_SECTIONS:
        section_text = _extract_section(text, name)
        spec["sections"][name] = section_text

    # Options: ### Option X: name inside Options section
    options_text = spec["sections"].get("Options", "")
    for opt_match in re.finditer(
        r"^###\s+Option\s+(\w+):?\s*(.+?)$(.*?)(?=^###|\Z)",
        options_text,
        re.MULTILINE | re.DOTALL,
    ):
        opt_letter = opt_match.group(1).strip()
        opt_name = opt_match.group(2).strip()
        opt_body = opt_match.group(3)
        tradeoff_match = re.search(
            r"\*\*Trade-off\*\*:\s*(.+?)$", opt_body, re.MULTILINE
        )
        tradeoff = tradeoff_match.group(1).strip() if tradeoff_match else ""
        spec["options"].append(
            {"letter": opt_letter, "name": opt_name, "tradeoff": tradeoff}
        )

    # Chosen option from Decision section
    decision_text = spec["sections"].get("Decision", "")
    chosen_match = re.search(
        r"\*\*Chosen:\s*Option\s+(\w+)\b", decision_text, re.IGNORECASE
    )
    if chosen_match:
        spec["chosen_option"] = chosen_match.group(1).strip()

    return spec


def _extract_section(text: str, name: str) -> str:
    """Extract the content of a ## section by name."""
    pattern = rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def is_measurable_tradeoff(line: str) -> bool:
    """Check if a trade-off line carries at least one measurable comparator."""
    if not line:
        return False
    return bool(MEASURABLE_PATTERN.search(line))


def validate(spec: dict, path: str = "<spec>") -> list[str]:
    """Return a list of violation messages for one SPEC."""
    errors: list[str] = []

    if not spec["title"]:
        errors.append(f"{path}: missing title line `# SPEC-NNN: ...`")

    if not spec["linked_issue"]:
        errors.append(f"{path}: missing `Linked Issue:` frontmatter")

    if not spec["status"]:
        errors.append(
            f"{path}: missing or invalid `Status:` "
            f"(expected one of draft/under-review/accepted/superseded)"
        )

    if not spec["date"]:
        errors.append(f"{path}: missing `Date:` frontmatter")

    # Required sections
    for name in REQUIRED_SECTIONS:
        if not spec["sections"].get(name):
            errors.append(f"{path}: required section `## {name}` is missing or empty")

    # Options: minimum 2
    if len(spec["options"]) < 2:
        errors.append(
            f"{path}: only {len(spec['options'])} option(s); minimum 2 required"
        )

    # Each option must have a measurable trade-off
    for opt in spec["options"]:
        if not opt["tradeoff"]:
            errors.append(
                f"{path}: Option {opt['letter']} ({opt['name']}) missing **Trade-off:** line"
            )
        elif not is_measurable_tradeoff(opt["tradeoff"]):
            errors.append(
                f"{path}: Option {opt['letter']} trade-off is not measurable "
                f"(needs numeric/+-/% or comparator): {opt['tradeoff']!r}"
            )

    # Chosen option must match one of the options
    if spec["chosen_option"] and spec["options"]:
        letters = {o["letter"] for o in spec["options"]}
        if spec["chosen_option"] not in letters:
            errors.append(
                f"{path}: Decision chose Option {spec['chosen_option']} "
                f"but options defined are {sorted(letters)}"
            )

    return errors


def _iter_spec_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(target.glob("SPEC-*.md"))
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate SPEC documents")
    parser.add_argument("path", help="SPEC file or docs/specs/ directory")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any SPEC has violations (default for single file)",
    )
    args = parser.parse_args(argv)

    target = Path(args.path)
    if not target.exists():
        print(f"Error: {target} not found", file=sys.stderr)
        return 2

    files = _iter_spec_files(target)
    if not files:
        print(f"No SPEC files found at {target}", file=sys.stderr)
        return 0

    total_errors = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        spec = parse_spec(text)
        errors = validate(spec, str(f))
        if errors:
            total_errors += len(errors)
            for e in errors:
                print(f"  - {e}")

    if total_errors:
        print(f"\n{total_errors} violation(s) across {len(files)} SPEC(s)")
        return 1 if args.strict or target.is_file() else 0

    print(f"All {len(files)} SPEC(s) passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
