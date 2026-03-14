# Execution Model

This document describes how claude-dev-kit orchestrates skills, agents, worktrees, and checkpoints at runtime.

## Skill → Agent Invocation

Skills (defined in `skills/<name>/SKILL.md`) are the entry points. Each skill:
1. Validates arguments and pre-conditions
2. Gathers context by reading project files
3. Invokes one or more agents via the Task tool
4. Verifies outputs at checkpoints

Agents (defined in `agents/<name>.md`) are specialized workers invoked by skills. An agent receives full document content (not file paths) as context and writes its output to a specified file.

### Invocation Chain
```
User runs /sprint
  → sprint SKILL.md algorithm executes
    → Invokes team-lead agent via Task tool
      → team-lead dispatches developer/reviewer/etc. per issue
        → Each agent follows its own guidelines + relevant SKILL.md
```

## Worktree Concurrent Execution

Each issue gets its own git worktree, enabling parallel work on multiple issues without branch conflicts.

### Worktree Lifecycle
1. **Create**: `bash scripts/worktree.sh create <branch-slug>`
2. **Work**: All file operations happen inside the worktree directory (`$WT/`)
3. **Remove**: `cd "$(bash scripts/worktree.sh root)" && bash scripts/worktree.sh remove <branch>`

### Parallel Safety
- Each worktree is an independent directory with its own working tree
- Multiple agents can work in different worktrees simultaneously
- Worktree slugs use word-boundary matching to avoid false positives (e.g., `ISSUE-001` does not match `ISSUE-0010`)

## flock_edit.sh — Race Condition Prevention

Shared registry files (`issues.md`, `STATUS.md`, `CHANGELOG.md`) live only on the main branch. When multiple agents need to update these files concurrently:

- All edits go through `scripts/flock_edit.sh`, which uses `flock(1)` to serialize writes
- Agents never commit registry files to feature branches
- Updates use `$ROOT/` path (repo root) to access the correct copy

## Checkpoint Gates

Checkpoints are mandatory verification points in every skill pipeline. They prevent broken artifacts from propagating to later phases.

### How Checkpoints Work
1. Each skill has `> **CHECKPOINT — MANDATORY — NEVER SKIP**` markers
2. After the marker, a verification command runs (typically `scripts/verify_checkpoint.py`)
3. If exit code ≠ 0: the pipeline STOPS immediately
4. The agent must report the failure and NOT proceed to the next phase

### Checkpoint Script
`scripts/verify_checkpoint.py` is the centralized verifier. It supports all skills:
- **implement**: issue → worktree → code → test → push → pr → registry
- **review**: checkout → review → ui-review → test → push
- **ship**: checks → merge → cleanup
- **diagnose/refactor/devops/migrate**: worktree → test → push
- **uiux/mobile-uiux**: context → philosophy → system

### Exit Codes
- `0` — checkpoint passed, proceed
- `1` — checkpoint failed, agent must stop
- `2` — usage error (invalid arguments)
- `124` — command timed out
- `127` — command not found (e.g., `gh` not installed)

### Network Resilience
Commands that depend on network (e.g., `gh` API calls) use `_run_with_retry()` which retries up to 2 times with a 1-second delay between attempts.
