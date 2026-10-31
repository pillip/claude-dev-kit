# Review Notes — PR #147

## Code Review
_Source: code-review_

- **[High] `delegate`'s "verify what landed" check is satisfied by ANOTHER dimension's receipt, so it is vacuous for every dimension after the first (fail-open inside the newly added guard)**
  Evidence: scripts/review_context.py:1147 @ 7e3d5f9. `cmd_delegate` calls `_require_verification(root, args.issue, subject)` and only requires the returned list to be non-empty; `_verified_dimensions` (:875) scans all of `DIMENSION_SKILLS` and never compares against `args.dimension`.

Runtime /code-review, verbatim: "Reproduced: `delegate --dimension code` passes and writes its receipt; make the run file un-appendable (`chmod 0444` — ENOSPC, a read-only mount, or a `chmod` sweep does the same) so `_emit_event`'s blanket `except Exception` swallows the write; then `delegate --dimension security` with a *correct* echo exits **0** and prints `echo verified: security reviewed 810 bytes at head …` while the run file still contains only `review_delegated_to_code_review`. The docstring's claim "a pass whose receipt could not be recorded is itself a refusal" is false, and `record-subject` later writes `verified_dimensions: code` — the notes and the operator-facing message disagree. Fix: `if args.dimension not in dimensions: raise _refuse("verification-missing", …)`."

Independently reproduced twice more, with the dimensions in the opposite order. Reviewing agent's own run, literal output:

    [security delegate] exit=0  (receipt written)
    [code delegate, unwritable receipt] exit=0
      stdout: echo verified: code reviewed 497 bytes at head 05fc7c8565c1… (range 90b536f3e502…05fc7c8565c1…)
      stderr:
      event types in receipt file: ['review_delegated_to_security_review']
      >> code receipt actually landed? False
      >> delegate exited 0 claiming code verified? True

The comment at :1145 states the intent this misses verbatim: "Verify what landed, not what was intended". SKILL.md step 3.1(c) branches on this exit code ("A non-zero exit means the verdict is not usable"), so the dimension is recorded as delegated-and-verified and never falls back to the degraded reviewer.

Why the guard's own disarm matrix did not catch it (review lesson 16): the only guarding test, `TestEchoGate::test_delegate_refuses_when_its_verification_cannot_be_recorded` (tests/test_review_subject_binding.py:1131), arms solely the `_receipt_path() is None` branch — "no KIT_RUN_ID, no runs dir" → `verification-unconfigured`. The arm where the run file exists and is readable but the append failed is untested, and mutant M12 (which the reviewing agent re-ran: 1 failed, 125 passed) is killed by that same single test, so the matrix never reaches this arm either. The defence was exercised in one direction, at the whole-file level, not per-dimension.

Severity note, recorded because the three passes disagreed and averaging would be distortion: runtime /code-review rated this **High**; the degraded security reviewer and the reviewing agent independently rated it **Medium**, on the grounds that the echo itself still matched (so no verdict about a wrong subject is ever accepted), that `record-subject` re-verifies independently and would render `- verified_dimensions:` without the unrecorded dimension (so the committed counter-evidence stays honest and AC-5 is intact), and that the precondition is environmental. The higher upstream severity is carried here, unmodified, as the blocking-gate-conservative choice.
  Fix: Bind the read-back to the dimension at hand — no vocabulary change needed, `verification-missing` already exists:

    verified = _require_verification(root, args.issue, subject)
    if args.dimension not in verified:
        raise _refuse(
            "verification-missing",
            f"the {args.dimension} echo matched but its receipt did not land in "
            f"{root}/.claude/runs — record-subject consumes that receipt, so an "
            "unrecorded verification is a silent pass one step later.",
        )

Add the missing disarm test at the untested arm: a readable-but-unappendable run file plus a pre-existing receipt for the OTHER dimension, asserting exit 2 and `reason=verification-missing`. That also gives M12 a second, independent killer. Then correct the docstring sentence at :1103-1105, which currently asserts the behaviour the code does not have.

- **[Medium] The notes are mutated BEFORE the read-back check, so one unpaired code fence makes `record-subject` append a new counter-evidence block on every run, forever, while exiting 2 under a reason that misdiagnoses the cause**
  Evidence: scripts/review_context.py:1210 (write-before-verify), :911-938 (`_subject_blocks`), :351 (`_FENCE_RE`) @ 7e3d5f9.

