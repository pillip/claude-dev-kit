# claude-kit (v0.1)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-917%20passing-brightgreen.svg)]()

Turn a PRD into shipped code. **33 engineering agents + 23 skills** (default install) handle the entire development lifecycle — from PRD to code review to deployment — so you can focus on what to build, not how. An optional **sales pack** (5 agents + 5 skills, opt-in via `--pack=sales`) covers account / discovery / proposal workflows for teams sharing a repo with engineering.

## Why claude-kit?

**Positioning: trustworthy code in collaboration → AI dev team control plane.** The kit's bet is that AI productivity is bottlenecked not by the model but by what surrounds it — concurrency, state, guardrails, decision capture, learning. Adding more agents doesn't close that gap; structuring the work does.

Claude Code is powerful on its own, but without structure it produces inconsistent results — skipped tests, forgotten reviews, PRs that drift from requirements. claude-kit solves this by giving Claude Code **a repeatable process**:

- **Structured pipeline**: Every issue goes through spec (when required) → implement → review → ship. No shortcuts, no skipped phases.
- **Specialized agents**: Instead of one generalist prompt, 33 engineering agents each handle what they're best at — an architect designs the system, a reviewer audits security, a QA designer writes test plans, a design-auditor critiques the system, a separate ui-reviewer critiques the implementation.
- **Decision capture**: Non-trivial issues require a SPEC (`/spec` → `docs/specs/SPEC-NNN.md`) — Problem / Options ≥2 / Trade-offs / Decision / Rollback. Sprint mode auto-runs it; non-sprint mode HOLDs for review.
- **Automatic feedback loops**: Review findings create follow-up issues. Test failures trigger root-cause analysis. Shipped code gets test gap detection. Nothing falls through the cracks.
- **Resumable state**: Sprint progress is checkpointed to `sprint_state.md`. Crash or timeout? Just re-run `/sprint` to pick up where you left off.
- **Zero configuration**: Install as a git submodule, run one script, and all agents/skills/hooks are ready. Pack opt-in via a single flag.

In short: claude-kit turns Claude Code from a smart assistant into a **development team that follows engineering best practices**.

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
/prd → /kickoff → /uiux → /sprint
# (optional pre-PRD: /brainstorm → /bizanalysis → /prd)
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

### 7. Add a feature to an existing product
```
/issue "Add Stripe payment processing with subscription tiers, billing page, and invoice history"
```
Auto-detects that this spans multiple screens/modules, estimates issue count, updates planning and design docs incrementally (append-only), and creates a batch of implementation issues with dependencies.

### 8. Maintain and evolve
```
/refactor src/legacy_module.py    # Improve code structure
/migrate "Django 5.0"             # Upgrade dependencies
/devops "github-actions"          # Set up CI/CD
```

## Workflow

**New project:**
```
/prd → /kickoff → /uiux → /sprint
# (optional pre-PRD: /brainstorm → /bizanalysis → /prd)
```

**Existing codebase (no PRD):**
```
/scan → /sprint
```

**Single issue:**
```
/implement ISSUE-001 → /review ISSUE-001 → /ship
```

**Add a feature to existing product:**
```
/issue "feature description" → /sprint (or /implement per issue)
```

> **Optional pre-PRD**: `/brainstorm` (Socratic exploration) and `/bizanalysis` (market + SWOT) are stand-alone primitives, not part of the default flow. If your idea is clear, start from `/prd`. These exist for the case where you genuinely don't know what to build yet.
> `/uiux`, `/mobile-uiux`, and `/desktop-uiux` are optional for UI projects. Backend/CLI projects go directly from `/kickoff` to `/sprint`.
> `/sprint` auto-orchestrates multiple issues. For a single issue, use `/implement` directly.
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

test failure → team-lead runs /diagnose for root cause analysis
            → diagnosed fix applied before retry

review lessons (native memory) → recurring high-impact patterns recalled next session
                  → team-lead creates preventive issues via planner
