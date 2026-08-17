# Changelog

All notable changes to claude-dev-kit. Versions are the plugin `version` field;
release tags are `claude-dev-kit--v<version>`.

## Unreleased

## 0.5.0 — 2026-08-17

Brownfield design support. The three uiux skills could only ever *create* a
design; they can now *read* the one a codebase already ships and extend it.

### Added
- **`extend` mode across `/uiux`, `/mobile-uiux`, and `/desktop-uiux`.** Each
  skill globbed existing UI files at Phase 1 and then discarded the reading —
  Phase 2 unconditionally committed to a new aesthetic and the pilot gate
  stamped a new Signature Move onto every screen. A project with a shipping UI
  and no Figma file had no path to "read the design that exists, then add
  screens that match", and running the skill anyway fought the codebase because
  existing patterns matching a listed AI Tell got swept out at Phase 5.5.
  Detection now proposes a mode and the user decides; modes never switch
  silently, and with no UI detected the `create` path is unchanged.
  (ISSUE-054, SPEC-054, PR #89)
- **`design-scanner` agent** (roster 32 → 33) — one platform-parameterized
  extraction agent, read-only by tool set (`Read, Glob, Grep`), carrying three
  source maps over one shared method: web CSS custom properties /
  `tailwind.config.*` / CSS-in-JS, React Native `StyleSheet` + `src/theme/`,
  and Electron renderer CSS + `src/theme/`. Provenance is non-negotiable:
  `[CONFIRMED]` requires a `file:line`, `[INFERRED]` requires a stated reason,
  and values are never invented. A codebase too thin to extract from returns
  `extraction_verdict: insufficient` rather than a padded system, and the
  Signature Move is derived by recurrence count or honestly reported as
  `none found` — a fabricated one would silently redesign the host product.
  (ISSUE-054, PR #89)
- **Overwrite guard on the extracted design system doc.** `extend` halts before
  writing when `docs/design_system[_mobile|_desktop].md` already exists and
  offers overwrite / write-alongside (`.extracted.md` plus a diff summary) /
  cancel, quoting the file's line count and last-modified date. A
  hand-maintained design system is the one artifact this mode can destroy, and
  "it's in git" is not treated as consent. (SPEC-054 open question 1, PR #89)
- **Slop calibration in the Anti-AI-Slop rules**, harvested from a comparison
  against the official `frontend-design` plugin: the three AI-design clusters
  currently produced regardless of subject (cream/serif/terracotta,
  near-black + acid accent, broadsheet hairline), banned as *defaults* rather
  than as choices; a self-similarity check before locking a design plan; and a
  CSS selector-specificity rule for web and the Electron renderer.
  Landed as a shared `{{SLOP_CALIBRATION}}` fragment plus three guarded agent
  chunks, so the three uiux skills and their developer agents cannot drift.
  (PR #86)

### Changed
- **`Brief overrides:` resolves a standing contradiction in the slop rules.**
  The "Specific AI Tells" header already allowed a brief to call for a banned
  pattern, while the Phase 5.5 sweep enforced zero tolerance — the two
  disagreed. Brief-pinned directions now win, recorded as `Brief overrides:`
  bullets in `docs/design_philosophy.md`, and each skill's AI Tell sweep exempts
  exactly the recorded tells and no others. An unrecorded violation is still a
  violation. `extend` mode reuses this seam so the sweeps stop rewriting the
  host product's own conventions. (PR #86, PR #89)

## 0.4.0 — 2026-08-12

### Added
- Documented the `KIT_ALLOW_BROWSER_INSTALL` (ISSUE-049) and
  `KIT_SPRINT_QUEUE_GH_TIMEOUT` (ISSUE-052) behaviour-control env knobs in
  README.md (new "Behaviour-control environment variables" subsection) and
  docs/troubleshooting.md, alongside the existing `KIT_CHECKPOINT_TEST_TIMEOUT`
  documentation. A drift-guard test (`tests/test_env_knob_docs.py`) fails if a
  knob is referenced in code but absent from both docs. (ISSUE-053, PR #85)
- Made the sprint queue crash-recovery aware of already-merged PRs. A ship-phase
  interruption (API/spend limit) between the squash-merge and the post-merge smoke
  checkpoint used to leave an issue at sprint_state phase `reviewed`/`shipping` while
  its PR was already merged; `sprint_queue.py next-action` re-proposed SHIP (risking a
  double-merge). It now probes the PR merge state (`gh pr view --json state,mergedAt`,
  timeout-guarded via `KIT_SPRINT_QUEUE_GH_TIMEOUT`, cached, `--no-check-merged` opt-out)
  and emits a new **FINALIZE** action (smoke + registry only) for already-merged reviewed
  issues — never a re-merge. An idempotent ship-merge guard (`ship-merge-decision`
  subcommand / `ship_merge_decision()`) makes the ship merge step a no-op when the PR is
  already merged. Wired end-to-end (queue → sprint orchestrator routing + team-lead
  FINALIZE handler → ship SKILL guard). Degrades gracefully when `gh` is
  missing/unauthenticated/offline (phase-only decision + logged warning, never crashes).
  (ISSUE-052, PR #83)
- Added unit tests for six previously untested checkpoint-gate scripts — the
  Figma visual-diff family (`verify_visual_diff.py`, `verify_computed_styles.py`,
  `verify_structural_match.py`, `verify_layout.py`, `generate_figma_css.py`) and
  the `validate_frontmatter.py` CI gate. Tests run without Chromium or network
  (browser boundaries mocked; synthetic PNG/JSON fixtures under
  `tests/fixtures/figma/`), pin both visual-diff thresholds (1% same-renderer,
  5% Figma-PNG fallback) so silent drift fails, and lift combined statement
  coverage of the six scripts to ~69% (each non-zero). (ISSUE-045, PR #73)

### Changed
- Deduplicated the UI/UX design-philosophy boilerplate that was copy-pasted across
  the three `uiux` / `mobile-uiux` / `desktop-uiux` skill templates and their three
  developer agents. The shared text now lives once as a canonical fragment in
  `scripts/fragments.py`, resolved into the skill templates via `{{DESIGN_PHILOSOPHY}}`
  / `{{DESIGN_PHILOSOPHY_CHECKPOINT}}` tokens (alongside `{{PREAMBLE}}`); platform
  deltas stay inline. The static agent copies are held in sync by a drift-guard
  test (`tests/test_design_fragments.py`) that names any out-of-sync agent file.
  Regenerated `SKILL.md` output is semantically identical to before (mobile/desktop
  byte-identical; a few accidental wording divergences unified). (ISSUE-041, PR #72)

### Removed
- Removed four dead scripts and their orphaned tests — `ensure_permissions.py`
  and `ensure_gh.sh` (zero callers), `kit_root.sh` (referenced only by its own
  test; wrappers inline their own root resolution), and
  `lint_skill_cache_order.py` (wired to neither CI nor any skill; deleted per
  the repo-audit default rather than wired into `ci.yml`). Gitignored the
  `.claude/run/` session-telemetry subpath (only `run/`; `.claude/` stays
  visible) and added an ISSUE-027-style grep guard
  (`tests/test_dead_script_removal.py`) that blocks re-references to the removed
  names and asserts no tracked `__pycache__`/`.pyc`. (ISSUE-043, PR #68)

### Fixed
- De-conflict the parallel-review `docs/.review` scratch path. The review layer's
  fixed-path scratch artifacts (`code-review.md`, `findings.json`, `minimality.md`,
  `security-review.md`) were tracked, so parallel review branches merging in
  sequence conflicted on exactly these files every sprint (PRs #58/#64/#65/#72).
  Fix (option b): gitignore `docs/.review/` and untrack the scratch — it is
  regenerated and consumed within a single `/review` invocation (the canonical
  committed record stays `docs/review_notes/ISSUE-XXX.md`); no checkpoint reads it
  from a commit. A guard test asserts the path is ignored and no scratch remains
  tracked. (ISSUE-051, PR #81)
- Lint the README agents-table Tools/Effort cells against agent frontmatter.
  A new row-by-row test in `tests/test_readme_consistency.py` compares each
  row's Tools (set-equal, normalized) and Effort cell against the corresponding
  `agents/*.md` frontmatter, naming any offending row, so future drift fails the
  build. Reconciled the drift the test surfaced (frontmatter is the oracle):
  `brainstormer`/`business-analyst` dropped spurious `WebSearch, WebFetch`;
  `ui-reviewer` and `a11y-auditor` gained the missing `Bash`; `design-auditor`
  dropped spurious `Edit, Write`. (ISSUE-050, PR #79)
- Gated the Figma visual-diff browser auto-install behind an explicit opt-in.
  `_check_playwright()` in `verify_visual_diff.py` and `verify_computed_styles.py`
  shelled out to `pip install playwright` + `playwright install chromium`
  (~180s, network) on any import-failure path — a review/CI gate silently
  mutating its env and reaching the network. The heavy provisioning now runs
  only when `KIT_ALLOW_BROWSER_INSTALL=1`; unset, the gate reports "browser
  unavailable" to stderr and returns via the existing skip/degrade path. The
  no-browser-at-collection lazy-import guarantee is preserved. (ISSUE-049, PR #78)
- Scoped the implement-phase checkpoints (`verify_implement_tests_written`,
  `verify_implement_red`, `verify_implement_code`) to the branch's own delta.
  They diffed the worktree against `main` directly, so a worktree built on a
  stale `main` surfaced files a newer `main` added/deleted after the fork point
  (absent from the worktree tree) and `_has_real_tests` manufactured a phantom
  hollow-test FAIL (ISSUE-041/044 hit this). Now they diff against
  `git merge-base HEAD main` and intersect the classified set with files that
  exist in the worktree, falling back to the old behavior when the fork point
  is unresolvable. (ISSUE-048, PR #77)
- CI now fails loudly on dependency-install problems and runs under one
  consistent toolchain: `ci.yml` migrated from pip to uv (`astral-sh/setup-uv`
  + `uv sync --locked --extra dev`, every step via `uv run`), dropping the
  `2>/dev/null || true` swallow so a broken dev-extras spec fails the job; the
  dead `asyncio_mode = "strict"` config and unused `pytest-asyncio` dep were
  removed (no more PytestConfigWarning) and `uv.lock` regenerated.
  `gate_server.sh` now starts the server in its own process group (`set -m`)
  and its cleanup trap signals the whole group (graceful TERM then KILL,
  best-effort so the 124/125/passthrough exit-code contract is preserved), so
  forking servers no longer leak orphans. (ISSUE-044, PR #70)
- `verify_checkpoint.py` test-phase gates no longer false-fail on multi-minute
  suites: the implement `red`/`test` and ship `smoke` subprocess timeouts are
  env-configurable via `KIT_CHECKPOINT_TEST_TIMEOUT` (seconds; default 600,
  previously hard-coded 60s/120s). A RED-phase run that hits the timeout
  (exit 124) is now reported as an inconclusive FAIL instead of being
  mistaken for a genuinely failing suite. (ISSUE-046, PR #54)
- `verify_gates.py`'s blocking `unit` gate no longer false-fails on
  multi-minute suites: both pytest/npm subprocess timeouts (previously
  hard-coded 120s) honor the same `KIT_CHECKPOINT_TEST_TIMEOUT` env var
  (seconds; default 600) as `verify_checkpoint.py`. Also isolated two
  `verify_implement_test` tests that left the gate-runner seam unmocked
  and recursively spawned the full pytest suite inside itself.
  (ISSUE-047, PR #56)
- `/review` skill steps are now a single strictly increasing sequence: the
  duplicated 3.8–3.10 cluster (ui-review/design-audit/a11y) is renumbered to
  3.11–3.13 and synthesize/merge-audit shift to 3.14/3.15, so the synthesis
  step's "Figma 3.5–3.10" cross-reference is unambiguous. The brainstorm
  degraded path now names `docs/references/research/` explicitly instead of
  "snapshot directory". A step-number monotonicity regression guard was added.
  (ISSUE-036, PR #57)
- The SessionStart hook no longer bakes version-pinned plugin-cache paths
  into the contributor-mode instruction it injects into session context.
  The instruction now defers path resolution to the Kit Script Root shown
  in the active skill preamble, so it survives plugin updates and cache GC
  (no ENOENT, no silently stale `contributor_report.py`); standalone-layout
  behavior is unchanged. (ISSUE-037, PR #58)
- The autotest PostToolUse hook no longer re-walks the whole tests tree on
  every Write/Edit: related-test lookups use a disk-persisted module-to-test
  index under `.claude/run/` (invalidated by tests-dir mtime scan; warm hits
  re-validated on read so a poisoned or stale cache can never execute
  non-test paths), and repeat edits to the same module within the debounce
  window skip identical passing runs — failures are never debounced into
  silence. Behavior knobs (MAX_RELATED_TESTS, timeouts, block-on-failure)
  unchanged; corrupt/missing cache rebuilds fail-soft. (ISSUE-038, PR #59)
- The `secret_guard` and `dangerous_command_guard` hooks no longer traceback
  on malformed hook stdin: the JSON parse is guarded (invalid JSON, empty
  stdin, and valid-JSON-but-non-dict payloads all covered), and on parse
  failure the guard skips loudly — a one-line stderr diagnostic
  (`<guard>: malformed hook payload — guard skipped`) and exit 0 — instead
  of a silent fail-open traceback. stdout stays a pure JSON decision channel
  and blocking semantics are unchanged; an in-file comment documents the
  stdout-JSON blocking mechanism and the `|| true` / exit-code-2 footgun.
  (ISSUE-039, PR #63, merged cd7511d)
- The `/sprint` skill now sets `disable-model-invocation: true`, closing
  the 2026-08-10 repo-audit gap where the heaviest autonomous orchestrator
  (implements, reviews, and ships every backlog issue) was the only
  repo-mutating skill the model could auto-invoke without an explicit
  user command. Sprint is now explicit-user-invocation only, matching
  implement/review/ship/kickoff/scan; a frontmatter lint test
  (tests/test_orchestrator_disable_model_invocation.py, 6 cases) guards
  the invariant for all repo-mutating orchestrators.
  (ISSUE-042, PR #64, merged f254227)
- README.md no longer drifts from shipped reality: version pin dropped in
  favor of the `VERSION` file, agent roster corrected to 32 with the three
  auditor agents added to the table, stale model-mix line replaced with the
  inherit-model + effort-tier description, retired `.claude-kit/` submodule
  install diagrams replaced with plugin-first layouts, and a /spec Usage
  section added. A consistency test suite (tests/test_readme_consistency.py)
  guards version, roster count, and layout claims against future drift; the
  Tests badge was reconciled to the canonical dev-extras count (1190).
  (ISSUE-040, PR #65, merged 5990c93)

## 0.3.0 — 2026-08-09

### Removed
- **Sales pack removed entirely** — the `claude-dev-kit-sales` plugin, the whole
  `packs/` subtree (5 agents, 5 skills, 7 templates, manifest), `docs/sales-pipeline.md`,
  `templates/poc_results.md`, and `scripts/find_shared.sh`. It saw no real use and
  only added complexity to the kit.
- **Pack infrastructure removed with it** (sales was the only pack):
  `scripts/validate_pack_manifest.py` + its tests, the CI pack-manifest step,
  the marketplace `claude-dev-kit-sales` entry, and all `packs/*/` discovery
  globs in `gen_skills.py`, `validate_frontmatter.py`, and the lint tests.
- README/docs no longer document packs: install commands, the Packs section,
  sales team-scale patterns, and the sales rows in `docs/README.md` are gone.

### Migration
- New installs simply won't see `claude-dev-kit-sales` in the marketplace after
  `/plugin marketplace update claude-dev-kit`.
- If you had it installed, remove it manually: `claude plugin uninstall claude-dev-kit-sales`.
  Historical releases remain available at the `claude-dev-kit-sales--v*` tags.

## 0.2.1 — 2026-07-26

- Sync the root `VERSION` file with the plugin version (it was left at 0.1.0
  by the 0.2.0 release, breaking the CI version-match test and the
  `kit_update_check` local/remote comparison).

## 0.2.0 — 2026-07-26

The "harness fits modern Claude Code" release: the kit now installs purely as a
Claude Code plugin, delegates to platform capabilities where they're stronger,
and trims harness overhead that no longer earns its keep.

### Platform & install
- **Plugin is the only install path.** The bespoke `install_project.sh` +
  symlink installer is removed; install via `/plugin install claude-dev-kit@claude-dev-kit`
  (ISSUE-027). Skills are namespaced — `/claude-dev-kit:implement`, etc.
- **Scripts resolve under plugin install** via `${CLAUDE_PLUGIN_ROOT}` load-time
  substitution — no files copied into your project (ISSUE-035). Also fixed a
  manifest bug that was silently dropping skill frontmatter.
- **Removed the passive `WorktreeCreate` hook** — it's a creator contract that
  broke native worktree creation for plugin users (ISSUE-027).

### Behavior changes to know about
- **Checkpoints are two-tier** (ISSUE-031): existence checks (issue/worktree/
  code/registry/push/pr) are now **advisory** (report + continue), while
  behavior gates (tests, TDD red, hollow-test, Figma suite) stay blocking.
- **Review lessons moved to native memory** (ISSUE-033): `/review` records
  preventable patterns in Claude Code's persistent memory; the never-used
  `docs/review_lessons.md` registry is retired (existing files are inert).
- **Agents inherit the session model** (ISSUE-030): no more per-agent model
  pins. Pin once at the project/session level for deterministic deploys.
- **/review, /brainstorm, /bizanalysis delegate to platform skills** when
  available (`/code-review`, `/security-review`, `/deep-research`), with a
  degraded fallback (ISSUE-029).
- **4 unused persona agents absorbed** into their skills (ISSUE-034); roster 32.

### New
- **Run telemetry** (ISSUE-001): shape-only `.claude/run/events.jsonl` +
  `scripts/trace_query.py summary`.
- **SessionStart hook** runs kit checks once per session; skill preambles
  slimmed 56% (ISSUE-032).
- **Review-quality eval** (ISSUE-002): optional non-blocking `/ship` step runs
  an LLM-as-judge over review notes via `claude -p` (no separate billing).

## 0.1.0

Initial kit — 32 agents / 28 skills, GitHub-first sprint workflow, worktree
orchestration, checkpoint gates, design/uiux pipeline, sales pack.
