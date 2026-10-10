# Troubleshooting — claude-dev-kit

Common issues and solutions when using the claude-dev-kit pipeline.

## Checkpoint Failures

### Problem: verify_checkpoint.py fails with "command not found"
- **Symptom**: Exit code 127, error message mentions `gh: command not found`
- **Cause**: GitHub CLI (`gh`) is not installed or not in PATH
- **Solution**: Install `gh` via `brew install gh` (macOS) or see https://cli.github.com/. Then run `gh auth login`.

### Problem: Checkpoint times out
- **Symptom**: Exit code 124, error message mentions "timed out"
- **Cause**: Network issues or GitHub API rate limiting; or, for test-phase checkpoints (implement `red`/`test`, ship `smoke`), a test suite that runs longer than the test timeout (default 600 seconds). The same timeout applies to the platform `unit` gate run by `scripts/verify_gates.py` (e.g. during ship's blocking gates)
- **Solution**: For network commands, check your internet connection; if rate-limited, wait a few minutes and retry (the script retries automatically up to 2 times). For slow test suites, raise the timeout via the `KIT_CHECKPOINT_TEST_TIMEOUT` env var (seconds), e.g. `KIT_CHECKPOINT_TEST_TIMEOUT=1200`. Invalid or non-positive values fall back to the default. Note: a RED-phase run that times out is reported as inconclusive and FAILS — a timeout is not accepted as proof of a failing suite.

### Problem: Checkpoint fails with "issues.md not found"
- **Symptom**: FAIL message mentioning issues.md path
- **Cause**: Running verify_checkpoint.py from a worktree where issues.md doesn't exist
- **Solution**: The script should auto-detect the repo root. Ensure `scripts/worktree.sh` exists or that you're in a valid git repository.

### Problem: Visual-diff / computed-styles gate reports "browser unavailable"
- **Symptom**: The visual-diff or computed-styles gate is skipped with a "browser unavailable" note on stderr
- **Cause**: Playwright/Chromium is not installed, and by default the gate will not install it — a review/CI gate must not mutate its environment or hit the network as a silent side effect
- **Solution**: Set `KIT_ALLOW_BROWSER_INSTALL=1` to auto-install Playwright + Chromium before the gate runs. If you leave it unset the skip is intentional, not a failure.

### Problem: Sprint queue PR merge-state probe is slow or hangs
- **Symptom**: The sprint queue stalls while checking a PR's merge state against an offline or hung `gh`
- **Cause**: The `gh pr view` merge-state probe in `scripts/sprint_queue.py` is timeout-bounded so a stuck `gh` never blocks the frequently-run queue
- **Solution**: `KIT_SPRINT_QUEUE_GH_TIMEOUT` defaults to `10` seconds; on timeout the probe degrades to a phase-only decision. Override the bound by exporting `KIT_SPRINT_QUEUE_GH_TIMEOUT=<seconds>`.

### Problem: Sprint queue emits `SHIP` instead of `FINALIZE` with a "refusing PR ref" warning
- **Symptom**: a reviewed issue whose PR is already merged is still queued as `SHIP` (not `FINALIZE`), and stderr carries `Warning: refusing PR ref '...' read from the issues.md 'PR:' field`
- **Cause**: the `PR:` value in `issues.md` is not one of the three accepted forms, so the ISSUE-073 whitelist refuses to hand `gh` a ref whose **shape** it cannot confirm. What the whitelist attests is narrow and worth stating exactly: the value is not option-shaped and is `github.com`-hosted — **not** that the ref denotes this issue's PR. Common triggers, in order of likelihood:
  - a **compound** value such as `#122 https://github.com/<owner>/<repo>/pull/122` (two of which exist in this repo's own Board)
  - a `/files`- or `/commits`-suffixed PR URL pasted from the browser address bar, or a `www.github.com` host — `gh` itself resolves both, so these refuse a ref that would otherwise have worked. The whitelist is deliberately narrower than `gh`; widening it for an unattested shape is the fail-open direction.
- **Solution**: normalize the `PR:` field to a single accepted form — `123`, `#123`, or the full `https://github.com/<owner>/<repo>/pull/123` URL. The refusal is fail-safe, not a blocker: the ship path still runs and the real `gh pr merge` surfaces the true state. Normalizing also removes a reader divergence — `scripts/verify_checkpoint.py` reads the same field with a trailing-digits `re.search`, so it accepts compound values that `sprint_queue.py` refuses.

## Sprint Queue Visibility

### Problem: Sprint queue exits 2 refusing to dispatch off an "under-read roster"
- **Symptom**: `scripts/sprint_queue.py next-action` prints **nothing** on stdout and exits `2`; stderr opens with `Error: N Issue Progress roster row(s) were not parsed — refusing to dispatch off an under-read roster` and then names the offender on a `First unparsed row:` line. `/sprint` stops the loop, since it treats a non-zero exit with no JSON output as a hard stop
- **Cause**: the queue reads **exactly** the contiguous pipe rows of the `## Issue Progress` table — per GFM the table ends at the first line that is not a table row (blank, whitespace-only, prose, or a heading of **any** level), and a row must carry exactly 5 cells (`Issue | Status | Attempts | Last Error | Phase`). Dropped rows are refused rather than ignored because a dropped row is not merely absent: the issue still reads `Status: backlog` in `issues.md`, so the queue would re-materialize it as fresh backlog work and re-run an already-reviewed issue from scratch (the synthesized row also resets Attempts to 0, so the ≥3-attempt escalation never fires). Two triggers:
  - a stray blank, **whitespace-only** (invisible in an editor), or prose line inside the table — every row beneath it is dropped
  - a row whose cell count is not 5 — most often an unescaped `|` in the `Last Error` cell, since that text is executor output
- **Solution**: apply the fix the error already names — delete the stray line, escape `|` as `\|` inside cells, or move non-roster rows under their own heading. A `### …` subsection table (e.g. `### Review outcomes`) and a fenced code-block example are both excluded by design, so neither is ever the cause. `validate` keeps its JSON verdict and exit code unchanged, but prints the same cause as `Warning: N Issue Progress roster row(s) were not parsed (stray line inside the table, or a non-5-column row); first: …` on stderr — so a target that reports `stuck` right after a successful phase is explained there

### Problem: Sprint reports DONE while `issues.md` still has backlog issues
- **Symptom**: `scripts/sprint_queue.py next-action` prints `"action": "DONE"` together with a `"stranded": ["ISSUE-NNN", ...]` list and a warning appended to `reason`
- **Cause**: those issues are registered in `issues.md` with `Status: backlog` but have no row in the `docs/sprint_state.md` Issue Progress table, and the queue could not dispatch them — normally an unresolved `Depends-On`. The `stranded` list names the issues, not the cause, and a blocker can itself be an issue the queue does not list (see the next entry). The action stays `DONE` and the exit code stays `1`, exactly as for a clean sprint, so the `stranded` key and the `reason` warning are the only signal
- **Solution**: resolve the blocking dependency, or add rows for the issue **and its blocker** to the Issue Progress table (column order `Issue | Status | Attempts | Last Error | Phase`, with `backlog` in the Phase cell) and re-run `/sprint`

### Problem: A newly filed issue is never picked up by the sprint queue
- **Symptom**: an `issues.md` issue with `Status: backlog` is neither dispatched nor listed in `next-action`'s `unrostered` field
- **Cause**: an issue with no Issue Progress row is auto-considered only when its number is **above** the highest `ISSUE-NNN` already in that table, `Manual` is not `true`, and `Status` is exactly `backlog` — an annotated value such as `backlog (blocked on vendor)` is deliberately not admitted, so the queue fails closed rather than dispatching something a human gated. The boundary is re-derived from the table on every run, so rostering a higher-ID issue first drops its lower-ID siblings below it
- **Solution**: add a row for the issue to the Issue Progress table — a rostered issue is always considered, whatever its number. Keep `Status:` to the bare `backlog` keyword and put qualifiers elsewhere in the issue body, and roster newly discovered issues in ascending ID order

## GitHub Authentication

### Problem: `gh auth status` fails
- **Symptom**: Skills stop at pre-condition check with auth error
- **Cause**: Not logged into GitHub CLI
- **Solution**: Run `gh auth login` and follow the prompts. Use HTTPS protocol for simplest setup.

### Problem: `gh issue create` or `gh pr create` fails with 403
- **Symptom**: Permission denied when creating issues or PRs
- **Cause**: Token lacks required scopes
- **Solution**: Run `gh auth refresh -s repo` to add the `repo` scope.

## Worktree Issues

### Problem: Worktree creation fails with "already exists"
- **Symptom**: `scripts/worktree.sh create` fails
- **Cause**: A previous run left a stale worktree
- **Solution**: List worktrees with `git worktree list`, then remove the stale one with `cd "$(bash scripts/worktree.sh root)" && bash scripts/worktree.sh remove <branch>`.

### Problem: Shell stuck in deleted worktree directory
- **Symptom**: Commands fail with "No such file or directory" after worktree removal
- **Cause**: The `cd` and `remove` commands were run in separate shell invocations
- **Solution**: Always combine as: `cd "$(bash scripts/worktree.sh root)" && bash scripts/worktree.sh remove <branch>`. Navigate to the repo root first.

### Problem: Worktree not found for issue
- **Symptom**: FAIL message "no worktree found matching 'issue-NNN'"
- **Cause**: Worktree was never created, or the branch slug doesn't match the expected pattern
- **Solution**: Create the worktree with the correct slug: `bash scripts/worktree.sh create <type>/<issue-slug>`.

## validate_issues.py Warnings

### Problem: "circular dependency detected"
- **Symptom**: validate_issues.py reports a cycle in Depends-On references
- **Cause**: Two or more issues form a dependency loop (A→B→A)
- **Solution**: Edit `issues.md` to break the cycle. Usually one dependency is incidental and can be removed.

### Problem: "dependency chain depth is N (warning: > 3)"
- **Symptom**: A deep chain of sequential dependencies
- **Cause**: Issues are over-decomposed or have unnecessary sequential constraints
- **Solution**: Review the dependency chain. Consider parallelizing work by removing non-essential Depends-On links.

### Problem: "Depends-On references ISSUE-XXX which does not exist"
- **Symptom**: Dangling reference in Depends-On field
- **Cause**: Referenced issue was removed or renumbered
- **Solution**: Update the Depends-On field to reference the correct issue ID, or set to "none" if no dependency exists.
