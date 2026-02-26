# Data Model

## Storage Strategy
- Primary: [RDBMS / Document / Key-Value / IndexedDB]
- Rationale: [tied to NFRs]
- Secondary: [cache, search, file storage — if any]

## Access Patterns

| Pattern | Source | Operation | Frequency | Latency Target |
|---------|--------|-----------|-----------|----------------|

## Schema

### Table: [name]
| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| id | UUID | PK | gen | |

- Relationships:

## Indexes

| Table | Index | Columns | Type | Justification |
|-------|-------|---------|------|---------------|

## Migrations
- Strategy:
- Version 1:
- Rollback:

## Seed Data

| Table | Data | Purpose |
|-------|------|---------|

## Query Patterns

### [Pattern name]
- Used by:
- Query:
- Expected rows:
- Index used:
- Performance:

## Constraints & Validation
- Database-level:
- Application-level:
- Cross-table integrity:

## Scaling Notes
- Current design handles:
- At 10x:
- At 100x:
