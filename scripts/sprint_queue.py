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

Environment:
  KIT_SPRINT_DISPATCH_ABOVE_WATERMARK — 1/true/yes/on widens autonomous dispatch
    to Board issues ABOVE the pinned sprint roster boundary (default: off — they
    are flagged in `unrostered` but never targeted)
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
    if not isinstance(data, dict):
        # Valid JSON that is not an object (null / list / scalar) — treat as
        # indeterminate rather than raising, so AC3's "never crashes" holds.
        print(
            f"Warning: `gh pr view` JSON for {pr_ref} was not an object; "
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

# ISSUE-068 roster-ID shape. The digit run is BOUNDED on purpose: CPython 3.11+
# caps str→int conversion at ``sys.int_max_str_digits`` (4300), so an unbounded
# ``\d+`` fed to ``int()`` turns a pathological Board/roster cell into an
# uncaught ValueError — i.e. a traceback instead of JSON from the script that
# drives the sprint loop. A cell wider than the bound simply does not match and
# is ignored (no watermark contribution, not a candidate).
_ROSTER_ID_RE = re.compile(r"ISSUE-(\d{1,9})")

# Board ``Status`` comparisons below are deliberately EXACT, not prefix matches.
# Real issues.md entries do annotate the field (this repo carries
# ``drop (superseded by ISSUE-033, 2026-07-16)``), and tolerating the annotation
# looks like a robustness win — but both comparisons gate autonomous dispatch,
# and an annotation is usually written to say the opposite of its keyword:
# ``backlog (blocked — do NOT auto-dispatch)`` would be admitted, and
# ``done (security sign-off still pending)`` would resolve a dependency that is
# not actually met. Exact matching fails CLOSED in both directions, which is the
# safe side for an admission filter and a dependency gate. The excluded-by-
# annotation cases are pinned by TestAnnotatedBoardStatusFailsClosed.

# ── Roster watermark pin (ISSUE-069) ────────────────────────────────

# The ONLY accepted spelling of the sprint_state ``## Meta`` field that holds the
# sprint-start boundary. Acceptance is exact (see parse_roster_watermark).
_WATERMARK_CANONICAL_NAME = "- Roster-Watermark"

# Detection is deliberately BROAD — an occurrence-whitelist, not a phrasing
# blacklist: line-anchored, case-insensitive, optional bullet and ``**``/backtick
# decoration, optional whitespace before the colon. A field-shaped line the
# detector MISSED would be honoured-by-omission: the boundary would silently
# revert to the max-rostered-ID derivation with nothing in `reason` to say so.
# Leading indentation and whitespace before the colon are therefore DETECTED and
# then rejected as non-canonical — being found-then-refused is the whole point,
# because it fails closed and announces.
_WATERMARK_FIELD_RE = re.compile(
    r"^[ \t]*[-*]?[ \t]*\*{0,2}`?roster-watermark`?\*{0,2}[ \t]*:",
    re.IGNORECASE,
)


def _meta_section_bounds(lines: list[str]) -> tuple[int, int]:
    """Half-open ``[start, end)`` line range of the ``## Meta`` section body.

    The terminating condition is copied from the document structure
    ``parse_sprint_table`` already relies on (``## Meta`` → the next ``## ``
    heading → EOF), so an h3 sub-heading does not close the section and a stray
    paste under a sibling ``## `` heading is outside it. ``(0, 0)`` — an empty
    range — when there is no ``## Meta`` heading at all.
    """
    for start, line in enumerate(lines):
        if line == "## Meta":
            for end in range(start + 1, len(lines)):
                if lines[end].startswith("## "):
                    return start + 1, end
            return start + 1, len(lines)
    return 0, 0


def _truncate_value(value: str) -> str:
    """Cap an echoed untrusted value at 40 chars + an ellipsis.

    A rejected ``## Meta`` value is quoted back in ``reason``, so a pathological
    one (e.g. a 4301-digit ID) must not be amplified through stdout.
    """
    return value if len(value) <= 40 else value[:40] + "…"


def parse_roster_watermark(
    sprint_text: str,
    issues_meta: dict[str, dict],
) -> tuple[int | None, str | None, bool]:
    """Read the sprint-start roster boundary pinned in sprint_state's ``## Meta``.

    Returns ``(num, rejection_detail, present)``:
      * ``num`` — the pinned boundary when a canonical field passed every
        validation, else ``None`` (the caller then falls back to the ISSUE-068
        max-rostered-ID derivation).
      * ``rejection_detail`` — ``None`` when the field is absent or accepted; a
        short human-readable reason when it was found and refused.
      * ``present`` — ``True`` when a field-shaped line exists ANYWHERE in the
        document, accepted or not. The dispatch gate in ``cmd_next_action`` keys
        on this rather than on acceptance, so "we found a boundary declaration
        and refused it" stays distinguishable from "there is none".

    ``## Meta`` is workspace-writable state every phase executor rewrites, i.e.
    untrusted input this script reads back and acts on: detection is broad,
    acceptance is narrow, and everything in between falls back with the reason
    named in the output. Occurrence counting is deliberately FENCE-BLIND — a copy
    inside a code fence still counts as a duplicate. A fence-aware count and a
    fence-blind one degrade to the same announced fallback here, so mirroring the
    document's fence structure would be unjustified complexity, and the
    fence-blind rule additionally cannot be defeated by wrapping a second field
    in backticks.

    Never raises: every step is total for a ``str``/``dict`` pair, and both digit
    runs handed to ``int()`` are bounded by ``_ROSTER_ID_RE``.
    """
    lines = (sprint_text or "").splitlines()
    hits = [
        (index, line)
        for index, line in enumerate(lines)
        if _WATERMARK_FIELD_RE.match(line)
    ]
    if not hits:
        return None, None, False
    if len(hits) > 1:
        return None, f"{len(hits)} field lines found, expected exactly one", True

    index, line = hits[0]
    meta_start, meta_end = _meta_section_bounds(lines)
    if not meta_start <= index < meta_end:
        return None, "field is outside the ## Meta section", True

    name, _, raw_value = line.partition(":")
    if name != _WATERMARK_CANONICAL_NAME:
        return None, (
            f"non-canonical field line, expected "
            f"'{_WATERMARK_CANONICAL_NAME}: ISSUE-NNN'"
        ), True

    value = raw_value.strip()
    match = _ROSTER_ID_RE.fullmatch(value)
    if not match:
        return None, (
            f"value {_truncate_value(value)!r} is not a canonical "
            "ISSUE-<digits> id"
        ), True
    num = int(match.group(1))

    # Range sanity against the LIVE Board: a boundary above every real ID
    # silences the whole control while looking perfectly well-formed. Skipped
    # when no Board key is parseable, so an unrelated issues.md problem cannot
    # cost the sprint its pinned boundary. The bound on `_ROSTER_ID_RE` is
    # load-bearing on this scan too — an overlong Board heading reaching `int()`
    # is the same CPython 4300-digit crash via a different input file.
    board_nums = [
        board_match.group(1)
        for board_match in (_ROSTER_ID_RE.fullmatch(key) for key in issues_meta)
        if board_match
    ]
    if board_nums:
        board_max = max(int(digits) for digits in board_nums)
        if num > board_max:
            return None, (
                f"ISSUE-{num:03d} is above the highest Board id "
                f"ISSUE-{board_max:03d}"
            ), True

    return num, None, True


# ISSUE-069 opt-in knob: widen autonomous dispatch to Board issues ABOVE the
# pinned boundary (out-of-scope work). Read at CALL time, deliberately NOT via
# the module-level import-time pattern `GH_MERGE_PROBE_TIMEOUT` uses above: a
# constant snapshotted at import is unreachable by monkeypatch (the module is
# imported long before any test runs) and unsettable by an operator who exports
# the knob after the interpreter starts. The split in convention is intentional.
#   KIT_SPRINT_DISPATCH_ABOVE_WATERMARK — 1/true/yes/on dispatches above-boundary
#   issues (default off: they are flagged in `unrostered` but never targeted)
DISPATCH_ABOVE_WATERMARK_ENV = "KIT_SPRINT_DISPATCH_ABOVE_WATERMARK"
_DISPATCH_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _dispatch_above_watermark_enabled() -> bool:
    """True only for the documented truthy vocabulary — everything else is OFF."""
    raw = os.environ.get(DISPATCH_ABOVE_WATERMARK_ENV, "")
    return raw.strip().lower() in _DISPATCH_TRUTHY


def augment_roster_from_board(
    sprint_rows: list[dict[str, str]],
    issues_meta: dict[str, dict],
    *,
    pinned_watermark: int | None = None,
) -> tuple[list[dict], list[str]]:
    """Synthesize roster rows for Board-registered backlog issues (ISSUE-068).

    Rationale: ``next-action``'s roster is the sprint_state Issue Progress
    table, so issues registered in issues.md MID-SPRINT (e.g. by /triage or
    /plan while the loop runs) were invisible — the queue could emit DONE with
    actionable work still on the Board. This augmentation makes next-action
    auto-consider them without touching any rostered row.

    Watermark scoping: an issue counts as mid-sprint-registered if and only if
    its numeric ID is above EVERY sprint-start rostered ID. ``pinned_watermark``
    (ISSUE-069) IS that boundary when given — the roster max is then not
    consulted at all, so the boundary cannot drift upward as the roster grows and
    re-hide a lower-ID sibling it already surfaced. Without a pin the boundary is
    derived as ``max`` of the rostered ``ISSUE-<digits>`` cells, byte-identically
    to ISSUE-068: no rostered ID → no watermark → no synthesis. Pre-existing
    Board backlog below the boundary was deliberately excluded at sprint planning
    and stays invisible. The legacy empty-table DONE path is preserved in both
    cases (an un-started sprint must not become a Board-wide dispatcher).

    Synthesized candidates must be: above the watermark, not already rostered,
    Board ``Status: backlog``, and not ``Manual: true``. Each synthesized row
    is a backlog-phase row tagged ``unrostered: True`` so compute_queues can
    scope its Board-resolved dependency loosening to this caller class only.

    Returns ``(augmented_rows, unrostered_ids)``: the original rows unchanged
    (never mutated) with synthesized rows appended in ascending numeric-ID
    order, and the same sorted ID list.
    """
    if not sprint_rows:
        return sprint_rows, []

    rostered_ids: set[str] = set()
    rostered_nums: list[int] = []
    for row in sprint_rows:
        cell = row.get("issue", "")
        rostered_ids.add(cell)
        match = _ROSTER_ID_RE.fullmatch(cell)
        if match:
            rostered_nums.append(int(match.group(1)))

    if pinned_watermark is None:
        if not rostered_nums:
            return sprint_rows, []
        watermark = max(rostered_nums)
    else:
        watermark = pinned_watermark

    candidates: list[tuple[int, str]] = []
    for issue_id, meta in issues_meta.items():
        match = _ROSTER_ID_RE.fullmatch(issue_id)
        if not match:
            continue
        num = int(match.group(1))
        if num <= watermark:
            continue
        if issue_id in rostered_ids:
            continue
        if meta.get("status") != "backlog":
            continue
        if meta.get("manual", False):
            continue
        candidates.append((num, issue_id))

    candidates.sort()
    unrostered_ids = [issue_id for _, issue_id in candidates]
    synthesized = [
        {
            "issue": issue_id,
            "status": "active",
            "attempts": "0",
            "last_error": "-",
            "phase": "backlog",
            "unrostered": True,
        }
        for issue_id in unrostered_ids
    ]
    return sprint_rows + synthesized, unrostered_ids


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
            dep_resolved = resolved_issues
            if row.get("unrostered"):
                # ISSUE-068: synthesized (unrostered) rows ONLY also accept
                # Board-resolved deps — issues done/dropped on the Board that
                # never had a sprint row. Rostered rows keep the legacy
                # table-only resolution semantics byte-identically.
                dep_resolved = resolved_issues | {
                    iid
                    for iid, m in issues_meta.items()
                    if m.get("status") in ("done", "drop", "dropped")
                }
            if deps and not all(d in dep_resolved for d in deps):
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


def diagnose_carry_forward_gaps(
    sprint_rows: list[dict[str, str]],
    issues_meta: dict[str, dict],
    queues: dict[str, list[str]],
) -> list[tuple[str, list[str]]]:
    """Explain rostered backlog rows stalled by a PRIOR-sprint dependency.

    A rostered row resolves its ``Depends-On`` from the Issue Progress table
    ONLY. ISSUE-068's Board-resolved loosening deliberately covers synthesized
    (``unrostered``) rows only, and TC-068d pins that. So a rostered row whose
    dependency was satisfied in an earlier sprint — Board ``done``/``drop``/
    ``dropped`` with no row in this sprint's table — is undispatchable and
    nothing says why.

    This is a DIAGNOSIS, not a relaxation: the rostered-row contract stays
    table-only. The helper mutates nothing, and the caller may only feed it into
    ``reason`` — never into ``action``, ``targets`` or a queue.

    Returns ``[(issue_id, [dep_ids])]`` in Issue Progress table order. Board
    ``Status`` is matched EXACTLY, consistently with the ISSUE-068 filters:
    ``done (sign-off pending)`` does not resolve a dependency, so calling it
    "Board-resolved, only the row is missing" would be false advice.
    """
    rostered = {row.get("issue", "") for row in sprint_rows}
    queued = {issue_id for queue in queues.values() for issue_id in queue}

    gaps: list[tuple[str, list[str]]] = []
    for row in sprint_rows:
        if row.get("unrostered"):
            continue
        if row.get("phase") != "backlog":
            continue
        if row.get("status") in ("dropped", "waiting"):
            continue
        issue_id = row.get("issue", "")
        if issue_id in queued:
            continue
        meta = issues_meta.get(issue_id, {})
        if meta.get("manual", False):
            continue
        carried = [
            dep
            for dep in meta.get("depends_on", [])
            if dep not in rostered
            and issues_meta.get(dep, {}).get("status") in ("done", "drop", "dropped")
        ]
        if carried:
            gaps.append((issue_id, carried))
    return gaps


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
        if issue_id not in phase_by_issue:
            # ISSUE-068: a target entirely absent from the Issue Progress table
            # (e.g. a Board-discovered issue never written into sprint_state)
            # is reported explicitly instead of as an empty-phase mismatch.
            stuck.append(issue_id)
            errors.append(
                f"{issue_id}: no row in sprint_state Issue Progress table "
                f"(expected '{expected_phase}')"
            )
            continue

        current_phase = phase_by_issue[issue_id]
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

    # ISSUE-069: the roster boundary is PINNED at sprint start in sprint_state's
    # ## Meta, so it cannot drift upward as the roster grows and re-hide a
    # lower-ID sibling it already surfaced. An absent or refused pin falls back
    # to the ISSUE-068 max-rostered-ID derivation, named in `reason` below.
    pinned_watermark, watermark_detail, watermark_present = parse_roster_watermark(
        sprint_text, issues_meta
    )

    # ISSUE-068: surface Board-registered backlog issues that are absent from
    # the sprint roster (registered mid-sprint, above the roster ID watermark).
    # Synthesis happens BEFORE compute_queues so discovered issues can be
    # targeted; rostered rows and the empty-table path above are untouched.
    sprint_rows, unrostered_ids = augment_roster_from_board(
        sprint_rows, issues_meta, pinned_watermark=pinned_watermark
    )

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

    # ISSUE-068 (review): a synthesized row must never pre-empt the in-flight
    # STUCK escalation. `choose_action` checks implement_ready before in_flight,
    # so letting Board-discovered work populate implement_ready turns a STUCK on
    # an issue wedged in implementing/reviewing/shipping into a PIPELINE on new
    # work — and because the synthesized row is rebuilt with `attempts: "0"` on
    # every invocation, that starvation has no terminating counter: the wedged
    # issue's Attempts freezes and the >=3-attempt human escalation never fires.
    # Withholding only the synthesized ids keeps rostered-row outcomes identical
    # and still satisfies AC-1 (the issue stays surfaced via `unrostered`), so
    # discovery is deferred until the pipeline drains rather than dropped.
    if unrostered_ids and queues["in_flight"]:
        deferred = set(unrostered_ids)
        queues["implement_ready"] = [
            iid for iid in queues["implement_ready"] if iid not in deferred
        ]

    # ISSUE-069 (Harm B): above-boundary Board issues are FLAGGED, never
    # auto-driven through implement → review → `gh pr merge`. A sprint
    # deliberately scoped on older debt otherwise pulls in everything newer.
    #
    # The gate keys on field PRESENCE, not on acceptance: a REJECTED pin closes
    # it too. This is the one place where "fall back" does NOT mean "behave
    # exactly like legacy", and it is deliberate — a mangled ## Meta line must
    # never silently re-enable autonomous dispatch of unscoped work, or
    # corrupting one line becomes a way to widen a sprint's scope without opting
    # in. An ABSENT field is a legitimate pre-feature sprint and keeps the legacy
    # dispatch behaviour byte-identically (AC-6). Do NOT "simplify" this to key
    # on `pinned_watermark is not None`.
    #
    # Applied ALONGSIDE the in-flight deferral above, and only to the
    # synthesized ids, so rostered-row outcomes stay identical and the issues
    # remain visible in `unrostered`/`stranded`.
    dispatch_above = _dispatch_above_watermark_enabled()
    if unrostered_ids and watermark_present and not dispatch_above:
        withheld = set(unrostered_ids)
        queues["implement_ready"] = [
            iid for iid in queues["implement_ready"] if iid not in withheld
        ]

    result = choose_action(queues, args.max_parallel)

    # ISSUE-068: annotate the result whenever unrostered Board issues exist.
    # Without them, the output stays byte-identical to the legacy behavior.
    if unrostered_ids:
        result["unrostered"] = unrostered_ids
        if result["action"] == "DONE":
            # Discovered issues exist but none is actionable (e.g. unresolved
            # deps) — DONE must not be silent about them.
            result["stranded"] = unrostered_ids
            result["reason"] += (
                f" — WARNING: {len(unrostered_ids)} Board-registered backlog "
                "issue(s) absent from the sprint roster remain stranded: "
                f"{', '.join(unrostered_ids)}. Acknowledge before closing "
                "the sprint."
            )
        else:
            result["reason"] += (
                " [visibility: Board-registered issue(s) absent from the "
                f"sprint roster auto-considered: {', '.join(unrostered_ids)}]"
            )

    # ISSUE-069: every new signal lands in `reason` — the top-level key set stays
    # {action, targets, reason, unrostered, stranded}, which the sprint skill and
    # team-lead read. Clean runs stay quiet (an accepted or absent boundary with
    # nothing above it), which is what keeps the legacy `reason` byte-pins intact.

    # Note A — which boundary was used, and why, whenever that is not obvious.
    if watermark_detail is not None:
        # A refused boundary is announced even with an empty `unrostered`:
        # silence would be indistinguishable from health.
        result["reason"] += (
            f" [roster-watermark: rejected ({watermark_detail}) — fell back to "
            "the max rostered ID derivation]"
        )
    elif unrostered_ids and pinned_watermark is not None:
        result["reason"] += (
            f" [roster-watermark: pinned at ISSUE-{pinned_watermark:03d}]"
        )
    elif unrostered_ids:
        result["reason"] += (
            " [roster-watermark: absent from ## Meta — fell back to the max "
            "rostered ID derivation]"
        )

    # Note B — the dispatch decision for above-boundary work. Omitted entirely
    # when the field is absent: the gate is off in that state, so naming a knob
    # that would change nothing is noise.
    if unrostered_ids and watermark_present:
        if dispatch_above:
            result["reason"] += (
                f" [dispatch: {DISPATCH_ABOVE_WATERMARK_ENV} is set — "
                "above-boundary issue(s) dispatched]"
            )
        else:
            result["reason"] += (
                f" [dispatch: {len(unrostered_ids)} above-boundary issue(s) "
                "flagged but NOT dispatched — set "
                f"{DISPATCH_ABOVE_WATERMARK_ENV}=1 to dispatch them]"
            )

    # Note C — rostered rows stalled on a dependency satisfied in a PRIOR sprint.
    # Diagnosis only: `action`, `targets` and the queues are already decided.
    gaps = diagnose_carry_forward_gaps(sprint_rows, issues_meta, queues)
    if gaps:
        listed = ", ".join(
            f"{issue_id} (dep {', '.join(deps)})" for issue_id, deps in gaps
        )
        result["reason"] += (
            f" [carry-forward gap: {listed} — the dependency is resolved on the "
            "Board but has no Issue Progress row, and a rostered row resolves "
            "dependencies from that table only, so the row cannot dispatch. "
            "Carry the dependency forward by adding its Issue Progress row, or "
            "drop the dependency.]"
        )

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
