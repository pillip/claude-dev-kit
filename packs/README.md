# Packs

> Opt-in domain bundles installed on top of the core engineering kit.

The core plugin (`/plugin install claude-dev-kit@claude-dev-kit`) provides the **core** layer: engineering skills (`/prd`, `/kickoff`, `/uiux`, `/sprint`, `/implement`, `/review`, `/ship`, `/spec`, …), the design pack (uiux, mobile-uiux, desktop-uiux), and the safety guardrails (`/careful`, `/freeze`, `/guard`).

Packs are **additive** domain bundles that depend on core. Each pack ships as its own plugin in the repo's marketplace (`.claude-plugin/marketplace.json`) with `dependencies: ["claude-dev-kit"]` in its `plugin.json` — installing a pack auto-installs core. There is no "pack-only" install mode.

## Currently Available

| Pack | What it adds | Audience |
|---|---|---|
| **core** (default) | 33 engineering agents + 22 engineering/design/safety skills | every project |
| **sales** | 5 sales agents + 5 sales skills + 7 sales templates | account / customer-success teams sharing a repo with engineering |

## Pack Structure

A pack lives under `packs/<name>/` with this layout:

```
packs/<name>/
├── .claude-plugin/plugin.json  # Plugin manifest (name, dependencies: ["claude-dev-kit"])
├── manifest.yaml       # Contents + depends_on (kit-internal pack lint)
├── README.md           # What this pack adds, opt-in install command
├── agents/             # *.md agent files
├── skills/             # <skill-name>/ directories
└── templates/          # *.md template files
```

## Manifest schema

```yaml
name: <pack-name>           # required, must match directory name
description: <one line>     # required
depends_on:                 # required — every pack at minimum depends on core
  - core
agents: [...]               # optional — list of *.md filenames under agents/
skills: [...]               # optional — list of skill directory names under skills/
templates: [...]            # optional — list of *.md filenames under templates/
```

Rules:
- `name` must equal the directory name (`packs/sales/manifest.yaml` → `name: sales`).
- `depends_on` must include `core`. Packs cannot exist without core because they share `/prd`, `/kickoff`, `/issue`, `/sprint`, hooks, and templates.
- Every path listed under `agents` / `skills` / `templates` must exist under the pack directory at the listed location.
- An entry must not duplicate an entry under another pack (same agent/skill/template filename across packs is currently a hard error — packs cannot redefine sibling entries).

## Validation

```bash
python3 scripts/validate_pack_manifest.py packs/sales/manifest.yaml
python3 scripts/validate_pack_manifest.py packs/           # validate every pack
```

The validator is the single source of truth for the manifest schema (kept as a pack-authoring lint after the installer's retirement in ISSUE-027).

## Adding a new pack

1. Create `packs/<name>/` with the directory layout above.
2. `git mv` your domain agents/skills/templates into the pack.
3. Write `manifest.yaml` (must include `depends_on: [core]`) and `.claude-plugin/plugin.json` (with `dependencies: ["claude-dev-kit"]`).
4. Write a one-page `README.md` for the pack.
5. Run `scripts/validate_pack_manifest.py packs/<name>/manifest.yaml` and `claude plugin validate packs/<name>`.
6. Register the pack in `.claude-plugin/marketplace.json`; users opt in with `/plugin install <plugin-name>@claude-dev-kit`.
