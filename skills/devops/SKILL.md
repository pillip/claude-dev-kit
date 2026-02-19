---
name: devops
description: Set up or update CI/CD pipelines, Dockerfiles, and deployment configs, then create a GH Issue + PR.
argument-hint: [target, e.g. "github-actions", "docker", "compose"]
disable-model-invocation: false
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
---
Steps:
1) Ensure `gh` authenticated (`gh auth status`).
2) Identify the target from $ARGUMENTS (github-actions, docker, compose, or general).
3) Read the current project structure, tech stack, and existing infra configs.
4) Propose a CI/CD or infrastructure setup appropriate for the project.
5) After user approval, create branch: `devops/<slug>` (e.g., `devops/github-actions-ci`).
6) Create or update the relevant files:
   - Dockerfile / docker-compose.yml
   - .github/workflows/*.yml
   - Scripts (build, deploy, seed, etc.)
7) Validate locally where possible (e.g., docker build, syntax checks).
8) Update README or deployment docs with setup and usage instructions.
9) Create GH Issue:
    - `gh issue create --title "devops: <concise infrastructure description>" --body "<body>"`
    - Body must include: what was set up/changed, configuration details, validation results, and usage instructions.
10) Commit + push.
11) Create PR:
    - `gh pr create --title "devops: <concise description>" --body "Closes #<issue_number>\n\n<details>"`
12) Report the PR URL to the user — continue with `/review` and `/ship`.

## Error Handling
- If `gh auth status` fails: stop and instruct the user to run `gh auth login`.
- If the target is ambiguous: ask the user to clarify what they need (CI, containerization, deployment, etc.).
- If a build or validation fails: report the error and suggest a fix. Do NOT push broken configs.

## Rollback
- If failure occurs after branch creation but before PR:
  1. `git checkout main`
  2. `git branch -D <branch>` (local cleanup)
  3. `git push origin --delete <branch>` (remote cleanup, if pushed)
- If failure occurs after PR creation: `gh pr close <pr_number>` then clean up branch.

## Guidelines
- Follow least-privilege for secrets and permissions.
- Use multi-stage Docker builds to minimize image size.
- Cache dependencies in CI to speed up builds.
- Pin versions for reproducibility.
- Never hardcode secrets.
