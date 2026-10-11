# Review Notes — PR #133

## Code Review
_Source: reviewer-degraded_

- **[High] [RESOLVED IN REVIEW] The new boundary guard itself failed OPEN on 22 of 23 measured inputs, and affirmatively reported valid:true for files containing `- Status: running`**
  Evidence: sprint_status_is_running scoped its scan to _meta_section_bounds' first exactly-`## Meta` window. Any heading deviation emptied the window -> predicate False -> state:'not-running' -> exit 0/valid:true, while next-action on the SAME bytes returned PIPELINE targeting ISSUE-070/071/072 through to `gh pr merge`. 13 of the 22 variants contain the literal line `- Status: running`: `## Sprint Meta`, `## Meta Block`, `## meta`, `### Meta`, `# Meta`, `##Meta`, `##  Meta`, `  ## Meta`, `## Meta (sprint 3)`, setext, duplicate `## Meta` whose first block says `paused`, a fence-wrapped `## Meta` example, and `- Status: running` under `## Notes`. Independently reproduced by the team-lead (4 variants) and both reviewer dimensions (23-variant matrix). The shipped disclosure covered only the degenerate 'no `## Meta` heading at all' subcase, and its justification ('no generator in this repo emits') rests on a false premise: this file is rewritten by an LLM every iteration, not by a generator.
  Fix: FIXED in d328a6c: the ARMING predicate now scans the document instead of the `## Meta` window; the boundary FIELD stays `## Meta`-scoped (parse_roster_watermark and _meta_section_bounds byte-identical to main, so ISSUE-069 AC-6 byte-identity holds). Re-measured: all 14 location variants now exit 3/state:absent/valid:false, with 0 verdict changes across 16 real sprint_state/template/fixture files. The end-to-end composite (disarmed guard + open dispatch + valid:true) is now pinned, and the two assertions that pinned the fail-OPEN direction as a desired property (L7) were inverted rather than deleted.

- **[Medium] [RESOLVED IN REVIEW] The engine's own remediation advice was not replayable on the `rejected` half, and applying it literally made the state worse on every iteration**
  Evidence: cmd_validate emitted ONE errors string for both refusal causes, always saying "restore '- Roster-Watermark: ISSUE-<max rostered ID at sprint start>' inside ## Meta". Applied literally to a REJECTED boundary it adds a SECOND field line. Reproduced replay on `- Roster-Watermark: **ISSUE-011**`: round 0 'not a canonical id' -> round 1 '2 field lines found, expected exactly one' -> round 2 '3 field lines found'. The string lands in errors, is logged into sprint_state.md by step 4f, and is read back by an autonomous agent next iteration, so it is executable advice. No test replayed it; AC-2 only asserted the detail substring.
  Fix: FIXED in d328a6c: the remediation sentence now branches on whether the cause is absence or rejection (rejected -> FIX the existing line, do NOT add a second), with a replay pair asserting the absent branch reaches `accepted` and the rejected branch is idempotent.

- **[Medium] [RESOLVED IN REVIEW] The operator halt was prose, and the surrounding prose contradicted it two bullets later**
  Evidence: skills/sprint/SKILL.md step 4f said 'do not dispatch another iteration', but nine lines later '**Continue loop from step 4a.**' was unconditional; and the skill's only mechanical stop rule ('non-zero exit AND no JSON output') EXCLUDED exit 3, which does print JSON (581 bytes verified). docs/troubleshooting.md carried the same rule. So detection became deterministic while the HALT remained the model-followed prose substrate the issue was filed to replace.
  Fix: FIXED in d328a6c: the continue instruction is now conditional on exit 3, the mechanical stop rule covers exit 3 explicitly, and docs/troubleshooting.md matches. Regenerated via gen_skills.py (.tmpl and generated SKILL.md moved together, 27/27).

- **[Medium] [RESOLVED IN REVIEW] A typo'd `--issues` path silently downgraded the gate from exit 3 to exit 0 with nothing on stderr, while the sibling subcommand hard-fails on identical input**
  Evidence: cmd_validate degraded to issues_meta={} when the path did not exist. Reproduced on `- Roster-Watermark: ISSUE-9999` with a running sprint: `--issues <real>` -> exit 3/state:rejected ('above the highest Board id'); `--issues <typo>` -> exit 0/state:accepted/pinned:ISSUE-9999 with NO stderr output. next-action hard-exits 2 on the same input (required=True), so one flag name carried two contracts and the new caller class got the weaker one, silently, on the command whose job is enforcement.
  Fix: FIXED in d328a6c: one stderr warning naming the flag and the path is printed when the boundary was checked but the Board metadata is empty; exit code and JSON unchanged so AC-2's recorded ceiling-skip decision stands. tests/fixtures/sprint_state/README.md's drifted repro command (GAP-078g) also corrected.

