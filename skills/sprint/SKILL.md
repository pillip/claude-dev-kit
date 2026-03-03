---
name: sprint
description: issues.md의 모든 이슈를 자율적으로 implement → review → ship 하며, 동적 이슈 관리를 수행합니다.
argument-hint: [--parallel N] [--max-iterations N]
allowed-tools: Task, Read, Glob, Grep, Write, Edit, Bash
---

## Pre-conditions
1) `issues.md` must exist with at least one issue in `backlog` status.
2) `gh auth status` must succeed.
3) All planning docs should exist (docs/architecture.md, etc.) — warn if missing.

## Arguments
- `--parallel N`: Max parallel issues (default: 3)
- `--max-iterations N`: Max loop iterations (default: 20)

## Algorithm

1) Validate pre-conditions:
   - Read `issues.md` — if no backlog issues, report "nothing to sprint" and stop.
   - Run `gh auth status` — if fails, stop and instruct user to authenticate.
   - Check for planning docs (architecture.md, requirements.md) — warn if missing but continue.

2) Check for existing sprint state:
   - If `docs/sprint_state.md` exists with Status=running, ask user: resume or start fresh?
   - If resuming, pass existing state to team-lead.
   - If fresh, delete old sprint_state.md.

3) Gather context for team-lead:
   - `issues.md` — full content
   - `docs/sprint_state.md` — if resuming
   - `docs/review_lessons.md` — if exists
   - `docs/architecture.md` — if exists
   - `docs/data_model.md` — if exists
   - Parse --parallel and --max-iterations from arguments

4) Invoke team-lead agent via Task tool:
   - Pass all gathered context as prompt content (not file paths)
   - Include parsed arguments (parallel count, max iterations)
   - Include: "You are the team-lead agent. Follow your agent guidelines precisely."

5) On team-lead completion:
   - Read final `docs/sprint_state.md` for summary
   - Report sprint results to user:
     - Issues completed
     - Issues remaining
     - Issues escalated
     - New issues discovered

## Error Handling
- If team-lead agent fails (Task tool returns error): report error and current sprint_state.md status.
- If pre-conditions fail: stop with clear instructions on how to fix.
- Sprint state file ensures progress is never lost — user can re-run `/sprint` to resume.

## Rollback
- Sprint is composed of individual implement→review→ship cycles, each with their own rollback.
- If sprint must be fully abandoned: issues.md still reflects accurate status per issue.
- Delete `docs/sprint_state.md` to reset sprint state.
