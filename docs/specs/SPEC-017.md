# SPEC-017: Migrate kit packaging to the Claude Code plugin system

> Linked Issue: ISSUE-017
> Status: `accepted`
> Date: 2026-06-22
> Author: claude-dev-kit

## Problem

The kit hand-rolls its own plugin/marketplace layer: `install_project.sh` symlinks `scripts/`, `agents/`, `skills/`, and hooks into a target project; `install_packs.py` + `merge_settings.py` + `packs/*/manifest.yaml` + `validate_pack_manifest.py` implement optional-component selection; per-entry symlinks wire everything together. This bespoke layer is the proximate cause of a recurring bug class — the `scripts/` symlink wiring (#34), `freeze-dir.txt` tracking (#33/#34 era), and the pack-manifest PyYAML hard-fail (ISSUE-021) were all artifacts of maintaining install plumbing that Claude Code now ships natively (`.claude-plugin/plugin.json`, `hooks.json`, `.mcp.json`, `${CLAUDE_PLUGIN_ROOT}`, namespaced skills, `/plugin install`, marketplaces, versioning — all confirmed available, see `docs/cc_feature_matrix.md`). This SPEC decides **how** the kit adopts the native plugin system and decomposes the work into implementation issues. It produces no migration code itself (Spec-Required workflow, per ISSUE-006/007).

## Context

- **Verified platform support** (`docs/cc_feature_matrix.md`, build 2.1.185): full plugin component schema, `${CLAUDE_PLUGIN_ROOT}`/`${CLAUDE_PLUGIN_DATA}`, `/plugin install` with user/project/local scopes, marketplaces, and `version` gating are all present.
- **Constraint — plugin _agents_ drop `hooks`/`mcpServers`/`permissionMode`** (official, security boundary). **This applies to agents only.** _Correction (2026-06-22, ISSUE-022): plugin **skills** DO honor `hooks:` in frontmatter (`hooks.md` "Hooks in Skill Frontmatter"), so `/freeze`,`/careful`,`/guard` need NOT move to `hooks.json`._ The real defect is that those skills resolve their guard scripts via the **undocumented `${CLAUDE_SKILL_DIR}`** variable; the supported variables are `${CLAUDE_PROJECT_DIR}`/`${CLAUDE_PLUGIN_ROOT}`/`${CLAUDE_PLUGIN_DATA}`.
- **Mandatory namespacing**: plugin skills become `/<plugin>:<skill>` (e.g. `/kit:implement`). Standalone `.claude/` skills keep short names. Muscle-memory `/implement` would change for every user.
- **No manifest version floor**: `plugin.json` has no `requiredMinimumVersion`; only Claude Code settings (managed) can hard-gate a version.
- **Current consumers of the bespoke layer**: `install_project.sh`, `install_packs.py`, `merge_settings.py`, `validate_pack_manifest.py`, `packs/*/manifest.yaml`, and the repo-root `scripts/` symlink resolved by `checkpoint.sh` / `worktree.sh`.
- The kit is dogfooded on itself and used by at least one real workflow; a flag-day break of `/implement` muscle memory or in-flight worktrees is costly.

## Options

### Option A: Big-bang full migration
- **Approach**: Convert to a plugin in one PR — author `plugin.json`/`hooks.json`/`.mcp.json`, move all hook-bearing skills to `hooks.json`, switch every `scripts/` reference to `${CLAUDE_PLUGIN_ROOT}`, delete `install_project.sh`/`install_packs.py`/`merge_settings.py`/`validate_pack_manifest.py`, and require `/plugin install`. Skills become `/kit:*` immediately.
- **Pros**: One transition; no dual-maintenance window; smallest end-state surface.
- **Cons**: Every user's `/implement` muscle memory breaks on the same day; a single regression blocks the whole kit; no fallback if a feature behaves differently on an older build than the matrix predicts; hard to bisect which sub-change caused a break.
- **Trade-off**: -4 install scripts in 1 PR, but +6 coupled changes with -100% rollback granularity (revert = revert everything).

### Option B: Phased hybrid with a deprecation window
- **Approach**: Ship the plugin packaging **alongside** the existing installer. Land the manifests + `hooks.json` migration first (no behavior change for installer users), then `${CLAUDE_PLUGIN_ROOT}` path resolution that works under both layouts, then packs-as-components, then distribution, and finally deprecate `install_project.sh` only after parity is validated. Offer a standalone-install path that preserves short skill names during the window. Decompose into implementation issues, each independently revertable. _(One — ISSUE-024, plugin-data state move — was later dropped after verification; see Migration.)_
- **Pros**: Each step is ≤1.5d and revertable on its own; users migrate when ready; the matrix's `needs-verify` items (e.g. `WorktreeCreate`) get exercised before the fallback is removed; the bug-class motivation is addressed incrementally with tests at each step.
- **Cons**: A coexistence window where both the plugin and the installer must work (temporary dual-maintenance, ~2–3 issues' worth of overlap); two code paths to test until the installer is retired.
- **Trade-off**: +1 deprecation window (~6 issues, ≤1.5d each) and a temporary dual path, in exchange for 6× rollback granularity and removing the same ~4 scripts by the end with each step independently verifiable.

### Option C: Cherry-pick fixes, keep the bespoke installer
- **Approach**: Don't adopt the plugin system. Borrow only the idea of `${CLAUDE_PLUGIN_ROOT}`-style root resolution to fix the `scripts/` symlink bug, and otherwise keep `install_project.sh` + packs as-is.
- **Pros**: No namespacing churn; no plugin-subagent hook constraint to handle; least immediate work.
- **Cons**: Keeps the entire bespoke layer — the bug class persists; the kit never gains `/plugin install`, versioning, or marketplace distribution; diverges further from the platform over time, raising long-run maintenance.
- **Trade-off**: ~0 new packaging work now, but retains ~4 bespoke scripts indefinitely and forgoes native versioning/distribution (−100% of the platform-alignment benefit that motivates this issue).

## Decision

**Chosen: Option B (phased hybrid with a deprecation window).**

The trade-off line "+1 deprecation window (~6 issues, ≤1.5d each) for 6× rollback granularity, ending at the same ~4-script removal" wins because (i) it directly attacks the bug-class motivation while keeping every step independently testable and revertable, (ii) it lets the matrix's `needs-verify` items (notably `WorktreeCreate`, ISSUE-016) be exercised under the plugin layout before any fallback is deleted, and (iii) it never forces a flag-day break of `/implement` muscle memory — users opt in, and a standalone-install path preserves short names during the window. Option A couples six changes into one un-bisectable PR; Option C abandons the platform-alignment goal that is the entire point of the issue.

## Trade-offs Accepted

- **Dual-maintenance window** (~3 issues of overlap): both the plugin layout and `install_project.sh` must work until ISSUE-027 retires the installer. Mitigated by keeping a single source of truth (`agents/`, `skills/`, `hooks/`) that both packagings read.
- **Namespacing cost**: under the plugin, skills are `/kit:implement` etc. Users wanting short names must use the standalone-install path. Documented in ISSUE-026; not silently changed.
- **No manifest version gate**: the kit cannot self-declare "needs CC ≥ 2.1.x" from `plugin.json` — enforced via README prerequisites and (optionally, for orgs) managed settings. A user on too-old a build may see a skill misbehave rather than a clean refusal.
- **Skill hooks stay in frontmatter**: `/freeze`/`/careful`/`/guard` keep their inline `hooks:` (supported for plugin skills). The accepted cost is fixing their script-path resolution off the undocumented `${CLAUDE_SKILL_DIR}` onto documented variables with a fallback chain (ISSUE-022), which is slightly more verbose per hook command.

## Migration

Implemented as 6 sequenced, independently-revertable issues (each ≤1.5d). They are **stubs defined here**; they are filed as real issues when the migration is scheduled (this SPEC issue ships the plan, not the code).

1. **ISSUE-022 — Authoring & hook hygiene (1.5d)**: add `.claude-plugin/plugin.json` and `hooks/hooks.json` (porting the already-always-on `settings.snippet.json` hooks); **keep** `/freeze`,`/careful`,`/guard` hooks in skill frontmatter (supported) but fix their `${CLAUDE_SKILL_DIR}` resolution onto documented vars with a fallback; no `.mcp.json` (the kit ships no MCP servers). No installer change yet.
2. **ISSUE-023 — Root resolution via `${CLAUDE_PLUGIN_ROOT}` (1d)**: replace the repo-root `scripts/` symlink assumption in `checkpoint.sh`/`worktree.sh`/skill commands with `${CLAUDE_PLUGIN_ROOT}`, falling back to the symlink when the var is unset (works under both layouts). Directly closes the #34 bug class.
3. **ISSUE-024 — ~~Runtime state to `${CLAUDE_PLUGIN_DATA}`~~ — DROPPED (2026-06-22).** Verified that `${CLAUDE_PLUGIN_DATA}` is a **single global dir per plugin** (`~/.claude/plugins/data/{id}/`), shared across all projects and intended for persistent tooling (deps/caches), **not** per-project ephemeral state. Moving `.claude/run/` state there would collide across projects; the `.claude-kit/` freeze marker is worktree-scoped and must stay in the worktree. The kit's state is already correctly placed, so there is nothing to move — this step is dropped.
4. **ISSUE-025 — Packs as separate dependent plugins (1.5d)**: _Corrected (2026-06-22): plugins are all-or-nothing — "optional components within one plugin" is **not supported**. So a pack is modeled as its **own plugin** that declares `dependencies: ["claude-dev-kit"]` (enabling it auto-enables core)._ This issue gives the sales pack its own `packs/sales/.claude-plugin/plugin.json`. The marketplace wiring that lists both plugins moves to **ISSUE-026** (distribution); retiring `install_packs.py`/`merge_settings.py`/`validate_pack_manifest.py` moves to **ISSUE-027** (after parity — they must keep working during the coexistence window), each tied to the failure mode it caused.
5. **ISSUE-026 — Distribution & namespacing (1d)**: private git marketplace + `/plugin install kit@…` UX; document the `/kit:` namespace and the standalone-install short-name option in README.
6. **ISSUE-027 — Deprecate the bespoke installer (1d)**: after parity is validated, remove `install_project.sh` and the now-dead install scripts; flip docs to plugin-first. Gated on ISSUE-022–026 landing.

No data migration is required — `issues.md`, `docs/`, and `templates/` are untouched; only packaging/wiring changes.

## Rollback

This SPEC ships no runtime code, so accepting it has zero runtime impact — the bespoke installer remains authoritative until ISSUE-027. To abandon the migration: mark this SPEC `superseded` (or `drop` ISSUE-017) and do not file ISSUE-022–027; the kit continues on `install_project.sh` unchanged. Each implementation issue carries its own rollback (each is independently revertable by design — the reason Option B was chosen), so a regression in any single step reverts that step without unwinding the others.

## Open Questions

- [x] Should the kit ship as **one plugin with optional components** or **multiple plugins** (core + sales pack)? — **Resolved (2026-06-22): multiple plugins.** Optional-components-within-one-plugin is not supported (plugins load all-or-nothing); the platform-native pattern is separate plugins in one marketplace with `dependencies` (sales → core). See ISSUE-025.
- [ ] Is a standalone-install path (short skill names) worth maintaining long-term, or only through the deprecation window? — owner: process, by: ISSUE-026.
- [ ] Should the kit publish to a private git marketplace or the skills-directory plugin channel for team distribution? — owner: distribution, by: ISSUE-026.
- [ ] Can `WorktreeCreate` (ISSUE-016, currently `needs-verify`) be exercised under the plugin layout during ISSUE-023, closing the matrix gap? — owner: platform, by: ISSUE-023.
