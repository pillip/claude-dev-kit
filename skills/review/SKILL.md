---
name: review
description: PR 기준 시니어 리뷰를 수행하고 최소 수정/테스트/리뷰노트를 남깁니다.
argument-hint: [ISSUE-번호]
disable-model-invocation: true
allowed-tools: Task, Read, Glob, Grep, Write, Edit, Bash
---
Steps:
1) Find PR from issues.md (PR field) or `gh pr status`.
2) Checkout the PR branch in a worktree:
   ```bash
   BRANCH="$(gh pr view <pr_number> --json headRefName -q .headRefName)"
   WT="$(bash scripts/worktree.sh create "$BRANCH")"
   ```
   All subsequent file operations happen inside `$WT/`.

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill review --phase checkout --issue $ARGUMENTS`
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

3) Gather review context:
   **Read all applicable context files via parallel Read tool calls in a single message.**
   - `docs/review_lessons.md` — if exists (for recurring pattern detection)
   - `docs/architecture.md` — if exists (for conformance checks)
   - For UI issues, also read in parallel: `docs/design_system.md` (or `design_system_mobile.md`), `docs/copy_guide.md`, `docs/interactions.md` (or `interactions_mobile.md`), `docs/wireframes.md` (or `wireframes_mobile.md`).

   Ask reviewer subagent to perform code review + security audit:
   - Code quality: correctness, edge cases, maintainability, complexity, test coverage.
   - Security: injection, auth issues, hardcoded secrets, dependency CVEs, input validation, XSS, misconfiguration.
   - Pass gathered context (review_lessons, architecture) so the reviewer can identify recurring patterns.
3.5) IF the issue involves UI/frontend work (check `UI: true` field first; fall back to Track/title keywords: "UI", "screen", "component", "prototype"):
   Ask ui-reviewer subagent to perform UI state review:
   - Pass the UI context files gathered in step 3 plus `docs/review_lessons.md`.
   - Reviewer checks state coverage, copy compliance, token usage, accessibility, interaction fidelity.
   - Output: `docs/ui_review_notes.md` with severity-classified findings.

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill review --phase ui-review --issue $ARGUMENTS`
> The script auto-detects UI issues via Track field/title keywords. Non-UI issues pass automatically.
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

4) Apply minimal fixes for Critical/High findings (code + UI); re-run tests inside `$WT/`.

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill review --phase test --issue $ARGUMENTS`
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

5) Update docs/review_notes.md (inside `$WT/`) with sections:
   - **Code Review**: findings, changes, follow-ups.
   - **Security Findings**: severity-classified list with remediation steps.
   - **UI Review** (from ui-reviewer, if applicable): State Coverage, Copy, Tokens, Accessibility.
5.5) Ask reviewer subagent to update `docs/review_lessons.md`:
   - Use `$ROOT/docs/review_lessons.md` with `flock_edit.sh` for safe concurrent modification.
   - Add new preventable patterns or increment frequency of existing ones.

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill review --phase review --issue $ARGUMENTS`
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

6) Commit + push from `$WT/`.

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill review --phase push --issue $ARGUMENTS`
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

7) If PR is draft and ready: `gh pr ready`.

## Shared Registry Files
**IMPORTANT**: Never commit `issues.md`, `STATUS.md`, or `CHANGELOG.md` to the feature branch.
These are registry files managed only on main. Always use `$ROOT/` path with `flock_edit.sh`.

## Error Handling
- If PR not found (issues.md has no PR field and `gh pr status` returns nothing): stop and report; suggest running `/implement` first.
- If reviewer subagent fails: retry once; if still failing, skip automated review and log a warning in docs/review_notes.md.
- If applied fixes break tests:
  1. Revert the fix commits: `git checkout -- <files>` for unstaged or `git revert HEAD` for committed changes (inside `$WT/`).
  2. Re-run tests to confirm the branch is back to a passing state.
  3. Log the failed fix attempt in docs/review_notes.md as a follow-up item.
- If `gh pr ready` fails: report the error but do not block — the PR can be manually marked ready.

## Rollback
- Review changes are commits on the existing PR branch.
- If review fixes must be fully undone: `git revert` the review commits (do not force-push).
- docs/review_notes.md is append-only; no rollback needed for notes.
- Clean up worktree when done: `cd "$(bash scripts/worktree.sh root)" && bash scripts/worktree.sh remove "$BRANCH"`.
