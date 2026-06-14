# SPEC-004: Sales pack file relocation + manifest schema

> Linked Issue: ISSUE-004
> Status: `accepted`
> Date: 2026-06-14
> Author: claude-dev-kit

## Problem

Sales-domain assets (5 agents, 5 skills, 7 templates) live at the kit's top level (`agents/`, `skills/`, `templates/`) alongside core engineering assets. Every install pulls them in regardless of whether the user wants sales workflows. The kit's positioning ("trustworthy code in collaboration → AI dev team control plane") is diluted by sales-domain primitives appearing in the default agent/skill registry.

The reviewer's diagnosis: sales is off-thesis for the kit's identity but actively used by sales teams sharing a repo with engineering. Deleting it would lose real work; leaving it as default install muddies the kit's core message.

## Context

- The kit currently ships 38 agents + 27 skills at the top level. Of those, 5 agents (`account-researcher`, `champion-mapper`, `discovery-coach`, `meeting-synthesizer`, `proposal-writer`) and 5 skills (`account-brief`, `discovery-prep`, `followup`, `meeting-capture`, `proposal`) plus 7 templates are sales-domain.
- `install_project.sh` symlinks `agents/` and `skills/` top-level directories into `.claude/`. There is no pack concept yet.
- ISSUE-009 will introduce the install flag (`--pack=<core|sales|all>`); ISSUE-005 will sync the README. This SPEC is the file-relocation foundation that both depend on.
- The repo stays a monorepo. Spin-off to a separate `claude-sales-kit` is deliberately not pursued — shared primitives (`/prd`, `/kickoff`, `/issue`, `/sprint`, hooks, templates) are heavily reused by sales and splitting would require version-matrix management.

## Options

### Option A: `packs/<name>/` subtree + `manifest.yaml` + validator (this SPEC)
- **Approach**: Create `packs/sales/{agents,skills,templates}/`. `git mv` all 17 sales files. Write `packs/sales/manifest.yaml` declaring `depends_on: [core]` + the file lists. Write `packs/sales/README.md` (pack purpose, opt-in command after ISSUE-009 lands). Write `packs/README.md` (schema documentation). Write `scripts/validate_pack_manifest.py` enforcing schema + file existence + cross-pack duplicate detection. Extend `scripts/gen_skills.py` to walk `packs/<name>/skills/` too so moved skills still regenerate.
- **Pros**:
  - Establishes the pattern (manifest + validator + depends_on) future packs reuse.
  - Pure structural change at this stage — install behavior unchanged until ISSUE-009.
  - Validator is the single source of truth for the schema; ISSUE-009's installer imports it instead of re-parsing.
  - Git history preserved via `git mv`.
- **Cons**:
  - Two PRs (this + ISSUE-009) before users can opt in via the install flag. Between them, the default install loses sales (because `install_project.sh` symlinks `agents/`/`skills/` top-level only). Acceptable as long as ISSUE-009 lands soon after.
- **Trade-off**: +3 directories (`packs/`, `packs/sales/`, `packs/sales/{agents,skills,templates}`), +1 manifest file, +1 validator script (~200 LOC), +2 READMEs, +1 gen_skills hook (~5 LOC); -17 files relocated via `git mv` (blame preserved); -100% sales presence in default install between this PR and ISSUE-009 merging.

### Option B: Inline the pack flag in this PR (combine ISSUE-004 + ISSUE-009)
- **Approach**: Do file moves AND the install-flag work in a single PR.
- **Pros**:
  - No window where default install loses sales.
  - One PR review instead of two.
- **Cons**:
  - PR size doubles (~400 LOC + manifest validator + install script changes + 4–6 installer test cases). Conflicts with the kit's `1 Issue = 1 PR` and `≤ 1.5d` rules — combined work was originally estimated at 1.5d before split.
  - Larger PRs make rollback harder (revert affects both the structural move and the installer behavior).
- **Trade-off**: vs A, -1 PR; +2x review surface; -1 clean rollback boundary; -1 conformance with the kit's 1.5d/1-PR rules that ISSUE-004 set up in this kit's own SPEC chain.

