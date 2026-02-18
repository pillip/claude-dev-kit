#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")

def find_project_root(start: Path) -> Path:
    cur = start
    while True:
        if (cur / ".claude").is_dir():
            return cur
        if cur.parent == cur:
            return start
        cur = cur.parent

payload = json.load(sys.stdin)
event = payload.get("hook_event_name", "Unknown")
cwd = Path(payload.get("cwd") or os.getcwd())

project_root = find_project_root(cwd)
run_dir = project_root / ".claude" / "run"
run_dir.mkdir(parents=True, exist_ok=True)

state_path = run_dir / "agent-state.json"
log_path = run_dir / "events.jsonl"

try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
except FileNotFoundError:
    state = {"active_agents": {}, "last_event": None, "last_tool": None, "updated_at": None}

if event == "SubagentStart":
    agent_id = payload.get("agent_id")
    agent_type = payload.get("agent_type")
    if agent_id and agent_type:
        state["active_agents"][agent_id] = agent_type
elif event == "SubagentStop":
    agent_id = payload.get("agent_id")
    if agent_id:
        state["active_agents"].pop(agent_id, None)

if event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
    state["last_tool"] = payload.get("tool_name")

state["last_event"] = event
state["updated_at"] = now()

tmp = state_path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
tmp.replace(state_path)

payload["_ts"] = state["updated_at"]
with log_path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
