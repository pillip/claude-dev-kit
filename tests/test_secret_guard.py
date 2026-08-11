import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "project" / ".claude" / "hooks" / "secret_guard.py"


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


def run_hook_raw(raw_stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw_stdin,
        capture_output=True,
        text=True,
    )


class TestSecretDetection:
    def test_blocks_aws_key(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/config.py",
                "content": 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"',
            },
        }
        out = run_hook(payload)
        assert out is not None
        assert out["decision"] == "block"
        assert "AWS Access Key" in out["reason"]

    def test_blocks_openai_key(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/tmp/app.py",
                "new_string": 'api_key = "sk-abc123def456ghi789jkl012mno"',
            },
        }
        out = run_hook(payload)
        assert out is not None
        assert out["decision"] == "block"
        assert "OpenAI" in out["reason"]

    def test_blocks_github_pat(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/config.py",
                "content": 'TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"',
            },
        }
        out = run_hook(payload)
        assert out is not None
        assert out["decision"] == "block"
        assert "GitHub Personal Access Token" in out["reason"]

    def test_blocks_private_key(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/key.pem",
                "content": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...",
            },
        }
        out = run_hook(payload)
        assert out is not None
        assert out["decision"] == "block"
        assert "Private Key" in out["reason"]

    def test_blocks_hardcoded_password(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/config.py",
                "content": 'password = "super_secret_123"',
            },
        }
        out = run_hook(payload)
        assert out is not None
        assert out["decision"] == "block"
        assert "password" in out["reason"].lower()

    def test_blocks_hardcoded_secret(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/tmp/config.py",
                "new_string": 'secret = "my_secret_value"',
            },
        }
        out = run_hook(payload)
        assert out is not None
        assert out["decision"] == "block"

    def test_allows_clean_content(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/app.py",
                "content": 'api_key = os.environ["API_KEY"]',
            },
        }
        out = run_hook(payload)
        assert out is None


class TestSkipFiles:
    def test_skips_env_example(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/.env.example",
                "content": 'password = "placeholder"',
            },
        }
        out = run_hook(payload)
        assert out is None

    def test_skips_markdown(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/README.md",
                "content": 'password = "example"',
            },
        }
        out = run_hook(payload)
        assert out is None

    def test_skips_test_files(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/test_config.py",
                "content": 'password = "test_password"',
            },
        }
        out = run_hook(payload)
        assert out is None

    def test_skips_tests_directory(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/tests/test_auth.py",
                "content": 'FAKE_KEY = "sk-testapikey1234567890abcdef"',
            },
        }
        out = run_hook(payload)
        assert out is None


class TestNonTargetTools:
    def test_ignores_bash(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo AKIAIOSFODNN7EXAMPLE"},
        }
        out = run_hook(payload)
        assert out is None


class TestMalformedStdin:
    def assert_guard_skipped(self, result: subprocess.CompletedProcess):
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert "secret_guard" in result.stderr
        assert "malformed hook payload" in result.stderr
        assert "guard skipped" in result.stderr
        assert "Traceback" not in result.stderr

    def test_garbage_stdin_skips_guard_without_traceback(self):
        result = run_hook_raw("not-json")
        self.assert_guard_skipped(result)

    def test_empty_stdin_skips_guard_without_traceback(self):
        result = run_hook_raw("")
        self.assert_guard_skipped(result)

    def test_truncated_json_skips_guard_without_traceback(self):
        result = run_hook_raw('{"tool_name": "Write", "tool_input": {')
        self.assert_guard_skipped(result)

    def test_valid_blocking_payload_keeps_stderr_clean(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/config.py",
                "content": 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"',
            },
        }
        result = run_hook_raw(json.dumps(payload))
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["decision"] == "block"
        assert result.stderr == ""
