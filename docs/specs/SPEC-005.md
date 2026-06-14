# SPEC-005: README sync — counts, positioning, packs section, team-scale usage

> Linked Issue: ISSUE-005
> Status: `accepted`
> Date: 2026-06-14
> Author: claude-dev-kit

## Problem

The README hasn't been updated since the pack split. It still claims "33 AI agents and 22 skills," routes `/brainstorm` and `/bizanalysis` as part of the default workflow (now demoted to optional pre-PRD), shows the install command without the `--pack` flag, and has no Packs section, no Team-scale usage guidance, no Roadmap referencing the control-plane work. Reading the README as a new user today produces a wrong mental model of the kit.

## Context

- After ISSUE-004 + ISSUE-009: core = 33 agents + 23 skills (top-level); sales pack (opt-in) = 5 agents + 5 skills. Install command supports `--pack=core|sales|all`.
- The kit's positioning has sharpened to "trustworthy code in collaboration → AI dev team control plane." The README should make that the dominant frame.
- Six SPECs (006, 007, 010, 011, 012, 013) have already landed. ISSUE-001/002/003 (telemetry → eval → memory) and 008 (polyrepo) remain. The Roadmap section should reference them by ID.
- Team-scale usage was deferred from this issue's original scope but the discussion in conversation 2026-05-30 produced two patterns (monorepo + virtual monorepo wrapper) and an explicit rationale for NOT adding a separate "team layer." This SPEC captures the rationale so contributors don't re-propose it.

## Options

### Option A: Surgical edits in place (preserve structure)
- **Approach**: Update counts in 5 known spots (tagline, "Why" bullet, Project Structure, Agents section header, Installation post-install layout). Add three new sections (Packs, Team-scale usage, Roadmap) in coherent locations. Demote brainstorm/bizanalysis to a sub-note in workflow + decision tree. Add `--pack` flag to Installation. Replace the agent table's count claim with a core-count + a note pointing at Packs. Keep all skill descriptions intact.
- **Pros**:
  - Existing Workflow / Skill Orchestration / Decision Tree sections all work — only counts and a few entries need adjustment.
  - Reviewers can diff narrowly against today's README.
- **Cons**:
  - Three new sections grow the README ~80 lines.
- **Trade-off**: +3 new sections (~80 lines), +1 demotion sub-note (~3 lines), -5 stale count references (replaced); +0 structural rewrites; 0 breakage to existing internal links.

### Option B: Rewrite the README from scratch with new positioning as the spine
- **Approach**: Rebuild around the "control plane" framing.
- **Pros**:
  - Cleanest narrative.
- **Cons**:
  - Throws away years of careful sectioning (Decision Tree, Skill Orchestration, Workflow examples). Reviewer cognitive load is high. Risk of regressing in-doc references that other docs link to.
- **Trade-off**: vs A, +1 cohesive rewrite, -100% reviewer ability to spot drift, -1 link stability with external consumers of internal anchors.

### Option C: Defer the team-scale usage section to its own PR (just sync counts + Packs)
- **Approach**: Land counts + Packs section + Roadmap now, leave team-scale guidance for a follow-up.
- **Pros**:
  - Smaller PR.
- **Cons**:
  - Team-scale usage is the section future contributors most need to *not* re-propose "add a team layer." Delaying it lets the gap persist.
- **Trade-off**: vs A, -1 section (~30 lines); +1 risk that contributors propose a redundant team layer in the interim.

## Decision

**Chosen: Option A.**

The trade-off "+3 new sections (~80 lines), -5 stale count references" wins because the existing README structure is already in production use, internal anchors are likely referenced from contributor docs, and the new sections (Packs / Team-scale / Roadmap) each have a natural home in the existing flow. Option B risks more than it gains; Option C leaves the most-asked-for guidance unwritten.

## Trade-offs Accepted

- Counts are quoted in multiple places (tagline, Project Structure, Agents section header). When the kit grows, all three must be updated together. The README is unlikely to be auto-checked against `ls agents/ skills/ packs/sales/agents/`, so contributor discipline is required.
- The "/brainstorm" / "/bizanalysis" entries stay in the skill table but get an "optional pre-PRD" framing. We do not delete them — they remain valid skills.
- The Roadmap references issue IDs (not dates). When ISSUE-001/002/003/008 land, the Roadmap section needs a follow-up update — but counts-only updates without rewriting the Roadmap narrative.
- The Team-scale usage section explains why a separate "team layer" was NOT added. This is a defensive section — future contributors reading the kit should see this rationale before proposing the layer again.

## Migration

1. Edit `README.md`:
   - Tagline + "Why claude-kit?" intro: refresh positioning ("trustworthy code in collaboration → AI dev team control plane"), update counts to 33/23 + (sales pack: 5/5 opt-in).
   - Workflow + Decision Tree: demote `/brainstorm` and `/bizanalysis` to "optional pre-PRD" sub-note.
   - New section **Packs**: explain core (default) vs sales (opt-in via `--pack=sales`); how additional packs work; link to `packs/README.md`.
   - Installation: update post-install directory diagram to show 33 agents + 23 skills + optional `--pack` examples (`--pack=sales`, `--pack=all`).
   - New section **Team-scale usage** (after Installation):
     - Pattern (a) Monorepo (engineering + sales common pattern).
     - Pattern (b) Virtual monorepo wrapper (polyrepo team solution).
     - **Why no separate "team layer"** rationale — short paragraph stating the existing pack model + the wrapper directory cover both adoption shapes without adding a concept.
   - Agents section header: update count to "33 engineering agents (default install). Sales pack adds 5 more — see Packs."
   - Project Structure: update post-install layout to current counts; reflect `packs/sales/` subtree.
   - New section **Roadmap** (near the end, before Project Structure or after Agents): 3 bullets — telemetry (ISSUE-001), eval (ISSUE-002), cumulative memory (ISSUE-003) — each one sentence, no dates. Mention that spec / pilot gate / agent boundary / WebFetch fix already shipped (link by issue ID).
2. Run a manual link check (`grep -n '\.md' README.md`) and confirm no removed anchors.
3. No code changes. README is documentation-only.

## Rollback

`git revert` the README commit. The kit continues to work — README content is purely informational. No data or code dependencies on README. Rollback time: < 1 minute.

## Open Questions

- [ ] Should the README counts be auto-checked against the filesystem at CI time (e.g., a tiny script that compares quoted "33 agents" to `ls agents | wc -l`)? — owner: process, by: after a 3rd kit growth causes a stale count.
- [ ] Should the "Team-scale usage" section grow examples (a real monorepo layout + a real wrapper layout in code blocks)? — owner: docs, by: after the first contributor question about team adoption.
- [ ] Should the Roadmap section move to its own document (`docs/roadmap.md`) once it grows past 3–5 items? — owner: docs, by: when 6+ open ISSUEs are referenced.
