# docs/

This directory contains project-level documentation generated and managed by claude-kit skills.

## Kit-generated files

### Engineering pipeline

| File | Created by | Purpose |
|------|-----------|---------|
| `architecture.md` | `/kickoff` | System architecture and component design |
| `data_model.md` | `/kickoff` | Database schema and entity relationships |
| `prd_digest.md` | `/prd` | Condensed PRD for agent context |
| `review_lessons.md` | `/review` | Recurring review patterns and lessons |
| `review_notes.md` | `/review` | Per-PR review findings |
| `sprint_state.md` | `/sprint` | Sprint progress checkpoint |
| `test_plan.md` | `/review` | QA test plan and coverage tracking |

### Sales pipeline

| File | Created by | Updated by | Purpose |
|------|-----------|-----------|---------|
| `account_brief.md` | `/account-brief` | `/meeting-capture`, `/followup` (atomic Write) | Accumulated account intelligence; **Active Context** at top is the most-read section |
| `discovery_plan.md` | `/discovery-prep` | `/discovery-prep` | Pre-meeting SPIN/MEDDIC question plan (**max 6 questions**) |
| `meeting_notes_*.md` | **sales author** | — | Single source of truth for every meeting |
| `prd_draft.md` | `/meeting-capture` | `/meeting-capture` | Demo-scoped PRD draft; splits **PoC Deliverables** (one-shot) vs **Productionalizable Features** (real product) |
| `poc_results.md` | **sales + engineer** (fill from template) | — | **Required input to `/proposal`** — single source of truth for PoC metrics, success criteria, ROI assumptions |
| `proposal.md` | `/proposal` | `/proposal` | Closing proposal (business value first); cites `poc_results.md` for all metrics |
| `followup.md` | `/followup` | `/followup` | Post-meeting email + actions + CRM updates |
| `sales_lessons.md` | `/followup` (accumulates) | `/followup` | Cross-account patterns (read by `/discovery-prep` and `/meeting-capture`) |
| `sales_email_persona.md` | **sales author** (optional) | — | Sales-specific email tone/style; `/followup` follows it if present |

See [`sales-pipeline.md`](sales-pipeline.md) for the end-to-end sales flow.

## Templates

Example documents for reference are in the kit's `templates/` directory:
- `templates/sprint_state.md` -- sprint state format
- `templates/contributing.md` -- contributing guide template

## Notes

- These files are typically generated during `/kickoff` or `/sprint` workflows.
- Do not manually create these files unless you understand the expected format.
- `sprint_state.md` is ephemeral -- delete it to reset sprint state.
