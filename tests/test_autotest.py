import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "project" / ".claude" / "hooks" / "autotest.py"


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


class TestPythonTestDiscovery:
    def test_runs_test_file_directly(self):
        """When editing a test file itself, it should run that file."""
        with tempfile.TemporaryDirectory() as td:
            test_file = Path(td) / "test_example.py"
            test_file.write_text("def test_pass(): assert True\n")

            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": str(test_file)},
            }
            out = run_hook(payload)
            # Test should pass, so no block
            assert out is None

    def test_finds_corresponding_test(self):
        """When editing src/module.py, should find tests/test_module.py."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src_dir = td / "src"
            src_dir.mkdir()
            tests_dir = td / "tests"
            tests_dir.mkdir()

            src_file = src_dir / "calculator.py"
            src_file.write_text("def add(a, b): return a + b\n")

            test_file = tests_dir / "test_calculator.py"
            test_file.write_text("def test_add(): assert 1 + 1 == 2\n")

            payload = {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(src_file)},
            }
            out = run_hook(payload)
            assert out is None

    def test_blocks_on_failing_test(self):
        """When the corresponding test fails, should block."""
        with tempfile.TemporaryDirectory() as td:
            test_file = Path(td) / "test_broken.py"
            test_file.write_text("def test_fail(): assert False\n")

            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": str(test_file)},
            }
            out = run_hook(payload)
            assert out is not None
            assert out["decision"] == "block"
            assert "Test failed" in out["reason"]

    def test_skips_when_no_test_found(self):
        """When no corresponding test exists, should not block."""
        with tempfile.TemporaryDirectory() as td:
            src_file = Path(td) / "orphan_module.py"
            src_file.write_text("x = 1\n")

            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": str(src_file)},
            }
            out = run_hook(payload)
            assert out is None


class TestSkipFiles:
    def test_skips_json(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/config.json"},
        }
        out = run_hook(payload)
        assert out is None

    def test_skips_markdown(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/README.md"},
        }
        out = run_hook(payload)
        assert out is None

    def test_skips_toml(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/pyproject.toml"},
        }
        out = run_hook(payload)
        assert out is None

    def test_skips_css(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/styles.css"},
        }
        out = run_hook(payload)
        assert out is None


class TestJSTestDiscovery:
    def test_runs_test_file_directly(self):
        """When editing a .test.ts file, it should try to run it (skip if no runner)."""
        with tempfile.TemporaryDirectory() as td:
            test_file = Path(td) / "app.test.js"
            test_file.write_text("test('pass', () => expect(true).toBe(true));\n")

            payload = {
                "tool_name": "Write",
                "tool_input": {"file_path": str(test_file)},
            }
            # Without jest/vitest installed, should skip gracefully
            out = run_hook(payload)
            # Either None (no runner) or a result - should not crash
            assert out is None or "decision" in out

    def test_finds_test_file_for_source(self):
        """When editing app.ts, should look for app.test.ts."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "app.ts"
            src.write_text("export const x = 1;\n")
            test = td / "app.test.ts"
            test.write_text("test('x', () => {});\n")

            payload = {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(src)},
            }
            # Without jest/vitest installed, should skip gracefully
            out = run_hook(payload)
            assert out is None or "decision" in out


class TestNonTargetTools:
    def test_ignores_bash(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
        }
        out = run_hook(payload)
        assert out is None
