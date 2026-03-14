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
/brainstorm ──▶ /bizanalysis ──▶ /prd ──▶ /kickoff ──▶ /uiux ──▶ /sprint or /implement ──▶ /review ──▶ /ship
                                              │
                                              ├──▶ /issue (ad-hoc)
     │               │              │        │             │            │                       │            │
     ▼               ▼              ▼        ▼             ▼            ▼                       ▼            ▼
  Ideation     Business       Interactive  Requirements  Design      Code impl             Senior        Merge & deploy
  Socratic     validation     PRD writing  UX spec       philosophy  GH Issue              Minimal fix   CHANGELOG
  dialogue     Go/Pivot/No               Architecture  Design sys  PR creation            Re-run tests  STATUS update
                                           Issue plan    Wireframes  Closes #N              Security      Documentation
                                           Test plan     Prototype                          UI review
```

> `/brainstorm`과 `/bizanalysis`는 선택 단계입니다. 아이디어가 명확하면 `/prd`부터 시작할 수 있습니다.
> `/uiux`는 UI가 있는 프로젝트에서 선택적으로 사용합니다. UI가 없는 백엔드/CLI 프로젝트는 `/kickoff` → `/implement`로 바로 진행합니다.
> `/sprint`은 여러 이슈를 team-lead가 자동 오케스트레이션합니다. 단일 이슈는 `/implement`로 직접 진행합니다.

### Decision Tree — Which skill should I use?

```
START
 │
 ├─ 아이디어만 있고 방향이 불확실?
 │   └─ YES → /brainstorm → 사업성 검증 필요? → /bizanalysis → /prd
 │
 ├─ PRD가 없다?
 │   └─ YES → /prd
 │
 ├─ PRD는 있지만 planning docs가 없다?
 │   └─ YES → /kickoff PRD.md
 │
 ├─ Planning docs 완료, UI가 있는 프로젝트?
 │   ├─ 웹 → /uiux
 │   └─ 모바일 → /mobile-uiux
 │
 ├─ 이슈를 추가로 만들고 싶다?
 │   └─ YES → /issue "설명"
 │
 ├─ 구현할 이슈가 여러 개?
 │   ├─ YES → /sprint (team-lead가 자동 오케스트레이션)
 │   └─ 단일 이슈 → /implement ISSUE-001
 │
 ├─ PR이 올라왔다?
 │   └─ YES → /review ISSUE-001 → /ship
 │
 ├─ 버그가 발생했다?
 │   └─ YES → /diagnose "에러 설명"
 │
 ├─ 의존성/런타임 업그레이드?
 │   └─ YES → /migrate "target"
 │
 ├─ 코드 구조 개선?
 │   └─ YES → /refactor path/to/module
 │
 └─ CI/CD, Docker, 배포 설정?
     └─ YES → /devops "target"
