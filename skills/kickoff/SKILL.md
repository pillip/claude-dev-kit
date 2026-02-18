---
name: kickoff
description: PRD 기반으로 요구사항/UX 스펙/아키텍처/이슈/테스트 플랜(전략)을 생성합니다. (v0: UX spec only)
argument-hint: [PRD.md 경로]
disable-model-invocation: true
allowed-tools: Task, Read, Glob, Grep, Write, Edit
---
Steps:
1) Ensure docs/ exists.
2) Read PRD ($ARGUMENTS or PRD.md).
3) Run subagents to write:
   - requirement-analyst -> docs/requirements.md
   - ux-designer -> docs/ux_spec.md
   - architect -> docs/architecture.md
   - planner -> issues.md
   - qa-designer -> docs/test_plan.md
4) Create/update docs/README.md (setup/run/test).
5) Create/update STATUS.md (milestone/risks/next issues).
Outputs must exist: docs/requirements.md, docs/ux_spec.md, docs/architecture.md, docs/test_plan.md, issues.md, STATUS.md.

## Error Handling
- If a subagent fails (Task tool returns error):
  1. Retry the failed subagent once.
  2. If it fails again, skip with a warning message and continue with remaining subagents.
  3. Log the skipped subagent in STATUS.md under a `## Warnings` section.
- If the PRD file is not found: stop immediately and report the missing path.
- If docs/ cannot be created: stop immediately and report the filesystem error.

## Rollback
- Kickoff is additive (writes new files); no destructive rollback is needed.
- If partially completed, re-running `/kickoff` overwrites all outputs — safe to retry.
- If a subagent was skipped, re-run `/kickoff` after fixing the root cause to regenerate the missing document.
