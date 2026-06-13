# Issues

> SSOT: Progress and completion are tracked by the Status field in this document (not inferred from code analysis)
> Rule: **1 Issue = 1 PR** (GitHub-first)
> Context: claude-dev-kit dogfoods itself — these issues build the "AI dev team control plane" layer (telemetry → eval → memory → spec → release) on top of the existing 38 agents / 27 skills primitive set.

## Conventions
- Track: `product` | `platform`
- Status: `backlog` | `doing` | `waiting` | `done` | `drop`
- Priority: `P0` (blocks everything) | `P1` (core) | `P2` (nice-to-have)
- Estimate: `0.5d` | `1d` | `1.5d` (> 1.5d must be split)
- Platform: `web` (default) | `mobile` | `desktop`
- Manual: `true` = task requires human action; `false` = fully automatable
- Branch: `issue/ISSUE-<NNN>-<slug>`
- GitHub: **/implement creates a GH Issue (if missing) + PR and links them (Closes #N)**
- Spec PR exception: a `Spec-Required: true` issue produces **2 PRs in non-sprint mode** (spec-only PR `issue/ISSUE-NNN-spec` then impl PR `issue/ISSUE-NNN`), and **1 bundled PR in sprint mode** (single branch carrying both the SPEC commit and impl commits). See ISSUE-006/007.

---

## Board

### Backlog
- [ ] ISSUE-001: Run telemetry MVP — JSONL trace from agent_state hook _(track: platform, P1, 1.5d)_
- [ ] ISSUE-002: Workflow eval gate MVP — LLM-as-judge for review_notes quality _(track: platform, P1, 1.5d)_
- [ ] ISSUE-003: Cumulative learning memory MVP — promote review_lessons to structured store _(track: platform, P1, 1.5d)_
- [ ] ISSUE-004: Sales pack file move + manifest schema _(track: platform, P1, 1d)_
- [ ] ISSUE-005: README sync — reflect counts + positioning + post-sales-boundary layout + team-scale usage _(track: platform, P1, 1d)_
- [ ] ISSUE-007: /implement spec gate — sprint auto-run + non-sprint HOLD + signal detection _(track: platform, P1, 1d)_
- [ ] ISSUE-008: Virtual monorepo wrapper — polyrepo team support _(track: platform, P2, 1.5d)_
- [ ] ISSUE-009: Install script --pack flag + merge_settings + tests _(track: platform, P1, 1.5d)_
- [ ] ISSUE-010: Pilot Gate hardening — separate-context critic + auto-cycle + neutral observation + specificity check _(track: platform, P2, 1.5d)_
- [ ] ISSUE-011: Kill WebFetch reference fabrication — image-grounded references only _(track: platform, P1, 0.5d)_
- [ ] ISSUE-012: Reference Anchor tuning — 2-3 strong cues + 1 literal quote _(track: platform, P2, 0.5d)_
- [ ] ISSUE-013: Consolidate ui-reviewer / design-auditor agents — sharpen role boundaries _(track: platform, P2, 1d)_

### Doing

### Waiting

### Done
- [x] ISSUE-006: /spec skill — RFC pattern + Spec-Required metadata + non-sprint HOLD gate _(track: platform, P1, 1.5d)_

### Drop

---

## Issue Detail

### ISSUE-001: Run telemetry MVP — JSONL trace from agent_state hook
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30)
- Priority: P1
- Estimate: 1.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Every agent invocation, tool call, and skill phase emits a structured trace event to `.claude/runs/<run-id>.jsonl` (project-side, installed via install_project.sh — NOT in the `.claude-kit/` submodule source), enabling later metric extraction (lead time, retry rate, finding density) without touching agent prompts.

#### Scope (In/Out)
- In:
  - Extend `project/.claude/hooks/agent_state.py` to append JSONL trace events (agent_start, agent_end, tool_call, phase_transition).
  - New `scripts/trace_query.py` with basic queries: `lead-time <run-id>`, `agent-stats <run-id>`, `phase-histogram <run-id>`.
  - Trace schema documented in `docs/telemetry_schema.md`.
  - Unit tests for hook emission + query CLI.
- Out:
  - Dashboard / visualization (separate follow-up).
  - Cross-run aggregation / time-series DB (follow-up).
  - LLM-based event interpretation.

#### Acceptance Criteria (DoD)
- [ ] Given a `/sprint` run, when it completes, then `.claude/runs/<run-id>.jsonl` contains ≥2 events per agent invocation (a `agent_start` and `agent_end` pair) with `ts`, `agent`, `event_type`, `phase`, `issue_id` fields.
- [ ] Given a trace file, when `scripts/trace_query.py lead-time <run-id>` runs, then it prints lead time per issue (ready → shipped) in seconds.
- [ ] Given the existing test suite, when run, then no existing test regresses; new hook tests cover emission + schema validity.
- [ ] Given `docs/telemetry_schema.md`, when read, then every event type has field list + example.

#### Implementation Notes
- Reuse the existing `agent_state.py` hook plumbing — do not introduce a new hook surface.
- Append-safety under concurrent worktrees: POSIX `O_APPEND` only guarantees atomicity for writes ≤ `PIPE_BUF` (typically 4 KB on macOS/Linux). Cap each event payload to **< 4 KB** (schema validator enforces) **or** acquire `flock` on the run file before write. Document the chosen approach in `docs/telemetry_schema.md` and add a unit test that proves no line interleave under the chosen guarantee.
- Run-id = sprint start timestamp + short slug; surface it in `sprint_state.md` for cross-reference.
- Keep PII out of payloads — never log message bodies, only event shapes.

#### Tests
- [ ] Hook emits well-formed JSONL on agent start/end (unit).
- [ ] Concurrent worktrees writing to same run file do not corrupt lines (integration with 2 worktrees).
- [ ] `trace_query.py lead-time` returns correct value on a synthetic trace fixture.
- [ ] Schema validator rejects malformed events.

#### Rollback
Revert the hook patch and delete `scripts/trace_query.py` + `docs/telemetry_schema.md`. No data migration required since traces are append-only files.

---

### ISSUE-002: Workflow eval gate MVP — LLM-as-judge for review_notes quality
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30)
- Priority: P1
- Estimate: 1.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
A new `scripts/eval_review.py` runs an LLM-as-judge pass on a `review_notes.md` against the PR diff and emits a quality score + missed-finding list, wired into `/ship` as a non-blocking advisory.

#### Scope (In/Out)
- In:
  - `scripts/eval_review.py` that takes `(pr_number, review_notes_path)` and outputs a structured report (`docs/review_eval_<pr>.md`).
  - Rubric covering: critical/high finding coverage, false-positive rate, actionability, traceability to diff lines.
  - Wire as **non-blocking** advisory at the end of `skills/ship/SKILL.md` (warning only, never fails the gate).
  - Determinism check: re-run on the same input twice; report variance.
  - Unit tests for rubric parsing + advisory output formatting.
- Out:
  - Blocking enforcement (separate follow-up after we have baseline scores).
  - Eval for other artifacts (`design_audit.md`, `a11y_audit.md`) — follow-up issues.
  - Auto-improvement of `reviewer` agent prompt based on findings (follow-up).

#### Acceptance Criteria (DoD)
- [ ] Given a PR with a known critical bug intentionally missed by the reviewer, when `eval_review.py` runs, then it flags the missed finding with severity + diff line reference.
- [ ] Given `/ship` runs on a PR, when complete, then the run log shows the eval advisory section (pass/concerns) without changing exit code.
- [ ] Given the same input run twice, when reports are compared, then critical/high findings overlap ≥80% (determinism floor documented).
- [ ] Given `docs/review_eval_<pr>.md`, when read, then every concern cites a diff line range + rubric category.

