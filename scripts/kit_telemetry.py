#!/usr/bin/env python3
"""Shared kit telemetry emitter (ISSUE-067) — the single home of the
ISSUE-058 writer hardening, with every skip/fallback path ANNOUNCED.

Every kit telemetry emit either runs or announces its skip/fallback with a
named reason on stdout — "no signal" can no longer be confused with "all
clear". This module replaces the per-script hand-rolled appenders (the
first migration is ``synthesize_gate_results._emit_telemetry``) and backs
the skill-prompt call sites via the CLI below.

Python API (this docstring is the API contract — ISSUE-066 adopts it at
its ship-time rebase)::

    def emit_event(
        event_type: str,
        payload: dict | None = None,
        *,
        script_name: str,            # becomes the event's skill_or_script field
        project_path: str | Path | None = None,  # default Path.cwd();
                                     # events land in <project>/.claude/runs/
        issue_id: str | None = None, # optional schema field
    ) -> bool:                       # True = a line was written, False = skipped

Behavior (see docs/telemetry_schema.md for the event catalog):

- Run-id resolution happens INSIDE the helper from the env knob
  ``KIT_RUN_ID``:
    - set and matching ``[A-Za-z0-9_-]{1,64}`` (fullmatch) → clean path:
      append to ``<project>/.claude/runs/<run_id>.jsonl``, print NOTHING.
    - unset/blank → FALLBACK: append to ``.claude/runs/unattributed.jsonl``;
      the event gains a top-level ``"run_id_fallback": "KIT_RUN_ID unset"``
      field and ONE stdout line announces the fallback, naming the knob.
    - set but failing the whitelist → the same ``unattributed`` fallback
      with ``run_id_fallback`` noting the invalid value's rejection; the
      raw invalid value is NEVER used in a filename.
- ``<project>/.claude/runs/`` is auto-created (mkdir parents, exist_ok) —
  dir absence is no longer a silent-skip path; mere creation is not
  announced. The project ROOT itself is never created: a
  ``project_path`` that is not an existing directory is refused with an
  announcement (review fix, PR #123 security finding F1 — the emitter
  must not be a directory-creation primitive in an arbitrary location).
- Containment: the resolved runs dir must stay inside the resolved project
  root; on violation the rejection is announced with its named reason and
  NOTHING is written anywhere (the stdout line is the only signal).
- ISSUE-058 hardening preserved byte-for-byte: ``payload["detail"]`` longer
  than 512 chars is truncated with ``…[truncated]``; a serialized event
  over 4096 bytes is skipped (now ANNOUNCED, naming the cap — previously a
  silent drop); the event file is opened O_NOFOLLOW so a pre-planted
  symlink cannot redirect the append (refusal announced as a write
  failure).
- ``emit_event`` NEVER raises — telemetry is a non-blocking instrument and
  the parent must never fail because of it. Every skip announces and
  returns False.
- Event schema: ``ts`` (ISO-8601 UTC), ``event_type``, ``skill_or_script``,
  optional ``issue_id``, ``payload``, plus the optional ``run_id_fallback``.
- All announcements are single stdout lines prefixed ``[kit-telemetry]``.

CLI (for skill-prompt call sites — one-line adoption)::

    python3 scripts/kit_telemetry.py --script <name> --event <event_type> \\
        [--payload '<json-object>'] [--issue-id ISSUE-NNN] [--project-path <dir>]

The CLI always exits 0 (non-blocking), even on skip paths — the stdout
announcement is the signal. An invalid ``--payload`` announces and writes
nothing.

Env knobs (documented here and in README's environment-variable list):
    KIT_RUN_ID — run id for telemetry appends to
        ``<project>/.claude/runs/<run-id>.jsonl``. Unset or invalid =>
        the event is written under the ``unattributed`` run id with a
        ``run_id_fallback`` field and a stdout announcement naming the knob.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Env knob naming the run id (docs/telemetry_schema.md).
RUN_ID_ENV = "KIT_RUN_ID"

# Explicit fallback run id when KIT_RUN_ID is unset or invalid — the event
# survives, visibly unattributed, instead of being silently dropped.
FALLBACK_RUN_ID = "unattributed"

# Whitelist for the attacker-influenced run-id filename component.
_RUN_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")

# Attacker-derived text (e.g. error messages quoting unknown keys) is
# truncated rather than allowed to pad the event past the 4 KiB cap —
# padding would silently drop the forensic record.
_MAX_DETAIL_CHARS = 512

# Event payload ceiling per docs/telemetry_schema.md (POSIX O_APPEND
# atomicity for small writes).
_MAX_EVENT_BYTES = 4096

_ANNOUNCE_PREFIX = "[kit-telemetry]"


def _announce(message: str) -> None:
    """One stdout line per skip/fallback — the no-silent-no-op contract."""
    print(f"{_ANNOUNCE_PREFIX} {message}")


def _resolve_run_id() -> tuple[str, str | None]:
    """Resolve (run_id, fallback_reason) from the KIT_RUN_ID env knob.

    fallback_reason is None on the clean path; otherwise it names the knob
    and the condition, and run_id is the explicit ``unattributed`` id.
    """
    raw = os.environ.get(RUN_ID_ENV, "").strip()
    if not raw:
        return FALLBACK_RUN_ID, f"{RUN_ID_ENV} unset"
    if not _RUN_ID_RE.fullmatch(raw):
        # NEVER use the raw invalid value in a filename.
        return FALLBACK_RUN_ID, (
            f"{RUN_ID_ENV} invalid (must match {_RUN_ID_RE.pattern})"
        )
    return raw, None


def emit_event(
    event_type: str,
    payload: dict | None = None,
    *,
    script_name: str,
    project_path: str | Path | None = None,
    issue_id: str | None = None,
) -> bool:
    """Append one schema-conformant event line; announce every skip/fallback.

    Returns True when a line was written, False when the emit was skipped
    (the skip is always announced). Never raises.
    """
    try:
        project = Path(project_path) if project_path is not None else Path.cwd()
        run_id, fallback_reason = _resolve_run_id()

        # The project root must already exist (review fix, PR #123 security
        # finding F1). `.claude/runs/` is still auto-created inside a real
        # project — dir absence there is not a skip path — but the emitter
        # never materializes the root itself, so an attacker-influenced
        # ``--project-path`` cannot turn this instrument into a multi-level
        # directory-creation primitive in an arbitrary location.
        if not project.is_dir():
            _announce(
                f"skipped: project root '{project}' is not an existing "
                f"directory; event '{event_type}' NOT written"
            )
            return False

        # Containment before any mkdir: a symlinked .claude/ or runs/ must
        # not even gain subdirectories outside the project root.
        runs_dir = project / ".claude" / "runs"
        if not runs_dir.resolve().is_relative_to(project.resolve()):
            _announce(
                "skipped: containment violation — resolved .claude/runs "
                f"escapes the project root; event '{event_type}' NOT written"
            )
            return False
        runs_dir.mkdir(parents=True, exist_ok=True)

        body = dict(payload) if payload else {}
        detail = body.get("detail")
        if isinstance(detail, str) and len(detail) > _MAX_DETAIL_CHARS:
            body["detail"] = detail[:_MAX_DETAIL_CHARS] + "…[truncated]"

        event: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "skill_or_script": script_name,
        }
        if issue_id is not None:
            event["issue_id"] = issue_id
        event["payload"] = body
        if fallback_reason is not None:
            event["run_id_fallback"] = fallback_reason

        data = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        if len(data) > _MAX_EVENT_BYTES:
            _announce(
                f"skipped: serialized event exceeds the {_MAX_EVENT_BYTES}-byte "
                f"cap — event '{event_type}' NOT written"
            )
            return False

        # O_NOFOLLOW: a pre-planted symlink at the event path must not
        # redirect the append outside the project (ISSUE-058 hardening).
        try:
            fd = os.open(
                runs_dir / f"{run_id}.jsonl",
                os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
                0o644,
            )
            try:
                os.write(fd, data)
            finally:
                os.close(fd)
        except OSError as exc:
            _announce(
                f"skipped: write failed ({exc}) — event '{event_type}' NOT written"
            )
            return False

        if fallback_reason is not None:
            _announce(
                f"fallback: {fallback_reason} — event '{event_type}' written "
                f"under run id '{FALLBACK_RUN_ID}'"
            )
        return True
    except Exception as exc:  # non-blocking instrument: never fail the parent
        _announce(
            f"skipped: emit failed ({exc}) — event '{event_type}' NOT written"
        )
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit one kit telemetry event (non-blocking; always exits 0)."
    )
    parser.add_argument("--script", required=True, help="skill_or_script field")
    parser.add_argument("--event", required=True, help="event_type field")
    parser.add_argument("--payload", help="event payload as a JSON object")
    parser.add_argument("--issue-id", help="optional issue_id field")
    parser.add_argument(
        "--project-path", help="project root (default: current directory)"
    )
    args = parser.parse_args(argv)

    payload: dict | None = None
    if args.payload is not None:
        try:
            payload = json.loads(args.payload)
        except ValueError:
            _announce(
                f"skipped: --payload is not valid JSON — event "
                f"'{args.event}' NOT written"
            )
            return 0
        if not isinstance(payload, dict):
            _announce(
                f"skipped: --payload is not a JSON object — event "
                f"'{args.event}' NOT written"
            )
            return 0

    emit_event(
        args.event,
        payload,
        script_name=args.script,
        project_path=args.project_path,
        issue_id=args.issue_id,
    )
    return 0  # the announcement is the signal; telemetry never blocks


if __name__ == "__main__":
    sys.exit(main())
