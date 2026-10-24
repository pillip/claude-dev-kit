#!/usr/bin/env python3
"""Minimal trace query for the kit's run telemetry (ISSUE-001, baseline scope).

Reads BOTH of the kit's local telemetry streams on its default path and
prints per-session baseline metrics — the numbers used to compare harness
changes (ISSUE-030..033) before/after:

    turns, tool calls, tool failures, subagent spawns (by type),
    checkpoint runs / failures (by phase), wall-clock duration,
    script events (by event_type) and how many of them are unattributed

The two streams:

1. ``.claude/run/events.jsonl`` — the ISSUE-001 shape-only HOOK trace
   written by ``project/.claude/hooks/agent_state.py``, keyed by
   ``session_id`` and ``event``.
2. ``.claude/runs/<run-id>.jsonl`` — the ISSUE-067 shared EMITTER stream
   written by ``scripts/kit_telemetry.py``, keyed by ``event_type``, with
   the run id in the file name. Added here by ISSUE-071: until then the
   emitter stream was write-only — nothing read it on any default path —
   so the instrument's only output was a file no code opened plus a stdout
   line on 100% of runs. Removing that line (ISSUE-071's scarcity fix)
   is only honest if the record it defers to is actually readable, which
   is this. The ``unattributed events`` count is the aggregate readout
   that replaces the per-emit line: it answers "how many events lost their
   ``KIT_RUN_ID`` attribution" once, for the whole stream.

Usage:
    python3 scripts/trace_query.py summary [events.jsonl ...]
    python3 scripts/trace_query.py summary --json [events.jsonl ...]

Token usage is not hook-visible; record it alongside the baseline from
`claude -p --output-format json` (headless) or /cost (interactive).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import kit_telemetry  # noqa: E402 — sibling script, see the sys.path line above

DEFAULT_TRACE = Path(".claude/run/events.jsonl")

# The emitter's layout, imported rather than re-typed, so the path written
# and the path read are ONE value (ISSUE-071 AC-4; pinned by identity in
# tests/test_kit_telemetry.py::TestIssue071StreamHasANamedConsumer).
DEFAULT_RUNS_DIR = kit_telemetry.RUNS_SUBDIR


def default_trace_paths(root: str | Path = Path(".")) -> list[Path]:
    """Every trace this tool reads when given no explicit paths."""
    base = Path(root)
    return [base / DEFAULT_TRACE, *sorted((base / DEFAULT_RUNS_DIR).glob("*.jsonl"))]


def _parse_ts(ts: str):
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    try:
        # The emitter stream stamps datetime.now(timezone.utc).isoformat(),
        # which carries microseconds and so matches neither format above.
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def load_events(paths: list[Path]) -> list[dict]:
    events = []
    for path in paths:
        if not path.exists():
            print(f"trace not found: {path}", file=sys.stderr)
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # tolerate a torn line; telemetry must never hard-fail
    return events


def summarize(events: list[dict]) -> dict:
    """Group by session_id and compute baseline metrics."""
    sessions: dict[str, dict] = {}
    for ev in events:
        sid = ev.get("session_id", "(no-session)")
        s = sessions.setdefault(sid, {
            "turns": 0, "tool_calls": 0, "tool_failures": 0,
            "subagents": Counter(), "checkpoints": Counter(),
            "checkpoint_failures": Counter(), "first_ts": None, "last_ts": None,
            "script_events": Counter(), "unattributed": 0,
        })
        ts = _parse_ts(ev.get("ts", ""))
        if ts is not None:
            if s["first_ts"] is None or ts < s["first_ts"]:
                s["first_ts"] = ts
            if s["last_ts"] is None or ts > s["last_ts"]:
                s["last_ts"] = ts

        event = ev.get("event")
        if event == "UserPromptSubmit":
            s["turns"] += 1
        elif event == "PreToolUse":
            s["tool_calls"] += 1
        elif event == "PostToolUseFailure":
            s["tool_failures"] += 1
        elif event == "SubagentStart":
            s["subagents"][ev.get("agent_type", "unknown")] += 1

        # Emitter-stream shape (scripts/kit_telemetry.py): keyed by
        # `event_type`, not `event`, so the two schemas never collide.
        event_type = ev.get("event_type")
        if event_type is not None:
            s["script_events"][event_type] += 1
            if ev.get("run_id_fallback"):
                s["unattributed"] += 1

        cp = ev.get("checkpoint")
        if cp is not None and event in ("PostToolUse", "PostToolUseFailure"):
            phase = cp.get("phase", "unknown")
            s["checkpoints"][phase] += 1
            if ev.get("checkpoint_ok") is False:
                s["checkpoint_failures"][phase] += 1

    out = {}
    for sid, s in sessions.items():
        duration = None
        if s["first_ts"] is not None and s["last_ts"] is not None:
            duration = int((s["last_ts"] - s["first_ts"]).total_seconds())
        out[sid] = {
            "turns": s["turns"],
            "tool_calls": s["tool_calls"],
            "tool_failures": s["tool_failures"],
            "subagent_spawns": dict(s["subagents"]),
            "checkpoint_runs": dict(s["checkpoints"]),
            "checkpoint_failures": dict(s["checkpoint_failures"]),
            "duration_seconds": duration,
            "script_events": dict(s["script_events"]),
            "unattributed_events": s["unattributed"],
        }
    return out


def print_summary(summary: dict) -> None:
    for sid, s in summary.items():
        print(f"session {sid}")
        print(f"  turns:               {s['turns']}")
        print(f"  tool calls:          {s['tool_calls']}  (failures: {s['tool_failures']})")
        spawns = ", ".join(f"{k}×{v}" for k, v in sorted(s["subagent_spawns"].items())) or "—"
        print(f"  subagent spawns:     {spawns}")
        cps = ", ".join(f"{k}×{v}" for k, v in sorted(s["checkpoint_runs"].items())) or "—"
        print(f"  checkpoint runs:     {cps}")
        fails = ", ".join(f"{k}×{v}" for k, v in sorted(s["checkpoint_failures"].items())) or "—"
        print(f"  checkpoint failures: {fails}")
        dur = s["duration_seconds"]
        print(f"  wall-clock:          {dur}s" if dur is not None else "  wall-clock:          —")
        evs = ", ".join(f"{k}×{v}" for k, v in sorted(s["script_events"].items())) or "—"
        print(f"  script events:       {evs}")
        # The aggregate that replaced ISSUE-067's per-emit stdout line
        # (ISSUE-071): named here so the remediation is discoverable.
        print(
            f"  unattributed events: {s['unattributed_events']}"
            f"  (set {kit_telemetry.RUN_ID_ENV} to attribute them)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Query kit run telemetry.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_sum = sub.add_parser("summary", help="Per-session baseline metrics.")
    p_sum.add_argument("traces", nargs="*", type=Path, default=None,
                       help=(f"trace paths (default: {DEFAULT_TRACE} plus "
                             f"{DEFAULT_RUNS_DIR}/*.jsonl)"))
    p_sum.add_argument("--json", action="store_true", help="Machine-readable output.")
    args = parser.parse_args()

    paths = args.traces or [p for p in default_trace_paths() if p.exists()]
    summary = summarize(load_events(paths))
    if not summary:
        print("no events found", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print_summary(summary)


if __name__ == "__main__":
    main()