#### Implementation Notes
- Use Claude API directly (not a sub-agent) so the eval is deterministic-temperature and independent of the harness orchestration state.
- **Prerequisite + degraded mode**: requires `ANTHROPIC_API_KEY` env var and the `anthropic` SDK (added to `pyproject.toml` under `[project.optional-dependencies.eval]`). If the key is missing OR the SDK is not installed, `/ship` prints a one-line warning (`eval skipped: ANTHROPIC_API_KEY not set` / `anthropic SDK not installed`) and **continues without blocking**. Never fail the ship gate on a missing eval dependency.
- Prompt cache the PR diff + rubric across the two determinism runs.
- Keep the rubric in `templates/review_eval_rubric.md` so it can be versioned and tuned without touching code.
- This eval is the seed for ISSUE-003's anti-pattern DB — design the report schema so memory layer can ingest it.

#### Tests
- [ ] Rubric loader handles missing/extra sections without crashing.
- [ ] Synthetic "good review" fixture scores high; "missing critical" fixture scores low with correct flag.
- [ ] Ship skill advisory section renders even when eval fails (degraded mode).
- [ ] Determinism harness: 2 runs, report variance calculation correct.

#### Rollback
Remove the advisory block from `skills/ship/SKILL.md`, delete `scripts/eval_review.py` + `templates/review_eval_rubric.md`. No persistent state to clean up.

---

### ISSUE-003: Cumulative learning memory MVP — promote review_lessons to structured store
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30)
- Priority: P1
- Estimate: 1.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-002 (eval reports feed pattern extraction)

#### Goal
`docs/review_lessons.md` is replaced by a structured store (`.claude/memory/patterns.jsonl` + `docs/decision_log.md`) — same project-side location as ISSUE-001's traces, NOT inside the `.claude-kit/` submodule — that accumulates anti-patterns and architecture decisions across sprints, and `reviewer` + `planner` agents consume it as context.

#### Scope (In/Out)
- In:
  - Schema for two record types: `anti_pattern` (frequency, severity, last_seen, exemplar PRs) and `decision` (context, choice, trade-off, date).
  - `scripts/memory_promote.py` that scans `review_notes.md` + `review_eval_<pr>.md` outputs and promotes findings with Frequency ≥ 3 + Critical/High into `patterns.jsonl`.
  - Inject top-N relevant patterns into `reviewer` and `planner` agent context via a preamble hook (reuse `scripts/preambles.py`).
  - `decision_log.md` template + manual entry workflow (this MVP does not auto-extract decisions).
  - Tests for promotion thresholds + preamble injection.
- Out:
  - Per-codebase preference learning (functional vs OOP, etc.) — follow-up.
  - Semantic search over patterns (this MVP uses recency + frequency ranking).
  - Auto-extraction of decisions from PR descriptions (follow-up).
  - Migration of legacy `review_lessons.md` content — call it out in release notes, leave as-is.

#### Acceptance Criteria (DoD)
- [ ] Given 3+ `review_notes.md` files **from distinct PR numbers** with the same Critical finding category, when `memory_promote.py` runs, then `patterns.jsonl` contains exactly one consolidated `anti_pattern` record with frequency = 3 and exemplar PR list. Multiple findings in a single PR count as frequency = 1 for that PR.
- [ ] Given `patterns.jsonl` with ≥1 record, when `reviewer` agent runs on a new PR, then its preamble contains the top-N patterns (configurable, default N=5) selected by recency × frequency.
- [ ] Given `docs/decision_log.md`, when a new entry is appended manually, then format validator passes (date, context, choice, trade-off all present).
- [ ] Given a fresh repo with no memory, when agents run, then preamble injection degrades silently (no errors).

#### Implementation Notes
- Store path `.claude/memory/` is per-repo (project-side, populated by `install_project.sh`), gitignored by default (user can opt-in to commit). Document the trade-off in `README.md` memory section.
- **Frequency = distinct PR count**, not raw occurrence count. A single noisy PR repeating the same finding 5 times still contributes frequency 1 for that pattern. This prevents one bad PR from inflating rankings.
- Ranking function = `frequency × severity_weight × recency_decay` — keep it in one pure function so it's testable and tunable.
- Preamble injection must respect token budget — cap at ~500 tokens of memory context per agent.
- ISSUE-002's eval report is the highest-quality signal source; weight it higher than raw review_notes when promoting.

#### Tests
- [ ] Promotion threshold: 2 occurrences → not promoted, 3 → promoted, 3 with mixed severities → severity = max.
- [ ] Ranking function unit tests across edge cases (zero frequency, ancient last_seen).
- [ ] Preamble injection: agent context includes patterns when memory exists, omits cleanly when absent.
- [ ] Decision log validator rejects malformed entries.

#### Rollback
Delete `.claude-kit/memory/` and `scripts/memory_promote.py`; revert preamble hook changes. `review_lessons.md` is untouched so existing workflow continues.

---

### ISSUE-004: Sales pack file move + manifest schema
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30 — sales pack is off-thesis vs "trustworthy code / AI dev team control plane" positioning. Split from original ISSUE-004 — install script work is ISSUE-009.)
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Sales-domain agents, skills, and templates are physically relocated into a `packs/sales/` subtree with a manifest declaring contents and dependencies. **No install script change yet** — that is ISSUE-009. This issue is a pure relocation + schema definition so the boundary exists on disk and future install changes have a stable target.

#### Scope (In/Out)
- In:
  - Move sales agents (`account-researcher`, `champion-mapper`, `discovery-coach`, `meeting-synthesizer`, `proposal-writer`) under `packs/sales/agents/` via `git mv`.
  - Move sales skills (`account-brief`, `discovery-prep`, `followup`, `meeting-capture`, `proposal`) under `packs/sales/skills/` via `git mv`.
  - Move sales-only templates (`account_brief.md`, `discovery_plan.md`, `meeting_notes.md`, `proposal.md`, `sales_email_persona.md`, `sales_lessons.md`, `followup.md`) under `packs/sales/templates/` via `git mv`.
  - Write `packs/sales/manifest.yaml` listing the moved files with explicit paths (agents / skills / templates / optional settings.snippet.json) and a top-level `depends_on: [core]`.
  - Write `packs/sales/README.md` describing the pack purpose, which core skills it expects (`/prd`, `/kickoff`, `/issue`, `/sprint`), and that opt-in install is provided by ISSUE-009.
  - Write `packs/README.md` (root-level pack guide) documenting the manifest schema, the `depends_on` model, and the additive-only rule (packs never substitute core).
  - `scripts/validate_pack_manifest.py` — pure parser/validator with no install side effects. Validates: YAML well-formed, each listed file exists, `depends_on` references exist (only `core` for now), no duplicate entries across packs.
  - Unit tests for the manifest validator (4 cases: valid manifest, missing file, unknown dep, duplicate entry).
- Out:
  - `install_project.sh` / `install_user.sh` changes — ISSUE-009.
  - `merge_settings.py` extension — ISSUE-009.
  - README counts / Packs section in top-level README — ISSUE-005.
  - **Spin-off to a separate `claude-sales-kit` repo — deliberately not pursued.** This kit is a monorepo with install-time pack boundaries, not a transitional state toward multi-repo. Shared primitives (`/prd`, `/kickoff`, `/issue`, `/sprint`, hooks, templates, install scripts) are heavily reused by sales workflows; splitting them would require version-matrix management between repos and lose the ability to fix cross-cutting changes in a single PR. Revisit only if (a) sales evolves into a self-contained workflow that barely uses core, (b) audience/compliance forces a hard separation, or (c) release cadences diverge sharply.
  - Per-pack version pinning.
  - Deletion of sales code — this is a move, not a remove.

