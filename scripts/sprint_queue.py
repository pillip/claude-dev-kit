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
import os
import re
import subprocess
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
    # FINALIZE (ISSUE-052): a reviewed issue whose PR was already merged before a
    # ship-phase crash — only smoke + registry remain, which still ends at shipped.
    "FINALIZE": "shipped",
}

# ISSUE-052 crash-recovery: timeout (seconds) for the optional `gh pr view` merge
# probe. The queue runs frequently, so an offline/hung `gh` must never block it —
# on timeout the probe degrades to a phase-only decision. Overridable and
# documented via the env knob below (env-knob-documentation review lesson).
#   KIT_SPRINT_QUEUE_GH_TIMEOUT — seconds for the merge-state probe (default 10)
GH_MERGE_PROBE_TIMEOUT: float = float(
    os.environ.get("KIT_SPRINT_QUEUE_GH_TIMEOUT", "10")
)

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
        pr_raw = _extract_field(part, "PR")

        issues[issue_id] = {
            "manual": manual_raw.lower() == "true",
            "depends_on": _parse_depends_on(depends_raw),
            "priority": priority_raw.lower() if priority_raw else "p2",
            "status": status_raw.lower() if status_raw else "",
            # PR ref (URL or number) — used by the ISSUE-052 merge-state probe.
            "pr": pr_raw.strip(),
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


# ── Crash-recovery: already-merged PR awareness (ISSUE-052) ─────────


def _gh_pr_merge_state(pr_ref, *, timeout=None, runner=None):
    """Return the merge state of a PR: ``"merged"``, ``"open"``, or ``None``.

    Uses ``gh pr view <ref> --json state,mergedAt``. A PR counts as merged when
    ``state == "MERGED"`` OR a ``mergedAt`` timestamp is present (the GH issue is
    then CLOSED). Degrades to ``None`` — never raises — on an empty ref, a
    missing/unauthenticated ``gh``, a non-zero exit, a timeout, or unparseable
    JSON, so callers fall back to a phase-only decision. Offline-safe: the probe
    is timeout-guarded (see ``GH_MERGE_PROBE_TIMEOUT``).

    ``runner`` (defaults to ``subprocess.run``) is injectable for testing.
    """
    if not pr_ref:
        return None
    runner = runner or subprocess.run
    if timeout is None:
        timeout = GH_MERGE_PROBE_TIMEOUT
    try:
        proc = runner(
            ["gh", "pr", "view", pr_ref, "--json", "state,mergedAt"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"Warning: gh merge-state probe failed for {pr_ref}: {exc}; "
            "falling back to phase-only decision",
            file=sys.stderr,
        )
        return None
    if proc.returncode != 0:
        print(
            f"Warning: `gh pr view` exited {proc.returncode} for {pr_ref}: "
            f"{proc.stderr.strip()}; falling back to phase-only decision",
            file=sys.stderr,
        )
        return None
    try:
        data = json.loads(proc.stdout)
    except (ValueError, TypeError) as exc:
        print(
            f"Warning: `gh pr view` returned unparseable JSON for {pr_ref}: {exc}; "
            "falling back to phase-only decision",
            file=sys.stderr,
        )
        return None
    state = str(data.get("state") or "").upper()
    if state == "MERGED" or data.get("mergedAt"):
        return "merged"
    return "open"


def classify_ship_ready(ship_ready, issues_meta, *, merge_state_fn=None):
    """Split reviewed/ship-ready issues into ``(finalize_ready, ship_ready)``.

    An issue whose PR is already MERGED (a crash between the squash-merge and the
    post-merge smoke checkpoint) goes to ``finalize_ready`` — only smoke +
    registry remain, and no re-merge must be attempted. Un-merged or indeterminate
    (``gh`` error / no PR ref) issues stay in ``ship_ready`` (phase-only fallback).
    Order is preserved and the probe is cached per PR ref.
    """
    merge_state_fn = merge_state_fn or _gh_pr_merge_state
    finalize_ready: list[str] = []
    still_ship: list[str] = []
    cache: dict[str, str | None] = {}
    for issue_id in ship_ready:
        pr_ref = issues_meta.get(issue_id, {}).get("pr", "")
        if not pr_ref:
            # No PR recorded — cannot probe; leave it on the normal ship path.
            still_ship.append(issue_id)
            continue
        if pr_ref not in cache:
            cache[pr_ref] = merge_state_fn(pr_ref)
        if cache[pr_ref] == "merged":
            finalize_ready.append(issue_id)
        else:
            still_ship.append(issue_id)
    return finalize_ready, still_ship


def ship_merge_decision(pr_ref, *, merge_state_fn=None):
    """Idempotent ship-merge decision (ISSUE-052 crash-recovery safety net).

    Returns ``{"action": "skip"|"merge", "reason": str}``. ``"skip"`` when the PR
    is already merged — the ship executor then proceeds straight to smoke +
    registry without a second merge. ``"merge"`` otherwise, INCLUDING the
    ``gh``-indeterminate case (let the real ``gh pr merge`` surface any failure).
    This guard is the safety net even if the queue's classification is stale.
    """
    merge_state_fn = merge_state_fn or _gh_pr_merge_state
    state = merge_state_fn(pr_ref)
    if state == "merged":
        return {
            "action": "skip",
            "reason": (
                f"PR {pr_ref} is already merged — skip merge, proceed to "
                "smoke + registry finalization"
            ),
        }
    return {
        "action": "merge",
        "reason": f"PR {pr_ref} not merged (state={state}) — perform the merge",
    }


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

    Priority order: FINALIZE > SHIP > REVIEW > IMPLEMENT > STUCK > DONE.
    Caps targets at max_parallel.
    """
    # FINALIZE (ISSUE-052): reviewed issues whose PR is already merged are half-
    # shipped — clear them first (smoke + registry only) so the pipeline reaches a
    # clean state and no re-merge is ever attempted. `.get` keeps callers that
    # build queues without this key (compute_queues) working unchanged.
    if queues.get("finalize_ready"):
        targets = queues["finalize_ready"][:max_parallel]
        return {
            "action": "FINALIZE",
            "targets": targets,
            "reason": (
                f"{len(queues['finalize_ready'])} reviewed issue(s) whose PR is "
                "already merged — finalize only (smoke + registry), no re-merge"
            ),
        }

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

    # ISSUE-052 crash-recovery: for reviewed/ship-ready issues, probe the PR merge
    # state before proposing SHIP. An already-merged PR (a crash between merge and
    # the smoke checkpoint) is reclassified as FINALIZE (smoke + registry only).
    # Guarded so an offline/hung/unauthenticated `gh` never blocks or crashes the
    # frequently-run queue: probes are timeout-bounded and degrade to phase-only.
    # `--no-check-merged` opts out entirely (offline/deterministic runs).
    if not getattr(args, "no_check_merged", False) and queues["ship_ready"]:
        finalize_ready, still_ship = classify_ship_ready(
            queues["ship_ready"], issues_meta
        )
        queues["finalize_ready"] = finalize_ready
        queues["ship_ready"] = still_ship

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


def cmd_ship_merge_decision(args: argparse.Namespace) -> int:
    """Handler for 'ship-merge-decision' — idempotent merge guard (ISSUE-052).

    Emits the JSON decision (``skip`` if the PR is already merged, else ``merge``)
    that the ship executor consults before running ``gh pr merge``, so crash
    recovery in the ship window never attempts a second merge. Always exits 0 —
    a ``gh``-indeterminate probe yields ``merge`` and lets the real merge surface
    any failure.
    """
    print(json.dumps(ship_merge_decision(args.pr)))
    return 0


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
    na.add_argument(
        "--no-check-merged",
        action="store_true",
        help=(
            "Skip the ISSUE-052 `gh pr view` merge-state probe for reviewed "
            "issues (offline / deterministic runs). Reviewed issues then always "
            "propose SHIP (phase-only), never FINALIZE."
        ),
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
        choices=["SHIP", "REVIEW", "IMPLEMENT", "PIPELINE", "FINALIZE"],
        help="The action that was executed",
    )
    va.add_argument(
        "--targets",
        required=True,
        help="Comma-separated issue IDs (e.g. ISSUE-001,ISSUE-002)",
    )

    # ship-merge-decision subcommand (ISSUE-052 idempotent merge guard)
    smd = subparsers.add_parser(
        "ship-merge-decision",
        help="Emit skip/merge for a PR so ship recovery never re-merges",
    )
    smd.add_argument(
        "--pr",
        required=True,
        help="PR ref (number or URL) to probe for an already-merged state",
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
    elif args.command == "ship-merge-decision":
        return cmd_ship_merge_decision(args)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
