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


_ISSUE_PROGRESS_HEADING_RE = re.compile(r"^#{2,6}\s+Issue Progress\s*$")
_ATX_HEADING_RE = re.compile(r"^#{1,6}\s")

# The roster table is exactly: Issue | Status | Attempts | Last Error | Phase.
ROSTER_COLUMN_COUNT = 5

# A roster row's first cell is an issue ID. Used only to tell a row the roster
# MEANT to carry from the record-table rows the boundary must exclude. Header and
# separator lines never match it.
_ROSTER_ROW_SHAPE_RE = re.compile(r"^\|\s*ISSUE-\d+\s*\|")

# A fenced code block is illustration, never roster state. ISSUE-076 review:
# `agents/team-lead.md` teaches the writer agent a FENCED `## Issue Progress`
# example, and without this the first fenced heading wins the section and its
# example rows are dispatched as real work (identically broken on main).
_FENCE_RE = re.compile(r"^(?:`{3,}|~{3,})")


def _row_cells(line: str) -> list[str]:
    """Split a GFM table row into stripped cells."""
    return [c.strip() for c in line.strip("|").split("|")]


def _unfenced(lines: list[str]) -> list[str | None]:
    """Blank out every fenced line (and the fence delimiters themselves).

    Returns a list parallel to ``lines`` where a fenced position holds ``None``.
    ``None`` is deliberately neither a table row nor a heading, so a fence
    terminates a table exactly as any other non-row line does — which is what a
    GFM renderer does with it.
    """
    out: list[str | None] = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if _FENCE_RE.match(stripped):
            in_fence = not in_fence
            out.append(None)
        else:
            out.append(None if in_fence else stripped)
    return out


def _scan_issue_progress(text: str) -> tuple[list[str], list[str]]:
    """Scan the Issue Progress section once.

    Returns ``(table_lines, unparsed_roster_lines)``.

    ISSUE-076: the boundary is the table's own end, NOT the next h2. Phase
    executors write a `### Review outcomes` subsection table under Issue
    Progress, and a next-h2 capture swallowed it — its 6-column rows were then
    read as roster rows, with `cells[4]` ("High unresolved") taken as the Phase.
    A GFM table ends at the first line that is not a table row, so terminate
    there: blank line, prose, or a heading of any level.

    ISSUE-076 review: both of the new defences FAIL OPEN. They are correct about
    what to exclude but SILENT about it, and silence here is destructive, because
    a roster row that fails to parse is not merely absent — an in-flight issue
    keeps ``Status: backlog`` on the Board, so `augment_roster_from_board`
    re-materializes it as a fresh backlog candidate and a completed
    implement/review is run again from scratch (the synthesized row also resets
    ``attempts`` to 0, so the ≥3-attempt escalation never fires). Two triggers:

    * the boundary ``break`` discards EVERY row below a stray line inside the
      roster — and the line can be whitespace-only, hence invisible in an editor;
    * the exact-5 column guard discards a SINGLE off-shape row, e.g. one whose
      ``Last Error`` cell contains an unescaped ``|`` (error text is executor
      output, so this is not hypothetical).

    The parse contract is unchanged — both exclusions are the issue's specified
    behaviour. The second return value makes them loud, so a caller can refuse to
    dispatch off an under-read roster (review lesson 5: workspace-persisted state
    read by a gate is untrusted input, so validate on read).

    Rows beyond the next heading of ANY level belong to a different table — the
    `### Review outcomes` pattern this issue exists to exclude — and are never
    reported.

    Fenced code blocks are excluded throughout (review lesson 4's fence clause):
    a fenced `## Issue Progress` example otherwise wins the section outright and
    its illustration rows are dispatched as real work.
    """
    lines = _unfenced(text.splitlines())
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if line is not None and _ISSUE_PROGRESS_HEADING_RE.match(line)
        ),
        None,
    )
    if start is None:
        return [], []

    rest = lines[start + 1 :]
    table: list[str] = []
    stop = len(rest)
    for offset, line in enumerate(rest):
        if line is not None and line.startswith("|") and line.endswith("|"):
            table.append(line)
        elif table or (line is not None and _ATX_HEADING_RE.match(line)):
            # The table ended — or a heading was reached before it ever began,
            # meaning this section carries no table at all.
            stop = offset
            break
    if not table:
        return [], []

    # (a) off-shape rows the column guard drops from INSIDE the table.
    unparsed = [
        line
        for line in table
        if _ROSTER_ROW_SHAPE_RE.match(line)
        and len(_row_cells(line)) != ROSTER_COLUMN_COUNT
    ]
    # (b) rows the boundary truncated away, up to the next heading of any level.
    for line in rest[stop:]:
        if line is None:
            continue
        if _ATX_HEADING_RE.match(line):
            break
        if _ROSTER_ROW_SHAPE_RE.match(line):
            unparsed.append(line)
    return table, unparsed


