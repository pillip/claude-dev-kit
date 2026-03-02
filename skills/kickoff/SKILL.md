---
name: kickoff
description: PRD 기반으로 요구사항/UX 스펙/아키텍처/데이터 모델/이슈/테스트 플랜을 생성합니다. 6개 서브에이전트를 순서대로 실행합니다.
argument-hint: [PRD.md 경로]
disable-model-invocation: true
allowed-tools: Task, Read, Glob, Grep, Write, Edit
---

## Algorithm

### Phase 1 — Setup
1) Ensure `docs/` directory exists.
2) Read PRD (`$ARGUMENTS` or `PRD.md`). If not found, stop immediately and report.
3) Read existing project files if any (README, pyproject.toml, etc.) to understand tech stack context.

### Phase 1.5 — PRD Digest (Phase 2 전에 실행)
PRD가 3000단어 이상이면, 다음 구조로 요약을 생성하여 `docs/prd_digest.md`에 저장:
  - Goals (3줄 이내)
  - Target User (1줄)
  - Must-have Features (번호 목록, 각 1줄)
  - Key NFRs (번호 목록, 각 1줄)
  - Scope Boundaries (In/Out 각 3줄 이내)

이후 subagent에 context 전달 시: PRD 원문 + `docs/prd_digest.md`를 함께 전달.
3000단어 미만이면 이 단계를 skip.

### Phase 2 — Run Subagents (sequential, dependency order)

Subagents MUST run in this order because later agents depend on earlier outputs:

**Step 1: requirement-analyst → `docs/requirements.md`**
- Context to pass: Full PRD content + `docs/prd_digest.md` (if exists)
- Agent produces: Goals, prioritized user stories with AC, FRs, NFRs with measurable targets, scope, assumptions, risks
- Verify output exists before proceeding

**Step 2: ux-designer → `docs/ux_spec.md`**
- Context to pass: PRD + `docs/prd_digest.md` (if exists) + `docs/requirements.md`
- Agent produces: IA, key flows with error paths, screen list with 5 states each, copy guidelines, accessibility notes
- Verify output exists before proceeding

**Step 3: architect → `docs/architecture.md`**
- Context to pass: PRD + `docs/prd_digest.md` (if exists) + `docs/requirements.md` + `docs/ux_spec.md`
- Agent produces: Tech stack, modules, data model, API design, security, deployment, tradeoffs table
- Verify output exists before proceeding

**Step 3.5: data-modeler → `docs/data_model.md`**
- Context to pass: PRD + `docs/prd_digest.md` (if exists) + `docs/requirements.md` + `docs/ux_spec.md` + `docs/architecture.md`
- Agent produces: Access patterns, detailed schema (tables, columns, types, constraints), indexes with justification, migration strategy, seed data, query patterns, scaling notes
- Verify output exists before proceeding

**Step 4 & 5 (parallel — no dependency between them):**

**planner → `issues.md`**
- Context to pass: PRD + `docs/prd_digest.md` (if exists) + `docs/requirements.md` + `docs/ux_spec.md` + `docs/architecture.md` + `docs/data_model.md` + `docs/review_lessons.md` (if exists)
- Agent produces: Issues sized 0.5d–1.5d with AC, tests, dependencies, implementation notes
- Verify output exists

**qa-designer → `docs/test_plan.md`**
- Context to pass: PRD + `docs/prd_digest.md` (if exists) + `docs/requirements.md` + `docs/ux_spec.md` + `docs/architecture.md` + `docs/data_model.md`
- Agent produces: Risk matrix, critical flow test cases, edge cases, fixtures, automation candidates, smoke checklist
- Verify output exists

### Phase 3 — Supporting Documents
4) Create/update `docs/README.md`:
   - Project name and description (from PRD)
   - Prerequisites (from architecture tech stack)
   - Setup instructions (install, configure, run)
   - Test instructions
5) Create/update `STATUS.md`:
   - Current milestone (from PRD goals)
   - Issue summary (total, by priority, by track)
   - Key risks (from requirements)
   - Next issues to implement (top 3 P0 issues)

### Phase 4 — Verification
6) Run `scripts/validate_issues.py issues.md` to validate issue quality:
   - If violations are found, re-invoke the planner subagent once with the violation list and ask it to fix the issues.
   - If violations remain after the retry, log them in `STATUS.md` under `## Warnings` and proceed.
7) Verify all required outputs exist:
   - `docs/requirements.md`
   - `docs/ux_spec.md`
   - `docs/architecture.md`
   - `docs/data_model.md`
   - `docs/test_plan.md`
   - `issues.md`
   - `STATUS.md`
8) Report summary to the user:
   - Number of FRs/NFRs identified
   - Number of screens in UX spec
   - Architecture style chosen
   - Number of issues created
   - Suggest next step: `/uiux` (웹 UI 프로젝트), `/mobile-uiux` (모바일 앱 프로젝트), or `/implement ISSUE-001`

## Subagent Invocation Pattern

When invoking each subagent via the Task tool:
- Include the agent name in the prompt (e.g., "You are the requirement-analyst agent")
- Pass the full content of input documents — do NOT just pass file paths
- Specify the exact output file path
- Include: "Write your output to `docs/<file>.md`. Follow your agent guidelines precisely."

## Error Handling
- If a subagent fails (Task tool returns error):
  1. Retry the failed subagent once with the same context.
  2. If it fails again, skip with a warning message and continue with remaining subagents.
  3. Log the skipped subagent in `STATUS.md` under a `## Warnings` section.
- If the PRD file is not found: stop immediately and report the missing path.
- If `docs/` cannot be created: stop immediately and report the filesystem error.
- If a subagent produces empty or malformed output: treat as failure, retry once.

## Rollback
- Kickoff is additive (writes new files); no destructive rollback is needed.
- If partially completed, re-running `/kickoff` overwrites all outputs — safe to retry.
- If a subagent was skipped, re-run `/kickoff` after fixing the root cause to regenerate the missing document.

## Guidelines
- The dependency order is critical: requirements → UX → architecture → data model → (planner + QA in parallel).
- Each subagent should receive ALL prior outputs as context for maximum coherence.
- Do NOT modify subagent outputs after they are written — each agent owns its document.
- PRD Digest는 Phase 1.5에서 자동 생성됨. 개별 subagent가 임의로 요약하지 말 것.
