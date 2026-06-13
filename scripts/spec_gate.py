#!/usr/bin/env python3
"""Spec gate logic invoked by /implement.

Reads the target issue from issues.md and decides one of three outcomes:
- proceed         : implementation can begin immediately (no spec needed)
- auto_spec       : sprint mode + Spec-Required=true + no SPEC → /spec must run first
- hold            : non-sprint mode + missing SPEC OR signal-detected → user must choose
- bypassed        : --skip-spec-gate was passed → proceed + emit telemetry

The user-facing 3-way HOLD prompt itself lives in the /implement skill (uses
AskUserQuestion). This script's job is to produce the structured decision +
diagnostics that drive that prompt.

Usage:
    python3 scripts/spec_gate.py ISSUE-007 [--skip-spec-gate] [--issues-md=issues.md]
        → prints JSON: {decision, reasons, signals, spec_path}

Exit code:
    0 = decision computed successfully
    2 = bad input (issue not found, etc.)
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

SPRINT_ENV = "KIT_SPRINT_MODE"

# Keyword signals that recommend (never auto-trigger) a spec.
SIGNAL_KEYWORDS: list[tuple[str, str]] = [
    (r"\bAPI\b", "API surface"),
    (r"\bschema\b", "schema"),
    (r"\bmigration\b", "migration"),
    (r"\bbreaking\b", "breaking change"),
    (r"\bprotocol\b", "protocol"),
    (r"데이터모델", "data model (ko)"),
    (r"\bnew\s+package\b", "new package"),
    (r"\bnew\s+dependency\b", "new dependency"),
    (r"\badd\s+(?:a\s+)?dependency\b", "add dependency"),
]


def parse_issue(issues_md: Path, issue_id: str) -> dict | None:
    """Return a dict with the target issue's fields, or None if not found."""
    text = issues_md.read_text(encoding="utf-8")
    pattern = (
        rf"^### {re.escape(issue_id)}:.*?(?=^### ISSUE-\d+:|\Z)"
    )
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not m:
        return None
    block = m.group(0)
    return {
        "id": issue_id,
        "estimate": _field(block, "Estimate"),
        "status": _field(block, "Status").lower(),
        "spec_required": _field(block, "Spec-Required").lower(),
        "spec_path": _field(block, "Spec"),
        "body": block,
    }


def _field(block: str, name: str) -> str:
    m = re.search(rf"^- {re.escape(name)}:[ \t]*(.*)$", block, re.MULTILINE)
    return m.group(1).strip() if m else ""


def scan_signals(issue_body: str) -> list[dict]:
    """Return a list of {signal, evidence} dicts for recommendation logging."""
    found: list[dict] = []
    for pattern, label in SIGNAL_KEYWORDS:
        m = re.search(pattern, issue_body, re.IGNORECASE)
        if m:
            # Capture a small context window for evidence.
            start = max(0, m.start() - 30)
            end = min(len(issue_body), m.end() + 30)
            evidence = issue_body[start:end].replace("\n", " ")
            found.append({"signal": label, "evidence": evidence.strip()})
    # Estimate at cap = a signal.
    if re.search(r"^- Estimate:\s*1\.5d\s*$", issue_body, re.MULTILINE):
        found.append({"signal": "estimate at 1.5d cap", "evidence": "Estimate: 1.5d"})
    return found


def spec_path_exists(spec_path: str, issues_md_dir: Path) -> bool:
    if not spec_path or spec_path.strip().lower() == "none":
        return False
    return (issues_md_dir / spec_path).resolve().exists()


def decide(
    issue: dict,
    issues_md_dir: Path,
    sprint_mode: bool,
    skip_gate: bool,
) -> dict:
    """Apply the decision table.

    Returns a dict:
      {
        "decision": "proceed" | "auto_spec" | "hold" | "bypassed",
        "reasons": [str, ...],
        "signals": [{signal, evidence}, ...],
        "spec_path": str,
        "sprint_mode": bool,
      }
    """
    reasons: list[str] = []
    signals = scan_signals(issue["body"])
    spec_required = issue["spec_required"] == "true"
    spec_present = spec_path_exists(issue["spec_path"], issues_md_dir)

    if skip_gate:
        reasons.append("--skip-spec-gate was passed; bypassing gate")
        return _result("bypassed", reasons, signals, issue, sprint_mode)

    # Spec already exists for a required issue → use it.
    if spec_required and spec_present:
        reasons.append(f"Spec-Required=true and SPEC exists at {issue['spec_path']}")
        return _result("proceed", reasons, signals, issue, sprint_mode)

    # Spec required but missing.
    if spec_required and not spec_present:
        if sprint_mode:
            reasons.append(
                "Spec-Required=true, SPEC missing, sprint mode → auto-run /spec"
            )
            return _result("auto_spec", reasons, signals, issue, sprint_mode)
        else:
            reasons.append(
                "Spec-Required=true, SPEC missing, non-sprint mode → HOLD for user choice"
            )
            return _result("hold", reasons, signals, issue, sprint_mode)

    # Spec NOT required, but signals fired.
    if signals:
        labels = [s["signal"] for s in signals]
        if sprint_mode:
            reasons.append(
                f"Spec-Required=false; signals detected ({', '.join(labels)}); "
                "sprint mode → log recommendation, proceed"
            )
            return _result("proceed", reasons, signals, issue, sprint_mode)
        else:
            reasons.append(
                f"Spec-Required=false; signals detected ({', '.join(labels)}); "
                "non-sprint mode → HOLD for user choice"
            )
            return _result("hold", reasons, signals, issue, sprint_mode)

    # Nothing to gate on.
    reasons.append("Spec-Required=false and no signals; proceeding silently")
    return _result("proceed", reasons, signals, issue, sprint_mode)


def _result(
    decision: str,
    reasons: list[str],
    signals: list[dict],
    issue: dict,
    sprint_mode: bool,
) -> dict:
    return {
        "decision": decision,
        "reasons": reasons,
        "signals": signals,
        "spec_path": issue["spec_path"],
        "sprint_mode": sprint_mode,
        "issue_id": issue["id"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spec gate for /implement")
    parser.add_argument("issue_id", help="Target issue (e.g., ISSUE-007)")
    parser.add_argument(
        "--issues-md",
        default="issues.md",
        help="Path to issues.md (default: ./issues.md)",
    )
    parser.add_argument(
        "--skip-spec-gate",
        action="store_true",
        help="Bypass the gate; emit a 'bypassed' telemetry event",
    )
    parser.add_argument(
        "--force-sprint-mode",
        action="store_true",
        help="Override KIT_SPRINT_MODE env (for testing)",
    )
    args = parser.parse_args(argv)

    issues_md = Path(args.issues_md)
    if not issues_md.exists():
        print(json.dumps({"error": f"issues.md not found at {issues_md}"}))
        return 2

    if not re.match(r"^ISSUE-\d+$", args.issue_id):
        print(json.dumps({"error": f"invalid issue id: {args.issue_id}"}))
        return 2

    issue = parse_issue(issues_md, args.issue_id)
    if issue is None:
        print(json.dumps({"error": f"{args.issue_id} not found in {issues_md}"}))
        return 2

    sprint_mode = args.force_sprint_mode or os.environ.get(SPRINT_ENV) == "1"
    result = decide(issue, issues_md.resolve().parent, sprint_mode, args.skip_spec_gate)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
