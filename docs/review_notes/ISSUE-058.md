# Review Notes — PR #100

## Code Review
_Source: reviewer-degraded_

- **[Low] duration_s validator accepted NaN/Infinity — strictness hole in a strict-by-design contract [fixed in review]**
  Evidence: scripts/synthesize_gate_results.py (pre-fix): `NaN < 0` and `inf < 0` are both False, so `"duration_s": NaN` passed validation; consumer rendered `(nans)`. Reproduced by the code reviewer.
  Fix: Fixed in review: duration is float()-converted under an OverflowError guard, then required `math.isfinite` and bounded to [0, MAX_DURATION_S]; parametrized rejection tests added (NaN, inf, 10**400, MAX+1).

- **[Low] RecursionError from pathologically nested JSON escaped the module's "every violation degrades" contract [fixed in review]**
  Evidence: scripts/synthesize_gate_results.py (pre-fix catch tuple `(OSError, UnicodeDecodeError, ValueError)`): `json.loads("["*100000 + "]"*100000)` raises RecursionError (not a ValueError), escaping decide_gate_path; safe today only via the caller's blanket except. Reproduced.
  Fix: Fixed in review: RecursionError added to the caught tuple, mapped to GateSynthesisError; deep-nesting degrade test added.

- **[Low] Delegation-layer crash in the wiring is swallowed with zero signal (no telemetry, no stderr) [recorded, not fixed]**
  Evidence: scripts/verify_checkpoint.py `except Exception: results = None` — a crash in decide_gate_path is indistinguishable from capability_dormant; fail direction is safe (real gates run) and the crash path is unit-tested (test_delegation_layer_crash_falls_back_to_verify_gates).
  Fix: Not fixed (Low): candidate follow-up — best-effort `gates_degraded_path_used {reason: "delegation_error"}` telemetry or a one-line stderr note; requires adding the reason value to docs/telemetry_schema.md in the same change. Stdout must stay untouched (AC-1).

- **[Low] Pre-existing TestRunVerifyGates tests traversed the delegation consult with the ambient environment [fixed in review]**
  Evidence: tests/test_verify_checkpoint.py TestRunVerifyGates calls vc._run_verify_gates(...), which now reads KIT_GATE_RESULTS_FILE / KIT_RUN_ID; the hermetic-env fixture was scoped file-locally to tests/test_gate_delegation.py only.
  Fix: Fixed in review: autouse delenv fixture moved to new tests/conftest.py (suite-wide); file-local duplicate removed.

- **[Low] Consumer-side status-vocabulary drift guard only exercised pass/fail through the delegated rendering path [fixed in review]**
  Evidence: tests/test_gate_delegation.py `_fixture_results()` contained only pass and fail; skip/warn never flowed through the real `_run_verify_gates` icon lookup, so a one-directional oracle-mirror (lesson 4).
  Fix: Fixed in review: wiring fixtures extended to all four statuses; EXPECTED_LEGACY_STDOUT re-pinned; vocabulary drift now fails loudly as a KeyError.

- **[Low] [debt] 3 pre-existing no-trigger KIT-DEBT markers (silent-rot risk) — harvest noise outside this PR's diff**
  Evidence: checkpoint.sh --phase debt: scripts/debt_harvest.py:44 and tests/test_debt_harvest.py:27,59 flagged NO-TRIGGER — all are the harvester matching its own docstring/usage examples and test fixture strings, not real deferrals. This PR introduces zero KIT-DEBT markers.
  Fix: No action in this PR. If the harvester keeps self-matching its own documentation/fixtures every review, a future pass could teach it to skip its own module and test fixtures.

- **[Low] First real telemetry emitter writes to .claude/runs/ (per docs/telemetry_schema.md) but .gitignore lists .claude/run/ exactly — configured-telemetry runs would create untracked noise [recorded, not fixed]**
  Evidence: .gitignore: `.claude/run/` (singular, pinned exactly by TC-043e "no blanket .claude/ ignore"); docs/telemetry_schema.md: ".claude/runs/<run-id>.jsonl (project-side, gitignored)" — the doc's gitignored claim drifts from reality now that scripts/synthesize_gate_results.py is the first script-side emitter. Impact low: emission requires KIT_RUN_ID set AND the runs dir pre-created.
  Fix: Not fixed here (touching .gitignore interacts with the TC-043e exact pin). Candidate follow-up: add `.claude/runs/` to .gitignore and update tests/test_dead_script_removal.py TC-043e together, or converge schema+emitters on the already-ignored `.claude/run/`.

## Security Findings
_Source: reviewer-degraded_

