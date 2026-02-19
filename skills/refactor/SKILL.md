---
name: refactor
description: Improve code structure without changing behavior, then create a GH Issue + PR.
argument-hint: [file or module path to refactor]
disable-model-invocation: false
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
---
Steps:
1) Ensure `gh` authenticated (`gh auth status`).
2) Read the target file or module from $ARGUMENTS.
3) Read existing tests for the target to understand current behavior.
4) Identify code smells (long functions, duplication, deep nesting, tight coupling, etc.).
5) Present a prioritized list of proposed refactorings with rationale.
6) After user approval, create branch: `refactor/<slug>` (e.g., `refactor/extract-views-helpers`).
7) Apply refactorings one at a time, running tests after each step.
8) Confirm all tests pass after the final change.
9) Create GH Issue:
    - `gh issue create --title "refactor: <concise description>" --body "<body>"`
    - Body must include: identified code smells, applied refactoring patterns, affected files, and test results.
10) Commit + push.
11) Create PR:
    - `gh pr create --title "refactor: <concise description>" --body "Closes #<issue_number>\n\n<details>"`
12) Report the PR URL to the user — continue with `/review` and `/ship`.

## Error Handling
- If `gh auth status` fails: stop and instruct the user to run `gh auth login`.
- If no tests exist for the target: warn the user and suggest writing tests before refactoring.
- If tests fail after a refactoring step: revert the step and report the issue. Do NOT push or create PR.

## Rollback
- If failure occurs after branch creation but before PR:
  1. `git checkout main`
  2. `git branch -D <branch>` (local cleanup)
  3. `git push origin --delete <branch>` (remote cleanup, if pushed)
- If failure occurs after PR creation: `gh pr close <pr_number>` then clean up branch.

## Guidelines
- Never change observable behavior — structure-only changes.
- Run tests after every individual step, not just at the end.
- Keep each change small and focused on one transformation.
