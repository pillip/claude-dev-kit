# SPEC-088: Decline the disarm-DIRECTION property and record the limitation, rather than adopt an attestation successor

> Linked Issue: ISSUE-088
> Status: `accepted`
> Date: 2026-10-31
> Author: claude-dev-kit (implement phase, dogfooding)

## Problem

SPEC-081's 2026-10-24 tier split made `review/gate-evidence` truthful and left a named hole: the
arm-only authoring shape that shipped four consecutive fail-opens passes the phase with a printed
note. Amendment decision 8 named a candidate successor — **attestation plus a reviewer obligation**,
a per-gate declaration naming the test that carries the refusal, with the *detection* half supplying
the gate list mechanically — and deferred the choice. ISSUE-088 is that choice's durable carrier, and
it permits exactly two outcomes: **ADOPT** the successor with a measured argument for why it is not
the attestation shape SPEC-081 already measured at 0 of 4, or **DECLINE** the property outright. A
third deferral is not an outcome.

## Context

Bounding constraints, every one re-measured on 2026-10-31 against the **committed** tree at main
`cc9fe5d` and the retained predecessor branch `issue/ISSUE-081-gate-evidence` at `6aeaf3d`. Nothing
below is quoted from a prior table; the commands are named so each number is re-derivable.

- **ISSUE-081 was dropped unmerged.** PR #137 is closed. `scripts/verify_gate_evidence.py` does not
  exist on main. A case-insensitive `git grep -lEi 'gate.evidence|gate_evidence'` over tracked files
  returns hits in `docs/review_notes/ISSUE-071.md`, `docs/review_notes/ISSUE-083.md`,
  `docs/specs/SPEC-081.md`, `docs/sprint_state.md` and `issues.md` — and **nowhere else**. The
  occurrence count in `skills/review/SKILL.md.tmpl`, the generated `skills/review/SKILL.md` and
  `agents/team-lead.md` is **0**, and in `scripts/verify_gate_evidence.py` it is vacuously 0 because
  the file is absent.
- **The phase is unroutable.** `bash scripts/checkpoint.sh --skill review --phase gate-evidence
  --issue ISSUE-088` prints `ERROR: unknown phase 'gate-evidence' for skill 'review'` and exits **2**.
  `verify_checkpoint.VERIFIERS` registers 12 review phases and `gate-evidence` is not among them.
- **The retained branch is the only place detection exists.** `git diff --stat
  main...issue/ISSUE-081-gate-evidence` is **15341 insertions across 17 files**:
  `scripts/verify_gate_evidence.py` 1881 lines, `tests/test_gate_evidence_contract.py` 5908 lines,
  four committed fixtures 6310 lines, `scripts/verify_checkpoint.py` +399/-21, and 21 lines each in
  `skills/review/SKILL.md` and its template.
- **Detection's vocabulary is `REFUSAL_PATTERNS` itself.** `detect_gates`
  (`verify_gate_evidence.py:974-998` on the retained branch) iterates `REFUSAL_PATTERNS` directly to
  decide whether an added `def` is a gate at all. There is no second vocabulary beneath it.
- ISSUE-088's Scope/Out forbids editing `_refusal_shaped`, `REFUSAL_PATTERNS` or the direction regex,
  and AC-4 requires them byte-unchanged. The 2026-10-31 amendment separately permits *widening
  detection*. At the measured seam those two permissions are the same bytes.
- SPEC-081 measured **Option A** (prose obligation plus a live native-memory lesson) at **0 of 4** and
  **Option D** (PR-body checklist) at **0 of 4**. Those are the comparators any successor must beat.
- Native-memory review lesson 6: *an attestation that can satisfy a gate is forgeable — shape
  validation is not provenance.* A per-gate declaration a human writes **is** an attestation.

## Measurements

Five measurements decided this SPEC. Each is reproducible from this repo's own history.

### M1 — Detection recall for the declaration use case is 1 of 5

Method: for each historical fail-open instance, generate the diff of the commit that **added the
defence** against its parent (`narrow`), and the diff from `git merge-base main <commit>` to that
commit (`wide`, the subject the real consumer computes). Run the retained branch's
`verify_gate_evidence.analyze()` over each and compare the detected symbol set against the
hand-classified symbol that actually failed open.

