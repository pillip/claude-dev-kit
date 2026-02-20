# claude-kit (v0)

A reusable Claude Code kit for PRD-driven development with a GitHub-first workflow.

## Overview

claude-kit takes a PRD (Product Requirements Document) as input and orchestrates AI agents to support the entire development lifecycle — from requirements analysis to code review and deployment.

**Core Principles:**
- **GitHub-first**: Issues and PRs are the single source of truth
- **1 Issue = 1 PR**: Each issue maps to exactly one pull request
- **`issues.md` as SSOT**: Progress and completion are tracked by Status in this file

## Workflow

```
Idea ──▶ /prd ──▶ /kickoff ──▶ /implement ──▶ /review ──▶ /ship
          │        │              │              │            │
          ▼        ▼              ▼              ▼            ▼
     Interactive  Requirements  Code impl      Senior        Merge & deploy
     PRD writing  UX spec       GH Issue       Minimal fix   CHANGELOG
                  Architecture  PR creation    Re-run tests  STATUS update
                  Issue breakdown Closes #N
                  Test plan
```

| Skill | Description | Outputs |
|-------|-------------|---------|
| `/prd [path]` | Create or update a PRD via interactive conversation | `PRD.md` (or specified path) |
| `/kickoff PRD.md` | Analyze PRD and generate planning docs | `docs/requirements.md`, `docs/ux_spec.md`, `docs/architecture.md`, `issues.md`, `docs/test_plan.md`, `STATUS.md` |
| `/implement ISSUE-001` | Implement a single issue + create GH Issue/PR | Code, tests, PR (`Closes #N`) |
| `/review ISSUE-001` | Senior review + security audit on PR | `docs/review_notes.md` |
| `/ship` | Merge PR + update docs/changelog | `CHANGELOG.md`, `STATUS.md` updated |
| `/debug [error]` | Analyze a bug and propose a targeted fix | Diagnosis + fix |
| `/migrate [target]` | Plan and execute a migration | Migration plan + updated code/config |
| `/refactor [path]` | Improve code structure without changing behavior | Refactored code |
| `/devops [target]` | Set up CI/CD, Dockerfiles, deployment configs | Infrastructure files |

## Requirements

