# Test Plan

## Strategy
- Testing pyramid: unit / integration / e2e ratio and rationale
- Test framework: pytest (default)
- CI integration: what runs on every PR vs nightly

## Risk Matrix
| Flow | Likelihood | Impact | Risk | Coverage Level |
|------|-----------|--------|------|----------------|

## Critical Flows (ordered by risk)

### Flow: [Name]
- Risk level: High | Medium | Low
- Related requirements: FR-NNN, NFR-NNN

#### Test Cases
| ID | Precondition | Action | Expected Result | Type |
|----|-------------|--------|-----------------|------|

## Edge Cases & Boundary Tests
- Empty states, null inputs, max-length inputs
- Concurrent access scenarios
- Permission boundaries (authorized vs unauthorized)

## Test Data & Fixtures
- Required seed data descriptions
- Factory/fixture patterns
- Sensitive data handling (no real PII in tests)

## Automation Candidates
- CI (every PR): unit tests, integration tests, linting
- Nightly: e2e tests, performance benchmarks
- Manual: UX review, accessibility audit

## Release Checklist (Smoke)
- [ ] [Critical path 1 — one sentence]
- [ ] [Critical path 2 — one sentence]