#### Acceptance Criteria (DoD)
- [ ] Given the repo, when `ls packs/sales/agents/ packs/sales/skills/ packs/sales/templates/` runs, then it shows exactly the moved entries listed above.
- [ ] Given `agents/` and `skills/` at the top level, when listed, then no sales-named entry remains there (move is complete, not duplicated).
- [ ] Given `packs/sales/manifest.yaml`, when `scripts/validate_pack_manifest.py` runs, then it exits 0 and prints the parsed file list.
- [ ] Given a manifest pointing to a nonexistent file, when validator runs, then it exits non-zero with the missing path named.
- [ ] Given a manifest with `depends_on: [nonexistent]`, when validator runs, then it exits non-zero naming the missing dep.
- [ ] Given `git log --follow packs/sales/agents/proposal-writer.md`, when run, then prior history at the old path is preserved.
- [ ] Given existing integration tests for agents/skills frontmatter, when run, then they still pass under the new layout (they should walk all directories, including `packs/`).

#### Implementation Notes
- Use `git mv` for every file so blame survives — never copy+delete.
- Manifest schema (documented in `packs/README.md`):
  ```yaml
  name: sales
  depends_on: [core]
  agents: [account-researcher.md, champion-mapper.md, ...]
  skills: [account-brief, discovery-prep, ...]
  templates: [account_brief.md, ...]
  settings_snippet: settings.snippet.json   # optional
  ```
- The validator is the single source of truth for the schema — ISSUE-009's install script imports/calls it rather than re-parsing.
- Status line (`cc-statusline.py`) and any other consumer that walks `agents/` must also walk `packs/*/agents/` after this move. Audit and fix in this issue (small grep job).
- Existing CONTRIBUTING.md and PRD docs may reference sales agents at the old path — grep and update.
- This issue does NOT touch the main README — ISSUE-005's job.

#### Tests
- [ ] Validator: valid manifest passes.
- [ ] Validator: missing file path fails with the path named.
- [ ] Validator: unknown `depends_on` fails with the missing dep named.
- [ ] Validator: duplicate entry across packs fails (future-proofing — for now sales is alone, but the rule should be active).
- [ ] Agent/skill frontmatter walker discovers entries under `packs/sales/`.
- [ ] `cc-statusline.py` runs without error when sales agents live under `packs/sales/`.

#### Rollback
`git revert` the move commit; the manifest validator and `packs/` directory become orphaned but inert. No installer behavior is changed yet (ISSUE-009 hadn't landed) so no user-facing regression.

---

### ISSUE-005: README sync — reflect actual counts + new positioning + post-sales-boundary layout
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30)
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-004 (file move must land before counts and Packs section are accurate), ISSUE-009 (install flag must exist before Installation section can document `--pack`)

#### Goal
`README.md` accurately reflects the post-boundary kit: correct agent/skill counts, sharpened positioning ("trustworthy code in collaboration → AI dev team control plane"), brainstorm/bizanalysis demoted to optional pre-PRD, sales pack documented as an opt-in pack with its own install flag, and a new **Team-scale usage** section explaining how teams adopt the kit at monorepo and polyrepo scale.

#### Scope (In/Out)
- In:
  - Update opening tagline + "Why claude-kit?" to match the new positioning.
  - Replace stale counts ("33 agents / 22 skills") with current values after ISSUE-004 split (core count + sales pack count separately).
  - Add a "Packs" section explaining core (default) vs sales (opt-in via `--pack=sales`).
  - Update agent table and skill table to mark sales entries clearly (or move to a sub-table inside the Packs section).
  - Demote `/brainstorm` and `/bizanalysis` to an "Optional pre-PRD" sub-section (still listed, but golden path starts at `/prd`).
  - Add a brief "Roadmap" subsection referencing ISSUE-001/002/003/006/007 as the upcoming control plane + spec layer (telemetry → eval → memory → spec/release).
  - Update Installation section to document `--pack` flag.
  - Sync Decision Tree to match (sales workflows either removed from main tree or routed via opt-in pack note).
  - **Team-scale usage section** documenting two adoption patterns and the rationale for NOT introducing a separate "team layer":
    - **Pattern (a) Monorepo**: engineering teams put services under `services/<name>/` in one repo; sales teams put accounts under `accounts/<company>/` in one repo. The repo IS the team boundary; the kit installs once at the root.
    - **Pattern (b) Virtual monorepo wrapper** (polyrepo teams): a top-level wrapper directory contains `.claude-kit/` + shared state (`issues.md`, `sprint_state.md`, `STATUS.md`) at its root, and each git repo lives as an immediate subdir (`auth-service/`, `gateway-service/`, ...). Per-service work routes to the right subdir; the wrapper itself is also a git repo with the service subdirs in `.gitignore`. Cross-reference ISSUE-008 for the code-level support.
    - **Why no separate "team layer"**: an additional layer would raise onboarding cost (more concepts, more install steps) without adding capability the subdirectory pattern doesn't already provide. The existing core+sales additive model + the wrapper pattern cover both adoption shapes. Document this explicitly so future contributors don't re-propose a "team pack".
- Out:
  - CONTRIBUTING.md rewrite (separate follow-up).
  - Translated versions / docs site.
  - Logo / branding refresh.
  - Sales pack's own README (lives in `packs/sales/README.md`, handled in ISSUE-004).

#### Acceptance Criteria (DoD)
- [ ] Given the updated README, when agent/skill counts are checked against `ls agents/ skills/` (excluding `packs/`), then the numbers match exactly.
- [ ] Given the README, when the opening section is read, then the words "trustworthy" and "control plane" (or Korean equivalents if bilingual) appear in the positioning paragraph.
- [ ] Given the Decision Tree, when followed top-to-bottom, then no sales-specific entry appears in the default engineering path; sales appears only under an explicit "Sales pack (opt-in)" branch.
- [ ] Given the Installation section, when read, then `--pack=core|sales|all` is documented with examples.
- [ ] Given the Roadmap section, when read, then it references ISSUE-001/002/003/006/007 without committing to dates.
- [ ] Given the Team-scale usage section, when read, then both patterns (monorepo, virtual monorepo wrapper) are shown with concrete directory examples, and the rationale for not adding a "team layer" is stated.

#### Implementation Notes
- Do not rewrite from scratch — surgical edits to preserve existing structure that already works (Core Use Cases, Workflow, Skill Orchestration sections).
- Counts: when ISSUE-004 lands, run `ls agents/ skills/ packs/sales/agents/ packs/sales/skills/` and use those numbers literally. Avoid hand-counting.
- "Roadmap" subsection should be 3 bullets max — telemetry / eval / memory, one sentence each. Link to the issue IDs, not to dates.
- Keep `docs/PRD_agent_system_v0.md` reference in Project Structure — that's a kit-internal PRD and stays.
- Verify badge counts at top of README (e.g., "530 tests passing") — re-run `pytest` and update if stale.

#### Tests
- [ ] Markdown link checker: no broken internal links in README after edit.
- [ ] Count assertion script: parses the README's claimed counts and compares to filesystem; fails if mismatch (consider adding as a CI check).
- [ ] Manual smoke: read the README top-to-bottom as a new user; confirm the engineering golden path is obvious within the first screenful.

