---
name: guard
description: Activates both careful mode (destructive command warnings) and freeze mode (edit boundary). Use for maximum safety.
argument-hint: "[directory path to allow edits in]"
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "bash -c 'for D in \"$CLAUDE_PLUGIN_ROOT/skills/careful\" \"$CLAUDE_SKILL_DIR/../careful\" \"${CLAUDE_PROJECT_DIR:-.}/.claude/skills/careful\"; do [ -n \"$D\" ] && [ -f \"$D/careful_guard.py\" ] && exec python3 \"$D/careful_guard.py\"; done; true'"
    - matcher: "Edit"
      hooks:
        - type: command
          command: "bash -c 'for D in \"$CLAUDE_PLUGIN_ROOT/skills/freeze\" \"$CLAUDE_SKILL_DIR/../freeze\" \"${CLAUDE_PROJECT_DIR:-.}/.claude/skills/freeze\"; do [ -n \"$D\" ] && [ -f \"$D/freeze_guard.py\" ] && exec python3 \"$D/freeze_guard.py\"; done; true'"
    - matcher: "Write"
      hooks:
        - type: command
          command: "bash -c 'for D in \"$CLAUDE_PLUGIN_ROOT/skills/freeze\" \"$CLAUDE_SKILL_DIR/../freeze\" \"${CLAUDE_PROJECT_DIR:-.}/.claude/skills/freeze\"; do [ -n \"$D\" ] && [ -f \"$D/freeze_guard.py\" ] && exec python3 \"$D/freeze_guard.py\"; done; true'"
---
Guard mode activated — combines `/careful` and `/freeze`.

## Setup
1. Validate that `$ARGUMENTS` is a valid directory path. If not provided, ask the user.
2. Resolve to an absolute path and write to `.claude-kit/freeze-dir.txt`:
   ```bash
   mkdir -p .claude-kit && echo "<absolute-path>" > .claude-kit/freeze-dir.txt
   ```
3. Report activation status:
   - "Careful mode: ON — destructive Bash commands will be warned."
   - "Freeze mode: ON — edits restricted to `<path>`."

## Active Guards
- **Careful** (Bash): Warns on rm -rf, git push --force, git reset --hard, DROP TABLE, etc.
- **Freeze** (Edit/Write): Blocks file edits outside the freeze boundary.

## Deactivation
```bash
rm -f .claude-kit/freeze-dir.txt
```
Or end this conversation.
