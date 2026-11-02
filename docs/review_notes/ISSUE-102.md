# Review Notes — PR #151

## Code Review
_Source: reviewer-degraded_

- **[High] Widening the resolution roots introduced an uncaught OSError crash path: spec_lookup's regular-file test sits OUTSIDE _contain's guard, so one unreadable or odd directory in ANY sibling checkout aborts the gate (origin/main exits 0 on the same input)**
  Evidence: scripts/spec_gate.py:287 — `if resolved.is_file():` is outside the `try` in `_contain` (scripts/spec_gate.py:223-228), whose docstring and the module docstring (scripts/spec_gate.py:59-63) both claim "anything that is not a regular file" is REFUSED.

PROBE O — one sibling checkout has an unreadable docs/specs (mode 000); the SPEC is present and findable in another checkout, so the correct answer is `proceed`:
    --- origin/main module, CWD=main (stats ONE root):
    EXIT=0
    --- PR head, CWD=main (stats EVERY root):
    EXIT=1
    PermissionError: [Errno 13] Permission denied: '.../pa/other/docs/specs/SPEC-500.md'

PROBE N4 — the EXACT `Spec:` value live in this repo's issues.md (ISSUE-087, 544-byte basename), with Spec-Required=true and docs/specs/ present:
    --- PR head module: EXIT=1
    OSError: [Errno 63] File name too long: '.../p9/main/docs/specs/SPEC-081.md (existing - ...)'
    traceback frames: spec_gate.py:473 main -> :387 decide -> :287 spec_lookup

MUTANT R1 — the guard that was written for exactly this class is never exercised. Narrowing `except (OSError, ValueError)` to `except ValueError` (i.e. deleting the OSError half) leaves the suite green:
    BASELINE (unmutated): PASS - 60 passed in 3.00s
    R1  OSError dropped from _contain's except -> SURVIVED  (60 passed in 3.10s)
The PR's own M10 mutated the same line in the opposite direction (narrow to `except OSError`) and was KILLED by the NUL test, so M10 only ever proved the ValueError half.

Reachability measured honestly: 108/108 live issues exit 0 under the PR head today (ISSUE-087 is Spec-Required=false, so it short-circuits), and 1 live value has a basename > 255 bytes. Pre-fix the same value crashed the CLI unconditionally (`python3 scripts/spec_gate.py ISSUE-087` on origin/main -> OSError, EXIT=1), so the PR narrows this crash; it does not close it. Blast radius now scales with checkout count (4 in this repo).
  Fix: Move the stat inside the guard, so an OSError from any root means "not found in this root" rather than aborting the whole enumeration. Minimal change in `spec_lookup` (scripts/spec_gate.py:281-289):

    for root in roots:
        resolved = _contain(root, declared)
        if resolved is None:
            refused.append(root)
            continue
        try:
            is_file = resolved.is_file()
        except OSError:
            refused.append(root)   # or a separate `unreadable` list with its own reason line
            continue
        if is_file:
            found_at = root
            break

Then pin BOTH raisers in the disarm direction, since mutant R1 shows neither is covered: (a) a `Spec:` value whose basename exceeds NAME_MAX with `docs/specs/` present in the fixture (the parent must exist or the kernel returns ENOENT first and the probe gives a false all-clear - that is why PROBE N on a fixture without docs/specs/ reported EXIT=0); (b) a sibling checkout with an unreadable docs/specs. Re-run mutant R1 and require it to die.

- **[Medium] The cross-checkout Spec: field read is claimed id-scoped in three places but pinned by no test — a mutant that drops id-scoping entirely survives all 60 tests because the sibling-registry fixture holds exactly one issue block**
  Evidence: Claimed at scripts/spec_gate.py:41-44 ("only the ``Spec:`` FIELD is read"), at scripts/spec_gate.py:239-240, in tests/test_spec_gate.py:422-423 ("The cross-checkout field read is id-scoped") and in the PR body. The cited test is `test_an_unrelated_issues_spec_does_not_satisfy_this_issue` (tests/test_spec_gate.py:421-428) — but it plants an unrelated SPEC **file** (`SPEC-999.md`); it never plants an unrelated issue's `Spec:` **field** in a sibling registry, which is the thing `_spec_field_from_other_checkout` scopes.

