---
name: prd
description: 자유 대화를 통해 PRD를 함께 작성합니다.
argument-hint: [출력 파일 경로, 기본값 PRD.md]
disable-model-invocation: false
allowed-tools: Read, Glob, Grep, Write, Edit
---
Steps:
1) Determine the output path ($ARGUMENTS or PRD.md).
2) Check if the file already exists at that path.
3) Read `docs/example_prd.md` to load the reference PRD format.

### If the file does NOT exist (New PRD):
4a) Ask the user to freely describe their product idea.
5a) Analyze the input and identify missing PRD sections (Background, Goals, Target User, User Stories, Functional Requirements, Non-functional Requirements, Out of Scope, Success Metrics, Technical Notes).
6a) Ask clarifying questions conversationally — one or two gaps at a time.
7a) When enough information is gathered, generate a PRD draft following the example format and present it to the user.

### If the file DOES exist (Update PRD):
4b) Read the existing PRD and present a brief summary to the user.
5b) Ask the user what they want to change, add, or remove.
6b) Identify which sections are affected and flag any new gaps or inconsistencies.
7b) Ask clarifying questions about ambiguous changes.
8b) Generate the updated PRD, preserving unchanged sections. Highlight what changed (added/modified/removed).

### Common (both modes):
8) Incorporate user feedback and iterate until the user approves.
9) Save the final PRD to the output path.
10) Inform the user they can run `/kickoff <path>` to generate planning documents from the PRD.

## Error Handling
- If `docs/example_prd.md` is not found: warn the user and use a reasonable default PRD structure.
- If the output path is not writable: report the error and ask for an alternative path.

## Guidelines
- This is an interactive, conversational skill — engage naturally.
- Do NOT invent requirements the user hasn't mentioned; ask instead.
- Mark thin sections with `<!-- TODO: flesh out -->` if the user wants to finalize early.
