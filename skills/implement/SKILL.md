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
2) Locate $ARGUMENTS in issues.md.
3) Ensure Branch is set; if empty, derive `issue/$ARGUMENTS-<slug>` and write back.
4) Ensure GH-Issue exists:
   - If empty: `gh issue create --title "[$ARGUMENTS] <title>" --body "<body>"`
   - Body must include: issue goal, scope (in/out), acceptance criteria, and implementation notes from issues.md.
   - Capture issue number/url; write back to issues.md.
5) Checkout branch; implement minimal code + tests.
6) Run tests.
7) Commit + push.
8) Create PR (or update):
   - Title: `[$ARGUMENTS] <title>`
   - Body begins with `Closes #<issue_number>`
9) Record PR URL in issues.md; set Status=done; update STATUS.md.

## Error Handling
- If `gh auth status` fails: stop and instruct the user to run `gh auth login`.
- If issue not found in issues.md: stop and report the missing issue number.
- If `gh issue create` fails: retry once; if still failing, stop and report the error.
- If tests fail: do NOT push or create PR. Report failing tests and stop.
- If `git push` fails: check for upstream conflicts; report and stop.
- If `gh pr create` fails: retry once; if still failing, the branch is already pushed — report and let user create PR manually.

## Rollback
- If failure occurs after branch creation but before PR:
  1. `git checkout main`
  2. `git branch -D <branch>` (local cleanup)
  3. `git push origin --delete <branch>` (remote cleanup, if pushed)
- If failure occurs after PR creation:
  1. `gh pr close <pr_number>` to close the broken PR.
  2. Clean up branch as above.
- Revert issues.md status back to `doing` or `backlog` if it was prematurely set to `done`.
