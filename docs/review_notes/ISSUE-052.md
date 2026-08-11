# Review Notes — ISSUE-052 (PR #83): sprint_queue crash-recovery aware of already-merged PRs

Reviewer: degraded-path reviewer agent (runtime `/code-review` + `/security-review` not invocable from sub-agents; 048/049/050 precedent). Dimensions covered here: correctness, security, over-engineering minimality.

Verdict: **REQUEST-CHANGES** (1 High wiring gap; 1 Medium robustness nit; Lows record-only).

Tests: `pytest tests/test_sprint_queue.py` → 73 passed. All AC1/AC2/AC3 paths are covered at the script level and mocks are injected at the correct delegation seams (`runner`, `merge_state_fn`, module-global `_gh_pr_merge_state`); the argv is fixture-pinned (`test_argv_is_fixed_and_shell_free`).

---

## Code Review (correctness + minimality)

### [High] `FINALIZE` is emitted by `next-action` but no consumer routes it — end-to-end recovery is not deterministic
- Evidence: `scripts/sprint_queue.py:394-403` emits `action="FINALIZE"`, but the sole consumer of the `action` field — the sprint orchestrator — only routes `DONE | STUCK | PIPELINE | SHIP | REVIEW`:
  - `skills/sprint/SKILL.md:138-140` (and `skills/sprint/SKILL.md.tmpl:77-79`): "If action = **PIPELINE**, **SHIP**, or **REVIEW** → proceed to step 4d". `FINALIZE` is not listed.
  - `skills/sprint/SKILL.md:154` team-lead prompt hardcodes `## Phase: {PIPELINE | SHIP | REVIEW}` — `FINALIZE` is not an allowed phase value.
  - This PR updated `skills/ship/SKILL.md` (idempotent merge) but did NOT update `skills/sprint/SKILL.md`, which is where the decision to invoke ship lives.
- Impact: When the recovery scenario fires (reviewed issue, PR already merged), `next-action` correctly returns `FINALIZE` (AC1 satisfied at the script boundary) but the documented loop has no branch for it, so behavior is undefined — the kit's own rule is "do NOT override the script's action choice." Worse, the finalize-target issue is still at phase `reviewed`, so the step-5 completion gate (`skills/sprint/SKILL.md:193-197`, counts `implemented`/`reviewed`) re-enters step 4, `next-action` re-emits `FINALIZE`, and the loop can spin to `max-iterations` without ever finalizing. The issue Goal ("recovery is deterministic") is not met end-to-end.
- Fix: Route `FINALIZE` in step 4b-c — treat it like `SHIP` (dispatch to the team-lead **ship** phase, which now idempotently skips the merge via `ship-merge-decision` and proceeds to smoke + registry) — and add `FINALIZE` to the team-lead phase enum at step 4d. The script side is already consistent (`ACTION_END_PHASE["FINALIZE"]="shipped"`, `validate --action FINALIZE` accepted), so this is a small, safe skill-text change. Regenerate `skills/sprint/SKILL.md` from the `.tmpl`.
- Not tied to a recalled review lesson — this is an AC-verification / end-to-end-wiring catch.

### [Medium] `_gh_pr_merge_state` crashes on valid-but-non-object JSON — contradicts its "never raises" contract and AC3
- Evidence: `scripts/sprint_queue.py:248-258`. `json.loads` is wrapped in `try/except (ValueError, TypeError)`, but the subsequent `data.get("state")` / `data.get("mergedAt")` (lines 257-258) run OUTSIDE the `try`. Confirmed empirically: a runner returning returncode 0 with stdout `null`, `[]`, `123`, or `"x"` raises `AttributeError: '<type>' object has no attribute 'get'`, which propagates through `classify_ship_ready` (no try) → `cmd_next_action` and crashes the queue.
- Impact: The docstring promises "Degrades to None — never raises — on ... unparseable JSON" and AC3 requires "never crashing the queue." A JSON scalar/array is parseable-but-not-an-object and slips past the guard. Trigger is unlikely with real `gh pr view --json state,mergedAt` (returncode 0 always yields an object), so this is a hard-to-reach edge, not a hot-path failure — hence Medium, not High.
- Fix: guard the shape, e.g. `if not isinstance(data, dict): return None` right after the `json.loads` block, or move the two `.get` reads inside the existing `try`. Add a test for the non-object-JSON path.