MUTANT R3b — replace the id-scoped `parse_issue(candidate, issue_id)` at scripts/spec_gate.py:252 with "take the first `- Spec:` line in the sibling file":
    BASELINE: PASS - 60 passed in 3.00s
    R3b id-scoping GONE: sibling read takes the first `- Spec:` in the file -> SURVIVED  (60 passed in 3.18s)

It survives because `_two_checkouts` (tests/test_spec_gate.py:284-326) writes a registry containing only `_REPRO_BLOCK` (ISSUE-500), so "first `- Spec:` in the file" and "ISSUE-500's `Spec:`" are the same string and the scoping is never exercised. This is the same fixture-never-reaches-the-code weakness the implementer found once as M11 and did not generalise to the other guards on the same code path.
  Fix: Add a second issue block to `_REPRO_BLOCK` (e.g. ISSUE-501 with `Spec: docs/specs/SPEC-501.md`) placed BEFORE ISSUE-500, create `docs/specs/SPEC-501.md` on the branch and NOT `SPEC-500.md`, then assert the gate still returns `auto_spec` from the worktree. Re-run mutant R3b and require it to die.

- **[Medium] A non-authoritative sibling checkout can supply the Spec: FIELD as well as the file, flipping the authoritative registry's auto_spec to proceed — the PR discloses only the FILE half of this residual**
  Evidence: The PR body and scripts/spec_gate.py:51-57 disclose the residual as "some checkout of this repository holds a regular file at the declared path". The measured residual is wider: the FIELD can also come from a checkout that is not the one the caller pointed at.

PROBE G — main's authoritative registry says `Spec: none`; a leftover sibling worktree's frozen registry declares a path AND holds the file:
    main's own field : - Spec: none
    stale's field    : - Spec: docs/specs/SPEC-500.md
    --- origin/main module, CWD=main:
      decision= auto_spec
      reason= Spec-Required=true, SPEC missing, sprint mode -> auto-run /spec
    --- PR head, CWD=main:
      decision= proceed
      reason= Spec-Required=true and SPEC exists at docs/specs/SPEC-500.md (Spec: field read from .../pg/stale; file found in .../pg/stale; 3 checkout(s) consulted)

So the gate proceeds for an issue whose authoritative field declares no SPEC at all. Mitigating: the reason string DOES name the stale checkout as the source of both artifacts (D-3 counter-evidence works here).

Live reachability measured in this repo across all four checkouts (main + ISSUE-081 + ISSUE-102 + ISSUE-103): `live divergences where a sibling declares a field main does not: 0`. Latent, not live.

Also unpinned: which checkout's field wins is not tested. MUTANT R9 (reverse the sibling field-read order so the LAST checkout wins) -> SURVIVED (60 passed in 3.01s).
  Fix: Either (a) extend the disclosed residual in the module docstring and the PR body to say the FIELD is also non-provenanced, and add a characterization test for PROBE G alongside the two existing residual tests, so the wider residual is measured rather than narrowed in prose; or (b) prefer the field from the main worktree, which `git worktree list --porcelain` already reports first, so no branch or trunk name has to be resolved (ISSUE-089 stays clear). Either way pin the ordering so mutant R9 dies.

- **[Medium] The non-sprint hold-by-missing-SPEC row changes from hold to proceed cross-checkout — a path the issue declares out of scope, absent from the nine legacy pins and from every test**
  Evidence: issues.md:6302 (ISSUE-102 Scope/Out) — "The `hold` / `bypassed` / signal-detection paths, which are unaffected." scripts/spec_gate.py:39-40 narrows the claim to the `hold`-**by-signal** path, which my probe confirms is untouched; the `hold`-by-missing-SPEC path is reached through `if spec_required:` (scripts/spec_gate.py:386) and IS affected.

PROBE A / A2 — same field-on-main / file-on-branch fixture, non-sprint (no --force-sprint-mode):
    CWD=main      origin/main -> hold      PR head -> proceed
    CWD=worktree  origin/main -> hold      PR head -> proceed