def _issue_progress_table_lines(text: str) -> list[str]:
    """The contiguous table rows directly under the Issue Progress heading."""
    return _scan_issue_progress(text)[0]


def unparsed_roster_rows(text: str) -> list[str]:
    """Rows the Issue Progress roster MEANT to carry that the parse dropped.

    Non-empty means the parse is an under-read — the roster was truncated by a
    stray line, or a row was off-shape — see `_scan_issue_progress`. Callers must
    refuse to dispatch work off such a roster rather than silently acting on the
    surviving fragment.
    """
    return _scan_issue_progress(text)[1]


def parse_sprint_table(text: str) -> list[dict[str, str]]:
    """Parse the Issue Progress table from sprint_state.md.

    Returns list of dicts with keys: issue, status, attempts, last_error, phase.
    """
    rows: list[dict[str, str]] = []
    for line in _issue_progress_table_lines(text):
        cells = _row_cells(line)
        # Off-shape rows are skipped, never index-read (they stay inside the
        # table, so a stray wide row does not truncate the roster).
        if len(cells) != ROSTER_COLUMN_COUNT:
            continue
        # Skip header and separator rows
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

# ISSUE-073 PR-ref shape. This is a ``fullmatch`` WHITELIST, not a sanitizer:
# nothing is stripped or normalized, a ref either matches one of the three
# attested forms or it is refused. Both inputs that reach the probe are
# untrusted text — the Board ``PR:`` field (hand-written, and not always a bare
# ref) and the model-chosen ``ship-merge-decision --pr`` argument — and both
# arrive at ``gh`` as a command argument, where an option-shaped value such as
# ``--repo attacker/evil`` would be re-read as a flag. The digit runs and the
# owner/repo segments are BOUNDED on purpose (never ``\d+`` / unbounded ``+``)
# for the same reason as ``_ROSTER_ID_RE`` below: the pattern runs over text the
# kit does not author, so a pathological cell must simply fail to match rather
# than drive the regex engine over an arbitrarily long run. ``gh``'s
# branch-name ref form is deliberately EXCLUDED — it is unattested in every
# live ``PR:`` value, and admitting it would mean admitting near-arbitrary text.
_PR_REF_RE = re.compile(
    r"\d{1,9}"
    r"|#\d{1,9}"
    r"|https://github\.com/[\w.-]{1,64}/[\w.-]{1,64}/pull/\d{1,9}"
)