### [Low] `--no-check-merged` flag has no real caller — `yagni`
- Evidence: `scripts/sprint_queue.py:652-660`. The flag is exercised only by `tests/test_sprint_queue.py::TestCLIFinalize::test_no_check_merged_flag_skips_probe`; no skill (`skills/sprint/SKILL.md`) passes it. The offline / `gh`-missing case already degrades correctly without it (probe returns `None` → issue stays `ship_ready`), and a missing `gh` fails fast (`FileNotFoundError`), not on the 10s timeout — so the flag's marginal value (skipping a hung-network probe in deterministic/CI runs) is narrow.
- Minimality tag: `yagni` — `scripts/sprint_queue.py:652-660` `--no-check-merged` (+ the `getattr(args, "no_check_merged", ...)` guard at :574) → rely on graceful degradation, or wire the flag into a real caller. Defensible as a CI/offline escape hatch; record-only, not a blocker.

### [Low] Test coverage gaps around the probe timeout / degradation edges
- Evidence: `tests/test_sprint_queue.py` `TestGhPrMergeState` covers OSError, non-zero exit, and unparseable-JSON degradation, but not: (a) that the configured timeout (`GH_MERGE_PROBE_TIMEOUT` / `KIT_SPRINT_QUEUE_GH_TIMEOUT`) is actually passed to the runner's `timeout=` kwarg (the argv-pin test ignores kwargs), (b) that a `subprocess.TimeoutExpired` degrades to `None` (covered by the except clause but never asserted), (c) the non-object-JSON crash (finding above).
- Fix: add assertions for the `timeout=` kwarg and a `TimeoutExpired` case. Record-only.

### Minimality summary
- `FINALIZE` action, `_gh_pr_merge_state`, `classify_ship_ready` (with per-ref cache), `ship_merge_decision` + `ship-merge-decision` subcommand: all justified — the subcommand has a real single consumer (`skills/ship/SKILL.md` step 4) and centralizes merged-detection + degradation. Not over-built.
- Timeout knob is a latency/offline guard on a quick idempotent read that degrades to a safe phase-only decision — this is OUTSIDE the ISSUE-046/047 "hard-coded timeout that kills legitimately-long work" class (it kills nothing and loses no work), and it is env-overridable. Not flagged.
- Net removable lines: ~10-12 (the `--no-check-merged` flag + its guard), only if the escape hatch is deemed unnecessary. Otherwise: lean.

---

## Security Findings

_No findings._

Notes (not findings): The `gh` probe uses a fixed argv list with no `shell=True` (`scripts/sprint_queue.py:227-233`); `pr_ref` is interpolated as a single argv element, so a PR ref containing shell metacharacters cannot inject — worst case `gh` errors and the probe degrades to `None`. The `pr_ref` originates from the repo-controlled `issues.md` `- PR:` field. Stderr echoed in the warnings (`proc.stderr.strip()`, line 244) comes from `gh`, which does not emit auth tokens in its error text, so no credential-leak path. No hardcoded secrets introduced.

---

## Self-Review
- Severity re-assessment: High for the FINALIZE routing gap is justified — it defeats the issue's core "deterministic recovery" Goal and can non-terminate the sprint loop; the fix is small but load-bearing. Medium for the non-object-JSON crash is calibrated down from High because real `gh` cannot trigger it (returncode 0 ⇒ object). Env-knob doc + `--no-check-merged` are correctly Low.
- False-positive check: FINALIZE gap is not excused by the change-surface list — `skills/sprint/SKILL.md` is the only `action` consumer and was left unrouted; verified there is no catch-all/unknown-action branch. The JSON crash is reproduced empirically, not hypothesized.
- Blind-spot scan: injection (safe — fixed argv), backward compat (`choose_action` uses `queues.get("finalize_ready")`; existing tests with no `finalize_ready` key pass — `TestChooseActionFinalize::test_ship_when_no_finalize_key_present` pins this), idempotency default (`merge` on indeterminate is safe — the only way to `skip` is a definitive `merged`, and a stale-classification `gh pr merge` on an already-merged PR errors rather than double-merging; the merge checkpoint re-verifies).
- AC verification: AC1 (finalize-only, not SHIP, no re-merge) — satisfied at the script boundary, but NOT actionable end-to-end (see High). AC2 (un-merged → SHIP) — satisfied and tested. AC3 (gh unavailable → graceful, logged, no crash) — satisfied for all real failure modes; the only residual crash is the unlikely non-object-JSON edge (Medium). Ship-executor idempotency — wired into `skills/ship/SKILL.md`.
- Confidence: High.

