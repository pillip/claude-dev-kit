#!/usr/bin/env python3
"""Sprint pipeline queue computation and transition validation.

Deterministic replacement for LLM-driven queue computation in sprint skill
steps 4b-c (next action selection) and 4f (phase transition validation).

Subcommands:
  next-action  Compute the highest-priority action from sprint_state.md
  validate     Verify that phase transitions occurred after a team-lead run

Exit codes:
  0 — success (JSON output on stdout)
  1 — operational issue (nothing actionable, validation failure)
  2 — usage error (missing files, malformed input)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ── Valid phase values (pipeline order) ─────────────────────────────

PHASES = [
    "backlog",
    "implementing",
    "implemented",
    "reviewing",
    "reviewed",
    "shipping",
    "shipped",
]

# Expected end-phase after each action completes
ACTION_END_PHASE: dict[str, str] = {
    "PIPELINE": "shipped",
    "IMPLEMENT": "implemented",
    "REVIEW": "reviewed",
    "SHIP": "shipped",
}

# Phases that count as "in-flight" (actively being worked on)
IN_FLIGHT_PHASES = {"implementing", "reviewing", "shipping"}

# Priority sort order (lower = higher priority)
PRIORITY_ORDER = {"p0": 0, "p1": 1, "p2": 2, "p3": 3}


# ── Markdown parsing helpers ────────────────────────────────────────


def _extract_field(text: str, field_name: str) -> str:
    """Extract a metadata field value from issue text.

    Reused pattern from validate_issues.py.
    """
    match = re.search(rf"^- {field_name}:[ \t]*(.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _parse_depends_on(raw: str) -> list[str]:
    """Parse a Depends-On field value into a list of issue IDs.

    Handles: "ISSUE-001, ISSUE-002", "ISSUE-001", "none", "".
    """
    if not raw or raw.lower() == "none":
        return []
    return [dep.strip() for dep in re.findall(r"ISSUE-\d+", raw)]


def parse_sprint_table(text: str) -> list[dict[str, str]]:
    """Parse the Issue Progress table from sprint_state.md.

    Returns list of dicts with keys: issue, status, attempts, last_error, phase.
    """
    # Locate the ## Issue Progress section
    section_match = re.search(
        r"## Issue Progress\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if not section_match:
        return []

    section = section_match.group(1)

    # Extract table rows
    rows: list[dict[str, str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        # Skip header and separator rows
        if len(cells) < 5:
            continue
        if cells[0].lower() in ("issue", "") or cells[0].startswith("-"):
            continue
        if all(c.replace("-", "").strip() == "" for c in cells):
            continue

        rows.append(
            {
                "issue": cells[0],
                "status": cells[1].lower(),
                "attempts": cells[2],
                "last_error": cells[3],
                "phase": cells[4].lower().strip(),
            }
        )

    return rows


def parse_issues_metadata(text: str) -> dict[str, dict]:
    """Parse issues.md to extract Manual, Depends-On, Priority, and Status per issue.

    Returns dict keyed by issue ID with sub-dict:
      manual: bool, depends_on: list[str], priority: str, status: str
    """
    issues: dict[str, dict] = {}
    parts = re.split(r"(?=^### ISSUE-\d+:)", text, flags=re.MULTILINE)

    for part in parts:
        header_match = re.match(r"^### (ISSUE-\d+):", part)
        if not header_match:
            continue

        issue_id = header_match.group(1)
        manual_raw = _extract_field(part, "Manual")
        depends_raw = _extract_field(part, "Depends-On")
        priority_raw = _extract_field(part, "Priority")
        status_raw = _extract_field(part, "Status")

        issues[issue_id] = {
            "manual": manual_raw.lower() == "true",
            "depends_on": _parse_depends_on(depends_raw),
            "priority": priority_raw.lower() if priority_raw else "p2",
            "status": status_raw.lower() if status_raw else "",
        }

    return issues


# ── Dependency validation ───────────────────────────────────────────


def detect_circular_deps(issues_meta: dict[str, dict]) -> list[str]:
    """Detect circular Depends-On chains using DFS.

    Returns the cycle as a list of issue IDs if found, empty list otherwise.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {iid: WHITE for iid in issues_meta}
    parent: dict[str, str] = {}

    def _dfs(node: str) -> list[str]:
        color[node] = GRAY
        for dep in issues_meta.get(node, {}).get("depends_on", []):
            if dep not in color:
                continue  # dependency references an issue not in issues_meta
            if color[dep] == GRAY:
                # Found a cycle — reconstruct it
                cycle = [dep, node]
                cur = node
                while parent.get(cur) and parent[cur] != dep:
                    cur = parent[cur]
                    cycle.append(cur)
                cycle.reverse()
                return cycle
            if color[dep] == WHITE:
                parent[dep] = node
                result = _dfs(dep)
                if result:
                    return result
        color[node] = BLACK
        return []

    for issue_id in issues_meta:
        if color[issue_id] == WHITE:
            result = _dfs(issue_id)
            if result:
                return result
    return []


