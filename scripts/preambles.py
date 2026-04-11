#!/usr/bin/env python3
"""Preamble content generators for each tier.

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

_UPDATE_CHECK = """\
### Kit Update Check
Run silently at the start:
```bash
python3 scripts/kit_update_check.py 2>/dev/null
```
If exit code is 1 (update available), show the output to the user once. Do not block the workflow."""

_PROJECT_CONTEXT = """\
### Project Context Detection
Run these checks silently at the start. Use results to adapt behavior:
- `[ -f issues.md ]` — if true, this project uses the sprint system. Respect issue numbering and STATUS.md.
- `[ -f docs/sprint_state.md ]` — if true and Status shows `running`, a sprint is active. Be aware of parallel work in worktrees.
- `[ -f docs/prd_digest.md ]` — if true, read it for quick project context before starting."""

_BEHAVIORAL_RULES = """\
### Behavioral Rules
- Verify `gh auth status` before any GitHub operation.
- Never commit secrets, API keys, or credentials. Use environment variables.
- Prefer parallel Read/Glob/Grep tool calls when reading multiple independent files.
- When uncertain about intent, ask the user rather than guessing.
- Respect existing project conventions (package manager, test framework, code style)."""

_CONTRIBUTOR_MODE = """\
### Contributor Mode
At the start of this skill, check if contributor mode is enabled:
```bash
python3 scripts/kit_config.py get contributor_mode
```
If the result is `true`:
1. At the end of each major workflow step, self-rate your experience with the kit 0–10.
2. If rating < 10 and there is an actionable improvement, file a field report:
   ```bash
   python3 scripts/contributor_report.py --skill <name> --step "<step>" --rating <N> --notes "<friction or suggestion>"
   ```
3. Maximum 3 reports per session. Skip if a report for the same step already exists.
4. Do NOT stop the workflow to file reports — do it inline.
5. Only report kit/skill issues (unclear instructions, missing checkpoints, bad ergonomics). Do NOT report user-app bugs or network errors."""

# -- Tier 2 sections --------------------------------------------------------

_CHECKPOINT_PATTERN = """\
### Checkpoint Verification Pattern
Every phase has a mandatory checkpoint. Run the verification command and check exit code.
If exit code is not 0, **STOP immediately** and report failure. Do NOT proceed to the next phase.
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

_SELF_REVIEW = """\
### Self-Review Requirements
Before completing any major phase, pause and verify:
- Does the output satisfy the stated acceptance criteria?
- Are there edge cases not covered?
- Could this break existing functionality?
- Rate confidence: **High** / **Medium** / **Low**. If Low, flag to the user before proceeding."""

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
        _UPDATE_CHECK,
        _PROJECT_CONTEXT,
        _BEHAVIORAL_RULES,
        _CONTRIBUTOR_MODE,
    ]
    return "\n\n".join(sections)


def preamble_tier2(skill_name: str) -> str:
    """Generate Tier 2 preamble (pipeline skills). Includes all of Tier 1."""
    sections = [
        f"## Kit Preamble — {skill_name}",
        _UPDATE_CHECK,
        _PROJECT_CONTEXT,
        _BEHAVIORAL_RULES,
        _CHECKPOINT_PATTERN,
        _WORKTREE_PATTERN,
        _REGISTRY_UPDATE_PATTERN,
        _SELF_REVIEW,
        _CONTRIBUTOR_MODE,
    ]
    return "\n\n".join(sections)


def preamble_tier3(skill_name: str) -> str:
    """Generate Tier 3 preamble (orchestration skills). Includes all of Tier 2."""
    sections = [
        f"## Kit Preamble — {skill_name}",
        _UPDATE_CHECK,
        _PROJECT_CONTEXT,
        _BEHAVIORAL_RULES,
        _CHECKPOINT_PATTERN,
        _WORKTREE_PATTERN,
        _REGISTRY_UPDATE_PATTERN,
        _SELF_REVIEW,
        _PARALLEL_MANAGEMENT,
        _ESCALATION_RETRY,
        _CONTRIBUTOR_MODE,
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