## Recalled-lesson trace
- Env-var-knob documentation (ISSUE-046/047/038; ISSUE-049 precedent): `KIT_SPRINT_QUEUE_GH_TIMEOUT` is documented only in code comments/docstring, not in a user-facing doc or `--help`. Recorded as Low below.
- Hard-coded subprocess timeout class (ISSUE-046/047): probe timeout is OUTSIDE the boundary (guards a quick read, degrades safely, env-overridable) — no finding.
- Mock isolation at the delegation seam + fixture-pin (ISSUE-047/037): tests satisfy this (injected `runner`/`merge_state_fn`, monkeypatched module global, pinned argv) — no finding.

### [Low] `KIT_SPRINT_QUEUE_GH_TIMEOUT` not documented in a user-facing surface
- Evidence: `scripts/sprint_queue.py:51-58` documents the knob in comments/docstring only. It is absent from `docs/troubleshooting.md`, `README.md`, and the `next-action --help` text (which does surface `--no-check-merged`).
- Fix: add a one-line entry to `docs/troubleshooting.md` (and/or `README.md`) — same remediation recorded for `KIT_ALLOW_BROWSER_INSTALL` in `docs/review_notes/ISSUE-049.md`. Record-only.

---

## Resolution (fixes applied on-branch, tests-first)

- **[High] FINALIZE routing gap — FIXED.** Wired FINALIZE through the orchestrator:
  `skills/sprint/SKILL.md.tmpl` step 4b-c now routes FINALIZE (proceed to 4d), the 4d
  phase enum is `{PIPELINE | SHIP | REVIEW | FINALIZE}`, the priority note reads
  `FINALIZE > SHIP > REVIEW > PIPELINE`, and a phase-meaning explains FINALIZE routes to
  the team-lead ship executor with an idempotent (skip) merge + validate `--action FINALIZE`.
  `agents/team-lead.md` gains a "When Phase = FINALIZE" handler (idempotent merge no-op via
  `ship-merge-decision`, then smoke + registry; falls back to SHIP if the guard returns
  `merge`). Regenerated `skills/sprint/SKILL.md`; freshness gate passes. Recovery is now
  deterministic end-to-end and cannot spin the completion-gate loop.
- **[Medium] non-object JSON crash — FIXED.** `_gh_pr_merge_state` now returns `None` (with a
  warning) when `gh` yields valid-but-non-object JSON (`null`/`[]`/scalar) via an
  `isinstance(data, dict)` guard, so the probe never raises (AC3). Added regression tests:
  non-object JSON, timeout pass-through, and `TimeoutExpired` degradation.
- **[Low] Missing tests — ADDRESSED** (non-object JSON + timeout pass-through + TimeoutExpired).
- **[Low] `--no-check-merged` yagni — KEPT** as a deliberate offline/deterministic CI escape hatch
  (tested); net cost is small.
- **[Low] `KIT_SPRINT_QUEUE_GH_TIMEOUT` not in user-facing docs — DEFERRED** to a Discovered-Issue
  doc follow-up (env-knob-documentation lesson), consistent with the ISSUE-049
  `KIT_ALLOW_BROWSER_INSTALL` precedent — deferred off-branch to avoid conflicting with main's
  in-flight uncommitted `docs/troubleshooting.md`/README edits. Knob remains documented in the
  module (docstring + constant comment).

Full suite after fixes: 1340 passed, 4 skipped.
