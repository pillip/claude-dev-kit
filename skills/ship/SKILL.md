---
name: ship
description: 테스트/문서/체인지로그를 정리하고 PR을 merge 해서 배포 가능한 상태로 만듭니다.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
---
Steps:
1) Identify PR to merge (current branch or most recent done issue PR).
2) Ensure tests pass locally and PR checks are green.
3) Update docs/README.md, STATUS.md; append CHANGELOG.md.
4) Merge via `gh pr merge` (merge/squash per repo rules) and delete branch.
5) Post-merge smoke on main (optional).

## Error Handling
- Pre-merge checks (must all pass before merging):
  1. `gh pr checks <pr>` — all CI checks must be green.
  2. Local test suite must pass.
  3. PR must not be in draft state.
  If any check fails: stop and report which check failed.
- If `gh pr merge` fails: report the error (e.g., merge conflicts, branch protection rules).
- If post-merge smoke test fails on main:
  1. Immediately alert the user with the failing test output.
  2. Suggest `git revert -m 1 <merge_commit>` to revert the merge.
  3. Do NOT auto-revert without user confirmation.

## Rollback
- If merge must be reverted:
  1. `git revert -m 1 <merge_commit_sha>` on main.
  2. Push the revert commit.
  3. Update CHANGELOG.md with a revert entry.
  4. Update STATUS.md to reflect the reverted state.
- Branch is already deleted after merge; if rework is needed, create a new branch from the revert.
