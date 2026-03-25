import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "careful" / "careful_guard.py"


def run_hook(payload: dict) -> dict | None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    stdout = result.stdout.strip()
    if stdout:
        return json.loads(stdout)
    return None


def make_bash_payload(command: str) -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


class TestDangerousCommands:
    def test_blocks_rm_rf_root(self):
        out = run_hook(make_bash_payload("rm -rf /"))
        assert out is not None
        assert out["decision"] == "block"
        assert "careful" in out["reason"].lower()

    def test_blocks_rm_rf_home(self):
        out = run_hook(make_bash_payload("rm -rf ~"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_git_reset_hard(self):
        out = run_hook(make_bash_payload("git reset --hard HEAD~3"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_git_push_force(self):
        out = run_hook(make_bash_payload("git push --force origin main"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_git_branch_force_delete(self):
        out = run_hook(make_bash_payload("git branch -D feature"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_chmod_777(self):
        out = run_hook(make_bash_payload("chmod -R 777 /var"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_drop_table(self):
        out = run_hook(make_bash_payload("psql -c 'DROP TABLE users'"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_truncate(self):
        out = run_hook(make_bash_payload("psql -c 'TRUNCATE users'"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_kubectl_delete(self):
        out = run_hook(make_bash_payload("kubectl delete pod my-pod"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_docker_system_prune(self):
        out = run_hook(make_bash_payload("docker system prune -a"))
        assert out is not None
        assert out["decision"] == "block"


class TestSafeCommands:
    def test_allows_normal_commands(self):
        out = run_hook(make_bash_payload("ls -la"))
        assert out is None

    def test_allows_git_push(self):
        out = run_hook(make_bash_payload("git push origin feature"))
        assert out is None

    def test_allows_git_status(self):
        out = run_hook(make_bash_payload("git status"))
        assert out is None

    def test_allows_dry_run(self):
        out = run_hook(make_bash_payload("rm -rf / --dry-run"))
        assert out is None

    def test_allows_rm_node_modules(self):
        out = run_hook(make_bash_payload("rm -rf node_modules"))
        assert out is None

    def test_allows_rm_dist(self):
        out = run_hook(make_bash_payload("rm -rf dist"))
        assert out is None


class TestNonBashTool:
    def test_ignores_write_tool(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/x", "content": "rm -rf /"},
        }
        out = run_hook(payload)
        assert out is None