- macOS / Linux
- Python 3.11+
- Git
- [GitHub CLI](https://cli.github.com/) (`gh`) — authenticated

## Installation

claude-kit is installed into a service repo as a **git submodule**.

### 1. Add the submodule

```bash
cd your-service-repo
git submodule add git@github.com:pillip/claude-dev-kit.git .claude-kit
```

### 2. Install user tools

Installs the status line script to `~/.claude/kit/bin/`. Run once per machine.

```bash
bash .claude-kit/scripts/install_user.sh
```

### 3. Install into project

Copies agents, skills, hooks, and settings into the project's `.claude/` directory.

```bash
bash .claude-kit/scripts/install_project.sh
```

After installation:

```
your-service-repo/
├── .claude/
│   ├── agents/          # 13 agent definitions
│   ├── skills/          # 9 skills
│   ├── hooks/           # agent_state.py (agent state tracking)
│   └── settings.json    # Status line + hook config (auto-merged)
├── .claude-kit/         # submodule (source)
└── ...
```

### 4. Verify gh authentication

```bash
gh auth status
```

If not authenticated, run `gh auth login`.

## Usage

### PRD — Co-write a PRD interactively

```
/prd [output-path]
```

Starts an interactive conversation to help you create or update a PRD. If the file already exists, the agent reads it, summarizes the current state, and asks what you want to change — then produces an updated version with a diff summary. If the file doesn't exist, it guides you from scratch by asking about missing sections (goals, target users, requirements, etc.). Output follows the `docs/example_prd.md` format. Default output: `PRD.md`.

### Kickoff — Generate project plan

```
/kickoff PRD.md
```

Reads the PRD and runs 5 subagents to generate planning documents:
- `requirement-analyst` → `docs/requirements.md`
- `ux-designer` → `docs/ux_spec.md`
- `architect` → `docs/architecture.md`
- `planner` → `issues.md`
- `qa-designer` → `docs/test_plan.md`

### Implement — Build an issue

```
/implement ISSUE-001
```

1. Reads issue spec from `issues.md`
2. Creates GH Issue if missing
3. Creates branch → implements → tests → commits → pushes
4. Creates PR with `Closes #<issue_number>` in body
5. Updates `issues.md` metadata

### Review — Code review

```
/review ISSUE-001
```

Performs a senior code review with an integrated security audit. Checks correctness, maintainability, and complexity alongside OWASP Top 10 vulnerabilities, dependency CVEs, and hardcoded secrets. Outputs `docs/review_notes.md` with **Code Review** and **Security Findings** sections. Applies only minimal fixes; larger changes are proposed as follow-up issues.

### Ship — Deploy

```
/ship
```

Verifies tests pass, updates documentation, and merges the PR.

### Debug — Analyze and fix bugs

```
/debug [error description or file path]
```

Traces an error from stack trace or reproduction steps back to the root cause, proposes a minimal fix, and runs tests to confirm no regressions.

### Migrate — Upgrade dependencies or runtime

```
/migrate [target, e.g. "Django 5.0" or "Python 3.12"]
```

Scans the codebase for impact, generates a step-by-step migration plan with rollback instructions, and applies changes incrementally with test verification.

### Refactor — Improve code structure

```
/refactor [file or module path]
```

Identifies code smells, proposes prioritized refactorings, and applies them one at a time while running tests after each step. Never changes observable behavior.

### DevOps — Set up infrastructure

```
/devops [target, e.g. "github-actions", "docker", "compose"]
```

Creates or updates Dockerfiles, docker-compose configs, GitHub Actions workflows, and deployment scripts.

## Agents

13 specialized agents, each with a defined role and tool permissions:

| Agent | Role | Tools |
|-------|------|-------|
| `prd-writer` | Interactive PRD co-writing via conversation | Read, Glob, Grep, Write, Edit |
| `requirement-analyst` | Extract requirements from PRD | Read, Glob, Grep, Write, Edit |
| `ux-designer` | Create UX spec (v0: spec only) | Read, Glob, Grep, Write, Edit |
| `architect` | Design software architecture | Read, Glob, Grep, Write, Edit |
| `planner` | Break work into issues | Read, Glob, Grep, Write, Edit |
| `qa-designer` | Design test strategy and cases | Read, Glob, Grep, Write, Edit |
| `developer` | Implement code + GH Issue/PR | Read, Glob, Grep, Write, Edit, Bash |
| `reviewer` | Senior code review + security audit | Read, Glob, Grep, Edit, Bash, Write |
| `documenter` | Maintain documentation | Read, Glob, Grep, Write, Edit |
| `debugger` | Analyze bugs and propose targeted fixes | Read, Glob, Grep, Write, Edit, Bash |
| `migrator` | Plan and execute migrations | Read, Glob, Grep, Write, Edit, Bash |
| `refactorer` | Improve code structure without changing behavior | Read, Glob, Grep, Write, Edit, Bash |
| `devops` | Set up CI/CD pipelines and deployment infra | Read, Glob, Grep, Write, Edit, Bash |

## Project Structure

```
claude-dev-kit/
├── agents/                  # Agent role definitions (13)
│   ├── prd-writer.md
│   ├── requirement-analyst.md
│   ├── ux-designer.md
│   ├── architect.md
│   ├── planner.md
│   ├── qa-designer.md
│   ├── developer.md
│   ├── reviewer.md
│   ├── documenter.md
│   ├── debugger.md
│   ├── migrator.md
│   ├── refactorer.md
│   └── devops.md
├── skills/                  # Workflow skills (9)
│   ├── prd/SKILL.md
│   ├── kickoff/SKILL.md
│   ├── implement/SKILL.md
│   ├── review/SKILL.md
│   ├── ship/SKILL.md
│   ├── debug/SKILL.md
│   ├── migrate/SKILL.md
│   ├── refactor/SKILL.md
│   └── devops/SKILL.md
├── templates/               # Document templates
│   ├── requirements.md
│   ├── ux_spec.md
│   ├── architecture.md
│   ├── issues.md
│   └── test_plan.md
├── project/                 # Files installed into target project
│   └── .claude/
│       ├── hooks/agent_state.py
│       └── settings.snippet.json
├── scripts/                 # Install and utility scripts
│   ├── install_user.sh
│   ├── install_project.sh
│   ├── ensure_gh.sh
│   ├── merge_settings.py
│   ├── worktree.sh          # git worktree lifecycle (create/path/remove/root)
│   └── flock_edit.sh        # file-lock wrapper for shared files
├── user/                    # User-level tools
│   └── kit/bin/cc-statusline.py
├── tests/                   # Tests
│   ├── test_merge_settings.py
│   ├── test_agent_state.py
│   ├── test_worktree.py
│   └── test_flock_edit.py
├── docs/                    # Kit documentation
│   └── PRD_agent_system_v0.md
└── README.md
```

## Status Line

After installation, the Claude Code status line displays:

```
claude-opus-4-6 | agents:ux-designer,developer | tool:Write | tok:45230/200000 | $0.123
```

Shows the current model, active agents, last tool used, token usage, and cumulative cost.

## Testing

```bash
pytest tests/ -q
```

Current test coverage:
- `test_merge_settings.py` — JSON deep merge logic
- `test_agent_state.py` — Agent state hook lifecycle
- `test_worktree.py` — git worktree create/path/remove/root
- `test_flock_edit.py` — file-lock wrapper serialization

## Updating

Pull the latest submodule changes and re-run the project install script:

```bash
cd .claude-kit
git pull origin main
cd ..
bash .claude-kit/scripts/install_project.sh
```

## Concurrency

Multiple skill sessions (e.g., two `/implement` runs on different issues) can
execute in parallel thanks to **git worktrees**. Each session gets its own
working directory under `.worktrees/`, so branches never collide.

```bash
# Worktree lifecycle (used internally by skills)
bash scripts/worktree.sh create issue/ISSUE-001-login   # → .worktrees/issue-ISSUE-001-login/
bash scripts/worktree.sh path   issue/ISSUE-001-login   # print path
bash scripts/worktree.sh remove issue/ISSUE-001-login   # cleanup
bash scripts/worktree.sh root                            # main repo root
```

Shared files (`issues.md`, `STATUS.md`) live in the main repo root and are
protected by an exclusive file lock during read-modify-write:

```bash
ROOT="$(bash scripts/worktree.sh root)"
bash scripts/flock_edit.sh "$ROOT/issues.md" -- bash -c 'echo "update" >> "$ROOT/issues.md"'
```

`flock_edit.sh` uses `flock(1)` when available, falling back to `mkdir`-based
locking on macOS.

## v0 Scope & Limitations

- UX spec generation only (no UI code generation)
- macOS/Linux only
- Default architecture preference: Django monolith + Postgres
- All subagents use model: `opus`

## License

MIT
