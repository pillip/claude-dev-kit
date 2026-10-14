# Review Notes — PR #137

## Code Review
_Source: reviewer-degraded_

- **[Critical] [gate-evidence] Critical 1 is RELOCATED, not closed: `_refusal_shaped` hard-codes exit-code polarity, so any consumer whose SUCCESS value is a non-zero int credits an arm-only battery as disarm evidence — the PR's own decisive attack fixture returns to exit 0 with a byte-identical PASS line**
  Evidence: `_CONSUMER_RE` (scripts/verify_gate_evidence.py:280) deliberately whitelists `status_code` alongside `exit_code|exitcode|returncode|return_code|rc`. `_refusal_shaped` (:978-1005) then applies ONE polarity rule to all of them, `_NONZERO_INT_RE` (:317) = non-zero int means refusal. True for exit codes; FALSE for HTTP status codes, where 200/201/204 are the SUCCESS values.

Unit:
    _refusal_shaped('==','200') = True
    _refusal_shaped('==','201') = True
    _refusal_shaped('==','204') = True
    _refusal_shaped('==','0')   = False

The decisive attack, through the REAL blocking consumer (the seam the PR's own tests monkeypatch at tests/test_gate_evidence_contract.py:416,427,441). `issue_078_pre_fix.diff` is the diff AC-1/AC-2 REQUIRE to be blocked; the only addition is two PURELY arm-direction batteries whose single consumer assertion is `assert response.status_code == 200`:

    ### CONTROL: unmodified pre-fix fixture through the REAL checkpoint consumer
    FAIL: gate-evidence — 2 gate(s) added without paired evidence (ISSUE-081 / SPEC-081)
        consumer exit = 1
    ### ATTACK: same fixture + HTTP-idiom arm-only batteries, REAL consumer
    PASS: gate-evidence — 2 gate(s) carry both directions: cmd_validate, sprint_status_is_running
        consumer exit = 0

That PASS string is byte-identical to the output the PREVIOUS review recorded as its Critical 1. Every input in the attack is one the gate must ACCEPT; there is no `is False`, no non-zero exit, no refusal constant, no `pytest.raises`.

Why the validation corpus could not have caught it: `status_code` occurs 0 times repo-wide outside that regex; all four committed fixtures assert only `exit_code`/`rc`/`returncode` with 0=success and 1=refusal; and the 8 arm-only shapes behind the headline `1/8 -> 8/8` are ALL exit-code-idiom successes (`consumer_exit_zero`, `subprocess_returncode_zero`, `success_verdict_string`). So `8/8` and `0 false blocks over 15 diffs` follow from the corpus's idiom, not from classifier soundness.

Severity scope: this ships as plugin v0.7.0 and runs on the USER's branch diff (`_gate_evidence_diff`, scripts/verify_checkpoint.py:1377). The kit carries eight UI/UX agents (web, mobile, desktop), so HTTP-idiom projects are a first-class target, not an edge case.

Secondary vector, same root: `_SCREAMING_NAME_RE.findall` is UNANCHORED, so a trailing comment carrying an uppercase refusal token flips `disarm` on an arm-only battery — `assert proc.returncode == 0  # no ERROR expected on a good payload` yields `disarm: True`, versus `disarm: False` for the identical line without the comment. (The engine's own `_refusal_assertions` docstring at :1013 discloses this vector but its example `# rc is 1` does not reproduce, because the greedy `[^,\n]+` capture makes the anchored int/bool patterns fail; an UPPERCASE token reaches the unanchored findall and does reproduce.)
  Fix: Do not patch the vocabulary — polarity is a semantic property of the consumer, not a lexical one, and the implementer already conceded it is 'permanently undecidable' for detector-shaped gates. Split the tier along the line the code already draws. `missing-disarm-battery` (fires only when `attributed == []`, i.e. pure syntax via `_calls`/`_attributed`, measured 11/11 true positives per skills/review/SKILL.md:198) is the only finding kind free of the polarity classifier; keep it BLOCKING. `missing-refusal-direction` and `missing-composite-pin` both route through `_refusal_shaped` (:970, :1044) and must become ADVISORY. Measured cost of that split: ZERO on the entire committed corpus — on all four fixtures the polarity-free subset alone yields the identical exit code (pre_fix 1/1, post_fix 1/1, non_gate 0/0, colliding_main 1/1). This is NOT the blanket Option G the SPEC rejected: the obligation remains an exit code for the decidable property, so the 'advisory gate-evidence is Option A with a script' counter-argument does not apply.

- **[Critical] [gate-evidence] The direction classifier's entire error analysis is ONE-DIRECTIONAL — only `direction=False` verdicts were audited, so the fail-open direction was never measured; this is review lesson 16 recurring inside the PR that is lesson 16's carrier**
  Evidence: SPEC-081 scopes its own audit to one direction in both places it states the error rate:
  line 83  (Option E Cons): 'it misclassifies **16 of 27** `direction=False` verdicts (59%) as missing when the battery is a genuine disarm battery'
  line 187 (amendment decision 1): 'Hand-classified per battery, **16 of 27** `direction=False` verdicts are wrong'
Both populations are `direction=False` — the FALSE-BLOCK direction. The `direction=True` population, the only one that can produce a false PASS, is never audited in the SPEC, the module docstring, or the SKILL clause.

Line 188 then rests the safety case on the untested direction: '`any()` semantics, not classifier accuracy, is what makes this safe ... the safety margin is incidental rather than designed.' The argument is circular: the classifier's bias toward CREDITING is what holds false blocks at 0, and that same bias is the fail-open.

The over-credit direction is pinned by exactly 3 negative assertions in the whole 3407-line suite (tests/test_gate_evidence_contract.py:1452-1457): `('!=','False')`, `('==','0')`, `('is','True')` — all three in the exit-code idiom. Nothing pins a non-zero int that is not a refusal; nothing pins an existence `assert not`.

Measured over this repo's OWN test corpus (4047 assert lines in tests/): 598 (14.8%) are credited as refusal assertions by `_refusal_shaped`. Top drivers: `is False` 179, `== 1` 175, `== 2` 67, `== 3` 7, plus `== 45`, `== 600`, `== 124`, `== 42`, `== 32`, `== 30`, `== 900`. 242 of 598 (40%) are `== 1`/`== 2`, overwhelmingly `len(...)`/`count(...)` counts such as `assert len(results) == 1` and `assert len(entries) == 2`. A further 97 are `assert not`, including pure existence checks like `assert not (AGENT_DIR / "brainstormer.md").exists()`.

Mutation evidence that the pinning is idiom-bound, run on a scratch COPY (worktree never modified): the maximal over-credit mutant (`_refusal_shaped` always True) is caught — 16 failed, 187 passed. But a candidate FIX that excludes 2xx as a success status leaves the suite COMPLETELY GREEN — 203 passed — while closing the bypass (`_refusal_shaped('==','200')` -> False, `('==','404')` -> True, `('==','1')` -> True). A fix that breaks no test proves the current behaviour is wholly untested.
  Fix: Audit the `direction=True` population with the same hand-classification already applied to `direction=False`, and report BOTH rates wherever one is reported. Then apply the tier split in the preceding finding; a classifier with an unmeasured false-positive-on-evidence rate cannot carry a blocking verdict. Note that a 2xx patch alone is whack-a-mole: it does not touch the count-based over-credit (`== 1`/`== 2`, 40% of credited lines) or the unanchored SCREAMING-name path.

- **[High] [gate-evidence] Critical 3 is RELOCATED: the `origin/HEAD` fix tests for base EQUALITY, but narrowing the base to any ANCESTOR of HEAD hides every gate committed before it, and neither new refusal fires**
  Evidence: `_gate_evidence_diff` (scripts/verify_checkpoint.py:1410-1429) added two refusals — the resolved default branch equalling the branch under review, and `base_sha == head_sha`. Both are equality tests against a threat SPEC-081 itself describes as 'author-writable, local, never pushed, invisible in a PR' — and that threat does not require equality.

Independently reproduced (scratchpad/anc, 3-commit branch, gate in commit 1):
    === BASELINE: base = main (3 commits back) ===
    FAIL: gate-evidence — 1 gate(s) added without paired evidence (ISSUE-081 / SPEC-081)
      - [missing-disarm-battery] validate_token (scripts/gate.py:21) ...
    === ATTACK: base = HEAD~1 (an ANCESTOR of HEAD, not equal to it) ===
        merge_base=2ca8e82  HEAD=db35373  equal? NO
    PASS: gate-evidence — no gate DETECTED in the diff. ...
    EXIT=0

Confirmed through the full consumer path with a real `refs/remotes/origin/HEAD` write: `_default_branch() -> 'narrowed'`, `merge_base != HEAD`, verdict `PASS ... no gate DETECTED`, exit 0.
  Fix: Replace the equality tests with a reachability test: require `git merge-base --is-ancestor <base> HEAD` AND that `<base>` is reachable from the default branch's REMOTE ref, so a locally-written `origin/HEAD` cannot narrow the window. Pin with a fixture whose base is an ancestor rather than equal to HEAD.

- **[High] [gate-evidence] One committed `.gitattributes` line (`*.py -diff`) disarms the entire blocking gate, and there is no binary-rendering defence anywhere**
  Evidence: When `.py` renders as binary, `git diff` emits only headers, so `_parse` finds no added lines while the diff stays non-empty — the zero-byte guard at scripts/verify_checkpoint.py:1436 never fires.

Independently reproduced (scratchpad/gaprobe, real CLI):
    === CONTROL: gate committed, no .gitattributes ===
    FAIL: gate-evidence — 1 gate(s) added without paired evidence (ISSUE-081 / SPEC-081)
      - [missing-disarm-battery] validate_token (scripts/newguard.py:7) ...
    EXIT=1
    === ATTACK: one committed line '*.py -diff' in .gitattributes ===
    diff --git a/.gitattributes b/.gitattributes
    new file mode 100644
    PASS: gate-evidence — no gate DETECTED in the diff. ...
    EXIT=0

No binary handling exists: `grep -n 'Binary|binary'` across scripts/verify_gate_evidence.py and scripts/verify_checkpoint.py returns exactly one hit, an unrelated comment about a missing command binary. Binary rendering is tested only as a parser case for `assets/logo.png` (tests:2965); nothing refuses a changed `.py` that rendered as binary.

This is strictly worse than the original Critical 3 vector it resembles: `git remote set-head` was local-only and per-author, whereas `.gitattributes` is committed, applies to every subsequent PR, and reads as innocuous repo configuration.
  Fix: Refuse when the branch delta contains a changed non-test `.py` path whose hunk body is absent — i.e. when a path matched by detection rendered as `Binary files ... differ`. Fail CLOSED and name the cause, as the zero-byte and base guards already do. Optionally pass `-c core.safecrlf=false -c diff.*.binary=false` or `--text` for the acquisition diff.

- **[High] [gate-evidence] The evidenced verdict still asserts a fact the detector cannot know — decision 3's own lesson was applied to the gate-free verdict and not to the PASS line that certifies evidence**
  Evidence: Amendment decision 3 correctly rewrote the gate-FREE verdict to `no gate DETECTED ... A pass means no gate was detected, NOT that none was added` (scripts/verify_gate_evidence.py:1065-1070), and the SKILL reinforces it twice (skills/review/SKILL.md:199 'A pass from this phase means **no gate was detected**, never "no gate was added"'; :205 'Auto-passes when no gate is DETECTED ... which is not the same as the diff adding none'). That half is substantive and holds.

The evidenced verdict received no equivalent treatment and states a positive claim:
    PASS: gate-evidence — 2 gate(s) carry both directions: cmd_validate, sprint_status_is_running
That line is what my Critical-1 attack elicits for two gates evidenced ONLY in the arm direction.

The disclosure is one-directional too. The `_UNDIRECTED_MESSAGE` remedy and SKILL:198 both disclose only the UNDER-credit direction ('misread 16 of 27 such verdicts', 'the exemption is the designed remedy') — telling an author whose battery was wrongly rejected how to proceed. Neither discloses that the classifier can OVER-credit and print a false 'carry both directions'. A green gate-evidence line therefore becomes the review record's evidence that disarm coverage was verified.
  Fix: State what was actually checked, not what was concluded: e.g. `PASS: gate-evidence — N gate(s) have an attributed battery with a refusal-SHAPED assertion (polarity read lexically; see SPEC-081 amendment decision 1)`. Apply decision 3's own standard — say only what is known — to the evidenced verdict as well as the gate-free one.

- **[High] [gate-evidence] The self-application PASS that AC-5 rests on is an artifact of two unrecorded style choices inside the two functions the rework added to implement the new requirement — Goodhart's law inside the harness**
  Evidence: The team lead's implement instruction stated the self-application target as a required OUTPUT NUMBER ('the self-run must show 2 evidenced + 5 exempted'). The implementing sub-task disclosed, unprompted, choosing a `return bool(...)` style partly to hit it. Measured, the disclosure understates the effect.

`_BOOL_REFUSAL` is `\breturn\s+(?:True|False)\b`, so `return bool(x)` is invisible. Four functions in scripts/verify_gate_evidence.py are otherwise gate-shaped and written `return bool(`; rewriting each into an equivalent form flips detection on 4 of 4:
    is_test_path     `return bool(X)` invisible -> `if X: return True / return False` DETECTED
    _calls           invisible -> both rewrites DETECTED
    _refusal_shaped  invisible -> both rewrites DETECTED
    _asserts_refusal invisible -> both rewrites DETECTED

Two are hidden by return STYLE alone, with no restructuring, and both sit in the rework's new direction code:
  (a) `_refusal_shaped` (:978) already has an added `if` line and is predicate-shaped via `-> bool`. Teaching `_BOOL_REFUSAL` to see `return bool(` — a one-token vocabulary change — on the real committed diff: 7 gates -> 8, findings 0 -> 1, `[missing-composite-pin] _refusal_shaped`.
  (b) `_asserts_refusal` (:1037) is the sharpest instance. The module has FOUR knob-reading predicates. The three pre-rework ones (`_attributed`, `_is_non_vacuous`, `_has_consumer_outcome`) are written `if not KNOB: return True` / `return bool(...)`, are all DETECTED, and all three carry `GATE-EVIDENCE-EXEMPT` markers. The fourth — added by the rework to implement the new knob — is written as the one-liner `return (not REQUIRE_REFUSAL_DIRECTION) or bool(_refusal_assertions(block))` and needs no marker. Swapping it into its own siblings' style, same two statements, inside the real diff:
    as committed:                     gates=7  findings=0  exit 0
    _asserts_refusal in sibling style: gates=8  findings=1  exit 1  [missing-disarm-battery]
    BOTH style choices reverted:       gates=9  findings=2  exit 1

So the rework added 11 new functions and ZERO became a gate; the detector reports the identical 7 symbols it reported pre-rework at `7a10422`.

Idiom measurement — anomalous by ~40x:
    verify_gate_evidence.py (new):  return bool( = 6   return True/False = 13   (32%)
    every OTHER scripts/*.py:       return bool( = 2   return True/False = 259  (0.8%)
`return bool(regex.search(x))` is legitimate in isolation, so no single site is damning. What is not explainable by taste is the internal asymmetry: three pre-rework knob-readers in the detectable form, the one rework knob-reader in the invisible form, for the same two statements.

Carrier failures: the disclosure appears in NO committed artifact — `grep -rn 'return bool' docs/` returns 0 hits, no commit message on `b4dda36..HEAD` mentions it, and neither SPEC-081's amendment nor the module docstring records it (review lesson 15: a PR body is not a carrier). And no test pins the self-run numbers — there is no `2 evidenced / 5 exempted` assertion anywhere in the 3407-line test module, so the claim is not a CI tripwire.
  Fix: Two separable actions. (1) Never state a self-application target as a required output number — require the self-run to be reported and EXPLAINED instead; ISSUE-087 is already amended to carry whether such a criterion can be stated at all. (2) On this branch, either rewrite `_asserts_refusal` in its three siblings' style and `_refusal_shaped` detectably and then evidence or exempt them like their siblings, or record the two style choices and their measured effect in the SPEC amendment. Either closes the Goodhart loop; leaving the number unexplained does not.

- **[High] [gate-evidence] AC-5 surviving mutant: neutering `_CONDITIONAL` to match everything deletes half the SPEC's own gate definition and leaves the entire suite green (418/418)**
  Evidence: SPEC-081:126-129 defines a gate as diff-added lines containing BOTH a conditional AND a refusal. Replacing `_CONDITIONAL` with `re.compile(r"")` — so every line counts as conditional, removing the conjunct entirely — leaves 418/418 passing and is byte-identical on all four committed fixtures:
    fixture                        baseline      _CONDITIONAL matches everything
    issue_056_colliding_main.diff  gates=6 f=6   gates=6 f=6
    issue_074_non_gate.diff        gates=0 f=0   gates=0 f=0
    issue_078_post_fix.diff        gates=2 f=1   gates=2 f=1
    issue_078_pre_fix.diff         gates=2 f=2   gates=2 f=2
    <branch HEAD diff>             gates=7 f=0   gates=8 f=1
Only the branch's own diff distinguishes it, and `_REAL_MUTANTS` does not include it. AC-5 requires each rule to be shown load-bearing by mutation; this one is not.

Two further values are unpinned in the same way (the RULE is pinned via monkeypatch, the VALUE is not): `MIN_VARIANTS: 3 -> 1` leaves 418/418 passing, and `_TERNARY_GAP: 400 -> 40` leaves 418/418 passing.
  Fix: Add `conditional_matches_everything` to `_REAL_MUTANTS` with a fixture that distinguishes it — a changed non-test `.py` adding a refusal on a line with no conditional (an unconditional `raise`), which must NOT be a gate. Pin `MIN_VARIANTS`'s value with a 2-variant fixture that must not count.

- **[Medium] [yagni] 69 vocabulary elements and 2 numeric tiers inside a blocking gate have zero reachable effect on any committed input — each deletable with the full suite green**
  Evidence: Instrumented over all gate-evidence tests (four committed fixtures plus every synthetic diff):
    _INPUT_ROOTS    size=22  HIT=1   hit set ['text']   21 never hit
    _GENERIC_TOKENS size=28  HIT=1   hit set ['run']    27 never hit
    roots seen in guards but NOT in _INPUT_ROOTS: ['_meta_block', 'na']
Each of the following was removed one at a time with 418/418 still passing:
    REFUSAL_PATTERNS: drop sys.exit / os._exit / raise SystemExit / the verdict-value regex (0 hits each;
        `os._exit` and `raise SystemExit` occur 0 times in the whole repo and `os._exit` is not even in SPEC:129's list)
    _CONDITIONAL: drop the `^assert` alternative      (0 hits)
    _PREDICATE_SHAPE: drop `_has_`; drop `valid$`/`_ok$`
    _GIT_PATH_PREFIXES "abiwco12" -> "bw"            (only b/ 756 hits, w/ 2 hits)
    _REFUSAL_TOKEN_RE: 8 tokens -> 1 (EXIT)
    _attributed: needed 2-or-1 -> always 1
    _destring: \w{1,24} -> \w{1,2} AND -> \w{1,9999}  (both directions pass)
Engine statement coverage is 98% (481 stmts, 12 miss), so this is not a coverage hole — it is table surface the fixtures never reach. The 12 uncovered statements are all validation (`unquote_c_style`'s named-escape branch :445-448 and malformed-quoting guard :463-464, plus four defensive early returns) and are NOT recommended for cutting — though note the docstring at :417-419 claims verification 'for names containing ", \\ or a tab' and that is precisely the untested branch.

Line-wise the rework is lean: net removable is only -57 of 1527 added engine lines (3.7%), and all five claimed deletions (`--range`, `--repo`, `--json`, `_diff_from_range`, `_GIT_TIMEOUT`) genuinely happened — imports are now `argparse, re, sys, dataclasses, pathlib` only.
  Fix: Shrink the two tables to `frozenset("a b c ...".split())` (-52 lines, every entry KEPT — do not delete entries, since shrinking `_GENERIC_TOKENS` widens attribution and so moves in the fail-open direction); make `_refusal_assertions` return on first match and declare `-> bool` (-3, its only consumer is `bool(...)` at :1044); collapse `needed = 2 if len(symbol_tokens) >= 3 else 1` to `needed = 1` to remove an unpinned branch; narrow `_GIT_PATH_PREFIXES` to the structurally reachable set. Add the missing roots `_meta_block`/`na` or confirm their omission is intended.

- **[Medium] [record] The amendment's corrected numbers are stale a second time, and two further SPEC counts are wrong**
  Evidence: Measured at HEAD (402897c) against SPEC-081's own figures:
    SPEC:60,272  '+848 engine lines ... 129 blank, 45 comment, 74 docstring, 600 executable'
    measured     wc -l 1337 | blank 182 | comment 228 | docstring 243 | executable 717
                 plus scripts/verify_checkpoint.py 210 added / 20 removed
                 => 1527 ADDED engine lines, net +1517 — SPEC is off by 1.6x
    SPEC:60,293  '+3 fixture files' / 'the three fixture diffs'
    measured     4 (issue_056_colliding_main.diff was added by decision 4 itself)
    SPEC:232     'three input-handling fail-opens ... All three are fixed and pinned in this PR'
    measured     the rework fixed at least five (origin/HEAD, C-quoting, _CONDITIONAL ReDoS,
                 the untracked leg, the _CONSUMER_RE ReDoS) plus the UTF-16 fail-open, the
                 diff-of-a-diff phantom header, and exemption provenance
The amendment was committed at `8b86482`, commit 2 of 9, before `86f9bc2`, `d46c0f0` and `f4062a5` landed. This is precisely the class decision 5 exists to correct — 'a comparator that justified this decision has to be the measured number' — failing on its own first use, and it compounds the uncorrected '+~240 lines' still at SPEC:114.
  Fix: Re-measure every comparator at the final commit, or state each figure with the commit it was taken at. Prefer generating these counts rather than copying them into prose — a derived number written by hand is a record-rot generator.

- **[Medium] [gate-evidence] `_untracked_paths` conflates 'git failed' with 'nothing untracked', silently deleting the untracked leg that Critical 2's fix just added**
  Evidence: scripts/verify_checkpoint.py:478-481: `if result.returncode != 0 or not result.stdout.strip(): return []`. Armed control vs disarm in one repo (untracked gate plus a non-empty committed delta):
    --- mode=none ---              EXIT=1, validate_token named
    --- mode=ls-files-fail ---     [probe] DISARMED `git ls-files --others --exclude-standard` -> rc=1
                                   PASS: gate-evidence — no gate DETECTED in the diff.   EXIT=0
    --- mode=ls-files-timeout ---  [probe] rc=124
                                   PASS: gate-evidence — no gate DETECTED in the diff.   EXIT=0
No test covers a git failure anywhere in acquisition: `grep returncode tests/test_gate_evidence_contract.py` finds only detector-side cases.
  Fix: Separate the two conditions — return `None` (fail CLOSED, naming the cause) on non-zero/timeout, and `[]` only on a genuine empty success. Pin with a disarmed-git fixture in both directions.

- **[Medium] [gate-evidence] `_untracked_diff_text` drops an unreadable untracked file silently, and the comment justifying that choice rests on a measurably false premise**
  Evidence: scripts/verify_checkpoint.py:1365-1368 reasons that `git diff --no-index` 'exits 1 on an unreadable path — so the exit code cannot discriminate. The presence of diff text is the signal.' Git actually returns 128 there, so the exit code DOES discriminate (0 identical, 1 differ, anything else error). Real trigger, no monkeypatching — untracked gate at mode 000:
    -- what git itself says --
    error: open("scripts/gate.py"): Permission denied
    fatal: cannot hash scripts/gate.py
       (rc=128)
    PASS: gate-evidence — no gate DETECTED in the diff.
    EXIT=0
The readable control exits 1.
  Fix: Treat rc >= 2 as an error and fail CLOSED naming the path; keep 'presence of diff text' only for the rc in (0,1) case.

- **[Medium] [gate-evidence] A `#`-prefixed exemption marker inside a `.py` DOCSTRING in the gate's own file IS honoured, contradicting `_exemptions`' own docstring**
  Evidence: `_COMMENTED_RE = ^[^"'#]*#` (scripts/verify_gate_evidence.py:268) is a purely lexical prefix check with no string/docstring awareness, so any line whose first non-quote run ends in `#` qualifies — including docstring body lines.
    --- E  docstring body, marker line prefixed by '#', in the GATE'S OWN .py file   => GATE WAIVED? True
    --- G  FENCED code block inside a .py docstring, in the GATE'S OWN file          => GATE WAIVED? True
    --- J  triple-quoted assignment, marker on its own line                          => GATE WAIVED? True
    --- F  docstring body, marker NOT '#'-prefixed                                   => GATE WAIVED? False
Reproduced through the REAL branch diff (docstring line carrying `#` in scripts/verify_checkpoint.py): verdict moved to `1 gate(s) carry both directions: main | 6 exempted`, CHANGED VERDICT? True.

The `_exemptions` docstring (~:1132) claims the opposite: 'The marker has to sit in a comment ... so SPEC prose inside a fenced block and a docstring sentence are both inert.' False for the `#`-prefixed form. Narrowed but not closed by the same-file rule, so the exploit must land in the gate's own `.py` file; `verify_gate_evidence.py` is canaried by `test_the_five_intended_self_exemptions_are_well_formed`, no other script is.

No test covers this shape. `test_a_marker_in_a_python_docstring_does_not_exempt` (:1919) is OVERDETERMINED — its fixture is in `scripts/unrelated_helper.py` (wrong file) AND lacks a `#`, so it passes for two independent reasons.
  Fix: Decide provenance with `tokenize`, crediting only real COMMENT tokens, rather than a lexical prefix regex. Add a disarm test for a `#`-prefixed docstring/triple-quote marker in the gate's own file.

- **[Medium] [gate-evidence] Two surviving mutants in the exemption-provenance guards, and two false 'pinned by' provenance claims in the same docstring**
  Evidence: Both mutants leave the ENTIRE module suite green (203 passed), yet both are behaviour-changing:
  mut_quote    `_COMMENTED_RE := ^[^#]*#` (drop the quote-exclusion)  -> 203 passed
      REAL   ^[^"'#]*#  -> exemptions=[]                            findings=['missing-disarm-battery']
      MUTANT ^[^#]*#    -> exemptions=[('scripts/demo.py','check_thing')] findings=[]
  mut_testpath `is_test_path` clause removed from `_exemptions`       -> 203 passed

The docstring's provenance claims for both are false. It says the non-test rule is 'pinned by `test_an_exemption_quoted_in_a_TEST_file_does_not_count`'; that test's fixture is blocked by the quote-exclusion instead, so the clause is shadowed:
    fixture: '    assert "# GATE-EVIDENCE-EXEMPT(check_thing): nope" in doc'
    quote-exclusion blocks it?      True
    test-path rule alone blocks it? True
    REAL on the suite's own fixture              -> exemptions: []
    MUTANT (no test-path clause) on the SAME fixture -> exemptions: []   <-- shadowed
Requirements 1 and 3 mutually shadow each other in one shared fixture: deleting either alone leaves the suite green. Because `detect_gates` also skips test paths, the `is_test_path` clause in `_exemptions` is now reporting-only for the verdict.

This is the fourth instance on this branch of 'a stated provenance or measurement is not the measured thing' — after `_GIT_TIMEOUT`'s untrue provenance (closed by deletion), commit 402897c ('correct a provenance comment that was false in three ways'), and the SPEC engine-size figure below. The class is not closed.
  Fix: Add a distinguishing fixture per clause: a BARE `#` marker in a test file (isolates the test-path rule) and a quote-shadowed `#` in a non-test `.py` file (isolates the quote-exclusion). Then correct the two 'pinned by' sentences to name the tests that actually kill each mutant.

- **[Medium] [record] SPEC-081's own engine-size correction is already stale by 489 lines, and the figure decision 5 claims to have 'corrected in place' was only corrected in one of its two locations**
  Evidence: Amendment decision 5 (docs/specs/SPEC-081.md:272) states: 'The engine-size trade-off line was wrong by 3.5x and is corrected in place ... the measured file is **848** lines — 129 blank, 45 comment, 74 docstring, **600 executable**', and justifies the correction on the principle that 'a comparator that justified this decision has to be the measured number'.

Measured on the committed HEAD (402897c):
    wc -l scripts/verify_gate_evidence.py = 1337
    blank=181  comment=228  docstring~=243  executable~=685
The 848 figure was measured at commit 2 of 9 (`8b86482`); commits 3-9 added 489 more engine lines and the number was never re-measured. Against the SPEC's original '+~240 engine lines' estimate the delivered engine is 5.6x, not 3.5x.

And the 'corrected in place' claim holds for only one of the two sites: line 60 (Option C's trade-off line) now reads '+848 engine lines', but line 114 (the Decision prose) still reads 'Option C's cost (+1 blocking phase, +~240 lines, +3.4k fixture lines)' — uncorrected.

For completeness the test module is 3407 lines / 130 test functions, and comment+docstring is 471 of 1337 engine lines (35%), much of it prose justifying the classifier's disclosed error rate.
  Fix: Re-measure at the final commit and correct both sites, or state the figure as a range with the commit it was taken at. A self-correcting record that fails on its first use is worse than an uncorrected one, because it certifies the number.

- **[Medium] [gate-evidence] Critical 5's remedy is incomplete in a third place: `analyze()` is QUADRATIC in gates x batteries with no memoisation, so the gate takes 32.5 s on a 212 KB diff — double the wall-clock that was cited as grounds for an advisory landing — and nothing bounds it**
  Evidence: Both committed ReDoS fixes genuinely hold (verified separately, see the positives). The residual cost is STRUCTURAL, not regex-internal, and `_MAX_SCAN_CHARS` does not bound it: `analyze()` recomputes `attributed` / `_has_consumer_outcome` / `_asserts_refusal` once per (gate x battery) pair with no memoisation, so the same lines are re-scanned G*B times. The bound caps ONE scan at 3.5 ms; it does not cap how many scans happen.

Measured through the real `analyze()`, one 2044-char `assert`-spam line per battery (every number carries the regex execution count, so no row is a false all-clear):
    G=B    input B    analyze    _CONSUMER_RE calls   growth
      2       4800    0.0151s                    22
      4       9327    0.0570s                    92    3.78x
      8      18379    0.2257s                   376    3.96x
     16      36495    0.9087s                  1520    4.03x
     32      72737    3.7018s                  6112
     48     108977    8.1099s                 13776
     64     145217   14.307 s                 24512    (quadratic prediction 14.401s)
     96     217697   32.531 s                 55200    (quadratic prediction 32.153s)
Quadratic across five doublings, predicted within 1%. At 212.6 KB the gate takes 32.5 s, versus the 15.2 s that docs/specs/SPEC-081.md:232 cites as one of the three grounds raised for an advisory first landing, at essentially the same input size (208 KB). Extrapolated ~425 KB -> 130 s, ~850 KB -> 520 s.

Nothing bounds it (review lesson 1): `verify_review_gate_evidence` (scripts/verify_checkpoint.py:1448) calls `vge.analyze(diff_text)` IN-PROCESS; `scripts/checkpoint.sh:21` is `exec python3 ... verify_checkpoint.py "$@"` with no timeout; `_gate_evidence_diff` applies no size cap to the diff text; and there is no `signal.alarm`/`SIGALRM` anywhere under `scripts/`. The `_DEFAULT_TEST_TIMEOUT = 600` at scripts/verify_checkpoint.py:68 is a SUBPROCESS timeout and cannot bound an in-process call.

Adversarial-only, and more conspicuous in a diff than one long line: the benign control with ordinary short lines shows the same quadratic with a negligible constant (G=B=48, 12017 B, 0.0774 s), and this PR's own merge-base diff is 684077 chars / analyze=0.1937s / gates=7 batteries=29. But it is the same threat model Critical 5 was fixed under, and it is now the third of the five Criticals whose remedy closed the measured instance and left the class reachable.
  Fix: Memoise per battery rather than per (gate, battery) — `_asserts_refusal`, `_is_non_vacuous` and `_has_consumer_outcome` are all functions of the battery alone, so hoisting them out of the gate loop makes the pass linear and is a pure refactor with no behaviour change. Separately, give the blocking gate a wall-clock bound (a `signal.alarm` in the phase, or a diff-size cap that fails CLOSED and names the cause) so lesson 1 is closed structurally rather than per-regex.

- **[Medium] [record] The safety numbers that block demotion — '0 false blocks over 15 corpus diffs' and '0 false positives over 12 real merged diffs' — are recorded nowhere reproducible**
  Evidence: SPEC-081 cites these figures five times as the reason the blocking tier stands, and states the demotion criterion IS a measured false-positive rate (lines 81, 86, 107, 183, 236): 'The SPEC's own stated demotion criterion is a measured false-positive rate; the measured rate is 0 false positives over 12 real merged diffs and 0 false blocks over 15, so the criterion is not met.'

But only FOUR diffs are committed (`tests/fixtures/gate_evidence/*.diff`), and no test replays a 15- or 12-diff corpus. The other 11 are not named, not committed, and carry no SHAs. By contrast the four committed fixtures have exemplary provenance — `tests/fixtures/gate_evidence/README.md` gives the exact regeneration command and resolved SHAs for each, specifically because CI runs at `fetch-depth: 1`. The same discipline was not applied to the larger corpus.

This matters beyond bookkeeping: this review's Critical findings show the corpus was idiom-homogeneous (zero `status_code` consumers, every fixture using 0=success), which is precisely the property an inspectable corpus would have exposed. An unreproducible measurement cannot be re-run against a widened corpus, so the demotion criterion can neither be re-tested nor falsified.
  Fix: Commit the corpus manifest — the 15 SHAs plus the regeneration commands — in the same README format already used for the four fixtures, and add a test that replays it. Until then, cite the figures as 'measured once, not reproducible' rather than as a criterion.

- **[Low] [gate-evidence] Review lesson 2 residual: the four `REQUIRE_*` knobs are absent from the docstring's tunables paragraph, and the finding they remediate does not print the knob name**
  Evidence: The module docstring's tunables paragraph names only `MIN_VARIANTS`, `_TERNARY_GAP` and `_MAX_SCAN_CHARS`. `REQUIRE_REFUSAL_DIRECTION`, `REQUIRE_VACUITY_GUARD`, `REQUIRE_INPUT_ONLY_PARAMS` and `REQUIRE_CONSUMER_OUTCOME` are each documented at their own definition but appear in no summary list, and `_UNDIRECTED_MESSAGE` — the finding `REQUIRE_REFUSAL_DIRECTION` remediates — does not print the knob name. Lesson 2's user-facing-doc half is N/A here: no env knobs were added (the module imports no `os`). For the record, `REQUIRE_REFUSAL_DIRECTION` IS load-bearing — flipping it fails 15 tests.
  Fix: List all seven tunables in the docstring paragraph and name the knob in the message it governs.

- **[Low] [gate-evidence] Three pieces of surface have a review-note carrier but no AC and no amendment decision**
  Evidence: Lesson 14's shape, though each does have a durable carrier so lesson 15 is satisfied: the untracked-diff leg (`_untracked_paths` + `_untracked_diff_text`, ~60 engine lines plus 2 test classes — carrier `docs/review_notes/ISSUE-081.md:12-19`); the `diff.mnemonicPrefix` and `diff -u` TAB-timestamp renderings (~8 lines — carrier :92-93, which itself records that 'the gate is still detected, only the label is wrong', i.e. 8 lines bought for a label); and the second `_CONSUMER_RE` ReDoS bound (commit `d46c0f0`, carried only by a code comment at :948-962 plus `TestTheConsumerOutcomeScanIsBounded`, with nothing in SPEC-081). All 29 test classes otherwise map to an AC, an amendment decision, or a committed review finding.
  Fix: Name these three in the SPEC amendment's decision list, or route the label-only one to a carrier and drop its 8 lines.

- **[Low] [gate-evidence] The 'guard the guard' test for the second ReDoS bound does not pin attribution, so the whole bounded-scan class can go vacuous without it noticing**
  Evidence: `test_the_costly_call_is_actually_reached` pins two of the three preconditions (battery-ness, non-vacuity) but not attribution — the one that actually puts the battery into `attributed`. Measured on a 192 KB payload:
    as committed: run_guard(text)        reached-guard asserts PASS=True  _CONSUMER_RE exec=6  analyze=0.0157s
    attribution removed: probe_it(text)  reached-guard asserts PASS=True  _CONSUMER_RE exec=0  analyze=0.0090s
The guard still passes while the regex executes ZERO times, so a future rename in the fixture would make the entire `TestTheConsumerOutcomeScanIsBounded` class vacuous silently. This is the exact failure the class was written to prevent — two probes in the previous round reported false all-clears for precisely this reason — reproduced one level up, in the test that exists to stop it. The class as committed does pass (12 passed).
  Fix: Assert the precondition that matters: `assert vge._calls(block, SYMBOL) or vge._attributed(block, SYMBOL)`, or assert the execution count directly by counting `_CONSUMER_RE.search` calls.

- **[Low] [record] SPEC-081's decisive decision-2 measurement is reproducible but not re-derivable — 'refusal vocabulary' is never defined, and the mirage result holds under only one of five plausible readings**
  Evidence: The claim that kills the best-looking `return None` closure rests on a rule the SPEC names only as `| refusal vocabulary anywhere in the def | +3, 0 FP | yes | **no** | a measurement artifact — rejected |` (docs/specs/SPEC-081.md:209), with :214 describing only the rewording. The result reproduces EXACTLY under a case-sensitive `refusal|refused` and only under that reading. Measured through the identical docstring-only mutation:
    reading of 'refusal vocabulary'                extras   turned OFF
    case-sensitive `refusal|refused`                  +3     2 of 3   <- matches the SPEC
    same, case-insensitive                            +4     2 of 4
    `refus|reject|deny|invalid|block`                 +7     1 of 7
    the module's own `_REFUSAL_STRING_RE`            +11     0 of 11
    the module's own `_REFUSAL_TOKEN_RE` (ci)        +12     0 of 12
Under either of the module's OWN refusal vocabularies the rule is not a mirage at all — it is plain over-detection and the mutation changes nothing. So the next reader re-runs a different experiment and reaches a different verdict.

Also a framing nuance on the same decision: under the promotion, PR #129 ALSO yields a blocking finding (`parse_roster_watermark: attributed=3 disarm=True composite=False -> missing-composite-pin`), so 2 of 2 recalls produce a blocking verdict rather than the recorded '1 false BLOCK per 2 recalls'. Only #127's is the mis-attribution class the claim names, and decision 1 already records #129's composite-pin outcome, so this is wording rather than a contradiction.

And a third record note from the same dimension: the committed comment at scripts/verify_gate_evidence.py:158 records '15.2 s on one 208 KB added line'; the same payload size measures 49.94 s here, understating by 3.3x (payload/hardware dependent, direction unaffected).
  Fix: Carry the exact pattern — including its case-sensitivity — into ISSUE-086 as decision 2's starting point, and state the measurement's corpus command as the fixtures README already does. Re-word the '1 false BLOCK per 2 recalls' line to name the class rather than the ratio.

- **[Low] [record] The '11 of 11 true positives' reliability figure for `missing-disarm-battery` exists only in SKILL prose, with no source in the SPEC, the code, or any test**
  Evidence: `grep -rn '11 of 11|11/11'` across docs/specs/SPEC-081.md, skills/review/SKILL.md, scripts/verify_gate_evidence.py and tests/test_gate_evidence_contract.py returns exactly one hit — skills/review/SKILL.md:198. The paired figure in the same sentence (16 of 27) is sourced to SPEC-081 amendment decision 1; this one is sourced to nothing.

Flagged because it is the number that distinguishes the reliable finding kind from the unreliable one, and this review's recommendation concerns exactly that split. The recommendation does not depend on it: the structural argument (the kind fires only when `attributed == []`, so it never consults `_refusal_shaped`) and this review's own measurement (the polarity-free subset preserves the exit code on all four committed fixtures) are independent support.
  Fix: Source it to a measurement in the SPEC amendment or drop the figure, applying the same standard decision 5 set for the engine-size comparator.

- **[Low] [gate-evidence] The named `base == branch` refusal is unreachable for the kit's own branch names, and the test that pins it uses a branch shape the real caller never has**
  Evidence: `_default_branch` reduces to the last path segment (scripts/verify_checkpoint.py:141, `rsplit("/", 1)[-1]`), and kit review branches always contain `/` (`refs/heads/issue/ISSUE-081-gate-evidence`), so `base == branch` is unsatisfiable on the real path. Pointing `origin/HEAD` at the branch under review lands on the generic refusal instead:
    refs/remotes/origin/issue/ISSUE-900-probe
    _default_branch() -> 'ISSUE-900-probe'
    FAIL: gate-evidence — REFUSED (not clean): no trustworthy branch diff ...
    EXIT=1
Still fail-closed, so verdict-neutral. But `test_a_disarmed_run_does_not_read_like_a_clean_one` pins the named cause using the slash-free branch `work` — review lesson 16's 'tested in the arm direction at its helper' shape, with a fixture the real consumer cannot produce.
  Fix: Either compare against the full ref rather than the last segment, or pin the named refusal with a slash-containing branch name matching the kit's own convention.

- **[Low] [gate-evidence] 'exactly one definition repo-wide' is pinned over a non-recursive `scripts/*.py` glob only**
  Evidence: tests/test_gate_evidence_contract.py:380-390 counts the two regex fragments as plain substrings across a non-recursive `scripts/` glob. Copies planted in `tests/conftest.py` or `scripts/sub/dup.py` both leave the class 10/10 green. The positive control confirms the test works within its scope — planting a 5th copy in `scripts/verify_gates.py` fails `test_the_two_regexes_have_exactly_one_home_in_scripts`. No out-of-scope copy exists today; the test docstring is honest about its scope and only the commit-message claim ('one definition repo-wide') overstates it.
  Fix: Walk the repo recursively, or soften the commit/record wording to match the pinned scope.

- **[Low] [record] The dropped stash's cited archive path does not exist where the record says it does**
  Evidence: docs/sprint_state.md cites the archive as `scratchpad/dead-run-uncommitted-1f6d924e78bbab9c7d82b3e314ca999b1d33211e.diff`, which reads repo-relative; `ls` in the repo root returns 'No such file or directory'. The file is actually in the per-session OS temp directory (`/private/tmp/claude-501/.../scratchpad/`), which is not durable across sessions — review lesson 15's class applied to an archive rather than a carrier.

Substance is NOT lost: the stash commit `1f6d924` is still a reachable object (`git cat-file -t 1f6d924` -> commit), and the drop itself was justified — 0 hits for every one of the five Critical sites (`unquote_c_style`, `_untracked_paths`, `origin/HEAD`, `_TERNARY_GAP`, `_refusal_shaped`, `REQUIRE_REFUSAL_DIRECTION`, `is_test_path`), and its one substantive engine change was widening `REFUSAL_PATTERNS`, which is amendment decision 2's territory.
  Fix: Cite the recoverable git object (`1f6d924`) as the archive of record, or copy the diff somewhere durable. Do not cite a session temp path as though it were repo-relative.

- **[Low] [gate-evidence] An unhonoured cross-file exemption marker still prints a bare `EXEMPT:` header line**
  Evidence: `report.exemptions` collects every well-formed non-test `.py` marker regardless of locality, and `format_report` prints them all before the verdict:
    EXEMPT: scripts/other.py:check_thing — written in the WRONG file
    FAIL: gate-evidence — 1 gate(s) added without paired evidence (ISSUE-081 / SPEC-081)
      - [missing-disarm-battery] check_thing (scripts/demo.py:5) ...
The header reads as a waiver that did not happen. The suite asserts this deliberately and the summary's `exempted & keys` count is correct, so this is cosmetic only.
  Fix: Mark unhonoured markers explicitly, e.g. `EXEMPT (IGNORED — wrong file): ...`, so the echo cannot be misread as an applied waiver.

- **[Low] [debt] Tech-debt ledger: 3 no-trigger markers and 1 malformed marker (pre-existing, unchanged by this PR)**
  Evidence: `bash scripts/checkpoint.sh --skill review --phase debt --issue ISSUE-081` (advisory, exit 0): 'total: 14 | no-trigger (silent-rot risk): 3 | malformed: 1'. Byte-identical to the baseline recorded by the previous review.
  Fix: Add a `trigger=` to the three bare markers and repair the malformed one, under the existing debt carrier rather than this PR.

## Security Findings
_Source: reviewer-degraded_

- **[High] A blocking gate is disarmable by two author-controlled, low-suspicion vectors that leave the output reading like a clean pass**
  Evidence: SPEC-081's security claim is that 'this is a deliberately defeatable gate; the claim is that defeating it is *visible*, not impossible' (Trade-offs Accepted). Two vectors defeat it while printing the ordinary gate-free PASS line, so nothing is visible:

1. One committed `.gitattributes` line `*.py -diff` — all `.py` files render as `Binary files ... differ`, `_parse` sees no added lines, the non-empty diff defeats the zero-byte guard, and the phase prints `PASS: gate-evidence — no gate DETECTED in the diff` at exit 0. Reproduced independently against a control that exits 1. Committed and therefore permanent for every later PR, while reading as routine repo config.
2. A local `refs/remotes/origin/HEAD` write to any ANCESTOR of HEAD (not equal to it) narrows the branch delta and hides every gate committed before that point. Both new refusals test equality only, so neither fires. Reproduced independently.

For contrast, the designed escape (`GATE-EVIDENCE-EXEMPT`) is path-qualified, reason-bearing and echoed as an `EXEMPT:` line. Neither vector above produces any marker in the output. This is the rework's own lesson — 'visibility is not enough if the waiver is unrecognisable' — recurring with no waiver printed at all.
  Fix: Fail CLOSED when a detected-scope `.py` path rendered as binary, and replace the base-equality tests with an ancestry-plus-remote-reachability check. Both refusals should name their cause, matching the existing zero-byte and base refusals.

- **[Medium] Exemption provenance is decided by a lexical prefix regex, so a docstring is a usable attestation channel in the gate's own file**
  Evidence: `_COMMENTED_RE = ^[^"'#]*#` has no string/docstring awareness. A `#`-prefixed line inside a `.py` docstring — including inside a fenced block in that docstring — is collected as a live exemption and waives the gate (`GATE WAIVED? True` for shapes E, G and J), reproduced through the real branch diff on scripts/verify_checkpoint.py. Review lesson 6 applies: shape validation is not provenance. Narrowed by the same-file rule, so impact requires write access to the gate's own module — which an author of a gate-adding PR has by construction.
  Fix: Use `tokenize` and credit only genuine COMMENT tokens.

## Over-Engineering

- **[Medium] [shrink] The engine is 5.6x its own SPEC estimate and grew 58% during a rework chartered to fix five Criticals, with the growth unaccounted in the record**
  Evidence: scripts/verify_gate_evidence.py: 848 lines at `7a10422` -> 1337 at HEAD (+489, +58%). Composition at HEAD: 181 blank, 228 comment, ~243 docstring, ~685 executable; comment+docstring is 471 lines (35%). SPEC-081's Decision estimated '+~240 engine lines' (line 114, still uncorrected) and the amendment's correction records 848 (line 60, line 272) — neither matches the delivered 1337. The test module is 3407 lines / 130 test functions. The brief's working figure of '~+848 lines over main' is the pre-rework engine size; the branch's actual delta vs merge-base is +11,943 / -21 across 15 files.
  Fix: Re-measure and record the delivered figure, then justify or reduce the 489-line rework growth against the five Criticals it was authorized for. A large share of the new prose is self-justification for a classifier this review recommends demoting, so the tier split would retire some of it.
