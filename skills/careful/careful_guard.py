#!/usr/bin/env python3
"""PreToolUse hook: warn on destructive Bash commands (skill-level /careful guard).

Unlike the global dangerous_command_guard.py which hard-blocks, this guard
blocks with an explanatory message that encourages the user to re-confirm.
It also covers additional risky patterns beyond the global guard.
"""

import json
import re
import sys

DANGEROUS_PATTERNS = [
    # Destructive file operations
    (r"rm\s+-[^\s]*r[^\s]*f[^\s]*\s+/\s*$|rm\s+-[^\s]*r[^\s]*f[^\s]*\s+/[^a-zA-Z]", "rm -rf on root"),
    (r"rm\s+-[^\s]*r[^\s]*f[^\s]*\s+~", "rm -rf on home directory"),
    (r"rm\s+-[^\s]*r[^\s]*f[^\s]*\s+\.\s*$", "rm -rf on current directory"),
    # Git destructive operations
    (r"git\s+push\s+.*--force", "git push --force"),
    (r"git\s+reset\s+--hard", "git reset --hard"),
    (r"git\s+clean\s+-[^\s]*f", "git clean with force"),
    (r"git\s+branch\s+-D\b", "git branch force-delete"),
    (r"git\s+checkout\s+\.\s*$", "git checkout . (discard all changes)"),
    (r"git\s+restore\s+\.\s*$", "git restore . (discard all changes)"),
    # Database destructive operations
    (r"DROP\s+(TABLE|DATABASE)", "DROP TABLE/DATABASE"),
    (r"DELETE\s+FROM\s+\w+\s*;", "DELETE without WHERE clause"),
    (r"TRUNCATE\s+", "TRUNCATE"),
    # System-level danger
    (r"\bmkfs\b", "mkfs (format filesystem)"),
    (r"\bdd\s+if=", "dd (raw disk write)"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "Fork bomb"),
    # Additional patterns beyond global guard
    (r"chmod\s+-R\s+777\b", "chmod -R 777 (world-writable)"),
    (r">\s*/dev/sd[a-z]", "direct device write"),
    (r"kubectl\s+delete\b", "kubectl delete"),
    (r"docker\s+system\s+prune", "docker system prune"),
]

# Safe exceptions — always allow these
SAFE_PATTERNS = [
    r"rm\s+-rf?\s+(node_modules|\.next|dist|__pycache__|\.cache|build|\.turbo|coverage)\b",
]


def check_command(command: str) -> tuple[bool, str]:
    if "--dry-run" in command:
        return False, ""

    for pattern in SAFE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
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
            "reason": (
                f"[careful] Potentially destructive: {label}. "
                f"Command: {command[:120]}. "
                f"Re-invoke the command to confirm you intend to proceed."
            ),
        }))


if __name__ == "__main__":
    main()
