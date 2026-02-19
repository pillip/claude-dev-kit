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
| `/review ISSUE-001` | Senior review on PR + minimal fixes | `docs/review_notes.md` |
| `/ship` | Merge PR + update docs/changelog | `CHANGELOG.md`, `STATUS.md` updated |

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
│   ├── agents/          # 9 agent definitions
│   ├── skills/          # 5 skills (prd, kickoff, implement, review, ship)
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

Performs a senior review on the PR. Applies only minimal fixes; larger changes are proposed as follow-up issues.

### Ship — Deploy

```
/ship
```

Verifies tests pass, updates documentation, and merges the PR.

## Agents

9 specialized agents, each with a defined role and tool permissions:

| Agent | Role | Tools |
|-------|------|-------|
| `prd-writer` | Interactive PRD co-writing via conversation | Read, Glob, Grep, Write, Edit |
| `requirement-analyst` | Extract requirements from PRD | Read, Glob, Grep, Write, Edit |
| `ux-designer` | Create UX spec (v0: spec only) | Read, Glob, Grep, Write, Edit |
| `architect` | Design software architecture | Read, Glob, Grep, Write, Edit |
| `planner` | Break work into issues | Read, Glob, Grep, Write, Edit |
| `qa-designer` | Design test strategy and cases | Read, Glob, Grep, Write, Edit |
| `developer` | Implement code + GH Issue/PR | Read, Glob, Grep, Write, Edit, Bash |
| `reviewer` | Senior code review | Read, Glob, Grep, Edit, Bash, Write |
| `documenter` | Maintain documentation | Read, Glob, Grep, Write, Edit |

## Project Structure

```
claude-dev-kit/
├── agents/                  # Agent role definitions (9)
│   ├── prd-writer.md
│   ├── requirement-analyst.md
│   ├── ux-designer.md
│   ├── architect.md
│   ├── planner.md
│   ├── qa-designer.md
│   ├── developer.md
│   ├── reviewer.md
│   └── documenter.md
├── skills/                  # Workflow skills (5)
│   ├── prd/SKILL.md
│   ├── kickoff/SKILL.md
│   ├── implement/SKILL.md
│   ├── review/SKILL.md
│   └── ship/SKILL.md
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
│   └── merge_settings.py
├── user/                    # User-level tools
│   └── kit/bin/cc-statusline.py
├── tests/                   # Tests
│   ├── test_merge_settings.py
│   └── test_agent_state.py
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

## Updating

Pull the latest submodule changes and re-run the project install script:

```bash
cd .claude-kit
git pull origin main
cd ..
bash .claude-kit/scripts/install_project.sh
```

## v0 Scope & Limitations

- UX spec generation only (no UI code generation)
- macOS/Linux only
- Default architecture preference: Django monolith + Postgres
- All subagents use model: `opus`

## License

MIT
