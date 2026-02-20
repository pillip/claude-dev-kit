---
name: migrate
description: Plan and execute a migration, then create a GH Issue + PR.
argument-hint: [migration target, e.g. "Django 5.0" or "Python 3.12"]
disable-model-invocation: false
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
---
Steps:
1) Ensure `gh` authenticated (`gh auth status`).
2) Identify the migration target from $ARGUMENTS (library version, DB schema, runtime, etc.).
3) Read the current project configuration (pyproject.toml, requirements, Dockerfile, etc.).
4) Scan the codebase for affected files, deprecated APIs, and breaking changes.
5) Generate a step-by-step migration plan with rollback instructions.
6) Present the plan to the user for approval.
7) Create worktree for the branch:
   ```bash
   WT="$(bash scripts/worktree.sh create migrate/<slug>)"
   ```
   All subsequent file operations happen inside `$WT/`.
8) Execute changes incrementally inside `$WT/`, running tests after each step.
9) Run the full test suite to confirm no regressions.
10) Update relevant documentation (README, CHANGELOG, architecture notes) inside `$WT/`.
11) Create GH Issue:
    - `gh issue create --title "migrate: <target description>" --body "<body>"`
    - Body must include: migration scope, affected files/APIs, step-by-step plan, and rollback instructions.
12) Commit + push (from `$WT/`).
13) Create PR:
    - `gh pr create --title "migrate: <target description>" --body "Closes #<issue_number>\n\n<details>"`
14) Report the PR URL to the user — continue with `/review` and `/ship`.

## Error Handling
- If `gh auth status` fails: stop and instruct the user to run `gh auth login`.
- If the migration target is ambiguous: ask the user to clarify the exact version or scope.
- If tests fail after a step: stop, report the failure, and suggest a rollback or fix. Do NOT push or create PR.

## Rollback
- **CRITICAL**: `cd` and `remove` MUST run in a single shell command (`&&`).
  A child process `cd` cannot change the parent shell's CWD — separate calls
  leave the shell in a deleted directory, breaking all subsequent commands.
- If failure occurs after worktree creation but before PR:
  1. `cd "$(bash scripts/worktree.sh root)" && bash scripts/worktree.sh remove <branch>`
  2. `git push origin --delete <branch>` (remote cleanup, if pushed)
- If failure occurs after PR creation: `gh pr close <pr_number>` then clean up worktree and branch as above.

## Guidelines
- Always create a rollback plan before making changes.
- Apply changes in small, reversible increments.
- Check official changelogs and migration guides before starting.
