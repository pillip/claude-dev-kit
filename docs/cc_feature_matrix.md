# Claude Code Feature / Version Support Matrix

> **Purpose (ISSUE-014).** Single source of truth for which Claude Code capabilities the kit may rely on, so ISSUE-015/016/017 reference this instead of re-investigating. Verify against the *targeted* build, not memory — doc briefings drift from installed builds.

## Targeted version

- **Verified local build:** `2.1.185 (Claude Code)` — `claude --version`, 2026-06-22.
- **Kit minimum target:** **≥ 2.1.185** (the floor we have actually probed). All features below are present in the official docs current as of 2026-06-19; exact per-feature *introduction* versions are **UNVERIFIED** (would require changelog archaeology) but all are confirmed available at/above this floor.
- **Where enforced:** documented as a prerequisite in `README.md`. A hard gate (`requiredMinimumVersion`) is **not** available to the kit unless it ships as managed settings — see row 9.

## Verification levels

- **doc** — confirmed in official docs with a cited URL (via `claude-code-guide`, 2026-06-22).
- **local** — exercised against the installed 2.1.185 build.
- **needs-verify** — not yet exercised locally; adopt behind a fallback or probe before relying on it.

## Matrix

| # | Feature | Status | Verified | Notes for adoption | Consumer |
|---|---------|--------|----------|--------------------|----------|
| 1 | Agent `effort:` frontmatter | **supported** | doc | Values `low/medium/high/xhigh/max`. `xhigh`/`max` are **model-dependent** (Opus 4.7/4.8, Fable 5 only; Opus 4.6 & Sonnet 4.6 cap at `high`). `max` is **session-only — not accepted in frontmatter/settings**. CC auto-falls-back to the highest supported level ≤ requested, so `xhigh` is safe to set even where unsupported. | ISSUE-015 |
| 2 | Agent `model: inherit` | **supported** | doc | Resolves via normal model resolution instead of overriding. | ISSUE-015 |
| 3 | Model aliases (`opus`/`sonnet`/`haiku`/`fable`/`best`) | **supported** | doc + local | `opus`→4.8 (API), **→4.6 on Bedrock/Vertex/Foundry**; `sonnet`→4.6; `haiku`→4.5; `fable`→Fable 5; `best`→Fable 5 (else latest Opus). Kit already uses aliases (21×`opus`, 12×`sonnet`). **Caveat:** on Bedrock/Vertex `opus`→4.6, which lacks `xhigh` — relevant to row 1. | ISSUE-015 |
| 4 | Hook event `WorktreeCreate` | **supported** | doc / needs-verify | Exists. Not yet exercised locally — probe a no-op hook before removing the imperative `wt_setup.sh` freeze-write. | ISSUE-016 |
| 4b | Hook event `WorktreeRemove` | **supported** | doc | Exists (companion to WorktreeCreate). | ISSUE-016 |
| 4c | Hook events `SessionEnd` / `Stop` | **supported** | doc | Both exist; suitable for `.claude/run/` cleanup. | ISSUE-016 |
| 4d | Hook events `PreCompact` / `PostCompact` | **supported** | doc | Exist; out of scope for 016 (noted as future). | (future) |
| 5 | Plugin manifest `.claude-plugin/plugin.json` + `hooks.json` + `.mcp.json` | **supported** | doc | Full plugin component schema present. | ISSUE-017 |
| 5b | `${CLAUDE_PLUGIN_ROOT}` / `${CLAUDE_PLUGIN_DATA}` | **supported** | doc | `CLAUDE_PLUGIN_ROOT` replaces the repo-root `scripts/` symlink; `CLAUDE_PLUGIN_DATA` survives updates. | ISSUE-017 |
| 5c | `/plugin install`, marketplaces, versioning | **supported** | doc | Scopes user/project/local; curated + custom marketplaces; `version` field or git SHA. | ISSUE-017 |
| 6 | **Plugin subagents ignore `hooks`/`mcpServers`/`permissionMode`** | **confirmed limitation** | doc | Official: *"For security reasons, `hooks`, `mcpServers`, and `permissionMode` are not supported for plugin-shipped agents."* The kit's `/freeze`, `/careful`, `/guard` embed `hooks:` in frontmatter → **must move to `hooks.json`** under a plugin. Plugin agents DO support `name/description/model/effort/maxTurns/tools/disallowedTools/skills/memory/background/isolation:"worktree"`. | ISSUE-017 (blocking design constraint) |
| 7 | Plugin skill/command namespacing | **supported (mandatory)** | doc | Plugin skills become `/<plugin>:<skill>` (e.g. `/kit:implement`); cannot be disabled. Standalone `.claude/` skills keep short names. | ISSUE-017 |
| 8 | `fallbackModel` setting | **supported** | doc | Array of ≤3 models/aliases, tried in order; **not merged across settings files** (highest-precedence file supplies the whole chain); `--fallback-model` overrides per session. | ISSUE-015 |
| 9 | `requiredMinimumVersion` for the kit | **partial** | doc | `minimumVersion`/`requiredMinimumVersion`/`requiredMaximumVersion` gate the **Claude Code** version but live in **settings** (`requiredMinimumVersion` is managed-settings-only, hard-blocks startup). **`plugin.json` has NO version-floor field** — a plugin can only declare semver deps on *other plugins* via `dependencies`. So the kit cannot self-declare "needs CC ≥ X" from its manifest; enforce via README + optional managed settings. | ISSUE-017 |

## Readiness verdict per dependent issue

- **ISSUE-015 (effort tiers + model refresh)** — **GREEN.** Set `effort: xhigh` (or `high`) on heavy agents, `low/medium` on extraction agents; `xhigh` is safe everywhere thanks to auto-fallback, but note Bedrock/Vertex `opus`→4.6 caps at `high`. Add `fallbackModel` (≤3, single highest-precedence file). Refresh the stale model id in `README.md` (~line 726).
- **ISSUE-016 (lifecycle hooks)** — **GREEN with a probe.** All needed events exist; locally exercise `WorktreeCreate` before dropping the imperative freeze-write, and keep the `wt_setup.sh` fallback for older builds.
- **ISSUE-017 (plugin migration SPEC)** — **GREEN; design around row 6 & 9.** Plugin system is fully present. The SPEC must (a) move `/freeze`,`/careful`,`/guard` hooks from frontmatter to `hooks.json`, (b) account for mandatory `/kit:` namespacing, (c) note the kit cannot declare a CC min-version in `plugin.json`.

## Sources

Verified 2026-06-22 via official docs (cited inline):
- `https://code.claude.com/docs/en/model-config.md` — effort levels, model aliases, fallback chains
- `https://code.claude.com/docs/en/agent-sdk/subagents.md` — `model: inherit`
- `https://code.claude.com/docs/en/plugins-reference.md` — hook events (33 total), plugin schema, plugin-agent field restrictions (line 71)
- `https://code.claude.com/docs/en/plugins.md` — namespacing
- `https://code.claude.com/docs/en/settings.md` — `minimumVersion` / `requiredMinimumVersion` / `requiredMaximumVersion`

> Re-run the probe (`claude --version` + a no-op `WorktreeCreate` hook + an `effort:` agent) when bumping the targeted version; update the `needs-verify` rows to `local` once exercised.