# ── Queue computation ───────────────────────────────────────────────


def compute_queues(
    sprint_rows: list[dict[str, str]],
    issues_meta: dict[str, dict],
) -> dict[str, list[str]]:
    """Compute the four pipeline queues from sprint state and issue metadata.

    Returns dict with keys: ship_ready, review_ready, implement_ready, in_flight.
    """
    # Build a set of resolved issues (shipped or dropped in sprint state)
    resolved_phases = {"shipped"}
    resolved_statuses = {"dropped", "waiting"}
    resolved_issues: set[str] = set()
    for row in sprint_rows:
        if row["phase"] in resolved_phases or row["status"] in resolved_statuses:
            resolved_issues.add(row["issue"])

    ship_ready: list[str] = []
    review_ready: list[str] = []
    implement_ready: list[str] = []
    in_flight: list[str] = []

    for row in sprint_rows:
        issue_id = row["issue"]
        phase = row["phase"]
        status = row["status"]

        # Skip non-active issues
        if status in ("dropped", "waiting"):
            continue

        if phase == "reviewed":
            ship_ready.append(issue_id)
        elif phase == "implemented":
            review_ready.append(issue_id)
        elif phase in IN_FLIGHT_PHASES:
            in_flight.append(issue_id)
        elif phase == "backlog":
            meta = issues_meta.get(issue_id, {})
            # Filter out manual issues
            if meta.get("manual", False):
                continue
            # Filter out issues with unresolved dependencies
            deps = meta.get("depends_on", [])
            if deps and not all(d in resolved_issues for d in deps):
                continue
            implement_ready.append(issue_id)

    # Sort implement_ready by priority (P0 first)
    implement_ready.sort(
        key=lambda iid: PRIORITY_ORDER.get(
            issues_meta.get(iid, {}).get("priority", "p2"), 99
        )
    )

    return {
        "ship_ready": ship_ready,
        "review_ready": review_ready,
        "implement_ready": implement_ready,
        "in_flight": in_flight,
    }


def choose_action(
    queues: dict[str, list[str]],
    max_parallel: int,
) -> dict:
    """Apply strict priority to choose ONE action.

    Priority order: SHIP > REVIEW > IMPLEMENT > STUCK > DONE.
    Caps targets at max_parallel.
    """
    if queues["ship_ready"]:
        targets = queues["ship_ready"][:max_parallel]
        return {
            "action": "SHIP",
            "targets": targets,
            "reason": f"{len(queues['ship_ready'])} issue(s) in reviewed status — must ship before other work",
        }

    if queues["review_ready"]:
        targets = queues["review_ready"][:max_parallel]
        return {
            "action": "REVIEW",
            "targets": targets,
            "reason": f"{len(queues['review_ready'])} issue(s) in implemented status — must review before implementing new issues",
        }

    if queues["implement_ready"]:
        targets = queues["implement_ready"][:max_parallel]
        return {
            "action": "PIPELINE",
            "targets": targets,
            "reason": f"{len(queues['implement_ready'])} issue(s) ready for full pipeline — implement→review→ship in one invocation",
        }

    if queues["in_flight"]:
        return {
            "action": "STUCK",
            "targets": queues["in_flight"],
            "reason": f"{len(queues['in_flight'])} issue(s) stuck in progress: {', '.join(queues['in_flight'])}",
        }

    return {
        "action": "DONE",
        "targets": [],
        "reason": "All issues are shipped, waiting, or dropped",
    }


# ── Transition validation ───────────────────────────────────────────


def validate_transitions(
    sprint_rows: list[dict[str, str]],
    action: str,
    targets: list[str],
) -> dict:
    """Validate that target issues transitioned to the expected end-phase.

    Returns dict: {valid, transitioned, stuck, errors}.
    """
    expected_phase = ACTION_END_PHASE.get(action)
    if not expected_phase:
        return {
            "valid": False,
            "transitioned": [],
            "stuck": targets,
            "errors": [f"Unknown action: {action}"],
        }

    # Build lookup from sprint rows
    phase_by_issue: dict[str, str] = {}
    status_by_issue: dict[str, str] = {}
    for row in sprint_rows:
        phase_by_issue[row["issue"]] = row["phase"]
        status_by_issue[row["issue"]] = row["status"]

    transitioned: list[str] = []
    stuck: list[str] = []
    errors: list[str] = []

    # For PIPELINE, any progress beyond backlog counts as "progressed" (not stuck).
    # The issue may have stopped mid-pipeline due to a phase failure, which is
    # expected — it will be picked up by a standalone REVIEW or SHIP retry.
    pipeline_progress_phases = {
        "implementing", "implemented", "reviewing", "reviewed", "shipping", "shipped",
    }

    for issue_id in targets:
        current_phase = phase_by_issue.get(issue_id, "")
        current_status = status_by_issue.get(issue_id, "")

        # Issue marked as waiting/dropped counts as "handled" (escalated)
        if current_status in ("waiting", "dropped"):
            transitioned.append(issue_id)
            continue

        if current_phase == expected_phase:
            transitioned.append(issue_id)
        elif action == "PIPELINE" and current_phase in pipeline_progress_phases:
            # Pipeline made progress but stopped before shipped (phase failure).
            # This is not stuck — the issue will be retried via REVIEW or SHIP.
            transitioned.append(issue_id)
        else:
            stuck.append(issue_id)
            errors.append(
                f"{issue_id}: Phase is '{current_phase}', expected '{expected_phase}'"
            )

    return {
        "valid": len(stuck) == 0,
        "transitioned": transitioned,
        "stuck": stuck,
        "errors": errors,
    }