### Option C: Use a top-level subdirectory (`sales/`) without manifests
- **Approach**: Create `sales/` next to `agents/`, `skills/`, `templates/`. Move files in. No manifest, no validator.
- **Pros**:
  - Smallest possible change.
- **Cons**:
  - No reusable pattern — every future pack reinvents its own layout.
  - No automatic validation of `depends_on`, file existence, or cross-pack duplicates.
  - Hard to extend to a `--pack` install flag later (ISSUE-009) without retrofitting a schema.
- **Trade-off**: vs A, -1 manifest, -1 validator script; +0 reusable pattern for future packs; -1 schema enforcement (silent breakage when a manifest entry vanishes).

## Decision

**Chosen: Option A.**

The trade-off "+1 manifest + 1 validator + 2 READMEs, -100% sales presence in default install for ~1 PR cycle" wins because the temporary install gap is acceptable (ISSUE-009 lands immediately after) and the validator pays for itself the second a contributor adds a typo or removes a referenced file. Option B inflates PR size and violates the kit's own size discipline; Option C leaves the system without a schema, guaranteeing future packs each reinvent their own shape.

## Trade-offs Accepted

- Between this PR landing and ISSUE-009 landing, `bash install_project.sh` does not install sales agents/skills. Sales users who reinstall in that window get a core-only kit. Mitigation: ISSUE-009 is the next PR, opened immediately; users can manually symlink `packs/sales/agents/` into `.claude/agents/` as a stopgap.
- The manifest hard-rejects duplicate entry names across packs (e.g., two packs cannot both declare `agents/proposal-writer.md`). This is deliberate — packs are additive, not redefinitions. Documented in `packs/README.md`.
- `gen_skills.py` now walks both `skills/` and `packs/*/skills/`. A pack-level `SKILL.md.tmpl` is treated identically to a top-level one. No namespacing is added; if two skills with the same name lived in different packs, the second registration would overwrite the first. Acceptable for now; future-pack scope can revisit.
- The kit's CONTRIBUTING / docs reference sales agents by name (no paths) and so are unaffected by the file relocation. No doc updates included here.

## Migration

1. Create `packs/sales/{agents,skills,templates}/` directories.
2. `git mv agents/<sales-agent>.md → packs/sales/agents/` for all 5 agents.
3. `git mv skills/<sales-skill>/ → packs/sales/skills/` for all 5 skills.
4. `git mv templates/<sales-template>.md → packs/sales/templates/` for all 7 templates.
5. Write `packs/sales/manifest.yaml` with `name: sales`, `depends_on: [core]`, file lists.
6. Write `packs/sales/README.md` and `packs/README.md` (schema docs).
7. Write `scripts/validate_pack_manifest.py`.
8. Extend `scripts/gen_skills.py` so `discover_templates()` walks `packs/*/skills/*/SKILL.md.tmpl` in addition to `skills/*/SKILL.md.tmpl`.
9. Write `tests/test_validate_pack_manifest.py` with: valid pass, missing file, missing depends_on, no `core` in depends_on, unknown pack dep, duplicate entry across packs, name mismatch, valid settings_snippet, missing settings_snippet, CLI returns 0/1/2.

## Rollback

`git revert` the move commit. The `packs/` directory and validator script become orphaned (harmless). `install_project.sh` continues working unchanged (it never depended on the new layout). Tests for the validator continue to pass (it walks whatever exists). Rollback time: < 5 minutes.

## Open Questions

- [ ] Should the manifest support a `version:` field for per-pack version pinning? — owner: process, by: when a real divergence in sales vs core cadence appears.
- [ ] Should `gen_skills.py` namespace pack skills (e.g., `sales/proposal` vs `proposal`) to allow same-name skills in different packs? — owner: design, by: when a 2nd pack lands with a same-name skill collision.
- [ ] Should `scripts/find_shared.sh` and other repo-walking utilities also be taught about `packs/*/templates/`? — owner: design, by: ISSUE-009 implementation (when install needs to copy templates into the user project).
