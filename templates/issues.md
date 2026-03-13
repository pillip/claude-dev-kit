# Issues

> SSOT: Progress and completion are tracked by the Status field in this document (not inferred from code analysis)
> Rule: **1 Issue = 1 PR** (GitHub-first)

## Conventions
- Track: `product` | `platform`
- Status: `backlog` | `doing` | `waiting` | `done` | `drop`
- Priority: `P0` (blocks everything) | `P1` (core) | `P2` (nice-to-have)
- Estimate: `0.5d` | `1d` | `1.5d` (> 1.5d must be split)
- Branch: `issue/ISSUE-<NNN>-<slug>`
- GitHub: **/implement creates a GH Issue (if missing) + PR and links them (Closes #N)**

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

#### Tests
- [ ] [Specific test case 1]
- [ ] [Specific test case 2]

#### Rollback
[How to undo if something goes wrong]