```

| Skill | Description | Outputs |
|-------|-------------|---------|
| `/brainstorm [idea]` | Interactive brainstorming via Socratic dialogue | `docs/brainstorm_notes.md` |
| `/bizanalysis [idea]` | Business viability analysis with market research | `docs/business_analysis.md` |
| `/prd [path]` | Create or update a PRD via interactive conversation | `PRD.md` (or specified path) |
| `/kickoff PRD.md` | Analyze PRD and generate planning docs | `docs/requirements.md`, `docs/ux_spec.md`, `docs/architecture.md`, `issues.md`, `docs/test_plan.md`, `STATUS.md` |
| `/issue [description]` | 자연어로 단일 이슈 생성 + planning docs 자동 업데이트 | `issues.md`, `STATUS.md`, 관련 `docs/*.md` |
| `/uiux [PRD.md]` | Design philosophy + design system + HTML/CSS prototype | `docs/design_philosophy.md`, `docs/design_system.md`, `docs/wireframes.md`, `docs/interactions.md`, `prototype/` |
| `/mobile-uiux [PRD.md]` | Mobile design system + React Native (Expo) prototype | `docs/design_philosophy.md`, `docs/design_system_mobile.md`, `docs/wireframes_mobile.md`, `docs/interactions_mobile.md`, `prototype-mobile/` |
| `/sprint` | Auto-orchestrate multiple issues via team-lead | `docs/sprint_state.md`, `STATUS.md` |
| `/implement ISSUE-001` | Implement a single issue + create GH Issue/PR | Code, tests, PR (`Closes #N`) |
| `/review ISSUE-001` | Senior review + security audit + UI review on PR | `docs/review_notes.md`, `docs/ui_review_notes.md` |
| `/ship` | Merge PR + update docs/changelog | `CHANGELOG.md`, `STATUS.md` updated |
| `/diagnose [error]` | Analyze a bug and propose a targeted fix | Diagnosis + fix |
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
│   ├── agents/          # 22 agent definitions
│   ├── skills/          # 15 skills
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

Reads the PRD and runs 5 subagents to generate planning documents:
- `requirement-analyst` → `docs/requirements.md`
- `ux-designer` → `docs/ux_spec.md`
- `architect` → `docs/architecture.md`
- `planner` → `issues.md`
- `qa-designer` → `docs/test_plan.md`

### UI/UX — Design and prototype

```
/uiux [PRD.md]
```

Requires `/kickoff` outputs. Design Interview를 통해 프로젝트 고유의 디자인 방향을 수립한 뒤, 레퍼런스 리서치를 거쳐 차별화된 디자인 시스템을 생성합니다. Builds on `docs/ux_spec.md` and `docs/requirements.md` to produce:

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

Requires `/kickoff` outputs. Like `/uiux` but for React Native (Expo) mobile apps. Design Interview를 통해 프로젝트 고유의 디자인 방향을 수립한 뒤, 레퍼런스 리서치를 거쳐 차별화된 모바일 디자인 시스템을 생성합니다. If `docs/design_philosophy.md` already exists (from `/uiux`), reuses it with user confirmation; otherwise generates it from scratch. Produces design philosophy, mobile-specific design system, wireframes with thumb zone considerations, and a runnable Expo prototype.

### Sprint — Auto-orchestrate multiple issues

```
/sprint
```

Dispatches the team-lead agent to automatically pick up ready issues from `issues.md`, implement them via `/implement`, review via `/review`, and ship via `/ship`. Loops until all issues are done or max iterations reached.

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

### DevOps — Set up infrastructure

```
/devops [target, e.g. "github-actions", "docker", "compose"]
```

Creates or updates Dockerfiles, docker-compose configs, GitHub Actions workflows, and deployment scripts.

## Agents

22 specialized agents, each with a defined role and tool permissions:

| Agent | Role | Tools |
|-------|------|-------|
| `brainstormer` | Interactive brainstorming facilitator | Read, Glob, Grep, Write, Edit, WebSearch, WebFetch |
| `business-analyst` | Business viability analysis + market research | Read, Glob, Grep, Write, Edit, WebSearch, WebFetch |
| `prd-writer` | Interactive PRD co-writing via conversation | Read, Glob, Grep, Write, Edit |
| `requirement-analyst` | Extract requirements from PRD | Read, Glob, Grep, Write, Edit |
| `ux-designer` | Create UX spec (v0: spec only) | Read, Glob, Grep, Write, Edit |
| `uiux-developer` | Design philosophy + design system + HTML/CSS prototype | Read, Glob, Grep, Write, Edit, Bash, WebSearch, WebFetch |
| `mobile-uiux-developer` | Mobile design system + React Native (Expo) prototype | Read, Glob, Grep, Write, Edit, Bash, WebSearch, WebFetch |
| `copywriter` | Write all user-facing copy (labels, errors, CTAs) | Read, Glob, Grep, Write, Edit |
| `architect` | Design software architecture | Read, Glob, Grep, Write, Edit |
| `data-modeler` | Design schemas, indexes, migrations, query patterns | Read, Glob, Grep, Write, Edit |
| `planner` | Break work into issues | Read, Glob, Grep, Write, Edit |
| `issue-writer` | 자연어 → 단일 이슈 생성 + docs 업데이트 | Read, Glob, Grep, Write, Edit, Bash |
| `qa-designer` | Design test strategy and cases | Read, Glob, Grep, Write, Edit |
| `team-lead` | Sprint orchestrator — dispatch agents, manage issues | Read, Glob, Grep, Write, Edit, Bash, Task |
| `developer` | Implement code + GH Issue/PR | Read, Glob, Grep, Write, Edit, Bash |
| `reviewer` | Senior code review + security audit | Read, Glob, Grep, Edit, Bash, Write |
| `ui-reviewer` | UI review — state coverage, copy, tokens, a11y | Read, Glob, Grep, Edit, Write |
| `documenter` | Maintain documentation | Read, Glob, Grep, Write, Edit |
| `diagnostician` | Analyze bugs and propose targeted fixes | Read, Glob, Grep, Write, Edit, Bash |
| `migrator` | Plan and execute migrations | Read, Glob, Grep, Write, Edit, Bash |
| `refactorer` | Improve code structure without changing behavior | Read, Glob, Grep, Write, Edit, Bash |
| `devops` | Set up CI/CD pipelines and deployment infra | Read, Glob, Grep, Write, Edit, Bash |

## Project Structure

```
claude-dev-kit/
├── agents/                  # Agent role definitions (22)
│   ├── brainstormer.md
│   ├── business-analyst.md
│   ├── prd-writer.md
│   ├── requirement-analyst.md
│   ├── ux-designer.md
│   ├── uiux-developer.md
│   ├── mobile-uiux-developer.md
│   ├── copywriter.md
│   ├── architect.md
│   ├── data-modeler.md
│   ├── planner.md
│   ├── issue-writer.md
│   ├── qa-designer.md
│   ├── team-lead.md
│   ├── developer.md
│   ├── reviewer.md
│   ├── ui-reviewer.md
│   ├── documenter.md
│   ├── diagnostician.md
│   ├── migrator.md
│   ├── refactorer.md
│   └── devops.md
├── skills/                  # Workflow skills (15)
│   ├── brainstorm/SKILL.md
│   ├── bizanalysis/SKILL.md
│   ├── prd/SKILL.md
│   ├── kickoff/SKILL.md
│   ├── issue/SKILL.md
│   ├── uiux/SKILL.md
│   ├── mobile-uiux/SKILL.md
│   ├── sprint/SKILL.md
│   ├── implement/SKILL.md
│   ├── review/SKILL.md
│   ├── ship/SKILL.md
│   ├── diagnose/SKILL.md
│   ├── migrate/SKILL.md
│   ├── refactor/SKILL.md
│   └── devops/SKILL.md
├── templates/               # Document templates (19)
│   ├── requirements.md
│   ├── ux_spec.md
│   ├── architecture.md
│   ├── data_model.md
│   ├── design_philosophy.md
│   ├── design_system.md
│   ├── design_system_mobile.md
│   ├── wireframes.md
│   ├── wireframes_mobile.md
│   ├── interactions.md
│   ├── interactions_mobile.md
│   ├── copy_guide.md
│   ├── issues.md
│   ├── test_plan.md
│   ├── review_lessons.md
│   ├── review_notes.md
│   ├── ui_review_notes.md
│   ├── brainstorm_notes.md
│   └── business_analysis.md
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
│   ├── validate_issues.py   # issues.md format validator
│   ├── verify_checkpoint.py # Skill phase gate verification
│   ├── worktree.sh          # git worktree lifecycle (create/path/remove/root)
│   └── flock_edit.sh        # file-lock wrapper for shared files
├── user/                    # User-level tools
│   └── kit/bin/cc-statusline.py
├── tests/                   # Tests
│   ├── test_merge_settings.py
│   ├── test_agent_state.py
│   ├── test_worktree.py
│   ├── test_flock_edit.py
│   └── test_integration.py
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
- `test_integration.py` — Agent/skill frontmatter, template existence, cross-references, checkpoint markers, self-review sections

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
- All subagents use model: `opus`

## License

MIT
