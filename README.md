# claude-kit (v0)

A reusable Claude Code kit for PRD-driven development with a GitHub-first workflow.

## Overview

claude-kit takes a PRD (Product Requirements Document) as input and orchestrates AI agents to support the entire development lifecycle — from requirements analysis to code review and deployment.

**Core Principles:**
- **GitHub-first**: Issues and PRs are the single source of truth
- **1 Issue = 1 PR**: Each issue maps to exactly one pull request
- **`issues.md` as SSOT**: Progress and completion are tracked by Status in this file
- **Skill orchestration**: Skills feed back into each other — review findings auto-create issues, shipped code triggers test gap detection, standalone skills register in the sprint ecosystem

## Core Use Cases

### 1. Build a product from scratch
```
/brainstorm → /bizanalysis → /prd → /kickoff → /uiux → /sprint
```
Start with an idea, validate it, write a PRD, generate planning docs, design the UI, and let the team-lead auto-implement everything.

### 2. Implement a single feature
```
/implement ISSUE-001 → /review ISSUE-001 → /ship
```
Pick an issue from `issues.md`, implement it with TDD, review with security audit, and merge.

### 3. Run a full sprint
```
/sprint
```
Team-lead picks up all ready issues, implements them in parallel, reviews each PR, ships merged code, and auto-creates follow-up issues from review findings.

### 4. Fix a bug
```
/diagnose "TypeError in auth.py line 42" → /review → /ship
```
Trace the root cause, apply a minimal fix with regression test, review, and ship.

### 5. Improve test coverage
```
/testgen src/auth/
```
Scan for missing or hollow tests, generate unit/integration/E2E tests, and create a PR.

### 6. Analyze an existing codebase
```
/scan
```
Reverse-engineer docs from code: architecture, requirements, test plan, and improvement issues — then feed into `/sprint` or `/implement`.

### 7. Maintain and evolve
```
/refactor src/legacy_module.py    # Improve code structure
/migrate "Django 5.0"             # Upgrade dependencies
/devops "github-actions"          # Set up CI/CD
```

## Workflow

```
/brainstorm ──▶ /bizanalysis ──▶ /prd ──▶ /kickoff ──▶ /uiux ──▶ /sprint or /implement ──▶ /review ──▶ /ship
                                              │
                                              ├──▶ /issue (ad-hoc)
     │               │              │        │             │            │                       │            │
     ▼               ▼              ▼        ▼             ▼            ▼                       ▼            ▼
  Ideation     Business       Interactive  Requirements  Design      Code impl             Senior        Merge & deploy
  Socratic     validation     PRD writing  UX spec       philosophy  GH Issue              Minimal fix   CHANGELOG
  dialogue     Go/Pivot/No               Architecture  Design sys  PR creation            Re-run tests  STATUS update
                                           Issue plan    Wireframes  Closes #N              Security      Documentation
                                           Test plan     Prototype                          UI review     Test gap advisory

Existing codebase (no PRD):
/scan ──▶ /sprint or /implement ──▶ /review ──▶ /ship
  │
  ▼
  Reverse-engineer docs from code:
  requirements, architecture, test plan, issues
```

> `/brainstorm` and `/bizanalysis` are optional. If your idea is clear, start from `/prd`.
> `/uiux` is optional for UI projects. Backend/CLI projects go directly from `/kickoff` to `/implement`.
> `/sprint` auto-orchestrates multiple issues via team-lead. For a single issue, use `/implement` directly.
> `/scan` is for existing codebases without a PRD. It reverse-engineers planning docs from code.

### Skill Orchestration

Skills automatically feed into each other within `/sprint`:

```
implement → developer reports Discovered Findings
         → team-lead invokes planner to create follow-up issues

review   → review_notes.md with severity-classified findings
         → team-lead triages Critical/High findings → auto-creates issues

ship     → post-ship test gap scan
         → team-lead auto-triggers /testgen for uncovered files

test failure → team-lead invokes diagnostician for root cause analysis
            → diagnostician fix applied before retry

review_lessons.md → patterns with Frequency ≥ 3 + Critical/High severity
                  → team-lead creates preventive issues via planner
```

