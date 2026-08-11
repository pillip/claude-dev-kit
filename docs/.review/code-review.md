# Code Review — ISSUE-042 (PR #64, branch issue/ISSUE-042-sprint-disable-model-invocation @ 82016f5)

Degraded-path review. Dimension: CODE (correctness/quality) + Over-Engineering minimality axis.
Runtime `/code-review` unavailable; security dimension NOT covered here (out of this invocation's scope).

## Verdict

**Approve with non-blocking Low findings.** Both ACs verified empirically. No blocking issues.

## AC Verification (evidence, executed in the worktree)

- **AC1 PASS** — `skills/sprint/SKILL.md` frontmatter YAML-parses to a dict with
  `disable-model-invocation == True` (bool, PyYAML `safe_load`). `python3 scripts/validate_frontmatter.py`:
  55 files clean. `python3 scripts/gen_skills.py --dry-run`: "All 20 SKILL.md files are fresh"
  (tmpl and generated file in sync).
- **AC2 PASS** — sandbox regression runs (scratchpad copy, worktree untouched):
  - flag set `false` → exit 1, message `sprint: disable-model-invocation is set to 'false' — …` (names skill and value)
  - flag line removed → exit 1, `sprint: frontmatter lacks disable-model-invocation — …` (names skill)
  - `SKILL.md` deleted → exit 1, `sprint: generated skills/sprint/SKILL.md not found`
  - baseline (all six true) → 6 passed in 0.02s
- **Scope PASS** — diff is exactly 3 files / 49 insertions / 0 deletions. One identical line in
  `SKILL.md.tmpl` and generated `SKILL.md`; no workflow-body or allowed-tools drift; no flags flipped
  on non-orchestrator skills. Full suite collects 1176 tests with no import errors or name collisions.
- **Recalled review lessons** — (1) hard-coded subprocess timeouts: no subprocess calls anywhere in the
  diff; n/a. (2) env-var knobs: none added; n/a. (3) delegation-seam mocking / recursive pytest spawn:
  verified the test reads files via `Path.read_text` only — no subprocess, no pytest-in-pytest, no mocks
  needed. Hermetic: no network, no writes, no mutation.

## Findings

### [Low] Missing closing-fence check lets the guard scan the document body
- **Evidence**: `tests/test_orchestrator_disable_model_invocation.py:27` —
  `return text.split("---", 2)[1].splitlines()`. If a file starts with `---\n` but lacks a closing
  `---`, `split` returns only 2 parts and `[1]` is the ENTIRE remainder of the file. Empirically
  demonstrated false-pass: a fence-less file with `disable-model-invocation: true` only in the body
  passes the guard. The docstring claims to mirror `scripts/validate_frontmatter.py`, but the oracle
  guards this exact case (`scripts/validate_frontmatter.py:39-40`: `parts[1] if len(parts) >= 3 else None`).
- **Impact**: false-pass requires two simultaneous defects (missing fence AND key at line-start in the
  body), and `validate_frontmatter.py` in the release gate independently rejects fence-less files as
  "no frontmatter block at byte 0" — so no realistic path to shipping a bad file. Low, not Medium.
- **Fix**: in `_frontmatter_lines`, split once and assert `len(parts) >= 3` with a message like
  `f"{path}: frontmatter closing '---' not found"` before returning `parts[1].splitlines()`.

### [Low] First-match-wins diverges from YAML last-wins on duplicate keys
- **Evidence**: `tests/test_orchestrator_disable_model_invocation.py:42` — `return` after the first
  matching key. PyYAML `safe_load` silently takes the LAST duplicate. Empirically demonstrated:
  frontmatter containing `disable-model-invocation: true` followed by `disable-model-invocation: false`
  passes the guard while the effective parsed value is `false`.
- **Impact**: requires a duplicate key to be introduced in the tmpl (generated files are gen-locked by
  the `gen_skills.py --dry-run` freshness gate), and neither `validate_frontmatter.py` nor PyYAML flags
  duplicates — so this guard is the only line of defense for this case, but there is no plausible path
  to the state. Low.
- **Fix**: collect all occurrences instead of returning on the first; assert the list is exactly
  `["true"]` (catches both duplicates and wrong values in one assertion).

### [Low] `_frontmatter_lines` is copy-pasted from an existing test module
- **Evidence**: `tests/test_orchestrator_disable_model_invocation.py:24-27` is logic-identical to
  `tests/test_skill_frontmatter_yaml.py:21-24` (same `startswith` assert, same `split("---", 2)[1]`,
  same missing-fence weakness).
- **Impact**: duplication means the fence-check fix (finding 1) must be applied twice or will drift.
- **Fix**: extract one shared helper (e.g., `tests/conftest.py` or a small `tests/_frontmatter.py`) with
  the `len(parts) >= 3` guard added — one change fixes both files.

### [Low] [design] Frozen six-skill allowlist cannot catch a future orchestrator by itself — accepted
- **Evidence**: `tests/test_orchestrator_disable_model_invocation.py:17-21` — `ORCHESTRATOR_SKILLS`
  tuple with an explicit "adding a future orchestrator? Add it here as a conscious decision" comment.
- **Judgment**: acceptable. A property-derived detection (e.g., "any skill whose allowed-tools grants
  `Bash(git *)` + `Task` must set the flag") would auto-catch future orchestrators but adds heuristic
  complexity and false-positive risk; the comment makes the allowlist a deliberate registry, which
  matches the kit's lean bias. Non-blocking; no change requested.

## Edge-case probes (all empirically executed; conservative behavior confirmed)

- Indented key (`  disable-model-invocation: true`) → treated as absent → test fails. Correct: an
  indented key is not a top-level YAML key; not stripping `key` is stricter than the oracle in the
  right direction.
- `disable-model-invocation : true` (space before colon) → test fails demanding the canonical form.
  Stricter than YAML, acceptable for gen-produced canonical files (fails toward fixing, never toward
  a silent pass).
- Embedded `---` inside an earlier frontmatter value → frontmatter truncated at that point → key not
  found → test fails (conservative). Identical truncation behavior to the oracle's own
  `split("---", 2)`; consistent by construction. No current frontmatter value contains `---`.
- `disable-model-invocation:  true ` (extra whitespace) → passes via `value.strip()`. Correct.
- YAML comment `# disable-model-invocation: true` → key becomes `# disable-…` → skipped. Correct.
- `True` / `"true"` / `yes` variants → fail with "must set it to exactly 'true'". Intentional
  canonicalization of generated output; message says so explicitly. Correct.

## Environment observation (not attributable to the diff)

During review, one `grep` read of `skills/sprint/SKILL.md` in the worktree transiently showed
`disable-model-invocation: false` (file mtime 12:29:40, after the 12:19 checkout), then the file
immediately read back as `true`, matched `git show HEAD:skills/sprint/SKILL.md` exactly, md5 was
stable across three subsequent reads, and `git status` was clean. The diff under review contains no
code that writes files (the test is read-only), so the rewrite came from something outside the PR —
likely a local regeneration hook. The COMMITTED content at 82016f5 is verified correct. Flagging for
awareness only; if the merge-auditor sees flapping too, investigate local hooks, not this PR.

## Over-Engineering (minimality axis)

- `tests/test_orchestrator_disable_model_invocation.py:24`: shrink duplicate `_frontmatter_lines`
  helper → reuse/extract the identical helper already in `tests/test_skill_frontmatter_yaml.py:21`
  (shared conftest helper; also the seam for the fence-check fix)

Net removable lines: ~4. Everything else is load-bearing: the 9-line docstring carries the
ISSUE-042/ISSUE-021 rationale, the `path.exists()` assert exists for skill-named failure messages,
and the parametrize shape gives per-skill reporting. No delete/stdlib/native/yagni findings.

## Self-Review

1. **Severity re-assessment**: all Lows re-checked. Finding 1 was the Medium candidate; downgraded
   because the CI oracle gate (`validate_frontmatter.py`) independently rejects the precondition
   (fence-less file), leaving no pipeline path to a shipped regression. Finding 2 has no plausible
   path to the bad state at all. Neither causes data loss or hot-path failure.
2. **False positive check**: findings 1 and 2 are demonstrated by sandbox execution, not inspection;
   finding 3 verified by reading both files side by side. Not false positives.
3. **Blind spot scan**: re-checked encoding (explicit utf-8), CRLF (`startswith("---\n")` fails
   conservatively on CRLF; repo is LF), test isolation/order-dependence (module-level constants only,
   no state mutation), suite collection (1176 tests, clean), failure-message quality (all three modes
   name the skill and the file path). No additional findings surfaced.
4. **AC verification**: AC1 and AC2 both empirically PASS (see evidence above); scope constraints
   respected.
5. **Confidence**: **High** — every finding and every AC claim is backed by executed evidence in the
   worktree or a scratchpad sandbox. The single uncertainty (transient file rewrite) is external to
   the diff and flagged explicitly above.

## Synthesizer findings block

```json
[
  {
    "severity": "Low",
    "title": "Frontmatter helper misses closing-fence check; scans body when fence absent (diverges from validate_frontmatter.py oracle)",
    "evidence": "tests/test_orchestrator_disable_model_invocation.py:27 — text.split(\"---\", 2)[1] returns entire file remainder when no closing --- exists; empirically false-passes with key only in body. Oracle guards this at scripts/validate_frontmatter.py:39-40.",
    "fix": "Assert len(text.split(\"---\", 2)) >= 3 in _frontmatter_lines with a named failure message before indexing [1]."
  },
  {
    "severity": "Low",
    "title": "First-match-wins on duplicate disable-model-invocation keys; YAML last-wins would yield false while guard passes",
    "evidence": "tests/test_orchestrator_disable_model_invocation.py:42 — early return on first match; empirically passes on 'true' followed by 'false', which safe_load resolves to false.",
    "fix": "Collect all matching values and assert the list equals [\"true\"] (catches duplicates and wrong values together)."
  },
  {
    "severity": "Low",
    "title": "[shrink] _frontmatter_lines duplicated from tests/test_skill_frontmatter_yaml.py (both copies share the fence weakness)",
    "evidence": "tests/test_orchestrator_disable_model_invocation.py:24-27 vs tests/test_skill_frontmatter_yaml.py:21-24 — logic-identical helpers.",
    "fix": "Extract one shared helper (tests/conftest.py) with the closing-fence assert; ~4 net lines removed and one seam for the fix."
  },
  {
    "severity": "Low",
    "title": "[design] Frozen ORCHESTRATOR_SKILLS allowlist cannot self-detect future orchestrators — accepted as conscious-decision registry",
    "evidence": "tests/test_orchestrator_disable_model_invocation.py:17-21 — explicit comment directs future orchestrators to be added deliberately.",
    "fix": "No change requested; optionally add a heuristic companion check (skills granting Bash(git *) must set the flag) if orchestrators proliferate."
  }
]
```
