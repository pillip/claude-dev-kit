# Security Review — ISSUE-039 guard stdin hardening (PR #63)

Reviewer: degraded-path security reviewer (runtime `/security-review` not exposed).
Diff range: `e87bc38..cde204d`.

## No findings.

No Critical/High/Medium/Low security findings in this diff. The fail-open change
was audited against the checklist below; conclusions with evidence:

### Fail-open decision and bypass analysis (the central question)

**Threat model:** stdin to a PreToolUse hook is written exclusively by the Claude
Code runtime, which serializes the hook payload itself. The adversarial party
these guards defend against — a model turn attempting to write a secret or run a
dangerous command (e.g. under prompt injection) — controls only the *values*
inside `tool_input`, and the runtime JSON-escapes those values during
serialization. There is no path by which attacker-influenced tool content can
make the top-level payload undecodable or non-JSON, so **malformed stdin is not
an attacker-reachable bypass**; it only occurs on runtime bugs or manual
invocation. Given that, fail-open with a loud diagnostic is the correct posture:
fail-closed would let a runtime serialization bug deny all Write/Edit/Bash use,
and these guards are defense-in-depth behind the Claude Code permission system,
not the primary boundary. This matches the issue spec's explicit design choice.

### Checklist results

- **Injection/spoofing via diagnostics:** none. Both diagnostic strings
  (`secret_guard.py:58`, `dangerous_command_guard.py:48`) are compile-time
  constants with zero interpolation of payload data — no log-injection surface.
- **Decision-channel integrity:** the diagnostic goes to stderr; stdout stays
  JSON-or-nothing. Verified by tests asserting `stdout.strip() == ""` on the skip
  path and `stderr == ""` on the block path, and empirically (rc 0, clean stdout)
  for garbage / empty / non-dict / undecodable-bytes stdin.
- **Guard regression on the block path:** none — valid secret and dangerous-command
  payloads still emit the identical `{"decision": "block"}` stdout JSON (AC2/AC3
  tests plus 20 pre-existing detection tests, all passing).
- **Footgun comment accuracy:** verified against the real wrappers. Both
  `hooks/hooks.json:62,71` and `project/.claude/settings.snippet.json:71,80` wrap
  the guards in `bash -c '[ -f ... ] && python3 ... || true'`. The comment's
  claims are correct: `|| true` is harmless while blocking is stdout-JSON with
  exit 0, and would silently neutralize any future exit-code-2 conversion.
- **Secrets in code/tests:** no new credentials. Test fixtures use the canonical
  AWS documentation key (`AKIAIOSFODNN7EXAMPLE`) and synthetic tokens, in files
  the secret guard's own SKIP_PATTERNS exempt — pre-existing pattern, unchanged.
- **Dependencies / misconfiguration / XSS / authz:** no dependency, configuration,
  or user-facing-output changes in the diff — n/a.

### Informational notes (not findings, no action required for merge)

1. **Diagnostic visibility is bounded by the runtime:** stderr from an exit-0
   PreToolUse hook surfaces in transcript/verbose output, not as a prominent
   warning. "Loud" is as loud as the runtime allows for exit 0; this is the
   documented tradeoff the issue chose over exit-code-2, and the alternative is
   explicitly out of scope.
2. **Known residual crash surfaces, both fail-open with visible tracebacks and
   masked exit codes by `|| true`:** closed stdin fd (code-review finding 1) and
   wrong-typed dict fields (GAP-039a, out of scope, boundary re-confirmed:
   `tool_input: null` still tracebacks). Neither is attacker-reachable for the
   same threat-model reason as above.
3. **Pre-existing, not in diff:** the `[ -f ... ] &&` wrapper means a
   missing/renamed guard file silently disables the guard with no diagnostic at
   all — a quieter fail-open than anything this PR touches. Worth a future issue
   if guard-presence assurance ever matters.

## Self-Review

- Severity re-assessment: zero findings is the honest result — every candidate
  either lacks an exploit path under the actual threat model (stdin author is the
  trusted runtime) or re-litigates an explicit, documented spec decision.
- False-positive/false-negative check: actively searched for a bypass (can guarded
  content break the payload parse? No — runtime escapes it) and for diagnostic
  injection (constant strings — none).
- Blind spot scan: re-checked all seven checklist categories; only injection,
  input-validation, and misconfiguration are touched by this diff, and each was
  probed empirically.
- Confidence: **High** — wrapper wiring, escape behavior, and all skip/block paths
  verified by direct execution against both the head and base commits.
