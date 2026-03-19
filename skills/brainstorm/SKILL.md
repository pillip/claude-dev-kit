---
name: brainstorm
description: Explores ideas and defines problems through free-form conversation. Use before /prd when direction is unclear.
argument-hint: [output file path, default docs/brainstorm_notes.md]
disable-model-invocation: false
allowed-tools: Read, Glob, Grep, Write, Edit, WebSearch, WebFetch
---
Steps:
1) Determine the output path ($ARGUMENTS or `docs/brainstorm_notes.md`).
2) Check if the file already exists at that path.

### If the file does NOT exist (New Session):
3a) Ask the user to freely describe their idea, problem, or direction — anything goes.
4a) **Discovery phase**: Explore the problem space with Socratic questions:
    - Who has this problem? Why does it matter?
    - What solutions exist today? What are their limitations?
    - What does success look like? What constraints exist?
    Ask 1–2 questions at a time. Do not overwhelm.
5a) **Ideation phase**: Once the problem is clear, propose 2–3 solution directions with brief pros/cons for each. Help the user narrow down.
6a) Synthesize findings into the brainstorm notes format (Problem Space, Existing Landscape, Idea Candidates, Decisions).

### If the file DOES exist (Continue Session):
3b) Read the existing notes and present a brief recap.
4b) Ask the user which section or direction they want to develop further.
5b) Repeat Discovery/Ideation as needed for that area.
6b) Merge new insights into the existing notes.

### Common (both modes):
7) Present the draft to the user and incorporate feedback.
8) Save the final notes to the output path.
9) Inform the user they can run `/bizanalysis` next to validate business viability, or `/prd` to go straight to PRD creation — brainstorm notes will be automatically used as context in both.

## Error Handling
- If the output path is not writable: report the error and ask for an alternative path.

## Quality Criteria

**NEVER:**
- Invent problems the user hasn't mentioned — ask instead
- Ask more than 2 questions at a time — keep it conversational
- Jump to solutions before the problem space is understood
- Steer toward a single direction — always present alternatives

**INSTEAD:**
- Mirror the user's words and terminology
- Propose concrete examples to spark thinking
- Clearly separate problem exploration from solution exploration
- Use "what if..." prompts when the user seems stuck

## Guidelines
- This is an interactive, conversational skill — engage naturally.
- If the user says "that's enough" or similar, synthesize the best notes possible with available information.
- After saving, suggest next step: `/prd` to create a PRD using the brainstorm notes as context.
