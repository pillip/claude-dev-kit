"""ISSUE-001 (minimal baseline): run telemetry via agent_state.py + trace_query.

Pins the two guarantees the baseline depends on:
1. events.jsonl records are SHAPE-ONLY — no tool inputs, file contents, or
   prompts ever land in the trace (PII + line-size guarantee);
2. trace_query.summarize derives the baseline metrics (turns, tool calls,
   failures, subagent spawns, checkpoint runs/failures, duration) correctly.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "project" / ".claude" / "hooks" / "agent_state.py"

sys.path.insert(0, str(ROOT / "scripts"))
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
