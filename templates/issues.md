# Issues

> SSOT: Progress and completion are tracked by the Status field in this document (not inferred from code analysis)
> Rule: **1 Issue = 1 PR** (GitHub-first)

## Conventions
- Track: `product` | `platform`
- Status: `backlog` | `doing` | `waiting` | `done` | `drop`
- Priority: `P0` (blocks everything) | `P1` (core) | `P2` (nice-to-have)
- Estimate: `0.5d` | `1d` | `1.5d` (> 1.5d must be split)
- Platform: `web` (default) | `mobile` (React Native/Expo) | `desktop` (Electron/Tauri) — auto-inferred from PRD/architecture if available
- Manual: `true` = task requires human action (API key provisioning, external service setup, environment variable configuration, OAuth registration, DNS setup, etc.); `false` = fully automatable by code
- Spec-Required: `true` = a tech spec / RFC (`docs/specs/SPEC-NNN.md`) MUST exist before `done`; `false` (default) = no spec needed
- Spec: path to the SPEC file (e.g., `docs/specs/SPEC-007.md`) or `none`
- Branch: `issue/ISSUE-<NNN>-<slug>` (impl) / `issue/ISSUE-<NNN>-spec` (spec-only PR in non-sprint mode)
- GitHub: **/implement creates a GH Issue (if missing) + PR and links them (Closes #N)**
- Spec PR exception: a `Spec-Required: true` issue produces **2 PRs in non-sprint mode** (spec-only PR then impl PR), or **1 bundled PR in sprint mode** (single branch carrying both the SPEC commit and impl commits).

---

## Board

### Backlog
- [ ] ISSUE-001: <title> _(track: product, P1, 1d)_

### Doing

### Waiting

### Done

### Drop

---

## Issue Detail (copy & fill)

### ISSUE-<NNN>: [imperative verb + object]
- Track: product | platform
- UI: true | false
- Platform: web | mobile | desktop
- Manual: true | false
- Spec-Required: true | false
- Spec: docs/specs/SPEC-<NNN>.md | none
- PRD-Ref: FR-NNN or Story-NNN
- Priority: P0 | P1 | P2
- Estimate: 0.5d | 1d | 1.5d
- Status: backlog | doing | waiting | done | drop
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: [ISSUE-NNN list, or "none"]

#### Goal
[One sentence: what is true when this issue is done]

#### Scope (In/Out)
- In: [specific deliverables]
- Out: [what this issue does NOT include]

#### Acceptance Criteria (DoD)
- [ ] Given [precondition], when [action], then [expected result]
- [ ] Given [precondition], when [action], then [expected result]

#### Implementation Notes
[Key technical hints — which files, patterns, gotchas]
[Figma references (optional) — paste Figma frame URLs here, one per line:
  - https://www.figma.com/design/FILE_KEY/Name?node-id=XX-YYYY
  - https://www.figma.com/design/FILE_KEY/Name?node-id=XX-ZZZZ
  When present, /implement auto-generates prototype HTML from these before coding.]

#### Tests
- [ ] [Specific test case 1]
- [ ] [Specific test case 2]

#### Rollback
[How to undo if something goes wrong]