Runtime /code-review, verbatim: "`_subject_blocks` tracks fences by parity (`in_fence = not in_fence`), and `synthesize_review_notes.py::_render_finding` indents only the *first* line of `evidence`, so any multi-line evidence puts fence lines at column 0. With an odd count, a real `## Review Subject` block is invisible to the detector. `cmd_record_subject` then takes the "no block" branch, appends, writes, and only afterwards fails the readback. Reproduced over three successive invocations: `exit=2 reason=subject-incomplete literal_headings=1 → 2 → 3, detected=0` each time. `subject-duplicate-block` never fires (the duplicates are invisible), `subject-incomplete`'s message ("could not read both values back") does not name the cause, and `subject-incomplete` is absent from SKILL.md step 5.3's remediation list."

That identifies the concrete carrier inside this very pipeline: `docs/review_notes/*.md` is synthesizer output embedding upstream reviewer prose verbatim, and a finding whose `evidence` quotes a snippet after an unclosed ```python fence produces exactly this input.

The reviewing agent independently drove seven fence shapes through the REAL consumer (`record-subject`, after a passing echo gate, on an offline fixture) rather than through the helper. Literal results:

    control: plain notes, no block                                   exit=0  reason=None   headings=1
    prose inline-code mention of the heading                         exit=0  reason=None   headings=1
    heading quoted inside a 3-backtick fence                         exit=0  reason=None   headings=2
    heading inside a 4-backtick fence wrapping a 3-backtick fence    exit=0  reason=None   headings=1
    UNTERMINATED fence before a real heading                         exit=2  reason=subject-incomplete  headings=2
    a real stale block (the cycle-2 shape)                           exit=0  reason=None   headings=1
    unbalanced fence inside a synthesized finding's evidence         exit=2  reason=subject-incomplete  headings=2

Two things that adds. First, the self-referential cases the gate was specifically hardened for DO hold: prose quoting the heading in inline code, and the heading quoted inside a plain 3-backtick or tilde fence, are all correctly ignored and do not wedge the detector. Second, a NESTED fence is a distinct defect in the opposite direction: a 4-backtick fence wrapping a 3-backtick fence lets the inner ``` flip `in_fence` back to False, exposing a heading inside the illustration. With a real block also present `_subject_blocks` returns 2 spans for 1 real block (verified at the helper) and the gate refuses `subject-duplicate-block`; with no real block present — row 4 — it exits **0** having written the counter-evidence INSIDE the illustrative fenced example. A review note that documents this gate by showing the block inside a fence needs 4 backticks to do so, which makes that input self-referentially likely.

Stated so this is not read as more than it is: the fence pattern IS byte-equal to `sprint_queue._FENCE_RE`, which the reviewing agent verified by execution (`rc._FENCE_RE.pattern == sq._FENCE_RE.pattern` → True, flags equal) and which `sprint_queue.py:134` toggles on identically — so the PR's non-drift claim holds and the blind spot is shared with the kit's existing oracle rather than introduced here. Every wedge case is fail-CLOSED: no false counter-evidence is ever recorded. Review lesson 4 is the relevant one — the parser matches its oracle but matches neither CommonMark's fence-length rule nor the intended boundary (never mistake an illustration for a record).
  Fix: Three independent fixes, cheapest first. (1) Do not mutate the notes before the read-back succeeds: build `updated`, verify it parses to exactly one block, then write once — a refusal then leaves the file untouched and retries stop accumulating blocks. (2) Refuse with a reason that names the real cause when the literal heading count disagrees with `len(_subject_blocks(text))` (an unterminated fence), instead of `subject-incomplete`; and add `subject-incomplete` to step 5.3's remediation list, where it is currently missing. (3) For the nested case, track the opening fence's character and run length and close only on a run of >= that length of the same character, implemented in `sprint_queue`'s helper so both consumers inherit it and the byte-equality test keeps them pinned together.

- **[Medium] The whole subject-binding chain is enforced only by prose — no gate checks that it ran, which is the exact omission ISSUE-096 documents happening five times**
  Evidence: skills/review/SKILL.md:233 and scripts/verify_checkpoint.py:1138 (`verify_review_review`) @ 7e3d5f9.

