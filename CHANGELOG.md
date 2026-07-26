# Changelog

All notable changes to claude-dev-kit. Versions are the plugin `version` field;
release tags are `claude-dev-kit--v<version>` (and `claude-dev-kit-sales--v<version>`).

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