```

Standalone skills (`/testgen`, `/diagnose`, `/refactor`) register their work in `issues.md` when it exists, so team-lead can track all work in `sprint_state.md`.

### Packs

The default install ships the **core** layer — engineering agents, design pack (uiux / mobile-uiux / desktop-uiux), and safety guardrails. Domain-specific workflows live in opt-in **packs** that depend on core.

| Pack | What it adds | Install command |
|---|---|---|
| **core** (default) | 33 engineering agents + 23 skills | `/plugin install claude-dev-kit@claude-dev-kit` |
| **sales** | 5 sales agents + 5 sales skills + 7 sales templates | `/plugin install claude-dev-kit-sales@claude-dev-kit` |

Rules:
- **Packs are additive on top of core, never substitutes.** Every pack plugin declares `dependencies: ["claude-dev-kit"]` in its `plugin.json` — installing a pack auto-installs and enables core.
- Pack skills are namespaced by their plugin name (`/claude-dev-kit-sales:proposal`), so pack and core entries never collide.

See `packs/README.md` for the manifest schema and rules for contributing new packs.

### Decision Tree — Which skill should I use?

```
START
 │
 ├─ No PRD yet?
 │   └─ YES → /prd
 │   └─ (optional pre-PRD: direction unclear → /brainstorm → /bizanalysis → /prd)
 │
 ├─ PRD exists but no planning docs?
 │   └─ YES → /kickoff PRD.md
 │
 ├─ Planning docs ready, project has UI?
 │   ├─ Web → /uiux
 │   ├─ Mobile → /mobile-uiux
 │   ├─ Desktop → /desktop-uiux
 │   └─ Have Figma design → /figma2proto [--mobile|--desktop] <URLs>
 │
 ├─ Want to add a feature or issues to an existing product?
 │   ├─ Small (single task) → /issue "description" (creates 1 issue)
 │   └─ Medium (multi-screen/module) → /issue "feature description" (auto-detects batch mode, creates multiple issues)
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
| `/issue [description]` | Create issues (single or batch) from natural language + auto-update planning and design docs | `issues.md`, `STATUS.md`, related `docs/*.md` |
| `/uiux [PRD.md]` | Design philosophy + design system + HTML/CSS prototype | `docs/design_philosophy.md`, `docs/design_system.md`, `docs/wireframes.md`, `docs/interactions.md`, `prototype/` |
| `/mobile-uiux [PRD.md]` | Mobile design system + React Native (Expo) prototype | `docs/design_philosophy.md`, `docs/design_system_mobile.md`, `docs/wireframes_mobile.md`, `docs/interactions_mobile.md`, `prototype-mobile/` |
| `/desktop-uiux [PRD.md]` | Desktop design system + Electron prototype | `docs/design_philosophy.md`, `docs/design_system_desktop.md`, `docs/wireframes_desktop.md`, `docs/interactions_desktop.md`, `prototype-desktop/` |
| `/figma2proto [--mobile\|--desktop] <URLs>` | Fetch Figma design via API and generate complete design deliverable (prototype + docs) | `prototype/`, `docs/design_system.md`, `docs/design_philosophy.md`, `docs/wireframes.md`, `docs/interactions.md`, `docs/copy_guide.md` |
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

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — CLI, desktop app, or IDE extension
- macOS / Linux
- Python 3.11+
- Git
- [GitHub CLI](https://cli.github.com/) (`gh`) — authenticated

## Installation

claude-dev-kit ships as a Claude Code **plugin marketplace** (`.claude-plugin/marketplace.json`).

### 1. Install the plugin

Inside a Claude Code session:

```bash
# Add the marketplace (the repo itself), then install the core plugin
/plugin marketplace add pillip/claude-dev-kit
/plugin install claude-dev-kit@claude-dev-kit

# Optionally add the sales pack — installing it auto-installs core (declared dependency)
/plugin install claude-dev-kit-sales@claude-dev-kit
```

Or from a shell (same effect, scriptable):

```bash
claude plugin marketplace add pillip/claude-dev-kit
claude plugin install claude-dev-kit@claude-dev-kit          # --scope user|project|local
```

**Namespacing:** plugin skills are namespaced by plugin name — e.g. `/claude-dev-kit:implement`, `/claude-dev-kit:review`. This is mandatory for plugins (it prevents cross-plugin collisions).

**Script resolution:** kit helper scripts (checkpoints, worktree wrappers) resolve through `${CLAUDE_PLUGIN_ROOT}`, which Claude Code substitutes into skill text at load time — no files are copied into your project, and the absolute prefix keeps working from inside worktrees.

### 2. Install user tools (optional)

Installs the status line script to `~/.claude/kit/bin/`. Run once per machine (needs a clone of this repo):

```bash
bash scripts/install_user.sh
```

> **Migrating from the retired submodule installer?** The symlink-based project installer was removed after the plugin path reached parity (ISSUE-027). Remove the old symlinks from your project's `.claude/agents/`, `.claude/skills/`, and `.claude/hooks/`, drop the `.claude-kit` submodule if you no longer need it, and install the plugin as above. Skill names gain the `/claude-dev-kit:` prefix.

### 3. Verify gh authentication

```bash
gh auth status
```

If not authenticated, run `gh auth login`.

## Team-scale usage

The kit assumes **the repo IS the team boundary**. Two adoption patterns cover the common shapes — and there is deliberately no separate "team layer."

### Pattern (a) — Monorepo (engineering or sales)

The common pattern. One repo holds all team work; the kit installs once at the root.

- **Engineering team**: services live under `services/<name>/` subdirectories. Each service worktree is created from the repo root via `scripts/worktree.sh`. Shared state (`issues.md`, `STATUS.md`, `sprint_state.md`) sits at the root.
- **Sales team**: accounts live under `accounts/<company>/` subdirectories. Cross-account patterns accumulate in repo-root `docs/sales_lessons.md`. Walk-up resolution via `scripts/find_shared.sh` finds shared sales-pack files (e.g., `sales_email_persona.md`) from inside any account directory.

```
~/work/my-team/                       # team boundary == repo boundary
├── .claude-kit/                      # submodule
├── .claude/                          # installed (--pack=sales for sales)
├── issues.md, STATUS.md
├── docs/                             # shared knowledge
├── services/auth/                    # (engineering) one git checkout
├── services/gateway/                 # ...
│   └── ...
# OR
├── accounts/customer-a/              # (sales) one account
├── accounts/customer-b/              # ...
```

### Pattern (b) — Virtual monorepo wrapper (polyrepo teams)

When services genuinely cannot be in one repo (independent release cadence, vendor isolation, etc.), wrap them. A top-level **wrapper directory** is itself a git repo holding the `.claude-kit/` submodule and shared kit state at its root; each independent service repo lives as an immediate subdirectory and is gitignored from the wrapper.

```
~/work/my-team/                       # wrapper = git repo
├── .git/
├── .gitignore                        # auth-service/, gateway-service/, ...
├── .claude-kit/                      # submodule
├── .claude/                          # installed at wrapper root
├── issues.md, STATUS.md, sprint_state.md
├── docs/
├── auth-service/                     # independent git repo (gitignored)
├── gateway-service/                  # independent git repo (gitignored)
└── payments-service/                 # independent git repo (gitignored)
```

Per-service work routes to the right subdirectory; kit state stays at the wrapper root. Code-level support for this layout (Target-Service field, `worktree.sh --service` flag, wrapper-root detection in `flock_edit.sh`) is tracked as ISSUE-008 — gated on telemetry signal that polyrepo friction is real before we ship the helpers.

### Why no separate "team layer"

A separate layer would add concepts (a new manifest type, a new install scope) without adding capability:
- **Sales team accumulation** already works via `accounts/<company>/` subdirectories in a sales-pack install. The repo's accounts directory IS the team asset store.
- **Cross-team installation** uses the existing `--pack` flag (one repo can install core + sales together).
- **Polyrepo collaboration** uses the wrapper pattern above. The wrapper directory IS the team boundary.

Adding a "team layer" would raise the onboarding cost (more concepts to learn, more install steps) for zero new capability over what the existing core + pack + wrapper model already provides. **This decision is intentional, not a transitional state.** Documented here so contributors don't re-propose it.

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

### Desktop UI/UX — Design and prototype for desktop

```
/desktop-uiux [PRD.md]
```

Requires `/kickoff` outputs. Like `/uiux` but for Electron desktop apps. Conducts a Design Interview with an additional "Desktop Identity" question (native OS integration vs distinct branded identity). If `docs/design_philosophy.md` already exists (from `/uiux` or `/mobile-uiux`), reuses it with user confirmation; otherwise generates it from scratch. Produces desktop-specific design system with keyboard shortcuts, window chrome specs, and multi-window configurations, plus an Electron prototype with main/preload/renderer separation.

### Figma to Prototype — Design from existing Figma

```
/figma2proto https://www.figma.com/design/ABC123/MyProject?node-id=42-1234
/figma2proto --mobile https://...?node-id=42-5678 https://...?node-id=42-9012
/figma2proto --desktop https://...?node-id=42-3456
```

Fetches design data from Figma via API and generates the **same complete deliverable** as `/uiux` — prototype, design system, design philosophy, wireframes, interactions, and copy guide. The Figma design is treated as the source of truth: the design philosophy is reverse-engineered from the design (not invented), and interactions/copy that Figma can't express are filled in by asking the user. Supports web (default), mobile (`--mobile` → React Native prototype), and desktop (`--desktop`). Requires `FIGMA_TOKEN` environment variable.

### Issue — Create issues and update planning/design docs

```
/issue "description"
```

Creates issues from a natural language description and auto-updates related planning and design docs. Operates in two modes:

- **Single-issue mode**: For small tasks (one module, one screen). Creates 1 issue, updates affected docs.
- **Batch mode**: For medium-sized features spanning multiple modules/screens. Auto-detects scope, estimates issue count (3–8), and creates multiple issues with dependencies via the planner agent in append mode.

When design docs exist (`design_philosophy.md`, `wireframes.md`, etc.), the skill also detects and incrementally updates them — appending new screens to wireframes, new flows to interactions, new components to the design system, and new copy entries. Design philosophy is read-only; if a conflict is detected, the skill warns and suggests running `/uiux`.

### Test Generation — Fill test gaps

```
/testgen [path]
```

Scans source files for missing or hollow tests (empty functions, no assertions). Detects unit, integration, and E2E gaps by cross-referencing `docs/test_plan.md` critical flows. Generates tests with real assertions and creates a PR. When `issues.md` exists, registers the work as an issue in the sprint ecosystem.

### Sprint — Auto-orchestrate multiple issues

```
/sprint
```

Runs a phase-based sprint loop: each iteration reads `sprint_state.md`, picks the highest-priority phase (ship first, review second, implement last), and dispatches the team-lead agent for that single phase. This structural enforcement guarantees every issue completes the full implement → review → ship pipeline — no phase gets skipped. Includes automated feedback loops: review findings create follow-up issues, test failures trigger /diagnose, and shipped code gets test gap detection.

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

**33 core engineering agents.** Agents **inherit the session model** (no `model:` pins — ISSUE-030): whatever model your session runs, subagents run it too, so the kit never caps agent quality below the model you chose. Per-agent cost/depth is tuned with **effort tiers** instead — `high`/`xhigh` for judgment and creation, `low`/`medium` for structured extraction (`xhigh` auto-falls-back on models that cap at `high`). **The sales pack adds 5 more** (`account-researcher`, `champion-mapper`, `discovery-coach`, `meeting-synthesizer`, `proposal-writer`) via the `claude-dev-kit-sales` plugin. See [Packs](#packs).

> **Deterministic deployments:** to pin agent behavior for production use, set the model once at the session/project level (`model` in `.claude/settings.json`, or `claude --model <alias>`) — one control point instead of the old 33 per-agent pins. All inherit-agents follow it.

| Agent | Effort | Role | Tools |
|-------|-------|------|-------|
| `brainstormer` | high | Interactive brainstorming facilitator | Read, Glob, Grep, Write, Edit, WebSearch, WebFetch |
| `business-analyst` | high | Business viability analysis + market research | Read, Glob, Grep, Write, Edit, WebSearch, WebFetch |
| `requirement-analyst` | medium | Extract requirements from PRD | Read, Glob, Grep, Write, Edit |
| `ux-designer` | high | Create UX spec (v0: spec only) | Read, Glob, Grep, Write, Edit |
| `uiux-developer` | xhigh | Design philosophy + design system + HTML/CSS prototype | Read, Glob, Grep, Write, Edit, Bash, WebSearch, WebFetch |
| `mobile-uiux-developer` | xhigh | Mobile design system + React Native (Expo) prototype | Read, Glob, Grep, Write, Edit, Bash, WebSearch, WebFetch |
| `desktop-uiux-developer` | xhigh | Desktop design system + Electron/Tauri prototype | Read, Glob, Grep, Write, Edit, Bash, WebSearch, WebFetch |
| `copywriter` | medium | Write all user-facing copy (labels, errors, CTAs) | Read, Glob, Grep, Write, Edit |
| `figma-converter` | medium | Convert Figma exports to clean prototype HTML with design tokens | Read, Glob, Grep, Write, Edit, Bash |
| `architect` | xhigh | Design software architecture | Read, Glob, Grep, Write, Edit |
| `data-modeler` | xhigh | Design schemas, indexes, migrations, query patterns | Read, Glob, Grep, Write, Edit |
| `planner` | xhigh | Break work into issues + convert review findings to issues | Read, Glob, Grep, Write, Edit |
| `issue-writer` | medium | Natural language → issue creation + planning/design docs update | Read, Glob, Grep, Write, Edit, Bash |
| `qa-designer` | high | Design test strategy and cases | Read, Glob, Grep, Write, Edit |
| `team-lead` | xhigh | Sprint phase executor — receives one phase (implement/review/ship), executes it, returns | Read, Glob, Grep, Write, Edit, Bash, Task |
| `developer` | xhigh | Implement code + GH Issue/PR + report discovered findings | Read, Glob, Grep, Write, Edit, Bash |
| `test-generator` | high | Generate missing unit/integration/E2E tests | Read, Glob, Grep, Write, Edit, Bash |
| `reviewer` | xhigh | Senior code review + security audit | Read, Glob, Grep, Edit, Bash, Write |
| `ui-reviewer` | high | UI review — state coverage, copy, tokens, a11y | Read, Glob, Grep, Edit, Write |
| `design-auditor` | high | Design system audit — token consistency, component completeness | Read, Glob, Grep, Edit, Write |
| `a11y-auditor` | medium | WCAG 2.1 AA accessibility audit | Read, Glob, Grep, Edit, Write |
| `documenter` | low | Maintain documentation | Read, Glob, Grep, Write, Edit |
| `devops` | medium | Set up CI/CD pipelines and deployment infra | Read, Glob, Grep, Write, Edit, Bash |
| `codebase-scanner` | low | Analyze existing codebase in 4 passes (identity, architecture, requirements, quality) | Read, Glob, Grep |
| `scan-analyst` | low | Reverse-engineer requirements from existing code and tests | Read, Glob, Grep, Write, Edit |
| `scan-architect` | medium | Document as-is architecture from scan context | Read, Glob, Grep, Write, Edit |
| `scan-data-modeler` | medium | Extract data models from ORM/migration/schema declarations | Read, Glob, Grep, Write, Edit |
| `scan-qa-designer` | medium | Assess existing test coverage and identify gaps | Read, Glob, Grep, Write, Edit |
| `scan-planner` | medium | Generate improvement issues from scan observations | Read, Glob, Grep, Write, Edit |

## Roadmap

The next layer the kit is building: **AI dev team control plane** — telemetry → eval → cumulative learning memory. Each issue ships as its own SPEC + PR; no dates committed.

- **ISSUE-001 — Run telemetry**: every agent invocation, tool call, and phase emits a JSONL trace event so lead time, retry rate, and finding density can be measured without touching agent prompts.
- **ISSUE-002 — Workflow eval gate**: LLM-as-judge scoring of `review_notes.md` against the PR diff. Non-blocking advisory at first; data feeds future thresholds.
- **ISSUE-033 — Native-memory learning loop** (supersedes ISSUE-003): `/review` records preventable patterns as **review lessons in Claude Code native memory** (one fact per entry + `MEMORY.md` index), auto-recalled into later sessions. Separate-context subagents receive relevant lessons injected by the calling skill (subagents get no auto-recall). Replaces the never-used `docs/review_lessons.md` registry.
- **ISSUE-008 — Virtual monorepo wrapper code support**: per-service routing helpers + wrapper-root detection. Gated on telemetry signal (ISSUE-001) that polyrepo teams actually hit friction.

Recently shipped (Cluster C + D this session): `/spec` skill + Spec-Required metadata (ISSUE-006), `/implement` Phase 0 spec gate (ISSUE-007), Pilot Gate hardening — neutral observation + separate-context critic + specificity + auto-cycle (ISSUE-010), Kill WebFetch reference fabrication (ISSUE-011), Reference Anchor tuning to 2–3 cues + literal_quote (ISSUE-012), `design-auditor` / `ui-reviewer` scope split (ISSUE-013). See `docs/specs/` for each SPEC.

## Project Structure

```
claude-dev-kit/
├── agents/                  # Core engineering agents (33)
├── skills/                  # Core engineering / design / safety skills (23)
├── packs/                   # Opt-in domain packs
│   └── sales/               # Sales pack (5 agents + 5 skills + 7 templates)
│       ├── agents/
│       ├── skills/
│       ├── templates/
│       └── manifest.yaml
│   ├── brainstorm/SKILL.md
│   ├── bizanalysis/SKILL.md
│   ├── prd/SKILL.md
│   ├── kickoff/SKILL.md
│   ├── issue/SKILL.md
│   ├── uiux/SKILL.md
│   ├── figma2proto/SKILL.md    # Convert Figma exports to prototype
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
├── templates/               # Core document templates (26)
├── project/                 # Files installed into target project
│   └── .claude/
│       ├── hooks/agent_state.py
│       └── settings.snippet.json
├── scripts/                 # Utility scripts
│   ├── install_user.sh      # Status line install (user scope; project install is /plugin)
│   ├── ensure_gh.sh
│   ├── ensure_permissions.py
│   ├── gen_skills.py        # Template → SKILL.md generator
│   ├── preambles.py         # Tiered preamble injection
│   ├── validate_issues.py   # issues.md format validator
│   ├── verify_checkpoint.py # Skill phase checkpoint verification
│   ├── verify_gates.py      # Platform gate engine (e2e-web, e2e-mobile, api, load, …)
│   ├── gate_server.sh       # Server lifecycle wrapper for e2e/api gates
│   ├── checkpoint.sh        # Wrapper: resolve repo root + run verify_checkpoint.py
│   ├── worktree.sh          # git worktree lifecycle (create/path/remove/root)
│   ├── wt_setup.sh          # Wrapper: worktree create + freeze marker in one step
│   ├── wt_cleanup.sh        # Wrapper: safe cd-to-root + worktree remove
│   ├── registry_edit.sh     # Wrapper: flock_edit on main-rooted registry files
│   └── flock_edit.sh        # file-lock wrapper for shared files
├── user/                    # User-level tools
│   └── kit/bin/cc-statusline.py
├── tests/                   # Tests
├── docs/                    # Kit documentation
│   └── PRD_agent_system_v0.md
└── README.md
```

## Platform Gates

`/implement` and `/ship` automatically run platform-specific test gates via
`scripts/verify_gates.py`. Gates are detected from the project layout —
no manual wiring required if you use the default conventions.

| Gate          | Detected when…                                                                                  | Default blocking |
|---------------|-------------------------------------------------------------------------------------------------|------------------|
| `unit`        | `tests/` directory or `test_*.py` / `*.test.ts` / `*.spec.ts` files exist                       | yes              |
| `integration` | `tests/integration/` directory exists                                                           | yes              |
| `e2e-web`     | `playwright.config.*` exists or `package.json` lists React/Vue/Svelte/Next/Angular/Nuxt         | yes              |
| `e2e-mobile`  | `app.json` / `android/` / `ios/` exists or `package.json` lists `react-native`                  | yes              |
| `api`         | `openapi.{yaml,json}` exists or `pyproject.toml` lists FastAPI/Flask/Django (or Express in JS)  | yes              |
| `load`        | Locust / k6 / Artillery config present                                                          | **no** (warn)    |

Gate behavior by phase:

- **`/implement` → non-blocking**: failing gates surface as warnings during
  implementation, flagging integration risks early without stopping the
  TDD loop.
- **`/ship` → blocking**: failing a real gate must stop ship. `load` stays
  non-blocking even here, since perf work is typically out-of-band.

Missing tools (Playwright browsers, Maestro, Detox) are auto-installed
before the gate runs. Server-based gates (e2e-web, api) use
`scripts/gate_server.sh` to start the app, poll a health endpoint, run
the test command, and clean up the process group on exit.

### Configuring gates via `docs/test_plan.md`

`qa-designer` generates a `## Verify Gates Configuration` section in
`docs/test_plan.md`. Users can edit it to override defaults without
touching Python:

```markdown
## Verify Gates Configuration

Server start command: `npm run dev`
Server health URL: `http://localhost:3000`
Server startup timeout: 30
Mobile test framework: `maestro`
Mobile build command: `npm run build:ios`
Mobile Detox config: `ios.sim.debug`

### Gate Overrides
| Gate        | Enabled | Blocking |
|-------------|---------|----------|
| unit        | yes     | yes      |
| integration | yes     | yes      |
| e2e-web     | yes     | yes      |
| e2e-mobile  | yes     | yes      |
| api         | yes     | yes      |
| load        | yes     | no       |
```

Key names are parsed literally by `scripts/verify_gates.py` — do not
rename them. If the section is absent, defaults are used.

## Status Line

After installation, the Claude Code status line displays:

```
claude-opus-4-8 | agents:ux-designer,developer | tool:Write | tok:45230/200000 | $0.123
```

Shows the current model, active agents, last tool used, token usage, and cumulative cost.

## Testing

```bash
pytest tests/ -q
```

Tests cover merge logic, agent state hooks, worktree lifecycle, file locking, integration checks (frontmatter, templates, cross-references), scan pipeline validation, skill generation, preamble injection, safety guardrails, and more.

## Updating

```bash
claude plugin update claude-dev-kit        # restart the session to apply
```

Or in-session: `/plugin` → claude-dev-kit → update.

## Uninstalling

```bash
claude plugin uninstall claude-dev-kit-sales   # if installed (packs first — they depend on core)
claude plugin uninstall claude-dev-kit
claude plugin marketplace remove claude-dev-kit
```

Or in-session via `/plugin`. Plugin files live in Claude Code's cache (`~/.claude/plugins/`), so uninstalling leaves nothing behind in your project — any `.claude-kit/` runtime state in a project can be deleted freely.

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

## Current Scope (v0.1)

- **Platform**: macOS / Linux
- **Default stack** (when PRD doesn't specify):
  - Backend: Django + Postgres
  - Web frontend: React + TypeScript
  - Mobile: React Native (Expo)
- **Custom stack**: Define your preferred tech stack during `/prd` and the architect agent will follow it
- **Model mix**: opus (21 agents) for judgment/creativity, sonnet (12 agents) for structured extraction

## License

MIT