| # | Instance | commit | defence symbol(s) that failed open | detected (narrow) | detected (wide) | defence in list? |
|---|---|---|---|---|---|---|
| 1 | ISSUE-068 / #121 | `fc7dbe6` | `augment_roster_from_board` — refuses by `if … continue` (×6) | `[]` | `[]` | **no — empty list** |
| 2 | ISSUE-076 / #128 under-read roster | `dfd4821` | `_scan_issue_progress`, `unparsed_roster_rows`, `_issue_progress_table_lines`, `_row_cells` — refuse by **omitting a line** | `['cmd_next_action']` | `['cmd_next_action']` | **no — wrong symbol** |
| 3 | ISSUE-076 / #128 fenced blocks | `1dc575c` | `_unfenced` — refuses by **omitting a line** | `[]` | `['cmd_next_action']` | **no** |
| 4 | ISSUE-078 / #133 | `0d0cae1` | `sprint_status_is_running` | `['cmd_validate', 'sprint_status_is_running']` | same | **yes** |
| 5 | ISSUE-072 / #135 | `9a4cfe9` | `_grant_defects`, `_row_defects` — the guard **is** a test | `[]` | `[]` | **no — empty list** |

**Recall = 1 of 5.** The human is handed an **empty list** on 2 of 5 under the wide subject and 3 of 5
under the narrow one, and a **non-empty list naming a different symbol** on 2 of 5.

### M2 — The one available widening is forbidden by AC-4 by construction

`detect_gates` consults `REFUSAL_PATTERNS` directly, so "widen detection" and "`REFUSAL_PATTERNS`
byte-unchanged" are the same bytes read two ways. The 2026-10-31 amendment's permission to widen and
ISSUE-088's own Scope/Out and AC-4 are mutually exclusive **at the measured seam**, not merely in
tension. Taking the widening means editing exactly the predicate four prior measurements rejected;
honouring AC-4 means detection stays at M1's recall.

### M3 — And the widening does not work anyway

Probe (in-memory only, never written to a file): append `re.compile(r"^\s*continue\b")` to
`REFUSAL_PATTERNS` and re-run M1.

- Recall moves **1 of 5 → 2 of 5**. It closes instance 1 and nothing else.
- Instance 2 still misses under both subjects. Instance 3 now reports `_scan_issue_progress` — still
  not `_unfenced`. Instance 5 is still empty.
- Cost, measured over a whole-tree diff of main (`git diff <empty-tree> HEAD`, 82191 lines): the gate
  count goes **101 → 152**, admitting **51** new symbols. They are overwhelmingly loop-skip idioms,
  not gates: `extract_colors_from_source`, `extract_gradients`, `extract_box_shadows`,
  `generate_css_file`, `_shadow_to_css`, `_pixel_diff`, `export_assets`, `_walk_node`,
  `compare_structure`, `dedupe_exportable_assets`. A declaration list for a human would be **+50%
  longer and dominated by Figma/CSS extraction loops**.

### M4 — Two of the five misses are unreachable by *any* pattern vocabulary

- **Refusal by omission** (instances 2 and 3). A pattern matches an **added line**; a refusal
  expressed by *not emitting* a line adds none. This is a category error, not a vocabulary gap, and
  M3 measured the consequence: instance 2 misses under both vocabularies. No enlargement of
  `REFUSAL_PATTERNS` can reach it, because there is no line to match.
- **The guard is itself a test** (instance 5). `is_test_path` excludes test paths **upstream** of any
  vocabulary, in `detect_gates`'s first `continue`. M3 measured it: empty under both vocabularies.

So the reachable ceiling for a vocabulary-only widening is 3 of 5, and the only step toward it that was
measured costs +51 whole-tree false entries.

### M5 — The ADOPT branch's own ACs are unsatisfiable inside the split trigger's budget

- A **detection-only** lift is genuinely small: the transitive dependency closure of
  `detect_gates`/`_parse`/`is_test_path`/`_FileDiff` is **23 symbols / 268 definition lines**, against
  1310 lines for the full `analyze`/`format_report`/`main` closure of an 1881-line file. The engine
  lift alone would fit the budget, which is why this SPEC does not reject ADOPT on size alone.
- But AC-5 and AC-6 drive `bash scripts/checkpoint.sh --skill review --phase gate-evidence`, which
  exits **2** with `unknown phase` on main. Routing it means landing the retained branch's
  `verify_checkpoint.py` **+399/-21**.
