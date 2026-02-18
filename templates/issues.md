# Issues

> SSOT: 진행/완료 판정은 이 문서의 Status로 관리 (코드 분석으로 PRD 완료 판정하지 않음)
> Rule: **1 Issue = 1 PR** (GitHub-first)

## Conventions
- Track: `product` | `platform`
- Status: `backlog` | `doing` | `waiting` | `done` | `drop`
- Priority: `P0` | `P1` | `P2`
- Estimate: `0.5d` | `1d` | `1.5d`
- Branch: `issue/ISSUE-<NNN>-<slug>`
- GitHub: **/implement가 GH Issue(없으면 생성) + PR 생성하고 연결(Closes #N)**

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

### ISSUE-<NNN>: <title>
- Track: product | platform
- PRD-Ref: <optional: PRD#section>
- Priority: P0 | P1 | P2
- Estimate: 0.5d | 1d | 1.5d
- Status: backlog | doing | waiting | done | drop
- Owner: <name>
- Branch: issue/ISSUE-<NNN>-<slug>
- GH-Issue: <url or #number>
- PR: <url>
- Labels: <optional>

#### Goal
- ...

#### Scope
- In:
  - ...
- Out:
  - ...

#### Acceptance Criteria (DoD)
- [ ] ...
- [ ] ...

#### Implementation Notes
- ...

#### Tests
- [ ] Unit: ...
- [ ] Integration: ...
- [ ] Smoke: ...
- Test Command: `<...>`

#### Observability (Minimal)
- [ ] Logs: ...
- [ ] Metrics: N/A
- [ ] Tracing: N/A

#### Rollback
- ...

#### Dependencies / Blockers
- ...
