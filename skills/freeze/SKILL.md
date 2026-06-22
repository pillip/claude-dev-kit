---
name: freeze
description: Blocks file edits outside a specified directory boundary. Use to scope work to a specific module.
argument-hint: "[directory path to allow edits in]"
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
hooks:
  PreToolUse:
    - matcher: "Edit"
      hooks:
        - type: command
          command: "bash -c 'for D in \"$CLAUDE_PLUGIN_ROOT/skills/freeze\" \"$CLAUDE_SKILL_DIR\" \"${CLAUDE_PROJECT_DIR:-.}/.claude/skills/freeze\"; do [ -n \"$D\" ] && [ -f \"$D/freeze_guard.py\" ] && exec python3 \"$D/freeze_guard.py\"; done; true'"
    - matcher: "Write"
      hooks:
        - type: command
          command: "bash -c 'for D in \"$CLAUDE_PLUGIN_ROOT/skills/freeze\" \"$CLAUDE_SKILL_DIR\" \"${CLAUDE_PROJECT_DIR:-.}/.claude/skills/freeze\"; do [ -n \"$D\" ] && [ -f \"$D/freeze_guard.py\" ] && exec python3 \"$D/freeze_guard.py\"; done; true'"
---
Freeze mode activated.

## Setup
1. Validate that `$ARGUMENTS` is a valid directory path. If not provided, ask the user which directory to freeze to.
2. Resolve to an absolute path.
3. Write the absolute path to `.claude-kit/freeze-dir.txt` in the repo root:
   ```bash
   mkdir -p .claude-kit && echo "<absolute-path>" > .claude-kit/freeze-dir.txt
   ```
4. Report: "Freeze boundary set to: `<path>`. All Edit/Write operations outside this directory will be blocked."

## Behavior
- **Read/Glob/Grep**: Always allowed anywhere (read-only operations).
- **Edit/Write inside boundary**: Allowed.
- **Edit/Write outside boundary**: Hard-blocked with explanation.

## Deactivation
To deactivate, remove the boundary file:
```bash
rm -f .claude-kit/freeze-dir.txt
```
Or end this conversation.