# ── CLI subcommand handlers ─────────────────────────────────────────


def cmd_next_action(args: argparse.Namespace) -> int:
    """Handler for 'next-action' subcommand."""
    sprint_path = Path(args.sprint_state)
    issues_path = Path(args.issues)

    if not sprint_path.exists():
        print(f"Error: {sprint_path} not found", file=sys.stderr)
        return 2
    if not issues_path.exists():
        print(f"Error: {issues_path} not found", file=sys.stderr)
        return 2

    sprint_text = sprint_path.read_text(encoding="utf-8")
    issues_text = issues_path.read_text(encoding="utf-8")

    sprint_rows = parse_sprint_table(sprint_text)
    if not sprint_rows:
        # Distinguish between empty table and parse failure:
        # Count non-header, non-separator data rows with pipe delimiters
        import re as _re
        data_lines = [
            line for line in sprint_text.splitlines()
            if line.strip().startswith("|") and line.strip().endswith("|")
            and not _re.match(r"^\|[\s\-|]+\|$", line.strip())
            and "Issue" not in line and "Phase" not in line
        ]
        if data_lines:
            print("Error: sprint_state.md has data rows but parsing returned 0 rows", file=sys.stderr)
            print("  Check table format: | Issue | Status | Attempts | Last Error | Phase |", file=sys.stderr)
            return 2
        result = {
            "action": "DONE",
            "targets": [],
            "reason": "No issues found in sprint_state.md Issue Progress table",
        }
        print(json.dumps(result))
        return 1

    issues_meta = parse_issues_metadata(issues_text)

    # Detect circular dependencies before computing queues
    cycle = detect_circular_deps(issues_meta)
    if cycle:
        print(f"Error: Circular Depends-On detected: {' → '.join(cycle)}", file=sys.stderr)
        result = {
            "action": "STUCK",
            "targets": cycle,
            "reason": f"Circular dependency: {' → '.join(cycle)}. Break the cycle in issues.md.",
        }
        print(json.dumps(result))
        return 1

    queues = compute_queues(sprint_rows, issues_meta)
    result = choose_action(queues, args.max_parallel)

    print(json.dumps(result))
    return 0 if result["action"] not in ("DONE", "STUCK") else 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Handler for 'validate' subcommand."""
    sprint_path = Path(args.sprint_state)

    if not sprint_path.exists():
        print(f"Error: {sprint_path} not found", file=sys.stderr)
        return 2

    sprint_text = sprint_path.read_text(encoding="utf-8")
    sprint_rows = parse_sprint_table(sprint_text)

    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    if not targets:
        print("Error: --targets is empty", file=sys.stderr)
        return 2

    result = validate_transitions(sprint_rows, args.action, targets)
    print(json.dumps(result))
    return 0 if result["valid"] else 1


# ── CLI entry point ─────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sprint pipeline queue computation and transition validation",
    )
    subparsers = parser.add_subparsers(dest="command")

    # next-action subcommand
    na = subparsers.add_parser(
        "next-action",
        help="Compute the highest-priority action from sprint state",
    )
    na.add_argument(
        "--sprint-state",
        required=True,
        help="Path to docs/sprint_state.md",
    )
    na.add_argument(
        "--issues",
        required=True,
        help="Path to issues.md",
    )
    na.add_argument(
        "--max-parallel",
        type=int,
        default=3,
        help="Maximum issues to process in parallel (default: 3)",
    )

    # validate subcommand
    va = subparsers.add_parser(
        "validate",
        help="Verify that phase transitions occurred",
    )
    va.add_argument(
        "--sprint-state",
        required=True,
        help="Path to docs/sprint_state.md",
    )
    va.add_argument(
        "--action",
        required=True,
        choices=["SHIP", "REVIEW", "IMPLEMENT", "PIPELINE"],
        help="The action that was executed",
    )
    va.add_argument(
        "--targets",
        required=True,
        help="Comma-separated issue IDs (e.g. ISSUE-001,ISSUE-002)",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if not args.command:
        parser.print_help()
        return 2

    if args.command == "next-action":
        return cmd_next_action(args)
    elif args.command == "validate":
        return cmd_validate(args)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