Runtime /code-review, verbatim: "`("review", "review") → verify_review_review` … is the one *blocking* checkpoint over `docs/review_notes/<ISSUE>.md`, and it still checks only for the Code Review / Security Findings / Over-Engineering headers. Nothing anywhere greps for `## Review Subject` (`grep -rn "Review Subject" scripts skills docs` returns nothing outside `review_context.py`). Concretely: a review run that never invokes `delegate` or `record-subject` passes `checkpoint.sh --skill review --phase review` byte-identically to one that did, so the new gate is defeated by the same omission (a model skipping a prose step) that ISSUE-096 documents happening on PRs #139/#141/#145/#147. One line in `verify_review_review` — require the block when any `review_delegated_to_*` receipt exists for the run — would close it."

Independently verified by the reviewing agent on both trees:

    $ grep -rn "Review Subject" scripts/ skills/ | grep -v review_context.py
    (no output — on main AND on the branch)

and `verify_review_review` was read directly: its only content checks are three `re.search(r"^#{1,6}\s+.*(Code Review|Security Findings|Over-Engineering)", …)` calls, then `print("PASS: review_notes.md has required sections")`.

This lands on the PR's own decision rationale. The module docstring at :104-106 records the decision as "option (c): the script owns everything checkable, the step-3.1 prose consumes it — prose alone is precisely what was skipped five times." The production half of that is real and well built; the CONSUMPTION half is prose-only and ungated, so the half that was skipped five times is still the half nothing enforces. It is Medium rather than High because the script-side refusals genuinely cannot be talked past once invoked — the gap is that nothing compels the invocation.
  Fix: Extend `verify_review_review` to require the `## Review Subject` block (line-anchored, reusing `review_context._SUBJECT_HEADING_RE` rather than a second hand-rolled matcher) whenever the run file carries a `review_delegated_to_*` receipt for the issue — so the requirement is conditional on a delegation actually having been decided, and a fully degraded review is not forced to carry a block it cannot produce. Pin it in both directions: notes without the block must FAIL when a receipt exists, and must PASS when none does.

- **[Medium] Step 3.1's degradation `emit` omits the `KIT_RUN_ID` its two new siblings carry, so the security dimension's expected, documented degradation event is silently dropped**
  Evidence: skills/review/SKILL.md.tmpl:72 and the generated skills/review/SKILL.md @ 7e3d5f9:

    python3 scripts/review_context.py emit --event review_degraded_path_used --dimension <code|security> --reason inline-attempt-failed --issue $ARGUMENTS

The two commands this PR adds both carry the knob — `delegate` at :61 and `record-subject` at :187 (`KIT_RUN_ID=review-$ARGUMENTS …`) — and step 3.1's own new prose at :40 says "the kit has no other producer for `KIT_RUN_ID`; use the same literal value in every command of this review". This command is the exception, and `_emit_event` treats an unset run id as a silent no-op at exit 0 (:429-430, the ISSUE-066 contract pinned by `tests/test_review_context.py`).

Reproduced literally by the reviewing agent while dogfooding this PR's own flow, running the command exactly as the skill prints it:

    $ python3 scripts/review_context.py emit --event review_degraded_path_used --dimension security --reason inline-attempt-failed --issue ISSUE-096
    EMIT_EXIT=0
    $ cat .claude/runs/review-ISSUE-096.jsonl
    cat: .claude/runs/review-ISSUE-096.jsonl: No such file or directory

The identical command prefixed with `KIT_RUN_ID=review-ISSUE-096` wrote the event. This is newly consequential because of this PR: the measured constraint it adds makes that command the expected steady-state path for the security dimension on every review on this runtime (and this review took it — see the Security Findings source). So the one event recording why half the delegated review degraded is dropped by default, in a PR whose thesis is that a control's defeated output must not be indistinguishable from its healthy one.
  Fix: Needs a decision, not a one-token edit, because the two commands anchor differently: `cmd_emit` writes under `Path.cwd()` (:1264) while `delegate`/`record-subject` write under the resolved branch worktree (:1108, :1171). Prefixing the knob makes the event land, but in the CWD's `.claude/runs/` — a different file from the receipts, splitting one review's events across two run files. Options: (a) prefix the knob and document the split; (b) run that command from `$WT/`; (c) anchor the degradation event on the worktree root like its siblings. Whichever is chosen, add a sibling of `test_the_record_step_supplies_the_run_id_the_receipt_lives_under` so the omission cannot return.

