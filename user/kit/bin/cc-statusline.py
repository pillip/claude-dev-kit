#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

payload = json.load(sys.stdin)
workspace = payload.get("workspace") or {}
project_dir = workspace.get("project_dir") or payload.get("cwd") or os.getcwd()

state_path = Path(str(project_dir)) / ".claude" / "run" / "agent-state.json"

agents, last_tool = [], "-"
try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    agents = list((state.get("active_agents") or {}).values())
    last_tool = state.get("last_tool") or "-"
except Exception:
    pass

model = (payload.get("model") or {}).get("display_name") or (payload.get("model") or {}).get("id") or "?"
cost = (payload.get("cost") or {}).get("total_cost_usd", 0.0)
ctx = payload.get("context_window") or {}
tok_used = (ctx.get("total_input_tokens", 0) + ctx.get("total_output_tokens", 0))
tok_max = ctx.get("context_window_size", 0)

agents_str = ",".join(agents) if agents else "idle"
print(f"{model} | agents:{agents_str} | tool:{last_tool} | tok:{tok_used}/{tok_max} | ${cost:.3f}")
