---
name: review
description: PR 기준 시니어 리뷰를 수행하고 최소 수정/테스트/리뷰노트를 남깁니다.
argument-hint: [ISSUE-번호]
disable-model-invocation: true
allowed-tools: Task, Read, Glob, Grep, Write, Edit, Bash
---
Steps:
1) Find PR from issues.md (PR field) or `gh pr status`.
2) Ask reviewer subagent to perform code review + security audit:
   - Code quality: correctness, edge cases, maintainability, complexity, test coverage.
   - Security: injection, auth issues, hardcoded secrets, dependency CVEs, input validation, XSS, misconfiguration.
3) Apply minimal fixes for Critical/High security findings and code issues; re-run tests.
4) Update docs/review_notes.md with two sections:
   - **Code Review**: findings, changes, follow-ups.
   - **Security Findings**: severity-classified list with remediation steps.
5) If PR is draft and ready: `gh pr ready`.

## Error Handling
- If PR not found (issues.md has no PR field and `gh pr status` returns nothing): stop and report; suggest running `/implement` first.
- If reviewer subagent fails: retry once; if still failing, skip automated review and log a warning in docs/review_notes.md.
- If applied fixes break tests:
  1. Revert the fix commits: `git checkout -- <files>` for unstaged or `git revert HEAD` for committed changes.
  2. Re-run tests to confirm the branch is back to a passing state.
  3. Log the failed fix attempt in docs/review_notes.md as a follow-up item.
- If `gh pr ready` fails: report the error but do not block — the PR can be manually marked ready.

## Rollback
- Review changes are commits on the existing PR branch.
- If review fixes must be fully undone: `git revert` the review commits (do not force-push).
- docs/review_notes.md is append-only; no rollback needed for notes.
