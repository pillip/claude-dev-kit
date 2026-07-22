# Sales Pack

Opt-in domain bundle for account / customer-success teams that share a repo with engineering.

## What this pack adds

**5 agents** (under `packs/sales/agents/`):
- `account-researcher.md` — initial account intelligence + deal landscape
- `champion-mapper.md` — internal champion identification + influence map
- `discovery-coach.md` — discovery-call coaching + question framework
- `meeting-synthesizer.md` — meeting note → structured account record
- `proposal-writer.md` — proposal drafting against discovered pain + champion ask

**5 skills** (under `packs/sales/skills/`):
- `/account-brief` — produce a one-page brief for a target account
- `/discovery-prep` — pre-call preparation against the account brief
- `/followup` — follow-up email + internal CRM update from meeting notes
- `/meeting-capture` — structured meeting capture for downstream agents
- `/proposal` — proposal generation grounded in account brief + discovery

**7 templates** (under `packs/sales/templates/`): the deliverable shapes the skills produce — `account_brief.md`, `discovery_plan.md`, `followup.md`, `meeting_notes.md`, `proposal.md`, `sales_email_persona.md`, `sales_lessons.md`.

## How it works with core

The sales pack **depends on core** (`dependencies: ["claude-dev-kit"]` in its `plugin.json`; mirrored as `depends_on: [core]` in `manifest.yaml`). Sales workflows reuse core's primitives — `/prd`, `/kickoff`, `/issue`, `/sprint` — and shared templates (`issues.md`, `sprint_state.md`). Installing the sales plugin auto-installs core.

A typical sales team layout uses `accounts/<company>/` subdirectories at the repo root (one subdir per active account, each holding the deliverables produced by the skills above). That accumulation pattern is the same shape engineering teams use for `services/<name>/` — the repo IS the team boundary, no extra layer is needed.

## Install

The pack ships as the `claude-dev-kit-sales` plugin in the repo's marketplace:

```bash
/plugin marketplace add pillip/claude-dev-kit
/plugin install claude-dev-kit-sales@claude-dev-kit   # auto-installs core (declared dependency)
```

Sales skills are namespaced by the plugin name — e.g. `/claude-dev-kit-sales:proposal`.

## Why a separate pack (not core)

The kit's positioning is "trustworthy code in collaboration → AI dev team control plane." Sales workflows are domain-specific and would dilute that positioning if bundled into the default install. The pack boundary lets sales-using teams install both layers while engineering-only teams get a clean install.

This is **not a step toward a separate repo**. The kit stays monorepo with plugin-boundary packs — shared primitives (`/prd`, `/kickoff`, hooks, helper scripts) are heavily reused by sales, and splitting would create version-matrix overhead without capability gain. Rationale documented in `docs/specs/SPEC-004.md`.
