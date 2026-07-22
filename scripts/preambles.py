#!/usr/bin/env python3
"""Preamble content generators for each tier.

Session-level startup (kit update check, contributor-mode detection) moved to
the SessionStart hook in ISSUE-032 — preambles carry only what the specific
skill tier uses at task time.

Tier 1: Lightweight skills (brainstorm, prd, bizanalysis, etc.)
Tier 2: Pipeline skills (implement, review, ship, kickoff, diagnose)
Tier 3: Orchestration skills (sprint)
"""

SKILL_TIERS: dict[str, int] = {
    "brainstorm": 1,
    "prd": 1,
    "bizanalysis": 1,
    "issue": 1,
    "uiux": 1,
    "mobile-uiux": 1,
    "desktop-uiux": 1,
    "testgen": 1,
    "devops": 1,
    "migrate": 1,
    "refactor": 1,
    "implement": 2,
    "review": 2,
    "ship": 2,
    "scan": 1,
    "kickoff": 2,
    "diagnose": 2,
    "sprint": 3,
}

# -- Tier 1 sections --------------------------------------------------------

# ${CLAUDE_PLUGIN_ROOT} below is NOT a shell variable: Claude Code substitutes
# it as load-time TEXT replacement in plugin-installed skill bodies (verified
# live 2026-07-22, ISSUE-035). It is NOT exported to the model's shell, so the
# section teaches the model to use the substituted absolute path directly.
_KIT_SCRIPT_ROOT = """\
### Kit Script Root
Kit root: `${CLAUDE_PLUGIN_ROOT}`
- Absolute path above → plugin install (substituted at load time; no project
  `scripts/` dir): prefix every kit script command with it, e.g.
  `bash <kit-root>/scripts/checkpoint.sh …`. Absolute paths also work from worktrees.
- Literal `${…}` placeholder above → standalone layout: run commands as written."""

_PROJECT_CONTEXT = """\
### Project Context Detection
Run these checks silently at the start. Use results to adapt behavior:
- `[ -f issues.md ]` — if true, this project uses the sprint system. Respect issue numbering and STATUS.md.
- `[ -f docs/sprint_state.md ]` — if true and Status shows `running`, a sprint is active. Be aware of parallel work in worktrees.
- `[ -f docs/prd_digest.md ]` — if true, read it for quick project context before starting."""

_BEHAVIORAL_RULES = """\
### Kit Rules
- Verify `gh auth status` before any GitHub operation."""

# -- Tier 2 sections --------------------------------------------------------

_CHECKPOINT_PATTERN = """\
### Checkpoint Verification Pattern
Every phase has a checkpoint. Run the verification command and check the exit code.
- Exit non-zero (blocking gate): **STOP immediately**, report failure, do NOT proceed.
- Exit 0 with an `ADVISORY:` line (advisory gate): report the gap, self-correct, continue.
Standard prefix:
```
bash scripts/checkpoint.sh
```
Append `--skill <name> --phase <phase> --issue <ID>` for the specific check.
`checkpoint.sh` resolves the main repo root internally, so the command stays
a single prefix-matchable form (safe to allowlist as `Bash(bash scripts/checkpoint.sh *)`)."""

_WORKTREE_PATTERN = """\
### Worktree Setup Pattern
Pipeline skills operate in git worktrees to isolate changes from main.
- Create + freeze: `WT="$(bash scripts/wt_setup.sh <branch>)"` — creates the
  worktree via `scripts/worktree.sh create` and writes `.claude-kit/freeze-dir.txt`
  inside it in a single step.
- Resolve main root: `bash scripts/worktree.sh root`
- Remove safely: `bash scripts/wt_cleanup.sh <branch>` — cd's to main root
  inside a subshell, then removes the worktree (never leaves CWD dangling).
All file operations happen inside `$WT/`. Shared files live on main only."""

_REGISTRY_UPDATE_PATTERN = """\
### Registry Update Pattern
Shared files (`issues.md`, `STATUS.md`, `CHANGELOG.md`) are managed on main only.
Always use `registry_edit.sh` for concurrent-safe writes — it resolves the
main repo root internally and delegates to `flock_edit.sh`:
```bash
bash scripts/registry_edit.sh issues.md -- bash -c '<update command>'
```
Never commit these files to feature branches."""

# -- Tier 3 sections --------------------------------------------------------

_PARALLEL_MANAGEMENT = """\
### Parallel Management Rules
- Respect the `--parallel N` limit for concurrent subagent tasks.
- Use the Task tool for subagent dispatch; track completion in `docs/sprint_state.md`.
- Each parallel track is independent; do not share mutable state between tracks.
- Use `registry_edit.sh` for any shared file writes (issues.md, STATUS.md)."""

_ESCALATION_RETRY = """\
### Escalation and Retry Logic
- If a subagent fails: retry once with the same context.
- If the retry fails: mark the issue as `Status: waiting`, `Reason: <failure-type>` in sprint_state.md.
- After 2 consecutive review failures on the same issue, defer it and move to the next.
- After 3 total failures across any issues, escalate to the user with a summary.
- Report all escalations and deferred issues in the sprint summary."""


def preamble_tier1(skill_name: str) -> str:
    """Generate Tier 1 preamble (lightweight skills)."""
    sections = [
        f"## Kit Preamble — {skill_name}",
        _KIT_SCRIPT_ROOT,
        _PROJECT_CONTEXT,
        _BEHAVIORAL_RULES,
    ]
    return "\n\n".join(sections)


def preamble_tier2(skill_name: str) -> str:
    """Generate Tier 2 preamble (pipeline skills). Includes all of Tier 1."""
    sections = [
        f"## Kit Preamble — {skill_name}",
        _KIT_SCRIPT_ROOT,
        _PROJECT_CONTEXT,
        _BEHAVIORAL_RULES,
        _CHECKPOINT_PATTERN,
        _WORKTREE_PATTERN,
        _REGISTRY_UPDATE_PATTERN,
    ]
    return "\n\n".join(sections)


def preamble_tier3(skill_name: str) -> str:
    """Generate Tier 3 preamble (orchestration skills). Includes all of Tier 2."""
    sections = [
        f"## Kit Preamble — {skill_name}",
        _KIT_SCRIPT_ROOT,
        _PROJECT_CONTEXT,
        _BEHAVIORAL_RULES,
        _CHECKPOINT_PATTERN,
        _WORKTREE_PATTERN,
        _REGISTRY_UPDATE_PATTERN,
        _PARALLEL_MANAGEMENT,
        _ESCALATION_RETRY,
    ]
    return "\n\n".join(sections)


_TIER_GENERATORS = {
    1: preamble_tier1,
    2: preamble_tier2,
    3: preamble_tier3,
}


def generate_preamble(skill_name: str) -> str:
    """Generate preamble content for the given skill based on its tier."""
    tier = SKILL_TIERS.get(skill_name, 1)
    generator = _TIER_GENERATORS[tier]
    return generator(skill_name)
