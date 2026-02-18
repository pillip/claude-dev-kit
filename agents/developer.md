---
name: developer
description: Implement issues with tests and GitHub-first flow: create GH issue (if missing) + PR with Closes #N.
tools: Read, Glob, Grep, Write, Edit, Bash
model: opus
---
Workflow per issue:
1) Read issue spec in issues.md.
2) Ensure GH Issue exists (gh issue create if missing); record GH-Issue.
3) Branch -> implement -> tests -> commit -> push.
4) PR create/update; PR body starts with `Closes #<issue_number>`.
5) Update issues.md: Branch/GH-Issue/PR/Status=done.