Standalone skills (`/testgen`, `/diagnose`, `/refactor`) register their work in `issues.md` when it exists, so team-lead can track all work in `sprint_state.md`.

### Decision Tree — Which skill should I use?

```
START
 │
 ├─ Have an idea but direction is unclear?
 │   └─ YES → /brainstorm → Need business validation? → /bizanalysis → /prd
 │
 ├─ No PRD yet?
 │   └─ YES → /prd
 │
 ├─ PRD exists but no planning docs?
 │   └─ YES → /kickoff PRD.md
 │
 ├─ Planning docs ready, project has UI?
 │   ├─ Web → /uiux
 │   └─ Mobile → /mobile-uiux
 │
 ├─ Want to add more issues?
 │   └─ YES → /issue "description"
 │
 ├─ Multiple issues to implement?
 │   ├─ YES → /sprint (team-lead auto-orchestrates)
 │   └─ Single issue → /implement ISSUE-001
 │
 ├─ PR is ready for review?
 │   └─ YES → /review ISSUE-001 → /ship
 │
 ├─ Bug occurred?
 │   └─ YES → /diagnose "error description"
 │
 ├─ Dependency/runtime upgrade?
 │   └─ YES → /migrate "target"
 │
 ├─ Code structure needs improvement?
 │   └─ YES → /refactor path/to/module
 │
 ├─ Tests are insufficient?
 │   └─ YES → /testgen [path] (full scan or specific path)
 │
 ├─ CI/CD, Docker, deployment setup?
 │   └─ YES → /devops "target"
 │
 └─ Existing codebase, no PRD?
     └─ YES → /scan → /sprint or /implement
```

| Skill | Description | Outputs |
|-------|-------------|---------|
| `/brainstorm [idea]` | Interactive brainstorming via Socratic dialogue | `docs/brainstorm_notes.md` |
| `/bizanalysis [idea]` | Business viability analysis with market research | `docs/business_analysis.md` |
| `/prd [path]` | Create or update a PRD via interactive conversation | `PRD.md` (or specified path) |
| `/kickoff PRD.md` | Analyze PRD and generate planning docs | `docs/requirements.md`, `docs/ux_spec.md`, `docs/architecture.md`, `issues.md`, `docs/test_plan.md`, `STATUS.md` |
| `/issue [description]` | Create a single issue from natural language + auto-update planning docs | `issues.md`, `STATUS.md`, related `docs/*.md` |
| `/uiux [PRD.md]` | Design philosophy + design system + HTML/CSS prototype | `docs/design_philosophy.md`, `docs/design_system.md`, `docs/wireframes.md`, `docs/interactions.md`, `prototype/` |
| `/mobile-uiux [PRD.md]` | Mobile design system + React Native (Expo) prototype | `docs/design_philosophy.md`, `docs/design_system_mobile.md`, `docs/wireframes_mobile.md`, `docs/interactions_mobile.md`, `prototype-mobile/` |
| `/sprint` | Auto-orchestrate multiple issues via team-lead | `docs/sprint_state.md`, `STATUS.md` |
| `/implement ISSUE-001` | Implement a single issue + create GH Issue/PR | Code, tests, PR (`Closes #N`) |
| `/review ISSUE-001` | Senior review + security audit + UI review + design audit + a11y audit on PR | `docs/review_notes.md`, `docs/ui_review_notes.md`, `docs/design_audit.md`, `docs/a11y_audit.md` |
| `/ship` | Merge PR + update docs/changelog + test gap advisory | `CHANGELOG.md`, `STATUS.md` updated |
| `/diagnose [error]` | Analyze a bug and propose a targeted fix | Diagnosis + fix |
| `/migrate [target]` | Plan and execute a migration | Migration plan + updated code/config |
| `/refactor [path]` | Improve code structure without changing behavior | Refactored code |
| `/testgen [path]` | Scan for missing/hollow tests and generate unit/integration/E2E tests | Generated tests, PR |
| `/scan` | Reverse-engineer docs from existing codebase | `docs/prd_digest.md`, `docs/requirements.md`, `docs/architecture.md`, `docs/test_plan.md`, `issues.md`, `STATUS.md` |
| `/devops [target]` | Set up CI/CD, Dockerfiles, deployment configs | Infrastructure files |
| `/careful` | Activate destructive command warnings for current session | Safety guardrail |
| `/freeze` | Block file edits outside a specified directory boundary | Safety guardrail |
| `/guard` | Activate both careful + freeze modes | Safety guardrail |

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
│   ├── agents/          # 32 agent definitions
│   ├── skills/          # 21 skills
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

