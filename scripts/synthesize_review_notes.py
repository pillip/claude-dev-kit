#!/usr/bin/env python3
"""Synthesize runtime /code-review + /security-review + kit-distinctive findings into review_notes.md.

ISSUE-019 / SPEC-019 primary path: when the runtime exposes /code-review
and /security-review, /review delegates correctness/complexity/coverage
and the security audit to those skills. This synthesizer is the
deterministic writer that maps their outputs (plus the kit-distinctive
checks the runtime does NOT provide — Figma 3.5-3.10, ui-reviewer,
design-auditor, a11y-auditor) into the kit's existing 2-section
review_notes.md format, preserving every finding verbatim with its
upstream severity.

The LLM-y extraction (turning runtime prose output into structured
findings) happens in the SKILL.md.tmpl prompt itself; this Python module
takes a structured intermediate and renders. The review-merge-auditor
(separate Task invocation, refute-first prompt) then verifies the
mapping did not drop / distort / change severity of any finding.

Input contract (Python dict / JSON):
    {
      "pr_number":          "47",
      "code_findings":      [Finding, ...],  # from /code-review (primary) or reviewer agent (degraded)
      "security_findings":  [Finding, ...],  # from /security-review (primary) or reviewer agent (degraded)
      "code_source":        "code-review",   # "code-review" | "reviewer-degraded"
      "security_source":    "security-review",
      "ui_findings":        [Finding, ...] or null,         # ui-reviewer (kit-distinctive)
      "design_findings":    [Finding, ...] or null,         # design-auditor (kit-distinctive)
      "a11y_findings":      [Finding, ...] or null,         # a11y-auditor (kit-distinctive)
      "figma_findings":     [Finding, ...] or null          # Figma compliance (kit-distinctive)
    }

Finding shape:
    {
      "severity": "Critical" | "High" | "Medium" | "Low",
      "title":    "concise problem statement",
      "evidence": "verbatim upstream quote OR file:line excerpt",
      "fix":      "concrete suggestion"  # optional
    }

Output: markdown string preserving severity verbatim, stable section
order. Empty kit-distinctive sections are omitted (those are conditional
on the PR touching UI / having Figma data); empty code/security sections
render the no-finding literal so downstream consumers (/ship, /sprint)
see a consistent shape.

Exit codes (when invoked as CLI):
    0 = render succeeded
    2 = bad input

Usage:
    python3 scripts/synthesize_review_notes.py < input.json
    python3 scripts/synthesize_review_notes.py --input input.json --out docs/review_notes/47.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

VALID_SEVERITIES = ("Critical", "High", "Medium", "Low")

NO_FINDINGS_LINE = "_No findings._"

# Section order is fixed: runtime-owned sections first (Code Review,
# Security Findings), then the always-on Over-Engineering (minimality) section,
# then kit-distinctive sections in stable order.
RUNTIME_SECTIONS = (
    ("code_findings", "Code Review", "code_source"),
    ("security_findings", "Security Findings", "security_source"),
)
# Over-Engineering is a required section of the kit's SSOT review-notes
# contract (ponytail ISSUE-018; verify_checkpoint.verify_review_review asserts
# the header). It always renders — "_No findings._" when the minimality axis
# found nothing to cut ("Lean already. Ship.").
ALWAYS_SECTIONS = (
    ("minimality_findings", "Over-Engineering"),
)
KIT_DISTINCTIVE_SECTIONS = (
    ("ui_findings", "UI Review"),
    ("design_findings", "Design Audit"),
    ("a11y_findings", "Accessibility Audit"),
    ("figma_findings", "Figma Compliance"),
)


def _validate_finding(finding: Any, *, section: str, index: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(finding, dict):
        return [f"{section}[{index}] is not a dict"]
    severity = finding.get("severity")
    if severity not in VALID_SEVERITIES:
        errors.append(
            f"{section}[{index}].severity {severity!r} not in {VALID_SEVERITIES}"
        )
    for required in ("title", "evidence"):
        value = finding.get(required)
        if not value or not isinstance(value, str):
            errors.append(f"{section}[{index}] missing or empty {required!r}")
    return errors


def _validate_input(payload: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["input must be a JSON object"]
    if "code_findings" not in payload or "security_findings" not in payload:
        errors.append("input must contain 'code_findings' and 'security_findings' (may be empty lists)")
        return errors
    for section_key, _, _ in RUNTIME_SECTIONS:
        findings = payload.get(section_key)
        if findings is None or not isinstance(findings, list):
            errors.append(f"'{section_key}' must be a list (may be empty)")
            continue
        for i, finding in enumerate(findings):
            errors.extend(_validate_finding(finding, section=section_key, index=i))
    for section_key, _ in ALWAYS_SECTIONS + KIT_DISTINCTIVE_SECTIONS:
        findings = payload.get(section_key)
        if findings is None:
            continue
        if not isinstance(findings, list):
            errors.append(f"'{section_key}' if present must be a list")
            continue
        for i, finding in enumerate(findings):
            errors.extend(_validate_finding(finding, section=section_key, index=i))
    return errors


def _sort_by_severity(findings: list[dict]) -> list[dict]:
    """Critical → High → Medium → Low. Stable within severity."""
    order = {sev: i for i, sev in enumerate(VALID_SEVERITIES)}
    return sorted(findings, key=lambda f: order.get(f.get("severity", "Low"), 99))


def _render_finding(finding: dict) -> str:
    severity = finding["severity"]
    title = finding["title"].rstrip()
    evidence = finding["evidence"].rstrip()
    fix = (finding.get("fix") or "").rstrip()
    lines = [f"- **[{severity}] {title}**", f"  Evidence: {evidence}"]
    if fix:
        lines.append(f"  Fix: {fix}")
    return "\n".join(lines)


def _render_section(title: str, findings: list[dict], *, source: str | None = None) -> list[str]:
    out: list[str] = [f"## {title}"]
    if source:
        out.append(f"_Source: {source}_")
    out.append("")
    if not findings:
        out.append(NO_FINDINGS_LINE)
        out.append("")
        return out
    for finding in _sort_by_severity(findings):
        out.append(_render_finding(finding))
        out.append("")
    return out


def render(payload: dict[str, Any]) -> str:
    errors = _validate_input(payload)
    if errors:
        raise ValueError("; ".join(errors))

    lines: list[str] = []
    pr = payload.get("pr_number")
    if pr:
        lines.append(f"# Review Notes — PR #{pr}")
        lines.append("")

    for section_key, title, source_key in RUNTIME_SECTIONS:
        source = payload.get(source_key) or ""
        lines.extend(_render_section(title, payload[section_key], source=source or None))

    for section_key, title in ALWAYS_SECTIONS:
        lines.extend(_render_section(title, payload.get(section_key) or []))

    for section_key, title in KIT_DISTINCTIVE_SECTIONS:
        findings = payload.get(section_key)
        if findings is None:
            continue  # not run for this PR
        lines.extend(_render_section(title, findings))

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render runtime + kit-distinctive findings into review_notes.md."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="JSON file containing the structured findings (stdin if omitted).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Write rendered markdown to this path (stdout if omitted).",
    )
    args = parser.parse_args()

    try:
        raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading input: {exc}", file=sys.stderr)
        return 2

    try:
        rendered = render(payload)
    except ValueError as exc:
        print(f"Input validation failed: {exc}", file=sys.stderr)
        return 2

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
        print(f"wrote: {args.out}")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
