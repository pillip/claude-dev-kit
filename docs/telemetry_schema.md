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

### ISSUE-058 — test-execution gate delegation (dormant until the runtime capability ships)

| Event type                    | Owner script              | Payload fields                                                                        | Notes |
|-------------------------------|---------------------------|----------------------------------------------------------------------------------------|-------|
| `gates_delegated_to_runtime`  | synthesize_gate_results   | `skill: str, gate_count: int`                                                           | Emitted when a valid `KIT_GATE_RESULTS_FILE` handoff artifact is synthesized into gate results. |
| `gates_degraded_path_used`    | synthesize_gate_results   | `reason: "skill_missing" | "capability_dormant" | "invalid_results" | "binding-rejected", detail?: str` | One emission per gate run that falls back to `verify_gates.py`. `invalid_results` carries a `detail` naming `KIT_GATE_RESULTS_FILE` (truncated to keep the event under the 4 KB append cap — padding must not drop the forensic record). `binding-rejected` (ISSUE-065) means the artifact was refused by the provenance/freshness/consume-once binding layer; its `detail` names the failed check (`consumed`/`mac`/`stale`) and `KIT_GATE_RESULTS_FILE`. |

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
under the ISSUE-001 pipeline. The shared emitter
(`scripts/kit_telemetry.py`, ISSUE-067) resolves the run-id from the
`KIT_RUN_ID` env var and auto-creates `.claude/runs/`; an unset or invalid
run-id means the event is written under the explicit `unattributed` run id
with a top-level `run_id_fallback` field naming the condition, plus one
`[kit-telemetry]` stdout announcement naming the knob — never a silent
no-op.

Every remaining skip path announces its named reason on stdout (containment
violation, serialized event past the 4 KB cap, write failure). A rejected
containment violation writes nothing anywhere, so the stdout line is its
only signal. Telemetry stays non-blocking: never fail the parent skill on a
telemetry write error (unchanged).

## Emit-site inventory (ISSUE-067)

Audit of every telemetry emit call site: each site uses the shared emitter
(`scripts/kit_telemetry.py`) or carries a recorded justification — no
hand-rolled appender remains unexamined.

| Site | Mechanism | Status / justification |
|------|-----------|------------------------|
| `scripts/synthesize_gate_results.py` | `kit_telemetry.emit_event` (thin `_emit_telemetry` delegation) | Migrated to the shared helper. |
| `skills/review/SKILL.md.tmpl` delegation/degraded emits | `python3 scripts/kit_telemetry.py` CLI one-liner | Migrated from prose instruction. |
| `skills/bizanalysis/SKILL.md.tmpl` research emits | `python3 scripts/kit_telemetry.py` CLI one-liner | Migrated from prose instruction. |
| `skills/brainstorm/SKILL.md.tmpl` degraded emit | `python3 scripts/kit_telemetry.py` CLI one-liner | Migrated from prose instruction. |
| `scripts/spec_gate.py` | printed JSON decision object + the skill's stdout "telemetry-style" bypass line per SPEC-007 | JUSTIFIED, not migrated: no JSONL appender exists there — adding one is new scope (minimality). |
| `project/.claude/hooks/agent_state.py` | hook-trace appender to `.claude/run/events.jsonl` | JUSTIFIED: separate ISSUE-001 shape-only hook-trace stream with its own contract; ISSUE-001 analytics scope is explicitly Out. |
| `/ship` skill, `scripts/checkpoint.sh` / `verify_checkpoint.py` | — | JUSTIFIED: no emit call sites exist today (audited; nothing to migrate). |
| `scripts/trace_query.py` | — | Consumer, not an emitter. |

Events cataloged above without a live emit instruction (e.g.
`synthesis_*`, `research_quote_*`) have no call site to migrate; when a
skill gains one, it must use the shared emitter CLI.

## Updating this doc

- New event types require an entry in the table above, including owner
  skill, payload fields, and a one-line note.
- Removing or renaming an event type is a breaking change for downstream
  consumers (ISSUE-001 ingest, ISSUE-003 memory promotion). Record the
  change with a `Deprecated:` row before removal.
- The schema lives here, not inline in skill prompts. Skills cite event
  names; they do not redefine the schema.
