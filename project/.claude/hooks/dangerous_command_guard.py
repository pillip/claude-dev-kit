#!/usr/bin/env python3
"""PreToolUse hook: block dangerous Bash commands."""

import json
import re
import sys

DANGEROUS_PATTERNS = [
    (r"rm\s+-[^\s]*r[^\s]*f[^\s]*\s+/\s*$|rm\s+-[^\s]*r[^\s]*f[^\s]*\s+/[^a-zA-Z]", "rm -rf on root"),
    (r"rm\s+-[^\s]*r[^\s]*f[^\s]*\s+~", "rm -rf on home directory"),
    (r"rm\s+-[^\s]*r[^\s]*f[^\s]*\s+\.\s*$", "rm -rf on current directory"),
    (r"git\s+push\s+.*--force.*\s+(main|master)\b|git\s+push\s+.*\s+(main|master)\b.*--force", "Force push to main/master"),
    (r"git\s+reset\s+--hard", "git reset --hard"),
    (r"git\s+clean\s+-[^\s]*f", "git clean with force"),
    (r"DROP\s+(TABLE|DATABASE)", "DROP TABLE/DATABASE"),
    (r"DELETE\s+FROM\s+\w+\s*;", "DELETE without WHERE clause"),
    (r"\bmkfs\b", "mkfs (format filesystem)"),
    (r"\bdd\s+if=", "dd (raw disk write)"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "Fork bomb"),
]


def check_command(command: str) -> tuple[bool, str]:
    if "--dry-run" in command:
        return False, ""

    for pattern, label in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, label

    return False, ""


def main():
    hook_input = json.loads(sys.stdin.read())
    tool_name = hook_input.get("tool_name", "")

    if tool_name != "Bash":
        return

    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")

    if not command:
        return

    is_dangerous, label = check_command(command)
    if is_dangerous:
        print(json.dumps({
            "decision": "block",
            "reason": f"Dangerous command blocked: {label}. "
                      f"Command: {command[:100]}",
        }))


if __name__ == "__main__":
    main()