`_PREFIX_RESULTS` (tests/test_spec_gate.py:582-689) pins `spec_required_absent_nonsprint_hold` only for the SPEC-absent-everywhere case; there is no non-sprint cross-checkout test at all (`_decide_at` defaults `sprint=True`, tests/test_spec_gate.py:349). Consequence: in non-sprint mode the three-way AskUserQuestion prompt in skills/implement/SKILL.md:94-99 is now skipped whenever any checkout holds a file at the declared path — which, combined with the disclosed provenance residual, means a leftover worktree's old SPEC silently removes a user's choice.
  Fix: This is probably the behaviour you want (it matches row 6, non-sprint + SPEC exists -> proceed), so the gap is scope + evidence, not logic: state the non-sprint relaxation explicitly in the module docstring's scoping list (it currently reads as though only sprint mode is touched), and add the row to the legacy pins — a cross-checkout non-sprint case asserting `proceed`, captured the same way as the other nine. Lesson 8 asks for the legacy failure mode to be PINNED, not merely unchanged by accident.

- **[Medium] An unreadable or undecodable sibling registry is dropped silently with no INCOMPLETE marker, so "a checkout could not be read" renders byte-identically to "no checkout declares a SPEC" — the exact collapse the PR built INCOMPLETE_MARKER to prevent**
  Evidence: scripts/spec_gate.py:249-254 — `if not candidate.is_file(): continue` and `except (OSError, UnicodeDecodeError): continue` discard a checkout without recording anything; `lookup["incomplete"]` is set only by `checkout_roots` (scripts/spec_gate.py:184,190) for git-level failures.

