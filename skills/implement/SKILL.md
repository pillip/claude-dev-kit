---
name: implement
description: 단일 이슈를 구현하고 GitHub Issue/PR을 생성하며 `Closes #N`으로 연결합니다. (1 issue = 1 PR)
argument-hint: [ISSUE-번호]
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
---
## Checkpoint Rules — MANDATORY
Every phase in this skill has a CHECKPOINT block. You MUST run the verification command after completing each phase. If the exit code is not 0, STOP immediately and report the failure. Do NOT proceed to the next phase. Skipping checkpoints is a critical violation.

**Path convention**: Checkpoint commands use `ROOT="$(bash scripts/worktree.sh root)"` to resolve the main repo root. This ensures the script is found regardless of whether CWD is the main repo or a worktree.

Hard requirements:
- Create GitHub Issue if missing: `gh issue create`
- Create/update PR and include `Closes #<issue_number>` in PR body.

Algorithm:
1) Ensure `gh` authenticated (gh auth status).
2) Locate $ARGUMENTS in issues.md. Read the issue's Goal, Scope, AC, and Implementation Notes.
   - **Manual check**: If the issue has `Manual: true`, STOP immediately. Report to the user: "This issue requires manual action — see Implementation Notes." Do NOT proceed with automated implementation.
2b) Gather context — read the following docs (if they exist, skip silently if not).
   **Read all applicable documents via parallel Read tool calls in a single message. Do NOT read them sequentially.**
   - `docs/prd_digest.md` — quick PRD context (goals, features, NFRs, scope)
   - `docs/architecture.md` — tech stack, modules, API design
   - `docs/data_model.md` — schema, indexes, query patterns, seed data, migrations
   - `docs/requirements.md` — related FRs/NFRs referenced by the issue
   - `docs/review_lessons.md` — known recurring review findings to proactively avoid
   - **UI context** — read all of the following in parallel (when the issue has `UI: true`, or contains UI keywords in Track/title):
     - `docs/design_system.md` — CSS tokens, component specs
     - `docs/design_philosophy.md` — aesthetic direction
     - `docs/wireframes.md` — layout for the relevant screen
     - `docs/interactions.md` — states, transitions, animations for the relevant flow
     - `docs/copy_guide.md` — UI labels, error messages, empty states, glossary
     - `prototype/screens/*.html` — visual reference for the relevant screen
   - **Mobile UI context** — read all of the following in parallel (when the issue involves mobile/React Native work):
     - `docs/design_system_mobile.md` — React Native 디자인 토큰, 컴포넌트 스펙
     - `docs/design_philosophy.md` — 미적 방향 (웹과 공유)
     - `docs/wireframes_mobile.md` — 모바일 레이아웃, 제스처, safe area
     - `docs/interactions_mobile.md` — 제스처 스펙, 햅틱 매핑, 트랜지션
     - `docs/copy_guide.md` — UI 라벨, 에러 메시지 (웹과 공유)
     - `prototype-mobile/src/screens/*.tsx` — React Native 화면 참조
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

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill implement --phase issue --issue $ARGUMENTS`
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

5) Create worktree for the branch:
   ```bash
   WT="$(bash scripts/worktree.sh create issue/$ARGUMENTS-<slug>)"
   ```
   All subsequent file operations (code, tests) happen inside `$WT/`.

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill implement --phase worktree --issue $ARGUMENTS`
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

6) Implement minimal code + tests inside `$WT/`.

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill implement --phase code --issue $ARGUMENTS`
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

7) Run tests inside `$WT/`.

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill implement --phase test --issue $ARGUMENTS`
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

8) Commit + push (from `$WT/`).

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill implement --phase push --issue $ARGUMENTS`
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

9) Create PR (or update):
   - Title: `[$ARGUMENTS] <title>`
   - Body begins with `Closes #<issue_number>`

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill implement --phase pr --issue $ARGUMENTS`
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

10) Record PR URL in issues.md; set Status=done; update STATUS.md.
    Use main repo root for shared files:
    ```bash
    ROOT="$(bash scripts/worktree.sh root)"
    bash scripts/flock_edit.sh "$ROOT/issues.md" -- bash -c '<update command>'
    bash scripts/flock_edit.sh "$ROOT/STATUS.md" -- bash -c '<update command>'
    ```

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `ROOT="$(bash scripts/worktree.sh root)" && python3 "$ROOT/scripts/verify_checkpoint.py" --skill implement --phase registry --issue $ARGUMENTS`
> If exit code ≠ 0: STOP immediately and report the failure. Do NOT proceed.

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
