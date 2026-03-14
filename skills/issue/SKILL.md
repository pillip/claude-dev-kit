---
name: issue
description: 자연어 설명으로 단일 이슈를 생성하고 관련 planning docs를 자동 업데이트합니다.
argument-hint: [이슈 설명]
disable-model-invocation: false
allowed-tools: Task, Read, Glob, Grep, Write, Edit, Bash
---

## Algorithm

### Phase 1 — Context Gathering

1) Read `$ARGUMENTS`. If empty, ask the user for a description and stop.
2) Read `issues.md`. If not found, tell the user to run `/kickoff` first and stop.
3) Parse the highest issue number from `issues.md` using `### ISSUE-(\d+):` regex. Next issue number = max + 1.
4) Read the following docs in **parallel** (skip any that don't exist):
   - `docs/prd_digest.md`
   - `docs/requirements.md`
   - `docs/ux_spec.md`
   - `docs/architecture.md`
   - `docs/data_model.md`
   - `docs/test_plan.md`

If none of the planning docs exist, warn the user but proceed with `issues.md` + `STATUS.md` only.

### Phase 2 — Doc Update Detection

5) Analyze the natural-language description against existing planning docs to determine which docs need updating:
   - `issues.md` — always
   - `STATUS.md` — always
   - `docs/requirements.md` — when the description introduces requirements not covered by existing FRs/NFRs
   - `docs/ux_spec.md` — when the description involves UI elements, screens, user flows, or interactions
   - `docs/architecture.md` — when the description involves new modules, services, APIs, or infrastructure changes
   - `docs/data_model.md` — when the description involves new entities, fields, or schema changes
   - `docs/test_plan.md` — when the description introduces new test flows or critical paths

6) Present the analysis to the user:
   - Assigned issue number (e.g., ISSUE-NNN)
   - List of docs to update with rationale for each
   - Wait for user confirmation before proceeding.

### Phase 3 — Issue Creation & Doc Updates

7) Invoke the `issue-writer` agent via a single Task tool call. Include the following in the prompt:
   - The natural-language description
   - The assigned issue number
   - The list of docs to update (with rationale for each)
   - Full content of `issues.md` (for existing issue context)
   - Full content of each planning doc marked for update
   - Full content of `docs/prd_digest.md` (for PRD-Ref mapping)
   - Instruction: use `flock_edit.sh` for `issues.md` and `STATUS.md`

### Phase 4 — Validation & Report

8) Run `python3 scripts/validate_issues.py issues.md`.
   - If violations are found: re-invoke the issue-writer agent once with the violation list to fix them. Then re-validate.
   - If violations remain after retry: log warnings and proceed.

9) Report to the user:
   - Issue number and title
   - List of updated docs
   - Validation result (pass/warnings)

10) Suggest next step: `/implement ISSUE-NNN`

## Error Handling

- `$ARGUMENTS` is empty → ask the user for a description, stop.
- `issues.md` does not exist → instruct user to run `/kickoff` first, stop.
- All planning docs missing → update only `issues.md` + `STATUS.md`, warn the user.
- issue-writer agent fails → retry once. If it fails again, report the error and stop.

## Rollback

- This skill is additive (appends to existing files). If partially completed, the user can manually remove the last issue block from `issues.md` and revert doc changes via git.

## Shared Registry Files
**IMPORTANT**: Never commit `issues.md`, `STATUS.md`, or `CHANGELOG.md` to the feature branch.
These are registry files managed only on main. Always use `$ROOT/` path with `flock_edit.sh`.