- **[Medium] The running vocabulary is a one-literal whitelist, so 9 measured values/line-shapes in the one field the team-lead is licensed to edit still disarm the guard**
  Evidence: _SPRINT_RUNNING_VALUE_RE = r'^running\b'. Measured disarming, field absent and Board able to fire: `active`, `in progress`, `in-flight`, `dispatching`, `2 of 5 running`, `[running]`, `1. Status: running`, `- [Status]: running`, `- Sprint Status: running` -> all state:'not-running'/valid:true/PIPELINE x3. agents/team-lead.md:210 and skills/sprint/SKILL.md:244 instruct the team-lead to copy `## Meta` through 'editing only Iteration and Status' -- so arming is derived from the one field the control's own mutator is licensed to rewrite: the ratchet lesson, inverted to ratchet OPEN. Internal incoherence: the field-NAME regex is deliberately broad because 'a missed running status is the fail-OPEN direction', while the VALUE match three lines later is narrow, where a miss is the same direction.
  Fix: DEFERRED deliberately, carrier filed: ISSUE-080 (P1). Not fixed in review because the fix requires a new tri-state/`unknown` state value, i.e. new consumer surface no ISSUE-078 AC names -- the exact 'work added for a DECISION ships without AC' trap. ISSUE-080 AC-1/AC-2 cover all 9 variants plus the terminal-vocabulary whitelist.

- **[Medium] Deferred findings had no durable carrier -- in a PR that itself quotes the rule forbidding exactly that**
  Evidence: Seven deferrals (GAP-068d plus six PR findings) lived only in the PR body, which the PR body explicitly names as not a carrier, with no entry in docs/test_plan.md.
  Fix: RESOLVED: ISSUE-080 filed as the carrier for the arming-predicate family (M1 + security 3/4/7), and GAP-078h..GAP-078p appended to docs/test_plan.md under the registry lock for the remainder (security 2/5/6/8/9/10, L2/L3/L4/L6/L8/L9, the minimality shrinks, and the double-echo of boundary detail).

- **[Low] [RESOLVED IN REVIEW] Two WHY-comments and one skill bullet stated a residual narrower than the measured one**
  Evidence: The sprint_status_is_running docstring and skills/sprint/SKILL.md disclosed only 'no `## Meta` heading at all'; `## Sprint Meta` IS a `## Meta`-looking heading, so a reader of that bullet would believe such a file was checked.
  Fix: FIXED in d328a6c: the disclosures were rewritten to the post-fix truth -- the two now-false residuals removed and the real remaining one (the `Status:` VALUE vocabulary gap) disclosed, with the refusal message's false claim that '`## Meta` declares Status: running' corrected to 'this sprint_state declares', since the predicate no longer checks that location.

- **[Low] [RESOLVED IN REVIEW] Two assertions pinned the fail-open direction as a desired property, with no AC behind either**
  Evidence: tests/test_sprint_queue_watermark.py:2887 asserted sprint_status_is_running('- Status: running') is False, and TestRunningStatusScopingResidual pinned the `## Notes` scoping residual as desired behaviour.
  Fix: FIXED in d328a6c: both inverted rather than deleted -- the class became the inverse pin (document-wide arming, exit 3) while keeping its still-correct half (a Roster-Watermark outside `## Meta` is refused with detail 'field is outside the ## Meta section').

- **[Low] [RESOLVED IN REVIEW] docs/troubleshooting.md had no entry for the new exit-3 refusal class**
  Evidence: The new exit class was documented in the module docstring and step 4f but not in the operator troubleshooting doc, whose stop rule also excluded it.
  Fix: FIXED in d328a6c as part of the M3 fix.

- **[Low] The GAP-078b record is half wrong: narrowing `\d`->`[0-9]` inverts the dependency gate to fail-open, but the LENGTH bound does not**
  Evidence: Measured by the code dimension: in _parse_depends_on an overlong/non-ASCII-digit dependency id is currently extracted, matches no Board key, is unresolvable and therefore BLOCKS the row (fail-CLOSED). The recorded rationale generalized this to the whole hardening; only the character-class narrowing has the inverting effect, so the safe half (a length bound) could have been folded in.
  Fix: Carrier: GAP-078o in docs/test_plan.md. Do NOT bound the character class; the length bound may be applied separately with both-direction tests.

