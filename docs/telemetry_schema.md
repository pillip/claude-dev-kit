# Telemetry Schema

> **Status**: schema documentation. ISSUE-001 (done) shipped the *hook-level*
> trace — `agent_state.py` writing shape-only events to `.claude/run/events.jsonl`
> plus `scripts/trace_query.py`. The **semantic delegation events** below
> (`research_delegated_to_deep_research`, `review_delegated_to_code_review`, …)
> are skill-emitted markers documented here as the source of truth; they are
> best-effort local appends owned by the skills, a superset of the hook trace
> rather than a replacement. This file is the schema contract the SPEC-018/019
> guard tests assert against.

## Conventions

- One event per JSON object per line.
- Required fields on every event: `ts` (ISO-8601), `event_type`, `skill_or_script`, `issue_id?`.
- `payload` field carries event-specific data per the table below.
- Events are append-only; never edit historical lines.

## Event catalog

### ISSUE-018 — research grounding (brainstorm, bizanalysis)

| Event type                          | Owner skill         | Payload fields                                            | Notes |
|-------------------------------------|---------------------|-----------------------------------------------------------|-------|
| `research_delegated_to_deep_research` | brainstorm, bizanalysis | `dimension: str, question: str`                          | Emitted once per `/deep-research` invocation on the primary path. |
| `research_degraded_path_used`        | brainstorm, bizanalysis | `reason: "skill_missing" | "skill_unknown_inline_fail"`  | Emitted once when the runtime probe forces the degraded path. |
| `synthesis_claim_dropped`            | bizanalysis         | `section: str, upstream_excerpt: str`                     | From synthesizer-auditor finding. |
| `synthesis_claim_distorted`          | bizanalysis         | `section: str, kit_text: str, upstream_excerpt: str`      | From synthesizer-auditor finding. |
| `synthesis_audit_finding`            | brainstorm, bizanalysis | `verdict: str, finding_count: int`                       | Aggregate audit summary. |
| `research_quote_validated`           | brainstorm, bizanalysis | `claim_id: str`                                           | Degraded-path validator returned `ok`. |
| `research_quote_rejected`            | brainstorm, bizanalysis | `claim_id: str, verdict: str, reason: str`                | Degraded-path validator returned non-ok. |
| `research_source_stale`              | brainstorm, bizanalysis | `claim_id: str, age_days: int`                            | Sub-case of `research_quote_rejected` with verdict `stale`. |
| `research_triangulation_single`      | bizanalysis         | `section: str`                                            | TAM/SAM/SOM rendered as `range … [single-source]`. |
| `research_audit_finding`             | brainstorm, bizanalysis | `verdict: str, finding_count: int`                       | Degraded-path research-auditor summary. |

### ISSUE-019 — review delegation (placeholders pending implementation)

| Event type                          | Owner skill | Payload fields                          | Notes |
|-------------------------------------|-------------|-----------------------------------------|-------|
| `review_delegated_to_code_review`    | review      | `pr_number: int | str`                  | Emitted when runtime `/code-review` is invoked. |
| `review_delegated_to_security_review`| review      | `pr_number: int | str`                  | Emitted when runtime `/security-review` is invoked. |
| `review_degraded_path_used`          | review      | `dimension: "code" | "security"`        | One emission per missing dimension. |
| `review_finding_dropped`             | review      | `finding_id: str, dimension: str`       | From review-merge-auditor. |
| `review_severity_changed`            | review      | `finding_id: str, from: str, to: str`   | From review-merge-auditor. |
| `review_merge_audit_finding`         | review      | `verdict: str, finding_count: int`      | Aggregate audit summary. |

### ISSUE-007 — spec gate (already emitted)

| Event type                          | Owner skill | Payload fields                                  | Notes |
|-------------------------------------|-------------|-------------------------------------------------|-------|
| `spec_gate_triggered`                | implement   | `issue_id: str, mode: "sprint" | "non-sprint"`  | Pre-existing per SPEC-007. |
| `spec_gate_hold`                     | implement   | `issue_id: str, choice: int`                    | Non-sprint HOLD outcome. |
| `spec_gate_auto_ran`                 | implement   | `issue_id: str, spec_path: str`                 | Sprint auto-run produced SPEC. |
| `spec_gate_bypassed`                 | implement   | `issue_id: str, reason: "skip_flag"`            | `--skip-spec-gate` invoked. |

## Append behavior

Until ISSUE-001 lands its collector, events should be appended to
`.claude/runs/<run-id>.jsonl` (project-side, gitignored) using `O_APPEND`
with payloads kept under 4 KB to preserve POSIX atomicity. Each event line
must validate against this schema; future ingestion replays these files
under the ISSUE-001 pipeline.

When the kit's telemetry pipeline is unconfigured (no `.claude/runs/`
directory, no run-id available), event emission is a silent no-op — never
fail the parent skill on a telemetry write error.

## Updating this doc

- New event types require an entry in the table above, including owner
  skill, payload fields, and a one-line note.
- Removing or renaming an event type is a breaking change for downstream
  consumers (ISSUE-001 ingest, ISSUE-003 memory promotion). Record the
  change with a `Deprecated:` row before removal.
- The schema lives here, not inline in skill prompts. Skills cite event
  names; they do not redefine the schema.
