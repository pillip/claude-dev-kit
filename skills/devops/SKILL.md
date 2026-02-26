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
5) After user approval, create worktree for the branch:
   ```bash
   WT="$(bash scripts/worktree.sh create devops/<slug>)"
   ```
   All subsequent file operations happen inside `$WT/`.
6) Create or update the relevant files inside `$WT/`:
   - Dockerfile / docker-compose.yml
   - .github/workflows/*.yml
   - Scripts (build, deploy, seed, etc.)
7) Validate locally where possible (e.g., docker build, syntax checks).
8) Update README or deployment docs with setup and usage instructions inside `$WT/`.
9) Create GH Issue:
    - `gh issue create --title "devops: <concise infrastructure description>" --body "<body>"`
    - Body must include: what was set up/changed, configuration details, validation results, and usage instructions.
10) Commit + push (from `$WT/`).
11) Create PR:
    - `gh pr create --title "devops: <concise description>" --body "Closes #<issue_number>\n\n<details>"`
12) Report the PR URL to the user — continue with `/review` and `/ship`.

## Error Handling
- If `gh auth status` fails: stop and instruct the user to run `gh auth login`.
- If the target is ambiguous: ask the user to clarify what they need (CI, containerization, deployment, etc.).
- If a build or validation fails: report the error and suggest a fix. Do NOT push broken configs.

## Rollback
- **CRITICAL**: `cd` and `remove` MUST run in a single shell command (`&&`).
  A child process `cd` cannot change the parent shell's CWD — separate calls
  leave the shell in a deleted directory, breaking all subsequent commands.
- If failure occurs after worktree creation but before PR:
  1. `cd "$(bash scripts/worktree.sh root)" && bash scripts/worktree.sh remove <branch>`
  2. `git push origin --delete <branch>` (remote cleanup, if pushed)
- If failure occurs after PR creation: `gh pr close <pr_number>` then clean up worktree and branch as above.

## Shared Registry Files
**IMPORTANT**: Never commit `issues.md`, `STATUS.md`, or `CHANGELOG.md` to the feature branch.
These are registry files managed only on main. Always use `$ROOT/` path with `flock_edit.sh`.

## Guidelines
- Follow least-privilege for secrets and permissions — minimum scope needed.
- Use multi-stage Docker builds: build stage with dev deps → runtime stage with production deps only.
- Cache aggressively: dependency layers in Docker, pip/uv cache in CI, action caches.
- Pin every version: base images (`python:3.11.9-slim`), actions (`actions/checkout@v4`), dependencies.
- Never hardcode secrets — always use environment variables or secret stores.
- Add health checks to every service: HTTP endpoint, TCP check, or command-based.
- Test infrastructure changes locally before pushing: `docker build`, `docker compose up`, `act` for GitHub Actions.
