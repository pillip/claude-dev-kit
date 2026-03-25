---
name: careful
description: Activates destructive command warnings for the current session. Use when working in sensitive environments.
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          command: "python3 ${CLAUDE_SKILL_DIR}/careful_guard.py"
---
Careful mode is now **active**. All Bash commands are screened for destructive patterns before execution.

Detected patterns will be blocked with an explanation. You can re-invoke the command to confirm.

**Covered patterns**: rm -rf, git push --force, git reset --hard, git branch -D, DROP TABLE, DELETE without WHERE, TRUNCATE, mkfs, dd, chmod -R 777, kubectl delete, docker system prune.

**Safe exceptions**: Removing common build artifacts (node_modules, dist, .next, __pycache__, .cache, build, .turbo, coverage) is always allowed.

**Bypass**: Commands with `--dry-run` are always allowed.

To deactivate, end this conversation or start a new one without `/careful`.