- And AC-7 requires the four committed fixtures (6310 lines) to replay at exit **1 / 1 / 0 / 1** with a
  blocking-vs-advisory split identical to the post-split table. A detection-only engine has no
  findings, no `BLOCKING_KINDS` and no tiers: all four fixtures exit **0**. AC-7 is **unsatisfiable by
  the in-budget lift** and satisfiable only by the full **15341-insertion, 17-file** lift the split
  trigger forbids outright.

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line.

### Option A: ADOPT the amendment's candidate unchanged — attestation fed by today's detection

- **Approach**: Lift the detection half from `issue/ISSUE-081-gate-evidence`, register
  `review/gate-evidence`, and have it emit a per-gate declaration slot naming each detected gate. A
  human reviewer fills each slot with the test that carries the refusal and the polarity it asserts.
  `REFUSAL_PATTERNS` and the direction predicate are untouched, honouring AC-4.
- **Pros**:
  - The gate list arrives mechanically rather than from the author's memory, which is the one
    structural difference SPEC-081 ever claimed over Option D.
  - Reuses a branch that already exists; no detection logic is re-authored.
- **Cons**:
  - M1: recall is 1 of 5. On 2 of 5 historical instances the human receives an **empty list**, which is
    byte-identical to Option A-of-SPEC-081 (prose, 0 of 4) — a mechanism that says nothing is not a
    mechanism.
  - On 2 of 5 more the list is non-empty but names a symbol other than the one that failed open, so a
    conscientious reviewer declares correctly about the wrong function and still ships the fail-open.
  - Review lesson 6: the declaration is an attestation and is forgeable. The issue's own
    Implementation Notes supply the self-test — *if a reviewer can satisfy a per-gate declaration
    without opening the named test, the successor is Option D*. On an empty list a reviewer satisfies
    it without opening anything.
  - M5: the ACs that would pin it (5, 6, 7) are unroutable without a 15341-line lift.
- **Trade-off**: +15341 insertions across +17 files to route AC-5/AC-6/AC-7, buying 1 of 5 historical
  recall and an empty declaration list on 2 of 5 instances — a measured improvement of +1 instance over
  Option A-of-SPEC-081's 0 of 4.

### Option B: ADOPT with detection widened to close the misses

- **Approach**: As Option A, plus enlarge the detection vocabulary so the three detection misses
  become detected, with the widening's own disarm-direction test through the real consumer.
- **Pros**:
  - Directly attacks the recall failure M1 measures, rather than shipping around it.
  - The 2026-10-31 amendment explicitly contemplates this path.
- **Cons**:
  - M2: the widening *is* an edit to `REFUSAL_PATTERNS`, because `detect_gates` reads that tuple to
    decide gate-hood. AC-4 requires those bytes unchanged. This option fails AC-4 by construction, and
    "widening detection" versus "re-tightening the predicate" is a distinction without a difference at
    this seam.
  - M3: the measured widening moves recall 1 of 5 → 2 of 5 while adding 51 whole-tree symbols that are
    loop-skip idioms in Figma/CSS extraction code.
  - M4: 2 of the 5 misses — refusal by omission, and a guard that is itself a test — cannot be reached
    by any pattern vocabulary at all. The ceiling is 3 of 5 and the path there is unmeasured.
- **Trade-off**: +1 historical instance detected (1 of 5 → 2 of 5) for +51 whole-tree gate symbols
  (101 → 152, a +50% longer declaration list) and 1 acceptance criterion failed by construction.

### Option C: DECLINE the disarm-direction property and record the limitation

- **Approach**: Record in SPEC-088 and in SPEC-081 that the disarm-**direction** property has no
  adopted successor and is not enforced by any shipped artifact; resolve SPEC-081's `ISSUE-088` Open
  Question with a pointer to this Decision; and state the measured re-opener that would overturn the
  decline. Ship no engine, no phase, no attestation surface.