def _gh_pr_merge_state(pr_ref, *, timeout=None, runner=None):
    """Return the merge state of a PR: ``"merged"``, ``"open"``, or ``None``.

    Uses ``gh pr view <ref> --json state,mergedAt``. A PR counts as merged when
    ``state == "MERGED"`` OR a ``mergedAt`` timestamp is present (the GH issue is
    then CLOSED). Degrades to ``None`` — never raises — on an empty ref, a
    missing/unauthenticated ``gh``, a non-zero exit, a timeout, or unparseable
    JSON, so callers fall back to a phase-only decision. Offline-safe: the probe
    is timeout-guarded (see ``GH_MERGE_PROBE_TIMEOUT``).

    Only three ref forms are accepted (ISSUE-073): ``123``, ``#123``, and
    ``https://github.com/<owner>/<repo>/pull/123``. A non-conforming or
    option-shaped ref is refused before ``gh`` is invoked at all and likewise
    degrades to ``None`` (indeterminate) rather than raising, preserving the
    never-raises contract.

    ``runner`` (defaults to ``subprocess.run``) is injectable for testing.
    """
    if not pr_ref:
        return None
    if not _PR_REF_RE.fullmatch(pr_ref):
        print(
            f"Warning: refusing PR ref {pr_ref!r} read from the issues.md `PR:` "
            "field (or `ship-merge-decision --pr`) — not one of the accepted forms "
            "`123`, `#123`, `https://github.com/<owner>/<repo>/pull/123`; "
            "falling back to phase-only decision",
            file=sys.stderr,
        )
        return None
    runner = runner or subprocess.run
    if timeout is None:
        timeout = GH_MERGE_PROBE_TIMEOUT
    try:
        proc = runner(
            ["gh", "pr", "view", "--json", "state,mergedAt", "--", pr_ref],
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
#
# ``[0-9]`` and NOT ``\d`` (review fix, ISSUE-069): for ``str`` patterns Python's
# ``\d`` matches every Unicode decimal-digit (category Nd), and ``int()`` accepts
# them, so ``ISSUE-０５５`` (fullwidth) and ``ISSUE-٠١١`` (Arabic-Indic) were
# honoured as canonical ids. AC-7 requires a CANONICAL-id fullmatch, and a
# validator over untrusted workspace input must not accept a spelling no
# generator in this repo emits.
_ROSTER_ID_RE = re.compile(r"ISSUE-([0-9]{1,9})")

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
# blacklist: line-anchored, case-insensitive, and tolerant of every bullet
# marker, indentation and emphasis form the line could carry. A field-shaped line
# the detector MISSES is the worst outcome available: it is honoured-by-OMISSION,
# because `watermark_present` goes False, which (a) re-opens the above-boundary
# dispatch gate in `cmd_next_action` and (b) makes the engine affirmatively
# report `[roster-watermark: absent from ## Meta]` about a field that is plainly
# there. Decoration and indentation are therefore DETECTED and then rejected as
# non-canonical by the `_WATERMARK_CANONICAL_NAME` check — being found-then-
# refused is the whole point, because it fails closed and announces.
#
# Review fix (ISSUE-069): the previous pattern enumerated only `[-*]` as bullet
# markers and only `[ \t]` as whitespace, so eleven field-shaped lines slipped
# past it — `+` (CommonMark's third bullet marker), NBSP/ZWSP indentation,
# `_emphasis_`, `~~strike~~`, `***triple***`, and blockquoted `> - `. Each
# rendered identically to the canonical line and each silently re-opened
# dispatch; a single byte (`-` → `+`) turned `DONE`/`targets: []` into a
# `PIPELINE` on three out-of-scope issues. The duplicate guard inherited the same
# blind spot, so a canonical field plus a `+`-bulleted second copy counted as ONE
# hit and honoured the first — the exact silent loosening the duplicate rule
# exists to stop.
#
# Folding the leading run into ONE character class also removes the adjacent
# greedy quantifiers (`[ \t]*` … `[ \t]*` around an optional atom) that made the
# old pattern backtrack quadratically: a line of 80k spaces took 66s, and this
# scan runs over untrusted workspace input on every iteration of the sprint loop
# with no timeout wrapper. The class form is linear.
_WATERMARK_FIELD_RE = re.compile(
    r"^[\s\u00a0\u200b>+*\-_~`]*roster-watermark[*_~`\s\u00a0]*:",
    re.IGNORECASE,
)

# `str.splitlines()` also breaks on VT, FF, FS, GS, RS, NEL, LS and PS, none of
# which `Path.read_text`'s universal-newline translation normalizes. That let a
# whole field declaration — or even a `## Meta` heading — be smuggled INSIDE a
# physical `\n`-delimited line, where this parser saw and honoured it but `grep`,
# a line-based linter and a human reading the file could not find it. Detection
# stays broad (the smuggled field IS found, so the gate closes), and acceptance
# refuses it: a document whose line structure is ambiguous does not get to pin
# the boundary. No generator in this repo emits these characters.
_AMBIGUOUS_LINE_SEPARATORS = (
    "\x0b\x0c\x1c\x1d\x1e\u0085\u2028\u2029"
)

# Board ids are compared against the pinned value as a range check, and
# `board_max` is a `max()` over ids read from `issues.md` — also untrusted. One
# inert `### ISSUE-999999999:` heading would otherwise raise the ceiling far
# enough to make any forged boundary "in range", silencing the whole control.
# Real ids in this repo are 3 digits; 4 leaves generous headroom.
_MAX_PLAUSIBLE_BOARD_ID = 9999


def _meta_section_bounds(lines: list[str]) -> tuple[int, int]:
    """Half-open ``[start, end)`` line range of the ``## Meta`` section body.

    The terminating condition is copied from the structure of ``## Meta``
    ITSELF, not from any other scan in this module: ``## Meta`` is a
    bullet-list section, and a markdown section of that shape ends at its next
    SIBLING heading (``## `` → EOF). So an h3 sub-heading does not close it —
    an h3 nested inside ``## Meta`` is still ``## Meta`` — while a stray paste
    under a sibling ``## `` heading is correctly outside it. ``(0, 0)`` — an
    empty range — when there is no ``## Meta`` heading at all, which makes
    every field line "outside ## Meta" and therefore refused (fail-closed).

    Deliberately NOT the same terminator ``parse_sprint_table`` uses. That scan
    reads a GFM *table*, whose structure ends it at the first line that is not a
    table row (blank line, prose, or a heading of ANY level — ISSUE-076). Two
    different markdown constructs, so two different terminators, each taken from
    the construct it parses. Do not "unify" them.
    """
    for start, line in enumerate(lines):
        # ``rstrip()`` (review fix): ``parse_sprint_table``'s heading match is
        # ``r"## Issue Progress\s*\n"``, i.e. it tolerates trailing whitespace.
        # An exact ``==`` here was stricter than that oracle, so a cosmetic
        # trailing space on the heading moved every field line "outside
        # ## Meta" and cost the sprint its pin on every run (announced, and the
        # gate stays closed — degradation, not unsafety, but needless).
        if line.rstrip() == "## Meta":
            for end in range(start + 1, len(lines)):
                if lines[end].startswith("## "):
                    return start + 1, end
            return start + 1, len(lines)
    return 0, 0


def _truncate_value(value: str) -> str:
    """Sanitize + cap an echoed untrusted value at 40 chars + an ellipsis.

    A rejected ``## Meta`` value is quoted back in ``reason``, so a pathological
    one (e.g. a 4301-digit ID) must not be amplified through stdout.

    Square brackets are stripped first (review fix). ``reason`` is the channel an
    LLM orchestrator reads as the engine's verdict, and the engine marks its own
    signals with bracketed sentinels (``[dispatch: …]``, ``[roster-watermark:
    …]``). 40 characters is ample room for a convincing lookalike, e.g.
    ``x] [dispatch: ENABLED] [ok``, landing verbatim beside the real markers.
    Review lesson: those sentinels are data, not directives — so the untrusted
    echo must not be able to spell one.
    """
    cleaned = value.replace("[", "").replace("]", "")
    return cleaned if len(cleaned) <= 40 else cleaned[:40] + "…"


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
    inside a code fence still counts as a duplicate — and the reason is that the
    two rules do NOT degrade alike, so this is a safety choice rather than a
    simplicity one. Fence-AWARE counting would discard the fenced copy and
    HONOUR the remaining one, which hands an attacker (or a careless rewrite) a
    silent loosening: wrap the real field in a fence, add your own beside it, and
    exactly one "real" field remains — yours, accepted, with nothing in `reason`
    to say so. Fence-BLIND counting sees two declarations, refuses both, and
    announces. Refusing is the fail-closed direction, so it wins; it also cannot
    be defeated by wrapping a second field in backticks. Known cost, accepted: a
    field line that exists ONLY inside a fence (a doc example under ``## Meta``
    with no real field anywhere) is read as a real declaration. That direction is
    announced — ``reason`` names the boundary it pinned — and the dispatch gate
    closes either way, so it costs precision, never restraint.

    Never raises: every step is total for a ``str``/``dict`` pair, and both digit
    runs handed to ``int()`` are bounded by ``_ROSTER_ID_RE``.
    """
    text = sprint_text or ""
    # `splitlines()` is deliberate here, NOT `split("\n")`: it also breaks on the
    # separators in `_AMBIGUOUS_LINE_SEPARATORS`, which is what lets this scan
    # FIND a field smuggled inside a physical line. Finding it is what closes the
    # dispatch gate; the acceptance check below is what refuses to honour it.
    lines = text.splitlines()
    hits = [
        (index, line)
        for index, line in enumerate(lines)
        if _WATERMARK_FIELD_RE.match(line)
    ]
    if not hits:
        return None, None, False
    if len(hits) > 1:
        return None, f"{len(hits)} field lines found, expected exactly one", True

    # A field was found, so the gate is already closed from here on. Refuse to
    # HONOUR it if the document's line structure is ambiguous: a declaration that
    # only this parser can see is not a declaration an operator can audit.
    if any(sep in text for sep in _AMBIGUOUS_LINE_SEPARATORS):
        return None, (
            "document contains a non-newline Unicode line separator, so a field "
            "line here is not visible to a line-based reader"
        ), True

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

    # Lower end of the range (review fix): AC-7 names "out of the live ID range",
    # and a range has two ends — the upper bound alone let ``ISSUE-000`` through.
    # Canonical issue ids start at 001, and a boundary below every real id is the
    # mirror failure of one above every real id: instead of silencing the control
    # it maximally OPENS it (the whole Board backlog lands in
    # ``unrostered``/``stranded``, and with the opt-in set it becomes a Board-wide
    # dispatcher). Checked before the Board scan because it needs no Board at all.
    if num < 1:
        return None, (
            f"ISSUE-{num:03d} is below the lowest possible Board id ISSUE-001"
        ), True

    # Range sanity against the LIVE Board: a boundary above every real ID
    # silences the whole control while looking perfectly well-formed. Skipped
    # when no Board key is parseable, so an unrelated issues.md problem cannot
    # cost the sprint its pinned boundary. The bound on `_ROSTER_ID_RE` is
    # load-bearing on this scan too — an overlong Board heading reaching `int()`
    # is the same CPython 4300-digit crash via a different input file.
    #
    # The ceiling is clamped to `_MAX_PLAUSIBLE_BOARD_ID` (review fix): `issues.md`
    # is untrusted too, so without a clamp a single inert
    # `### ISSUE-999999999:` heading raised `board_max` high enough to make any
    # forged boundary "in range" — and a boundary above every real id silences the
    # whole control, which is precisely what this guard exists to stop. Ids beyond
    # the clamp are ignored for ceiling purposes rather than failing the check, so
    # one implausible heading cannot cost the sprint its pin either.
    board_nums = [
        int(board_match.group(1))
        for board_match in (_ROSTER_ID_RE.fullmatch(key) for key in issues_meta)
        if board_match
    ]
    plausible = [n for n in board_nums if n <= _MAX_PLAUSIBLE_BOARD_ID]
    if plausible:
        board_max = max(plausible)
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
    and stays invisible.

    The legacy empty-table DONE path is preserved in both cases: the
    ``if not sprint_rows`` short-circuit stays FIRST and a pin does not bypass it,
    so an un-started sprint never becomes a Board-wide dispatcher. A pin DOES
    deliberately override the narrower ``not rostered_nums`` no-op, i.e. a roster
    that HAS rows but no canonical ``ISSUE-<digits>`` cell (all cells decorated or
    mangled) synthesizes under a pin where legacy returned early. That is
    intended — it keeps the Board visible when the roster text is corrupted
    instead of reporting a false DONE — and it is reachable only via the new
    field, so no pre-feature file changes behaviour. It is also non-dispatching:
    the presence-keyed gate in ``cmd_next_action`` withholds every synthesized id
    unless the opt-in knob is set.

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

    # ISSUE-076 review: an under-read roster must never be acted on — the
    # surviving fragment re-dispatches completed work as fresh backlog.
    unparsed = unparsed_roster_rows(sprint_text)
    if unparsed:
        print(
            f"Error: {len(unparsed)} Issue Progress roster row(s) were not "
            "parsed — refusing to dispatch off an under-read roster",
            file=sys.stderr,
        )
        print(
            "  Causes: a stray blank/whitespace-only or prose line inside the "
            "table (it ends there, per GFM, dropping every row beneath), or a "
            "row whose cell count is not 5 (e.g. an unescaped '|' in Last "
            "Error).",
            file=sys.stderr,
        )
        print(f"  First unparsed row: {unparsed[0]}", file=sys.stderr)
        print(
            "  Fix: delete the stray line, escape '|' as '\\|' inside cells, or "
            "move non-roster rows under their own heading.",
            file=sys.stderr,
        )
        return 2

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
    #
    # `withheld_ids` records what this gate ACTUALLY removed, not what it decided
    # (review fix). Note B used to be driven by the decision, so it overstated in
    # both directions: with the opt-in set it claimed "dispatched" even when the
    # in-flight deferral above had already removed every synthesized id, and with
    # the opt-in unset it counted above-boundary issues that were never in
    # `implement_ready` anyway (e.g. an unresolved dependency) and promised the
    # knob would dispatch them. AC-5 exists so the log distinguishes a
    # deliberately widened sprint from a runaway one, so the log reports the
    # outcome.
    dispatch_above = _dispatch_above_watermark_enabled()
    withheld_ids: list[str] = []
    if unrostered_ids and watermark_present and not dispatch_above:
        withheld = set(unrostered_ids)
        withheld_ids = [iid for iid in queues["implement_ready"] if iid in withheld]
        queues["implement_ready"] = [
            iid for iid in queues["implement_ready"] if iid not in withheld
        ]

    # What the gate let through: synthesized ids still dispatchable at this point.
    dispatched_above_ids = [
        iid for iid in queues["implement_ready"] if iid in set(unrostered_ids)
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
    # team-lead read. Only the ABSENT-field state stays quiet when there is
    # nothing above the boundary, which is what keeps the legacy `reason`
    # byte-pins intact (a legacy sprint_state has no field at all).

    # Note A — which boundary was in force, and why.
    #
    # Review fix: a FOUND field is announced unconditionally — rejected OR
    # accepted — and NOT only when `unrostered` is non-empty. An accepted pin at
    # or above the Board max legitimately empties `unrostered`, and the old
    # `elif unrostered_ids and …` guard made that case emit nothing at all, so a
    # boundary that had silenced the entire control was byte-indistinguishable
    # from a healthy sprint with nothing to report. That is the GAP-068h
    # "one value disables the whole control with no signal" shape the issue's
    # Scope rules out ("never a silently emptied `unrostered_ids`"), reached via
    # a VALID value rather than a bad one. The boundary in force is the audit
    # record for a restraint mechanism: always state it.
    if watermark_detail is not None:
        # A refused boundary is announced even with an empty `unrostered`:
        # silence would be indistinguishable from health.
        result["reason"] += (
            f" [roster-watermark: rejected ({watermark_detail}) — fell back to "
            "the max rostered ID derivation]"
        )
    elif pinned_watermark is not None:
        # The count is the counter-evidence an operator needs to tell a correctly
        # quiet boundary from a defeated one (review fix). A forged-but-in-range
        # pin reports "0 of N above it" on an otherwise healthy DONE; a genuine
        # end-of-sprint boundary reports "0 of 0".
        board_backlog = sum(
            1
            for issue_id, meta in issues_meta.items()
            if _ROSTER_ID_RE.fullmatch(issue_id)
            and meta.get("status") == "backlog"
            and not meta.get("manual", False)
        )
        result["reason"] += (
            f" [roster-watermark: pinned at ISSUE-{pinned_watermark:03d} — "
            f"{len(unrostered_ids)} of {board_backlog} Board backlog issue(s) "
            "are above it]"
        )
    elif unrostered_ids:
        result["reason"] += (
            " [roster-watermark: absent from ## Meta — fell back to the max "
            "rostered ID derivation]"
        )

    # Note B — the dispatch OUTCOME for above-boundary work (review fix: the
    # outcome, not the gate's decision — see `withheld_ids` above). Omitted
    # entirely when the field is absent: the gate is off in that state, so naming
    # a knob that would change nothing is noise. Also omitted when the gate
    # neither withheld nor released anything, because then the knob is not what
    # is holding the work back — something upstream is (an in-flight deferral, an
    # unresolved dependency), and pointing at the knob would send the operator to
    # the wrong lever.
    if watermark_present:
        if dispatch_above and dispatched_above_ids:
            result["reason"] += (
                f" [dispatch: {DISPATCH_ABOVE_WATERMARK_ENV} is set — "
                f"{len(dispatched_above_ids)} above-boundary issue(s) "
                f"dispatched: {', '.join(dispatched_above_ids)}]"
            )
        elif withheld_ids:
            result["reason"] += (
                f" [dispatch: {len(withheld_ids)} above-boundary issue(s) "
                "flagged but NOT dispatched — set "
                f"{DISPATCH_ABOVE_WATERMARK_ENV}=1 to dispatch them: "
                f"{', '.join(withheld_ids)}]"
            )

    # Note C — rostered rows stalled on a dependency satisfied in a PRIOR sprint.
    # Diagnosis only: `action`, `targets` and the queues are already decided.
    gaps = diagnose_carry_forward_gaps(sprint_rows, issues_meta, queues)
    if gaps:
        # Bounded echo (review fix). Both the row ids and the dep ids come from
        # untrusted files, and `_parse_depends_on`/`parse_issues_metadata` use an
        # UNBOUNDED `ISSUE-\d+`, unlike `_ROSTER_ID_RE`. Unbounded, this note
        # reached 259 KB of `reason` from 60 rows carrying one 4299-digit dep id —
        # burying `action`, `targets` and the `[dispatch: … NOT dispatched]`
        # restraint marker under a quarter megabyte of digits in the string an
        # LLM orchestrator reads as the verdict.
        shown, extra = gaps[:5], len(gaps) - 5
        listed = ", ".join(
            f"{_truncate_value(issue_id)} "
            f"(dep {', '.join(_truncate_value(dep) for dep in deps[:5])})"
            for issue_id, deps in shown
        )
        if extra > 0:
            listed += f", and {extra} more"
        # The remediation names `Phase: shipped` explicitly. A row added with the
        # DEFAULT `backlog` phase does the OPPOSITE of the intent: `compute_queues`
        # resolves a dependency only at `phase == "shipped"` (or status
        # dropped/waiting), so a plain row makes the already-DONE dependency itself
        # a fresh `implement_ready` candidate and an autonomous consumer re-runs
        # implement → review → `gh pr merge` on shipped work. Verified: advice
        # followed literally → PIPELINE targeting the DONE dependency; advice with
        # `Phase: shipped` → PIPELINE targeting the blocked row, as intended.
        result["reason"] += (
            f" [carry-forward gap: {listed} — the dependency is resolved on the "
            "Board but has no Issue Progress row, and a rostered row resolves "
            "dependencies from that table only, so the row cannot dispatch. "
            "Carry the dependency forward by adding its Issue Progress row with "
            "Phase `shipped` (a row added with the default `backlog` phase makes "
            "the completed dependency a dispatch target instead), or drop the "
            "dependency.]"
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

    # ISSUE-076 review: warn but do not change the verdict — validate already
    # fails safe (a dropped target reports stuck). This names the cause.
    unparsed = unparsed_roster_rows(sprint_text)
    if unparsed:
        print(
            f"Warning: {len(unparsed)} Issue Progress roster row(s) were not "
            "parsed (stray line inside the table, or a non-5-column row); "
            f"first: {unparsed[0]}",
            file=sys.stderr,
        )

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
