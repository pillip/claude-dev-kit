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
| ID | Platform | Precondition | Action | Expected Result | Type |
|----|----------|-------------|--------|-----------------|------|

## E2E Testing Strategy

### Platform Detection
- Detected platform: web | mobile | API-only | web + mobile
- Source: `docs/architecture.md` tech stack

### Web E2E
- Framework: Playwright (default) / Cypress
- Test location: `tests/e2e/*.spec.ts`
- Viewport matrix: desktop (1280×720), tablet (768×1024), mobile (375×812)
- CI: run on PR for smoke scenarios, nightly for full suite

### Mobile E2E
- Framework: Maestro (default) / Detox
- Test location: `e2e/*.yaml` (Maestro) or `e2e/*.test.ts` (Detox)
- Device matrix: iOS (latest, latest-1), Android (latest, latest-1)
- CI: nightly on emulator/simulator farm

## Backend Robustness

### API Contract Tests
- Validate request/response schemas against OpenAPI spec
- Run on every PR in CI

### Load & Performance
| Endpoint | Expected RPS | Latency P95 | Tool |
|----------|-------------|-------------|------|

### Dependency Failure Scenarios
| Dependency | Failure Mode | Expected Behavior |
|------------|-------------|-------------------|

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

## Visual Regression
- Screenshot comparison target screens: [list key screens]
- Tool: Playwright visual comparisons or Percy/Chromatic
- Threshold: pixel diff < 0.1%

## Release Checklist (Smoke)
- [ ] [Critical path 1 — one sentence]
- [ ] [Critical path 2 — one sentence]
