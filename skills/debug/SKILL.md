---
name: debug
description: Analyze a bug from error logs or reproduction steps, fix it, and create a GH Issue + PR.
argument-hint: [error description or file path]
disable-model-invocation: false
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
---
Steps:
1) Ensure `gh` authenticated (`gh auth status`).
2) Gather the bug context from $ARGUMENTS (error message, stack trace, file path, or reproduction steps).
3) If a file path is provided, read it. If an error message is provided, use Grep to locate the source.
4) Trace the execution path from the error backward to identify the root cause.
5) Form 1–3 ranked hypotheses and verify each by reading relevant code.
6) Present the confirmed root cause and a minimal fix to the user.
7) After user approval, apply the fix.
8) Run `pytest` to confirm no regressions. Suggest a regression test if none exists.
9) Create worktree for the branch:
   ```bash
   WT="$(bash scripts/worktree.sh create fix/<slug>)"
   ```
   Apply the fix inside `$WT/`, run tests from `$WT/`.
10) Create GH Issue:
    - `gh issue create --title "fix: <concise bug description>" --body "<body>"`
    - Body must include: error summary, root cause analysis, fix description, and affected files.
11) Commit + push (from `$WT/`).
12) Create PR:
    - `gh pr create --title "fix: <concise bug description>" --body "Closes #<issue_number>\n\n<details>"`
13) Report the PR URL to the user — continue with `/review` and `/ship`.

## Error Handling
- If `gh auth status` fails: stop and instruct the user to run `gh auth login`.
- If the error cannot be located in the codebase: ask the user for more context (full stack trace, reproduction steps).
- If multiple root causes are plausible: present all hypotheses ranked by likelihood and ask the user to help narrow down.
- If tests fail after fix: do NOT push or create PR. Report failing tests and stop.

## Rollback
- **CRITICAL**: `cd` and `remove` MUST run in a single shell command (`&&`).
  A child process `cd` cannot change the parent shell's CWD — separate calls
  leave the shell in a deleted directory, breaking all subsequent commands.
- If failure occurs after worktree creation but before PR:
  1. `cd "$(bash scripts/worktree.sh root)" && bash scripts/worktree.sh remove <branch>`
  2. `git push origin --delete <branch>` (remote cleanup, if pushed)
- If failure occurs after PR creation: `gh pr close <pr_number>` then clean up worktree and branch as above.

## Guidelines
- Never guess-and-patch. Always confirm the root cause before proposing a fix.
- Keep fixes minimal — do not refactor surrounding code.
