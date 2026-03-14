# Troubleshooting — claude-dev-kit

Common issues and solutions when using the claude-dev-kit pipeline.

## Checkpoint Failures

### Problem: verify_checkpoint.py fails with "command not found"
- **Symptom**: Exit code 127, error message mentions `gh: command not found`
- **Cause**: GitHub CLI (`gh`) is not installed or not in PATH
- **Solution**: Install `gh` via `brew install gh` (macOS) or see https://cli.github.com/. Then run `gh auth login`.

### Problem: Checkpoint times out
- **Symptom**: Exit code 124, error message mentions "timed out"
- **Cause**: Network issues or GitHub API rate limiting
- **Solution**: Check your internet connection. If rate-limited, wait a few minutes and retry. The script retries automatically up to 2 times for network commands.

### Problem: Checkpoint fails with "issues.md not found"
- **Symptom**: FAIL message mentioning issues.md path
- **Cause**: Running verify_checkpoint.py from a worktree where issues.md doesn't exist
- **Solution**: The script should auto-detect the repo root. Ensure `scripts/worktree.sh` exists or that you're in a valid git repository.

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