- **[Low] [debt] 3 KIT-DEBT markers carry no `trigger=`, and 1 is malformed**
  Evidence: Advisory debt-ledger checkpoint: total 14 markers, 3 no-trigger (silent-rot risk), 1 malformed. Pre-existing, not introduced by this PR.
  Fix: Carrier: GAP-078p in docs/test_plan.md. A deferral without a trigger never reopens.

- **[Low] [shrink] Duplicated `_WATERMARK_FIELD_RE` character-class alphabet re-typed in `_SPRINT_STATUS_FIELD_RE`**
  Evidence: scripts/sprint_queue.py:800 -- the same leading-decoration alphabet is spelled twice, which is the fork risk the issue's own Scope In warned about.
  Fix: -4 lines: one `_meta_field_re(name)` factory called twice. Carrier GAP-078n.

- **[Low] [delete] The `pinned` key in roster_boundary has no consumer anywhere**
  Evidence: scripts/sprint_queue.py:908 -- step 4f never names it, no AC mentions it, and next-action's reason already prints `[roster-watermark: pinned at ISSUE-NNN - X of Y]`.
  Fix: -2 lines. Carrier GAP-078n.

- **[Low] [shrink] `checked` and `accepted` are total functions of `state`, giving a consumer three ways to disagree about one fact**
  Evidence: scripts/sprint_queue.py:869-910 -- checked == state != 'not-running'; accepted == state == 'accepted'.
  Fix: -4 lines: refusal predicate becomes state in ('absent','rejected'). Carrier GAP-078n. NOTE: ISSUE-080 adds new state values, so sequence this AFTER it to avoid rework.

## Security Findings
_Source: reviewer-degraded_

- **[High] [PARTIALLY RESOLVED IN REVIEW] ~30 input classes disarmed the arming predicate while the engine certified the sprint healthy; the heading-location classes are fixed, the value/structural classes remain**
  Evidence: Security dimension measured ~30 disarm classes, all yielding validate exit 0/valid:true/state:'not-running' AND next-action -> PIPELINE ISSUE-070,071,072. Beyond the heading mutations: duplicate `## Meta` (first window wins, so a `running` block hidden behind an earlier `paused` one is never scanned -- the code comment claiming 'a duplicated or edited block must not be able to disarm it by adding a second line' is true for a second LINE, false for a second BLOCK); any `## ` sibling between `## Meta` and the Status line; fenced `## Meta` examples in both directions; and critically the U+2028 defence is NOT inherited but RE-OPENED -- _AMBIGUOUS_LINE_SEPARATORS is only reached after `hits` is non-empty, so it never runs in the absent case, and U+2028/U+2029/NEL/VT/FF/FS each create a phantom `## ` sibling and disarm the control with ZERO visual change. Rated High rather than Critical only because cmd_next_action is byte-identical to main, so the dispatch escalation is pre-existing ISSUE-069 AC-6 fail-open; the harm this PR ADDED is the false assurance. Confirmed: no forged-boundary escalation exists -- augment_roster_from_board only synthesizes ids ABOVE the boundary, so a high forged value closes the gate; absent is the only escalating state. Measured linear to 8.2 MB / 0.154 s, so no ReDoS. CRLF and partition(':') ruled out.
  Fix: PARTIALLY FIXED in d328a6c: the document-wide arming predicate closes every heading-location and duplicate-block class (independently re-verified: 4/4 team-lead variants and 14/14 reviewer variants now exit 3). The value-vocabulary and structural-ambiguity classes, including the unreachable U+2028 defence, are carried by ISSUE-080 (AC-1 through AC-4).

- **[Medium] `not-running` reports an UNVERIFIED state in the shape of a verified-healthy one**
  Evidence: There is no `indeterminate`/`unknown` state, so a consumer cannot distinguish a genuinely idle sprint from a structurally unparseable file: {'checked': false, 'state': 'not-running'} + valid:true + exit 0 all read as healthy for a file whose `## Meta` says running.
  Fix: DEFERRED, carrier ISSUE-080 (AC-3): a fifth state with checked:true/accepted:false -> exit 3 whenever the document has zero or >1 exactly-`## Meta` headings, contains an ambiguous line separator, or has a `## ` line inside the located window.