PROBE K — the sibling checkout holding the Spec: field is unreadable (mode 000), CWD=worktree:
    EXIT=0
    {
      "decision": "auto_spec",
      "reasons": [
        "Spec-Required=true, SPEC missing, sprint mode -> auto-run /spec"
      ],

That is the verbatim pre-ISSUE-102 "SPEC missing" string with no count of checkouts consulted and no incompleteness marker. skills/implement/SKILL.md:92 instructs the agent to read exactly this as "no checkout holds the SPEC - i.e. `/spec` did not actually produce one" and STOP. The existing test `test_undecodable_sibling_registry_is_skipped_not_raised` (tests/test_spec_gate.py:481-496) asserts only `decision == "auto_spec"`, so it pins the collapse rather than catching it.
  Fix: Have `_spec_field_from_other_checkout` return the registries it had to skip and fold them into `lookup["incomplete"]` (or a sibling `unreadable` key) so the reason line names them, exactly as the git-failure path does. Then extend `test_undecodable_sibling_registry_is_skipped_not_raised` to assert the INCOMPLETE marker is present, and add the mirror assertion (clean fixture -> marker absent) as `TestComputedEmptyVersusCouldNotCompute` already does for the git half.

- **[Low] The DIRECTORY refusal is not named in reasons, contradicting the module docstring and the PR body's REFUSED table; the test named ..._is_refused asserts only the decision**
  Evidence: scripts/spec_gate.py:59-63 claims "an absolute value, a ``..`` escape, a symlink leaving the checkout, and anything that is not a regular file are all REFUSED, and the refusal is named in ``reasons`` so it cannot be read as 'simply absent'". The PR body's table lists `docs/specs` (a directory) under "Now: REFUSED".

PROBE P — `Spec: docs/specs` with docs/specs/ present as a directory:
    decision = auto_spec
    reason   = Spec-Required=true, SPEC declared at docs/specs but absent from all 2 checkout(s) consulted (...), sprint mode -> auto-run /spec
    contains REFUSED?  False

The code path explains it: `_contain` returns a contained path, so the root is never appended to `refused` (scripts/spec_gate.py:284-289); only containment failures reach the REFUSED vocabulary. `test_spec_path_naming_a_directory_is_refused` (tests/test_spec_gate.py:498-505) asserts `decision == "auto_spec"` and nothing about the reason.
  Fix: Either add a `not_a_regular_file` list parallel to `refused` and give it its own reason clause, or correct the docstring and the PR body to say only containment failures are named as REFUSED and a non-regular file reads as absent. Then make the test assert whichever is true.

- **[Low] Step 0c's new branch prose names two gate outcomes but the gate can now emit three — a containment REFUSAL is classified to the agent as "/spec did not actually produce one"**
  Evidence: skills/implement/SKILL.md:92 — "**STOP and report ONLY when no checkout holds the SPEC** - i.e. `/spec` did not actually produce one. Read the `reasons`: if a line contains `checkout enumeration INCOMPLETE` ... report that as an unresolved environment problem". A third outcome exists: scripts/spec_gate.py:330-335 emits "Spec: value ... REFUSED by containment in all N checkout(s) consulted ... absolute path, '..' escape, or symlink leaving the checkout" — a malformed registry value, not a missing SPEC and not an environment problem. The REFUSED vocabulary was added by this PR specifically so it "cannot be read as 'simply absent'" (scripts/spec_gate.py:62-63), but its only consumer still reads it that way.
  Fix: Add one clause to step 0c (and the .tmpl) naming the REFUSED reason as a malformed `Spec:` value to be corrected in the registry, not a missing SPEC. Mirrors the INCOMPLETE clause that is already there, and keeps the review-lesson-16 real-consumer wiring complete for all three outcomes.

- **[Low] Four newly added guards are unexercised — mutants removing them all survive the suite, including the prunable-worktree guard that is the one measurable defence against the predecessor issue's stale-registration failure mode**
  Evidence: Independent mutation run against tests/test_spec_gate.py (BASELINE: 60 passed in 3.00s):
    R2  prunable-worktree guard removed (candidate.is_dir())       -> SURVIVED  (60 passed in 3.04s)
    R4  sibling-registry regular-file guard removed                -> SURVIVED  (60 passed in 3.06s)
    R5  self-checkout skip removed (read_from not excluded)        -> SURVIVED  (60 passed in 3.12s)
    R6  GIT_QUERY_TIMEOUT removed from the subprocess call         -> SURVIVED  (60 passed in 3.12s)

The prunable behaviour itself is CORRECT — PROBE B, a registration left behind without `git worktree prune`:
    worktree .../p2/stale
    prunable gitdir file points to non-existent location
    ---- PR head, gate from main (sprint) ----
    "decision": "proceed" ... "2 checkout(s) consulted"
    EXIT=0
    ---- PR head, gate from worktree (sprint) ---- EXIT=0
No FileNotFoundError, no crash, and the deleted registration is correctly excluded from the count. The gap is purely that nothing pins it, so a refactor could reintroduce the predecessor issue's failure mode undetected.
  Fix: One test: register a worktree, remove its directory without pruning, assert `checkout_roots` excludes it and the CLI still exits 0 from both CWDs. R4 and R5 are better removed than tested (see the Over-Engineering section); R6's timeout deserves a test only if you keep the constant.

- **[Low] GIT_QUERY_TIMEOUT is a new timing constant documented only in the owning module docstring, with no user-facing doc line**
  Evidence: scripts/spec_gate.py:84-90 documents the constant and argues against an env knob ("both calls are local-only ... so there is nothing for an operator to tune"), and the value is interpolated into the failure message it remediates (scripts/spec_gate.py:184: `missing executable or >{GIT_QUERY_TIMEOUT}s`). Independently confirmed: `grep -rn GIT_QUERY_TIMEOUT` finds it only in scripts/spec_gate.py (3 hits), and no new env var is introduced. The sibling precedent `KIT_WORKTREE_FETCH_TIMEOUT` IS carried in README.md and docs/troubleshooting.md — but that one is an operator knob.
  Fix: Judged acceptable as-is: the stated rationale (local-only, immediate termination, nothing to tune) is sound and the review lesson's purpose is operator remediability. Recorded so the strict reading of the lesson is not silently skipped. If team-lead wants the lesson applied literally, one line in docs/troubleshooting.md naming the constant and the INCOMPLETE reason it produces closes it.

- **[Low] Reason strings embed the absolute filesystem path of every checkout, leaking the home directory and the names of all concurrent worktrees into any log the gate's output reaches**
  Evidence: scripts/spec_gate.py:311-315 and :326,:333,:339,:346 interpolate `lookup['roots']`, `field_root` and `found_at` as absolute paths. Measured output from PROBE E (3 checkouts): "Spec: field read from /private/tmp/.../p5/main; file found in /private/tmp/.../p5/det; 3 checkout(s) consulted". In this repo those paths are `/Users/<username>/project/practice/claude-dev-kit/.worktrees/issue-ISSUE-<nnn>-<slug>`, so the reason discloses every in-flight issue id. skills/implement/SKILL.md:99 instructs the agent to quote the gate's reasons to the user.
  Fix: Render roots relative to the common parent, or as the checkout basename, keeping the absolute path only for the single root that supplied each artifact. Low impact for a local dev tool, but the kit already redacts `/Users/<name>/...` in committed artifacts, so the convention exists.

- **[Low] spec_path_exists() was removed from the module's public surface — no caller breaks, recorded so the removal is not read as an oversight**
  Evidence: `grep -rn spec_path_exists --include=*.py --include=*.md --include=*.tmpl --include=*.sh` across the repo returns only scripts/spec_gate.py:89,115 on origin/main plus prose references in issues.md:6268 and docs/sprint_state.archive-2026-10-31-issue088.md:100. No script, skill or test imports it. Note scripts/validate_issues.py:87-98 `_spec_path_satisfied` carries an INDEPENDENT copy of the same single-root `.resolve().exists()` assumption (and also accepts a directory) — not a caller, so not broken by this change. Measured: `python3 scripts/validate_issues.py issues.md` exits 0 with Given/When/Then advisories only, so it cannot fail CI; it is a Medium elsewhere, not a finding against this PR.
  Fix: No action needed on this PR. The validate_issues.py duplicate wants its own carrier.

## Security Findings
_Source: reviewer-degraded_

- **[Low] No injection, secret or deserialization exposure in the added surface; the one genuine attack surface (an untrusted registry path under widened roots) is contained — verified by probe**
  Evidence: Subprocess use is list-form with no shell: scripts/spec_gate.py:155-160 `subprocess.run(["git", "-C", str(start), *args], ...)`, and `*args` is only ever the two literal argument lists at scripts/spec_gate.py:182 and :186. No `shell=True`, no f-string command construction, no new dependency, no secret, no deserialization, no network call.

Path containment of the untrusted `Spec:` value measured as REFUSED in every escape direction (tests re-run and probed independently): absolute value, `../` escape, symlink leaving the checkout, embedded NUL. Re-measured the live registry myself rather than accepting the PR's figure:
    total `- Spec:` field occurrences: 80
    distinct values: 31
    none=40  relative=40  absolute=0  dotdot=0
So the tightening refuses nothing that exists today.

Over-refusal probed in the other direction, since a containment check is also a way to break working configurations — PROBE Q, all with the SPEC genuinely present:
    ./docs/specs/SPEC-500.md       PR(multi-root)=proceed
    docs/specs/./SPEC-500.md       PR(multi-root)=proceed
    docs//specs/SPEC-500.md        PR(multi-root)=proceed
    Docs/specs/SPEC-500.md         PR(multi-root)=proceed   (case-insensitive APFS)
    docs/specs/SPEC-500.md/        PR(multi-root)=proceed
PROBE R — a `docs/` symlinked to an in-checkout directory: proceed. No legitimate shape is refused.

Resource exhaustion probed: PROBE H, a 72,089,193-byte sibling registry read by the unbounded `parse_issue` -> decision in 1.67s wall. The regex at scripts/spec_gate.py:113-116 is a lazy match with a cheap anchored lookahead, so it is linear, not ReDoS-prone. `GIT_QUERY_TIMEOUT = 10` bounds both git calls.
  Fix: No security fix required. The two availability defects reached through this surface are filed in the Code Review section (the uncaught OSError/PermissionError at scripts/spec_gate.py:287, and the silent drop of an unreadable sibling registry), and the path-disclosure note is recorded there as Low.

## Over-Engineering

- **[Low] [shrink] scripts/spec_gate.py:249-250: the sibling-registry `if not candidate.is_file(): continue` guard is redundant with the `except OSError` three lines below -> delete the guard, keep the handler**
  Evidence: scripts/spec_gate.py:249-254. `parse_issue` on a directory raises IsADirectoryError, a subclass of OSError, which the existing `except (OSError, UnicodeDecodeError)` already absorbs. Mutant R4 (guard removed) -> SURVIVED (60 passed in 3.06s), confirming it changes no observable behaviour.
  Fix: Delete the two lines. Net -2.

- **[Low] [yagni] scripts/spec_gate.py:246-247: the self-checkout skip is behaviourally inert -> delete it**
  Evidence: scripts/spec_gate.py:244-247. `roots[0]` is always `start`, whose own `Spec:` field was already read and found to declare nothing (that is the only condition under which `_spec_field_from_other_checkout` is called at all, scripts/spec_gate.py:274-277), so re-reading it would return the same empty answer. Mutant R5 (skip removed) -> SURVIVED (60 passed in 3.12s).
  Fix: Delete the two lines and the `read_resolved` local. Net -3.

- **[Low] [shrink] scripts/spec_gate.py:318-354: _spec_missing_reasons branches three ways to produce overlapping text -> two branches cover the same cases**
  Evidence: scripts/spec_gate.py:327-347. The `elif len(refused) == count:` branch and the `if refused:` append inside the `else` branch both exist to say "containment refused these roots"; the only difference is all-vs-some, which the message can express with the counts it already interpolates. 37 lines for four message shapes in a module whose other reason builder is 15.
  Fix: Collapse to: the declared-nowhere legacy string, then one "absent / refused" line parameterised by `len(refused)` and `count`. Keep the legacy string exactly (mutant M9 correctly kills a reword) and keep the REFUSED token (mutant R7 correctly kills its suppression). Net roughly -10.

- **[Low] Scope verdict: the module more than doubled (218 -> 487 lines), but the growth maps to ACs or to self-declared D-criteria, not to speculative surface — and the one measured unmapped risk is already filed as the High above**
  Evidence: Per-construct accounting of the 311-line diff in scripts/spec_gate.py:
    module docstring: ISSUE-102 prose                L  22-70     49 lines
    GIT_QUERY_TIMEOUT + its rationale                L  84-90      7 lines
    INCOMPLETE_MARKER + comment                      L  92-94      3 lines
    _git() subprocess helper                         L 152-162    11 lines
    checkout_roots() (incl. 15-line docstring)       L 165-204    40 lines
    _declares_spec()                                 L 207-209     3 lines
    _contain() containment/absolute/NUL              L 212-231    20 lines
    _spec_field_from_other_checkout()                L 234-257    24 lines
    spec_lookup()                                    L 260-298    39 lines
    _spec_present_reason()                           L 301-315    15 lines
    _spec_missing_reasons()                          L 318-354    37 lines

Mapping: `_git` + `checkout_roots` + `_declares_spec` + `_spec_field_from_other_checkout` + `spec_lookup` + the legacy half of `_spec_present_reason` are AC-1/AC-2/AC-3. Unmapped by any AC in issues.md:6306-6309: `_contain`'s containment + absolute + NUL + the `refused` plumbing (D-1, ~35 lines), regular-file-only (1 line), `INCOMPLETE_MARKER` + the `rev-parse` fallback + its reason line (D-2, ~16 lines), the cross-checkout counter-evidence string (D-3, ~6 lines), and the 49-line docstring.

The issue DID request a decision (issues.md:6297, "The choice is the issue's to make; it must be stated with the failure mode it accepts"), so review lesson 14 is live — and the implementer answered it correctly by writing D-1/D-2/D-3 criteria with 12 of the 40 new test executions behind them. Test executions by class, measured not counted: 60 total, 20 pre-existing and unchanged; new = AC-1 3, AC-2 6, AC-3 11, AC-4 8, D-1 6, D-2 4, residual 2.

Lesson 14 nonetheless held empirically: the High finding and two of the four Mediums live in D-1/D-2 surface, not in the AC-mapped core.
  Fix: No cut recommended beyond the ~15 lines named above. The 49-line docstring is the decision record issues.md:6297 asked for and must not be cut. Bucket C (verification core) is the right call for a gate every issue runs.