### Brainstorm — Explore ideas interactively

```
/brainstorm [idea description]
```

Starts a Socratic dialogue to help you explore a vague idea, define the problem space, and converge on a concrete direction. Uses web research to investigate the existing landscape and competitors. Output: `docs/brainstorm_notes.md`.

### Business Analysis — Validate business viability

```
/bizanalysis [idea description]
```

Conducts a structured business analysis: market research, competitive landscape, SWOT analysis, and Go/Pivot/No-Go recommendation. Reads `docs/brainstorm_notes.md` if it exists for context. Output: `docs/business_analysis.md`.

### PRD — Co-write a PRD interactively

```
/prd [output-path]
```

Starts an interactive conversation to help you create or update a PRD. If the file already exists, the agent reads it, summarizes the current state, and asks what you want to change — then produces an updated version with a diff summary. If the file doesn't exist, it guides you from scratch by asking about missing sections (goals, target users, requirements, etc.). Output follows the `docs/example_prd.md` format. Default output: `PRD.md`.

### Kickoff — Generate project plan

```
/kickoff PRD.md
```

Reads the PRD and runs 6 subagents to generate planning documents:
- `requirement-analyst` → `docs/requirements.md`
- `ux-designer` → `docs/ux_spec.md`
- `architect` → `docs/architecture.md`
- `data-modeler` → `docs/data_model.md`
- `planner` → `issues.md`
- `qa-designer` → `docs/test_plan.md`

### UI/UX — Design and prototype

```
/uiux [PRD.md]
```

Requires `/kickoff` outputs. Conducts a Design Interview to establish the project's unique design direction, then performs reference research to generate a differentiated design system. Builds on `docs/ux_spec.md` and `docs/requirements.md` to produce:

1. **Design Philosophy** (`docs/design_philosophy.md`) — Named aesthetic direction with visual philosophy
2. **Design System** (`docs/design_system.md`) — Colors, typography (Google Fonts), spacing, components as CSS custom properties
3. **Wireframes** (`docs/wireframes.md`) — Screen layouts with responsive breakpoints
4. **Interaction Spec** (`docs/interactions.md`) — User flows, state machines, animations
5. **HTML/CSS Prototype** (`prototype/`) — Self-contained, opens via `file://` in any browser

