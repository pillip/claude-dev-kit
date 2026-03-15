#!/usr/bin/env python3
"""PostToolUse hook: auto-run related tests after Write/Edit on source files."""

import json
import os
import shutil
import subprocess
import sys

SKIP_EXTS = {".json", ".md", ".toml", ".yaml", ".yml", ".css", ".html", ".txt", ".cfg", ".ini", ".lock"}
PYTHON_EXTS = {".py"}
JS_EXTS = {".js", ".ts", ".jsx", ".tsx"}
TIMEOUT = 30


def find_python_test(filepath: str) -> str | None:
    """Find the corresponding test file for a Python source file."""
    basename = os.path.basename(filepath)
    dirpath = os.path.dirname(filepath)

    # If it's already a test file, run it directly
    if basename.startswith("test_"):
        return filepath

    # Search for test_<module>.py in tests/ directories
    module_name = basename.replace(".py", "")
    test_name = f"test_{module_name}.py"

    # Walk up to find a tests/ directory
    search_dir = dirpath
    while search_dir:
        tests_dir = os.path.join(search_dir, "tests")
        candidate = os.path.join(tests_dir, test_name)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(search_dir)
        if parent == search_dir:
            break
        search_dir = parent

    return None


def find_js_test(filepath: str) -> str | None:
    """Find the corresponding test file for a JS/TS source file."""
    basename = os.path.basename(filepath)
    dirpath = os.path.dirname(filepath)

    # If it's already a test/spec file, run it directly
    if ".test." in basename or ".spec." in basename:
        return filepath

    # Search for <name>.test.<ext> or <name>.spec.<ext>
    name, ext = os.path.splitext(basename)
    for suffix in [".test", ".spec"]:
        for search_ext in [ext, ".ts", ".js", ".tsx", ".jsx"]:
            candidate = os.path.join(dirpath, f"{name}{suffix}{search_ext}")
            if os.path.isfile(candidate):
                return candidate
            # Also check __tests__ directory
            tests_candidate = os.path.join(dirpath, "__tests__", f"{name}{suffix}{search_ext}")
            if os.path.isfile(tests_candidate):
                return tests_candidate

    return None


def find_js_runner() -> list[str] | None:
    """Detect available JS test runner."""
    if shutil.which("vitest"):
        return ["vitest", "run"]
    if shutil.which("jest"):
        return ["jest", "--no-coverage"]
    npx = shutil.which("npx")
    if npx:
        return [npx, "jest", "--no-coverage"]
    return None


def run_python_test(test_file: str) -> dict | None:
    pytest_cmd = shutil.which("pytest")
    if not pytest_cmd:
        return None

    try:
        result = subprocess.run(
            [pytest_cmd, test_file, "-x", "-q", "--tb=short", "--no-header"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {
            "decision": "block",
            "reason": f"Test timed out after {TIMEOUT}s: {test_file}",
        }

    if result.returncode != 0:
        output = (result.stdout + result.stderr)[-1000:]
        return {
            "decision": "block",
            "reason": f"Test failed: {test_file}\n{output}",
        }

    return None


def run_js_test(test_file: str) -> dict | None:
    runner = find_js_runner()
    if not runner:
        return None

    try:
        result = subprocess.run(
            [*runner, test_file],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {
            "decision": "block",
            "reason": f"Test timed out after {TIMEOUT}s: {test_file}",
        }

    if result.returncode != 0:
        output = (result.stdout + result.stderr)[-1000:]
        return {
            "decision": "block",
            "reason": f"Test failed: {test_file}\n{output}",
        }

    return None


def main():
    hook_input = json.loads(sys.stdin.read())
    tool_name = hook_input.get("tool_name", "")

    if tool_name not in ("Write", "Edit"):
        return

    tool_input = hook_input.get("tool_input", {})
    filepath = tool_input.get("file_path", "")
    if not filepath:
        return

    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    if ext in SKIP_EXTS:
        return

    result = None
    if ext in PYTHON_EXTS:
        test_file = find_python_test(filepath)
        if test_file and os.path.isfile(test_file):
            result = run_python_test(test_file)
    elif ext in JS_EXTS:
        test_file = find_js_test(filepath)
        if test_file and os.path.isfile(test_file):
            result = run_js_test(test_file)

    if result:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
