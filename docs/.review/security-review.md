# Security Review — ISSUE-042 (PR #64, branch issue/ISSUE-042-sprint-disable-model-invocation @ 82016f5)

Dimension: security only (degraded path — runtime /security-review unavailable).
Reviewer: degraded-path security auditor. Scope: 3-file diff vs main (49 insertions, 0 deletions).

## Verdict

Security-positive change. One Low finding on guard-test robustness; no Critical/High/Medium findings.

The change correctly closes the autonomous-invocation hole: `disable-model-invocation: true`
is now set on the sprint skill in both the template and the generated file, making sprint —
the heaviest repo-mutating orchestrator (allowed-tools includes `Bash(git *)`, `Bash(gh *)`,
`Bash(python3 scripts/*)`, `Task`, `Write`, `Edit`) — invocable only by explicit user
`/sprint`, never by autonomous model invocation (e.g., steered by prompt-injected repo
content). All six orchestrators (implement, review, ship, kickoff, scan, sprint) are now
consistent, each verified at `skills/<skill>/SKILL.md:4-5` in this worktree.

## Findings

### [Low] Guard test's first-match frontmatter parse can disagree with the runtime YAML parser on duplicate keys

- **Severity:** Low (requires a committed edit by someone who already has repo write access; no external attack vector — per policy, no-exploit-path caps at Medium, and this is theoretical, so Low).
- **Evidence:** `tests/test_orchestrator_disable_model_invocation.py:34-42` — the loop `return`s on the FIRST unindented `disable-model-invocation:` line and never inspects the rest of the frontmatter.
- **Impact:** If a later duplicate line `disable-model-invocation: false` were ever added to the frontmatter, the guard would still pass (first occurrence is `true`), while the runtime parser would either take last-wins (PyYAML-style → flag becomes `false`) or reject the block entirely (js-yaml-style duplicate-key error → all frontmatter silently dropped, which also drops `allowed-tools`). Both runtime outcomes are fail-open — autonomous invocation re-enabled — while the security guard stays green. The kit's oracle does not catch this either: `scripts/validate_frontmatter.py:32` limits pattern checks to `SCALAR_KEYS = {"name", "description", "argument-hint"}`, and its PyYAML path (`scripts/validate_frontmatter.py:84`) accepts duplicate keys without error (last-wins).
- **Fix:** In the guard test, collect ALL top-level `disable-model-invocation` occurrences and assert (a) exactly one exists and (b) its value is `true` — e.g., gather matches into a list, `assert len(matches) == 1` then assert the value, instead of returning on the first hit. Two-line change, keeps the no-PyYAML constraint (ISSUE-021).

## Checklist results (no findings)

- **Injection / parsing confusion in the added frontmatter line:** None. `disable-model-invocation: true` (`skills/sprint/SKILL.md:5`, `skills/sprint/SKILL.md.tmpl:5`) is a static plain-scalar boolean — no user-controlled data, no quoting hazard, no `: ` inside a value, no flow-sequence. Oracle confirms: `python3 scripts/validate_frontmatter.py` → "Frontmatter OK — 55 skill/agent files parse cleanly." The key is outside `SCALAR_KEYS`, so no pattern-check interference, and it parses to a clean boolean under YAML.
- **Test file attack surface:** Pure read-only. Imports only `pathlib.Path` and `pytest`; the only I/O is `path.read_text(encoding="utf-8")` (`tests/test_orchestrator_disable_model_invocation.py:25`). Paths are built from a frozen literal tuple (`ORCHESTRATOR_SKILLS`, line 21) joined under `ROOT` — no external input, so no path traversal. No file writes, no subprocess, no network, no environment mutation. Deliberately avoids PyYAML (no new dependency surface) and avoids subprocess (no shell surface).
- **allowed-tools unchanged:** Confirmed in the diff for both `skills/sprint/SKILL.md` and `skills/sprint/SKILL.md.tmpl` — the `allowed-tools:` line appears only as an unmodified context line. No tool-surface widening.
- **Regression protection is real and composes:** The guard checks the GENERATED `SKILL.md` (what Claude Code actually loads). The bypass route "edit the .tmpl, skip regeneration" is closed by the pre-existing drift guard (`tests/test_gen_skills.py:131` `test_dry_run_passes_when_fresh`, `:139` `test_dry_run_detects_stale`); regenerating from a flag-stripped tmpl trips the new guard. Exact-match `value.strip() == "true"` is fail-closed: quoted `'true'`, `True`, or a missing key all fail the test.
- **Guard demonstrated live:** During this review the test was observed failing with `disable-model-invocation is set to 'false'` while the worktree file transiently differed (concurrent activity in the shared worktree — consistent with a parallel refute-first mutation check), then passing (6/6) against the committed state. The guard tripped on `false` and passed on `true` — it detects exactly the regression it exists to prevent. Informational only: like all lint tests here, it reads shared working-tree state, so concurrent mutation of the worktree can race it; not a defect of this change.

## Self-review

1. **Severity re-assessment:** The single Low is a guard-robustness gap with no external exploit path — Low is correct, not confrontation-avoidance; there is no realistic path to High.
2. **False-positive check:** Initial concern about tmpl/generated drift was refuted by `test_gen_skills.py` dry-run guards and removed. The duplicate-key finding was checked against the oracle — `validate_frontmatter.py` does not catch duplicates — so it stands.
3. **Blind-spot scan (security dimension):** secrets — none added; authn/z — n/a; dependencies — none added; XSS — n/a; misconfiguration — the change REMOVES one (autonomous invocation of a repo-mutating orchestrator was previously possible). Cross-checked all six orchestrator skills for flag presence and consistency: all set `disable-model-invocation: true`.
4. **AC verification:** ISSUE-042 asks for `disable-model-invocation: true` on the sprint skill. Satisfied in both source template and generated file, with a regression guard covering all six orchestrators. Validator passes across all 55 skill/agent files.
5. **Confidence:** High for the diff itself (small, fully read, oracle-verified, test run twice). Medium only on the exact duplicate-key semantics of Claude Code's runtime YAML parser (last-wins vs reject) — flagged inside the Low finding; the finding holds under either behavior.
