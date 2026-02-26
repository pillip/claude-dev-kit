---
name: implement
description: 단일 이슈를 구현하고 GitHub Issue/PR을 생성하며 `Closes #N`으로 연결합니다. (1 issue = 1 PR)
argument-hint: [ISSUE-번호]
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
---
Hard requirements:
- Create GitHub Issue if missing: `gh issue create`
- Create/update PR and include `Closes #<issue_number>` in PR body.

Algorithm:
1) Ensure `gh` authenticated (gh auth status).
2) Locate $ARGUMENTS in issues.md. Read the issue's Goal, Scope, AC, and Implementation Notes.
2b) Gather context — read the following docs (if they exist, skip silently if not):
   - `docs/architecture.md` — tech stack, modules, data model
   - `docs/requirements.md` — related FRs/NFRs referenced by the issue
   - **UI context** (when the issue involves UI/frontend work):
     - `docs/design_system.md` — CSS tokens, component specs
     - `docs/design_philosophy.md` — aesthetic direction
     - `docs/wireframes.md` — layout for the relevant screen
     - `docs/interactions.md` — states, transitions, animations for the relevant flow
     - `docs/copy_guide.md` — UI labels, error messages, empty states, glossary
     - `prototype/screens/*.html` — visual reference for the relevant screen
   - Pass all relevant context to the developer subagent prompt.
3) Ensure Branch is set; if empty, derive `issue/$ARGUMENTS-<slug>` and write back.
   - **File lock**: wrap the issues.md read-modify-write with:
     `bash scripts/flock_edit.sh issues.md -- bash -c '<update command>'`
4) Ensure GH-Issue exists:
   - If empty: `gh issue create --title "[$ARGUMENTS] <title>" --body "<body>"`
   - Body must include: issue goal, scope (in/out), acceptance criteria, and implementation notes from issues.md.
   - Capture issue number/url; write back to issues.md.
   - **File lock**: wrap the issues.md write-back with:
     `bash scripts/flock_edit.sh issues.md -- bash -c '<update command>'`
5) Create worktree for the branch:
   ```bash
   WT="$(bash scripts/worktree.sh create issue/$ARGUMENTS-<slug>)"
   ```
   All subsequent file operations (code, tests) happen inside `$WT/`.
6) Implement minimal code + tests inside `$WT/`.
7) Run tests inside `$WT/`.
8) Commit + push (from `$WT/`).
9) Create PR (or update):
   - Title: `[$ARGUMENTS] <title>`
   - Body begins with `Closes #<issue_number>`
10) Record PR URL in issues.md; set Status=done; update STATUS.md.
    Use main repo root for shared files:
    ```bash
    ROOT="$(bash scripts/worktree.sh root)"
    bash scripts/flock_edit.sh "$ROOT/issues.md" -- bash -c '<update command>'
    bash scripts/flock_edit.sh "$ROOT/STATUS.md" -- bash -c '<update command>'
    ```

## Shared Registry Files
**IMPORTANT**: Never commit `issues.md`, `STATUS.md`, or `CHANGELOG.md` to the feature branch.
These are registry files managed only on main. Always use `$ROOT/` path with `flock_edit.sh`.

## Error Handling
- If `gh auth status` fails: stop and instruct the user to run `gh auth login`.
- If issue not found in issues.md: stop and report the missing issue number.
- If `gh issue create` fails: retry once; if still failing, stop and report the error.
- If tests fail: do NOT push or create PR. Report failing tests and stop.
- If `git push` fails: check for upstream conflicts; report and stop.
- If `gh pr create` fails: retry once; if still failing, the branch is already pushed — report and let user create PR manually.

## Rollback
- **CRITICAL**: `cd` and `remove` MUST run in a single shell command (`&&`).
  A child process `cd` cannot change the parent shell's CWD — separate calls
  leave the shell in a deleted directory, breaking all subsequent commands.
- If failure occurs after worktree creation but before PR:
  1. `cd "$(bash scripts/worktree.sh root)" && bash scripts/worktree.sh remove <branch>`
  2. `git push origin --delete <branch>` (remote cleanup, if pushed)
- If failure occurs after PR creation:
  1. `gh pr close <pr_number>` to close the broken PR.
  2. Clean up worktree and branch as above.
- Revert issues.md status back to `doing` or `backlog` if it was prematurely set to `done`.
