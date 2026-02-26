# Architecture

## Overview
- Architecture style: [monolith / modular monolith / microservices / serverless]
- Justification: [why this style for this project]
- Key constraints: [driving the decision]

## Tech Stack
| Layer | Choice | Version | Rationale |
|-------|--------|---------|-----------|

## Modules

### Module: [Name]
- Responsibility: [single sentence]
- Dependencies: [other modules]
- Key interfaces: [public functions/endpoints]

## Data Model
- Entity relationships
- Storage choice per entity (RDBMS, document store, cache, file)
- Migration strategy

## API Design

### [Method] /path
- Request: [shape]
- Response: [shape]
- Auth: [required / public]
- Rate limit: [if applicable]

## Background Jobs
| Job | Trigger | Frequency | Idempotent |
|-----|---------|-----------|------------|

## Observability
- Logging: [structured, levels, what to log]
- Metrics: [key business + system metrics]
- Alerting: [thresholds]

## Security
- Auth scheme: [session / JWT / OAuth]
- Input validation strategy
- Secrets management
- OWASP Top 10 mitigations

## Deployment & Rollback
- Deployment target: [container / serverless / PaaS]
- CI/CD pipeline outline
- Rollback procedure
- Database migration rollback

## Tradeoffs
| Decision | Chosen | Rejected | Rationale |
|----------|--------|----------|-----------|
