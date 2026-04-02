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

### Test Independence
- Every test must be runnable in isolation — no dependency on execution order
- No shared mutable state between test files or test functions
- Each test sets up its own fixtures and tears down after itself
- Parallel test execution must be safe (no port conflicts, no shared DB rows)

### Network Mocking
- **Web**: Use MSW (Mock Service Worker) or Playwright route interception for API mocking — never stub internal modules
- **Mobile**: Use backend test mode or local mock server for API responses
- No real HTTP calls in unit or integration tests — all external services must be mocked
- Mock responses should match production API schemas

### Flaky Test Protocol
- **Retry policy**: Flaky tests get max 2 automatic retries in CI before failing the build
- **Quarantine process**: Tests that flake 3+ times in a week are moved to a quarantine suite (runs nightly, not on PR)
- **Resolution SLA**: Quarantined tests must be fixed or deleted within 5 business days
- **Root cause required**: Every flaky test fix must document the root cause (timing, race condition, shared state, etc.)

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

## Verify Gates Configuration
- Server start command: [e.g., `npm run dev` or `uvicorn main:app`]
- Server health URL: [e.g., `http://localhost:3000/health`]
- Server startup timeout: 30s
- Mobile test framework: [maestro/detox — auto-detected if omitted]
- Mobile build command: [e.g., `npx detox build -c ios.sim.debug` — skip if omitted]
- Mobile Detox config: [e.g., `ios.sim.debug` — only for Detox]

### Gate Overrides
| Gate | Enabled | Blocking | Notes |
|------|---------|----------|-------|
| unit | yes | yes | Always enabled |
| integration | [yes/no] | yes | |
| e2e-web | [yes/no] | yes | |
| e2e-mobile | [yes/no] | no | |
| api | [yes/no] | yes | |
| load | [yes/no] | no | Non-blocking by default |

## Release Checklist (Smoke)
- [ ] [Critical path 1 — one sentence]
- [ ] [Critical path 2 — one sentence]
