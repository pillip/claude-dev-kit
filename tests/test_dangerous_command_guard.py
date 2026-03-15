import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "project" / ".claude" / "hooks" / "dangerous_command_guard.py"


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

    def test_blocks_rm_rf_home(self):
        out = run_hook(make_bash_payload("rm -rf ~"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_rm_rf_dot(self):
        out = run_hook(make_bash_payload("rm -rf ."))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_force_push_main(self):
        out = run_hook(make_bash_payload("git push --force origin main"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_force_push_master(self):
        out = run_hook(make_bash_payload("git push origin master --force"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_git_reset_hard(self):
        out = run_hook(make_bash_payload("git reset --hard HEAD~3"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_git_clean_force(self):
        out = run_hook(make_bash_payload("git clean -fd"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_drop_table(self):
        out = run_hook(make_bash_payload("psql -c 'DROP TABLE users'"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_drop_database(self):
        out = run_hook(make_bash_payload("mysql -e 'DROP DATABASE mydb'"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_delete_without_where(self):
        out = run_hook(make_bash_payload("psql -c 'DELETE FROM users;'"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_mkfs(self):
        out = run_hook(make_bash_payload("mkfs.ext4 /dev/sda1"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_dd(self):
        out = run_hook(make_bash_payload("dd if=/dev/zero of=/dev/sda"))
        assert out is not None
        assert out["decision"] == "block"

    def test_blocks_fork_bomb(self):
        out = run_hook(make_bash_payload(":(){ :|:& };:"))
        assert out is not None
        assert out["decision"] == "block"


class TestSafeCommands:
    def test_allows_normal_rm(self):
        out = run_hook(make_bash_payload("rm temp.txt"))
        assert out is None

    def test_allows_git_push(self):
        out = run_hook(make_bash_payload("git push origin feature-branch"))
        assert out is None

    def test_allows_git_status(self):
        out = run_hook(make_bash_payload("git status"))
        assert out is None

    def test_allows_dry_run(self):
        out = run_hook(make_bash_payload("rm -rf / --dry-run"))
        assert out is None

    def test_allows_delete_with_where(self):
        out = run_hook(make_bash_payload("psql -c 'DELETE FROM users WHERE id = 1'"))
        assert out is None


class TestNonBashTool:
    def test_ignores_write_tool(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/x", "content": "rm -rf /"},
        }
        out = run_hook(payload)
        assert out is None