#### Rollback
`git revert` the README commit. No code or config depends on README content, so revert is purely cosmetic.

---

### ISSUE-006: /spec skill — RFC pattern + Spec-Required metadata + non-sprint HOLD gate
- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-006.md
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — tech spec layer between PRD and implement for cross-team features)
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
A new `/spec` skill writes `docs/specs/SPEC-NNN.md` (Problem / Options ≥2 / Trade-offs / Decision / Migration / Rollback / Open Questions) for features flagged `Spec-Required: true`. Adds the metadata fields to the issue template, the conventions exception (2 PRs non-sprint vs 1 bundled PR sprint), and a non-sprint HOLD gate when invoked standalone without a SPEC for a required issue.

#### Scope (In/Out)
- In:
  - New `skills/spec/SKILL.md` reading the target issue from `issues.md` plus relevant context (`docs/architecture.md`, `docs/ux_spec.md`, related code via grep) and producing a SPEC document.
  - `templates/spec.md` with required sections: Problem / Options (≥2 named, each with measurable trade-off statements like "+20% write latency, -1 service dependency") / Decision / Trade-offs accepted / Migration / Rollback / Open Questions.
  - Issue template additions: `Spec-Required: true | false` (default false), `Spec: <path | none>`.
  - `scripts/validate_issues.py` enforces: if `Spec-Required: true` AND issue Status in `{doing, waiting, done}`, then `Spec:` must reference an existing file.
  - `/spec ISSUE-NNN` standalone invocation: if SPEC exists, refuses without `--rewrite`; with `--rewrite`, regenerates.
  - `/spec` with no arg: creates `docs/specs/SPEC-NNN.md` with auto-incremented number, no issue linkage.
  - Conventions block in `issues.md` documents the 2-PR-non-sprint / 1-PR-sprint exception.
  - Branch convention recorded: spec PR uses `issue/ISSUE-NNN-spec`, impl PR uses `issue/ISSUE-NNN`.
  - Unit tests for spec template renderer + `validate_issues.py` Spec-Required enforcement.
- Out:
  - `/implement` spec gate logic — ISSUE-007.
  - Auto-detection of "should this issue be Spec-Required" — ISSUE-007.
  - Spec-on-spec (RFC of RFC) recursion.
  - Backfilling SPECs for already-merged issues.

#### Acceptance Criteria (DoD)
- [ ] Given an issue with `Spec-Required: true` and no SPEC file, when user runs `/spec ISSUE-NNN`, then `docs/specs/SPEC-NNN.md` is written with all required sections, ≥2 named options, and each option carries an explicit measurable trade-off line.
- [ ] Given a SPEC already exists, when `/spec ISSUE-NNN` runs again without `--rewrite`, then the skill refuses with a message naming the existing file and the `--rewrite` flag; with `--rewrite` it proceeds.
- [ ] Given `/spec` with no argument, when run, then a SPEC with auto-incremented number is written and no issue field is mutated.
- [ ] Given an issue is `done` with `Spec-Required: true` but `Spec: none`, when `validate_issues.py` runs, then it exits non-zero with a clear error naming the issue.
- [ ] Given the `issues.md` conventions block, when read, then the 2-PR exception for non-sprint Spec-Required issues and the branch naming rule are documented.

#### Implementation Notes
- SPEC numbering matches the issue when linked (SPEC-007 ↔ ISSUE-007); ad-hoc SPECs use their own monotonic `SPEC-` counter independent of issues.
- The template renderer MUST reject options that lack a measurable trade-off statement (heuristic: at least one numeric or "+/-" comparator in the trade-off line). This is the slop-prevention guarantee that keeps SPECs useful.
- The skill must NOT modify any file beyond the SPEC itself and the target issue's metadata (to set `Spec:`).
- When sprint mode auto-runs `/spec` (per ISSUE-007), the commit message must be `docs(spec): SPEC-NNN — <decision summary>` so the bundled PR's history is readable.
- `/review` reads SPEC when present and adds a "Spec compliance" section to `review_notes.md` (this hook lives here, not in ISSUE-007, so review behavior follows the skill even without the implement gate).

#### Tests
- [ ] Template renders fully when all input fields present.
- [ ] Template renderer rejects an options list with fewer than 2 entries.
- [ ] Template renderer rejects an option missing a measurable trade-off line.
- [ ] `validate_issues.py`: `Spec-Required: true` + `done` + `Spec: none` → fail.
- [ ] `validate_issues.py`: `Spec-Required: true` + `doing` + `Spec: docs/specs/SPEC-007.md` (exists) → pass.
- [ ] `/spec` with no argument: produces auto-numbered SPEC.
- [ ] `/spec ISSUE-NNN` against existing SPEC: refuses; with `--rewrite`: proceeds.

#### Rollback
Delete `skills/spec/`, `templates/spec.md`, revert `validate_issues.py` and `issues.md` conventions changes. Existing SPECs under `docs/specs/` remain on disk (harmless) but are no longer enforced.

---

### ISSUE-007: /implement spec gate — sprint auto-run + non-sprint HOLD + signal detection
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — decision table for sprint vs non-sprint Spec-Required handling)
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-006

#### Goal
`/implement ISSUE-NNN` gates on the issue's `Spec-Required` field. In sprint mode, missing SPEC for a required issue triggers auto-run of `/spec` then continues (single bundled PR). In non-sprint mode, the same condition triggers a 3-way HOLD prompt. Signal-based recommendations (API/schema/migration keywords, estimate-at-cap, new dep) surface but never auto-block.

#### Scope (In/Out)
- In:
  - `/implement` Phase 0 (pre-context) gate logic implementing the full decision table from conversation 2026-06-13.
  - Mode detection: sprint mode = env `KIT_SPRINT_MODE=1` (set by `/sprint` before invoking `/implement`); otherwise non-sprint.
  - Signal scanner: regex/keyword detection on issue body for `api`, `schema`, `migration`, `breaking`, `protocol`, `데이터모델`, new-dependency mentions (`add`, `new package`, etc.); plus estimate-equals-cap (`Estimate: 1.5d`).
  - Sprint auto-mode: when `Spec-Required: true` and SPEC missing, invoke `/spec ISSUE-NNN` inline on the same branch, then continue with `/implement`. Single PR carries both the SPEC commit (`docs(spec): SPEC-NNN — ...`) and the impl commits.
  - Non-sprint HOLD: present a 3-way choice via `AskUserQuestion` — (1) run `/spec` now and resume; (2) flip `Spec-Required` to false with a recorded reason; (3) cancel.
  - `--skip-spec-gate` CLI flag bypasses both gates in any mode and emits a `spec_gate_bypassed` telemetry event (uses ISSUE-001 schema).
  - Telemetry events added: `spec_gate_triggered`, `spec_gate_hold`, `spec_gate_auto_ran`, `spec_gate_bypassed` — documented in `docs/telemetry_schema.md`.
  - Unit tests covering every row in the decision table.
- Out:
  - `/spec` skill itself — ISSUE-006.
  - Auto-mutation of `Spec-Required` based on signals (signals only recommend; they never write to the field unless the user picks option 2 in the HOLD).
  - Bundling spec + impl in non-sprint mode (non-sprint deliberately keeps the 2-PR pattern).

