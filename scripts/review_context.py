#!/usr/bin/env python3
"""Review execution-context decision + telemetry seam (ISSUE-066 / SPEC-066).

Decides the SPEC-019 review path ONCE per review run for both dimensions
(``code`` -> runtime ``/code-review``, ``security`` -> ``/security-review``),
combining two inputs:

- the **capability half**: the in-process ``has_skill.find_skill`` probe per
  dimension (exit 1 = definitive filesystem miss; 0/2 = installed/unknown),
- the **context half**: a model-reported ``--invocation-tools
  {present,absent}`` flag — the model checks its own tool list once for the
  runtime skill-invocation tool (a script cannot observe the model's
  toolset). The flag is validated closed-vocabulary data, not a directive
  (review lesson 10): both misreport directions converge on a review that
  still runs — degraded, or inline-fail-then-degraded.

Decision table per dimension (``decide_review_context``):
    probe exit 1                      -> degraded, reason ``capability-absent``
    probe exit 0/2, tools ``absent``  -> degraded, reason ``context-unreachable``
    probe exit 0/2, tools ``present`` -> delegated (prose invokes the skill)

The reason vocabulary is exactly ``capability-absent`` /
``context-unreachable`` / ``inline-attempt-failed`` (hyphenated — the
ISSUE-066 ACs quote these strings). Decide-time reasons are emitted by the
``decide`` subcommand only; ``inline-attempt-failed`` is the single reason
the prose-side ``emit`` subcommand accepts for ``review_degraded_path_used``
(a ``delegated`` dimension whose inline invocation failed anyway —
probe-exit-2 ambiguity).

**Single emit seam**: ``_emit_event`` is the ONE function through which every
review delegation event is appended (``decide`` for decide-time degradations,
``emit`` for the prose-side events). ISSUE-067's shared telemetry helper
replaces this one function body at ISSUE-066's ship-time rebase — do not add
a second emission call site. It mirrors the hardened best-effort append
contract proven in ``synthesize_gate_results._emit_telemetry``
(docs/telemetry_schema.md): run-id whitelist, runs-dir realpath containment,
``O_NOFOLLOW`` append, 4096-byte event cap with long-string truncation,
never raises, silent no-op when unconfigured.

Env knobs (no new ones — ``KIT_RUN_ID`` is pre-documented in README and
docs/telemetry_schema.md):
    KIT_RUN_ID — run id for best-effort telemetry appends to
        ``<cwd>/.claude/runs/<run-id>.jsonl``. Unset or no runs dir =>
        emission is a silent no-op.

Usage (from the project root — ``skills/review/SKILL.md`` step 3.1):
    python3 scripts/review_context.py decide --invocation-tools absent --issue ISSUE-066
    python3 scripts/review_context.py emit --event review_delegated_to_code_review --issue ISSUE-066 [--pr 123]
    python3 scripts/review_context.py emit --event review_degraded_path_used \\
        --dimension code --reason inline-attempt-failed --issue ISSUE-066

Exit codes: 0 = decision computed / event handled (telemetry no-op included);
2 = bad input (closed-vocabulary violation, bad issue id format ISSUE-<digits>).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import has_skill

_SCRIPT_NAME = "review_context"

# Dimension -> runtime skill name (the SPEC-019 review vocabulary).
DIMENSION_SKILLS: dict[str, str] = {
    "code": "code-review",
    "security": "security-review",
}

# Allowlisted prose-side events (docs/telemetry_schema.md, ISSUE-019 table).
DEGRADED_EVENT = "review_degraded_path_used"
ALLOWED_EMIT_EVENTS: tuple[str, ...] = (
    "review_delegated_to_code_review",
    "review_delegated_to_security_review",
    DEGRADED_EVENT,
)

# The only reason the prose-side emit seam accepts; decide-time reasons
# (capability-absent / context-unreachable) are emitted by `decide` only.
INLINE_ATTEMPT_FAILED = "inline-attempt-failed"

INVOCATION_TOOLS_VALUES: tuple[str, ...] = ("present", "absent")

_ISSUE_ID_RE = re.compile(r"ISSUE-\d+")

# Script-side run-id source for telemetry (docs/telemetry_schema.md).
RUN_ID_ENV = "KIT_RUN_ID"

# Hardened-append constants — mirror synthesize_gate_results._emit_telemetry
# (ISSUE-067's shared helper subsumes these at ship-time rebase).
_RUN_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")
_MAX_EVENT_BYTES = 4096
_MAX_DETAIL_CHARS = 512


# ── pure decision table ──────────────────────────────────────────────


def decide_review_context(
    invocation_tools: str, probe=has_skill.find_skill
) -> dict[str, dict[str, str]]:
    """Decide the review path per dimension — ONCE for both dimensions.

    ``invocation_tools`` is the model-reported context half (``present`` /
    ``absent``); ``probe`` is the capability half (injectable for tests,
    defaults to :func:`has_skill.find_skill` returning ``(exit_code,
    evidence)``). Returns ``{"code": {"path": ..., "reason": ...},
    "security": {...}}`` with path ``delegated`` (reason ``""``) or
    ``degraded`` (reason ``capability-absent`` / ``context-unreachable``).

    Raises :class:`ValueError` on a closed-vocabulary violation — validated
    data, not a directive (review lesson 10).
    """
    if invocation_tools not in INVOCATION_TOOLS_VALUES:
        raise ValueError(
            f"invocation_tools must be one of {INVOCATION_TOOLS_VALUES}, "
            f"got {invocation_tools!r}"
        )
    decisions: dict[str, dict[str, str]] = {}
    for dimension, skill in DIMENSION_SKILLS.items():
        code, _evidence = probe(skill)
        if code == 1:
            decisions[dimension] = {"path": "degraded", "reason": "capability-absent"}
        elif invocation_tools == "absent":
            decisions[dimension] = {
                "path": "degraded",
                "reason": "context-unreachable",
            }
        else:
            decisions[dimension] = {"path": "delegated", "reason": ""}
    return decisions


# ── telemetry (best-effort, silent no-op, never raises) ──────────────


def _emit_event(
    project_path: Path,
    event_type: str,
    payload: dict,
    issue_id: str | None = None,
) -> None:
    """Append one schema-conformant event line; silent no-op when unconfigured.

    THE single emit seam for all review delegation events (see module
    docstring — ISSUE-067's shared helper replaces this body at ship-time
    rebase). Hardened as an untrusted-path write: run-id is
    whitelist-validated, the runs dir realpath must stay inside the project,
    the event file is opened ``O_NOFOLLOW`` so a pre-planted symlink cannot
    redirect the append, long string values are truncated, and events over
    the 4096-byte POSIX-atomicity cap are dropped.
    """
    try:
        run_id = os.environ.get(RUN_ID_ENV, "").strip()
        if not _RUN_ID_RE.fullmatch(run_id):
            return
        runs_dir = Path(project_path) / ".claude" / "runs"
        if not runs_dir.is_dir():
            return
        if not runs_dir.resolve().is_relative_to(Path(project_path).resolve()):
            return
        trimmed: dict = {}
        for key, value in payload.items():
            if isinstance(value, str) and len(value) > _MAX_DETAIL_CHARS:
                value = value[:_MAX_DETAIL_CHARS] + "…[truncated]"
            trimmed[key] = value
        event: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "skill_or_script": _SCRIPT_NAME,
        }
        if issue_id is not None:
            event["issue_id"] = issue_id
        event["payload"] = trimmed
        data = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        if len(data) > _MAX_EVENT_BYTES:
            return
        fd = os.open(
            runs_dir / f"{run_id}.jsonl",
            os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o644,
        )
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
    except Exception:
        # Never fail the parent review run on a telemetry write error.
        return


# ── CLI handlers ─────────────────────────────────────────────────────


def cmd_decide(args: argparse.Namespace) -> int:
    """Handler for `decide` — compute the per-dimension path decisions once,
    emit one reason-tagged ``review_degraded_path_used`` event per degraded
    dimension (none for delegated), and print the decision JSON."""
    # Call-time attribute lookup keeps the delegation seam monkeypatchable
    # (tests patch has_skill.find_skill).
    decisions = decide_review_context(
        args.invocation_tools, probe=has_skill.find_skill
    )
    project = Path.cwd()
    for dimension, decision in decisions.items():
        if decision["path"] == "degraded":
            _emit_event(
                project,
                DEGRADED_EVENT,
                {"dimension": dimension, "reason": decision["reason"]},
                issue_id=args.issue,
            )
    print(
        json.dumps(
            {
                "issue_id": args.issue,
                "invocation_tools": args.invocation_tools,
                "dimensions": decisions,
            }
        )
    )
    return 0


def cmd_emit(args: argparse.Namespace) -> int:
    """Handler for `emit` — the prose-side call site of the single emit seam.

    Cross-field closed vocabulary: ``review_degraded_path_used`` requires
    ``--dimension`` + ``--reason inline-attempt-failed`` (and no ``--pr``);
    the delegated events take an optional ``--pr`` only.
    """
    if args.event == DEGRADED_EVENT:
        if args.dimension is None or args.reason is None:
            print(
                f"Error: --event {DEGRADED_EVENT} requires --dimension "
                f"{{code,security}} and --reason {INLINE_ATTEMPT_FAILED}",
                file=sys.stderr,
            )
            return 2
        if args.pr is not None:
            print(
                f"Error: --pr is not accepted with --event {DEGRADED_EVENT}",
                file=sys.stderr,
            )
            return 2
        payload: dict = {"dimension": args.dimension, "reason": args.reason}
    else:
        if args.dimension is not None or args.reason is not None:
            print(
                "Error: --dimension/--reason are only valid with "
                f"--event {DEGRADED_EVENT}",
                file=sys.stderr,
            )
            return 2
        payload = {}
        if args.pr is not None:
            payload["pr_number"] = args.pr
    _emit_event(Path.cwd(), args.event, payload, issue_id=args.issue)
    return 0


# ── CLI entry point ──────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Exit 0 on a computed decision / handled event
    (telemetry no-op included); exit 2 on bad input."""
    parser = argparse.ArgumentParser(
        description=(
            "Decide the /review execution context once (SPEC-066) and emit "
            "review delegation telemetry through the single seam."
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    de = subparsers.add_parser(
        "decide",
        help="Compute the per-dimension delegated/degraded decision ONCE",
    )
    de.add_argument(
        "--invocation-tools",
        required=True,
        choices=INVOCATION_TOOLS_VALUES,
        help=(
            "Model-reported context half: is the runtime skill-invocation "
            "tool (SlashCommand) in the current tool list?"
        ),
    )
    de.add_argument(
        "--issue",
        required=True,
        help="Issue id, format ISSUE-<number> (e.g. ISSUE-066)",
    )

    em = subparsers.add_parser(
        "emit",
        help="Prose-side emit seam for allowlisted review delegation events",
    )
    em.add_argument(
        "--event",
        required=True,
        choices=ALLOWED_EMIT_EVENTS,
        help="Allowlisted event type (docs/telemetry_schema.md, ISSUE-019 table)",
    )
    em.add_argument(
        "--issue",
        required=True,
        help="Issue id, format ISSUE-<number> (e.g. ISSUE-066)",
    )
    em.add_argument(
        "--pr",
        default=None,
        help="PR ref for the delegated events (optional)",
    )
    em.add_argument(
        "--dimension",
        choices=sorted(DIMENSION_SKILLS),
        default=None,
        help=f"Required with --event {DEGRADED_EVENT}",
    )
    em.add_argument(
        "--reason",
        choices=(INLINE_ATTEMPT_FAILED,),
        default=None,
        help=(
            f"Required with --event {DEGRADED_EVENT}; the only reason the "
            "prose seam accepts (decide-time reasons are emitted by `decide`)"
        ),
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if not args.command:
        parser.print_help()
        return 2

    if not _ISSUE_ID_RE.fullmatch(args.issue):
        print(
            f"Error: --issue must match ISSUE-<number> (e.g. ISSUE-066), "
            f"got {args.issue!r}",
            file=sys.stderr,
        )
        return 2

    if args.command == "decide":
        return cmd_decide(args)
    return cmd_emit(args)


if __name__ == "__main__":
    raise SystemExit(main())