- **[Medium] `_meta_section_bounds` is fence-blind, so a fenced `## Meta` example can supply the LIVE boundary -- including a false `accepted`**
  Evidence: The locator has no fence guard even though `_unfenced()` exists in the same module and is used for the `## Issue Progress` scan precisely because 'a fenced `## Issue Progress` example otherwise wins the section outright' (ISSUE-076). agents/team-lead.md:182-207 still teaches the fenced shape. Security dimension measured next-action reporting `pinned at ISSUE-079` FROM INSIDE A CODE FENCE while validate said not-running. Team-lead independently confirmed the worse direction AFTER the review fix: a fixture whose fenced block carries `- Roster-Watermark: ISSUE-079` and whose live `## Meta` says `Status: running` with no field yields exit 0 / state:'accepted' / pinned:'ISSUE-079' -- a false ACCEPTED attestation sourced from a code fence, which is strictly worse than a false not-running.
  Fix: DEFERRED, carrier ISSUE-080 (AC-5, both directions). NOT fixed in review on purpose: making the locator fence-aware changes parse_roster_watermark's acceptance surface, which ISSUE-078's Scope-Out forbade touching. ISSUE-080 is where that becomes legitimate, and it requires a both-direction mutant so the guard cannot wrongly exclude a real `## Meta`.

- **[Medium] An unreadable `--issues` path suppresses the refusal entirely and downgrades exit 3 to exit 1 with no JSON at all**
  Evidence: exists()-then-read_text() with no OSError guard: a directory, invalid UTF-8, or mode-000 issues.md raises an uncaught IsADirectoryError/UnicodeDecodeError/PermissionError, so the process exits 1 with a traceback and NO JSON -- suppressing the boundary refusal the leg exists to emit. The in-code comment claims the opposite ('A non-existent path degrades the same way rather than failing: an unrelated issues.md problem must not cost the sprint its boundary verdict'). Rated Medium because next-action crashes identically on the same input, making the persistent case fail-closed and the fail-open case a race.
  Fix: DEFERRED. Carrier GAP-078h. Wrap both read sites in try/except OSError/UnicodeDecodeError and degrade the documented way, or fail with JSON. Also covers L6 and the TOCTOU between exists() and read_text() (security 10).

- **[Medium] Omitting `--issues` silently drops the strictest acceptance rule, with no flag in the output marking the degraded verdict**
  Evidence: Without --issues the Board-range ceiling class is undetectable, so `{'state':'accepted','pinned':'ISSUE-900'}` exit 0 is emitted for a boundary next-action rejects. The ceiling-skip is a recorded decision, but a recorded decision is not a control: the weaker verdict is byte-identical to the stronger one, so no consumer can tell which it got.
  Fix: PARTIALLY RESOLVED in d328a6c (a stderr warning now names the flag and path). The machine-readable half remains: carrier GAP-078i for a `board_ceiling_applied` boolean in roster_boundary so the degradation is readable by the orchestrator, not only by a human reading stderr.

- **[Medium] The refusal message is appended last to an `errors` array that echoes unbounded untrusted text**
  Evidence: Measured: the refusal landed at errors[40] behind ~803,000 characters of untrusted Phase text (804 KB stdout), with a forged `[roster_boundary: accepted]` string echoed verbatim from the file. The channel is pre-existing on main; the buriable payload is new, and an LLM orchestrator reading the tail of that array can miss the refusal.
  Fix: DEFERRED. Carrier GAP-078j: bound the per-element and total size of `errors`, and insert the boundary refusal FIRST rather than appending it last. Also covers the Low that boundary detail is echoed twice in the rejected message (bounded today only because _truncate_value caps at 40 chars -- the 2x factor is implicit, not pinned).

- **[Low] `Status:` value and field-name alphabet gaps**
  Evidence: `Sprint Status:`, `Sprint-Status:`, `State:`, and the value prefixes U+200E/U+2060/U+FEFF/U+3000, plus the wrappers 'running', (running), [running], <running>.
  Fix: DEFERRED, folded into ISSUE-080 (AC-6).

- **[Low] Exit 3 masks exit 1, so a concurrent transition failure loses its exit class**
  Evidence: The boundary exit wins over the transition exit by design, so an issue that is genuinely stuck in the same run is reported only in the JSON, not in the exit code. Every caller was enumerated; no machine consumer currently branches on the distinction.
  Fix: DEFERRED. Carrier GAP-078k: document the precedence in the module docstring and step 4f, since the JSON already carries both facts.

- **[Low] `roster_boundary` does not reflect that the opt-in dispatch knob is widening dispatch**
  Evidence: KIT_SPRINT_DISPATCH_ABOVE_WATERMARK appears in next-action's reason but not in validate's boundary signal, so a deliberately widened sprint and a correctly bounded one are indistinguishable at step 4f.
  Fix: DEFERRED. Carrier GAP-078l.

- **[Low] 'roster_boundary is always present in the output' is false on both exit-2 paths**
  Evidence: The unconditional-key claim in step 4f and the module docstring does not hold when validate exits 2 (missing sprint_state, empty --targets), where no JSON is printed at all.
  Fix: DEFERRED. Carrier GAP-078m: narrow the claim to 'present whenever validate prints JSON'.

## Over-Engineering

_No findings._
