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
| 2 | Agent `model: inherit` | **supported — kit default since ISSUE-030** | doc | Resolves via normal model resolution instead of overriding. **All 33 core + 5 sales agents ship without `model:` (= inherit)**; a pin may return only with an adjacent `# pin:` rationale (enforced by `test_agent_effort.py`). Deterministic deployments pin once at session/project level (`model` setting / `--model`). | ISSUE-015 / 030 |
| 3 | Model aliases (`opus`/`sonnet`/`haiku`/`fable`/`best`) | **supported** | doc + local | `opus`→4.8 (API), **→4.6 on Bedrock/Vertex/Foundry**; `sonnet`→4.6; `haiku`→4.5; `fable`→Fable 5; `best`→Fable 5 (else latest Opus). Kit agents no longer pin aliases (ISSUE-030 — inherit sidesteps alias drift entirely); aliases remain relevant for `fallbackModel` and session-level pins. | ISSUE-015 / 030 |
| 4 | Hook event `WorktreeCreate` | **supported — CREATOR contract; kit must NOT register it** | doc + local (live probe 2026-07-22) | Official docs: *"The hook is responsible for creating the worktree… It replaces default git behavior"* — the hook must print the created worktree path (stdout / `hookSpecificOutput.worktreePath`); **no output aborts creation, with no built-in fallback**. Live probe confirmed: the kit's passive `worktree_freeze.py` hook fired, returned nothing, and **broke native worktree creation** for the plugin-installed project. Hook + handler removed in ISSUE-027; the freeze marker is written by `scripts/wt_setup.sh` on the skill path (the only supported path). A guard test (`test_plugin_manifest.py`) fails if a WorktreeCreate hook is re-added. | ISSUE-016 / 023 / 027 |
| 4b | Hook event `WorktreeRemove` | **supported** | doc | Exists (companion to WorktreeCreate). | ISSUE-016 |
| 4c | Hook events `SessionEnd` / `Stop` | **supported** | doc | Both exist; suitable for `.claude/run/` cleanup. | ISSUE-016 |
| 4d | Hook events `PreCompact` / `PostCompact` | **supported** | doc | Exist; out of scope for 016 (noted as future). | (future) |
| 5 | Plugin manifest `.claude-plugin/plugin.json` + `hooks.json` + `.mcp.json` | **supported** | doc | Full plugin component schema present. | ISSUE-017 |
| 5b | `${CLAUDE_PLUGIN_ROOT}` / `${CLAUDE_PLUGIN_DATA}` | **supported** | doc | `CLAUDE_PLUGIN_ROOT` replaces the repo-root `scripts/` symlink. **`CLAUDE_PLUGIN_DATA` is a single GLOBAL dir per plugin** (`~/.claude/plugins/data/{id}/`), shared across all projects — for persistent tooling (deps/caches), **NOT** per-project/per-session ephemeral state. Per-project state stays in `<project>/.claude/run/`; worktree markers stay in the worktree. (This is why ISSUE-024 was dropped.) | ISSUE-017 / 023 |
| 5c | `/plugin install`, marketplaces, versioning | **supported** | doc | Scopes user/project/local; curated + custom marketplaces; `version` field or git SHA. | ISSUE-017 |
| 6 | **Plugin _agents_ ignore `hooks`/`mcpServers`/`permissionMode`** | **confirmed limitation (agents only)** | doc | Official: *"For security reasons, `hooks`, `mcpServers`, and `permissionMode` are not supported for plugin-shipped agents."* Applies to **agents only**. Plugin agents DO support `name/description/model/effort/maxTurns/tools/disallowedTools/skills/memory/background/isolation:"worktree"`. **Correction (2026-06-22):** this restriction does **NOT** extend to skills — see row 6b. | ISSUE-017 |
| 6b | **Plugin _skills_ honor `hooks:` in frontmatter** | **supported** | doc | Official (`hooks.md`, "Hooks in Skill Frontmatter"): skill frontmatter hooks work for both standalone and plugin-shipped skills, scoped to when the skill is active. So `/freeze`,`/careful`,`/guard` do **NOT** need to move to `hooks.json`. **Caveat:** `${CLAUDE_SKILL_DIR}` is **undocumented** (only `${CLAUDE_PROJECT_DIR}`/`${CLAUDE_PLUGIN_ROOT}`/`${CLAUDE_PLUGIN_DATA}` are documented) — skill hook commands should resolve via documented vars with a fallback. | ISSUE-022 |
| 7 | Plugin skill/command namespacing | **supported (mandatory)** | doc | Plugin skills become `/<plugin>:<skill>` (e.g. `/kit:implement`); cannot be disabled. Standalone `.claude/` skills keep short names. | ISSUE-017 |
| 8 | `fallbackModel` setting | **supported** | doc | Array of ≤3 models/aliases, tried in order; **not merged across settings files** (highest-precedence file supplies the whole chain); `--fallback-model` overrides per session. | ISSUE-015 |
| 9 | `requiredMinimumVersion` for the kit | **partial** | doc | `minimumVersion`/`requiredMinimumVersion`/`requiredMaximumVersion` gate the **Claude Code** version but live in **settings** (`requiredMinimumVersion` is managed-settings-only, hard-blocks startup). **`plugin.json` has NO version-floor field** — a plugin can only declare semver deps on *other plugins* via `dependencies`. So the kit cannot self-declare "needs CC ≥ X" from its manifest; enforce via README + optional managed settings. | ISSUE-017 |

## Readiness verdict per dependent issue

- **ISSUE-015 (effort tiers + model refresh)** — **GREEN.** Set `effort: xhigh` (or `high`) on heavy agents, `low/medium` on extraction agents; `xhigh` is safe everywhere thanks to auto-fallback, but note Bedrock/Vertex `opus`→4.6 caps at `high`. Add `fallbackModel` (≤3, single highest-precedence file). Refresh the stale model id in `README.md` (~line 726).
- **ISSUE-016 (lifecycle hooks)** — **GREEN with a probe.** All needed events exist; locally exercise `WorktreeCreate` before dropping the imperative freeze-write, and keep the `wt_setup.sh` fallback for older builds.
- **ISSUE-017 (plugin migration SPEC)** — **GREEN; design around row 6 & 9.** Plugin system is fully present. The SPEC must (a) **keep** `/freeze`,`/careful`,`/guard` hooks in skill frontmatter (supported for plugin skills, row 6b) while fixing the undocumented `${CLAUDE_SKILL_DIR}` resolution, (b) account for mandatory `/kit:` namespacing, (c) note the kit cannot declare a CC min-version in `plugin.json`.

## Sources

Verified 2026-06-22 via official docs (cited inline):
- `https://code.claude.com/docs/en/model-config.md` — effort levels, model aliases, fallback chains
- `https://code.claude.com/docs/en/agent-sdk/subagents.md` — `model: inherit`
- `https://code.claude.com/docs/en/plugins-reference.md` — hook events (33 total), plugin schema, plugin-agent field restrictions (line 71)
- `https://code.claude.com/docs/en/plugins.md` — namespacing
- `https://code.claude.com/docs/en/settings.md` — `minimumVersion` / `requiredMinimumVersion` / `requiredMaximumVersion`

> Re-run the probe (`claude --version` + a no-op `WorktreeCreate` hook + an `effort:` agent) when bumping the targeted version; update the `needs-verify` rows to `local` once exercised.