- **Pros**:
  - It is the only outcome the measurements support. M1 plus review lesson 6 reduce the candidate to
    Option D (0 of 4) on 4 of 5 instances and to Option A (0 of 4) on the empty-list instances.
  - Removes the standing invitation to re-attempt a 15341-line lift whose own ACs it cannot satisfy.
  - Costs an ordinary PR nothing: no new blocking phase, no new review wall-time, no false-positive
    tax on any diff.
  - The property's absence becomes a written, dated, falsifiable record instead of a silently open
    carrier — which is what a SPEC exists to preserve.
- **Cons**:
  - The arm-only authoring shape stays uncaught by any mechanism. That is the exact shape measured in
    four consecutive sprints, and declining it means accepting a 5th occurrence is possible.
  - `review/gate-evidence` does not exist on main, so the decidable half SPEC-081 judged worth an exit
    code is also not shipped — this SPEC does not restore it and does not claim to.
  - A decline is only honest if it is re-openable; it depends entirely on the re-opener below being
    acted on, and no mechanism enforces that.
- **Trade-off**: +0 engine lines, +0 fixtures, +0 new blocking phases and +0 s added review time,
  against 0 of 5 historical instances caught — versus Option A's 1 of 5 at a cost of +15341 insertions.

### Option D: Defer again to a further carrier

- **Approach**: Record that the evidence is still incomplete and file a successor issue to decide
  later.
- **Pros**:
  - Zero artifacts written now.
- **Cons**:
  - ISSUE-088's AC-1 states in terms that a Decision deferring the choice to a further carrier **fails
    that AC**. This option is excluded by the issue, not merely disfavoured by it.
  - Review lesson 14: work added to satisfy a request for a decision ships without acceptance
    criteria, and that is where the defects are. A fifth deferral would carry none.
  - The predecessor already consumed 4 review cycles before being dropped; a further deferral spends
    that again with no new measurement in hand.
- **Trade-off**: +0 artifacts now and +1 further carrier, against 4 review cycles already spent and 1
  acceptance criterion failed by construction.

## Decision

**Chosen: Option C**

Decline the disarm-direction property. The line that tipped it is Option A's trade-off: **1 of 5
historical recall, with an empty declaration list on 2 of 5 instances, bought for +15341 insertions.**
The only structural claim ever made for the candidate successor is that the gate list arrives
mechanically rather than from the author's memory; M1 measures that the mechanical supply is *absent
exactly on the instances it was meant to cover*. On an empty list the reviewer obligation is
indistinguishable from SPEC-081's Option A (prose, 0 of 4), and on a wrong-symbol list it is
indistinguishable from Option D (checklist, 0 of 4) — the reviewer declares accurately about a function
that did not fail open. Option B's escape is closed twice over: M2 shows the widening is an edit to
`REFUSAL_PATTERNS` that AC-4 forbids, and M3 shows it buys +1 instance for +51 whole-tree false
entries. M4 shows 2 of the 5 misses are unreachable by any pattern vocabulary in principle. Option D
is excluded by AC-1.

**Recorded explicitly, because declining must not become unfalsifiable** — the **re-opener** for this
Decision, which is the symmetric obligation to the falsifier AC-2 asks of the ADOPT branch:

> If a detection mechanism is ever measured at **>= 4 of 5** on the five instances in M1 **without
> editing `REFUSAL_PATTERNS`, `_refusal_shaped` or the direction regex**, then the mechanical-supply
> claim becomes true in fact and ADOPT should be re-filed. Until that measurement exists, a successor
> is Option D with extra steps.

And the **falsifier recorded against the rejected ADOPT branch**, as AC-2 requires of it:

> ADOPT is Option D with extra steps if a reviewer can satisfy the per-gate declaration without
> opening the named test. M1 measures that this is not merely possible but *forced* on 2 of 5
> instances, where the list is empty and there is no named test to open.

**What this Decision does NOT do.** It does not re-tier anything: `BLOCKING_KINDS` does not exist on
main and this PR does not create it, so SPEC-081 decision 6 is untouched in both directions. It does
not re-tighten any predicate. It does not pre-empt ISSUE-084, ISSUE-085, ISSUE-086 or ISSUE-087 — if
any of them lands a detection half, the re-opener above is the measurement that should be run against
it.

### The AC audit this Decision owes, because four of ISSUE-088's seven ACs were written against a tree that does not exist

ISSUE-088's AC-4 through AC-7 were authored on the assumption that ISSUE-081 had landed. It did not.
Claiming them as met would be the defect this SPEC exists to avoid, so each is recorded with the
measurement showing its status:

