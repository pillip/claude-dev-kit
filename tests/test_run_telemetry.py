"""ISSUE-001 (minimal baseline): run telemetry via agent_state.py + trace_query.

Pins the two guarantees the baseline depends on:
1. events.jsonl records are SHAPE-ONLY — no tool inputs, file contents, or
   prompts ever land in the trace (PII + line-size guarantee);
2. trace_query.summarize derives the baseline metrics (turns, tool calls,
   failures, subagent spawns, checkpoint runs/failures, duration) correctly.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "project" / ".claude" / "hooks" / "agent_state.py"

sys.path.insert(0, str(ROOT / "scripts"))
import kit_telemetry as kt  # noqa: E402
import trace_query  # noqa: E402
from trace_query import summarize  # noqa: E402


def run_hook(payload: dict, cwd: Path):
    subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        cwd=str(cwd),
        check=True,
        capture_output=True,
    )


def read_events(root: Path) -> list[dict]:
    path = root / ".claude" / "run" / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_events_are_shape_only(tmp_path):
    (tmp_path / ".claude" / "run").mkdir(parents=True)
    secret = "SUPER-SECRET-FILE-CONTENT"
    run_hook({
        "hook_event_name": "PreToolUse",
        "cwd": str(tmp_path),
        "session_id": "s1",
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/x", "content": secret},
    }, tmp_path)

    [event] = read_events(tmp_path)
    blob = json.dumps(event)
    assert secret not in blob, "tool_input content leaked into the trace"
    assert "tool_input" not in event
    assert event["event"] == "PreToolUse"
    assert event["session_id"] == "s1"
    assert event["tool_name"] == "Write"
    assert "ts" in event
    assert len(blob.encode()) < 4096


def test_checkpoint_detection_pass_and_fail(tmp_path):
    (tmp_path / ".claude" / "run").mkdir(parents=True)
    cmd = "bash scripts/checkpoint.sh --skill implement --phase test --issue ISSUE-042"
    run_hook({"hook_event_name": "PostToolUse", "cwd": str(tmp_path), "session_id": "s1",
              "tool_name": "Bash", "tool_input": {"command": cmd}}, tmp_path)
    run_hook({"hook_event_name": "PostToolUseFailure", "cwd": str(tmp_path), "session_id": "s1",
              "tool_name": "Bash", "tool_input": {"command": cmd}}, tmp_path)

    ok, fail = read_events(tmp_path)
    assert ok["checkpoint"] == {"skill": "implement", "phase": "test", "issue": "ISSUE-042"}
    assert ok["checkpoint_ok"] is True
    assert fail["checkpoint_ok"] is False
    assert "tool_input" not in ok  # args extracted, command line itself not stored


def test_non_checkpoint_bash_has_no_checkpoint_field(tmp_path):
    (tmp_path / ".claude" / "run").mkdir(parents=True)
    run_hook({"hook_event_name": "PostToolUse", "cwd": str(tmp_path), "session_id": "s1",
              "tool_name": "Bash", "tool_input": {"command": "git status"}}, tmp_path)
    [event] = read_events(tmp_path)
    assert "checkpoint" not in event


def test_user_prompt_submit_recorded(tmp_path):
    (tmp_path / ".claude" / "run").mkdir(parents=True)
    run_hook({"hook_event_name": "UserPromptSubmit", "cwd": str(tmp_path),
              "session_id": "s1", "prompt": "do the thing"}, tmp_path)
    [event] = read_events(tmp_path)
    assert event["event"] == "UserPromptSubmit"
    assert "prompt" not in json.dumps(event), "prompt text must not be logged"


def test_summarize_baseline_metrics():
    events = [
        {"ts": "2026-07-23T10:00:00", "event": "UserPromptSubmit", "session_id": "s1"},
        {"ts": "2026-07-23T10:00:05", "event": "PreToolUse", "session_id": "s1", "tool_name": "Bash"},
        {"ts": "2026-07-23T10:00:06", "event": "PostToolUse", "session_id": "s1", "tool_name": "Bash",
         "checkpoint": {"skill": "implement", "phase": "test", "issue": "ISSUE-1"}, "checkpoint_ok": True},
        {"ts": "2026-07-23T10:00:10", "event": "PreToolUse", "session_id": "s1", "tool_name": "Bash"},
        {"ts": "2026-07-23T10:00:11", "event": "PostToolUseFailure", "session_id": "s1", "tool_name": "Bash",
         "checkpoint": {"phase": "test"}, "checkpoint_ok": False},
        {"ts": "2026-07-23T10:00:20", "event": "SubagentStart", "session_id": "s1",
         "agent_id": "a1", "agent_type": "developer"},
        {"ts": "2026-07-23T10:05:00", "event": "SubagentStop", "session_id": "s1", "agent_id": "a1"},
        # separate session must not bleed in
        {"ts": "2026-07-23T11:00:00", "event": "UserPromptSubmit", "session_id": "s2"},
    ]
    summary = summarize(events)
    s1 = summary["s1"]
    assert s1["turns"] == 1
    assert s1["tool_calls"] == 2
    assert s1["tool_failures"] == 1
    assert s1["subagent_spawns"] == {"developer": 1}
    assert s1["checkpoint_runs"] == {"test": 2}
    assert s1["checkpoint_failures"] == {"test": 1}
    assert s1["duration_seconds"] == 300
    assert summary["s2"]["turns"] == 1


def test_trace_query_cli_smoke(tmp_path):
    trace = tmp_path / "events.jsonl"
    trace.write_text(json.dumps(
        {"ts": "2026-07-23T10:00:00", "event": "UserPromptSubmit", "session_id": "s1"}
    ) + "\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "trace_query.py"), "summary", "--json", str(trace)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["s1"]["turns"] == 1


# ═════════════════════════════════════════════════════════════════════
# ISSUE-071 — trace_query is the NAMED CONSUMER of the emitter stream
# ═════════════════════════════════════════════════════════════════════
#
# Before this change `.claude/runs/<run-id>.jsonl` was write-only: the
# shared emitter appended to it and no kit script read it on any default
# path, while trace_query read only the ISSUE-001 hook trace at the
# differently-named `.claude/run/events.jsonl`. ISSUE-071's stream decision
# is "name a consumer" rather than "unify the files", so both streams are
# read on the default path and the emitter's run-id-keyed layout (and every
# containment test that pins it) survives untouched.


def test_default_trace_paths_covers_both_streams(tmp_path):
    hook = tmp_path / trace_query.DEFAULT_TRACE
    hook.parent.mkdir(parents=True)
    hook.write_text("", encoding="utf-8")
    runs = tmp_path / kt.RUNS_SUBDIR
    runs.mkdir(parents=True)
    unattributed = runs / f"{kt.FALLBACK_RUN_ID}.jsonl"
    unattributed.write_text("", encoding="utf-8")
    named = runs / "abc123.jsonl"
    named.write_text("", encoding="utf-8")
    (runs / "not-a-trace.txt").write_text("x", encoding="utf-8")

    paths = [p.resolve() for p in trace_query.default_trace_paths(tmp_path)]
    assert hook.resolve() in paths, "the ISSUE-001 hook trace must not be dropped"
    assert unattributed.resolve() in paths
    assert named.resolve() in paths
    assert (runs / "not-a-trace.txt").resolve() not in paths


def test_summarize_counts_emitter_events_and_unattributed_fallbacks():
    """The aggregate readout that REPLACES the per-emit stdout line: how many
    events this stream holds, and how many of them lost their attribution."""
    events = [
        {"ts": "2026-10-25T10:00:00.123456+00:00",
         "event_type": "gates_degraded_path_used",
         "skill_or_script": "synthesize_gate_results",
         "payload": {"reason": "skill_missing"},
         "run_id_fallback": "KIT_RUN_ID unset"},
        {"ts": "2026-10-25T10:01:00.654321+00:00",
         "event_type": "gates_degraded_path_used",
         "skill_or_script": "synthesize_gate_results",
         "payload": {"reason": "capability_dormant"},
         "run_id_fallback": "KIT_RUN_ID unset"},
        {"ts": "2026-10-25T10:01:00.654321+00:00",
         "event_type": "gates_delegated_to_runtime",
         "skill_or_script": "synthesize_gate_results",
         "payload": {}},
    ]
    s = summarize(events)["(no-session)"]
    assert s["script_events"] == {
        "gates_degraded_path_used": 2,
        "gates_delegated_to_runtime": 1,
    }
    assert s["unattributed_events"] == 2
    # Microsecond-bearing ISO-8601 (what datetime.now(timezone.utc) emits)
    # has to parse, or the stream trace_query now reads is unreadable.
    assert s["duration_seconds"] == 60


def test_hook_trace_events_are_not_counted_as_emitter_events():
    """Disarm direction: the two schemas must stay apart, so the new counter
    cannot silently absorb the ISSUE-001 stream and inflate itself."""
    s = summarize([
        {"ts": "2026-07-23T10:00:00", "event": "UserPromptSubmit", "session_id": "s1"},
    ])["s1"]
    assert s["script_events"] == {}
    assert s["unattributed_events"] == 0
    assert s["turns"] == 1


def test_trace_query_cli_reports_the_emitter_stream_by_default(tmp_path):
    """End-to-end through the real CLI with NO path arguments: an event the
    production emitter wrote is found, counted, and reported."""
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    env = dict(os.environ)
    env.pop(kt.RUN_ID_ENV, None)
    env.pop("CLAUDE_PROJECT_DIR", None)
    emit = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "kit_telemetry.py"),
         "--script", "synthesize_gate_results",
         "--event", "gates_degraded_path_used"],
        capture_output=True, text=True, cwd=str(project), env=env, timeout=60,
    )
    assert emit.returncode == 0, emit.stderr
    assert emit.stdout == "", emit.stdout

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "trace_query.py"), "summary", "--json"],
        capture_output=True, text=True, cwd=str(project), env=env, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)["(no-session)"]
    assert summary["script_events"] == {"gates_degraded_path_used": 1}
    assert summary["unattributed_events"] == 1


def test_the_knob_hint_appears_only_when_there_is_something_to_remediate(capsys):
    """Both directions. Review lesson 2 says name the knob in the failure
    message it remediates — printing `set KIT_RUN_ID` beside a zero would
    rebuild, inside this fix, the always-on line the fix removes."""
    noisy = summarize([
        {"ts": "2026-10-25T10:00:00+00:00", "event_type": "e",
         "skill_or_script": "s", "payload": {}, "run_id_fallback": "KIT_RUN_ID unset"},
    ])
    trace_query.print_summary(noisy)
    out = capsys.readouterr().out
    assert "unattributed events: 1" in out
    assert f"set {kt.RUN_ID_ENV}" in out, "a real gap must name the knob"

    clean = summarize([
        {"ts": "2026-10-25T10:00:00+00:00", "event_type": "e",
         "skill_or_script": "s", "payload": {}},
    ])
    trace_query.print_summary(clean)
    out = capsys.readouterr().out
    assert "unattributed events: 0" in out
    assert kt.RUN_ID_ENV not in out, (
        "with nothing to remediate the knob must not be mentioned"
    )