#### Acceptance Criteria (DoD)
- [ ] Given sprint mode (`KIT_SPRINT_MODE=1`) + `Spec-Required: true` + no SPEC, when `/implement` runs, then `/spec` is invoked first on the same branch, SPEC-NNN.md is created, and `/implement` continues without user prompt.
- [ ] Given non-sprint mode + same inputs, when `/implement` runs, then it HOLDs with a 3-way prompt. On (1) it runs `/spec` then resumes; on (2) it sets `Spec-Required: false` with the recorded reason in issue notes; on (3) it exits cleanly.
- [ ] Given `Spec-Required: false` + ≥1 signal detected + sprint mode, when `/implement` runs, then a recommendation event is logged to telemetry and execution proceeds without prompting.
- [ ] Given `Spec-Required: false` + ≥1 signal detected + non-sprint mode, when `/implement` runs, then the user is prompted (no default) and the choice is recorded.
- [ ] Given `--skip-spec-gate` in any mode, when `/implement` runs, then both gates are bypassed and a `spec_gate_bypassed` telemetry event is emitted.
- [ ] Given the decision table, when the test suite runs, then every row has a passing test.

#### Implementation Notes
- `KIT_SPRINT_MODE` is set by the `/sprint` skill (single-line export before invoking implement). Document in `skills/sprint/SKILL.md`.
- The HOLD prompt must use `AskUserQuestion`-style structured choice — do not parse free text.
- Sprint auto-run commit sequence: `docs(spec): SPEC-NNN — <decision summary>` (from `/spec`) → impl commits (from `/implement`). PR description must include a SPEC excerpt at the top.
- `/review` (from ISSUE-006) reads SPEC and adds "Spec compliance" findings; this issue does NOT modify `/review`.
- Signal scanner returns a list of `{signal, evidence}` pairs — the recommendation log includes this list verbatim so users can see WHY a spec was recommended.

#### Tests
- [ ] Decision table coverage: one test per row.
- [ ] Sprint auto-run produces a single PR with both spec commit and impl commits in correct order.
- [ ] Non-sprint HOLD: simulate user choices (1, 2, 3) and verify the resulting state transitions and on-disk effects.
- [ ] Signal scanner unit tests: api / schema / migration / breaking / protocol / cap-estimate / new-dep.
- [ ] `--skip-spec-gate` emits the bypass event regardless of mode.
- [ ] No prompt fires when `Spec-Required: false` and no signal hits.

#### Rollback
Revert `/implement` gate logic; the signal scanner and `--skip-spec-gate` flag become inert. `/spec` skill (ISSUE-006) continues to work standalone. No issue-metadata migration needed since `Spec-Required` defaults to false.

---

### ISSUE-008: Virtual monorepo wrapper — polyrepo team support
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30 — polyrepo team friction; deferred until measured)
- Priority: P2
- Estimate: 1.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-001 (telemetry signal needed before justifying this work)

#### Goal
Polyrepo teams can wrap multiple independent git repos in a top-level "virtual monorepo" directory that holds shared kit state (`issues.md`, `sprint_state.md`, `STATUS.md`) and the `.claude-kit/` installation at the wrapper root. Each service subdir stays an independent git repo. Per-service work routes to the right subdir automatically.

#### Scope (In/Out)
- In:
  - "Wrapper root" detection concept: walk upward from `pwd` to find the closest ancestor containing `.claude-kit/`. If that ancestor is distinct from `git rev-parse --show-toplevel`, it is the wrapper root; otherwise the layout is a normal single repo and wrapper-aware code falls back transparently.
  - Issue template field `Target-Service: <subdir-name | none>` (default none = single-repo behavior).
  - `scripts/worktree.sh` `--service <name>` flag: when set, the worktree is created at `<wrapper-root>/<service>/.worktrees/issue-NNN/` against that service's git repo; `gh pr create` runs in that service repo.
  - `scripts/list_services.sh`: enumerates wrapper-root immediate subdirs that contain `.git/` and prints their names.
  - `scripts/flock_edit.sh` corrected to lock files at wrapper root (issues.md, sprint_state.md, STATUS.md) regardless of which service subdir `pwd` is in.
  - `docs/wrapper_usage.md` documenting the structure with the `~/work/my-team/` example tree and the wrapper's own `.gitignore` rules (service subdirs ignored, kit state tracked).
- Out:
  - Auto-creating service git repos (user does this manually).
  - Cross-service git operations (each service PR is independent).
  - Migrating an existing monorepo into wrapper form.
  - Wrapper-level CI orchestration (out of scope for this MVP).

#### Acceptance Criteria (DoD)
- [ ] Given a wrapper-root layout with 3 service subdirs each holding `.git/`, when `scripts/list_services.sh` runs, then it lists exactly those 3 services and skips non-repo subdirs.
- [ ] Given ISSUE-NNN with `Target-Service: auth-service`, when `/implement` runs in wrapper mode, then the worktree is created at `<wrapper-root>/auth-service/.worktrees/issue-NNN/` and `gh pr create` is invoked in that service's repo.
- [ ] Given two concurrent `/implement` calls editing `issues.md` from different service subdirs, when both complete, then `issues.md` at the wrapper root contains both edits (flock at wrapper root, not at service-repo toplevel).
- [ ] Given a non-wrapper layout (`.claude-kit/` parent equals `git rev-parse --show-toplevel`), when wrapper-aware scripts run, then they fall back to today's single-repo behavior with no errors.
- [ ] Given `docs/wrapper_usage.md`, when read, then the directory example, the `.gitignore` rules, and the per-service work routing flow are all present.