- **[Low] On the `main-checkout` fallback, `record-subject` targets the MAIN checkout's review notes — the location dependence the issue exists to remove**
  Evidence: scripts/review_context.py:1174 @ 7e3d5f9. Runtime /code-review, verbatim: "`root = Path(subject["worktree_path"])` and `_resolve_worktree` falls back to the main work tree whenever no worktree holds `refs/heads/<headRefName>` — a fork PR whose local branch name differs, or a re-review after `wt_cleanup.sh`. The counter-evidence (and `delegate`'s receipt) then land in the main checkout, which step 6 never commits, so the PR's notes silently lack the block; once the issue's notes file exists on main, the command overwrites it in main's dirty tree. This is the same CWD/location dependence the issue exists to remove, and the docstring asserts the opposite ("The notes live in the BRANCH WORKTREE")."
  Fix: Refuse the WRITE path when `worktree_source == "main-checkout"` with a named reason, or at minimum name the fallback in the success message so a reviewer sees where the block actually went. The `collect`/read paths can keep the fallback.

- **[Low] The "nothing else exits 1" invariant is documented and currently true, but unenforced and untested — `exit_code` is a free parameter with no reason-to-code pairing**
  Evidence: scripts/review_context.py:492 (`_refuse`) and :478-489 (`SubjectRefused.__init__`) @ 7e3d5f9. Runtime /code-review, verbatim: "`SubjectRefused.__init__` validates the reason against the closed `SUBJECT_REASONS` (and a test pins that under `-O`), but `exit_code` is a free parameter of `_refuse` with no reason↔code pairing and no test table. A future `_refuse("git-diff-failed", …, exit_code=1)` would silently reinstate the "computed and empty" vs "could not compute" conflation that AC-3 and the module docstring ("**Nothing else exits 1**") exist to prevent."