- **AC-1 — met.** This Decision records exactly one of two outcomes (DECLINE) and records the unchosen
  ADOPT branch as Options A and B together with M1/M2/M3/M4/M5, the measurements that rejected them.
- **AC-2 — met in the form the DECLINE branch can meet it.** The ADOPT branch's falsifier is recorded
  above, as is the re-opener for the DECLINE.
- **AC-3 — partially vacuous, measured.** The occurrence count of any gate-evidence claim string across
  `skills/review/SKILL.md.tmpl`, the generated `skills/review/SKILL.md`, `agents/team-lead.md` and
  `scripts/verify_gate_evidence.py` is already **0** on main — two of the artifacts contain no such
  string and the fourth does not exist. **That 0 is produced by ISSUE-081's drop, not by any edit this
  PR makes.** A test asserting it would pass trivially and could never fail; this repo deflated exactly
  that manufactured-record pattern in commit `2a93d09`, and documentation-accuracy tests are issue
  generators. No such test is written, and this paragraph is the record instead. The limitation is
  written into SPEC-081 below. The **user-facing phase text half is unroutable**: there is no phase and
  no phase text, and inserting a sentence describing the limits of a gate that does not exist would
  itself be a false claim. It becomes live only if a future issue lands the phase.
- **AC-4 — vacuous, measured.** `scripts/verify_gate_evidence.py` does not exist on main, so
  `_refusal_shaped`, `REFUSAL_PATTERNS`, `_CONSUMER_RE` and `BLOCKING_KINDS` cannot be byte-changed by
  this PR. The AC's *intent* — this issue does not touch the rejected predicate or the tier split — is
  satisfied trivially and is stated here rather than asserted by a test that cannot fail.
- **AC-5 — unroutable.** `bash scripts/checkpoint.sh --skill review --phase gate-evidence --issue
  ISSUE-088` exits **2** with `ERROR: unknown phase 'gate-evidence' for skill 'review'`. No detector-
  shaped fixture can be driven through a consumer that does not exist. Needs an issue-level amendment.
- **AC-6 — not applicable.** It is explicitly ADOPT-branch-only, and the Decision is DECLINE. No
  gate-list hand-off is landed, so there is no new defence to disarm-test. Stated rather than silently
  skipped.
- **AC-7 — unroutable.** `tests/fixtures/gate_evidence/` does not exist on main; there are no fixtures
  to replay. Needs an issue-level amendment.
- **AC-8 — met.** SPEC-081's `ISSUE-088` Open Question is resolved below with a pointer to this
  Decision, `issues.md` carries the pointer, and every residual this SPEC leaves open carries a named
  carrier in Open Questions.

### The self-run, reported rather than required to hit a number

ISSUE-088 forbids stating the successor's self-application as a required output number, because
ISSUE-087 measured that doing so creates an incentive to write code the control cannot observe. So this
is reported, not targeted: running the retained branch's `analyze()` over **this PR's own committed
diff** reports **0 gates and 0 findings**. The explanation, which matters more than the number: this PR
adds one Markdown SPEC, one Markdown edit and one test module. `detect_gates` only ever looks inside an
added `def` in a changed **non-test** `.py` file, so a PR of this shape is invisible to it by
construction — the 0 is a property of the subject, not evidence about the mechanism. Reporting it
without that sentence would be the Goodhart failure ISSUE-087 recorded.

## Trade-offs Accepted

- **The arm-only authoring shape stays uncaught.** Four measured occurrences; a fifth is possible and
  nothing in this repo will stop it. This is deliberate, not an oversight.
- **The decidable half is not shipped either.** SPEC-081 judged "a gate with no attributed battery at
  all" worth an exit code. That half is decidable and does work, and this SPEC leaves it on an unmerged
  branch. Reviving it is a separate decision about a 268-line detection lift plus phase registration —
  carried in Open Questions, not smuggled in here.
- **A 15341-insertion branch is retained with no consumer.** It is kept because its measurements are
  the decision record, exactly as SPEC-081 is.
- **This Decision rests on 5 historical instances.** That is the whole measured population, and it is
  small. The re-opener is stated in instance-count terms so a larger population can overturn it.
