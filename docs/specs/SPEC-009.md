# SPEC-009: install_project.sh --pack flag + per-entry symlinks + settings merge order

> Linked Issue: ISSUE-009
> Status: `accepted`
> Date: 2026-06-14
> Author: claude-dev-kit

## Problem

After ISSUE-004 relocated sales assets into `packs/sales/`, the existing `install_project.sh` no longer installs them — it symlinks the **directory** `KIT_ROOT/agents` to `.claude/agents`, which no longer contains sales agents. Users running default install today get core-only, but there is no opt-in path to add sales (or any future pack) back.

The directory-symlink approach is also fundamentally incompatible with the pack model: a single directory symlink cannot mix entries from `KIT_ROOT/agents/` and `KIT_ROOT/packs/sales/agents/`. The kit needs per-entry symlinks under `.claude/agents/` and `.claude/skills/` so core + selected packs can coexist.

## Context

- `install_project.sh` previously did `ln -sfn "$KIT_ROOT/agents" "$PROJ_ROOT/.claude/agents"` and the same for skills. Directory-level symlinks.
- ISSUE-004 added `packs/sales/manifest.yaml` + `scripts/validate_pack_manifest.py` declaring the schema and validating presence + depends_on + cross-pack duplicates.
- The kit's `merge_settings.py` already exists and does a deep merge with last-write-wins.
- `templates/` is not currently installed into the user's project (skills read them from the kit source). This SPEC does not change that.

## Options

### Option A: Python helper + per-entry symlinks + shell wrapper
- **Approach**:
  - New `scripts/install_packs.py` resolves `--pack` args into an ordered selection (`['core', <sorted non-core packs>]`), verifies each pack's `depends_on`, creates per-entry symlinks under `.claude/agents/` and `.claude/skills/`, raises on entry collisions across packs, and returns settings_snippet paths for the shell wrapper to merge.
  - `install_project.sh` forwards `--pack` args to the helper, captures the snippet list, then runs `merge_settings.py` with core's snippet first followed by each pack snippet in selection order (deep merge, pack wins on collision).
  - Migration note: when `.claude/agents` was a legacy directory symlink (pre-pack install), print a one-line info message before replacing it. Never auto-delete the user's project files.
- **Pros**:
  - YAML parsing + collision detection live in Python (already PyYAML in deps via ISSUE-004 validator).
  - Per-entry symlinks let arbitrary pack combinations coexist.
  - Reuses ISSUE-004's `_load_manifest` so the schema definition stays single-sourced.
  - Tests are deterministic (synthetic kit fixtures + tmpdir target).
- **Cons**:
  - install_project.sh becomes a shell-to-python forward instead of doing all the work itself. Slight indirection for readers.
  - Many small symlinks instead of one big one. Marginally slower install, no runtime difference.
- **Trade-off**: +1 Python helper (~250 LOC), +15 integration tests, +1 shell wrapper change (~15 lines); -1 directory symlink per kit dir; -1 monolithic install_project.sh.

### Option B: All-bash install with grep+find walking manifests
- **Approach**: Parse manifest.yaml inside bash (e.g., with `yq` or fragile grep), no Python helper.
- **Pros**:
  - install_project.sh stays self-contained.
- **Cons**:
  - YAML parsing in bash is unreliable (yq dependency or grep that breaks on multi-line values).
  - Cross-pack collision detection is hard to write correctly in bash.
  - Reuses neither `_load_manifest` nor the validator — schema would have two parsers, drifting apart.
- **Trade-off**: vs A, -1 Python file but +1 yq runtime dependency OR fragile grep; +2 sources of truth for the manifest schema (Python validator + bash parser); -100% reliability.

### Option C: Copy files instead of symlink
- **Approach**: For each selected pack entry, `cp` instead of `ln -sfn`. Pack updates would require reinstall.
- **Pros**:
  - User project is self-contained; works even if the kit checkout moves.
- **Cons**:
  - Loses the kit's "live updates by re-pull" property — symlinks today auto-reflect kit changes.
  - Reinstall friction every time the kit is updated.
- **Trade-off**: vs A, -0 LOC; +1 reinstall step on every kit update; -1 live-update property that the kit currently relies on.

## Decision

**Chosen: Option A.**

The trade-off "+1 Python helper (~250 LOC), +15 tests, -1 directory symlink convention" wins because (i) Python reuses the validator's schema source-of-truth and gives us deterministic test fixtures, (ii) per-entry symlinks are the only design that lets core + arbitrary packs coexist, and (iii) the live-update property (kit pull = effective immediately in installed projects) is worth preserving. Options B and C each fail one of these.

## Trade-offs Accepted

- Many small symlinks per install. macOS / Linux handle this fine; Windows would not (the kit never claimed Windows support).
- A pack's settings_snippet overrides core's on key collision (deep merge, last-write-wins). Pack authors must be conservative about which top-level keys they touch. Documented in `packs/README.md`.
- Switching from `--pack=sales` to `--pack=core` (no flag) at reinstall time removes the sales entries from `.claude/`. This is the desired behavior — the install set IS the active install — but contributors should know reinstall is destructive of pack entries.
- The migration note for legacy directory symlinks fires when running this script against a project last installed with the pre-pack version. The note is informational, never an error.
- `install_user.sh` is not changed in this PR. User-level installs are core-only for now; no pack today declares user-level assets.

## Migration

1. Land `scripts/install_packs.py` implementing the selection resolver + installer + collision detection + depends_on verification.
2. Land `tests/test_install_packs.py` with 15 cases (defaults, named pack, all expansion, dedup, unknown pack, core install, pack adds entries, collision raises, depends_on raises, snippet returned, idempotent reinstall, removal on reinstall-without-pack, plus 2 smoke tests against the actual kit checkout).
3. Replace `install_project.sh`'s directory-symlink block with a call to the helper, capture stdout for snippet paths, then run `merge_settings.py` in order: core's snippet first, then each pack snippet.
4. No data migration needed. Existing user projects with the legacy directory symlink trigger the migration note and continue to work after first reinstall.

## Rollback

Revert `install_project.sh` to the pre-PR version (directory symlinks). Delete `scripts/install_packs.py` and `tests/test_install_packs.py`. Users who had reinstalled with the new layout will need to re-run the old install script to re-create the directory symlinks. Rollback time: < 5 minutes; users only need to rerun install once.

## Open Questions

- [ ] Should the helper emit machine-readable JSON instead of one-snippet-per-line stdout, so future tooling can consume it? — owner: design, by: when a second consumer of the install output appears.
- [ ] Should `install_user.sh` adopt the same `--pack` flag (currently unchanged)? — owner: process, by: when the first pack declares user-level assets.
- [ ] Should the kit ship a `packs/core/manifest.yaml` (explicit core manifest instead of implicit top-level)? Would simplify the helper but requires moving the top-level agents/skills/ into `packs/core/`. — owner: design, by: after 3+ packs exist and the implicit-core asymmetry becomes a maintenance issue.
