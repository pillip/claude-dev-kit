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