The invariant does hold today — the reviewing agent verified it adversarially rather than by reading. Static: only two `exit_code=1` constructions exist in the file (:741, :748), both reached from `empty-diff-head-is-merge-base` and `empty-diff-unexplained`. Dynamic, through the real CLI on an offline fixture, every shape exited 2 with a `reason=` token and an empty stdout and no traceback: a `prunable` `.worktrees/<slug>` registration (the original High (a) defect), `git` absent from PATH, `gh` absent from PATH, a non-git CWD, an unreachable head oid, and a malformed `--pr`. Two stream-failure shapes were also probed, since this repo has an ISSUE-070 precedent for a closed stream breaking a never-fails contract: with fd 2 closed the refusal still exited 2, and with stderr redirected to a broken pipe the process exited 120 (CPython's stream-flush failure code), not 1. AC-3's "differ by exit code or reason token" is satisfied on every path reachable.
  Fix: Make the documented invariant executable in `SubjectRefused.__init__`: `exit_code == 1` iff `reason.startswith("empty-diff-")`, raising `ValueError` otherwise — the same real-check-not-`assert` treatment the reason vocabulary already gets. Add a table test over all 25 tokens pairing each with its expected exit code.

- **[Low] [scope] The PR declares no Kept-Surface bucket, which CONTRIBUTING.md requires for a substantially changed skill**
  Evidence: CONTRIBUTING.md:39-62 (SPEC-055): "Every new or substantially changed skill/agent states which bucket its value lives in." `skills/review/SKILL.md` has step 3.1 rewritten and a new step 5.3 in this diff. Neither the PR body nor the diff contains `bucket`, `Kept-Surface` or `SPEC-055` — grepped both, no hits. No skill or agent file in the repo carries a bucket declaration either, so the PR body is the only available carrier.
  Fix: Add one line to the PR body: bucket **C — verification core** (deterministic gate, provenance contract), which is the correct classification and the bucket CONTRIBUTING.md says to invest in.

## Security Findings
_Source: reviewer-degraded_

- **[Medium] `delegate` reports a dimension verified when its own receipt never landed (cross-dimension receipt inheritance) — same defect as the Code Review High above, carried at the security reviewer's own severity**
  Evidence: scripts/review_context.py:1147 @ 7e3d5f9. Recorded separately and at its upstream severity because two passes rated the same defect differently and collapsing them would be a severity change rather than a merge. Degraded security reviewer, verbatim: "The 'verify what landed, not what was intended' guard calls `_require_verification(...)` and **discards the return value**; that function raises only when the verified-dimension list is *empty*, so the second `delegate` call in a run is satisfied by the *first* dimension's receipt. I reproduced it against the pinned file — with the run file readable but not writable (read-only mount, sandbox write-deny, or a run file created by another uid), `_emit_event`'s silent-by-contract swallow means:

    security delegate -> 0        # "verdict is usable, delegation recorded"
    receipts actually on file now: ['review_delegated_to_code_review']

It printed `echo verified: security reviewed 169229 bytes` and exited 0 with no `review_delegated_to_security_review` receipt anywhere. SKILL.md step 3.1(c) branches on that exit code, so a whole dimension gets recorded as delegated-and-verified and never falls back to the degraded reviewer. Fix: keep the return value and refuse when `args.dimension not in verified` — `verification-missing` is already in `SUBJECT_REASONS`, so no vocabulary change. No test disarms `_emit_event`, so the guard is untested."

Its own severity note, verbatim: "Finding 1 is Medium, not High: the precondition is environmental and the first dimension of a run still fails closed, so it is not a correctness failure in the normal flow — but it is not Low either, because the guard is silently inert for its own stated purpose and is untested."
  Fix: See the Code Review entry — one fix closes both.

- **[Low] The counter-evidence block publishes an absolute local path into a tracked, pushed file**
  Evidence: scripts/review_context.py:985 (`_render_subject_lines`) @ 7e3d5f9: `f"- worktree_path: {subject['worktree_path']}"`. `docs/review_notes/*.md` is git-tracked (40+ files) and `skills/review/SKILL.md` step 6 commits and pushes it to a public remote, so every reviewed issue publishes a line of the form `- worktree_path: /Users/<username>/project/practice/claude-dev-kit/.worktrees/issue-ISSUE-096-bind-review-diff`, disclosing the OS account name and local directory layout of whoever ran `/review`.

Reconnaissance only — a username harvested from a public repo feeds credential-stuffing and spear-phishing target lists — which caps it at Low. Not hypothetical for this repo: the same class was already reported and accepted here at `docs/review_notes/ISSUE-038.md:58` ("impact is limited to leaking usernames and test structure if committed"), so the diff systematizes, per review and per issue, a leak the kit has previously treated as worth fixing.
  Fix: Record the path relative to the worktree root, or drop it: `worktree_source` (`branch-worktree` / `main-checkout`, already on the adjacent line) carries all the semantic content the counter-evidence needs, and the absolute path is reproducible locally from the issue id. Keep the absolute path in `delegate`/`record-subject` stdout and in the run-file payload — both untracked — and emit only `worktree_source` into the committed block.

- **[Low] The integrity receipt is stored inside the worktree that holds the code under review**
  Evidence: scripts/review_context.py:1108 and :1171 (`root = Path(subject["worktree_path"])`), consumed via :786-800 (`_receipt_path`) @ 7e3d5f9. The new subcommands deliberately move the telemetry root from `Path.cwd()` to the resolved branch worktree, so the echo-gate receipt lives at `<worktree>/.claude/runs/<run-id>.jsonl` — inside the checkout of the PR being reviewed.

The module docstring discloses the receipt as forgeable by "an orchestrator that writes the receipt line itself". Degraded security reviewer, verbatim: "That understates the trust boundary: the receipt store is writable by *anything that executes inside the worktree during the review*, and `/review` runs the PR's own test suite and hooks from that worktree. `collect` also publishes `diff_command` verbatim, so PR-supplied code can compute the matching `head_oid` / `diff_bytes` / `diff_sha256` at runtime and append a well-formed `review_delegated_to_security_review` line that satisfies `_verified_dimensions` without any reviewer having read anything."

What is NOT reachable, recorded so the severity is legible: committing the forged line as a file in the PR is infeasible (the digest would have to be a fixed point of a diff containing itself), and `_emit_event`'s `O_NOFOLLOW` plus `_contained` make a PR-committed symlink at `.claude/runs` fail CLOSED (`verification-unreadable` / `verification-unconfigured`) rather than redirect. The vector requires code execution during the review, which is a strictly larger problem — hence Low.
  Fix: Put the gate's evidence where the subject under review cannot write: keep the receipt root at the main checkout or an explicit out-of-tree run directory, or bind the receipt to the orchestrator with a per-run secret (`collect` mints a nonce, `delegate` writes `hmac(nonce, head_oid|diff_bytes|diff_sha256)`, `record-subject` requires the MAC). At minimum, update the docstring's disclosed residual to name the real writer set — "anything executing in the worktree during the review, including the PR's own tests and hooks" — since the current wording would lead a future reader to believe only the orchestrator can forge it.

## Over-Engineering

- **[Low] [delete] `head_ref` is written and never read — and a test in this PR asserts no such field exists**
  Evidence: scripts/review_context.py:723 @ 7e3d5f9: `"head_ref": f"gh:pr/{pr}#headRefOid"`. Nothing reads it (grep: only `tests/test_review_subject_binding.py:356,374`); it is a constant template restating `pr_number`, which the same payload already carries. Notable because `test_the_payload_carries_no_field_nothing_reads` is one of this PR's own additions and the PR body cites it as pinning "the exact key set" after removing the unread `merge_base` field — so the guard passed with an unread field still present.
  Fix: Delete the field; add `head_ref` to whatever the key-set test treats as forbidden rather than permitted.

- **[Low] [shrink] `base_oid` payload field duplicates the left half of `range`**
  Evidence: scripts/review_context.py:722 @ 7e3d5f9. Read by no consumer outside tests; it is literally the left half of the `range` field two lines above.
  Fix: Keep the local variable, drop the payload field.

- **[Low] [yagni] The `KIT_REVIEW_GH_TIMEOUT` override has no acceptance criterion and no caller that sets it — the 30s bound is the safety control and should stay**
  Evidence: scripts/review_context.py:338-339, :496-503, README.md:698-705, tests/test_review_subject_binding.py:1877-1883 @ 7e3d5f9 — `GH_TIMEOUT_ENV`, `_GH_TIMEOUT_DEFAULT`, `_gh_timeout()`, 7 docstring lines, 8 README lines and 1 doc-lint test. The knob appears in the PR body only under "Also in this PR", never against an AC, and ISSUE-096's Scope (In) does not mention bounding the `gh` consultation. Recorded because ISSUE-079 exists precisely for unspecified surface shipped during a rework, and this diff nearly doubled (97KB → 169KB) during one.

In its favour: review lesson 2 is fully satisfied — documented in the owning module's docstring (:200-206) AND in README's environment table next to `KIT_WORKTREE_FETCH_TIMEOUT`, with the knob's name printed in the `reason=gh-timeout` message it remediates (:589-591). `KIT_WORKTREE_FETCH_TIMEOUT` is a sibling knob and is the one argument for keeping the override.
  Fix: Keep the 30s bound as a module constant passed to `subprocess.run(timeout=...)`; drop the env override, its README entry and its doc-lint test. Or keep it and name it in the issue's Scope (In) retroactively.

- **[Low] [shrink] The 2026-10-31 / 48.5KB / "On branch main" measurement is restated in six places**
  Evidence: scripts/review_context.py:84-188 @ 7e3d5f9 — a 105-line ISSUE-096 narrative inside a 231-line module docstring (409 docstring + 70 comment lines against 850 code lines). The same anecdote appears in this docstring twice, `skills/review/SKILL.md:105`, `skills/review/SKILL.md.tmpl:57`, the `docs/cc_feature_matrix.md` row, `docs/telemetry_schema.md`, and the test module docstring. `docs/cc_feature_matrix.md` is the kit's canonical measurement registry and is self-contained by design.
  Fix: Keep the operational contract in the docstring and cite the matrix row for the anecdote. Relatedly, the `48\.5KB`, `2026-10-31` and `accepts no review target` entries of `STEP_31_REQUIREMENTS` (6 of its 24 test instances) duplicate `MATRIX_ROW_REQUIREMENTS`, which already pins the same strings, mutation-tested, in the file that owns the measurement — step 3.1's whitelist should pin the obligations (the commands, `--echoed-*`, `--head-oid`, `diff_command`, `KIT_RUN_ID`, the two prohibitions), not the dated anecdote twice.

- **[Low] [shrink] ~155 removable lines in the 1975-line test file: six redundant or strictly-subsumed tests, plus unused fixture parameters**
  Evidence: tests/test_review_subject_binding.py @ 7e3d5f9, from the minimality pass. Strictly subsumed or duplicative: `test_the_two_zero_byte_outcomes_do_not_collapse` (:616-645, same two inputs/codes/tokens as the two tests above it — but it is also the most literal rendering of AC-3, so keep this one and delete those, not all three); `test_a_wrong_but_non_empty_echo_is_refused` + `test_the_empty_collection_digest_cannot_satisfy_the_gate` (:980-1027, both assert the same three things through the one `if` at review_context.py:1122 — fold into the existing parametrize at :957 so no input is lost); `test_an_unmodelled_exception_becomes_a_named_could_not_compute` (:743-761, subsumed by the parametrized test below it); `test_decide_still_prints_its_json_and_exits_0` (:1709-1725, a weaker copy of `tests/test_review_context.py:177` — AC-7 is discharged by that file passing unmodified); `test_the_notes_flag_decoy_is_gone` (:1592-1600, asserts argparse rejects an unknown flag for an option that appears nowhere in the diff — it pins stdlib behaviour); `test_a_forged_block_is_replaced_by_the_verified_one` + `test_an_incomplete_block_is_completed` (:1438-1464, one parametrize over the pre-existing block body).

Also: `test_the_write_half_refuses_a_symlink_on_its_own` and `test_the_write_half_never_creates_a_missing_file` (:1523, :1544) request `pr_fixture` and `capsys` and reference neither (verified by AST) — each request builds a bare origin + clone + 2 commits + 2 pushes + `worktree add` (~10 git subprocesses) that is thrown away. Keep both tests: the reviewing agent re-ran mutant M22 split into its two halves and each kills exactly one of them (O_NOFOLLOW removed → 1 failed, 125 passed; O_CREAT added → 1 failed, 125 passed), confirming the PR's disclosure that this mutant survived until pinned at its own boundary. And `_collect_json`'s `*extra` parameter (:288) and `_delegate_args`'s `over.get("head", …)` branch (:305) have no callers.
  Fix: Net removable across all minimality findings: ~225 lines — ~155 in the test file, ~40 of module docstring prose, ~30 for the env knob and its README + doc-lint surface. No production code path, validation, error handling or security control is cut by any of them.

- **[Low] [note] Checked and cleared, recorded so the absences are not read as omissions**
  Evidence: From the minimality pass, with the reviewing agent's independent confirmation where noted. `SUBJECT_REASONS` has **no dead tokens** — both passes extracted the tuple and matched every `_refuse(` first argument: 25 of 25 are raised, each with a named test. No helper or module constant in `scripts/review_context.py` is test-only or written-never-read except `head_ref` above (verified mechanically). `diff_headers` is explicitly requested by the issue's 2026-10-31 amendment ("byte count + `diff --git` header count + sha256") and consumed by the notes block — though note it is computed but NOT gated, since the echo gate compares bytes + sha256 only. `worktree_source` has a consumer and is the live signal for the exact defect AC-4 pins. `diff_command` is load-bearing: the gate compares a digest, so the consumer must run byte-identical argv. No `stdlib` or `native` findings, scanned deliberately: the diff adds no dependency (stdlib only — `hashlib`, `shlex`, `stat`, `shutil`, `subprocess`), uses `shlex.join` instead of hand-rolled quoting and `Path.is_relative_to` for containment, and pins the hand-rolled fence predicate byte-equal to `sprint_queue._FENCE_RE` rather than respelling it. `TestTheMatrixCarriesTheReviewTargetMeasurement` (14 tests linting one documentation row) is deliberately NOT flagged: it mirrors the established kit pattern at `tests/test_subagent_skill_grant.py:285` and AC-6's sibling measurement asks for the row.
  Fix: No action.

## Review Subject
_Counter-evidence for what this review actually read (ISSUE-096): the subject whose digest a `review_context.py delegate` echo gate verified at the consumer. Copied from that run's delegation receipt, not recomputed here — a self-attesting block renders identically whether the gate passed, was rejected, or never ran._

- diff_bytes: 169229
- diff_headers: 7
- diff_sha256: 0fe8490f2ceb0c793378f46d93a71a371ab7b69434cf8c59e6ff707981e41e70
- head_oid: 7e3d5f91505b2b366be6fc328a715dc4a60dc900
- base_ref: refs/remotes/origin/main
- range: fce800b3b308ab7dfefcceffc6d1c49881cf1069...7e3d5f91505b2b366be6fc328a715dc4a60dc900
- worktree_path: /Users/pillip/project/practice/claude-dev-kit/.worktrees/issue-ISSUE-096-bind-review-diff
- worktree_source: branch-worktree
- verified_dimensions: code