The skill applies [Anthropic's frontend-design guidelines](https://claude.com/blog/improving-frontend-design-through-skills) to avoid generic "AI slop" aesthetics — no Inter fonts, no purple gradients, no cookie-cutter layouts. Every design choice is intentional and driven by the product's identity.

### Mobile UI/UX — Design and prototype for mobile

```
/mobile-uiux [PRD.md]
```

Requires `/kickoff` outputs. Like `/uiux` but for React Native (Expo) mobile apps. Conducts a Design Interview to establish the project's unique design direction, then performs reference research to generate a differentiated mobile design system. If `docs/design_philosophy.md` already exists (from `/uiux`), reuses it with user confirmation; otherwise generates it from scratch. Produces design philosophy, mobile-specific design system, wireframes with thumb zone considerations, and a runnable Expo prototype.

### Sprint — Auto-orchestrate multiple issues

```
/sprint
```

Dispatches the team-lead agent to automatically pick up ready issues from `issues.md`, implement them via `/implement`, review via `/review`, and ship via `/ship`. Loops until all issues are done or max iterations reached. Includes automated feedback loops: review findings create follow-up issues, test failures trigger diagnostician, and shipped code gets test gap detection.

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

Verifies tests pass, updates documentation, merges the PR, and reports test coverage gaps in shipped code with suggestions to run `/testgen`.

### Diagnose — Analyze and fix bugs

```
/diagnose [error description or file path]
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

### Scan — Reverse-engineer docs from existing codebase

```
/scan
```

Analyzes an existing codebase (no PRD required) and generates planning documents by running 6 scan agents:
- `codebase-scanner` — 4-pass analysis (identity, architecture, requirements, quality)
- `scan-analyst` → `docs/requirements.md` (CONFIRMED/INFERRED requirements)
- `scan-architect` → `docs/architecture.md` (as-is architecture)
- `scan-data-modeler` → `docs/data_model.md` (conditional, only if DB detected)
- `scan-qa-designer` → `docs/test_plan.md` (coverage gaps, risk matrix)
- `scan-planner` → `issues.md` (improvement issues from observations)

Output is compatible with `/sprint` and `/implement` — scan a codebase, then start working on improvement issues immediately.

### DevOps — Set up infrastructure

```
/devops [target, e.g. "github-actions", "docker", "compose"]
```

Creates or updates Dockerfiles, docker-compose configs, GitHub Actions workflows, and deployment scripts.

### Safety Guardrails

```
/careful    # Warn before destructive commands (rm -rf, git reset --hard, etc.)
/freeze     # Block edits outside a specified directory
/guard      # Both careful + freeze combined
```

Session-scoped safety modes for working in sensitive environments or scoping edits to a specific module.

## Agents

32 specialized agents with optimized model assignments (opus for judgment/creativity, sonnet for structured extraction):

| Agent | Model | Role | Tools |
|-------|-------|------|-------|
| `brainstormer` | opus | Interactive brainstorming facilitator | Read, Glob, Grep, Write, Edit, WebSearch, WebFetch |
| `business-analyst` | opus | Business viability analysis + market research | Read, Glob, Grep, Write, Edit, WebSearch, WebFetch |
| `prd-writer` | opus | Interactive PRD co-writing via conversation | Read, Glob, Grep, Write, Edit |
| `requirement-analyst` | sonnet | Extract requirements from PRD | Read, Glob, Grep, Write, Edit |
| `ux-designer` | opus | Create UX spec (v0: spec only) | Read, Glob, Grep, Write, Edit |
| `uiux-developer` | opus | Design philosophy + design system + HTML/CSS prototype | Read, Glob, Grep, Write, Edit, Bash, WebSearch, WebFetch |
| `mobile-uiux-developer` | opus | Mobile design system + React Native (Expo) prototype | Read, Glob, Grep, Write, Edit, Bash, WebSearch, WebFetch |
| `desktop-uiux-developer` | opus | Desktop design system + Electron/Tauri prototype | Read, Glob, Grep, Write, Edit, Bash, WebSearch, WebFetch |
| `copywriter` | opus | Write all user-facing copy (labels, errors, CTAs) | Read, Glob, Grep, Write, Edit |
| `architect` | opus | Design software architecture | Read, Glob, Grep, Write, Edit |
| `data-modeler` | opus | Design schemas, indexes, migrations, query patterns | Read, Glob, Grep, Write, Edit |
| `planner` | opus | Break work into issues + convert review findings to issues | Read, Glob, Grep, Write, Edit |
| `issue-writer` | sonnet | Natural language → single issue creation + docs update | Read, Glob, Grep, Write, Edit, Bash |
| `qa-designer` | opus | Design test strategy and cases | Read, Glob, Grep, Write, Edit |
| `team-lead` | opus | Sprint orchestrator — dispatch agents, manage issues, triage review findings | Read, Glob, Grep, Write, Edit, Bash, Task |
| `developer` | opus | Implement code + GH Issue/PR + report discovered findings | Read, Glob, Grep, Write, Edit, Bash |
| `test-generator` | opus | Generate missing unit/integration/E2E tests | Read, Glob, Grep, Write, Edit, Bash |
| `reviewer` | opus | Senior code review + security audit | Read, Glob, Grep, Edit, Bash, Write |
| `ui-reviewer` | sonnet | UI review — state coverage, copy, tokens, a11y | Read, Glob, Grep, Edit, Write |
| `design-auditor` | sonnet | Design system audit — token consistency, component completeness | Read, Glob, Grep, Edit, Write |
| `a11y-auditor` | sonnet | WCAG 2.1 AA accessibility audit | Read, Glob, Grep, Edit, Write |
| `documenter` | sonnet | Maintain documentation | Read, Glob, Grep, Write, Edit |
| `diagnostician` | opus | Analyze bugs and propose targeted fixes | Read, Glob, Grep, Write, Edit, Bash |
| `migrator` | opus | Plan and execute migrations | Read, Glob, Grep, Write, Edit, Bash |
| `refactorer` | opus | Improve code structure without changing behavior | Read, Glob, Grep, Write, Edit, Bash |
| `devops` | sonnet | Set up CI/CD pipelines and deployment infra | Read, Glob, Grep, Write, Edit, Bash |
| `codebase-scanner` | sonnet | Analyze existing codebase in 4 passes (identity, architecture, requirements, quality) | Read, Glob, Grep |
| `scan-analyst` | sonnet | Reverse-engineer requirements from existing code and tests | Read, Glob, Grep, Write, Edit |
| `scan-architect` | sonnet | Document as-is architecture from scan context | Read, Glob, Grep, Write, Edit |
| `scan-data-modeler` | sonnet | Extract data models from ORM/migration/schema declarations | Read, Glob, Grep, Write, Edit |
| `scan-qa-designer` | sonnet | Assess existing test coverage and identify gaps | Read, Glob, Grep, Write, Edit |
| `scan-planner` | opus | Generate improvement issues from scan observations | Read, Glob, Grep, Write, Edit |

## Project Structure

```
claude-dev-kit/
├── agents/                  # Agent role definitions (32)
├── skills/                  # Workflow skills (21)
│   ├── brainstorm/SKILL.md
│   ├── bizanalysis/SKILL.md
│   ├── prd/SKILL.md
│   ├── kickoff/SKILL.md
│   ├── issue/SKILL.md
│   ├── uiux/SKILL.md
│   ├── mobile-uiux/SKILL.md
│   ├── desktop-uiux/SKILL.md
│   ├── scan/SKILL.md        # Reverse-engineer docs from existing codebase
│   ├── sprint/SKILL.md
│   ├── implement/SKILL.md
│   ├── review/SKILL.md
│   ├── ship/SKILL.md
│   ├── diagnose/SKILL.md
│   ├── migrate/SKILL.md
│   ├── refactor/SKILL.md
│   ├── testgen/SKILL.md
│   ├── devops/SKILL.md
│   ├── careful/SKILL.md     # Safety guardrail: destructive command warnings
│   ├── freeze/SKILL.md      # Safety guardrail: edit boundary enforcement
│   └── guard/SKILL.md       # Safety guardrail: careful + freeze combined
├── templates/               # Document templates (24)
├── project/                 # Files installed into target project
│   └── .claude/
│       ├── hooks/agent_state.py
│       └── settings.snippet.json
├── scripts/                 # Install and utility scripts
│   ├── install_user.sh
│   ├── install_project.sh
│   ├── ensure_gh.sh
│   ├── ensure_permissions.py
│   ├── merge_settings.py
│   ├── gen_skills.py        # Template → SKILL.md generator
│   ├── preambles.py         # Tiered preamble injection
│   ├── validate_issues.py   # issues.md format validator
│   ├── verify_checkpoint.py # Skill phase gate verification
│   ├── worktree.sh          # git worktree lifecycle (create/path/remove/root)
│   └── flock_edit.sh        # file-lock wrapper for shared files
├── user/                    # User-level tools
│   └── kit/bin/cc-statusline.py
├── tests/                   # Tests
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

Tests cover merge logic, agent state hooks, worktree lifecycle, file locking, integration checks (frontmatter, templates, cross-references), scan pipeline validation, skill generation, preamble injection, safety guardrails, and more.

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

- macOS/Linux only
- Default architecture preference: Django monolith + Postgres
- Model mix: opus (20 agents) for judgment/creativity, sonnet (12 agents) for structured extraction

## License

MIT