#### Implementation Notes
- Wrapper-root detection lives in a single helper (`scripts/find_wrapper_root.sh` or Python equivalent) so every consumer uses the same logic. Tests live alongside.
- `Target-Service:` field default = none → routing helpers no-op → single-repo behavior preserved.
- This issue is **P2 and gated**: do not pick up until ISSUE-001 telemetry shows real polyrepo friction (e.g., a meaningful number of `flock` resolution errors or path mismatches from polyrepo users).
- Do NOT introduce a "team layer" concept — the wrapper directory is itself the team boundary; adding another abstraction would add onboarding cost without capability gain (rationale documented in ISSUE-005's Team-scale usage section).

#### Tests
- [ ] Wrapper-root detection: nested layout returns wrapper root; flat layout returns git toplevel; mixed cases handled.
- [ ] `list_services.sh`: skips subdirs without `.git/`; finds direct-child `.git/` dirs; ignores `.worktrees/` and similar.
- [ ] `worktree.sh --service`: worktree path correct; worktree registered in correct service repo.
- [ ] `flock_edit.sh`: lock file path resolves to wrapper root when running from a service subdir.
- [ ] Single-repo fallback: existing single-repo tests pass unchanged.

#### Rollback
Revert wrapper-root detection across scripts. `Target-Service:` becomes vestigial metadata that downstream code ignores. No file moves or data migrations are required.

---

### ISSUE-009: Install script --pack flag + merge_settings + tests
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; split from original ISSUE-004 — installer behavior layer on top of ISSUE-004's file move)
- Priority: P1
- Estimate: 1.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-004

#### Goal
`install_project.sh` and `install_user.sh` gain a `--pack=<core|sales|all>` flag (default `core`). They read each `packs/<name>/manifest.yaml` (using ISSUE-004's validator), enforce `depends_on`, and copy only the manifest-listed files. `merge_settings.py` merges pack-scoped `settings.snippet.json` after core's in a documented order. A migration note is printed when a legacy top-level sales path is detected.

#### Scope (In/Out)
- In:
  - `--pack=<name>` flag with values `core` | `sales` | `all` (extensible). Default `core`. Multiple `--pack` flags allowed but de-duplicated; selecting any non-core pack always includes core (because every pack has `depends_on: [core]`).
  - Install flow ordering: core first, then non-core packs in alphabetical order (deterministic). Settings overlay follows the same order.
  - `merge_settings.py` extended to merge `packs/<name>/settings.snippet.json` if present, with pack values **overriding** core values on key collision. Override policy documented in `packs/README.md`.
  - Error paths:
    - Unknown pack name → list available packs and exit non-zero.
    - Unsatisfied `depends_on` → name the missing dep and exit non-zero.
    - Manifest entry pointing at a missing file → name the path and exit non-zero (delegates to ISSUE-004 validator).
  - Re-install migration note: when a sales-named agent or skill is found at the legacy top-level path (`agents/account-researcher.md` etc.), print a one-line note telling the user to delete the old file (do NOT auto-delete).
  - Telemetry hook (uses ISSUE-001 schema): emit `install_pack` event per pack installed so adoption can be measured.
  - Integration tests over a tmpdir: default (no flag), `--pack=sales`, `--pack=all`, `--pack=unknown`, depends_on failure, settings collision, settings non-collision, legacy-path migration note.
- Out:
  - Pack uninstall (follow-up).
  - Per-pack version pinning.
  - Mid-session pack switching.
  - File moves themselves (ISSUE-004 owns this).
  - Top-level README updates (ISSUE-005).

#### Acceptance Criteria (DoD)
- [ ] Given a fresh tmpdir, when `bash install_project.sh` (no flag) runs, then `.claude/agents/` and `.claude/skills/` contain core entries only.
- [ ] Given `--pack=sales`, when run, then `.claude/` contains both core entries AND every sales pack entry listed in `packs/sales/manifest.yaml`.
- [ ] Given `--pack=all`, when run, then `.claude/` contains the union of every declared pack.
- [ ] Given `--pack=unknown`, when run, then the script exits non-zero and the error message lists the available packs.
- [ ] Given a manifest with `depends_on: [nonexistent]`, when install runs, then it exits non-zero and names the missing dep.
- [ ] Given core and sales each declaring an overlapping settings key, when `merge_settings.py` runs after install, then the merged settings file shows the pack value (sales) winning, and `packs/README.md` documents that this is the rule.
- [ ] Given a tmpdir with a legacy `agents/account-researcher.md` present, when install runs with default flag, then a one-line migration note is printed naming the legacy path; the file is NOT auto-deleted.
- [ ] Given the test suite, when run, then every existing test passes and every new install-flag test case passes.

#### Implementation Notes
- Use a tiny Python YAML parser (PyYAML — already an acceptable dep in the kit) rather than shelling out to `yq` to keep the install path dependency-light on fresh machines.
- Reuse ISSUE-004's `scripts/validate_pack_manifest.py` from the installer rather than re-implementing parsing.
- Symmetric handling in `install_user.sh` only if a user-level sales asset turns up during impl; otherwise document that user-level installs are core-only for now.
- The install_pack telemetry event lets ISSUE-001 measure adoption — without it we cannot prioritize future packs based on data.

#### Tests
- [ ] Default flag → core only, sales paths absent.
- [ ] `--pack=sales` → core + sales together (dependency satisfied).
- [ ] `--pack=all` → union of all declared packs.
- [ ] `--pack=unknown` → exits non-zero with usable error.
- [ ] Unsatisfied `depends_on` → exits non-zero, names missing dep.
- [ ] `merge_settings`: colliding keys → pack value wins, documented behavior.
- [ ] `merge_settings`: non-colliding keys → both present in output.
- [ ] Legacy-path migration note printed when `agents/account-researcher.md` exists at top level.
- [ ] `install_pack` telemetry event emitted for each pack installed.

#### Rollback
Revert install script changes. Old default ("install everything") was already replaced once by ISSUE-004's file move (no top-level sales files remain), so reverting THIS issue's installer changes simply makes the installer ignore packs entirely — a no-op for core, and sales becomes uninstalled but the files still exist under `packs/sales/`. Re-running with the reverted installer is safe.

---

### ISSUE-010: Pilot Gate hardening — separate-context critic + auto-cycle + neutral observation + specificity check
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — Phase 5A self-critique has sycophancy + leading-question + closed-loop + missing-specificity defects identified by external reviewer)
- Priority: P2
- Estimate: 1.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none (relies on `design-auditor` name, which ISSUE-013 explicitly preserves)

#### Goal
Phase 5A pilot critique is rebuilt to (1) precede judgment with a neutral observation pass, (2) run the visual critique in a **separate-context** `design-auditor` Task invocation, (3) add a product-specificity check requiring ≥3 details uniquely meaningful to this product/domain/user, and (4) enforce up to 3 automatic critique→patch→re-render cycles before the user gate fires.

#### Scope (In/Out)
- In:
  - Phase 5A Step 2 rewritten with 4 sub-steps:
    - **Step 2.0 — Neutral observation**: critic agent describes 5 visible facts from each pilot PNG **without referencing the design philosophy, signature move, aesthetic name, or archetype**. Output: `observations.md` per pilot. Banned vocabulary listed inline in the prompt.
    - **Step 2.1 — Separate-context critique**: invoke `design-auditor` via the Task tool (`subagent_type: design-auditor`) with the PNG + observations as input. The auditor does NOT inherit the generator's context. Returns a scored critique with evidence citing specific observations.
    - **Step 2.2 — Specificity check**: critique agent answers: "Name 3 details in this screen that ONLY make sense for THIS specific product/domain/user. Generic UI primitives don't count. If 0–1 → FAIL." Domain artifacts qualify (e.g., the literal_quote from ISSUE-012, domain-specific units, real entity names).
    - **Step 2.3 — Auto-correction cycle**: if any critique dimension fails OR specificity FAILs, the generator patches at the correct level (philosophy/tokens/CSS), re-renders, and the loop repeats. **Hard cap N=3 cycles.** After cycle 3, surface to the user with the cycle-by-cycle history.
  - Skill doc (`skills/uiux/SKILL.md`) updated Phase 5A section to reflect the 4 sub-steps; same change propagated to mobile and desktop variants.
  - Telemetry events (uses ISSUE-001 schema): `pilot_observation`, `pilot_critique`, `pilot_specificity`, `pilot_cycle_n`, `pilot_user_gate`, `pilot_degraded` (no-backend fallback).
  - **No-backend degraded mode**: if `screenshot_pilot.py` cannot capture, fall back to text-only critique reading the HTML source, with a `pilot_degraded` telemetry tag. **Never silently skip** the critique step.
  - Unit tests per sub-step prompt contract + cycle counter + degraded mode.
- Out:
  - Multi-direction parallel pilots (issue #1 in critique — deliberately deferred; reviewer's strongest call but conflicts with prior decision).
  - Token extraction inversion (issue #6 in critique — separate refactor scope).
  - Reference Anchor changes (ISSUE-012).
  - WebFetch correctness (ISSUE-011).

#### Acceptance Criteria (DoD)
- [ ] Given a pilot PNG, when Step 2.0 runs, then `observations.md` contains 5 facts and the banned-vocabulary lint (no `signature`, `aesthetic`, `archetype`, `philosophy` tokens) passes.
- [ ] Given observations + PNG, when Step 2.1 runs, then a Task invocation with `subagent_type: design-auditor` returns a structured critique; the critique's evidence field references at least one observation by index.
- [ ] Given Step 2.2, when the critique agent runs the specificity check, then it returns either exactly 3+ named product-specific details OR an explicit FAIL with a reason; never a vague pass.
- [ ] Given a failing critique on cycle 1, when Step 2.3 runs, then a patch is applied at one of {philosophy, tokens, CSS}, the pilot re-renders, and re-critiques. The cycle counter increments and stops at N=3.
- [ ] Given 3 cycles all failing, when the user gate fires, then the user sees the cycle history (what was tried each cycle and what still fails).
- [ ] Given no screenshot backend, when Phase 5A runs, then text-only critique runs with `pilot_degraded` telemetry tag — never a silent skip.
- [ ] Given existing Phase 5B tests, when run, then none regresses.

#### Implementation Notes
- The separate-context critic must be a real Task invocation — NOT an inline sub-prompt sharing the conversation. The `design-auditor` agent file already exists; ISSUE-013 sharpens its role but preserves the name.
- Step 2.0 prompt must explicitly list banned vocabulary; a simple regex post-check catches violations.
- Specificity FAIL: 0 or 1 named details = FAIL. Naming must be concrete (e.g., "the order ID 47.2-A in mono", "the unit '회' in the quantity selector") — not roles ("primary CTA", "user avatar").
- Hard 3-cycle cap is a backstop against runaway auto-correction. Telemetry surfaces 3-cycle-fail rates so we can later tune the patch quality.
- Patch level inference: dimension-based — if color/scale fails → tokens; if vocabulary/voice fails → philosophy; if composition fails → CSS. Document the mapping.

#### Tests
- [ ] Step 2.0 banned-vocabulary regex enforcement.
- [ ] Step 2.1: Task tool invoked with correct `subagent_type` and inputs.
- [ ] Step 2.2 FAIL on 0/1 details; PASS on 3+ properly-named details.
- [ ] Cycle counter increments through 3, hard-stops at 3.
- [ ] User gate fires with cycle history when 3 cycles fail.
- [ ] Degraded mode emits `pilot_degraded` event and runs text-only critique without raising.
- [ ] All three uiux skills (web/mobile/desktop) updated consistently.

#### Rollback
Revert Phase 5A changes in `skills/uiux/SKILL.md` (+ mobile/desktop). Step 2 reverts to single-pass self-critique. Telemetry events become inert. No data migration.

---

### ISSUE-011: Kill WebFetch reference fabrication — image-grounded references only
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — WebFetch returns parsed text only; asking the model to extract hex values "from a Dribbble URL" via WebFetch is fabrication regardless of the "(indirect)" label)
- Priority: P1
- Estimate: 0.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Phase 2 step 6.5 (Reference Anchor research) stops using WebFetch to "read" visual references. References must arrive as actual pixels — either user-provided image inputs or headless-captured screenshots of a page URL — and the Reference Anchor step is **skipped explicitly with a warning** when no image is available, never filled in with WebFetch text.

#### Scope (In/Out)
- In:
  - Phase 2 step 6.5 rewritten with two input paths:
    - **Path (a) — user-provided images**: 1–3 image URLs or local paths; `/uiux` reads them via the Read tool (image input) and extracts visual facts from actual pixels.
    - **Path (b) — auto-captured pages**: if the user provides a non-image URL (HTML page), invoke `scripts/capture_reference.py <url>` to headless-capture the page to PNG, then Read the PNG.
  - **Path (c) — neither available**: Reference Anchor step is **skipped entirely** with a one-line warning to the user explaining what to provide. Design philosophy proceeds without an anchor section.
  - New `scripts/capture_reference.py`: thin wrapper over `screenshot_pilot.py` capture logic. Takes URL + output path, saves to `docs/references/<slug>.png`.
  - Remove the "(indirect)" labeling from Phase 2 step 6.5 in `skills/uiux/SKILL.md` and mobile/desktop equivalents — the category does not exist anymore.
  - `templates/design_philosophy.md` updated: each cited anchor MUST reference an image file path under `docs/references/`. Empty `cues_to_adopt` is acceptable (means anchor step skipped); fabricated cues are not.
  - Unit tests for capture wrapper + the skip-with-warning behavior + grep test ensuring no WebFetch call remains in any uiux skill for the purpose of reference description.
- Out:
  - Reference Anchor tuning (5 → 2-3 + literal quote) — ISSUE-012.
  - Pilot Gate critique restructuring — ISSUE-010.
  - Interview skip-path hardening (issue #8 in critique — not requested).

#### Acceptance Criteria (DoD)
- [ ] Given user provides 2 image URLs, when Phase 2 step 6.5 runs, then both images are Read directly and extracted facts cite actual image content.
- [ ] Given user provides an HTML page URL, when Phase 2 runs, then `capture_reference.py` is invoked, the PNG is saved under `docs/references/`, and Read is called on the PNG (not on the URL).
- [ ] Given neither images nor URLs are provided, when Phase 2 runs, then the Reference Anchor step prints a one-line warning naming what to provide and proceeds without anchor section.
- [ ] Given `grep -RE 'WebFetch' skills/uiux/ skills/mobile-uiux/ skills/desktop-uiux/`, when run after this issue lands, then no result mentions reference description (WebFetch may remain for unrelated purposes — must be re-verified by hand).
- [ ] Given `docs/references/` is populated, when `design_philosophy.md` is validated, then every cited anchor points to an existing file under that directory.

#### Implementation Notes
- `screenshot_pilot.py` already has a headless capture backend probe — reuse, do not duplicate.
- The skip warning must be explicit ("Reference Anchor skipped: no image provided. Pass 1–3 image paths or a page URL to populate this section.") — silent fallback is the bug we are fixing.
- If no screenshot backend is available, `capture_reference.py` exits with a clear "install Playwright OR provide image paths directly" message. Pairs with ISSUE-010's degraded mode.
- Mobile and desktop uiux skills have analogous step — patch all three SKILL.md files in this single PR.

#### Tests
- [ ] Image-URL path: 2 image URLs → both Read as images, extracted facts present.
- [ ] Page-URL path: HTML URL → captured to PNG → Read invoked on PNG.
- [ ] Skip path: no inputs → warning printed, no WebFetch invoked, anchor section absent.
- [ ] Backend missing: `capture_reference.py` exits with install hint.
- [ ] All three uiux skills updated; reference-description WebFetch usage gone.

#### Rollback
Revert SKILL.md changes in the three uiux skills. Delete `scripts/capture_reference.py`. Reference Anchor returns to the WebFetch (indirect) flow — this restores the fabrication issue, so rollback should be a last resort.

---

### ISSUE-012: Reference Anchor tuning — 2-3 strong cues + 1 literal quote
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — 5 anchors create averaging pressure; a single literal quote injects product-specific concreteness at Phase 2)
- Priority: P2
- Estimate: 0.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-011 (image-grounded references must land first so anchor citations point to real images, not WebFetch text)

#### Goal
Phase 2's Reference Anchor section is reduced from "5 cues to adopt + 3–5 to avoid" to "2–3 strong cues + 1 mandatory literal quote + 3–5 anti-cues". The literal quote is a specific word, number, or glyph from the brand or domain that MUST appear verbatim in the prototype.

#### Scope (In/Out)
- In:
  - Phase 2 step 6.5 output spec updated:
    - 2–3 **strong** cues to adopt, each with image evidence (from ISSUE-011's image-grounded path).
    - 1 **literal quote** — a specific word, number, or glyph from the brand/domain. Examples: "the word *조용한* set in 168pt Fraunces in the hero", "the order ID 47.2-A shown in mono", "the unit *회* in the quantity selector".
    - 3–5 cues to **avoid** stays as-is (anti-references already worked).
  - `templates/design_philosophy.md` gains `literal_quote:` field that must be populated when Phase 1.5 interview was NOT skipped.
  - Validator (called from Phase 5A pilot gate): if `literal_quote:` is empty AND Phase 1.5 was not flagged as skipped, fail with a message naming the missing field.
  - Verbatim-render check: at Phase 5B exit, grep `prototype/screens/*.html` for the literal string; if absent, fail with a pointer to which screen should include it.
  - ISSUE-010's specificity check (Step 2.2) treats the literal_quote as 1 of the 3 required product-specific details — never sufficient alone (still need 2 more domain-grounded details).
  - Same change in mobile + desktop uiux SKILL.md.
  - Unit tests for anchor count, literal_quote presence, verbatim render.
- Out:
  - Image grounding mechanism (ISSUE-011).
  - Pilot Gate restructuring (ISSUE-010).
  - Interview skip-path hardening (#8 — not requested).

#### Acceptance Criteria (DoD)
- [ ] Given Phase 2 runs with image-grounded references available, when complete, then `design_philosophy.md` has exactly 2–3 strong cues, exactly 1 literal_quote, and 3–5 anti-cues.
- [ ] Given `literal_quote:` empty AND Phase 1.5 not skipped, when Phase 5A gate runs, then it fails naming the missing field.
- [ ] Given a non-empty literal_quote, when Phase 5B completes, then the literal string appears verbatim in at least one HTML file under `prototype/screens/`.
- [ ] Given ISSUE-010 Step 2.2, when it evaluates a pilot, then the literal_quote counts as exactly 1 of the required 3 product-specific details (not 0, not 2+).
- [ ] Given mobile + desktop variants, when their pilots run, then the same literal_quote requirement applies and the verbatim check covers all platform prototypes.

#### Implementation Notes
- Literal quote must be a string the prototype can render verbatim — word, short phrase, number, or glyph. Reject abstract concepts ("luxury", "trust") in a soft-fail with a hint about concreteness.
- The verbatim grep is over rendered HTML, not source templates — easier to verify and stricter (ensures the string actually appears in user-facing output).
- Anti-cues unchanged at 3–5: anti-references work in the current design and removing pressure there is not requested.
- Pair with ISSUE-010: when both ship, the specificity check has a concrete artifact (literal_quote) to lean on for one of its 3 required details.

#### Tests
- [ ] Anchor count enforcement: 0/1/4/5 strong cues → fail; 2–3 → pass.
- [ ] Literal quote presence: empty + interview not skipped → fail with field named.
- [ ] Literal quote presence: empty + interview skipped → pass with skip flag honored.
- [ ] Verbatim render check: literal_quote absent from all prototype HTML → fail with screen names suggested.
- [ ] ISSUE-010 specificity-check integration: literal_quote counted as 1 detail (not 0, not 2+) when present.

#### Rollback
Revert Phase 2 output spec, restore 5-cues template. Delete `literal_quote:` field validator and verbatim-render check. ISSUE-010's specificity check continues working without the literal-quote bonus (specificity still requires 3 domain-grounded details, just not bootstrapped by an explicit anchor).

---

### ISSUE-013: Consolidate ui-reviewer / design-auditor agents — sharpen role boundaries
- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — current ui-reviewer and design-auditor have overlapping prerequisites and checklist scope)
- Priority: P2
- Estimate: 1d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
`design-auditor` and `ui-reviewer` agents are refactored so that `design-auditor` owns **system-level audit** (philosophy, tokens, components at the system level, cross-platform alignment) and `ui-reviewer` owns **per-screen UI audit** (state coverage, copy compliance, token USAGE in implementation, accessibility at the implementation level). Overlapping checklist items are removed. The `design-auditor` name is preserved so ISSUE-010's Pilot Gate wiring is unaffected.

#### Scope (In/Out)
- In:
  - Open-section rewrite in both `agents/design-auditor.md` and `agents/ui-reviewer.md` declaring the role boundary explicitly with a mirrored "Owned by this agent / owned by the other" table.
  - **design-auditor scope** (owns):
    - Token consistency (color/typography/spacing/radius scales)
    - Component completeness at the SYSTEM level (does `design_system.md` define every component referenced by wireframes?)
    - Cross-platform alignment (web/mobile/desktop token consistency)
    - Philosophy compliance (does the system reflect the stated philosophy + signature move?)
    - Outputs `docs/design_audit.md`
  - **ui-reviewer scope** (owns):
    - Per-screen state coverage (default / loading / empty / error)
    - Copy compliance against `copy_guide.md`
    - Token USAGE in implementation (hex literals or magic numbers in HTML/CSS → flag)
    - Accessibility at the IMPLEMENTATION level (focus rings, ARIA, touch targets in code)
    - Outputs `docs/ui_review_notes.md`
  - Remove every duplicated checklist item from each agent (the consolidation: each category belongs to exactly one agent).
  - Cross-link: each agent file mentions the other and which categories live there.
  - Update Phase 5A (ISSUE-010 wiring) to call `design-auditor` for system-level critique and `ui-reviewer` for per-screen critique — two distinct concerns at different inputs.
  - Update `docs/design_audit.md` + `docs/ui_review_notes.md` templates if they exist; otherwise create per-output templates documenting the new ownership.
  - Non-overlap unit test: feed the same synthetic fixture to both agents and assert disjoint flagged-category sets.
- Out:
  - Renaming either agent (NOT done — ISSUE-010 wires to the `design-auditor` name).
  - Merging both into a single agent (deliberately rejected — two distinct concerns at different abstraction levels).
  - Adding new audit categories beyond the existing ones.

#### Acceptance Criteria (DoD)
- [ ] Given the two agent files after this issue, when their checklist categories are diffed, then no category appears in both (set intersection = ∅).
- [ ] Given a synthetic project with a missing token reference in `design_system.md`, when `design-auditor` runs, then it flags the missing token; when `ui-reviewer` runs in isolation, then it does NOT flag it (out of scope for that agent now).
- [ ] Given a synthetic project with a missing loading state in `prototype/screens/list.html`, when `ui-reviewer` runs, then it flags the missing state; when `design-auditor` runs, then it does NOT (out of scope).
- [ ] Given Phase 5A in ISSUE-010, when it invokes critics, then both `design-auditor` (system input) and `ui-reviewer` (screen input) are invoked with distinct prompt contexts.
- [ ] Given the existing test suite, when run, then no test for either agent regresses.

#### Implementation Notes
- The `design-auditor` name stays — ISSUE-010 wires Phase 5A's separate-context critic to that name specifically.
- The ownership table at the top of each file must be mirrored — a contributor reading either agent file sees the same partition.
- The non-overlap test is implemented by feeding the same synthetic fixture (a tiny project with one token-level bug + one screen-level bug) to both agents and comparing their flagged-category sets; they should be disjoint.
- This issue does NOT block ISSUE-010; both can proceed in parallel as long as the `design-auditor` name is preserved (which is a hard scope rule here).

#### Tests
- [ ] Category-set diff: design-auditor categories ∩ ui-reviewer categories = ∅.
- [ ] Token-mismatch synthetic: design-auditor catches it, ui-reviewer doesn't.
- [ ] Missing-state synthetic: ui-reviewer catches it, design-auditor doesn't.
- [ ] Cross-link: each agent's doc mentions the other by name + categories.
- [ ] No regression in existing per-agent tests.

#### Rollback
Revert both agent files. Both agents resume with overlapping checklists (today's behavior). ISSUE-010 continues to work because the `design-auditor` name is preserved across this issue's lifecycle — rollback does not break wiring.
