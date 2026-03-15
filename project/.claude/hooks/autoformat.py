#!/usr/bin/env python3
"""PostToolUse hook: auto-format/lint files after Write or Edit."""

import json
import os
import shutil
import subprocess
import sys

# Extensions mapped to formatters
PYTHON_EXTS = {".py"}
JS_EXTS = {".js", ".ts", ".jsx", ".tsx", ".json", ".css"}


def find_config(name: str) -> str | None:
    """Walk up from cwd to find a config file."""
    d = os.getcwd()
    while True:
        candidate = os.path.join(d, name)
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def run(cmd: list[str], filepath: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.dirname(filepath) or ".")


def handle_python(filepath: str) -> dict | None:
    ruff = shutil.which("ruff")
    if not ruff:
        return None

    config_args = []
    ruff_toml = find_config("ruff.toml")
    if ruff_toml:
        config_args = ["--config", ruff_toml]

    # 1. Auto-fix lint issues
    run([ruff, "check", "--fix", *config_args, filepath], filepath)

    # 2. Format
    run([ruff, "format", *config_args, filepath], filepath)

    # 3. Re-check for remaining errors
    result = run([ruff, "check", *config_args, filepath], filepath)
    if result.returncode != 0:
        return {
            "decision": "block",
            "reason": f"ruff lint errors remain after auto-fix:\n{result.stdout}{result.stderr}",
        }

    return None


def handle_js(filepath: str) -> dict | None:
    prettier = shutil.which("prettier")
    if not prettier:
        # Try npx as fallback
        npx = shutil.which("npx")
        if not npx:
            return None
        prettier_cmd = [npx, "prettier"]
    else:
        prettier_cmd = [prettier]

    config_args = []
    prettierrc = find_config(".prettierrc.json")
    if prettierrc:
        config_args = ["--config", prettierrc]

    # 1. Format
    result = run([*prettier_cmd, "--write", *config_args, filepath], filepath)
    if result.returncode != 0:
        return {
            "decision": "block",
            "reason": f"prettier failed:\n{result.stdout}{result.stderr}",
        }

    return None


def main():
    hook_input = json.loads(sys.stdin.read())
    tool_name = hook_input.get("tool_name", "")

    if tool_name not in ("Write", "Edit"):
        return

    tool_input = hook_input.get("tool_input", {})
    filepath = tool_input.get("file_path", "")
    if not filepath or not os.path.isfile(filepath):
        return

    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    result = None
    if ext in PYTHON_EXTS:
        result = handle_python(filepath)
    elif ext in JS_EXTS:
        result = handle_js(filepath)

    if result:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