- **No test pins the Decision's content.** The only test added drives `validate_spec.py`'s real
  `validate()` and CLI against the committed SPEC-088 in both the accept and reject directions. It pins
  that the Decision is *structurally* a decision — two or more options, measurable trade-offs, exactly
  one chosen option that is one of them. It does **not** pin that DECLINE is correct, and no test can.

## Migration

No code migrates; nothing is deployed, enabled or disabled. The steps are:

1. Write this SPEC at `docs/specs/SPEC-088.md`, `Status: accepted`.
2. Append a dated `## Decision 11` note to `docs/specs/SPEC-081.md` recording that the
   disarm-direction property is **declined**, not deferred, and that no shipped artifact enforces it.
3. Resolve SPEC-081's `ISSUE-088` Open Question entry in place with a pointer to this Decision.
4. Set `Spec: docs/specs/SPEC-088.md` on ISSUE-088 in `issues.md` (registry file, written on main under
   lock).
5. No change to `skills/review/SKILL.md.tmpl`, `agents/team-lead.md` or any script: the
   occurrence-count obligation is already satisfied at 0 and the phase text does not exist. Because no
   template changes, `python3 scripts/gen_skills.py` output is unchanged and
   `tests/test_gen_skills.py` cannot drift.

## Rollback

`git revert` the PR. The revert direction is safe in the only direction that matters: this PR adds no
gate, no exit code and no detection, so reverting cannot turn a FAIL into a PASS anywhere. What a
revert restores is a **worse record** — SPEC-081 carrying an unresolved Open Question that invites a
fifth attempt at a mechanism measured at 1 of 5 — which is the defect rather than a safe state. Prefer
amending this Decision over reverting it.

The signal that should trigger a rollback is precisely the re-opener in the Decision: a detection
mechanism measured at **>= 4 of 5** on M1's instances without editing `REFUSAL_PATTERNS`,
`_refusal_shaped` or the direction regex. Rollback takes one revert commit plus re-filing ADOPT as a
new issue; there is no state to migrate back.

A revert must not move any finding kind between tiers. `BLOCKING_KINDS` does not exist on main and this
PR does not introduce it, so a revert that changes a tier has reverted something other than this PR.

## Open Questions

Each is a residual this SPEC does **not** close, with a named durable carrier rather than prose —
review lesson 15.

- [ ] **Should the decidable half ship on its own?** The detection-only dependency closure is 23
      symbols / 268 definition lines, well inside a normal issue budget, but routing it needs a new
      `review/gate-evidence` phase and the four fixtures, and SPEC-081's own re-review measured the
      blocking half at 0 of 6. Deciding this is not deciding the direction property and must not be
      folded back into ISSUE-088 — owner: next sprint planner, by: file as a new issue before any
      future PR proposes lifting from `issue/ISSUE-081-gate-evidence`.
- [ ] **ISSUE-088's AC-5 and AC-7 are unroutable and AC-4 is vacuous on main** (measured in the AC audit
      above). They need an issue-level amendment rather than a silent claim of coverage — owner:
      orchestrator / team-lead, by: when ISSUE-088 is closed.
- [ ] **Is refusal-by-omission detectable by any instrument at all?** M4 argues it is not reachable by a
      pattern vocabulary, because a pattern matches an added line and omission adds none. Whether an
      AST- or dataflow-level instrument could reach it is unmeasured, and that question belongs with
      the detection-boundary owner, not here — owner: ISSUE-087, by: when its detection boundary is
      decided.
- [ ] **Does a guard that is itself a test deserve its own treatment?** Instance 5's `_grant_defects`
      lives in `tests/` and is excluded by `is_test_path` upstream of any vocabulary. Whether that
      exclusion is right is a detection-boundary question — owner: ISSUE-087, by: the same decision.
- [ ] **How will this DECLINE's own failure rate be measured?** The honest answer is by counting
      further occurrences of the arm-only fail-open shape, which is the same census SPEC-081 ran. It
      should be re-run and the count compared against the 4 recorded instances — owner: the reviewer who
      next records a "newly added defence fails OPEN" finding, by: at that finding's review.
- [ ] **Does retaining `issue/ISSUE-081-gate-evidence` indefinitely cost anything?** It is 15341
      insertions with no consumer. Keeping it is deliberate (its measurements are the record), but
      nothing schedules a re-decision — owner: next sprint planner, by: the sprint after this lands.