- **[High] Forged attestation could bypass the blocking ship-smoke gate; no freshness/one-shot/provenance binding on the handoff artifact [partially fixed in review — residual deferred to activation]**
  Evidence: Reproduced pre-fix: `KIT_GATE_RESULTS_FILE=<forged all-pass artifact>` made `_run_verify_gates(root, blocking=True)` return True with zero tests run and a transcript identical to a real gate run. Probe gating is structurally a no-op for `verify` (permanently in has_skill.RUNTIME_BUILTIN_SKILLS → exit 2, never 1). Delivery vectors: prompt-injected env+file write; committed `.claude/settings.json` env block + committed artifact.
  Fix: Fixed in review (2 of 3 fix bullets): (a) unconditional `GATES DELEGATED` stdout marker naming KIT_GATE_RESULTS_FILE — a delegated run is never byte-indistinguishable from a real one; (b) artifact containment tightened from project-wide to the gitignored `<project>/.claude/run/`, closing the committed-artifact vector (force-adds remain visible in diff review). NOT fixed (residual, High): provenance/freshness/one-shot binding — SPEC-058 Open Questions now marks it REQUIRED before activation on any blocking checkpoint. Needs a follow-up issue so activation cannot proceed without it.

- **[Medium] Delegated (possibly forged) run was byte-indistinguishable on stdout from a real gate run [fixed in review]**
  Evidence: Pre-fix: decide_gate_path prints nothing and synthesized results flow through the same GATE PASS/FAIL renderer; the only trace was best-effort telemetry, a silent no-op unless the attacker opts in (KIT_RUN_ID set + runs dir exists).
  Fix: Fixed in review: verify_checkpoint prints an unconditional `GATES DELEGATED: N synthesized gate result(s) ingested from KIT_GATE_RESULTS_FILE — tests were NOT executed by this checkpoint process` marker; stdout byte-identity is now guaranteed only for the degraded path (test-pinned both ways).

- **[Medium] Telemetry writer followed symlinks — arbitrary user-writable file append outside the project [fixed in review]**
  Evidence: Reproduced pre-fix: (1) no O_NOFOLLOW — pre-planted `.claude/runs/<id>.jsonl` symlink redirected the append to any user-writable file with partially attacker-chosen bytes (unknown-key names in `detail`); (2) `.claude/runs` symlinked outside the project landed every event out-of-tree (no realpath containment on the dir).
  Fix: Fixed in review: O_NOFOLLOW added to open flags; runs-dir realpath containment inside the project required; run-id blacklist replaced with whitelist `[A-Za-z0-9_-]{1,64}`; attacker-derived `detail` truncated. Symlink/containment/whitelist tests added.

- **[Medium] Huge-integer duration_s passed the "strict" schema and crashed the blocking checkpoint consumer (unhandled OverflowError); NaN/Infinity also accepted [fixed in review]**
  Evidence: Reproduced pre-fix: a ~350-digit integer duration passed `duration >= 0`, then `f"{...:.1f}"` raised OverflowError at verify_checkpoint's render loop — outside both try blocks — killing the ship-smoke checkpoint with a traceback instead of a gate verdict (fails closed, but breaks the degrade-toward-real-gates contract).
  Fix: Fixed in review: float() conversion under OverflowError guard + math.isfinite + [0, MAX_DURATION_S] bound in the validator; rejection tests for NaN/inf/10**400/MAX+1.

- **[Medium] Terminal escape-sequence and newline injection through free-form gate/output strings printed raw [fixed in review at the validator]**
  Evidence: Reproduced pre-fix: a gate name containing `\n  GATE PASS: ...` forged transcript lines; ANSI cursor sequences in a fail output tail visually masked a FAIL line in the live terminal (OSC 52 clipboard channel included). Exit codes computed from data, not display — no result flip, but operator deception.
  Fix: Fixed in review: `gate` must match the slug whitelist `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`; `output` rejects C0/C1 control characters except \n and \t. Residual (out of scope): the pre-existing real-gate output path prints local test-runner tails unsanitized — unchanged behavior, local-trust surface.

- **[Low] Attacker could suppress the forensic invalid_results telemetry via the 4 KiB event cap [fixed in review]**
  Evidence: Pre-fix: events over _MAX_EVENT_BYTES were silently dropped and `detail` embeds attacker-controlled text — a >4 KiB unknown-key name erased the only record of a probing attempt.
  Fix: Fixed in review: `detail` truncated to 512 chars + `…[truncated]` before the size check; truncation test asserts the event survives.

- **[Low] RecursionError from deeply nested JSON escaped the module's error contract [fixed in review]**
  Evidence: Duplicate of code finding 2 from the security angle: ~100k-deep nesting under the 1 MiB cap crashed out of decide_gate_path un-mapped; no invalid_results telemetry emitted; safety depended on the consumer's blanket except.
  Fix: Fixed in review: RecursionError added to the catch tuple (maps to GateSynthesisError → degraded path with telemetry).

## Over-Engineering

- **[Low] [delete] Dead bytes branch in the _write_results test helper [fixed in review]**
  Evidence: tests/test_gate_delegation.py: `payload.decode("utf-8", "replace")` was unreachable — no test ever passes bytes.
  Fix: Fixed in review: helper collapsed to `data = payload if isinstance(payload, str) else json.dumps(payload)`.

- **[Low] [shrink] Redundant Path re-coercion in _emit_telemetry [fixed in review]**
  Evidence: scripts/synthesize_gate_results.py: `Path(project_path)` re-coerced a value every caller already normalizes in decide_gate_path.
  Fix: Fixed in review: uses project_path directly (rewritten during the telemetry hardening).
