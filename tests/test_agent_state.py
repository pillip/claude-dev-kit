import json
import subprocess, sys, tempfile
from pathlib import Path

def run_hook(script: Path, payload: dict, cwd: Path):
    subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload).encode("utf-8"),
        cwd=str(cwd),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

def test_agent_state_records_active_agents():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / ".claude" / "run").mkdir(parents=True)

        script = Path(__file__).resolve().parents[1] / "project" / ".claude" / "hooks" / "agent_state.py"

        run_hook(script, {"hook_event_name": "SubagentStart", "cwd": str(td), "agent_id": "a1", "agent_type": "ux-designer"}, td)
        state_path = td / ".claude" / "run" / "agent-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["active_agents"]["a1"] == "ux-designer"

        run_hook(script, {"hook_event_name": "SubagentStop", "cwd": str(td), "agent_id": "a1"}, td)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert "a1" not in state["active_agents"]
