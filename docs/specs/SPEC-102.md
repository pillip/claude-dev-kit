# SPEC-102: Bound the spec gate to PRESENCE — decline SPEC validity and proof of absence, and close the over-refusal class rather than bound it

> Linked Issue: ISSUE-102
> Status: `accepted`
> Date: 2026-11-07
> Author: claude-dev-kit (implement phase, dogfooding)

## Problem

ISSUE-102's defect is a satisfiability failure: the gate fired on a set of inputs for which no
reachable action by the actor it addresses could make it pass, because it resolved the remedy's
output in a location the remedy never writes to. That is fixed and measured — 16/16 matrix cells,
both call sites, both CWDs, sprint and non-sprint.

What is not settled is **what a `proceed` from the repaired gate is allowed to mean**. Two review
cycles produced two High findings, and both sit on the same question:

1. The gate establishes that a file *exists*. It never establishes that the file is a *SPEC*.
2. The gate establishes that a file *was not found in the checkouts it could enumerate*. It never
   establishes that the SPEC is *absent*.

A third review cycle that re-litigated the design would be the fourth consecutive cycle in which
new unspecified engine surface was added in answer to a request for a decision. ISSUE-079 exists
because ~49 unspecified engine lines shipped exactly that way, and **both** engine defects review
found lived in that unrequested code. So this SPEC decides, in writing, which properties the gate
has and which it is never going to be given — and it separates that question, cleanly, from the
one class of finding a declaration may never cover.

## Context

Every number below was re-measured on 2026-11-07 against the committed tree at
`issue/ISSUE-102-spec-gate-satisfiable` `5a285c7` and the merge-base `ce44206`. Nothing is quoted
from a prior review table; several prior numbers were wrong and are corrected here.

- **The gate's scope.** The lookup runs only when `Spec-Required=true`. The `hold`-by-signal,
  `bypassed` and signal-detection paths never reach it, so nothing in this SPEC touches them.
- **Live blast radius is zero, re-measured.** Across every `Spec-Required=true` issue in the real
  registry, driven from the main checkout and from the worktree, base `ce44206` and head agree on
  every decision: **53 decision pairs compared, 0 divergences** (27 issues from the main checkout +
  26 from the worktree; the main checkout carries `ISSUE-110`, which the worktree's frozen registry
  predates). Review 2 measured 26 x 2 = 52 pairs and 0 divergences; the count differs because the
  registry grew, the result does not. None of this fires on the repository today — it fires on the
  multi-checkout configurations this PR exists to introduce.
- **The suite delta is +63 executed cases and nothing else**, decomposed by node-id **set-diff**
  against a `git archive ce44206` baseline materialised into a scratchpad copy: baseline 2616
  collected, head 2679 collected, **+63 added, 0 removed, all in `tests/test_spec_gate.py`**. Of
  those, 44 landed in the two preceding cycles and **+19 are this rework's** (2660 → 2679).
  Review 2 reported its own delta as "+44 minus 18 on `tests/test_sprint_queue.py`"; that -18 was an
  artifact of comparing against the **main working checkout**, which carries 11
  `docs/sprint_state*.md` files (5 tracked + 6 untracked) against the archive's 5 — 6 extra files x
  3 parametrized tests at `tests/test_sprint_queue.py:1821`. Against a tracked-only baseline the
  confound disappears. For the same reason, team-lead's "main at `e42519a` collects 2634" is a
  main-*checkout* number; `git archive e42519a` collects **2616**, with a node-id set identical to
  `ce44206`'s.

### Finding 1 — `!r`-quoting does NOT close the marker-forgery channel

Review 2's rework set prescribed `!r`-quoting as the fix for the forged-`INCOMPLETE` channel. A
prescribed fix is a CLAIM until executed, so it was executed:

```
raw value        : docs/checkout enumeration INCOMPLETE (git could not be run) SPEC.md
MARK in raw      : True
repr()'d value   : 'docs/checkout enumeration INCOMPLETE (git could not be run) SPEC.md'
MARK in repr()'d : True
```

`repr()` escapes quotes, backslashes and non-printables. It does **not** escape plain substrings —
measured per class: backslash changed=True, newline changed=True, tab changed=True, NUL
changed=True, **marker substring changed=False**, bare quote changed=False (Python switches the
delimiter instead). A quoted marker is still a marker to a substring grep, and step 0c's read is a
substring grep. Quoting is retained in this PR for **legibility only**, and it is recorded here so
that no later reader re-derives it as the fix.

### Finding 2 — "main emits a fixed string and never embeds the value" is false as stated

The right finding was reached by the wrong mechanism, and both halves belong in the record.

`git show origin/main:scripts/spec_gate.py` line 123 already reads:

```python
reasons.append(f"Spec-Required=true and SPEC exists at {issue['spec_path']}")
```

That is a bare interpolation of the untrusted registry value, on main, today. What is new in this
PR is the line's **reachability**: on main the gate cannot return `proceed` for the issues it fires
on — that is ISSUE-102's entire premise — so the interpolation existed and was **dead code**. The
PR did not introduce the interpolation; it introduced the reachability, and it separately added the
control signal that made prose interpolation dangerous. "New in this PR" is true of the hazard and
false of the line.

### Finding 3 — there are THREE bare interpolation sites, not two

Review 2 counted two bare against two `!r`-quoted. Measured at `5a285c7`:

| site | string | pre-fix |
|---|---|---|
| `_spec_present_reason` legacy | `SPEC exists at {spec_path}` | **bare** |
| `_spec_present_reason` multi-checkout | `SPEC exists at {lookup['declared']}` | **bare** |
| `_spec_missing_reasons` absent | `SPEC declared at {lookup['declared']}` | **bare** |
| `_spec_missing_reasons` all-refused | `{lookup['declared']!r}` | quoted |
| `_spec_missing_reasons` some-refused | `{lookup['declared']!r}` | quoted |

Three, not two. The miscount matters because it is the same shape as the defect itself: a per-site
inventory of a class, short by one. This is why the neutralisation in this PR is applied at **one
derivation point** (`spec_lookup` returns a `reason_value` key) rather than at each call site. Per-
site application is the mechanism by which this class recurred at three successive layers.

### Finding 4 — the harmful direction of the forgery needs no suppression, and it is the reason High 2 could not be bounded

Review 2 recorded the harmful direction as undemonstrated. Demonstrated:

- Step 0c reads the marker **only on the non-`proceed` branch** (`skills/implement/SKILL.md:92`,
  under `decision: "auto_spec"`). On `proceed` (`:84`) the agent logs reasons and continues. So a
  forged marker on a `proceed` is **inert**, and no suppression is owed there.
- The harmful direction is a registry `Spec:` value carrying the marker **with the SPEC genuinely
  absent**. Executed, with git healthy and 2 checkouts enumerated COMPLETE and the SPEC absent from
  both: `decision = auto_spec`, and `reasons[0]` =
  `Spec-Required=true, SPEC declared at docs/checkout enumeration INCOMPLETE (git could not be run) SPEC.md but absent from all 2 checkout(s) consulted (...)`.
  The marker is present. Step 0c then reports an "unresolved environment problem (git unavailable
  or failing)" and is instructed **not to re-run `/spec` on the strength of it**.
- On the merge-base the same value yields the fixed string `Spec-Required=true, SPEC missing,
  sprint mode → auto-run /spec` with the value not embedded at all.

That is a genuinely missing SPEC **misrouted into an environment fault**, with the pipeline halted
while refusing the one remedy it demands. It is ISSUE-102's own defect shape — a trigger set
strictly larger than the satisfiable set — re-created through the output channel. **This is why
High 2 could not be bounded**: a declaration can license a false *pass* inside a stated boundary,
but this finding is a false *halt*, and no boundary statement makes a wedged pipeline acceptable.

### Finding 5 — why High 1 (the four I/O sites) was FIXED rather than bounded

Stated as a rule, not as a preference:

> Declaring a property out of scope licenses false **passes** within the declared boundary. It
> never licenses **blocking legitimate work**.

Each of the four sites raises an uncaught exception, which becomes a traceback at **exit 1** —
outside the module's own documented `{0, 2}` contract (`scripts/spec_gate.py` docstring, "Exit
code") — and step 0c has no branch for a traceback, so each one **wedges** `/implement` for a
legitimate repository. That is an over-refusal, so it is not bound-eligible. Measured, base
`ce44206` versus head `5a285c7`, each through the real step-0c CLI with a PREMISE assertion that
the kernel genuinely raises:

| site | trigger | premise | base | head (pre-fix) |
|---|---|---|---|---|
| A `_git` | only `git` on PATH is mode-644 / a directory / a non-ELF blob | `PermissionError` EACCES x2, `OSError` ENOEXEC | rc 0 | **rc 1 + traceback** |
| B `checkout_roots` | listed worktree under a non-searchable parent | `is_dir()` raised errno 13 | rc 0 | **rc 1 + traceback** |
| C `_contain` | symlink loop in a SIBLING checkout | `resolve()` raised `RuntimeError` | rc 0 | **rc 1 + traceback** |
| D `_spec_field_from_other_checkout` | unreadable sibling checkout directory | `is_file()` raised errno 13 | rc 0 | **rc 1 + traceback** |

Three of the four are strict regressions this PR introduced (base exits 0 on identical input).
Site A is measured on a **legacy co-located** fixture, because `spec_lookup` calls
`checkout_roots` unconditionally before it ever tries the read registry's own root — so it
regressed exactly the pre-ISSUE-102 caller class, which review lesson 8 governs. Site D raises
from **both** call sites: the CLI exits 1 and the in-process `decide()` API raises identically.

The ELOOP class was verified on this repo's supported interpreters rather than assumed: **3.11.13
→ `RuntimeError`, 3.12.7 → `RuntimeError`** (both CI versions, both escaping the pre-fix
`(OSError, ValueError)` tuple), **3.13.6 → does not raise at all**. The underlying kernel error is
`OSError errno 62 ELOOP`, which pathlib converts into `RuntimeError("Symlink loop from ...")` —
and `RuntimeError` is not an `OSError`.

And the **carrier option was declined** for this class specifically because **a class scoped to a
line is how this recurred**: review 1 scoped the class to one line, the rework fixed the LOCATION
of one stat and the COMPLETENESS of no exception tuple, and the three siblings are what review 2
returned. Sites B and D are precisely the guards review 1 mutated as `R2`/`R4`, saw survive, and
triaged as "unexercised guards".

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line.

### Option A: Give the gate both properties — validate SPEC contents and prove absence

- **Approach**: Invoke `validate_spec.py` on the resolved file before returning `proceed`, and
  replace `git worktree list` with an enumeration that can prove a SPEC absent from the repository
  (all refs, all checkouts, `git cat-file -e <branch>:<path>` per candidate).
- **Pros**:
  - A `proceed` would then mean what a careless reader already assumes it means.
  - It would close ISSUE-104's adjacent half in the same change.
- **Cons**:
  - Both halves **add refusals**, which is the one thing this rework may not do: a gate that
    refuses on an invalid SPEC and on an unprovable absence has a trigger set strictly larger than
    its satisfiable set again, which is ISSUE-102's own defect.
  - `validate_spec.py`'s own enforcement holes are explicitly **ISSUE-104's**, and ISSUE-102's
    Scope/Out forbids touching them.
  - Proof of absence is not reachable at all: `git worktree list` enumerates only checkouts of the
    containing repository, so a SPEC on an unfetched remote, in an unregistered clone, or in a
    stale-but-unlisted worktree cannot be seen by any amount of local work.
  - It is unspecified engine surface added in answer to a request for a decision — the ISSUE-079
    shape, which produced both of the engine defects this review found.
- **Trade-off**: +2 new refusal classes and an estimated +120 engine lines with no AC in this
  issue, against 0 of the 2 properties actually reachable (proof of absence is unreachable by
  construction) and +1 forbidden dependency on ISSUE-104's surface.

### Option B: Bound and declare — decline both properties in writing, close the over-refusal class, and put the bound in the gate's own output

- **Approach**: Declare in this SPEC that `proceed` means presence-only (D1) and that `absent` is
  not a proof of absence (D2). Close the four I/O over-refusals, because an over-refusal is never
  bound-eligible. Neutralise the forged control marker at the class level, from one derivation.
  Append one standing reason line to `proceed` stating the bound, so the gate's output stops
  claiming more than it does.
- **Pros**:
  - Every code hunk is either the deletion of a claim or a **de-refusal** — it strictly reduces the
    set of inputs the gate blocks. Nothing added can wedge a pipeline, which is the failure mode
    that recurred at three successive layers.
  - The two declined properties become a dated, falsifiable written record instead of an unstated
    assumption a reader supplies for themselves.
  - The disclosure travels with the verdict rather than living only in a document nobody re-reads
    at decision time.
  - It leaves the measured satisfiability fix — the issue's actual goal — untouched.
- **Cons**:
  - A `proceed` on an empty file, or on a stale SPEC in an unrelated leftover worktree, still
    happens. The gate says so now; it does not stop it.
  - An `absent` verdict can still be wrong where the enumeration silently skipped a root, and D2
    rather than a signal is what covers that.
  - Four residuals survive into carriers that a human, not a mechanism, has to file.
- **Trade-off**: +4 de-refusals and +1 standing disclosure line for +19 executed test cases and
  **-0** refusals added, against 2 properties declined outright and 4 residuals deferred to
  carriers.

### Option C: Bound the I/O class too — fix nothing now, declare everything

- **Approach**: As Option B, but also record the four I/O sites as an accepted limitation and leave
  them to a carrier, keeping this PR to the SPEC plus the marker fix.
- **Pros**:
  - Smallest possible diff; no engine behaviour changes at all beyond the already-landed
    satisfiability fix.
  - Consistent-looking: one decision, one document, everything else deferred.
- **Cons**:
  - It bounds an **over-refusal**, which Finding 5's rule forbids: three of the four sites are
    strict regressions this PR introduced, so the carrier would be a known, measured, newly-shipped
    way to wedge `/implement` on a legitimate repository.
  - Review 1 already took exactly this option for sites B and D under the label "unexercised
    guards", and review 2 returned them as fatal. The triage category quietly assumed the guard's
    absence was harmless.
  - A blocking gate outside its own documented exit contract is not a limitation, it is a defect.
- **Trade-off**: -4 de-refusals shipped (about -30 engine lines) in exchange for +3 known strict
  regressions left live and +1 repetition of a triage that was already measured wrong once.

### Option D: Defer the decision to a further carrier

- **Approach**: Record that the evidence is incomplete and file a successor issue to decide the
  two properties later.
- **Pros**:
  - Zero artifacts written now.
- **Cons**:
  - ISSUE-102 is at `review-rework` after two cycles; a third deferral spends a fourth cycle with
    no new measurement in hand.
  - Review lesson 14: work added to satisfy a request for a decision ships without acceptance
    criteria, and that is where the defects are. A deferral carries none.
  - It leaves the four over-refusals live for the duration, which Option C's cons already price.
- **Trade-off**: +0 artifacts now and +1 further carrier, against 2 review cycles already spent and
  +3 strict regressions left live for an unbounded period.

## Decision

**Chosen: Option B**

Bound and declare. Option A is excluded because both of its halves add refusals and one of them is
unreachable by construction; Option C is excluded by Finding 5's rule, which this SPEC treats as
load-bearing rather than stylistic; Option D is excluded by the cycle count. The line that decides
it is the asymmetry the three preceding layers kept missing: **a declaration can license a false
pass inside a stated boundary, and it can never license blocking legitimate work.** So the two
properties that would have to be *added* are declined in writing, and the four refusals that were
*accidentally added* are removed.

### D1 — SPEC validity is DECLINED

`proceed` means exactly this, and nothing more:

> A **regular file exists** at the declared relative path, inside the containment boundary of **some
> enumerated checkout** of the containing repository.

It does **not** mean the file is a valid SPEC. **This gate never invokes `validate_spec.py`.** An
empty file satisfies it — measured, and pinned by a test that writes a zero-byte file and asserts
both the `proceed` and the disclosure.

What a `proceed` verdict now licenses a reader to conclude:

- `/spec` (or something) left a regular file where the registry says the SPEC is.
- Therefore step 0c's STOP must not fire, which is ISSUE-102's goal.

What it does **not** license:

- That the file is a SPEC, that it has a Decision, that it has two options, that it parses, or that
  it is non-empty.
- That *this issue's branch* produced it. A leftover worktree holding an old SPEC at the same path
  satisfies the gate — pinned by `TestDisclosedResidual`. File existence is a weak attestation, not
  provenance (review lesson 6).
- That the SPEC is the one the `Spec:` field on main refers to in any sense beyond the path string.

Gate-side content validation is **ISSUE-104's adjacent half** and is carried in Open Questions, not
smuggled in here. The bound is additionally emitted in the gate's own `reasons` on every
`proceed`, as its own list element, so the existing reason strings stay byte-identical and the
co-located caller class keeps its pinned contract (review lesson 8).

### D2 — proof of absence is DECLINED

`auto_spec` / `hold` means exactly this:

> The declared path held no regular file in **the checkouts that could be enumerated**.

The existing `INCOMPLETE` marker already separates *could-not-compute* from *computed-and-empty*.
D2 adds the harder half: an `absent` verdict is **not a proof of absence even when the enumeration
reports COMPLETE**. Named concretely, because a vague disclosure is worse than none:

1. **`git worktree list` only enumerates checkouts of the containing repository.** A SPEC in an
   unregistered clone, on an unfetched remote, or in a worktree of a different repository is
   invisible, and the enumeration still reports COMPLETE. No trunk or branch name is resolved
   anywhere in this gate (ISSUE-089 has no foothold), which also means no ref is ever consulted.
2. **A listed path that cannot be statted is skipped silently.** This is new in this PR, by
   decision. `git worktree list` still prints the `worktree <path>` record for a checkout whose
   parent was later made non-searchable; `Path.is_dir()` then raises EACCES. That path is now
   **skipped**, exactly as a non-directory is, and the enumeration is **not** marked INCOMPLETE —
   because marking it would add a refusal and break this PR's governing invariant. A test pins the
   silence as deliberate rather than accidental. D2 is the disclosure that pays for it.

The architecturally right fix for the first-class version of this — a structured field instead of a
marker greppable out of prose — is Open Question 1. It is a contract change across script, skill
and `gen_skills.py`, and it has no AC in this issue.

## Trade-offs Accepted

- **An empty or invalid file at the declared path yields `proceed`.** Deliberate, declared in D1,
  pinned by a test, and emitted in the gate's own output. The gate is a satisfiability check, not a
  SPEC validator.
- **An `absent` verdict is not a proof of absence, even when COMPLETE.** Deliberate, declared in D2
  with both concrete mechanisms named. The silent skip of an unstattable listed root is the price
  of not adding a refusal, and it is paid knowingly.
- **`!r`-quoting is retained although it closes nothing.** It is legibility only — Finding 1
  measured the marker surviving `repr()` intact. The neutralisation is what closes the channel. The
  quoting change to the legacy present-reason is the one place this PR alters a pre-existing reason
  string's bytes; it is safe because `git show origin/main:tests/test_spec_gate.py | grep 'SPEC
  exists at'` returns **nothing**, so the full-dict pin being re-captured is this PR's own and no
  contract inherited from main is relaxed.
- **The forged-marker channel is closed by redaction, not refusal.** A value carrying the marker is
  still accepted and still decides; only its *rendering* is neutralised. Refusing such a value
  would add a refusal.
- **This PR's own Over-Engineering note recommends deleting the `:258` `is_file()` guard, and that
  recommendation is DECLINED.** The note argued the guard is redundant with the `except OSError`
  three lines below, citing surviving mutant `R4`. Re-measured here rather than inherited:
  `except OSError` does not cover a non-regular file that **opens successfully**, so with a FIFO
  planted at a sibling checkout's `issues.md` the as-shipped gate returns **rc 0 / `auto_spec`**
  while the guard-deleted variant **HUNG until killed** — the rc=124 shape. Nothing bounds
  `parse_issue`; `GIT_QUERY_TIMEOUT` covers only `_git`. `R4` survived because no test covered
  non-regular files, which is the opposite of the conclusion drawn from its survival. A minimality
  recommendation that would reinstate a known hazard class is refused, and the correct edit at that
  line was to move the stat **inside** the guard — which is what site D does.
- **The reasons still embed absolute checkout paths**, and the disclosure is now proportional to
  checkout count. Unchanged by this PR and not addressed by it.
- **No test pins that D1 and D2 are the *right* decisions.** The tests pin that the gate behaves as
  declared and that the declaration is structurally a decision. Whether declining is correct is not
  testable, and this SPEC does not pretend otherwise.

## Migration

No data migrates and nothing is enabled or disabled. The steps, all inside this PR:

1. Write this SPEC at `docs/specs/SPEC-102.md`, `Status: accepted`.
2. `scripts/spec_gate.py`: widen `_git` to `OSError`; guard `checkout_roots`' `is_dir()` and skip
   an unstattable listed path; add `RuntimeError` to `_contain`'s tuple and correct its docstring's
   ELOOP silence; move `_spec_field_from_other_checkout`'s `is_file()` inside the existing guard.
3. `scripts/spec_gate.py`: add `_redact_marker` plus `MARKER_REDACTION`, and derive `reason_value`
   **once** in `spec_lookup` so every value-derived reason inherits the neutralisation. The
   derivation is structurally upstream of the `if lookup["incomplete"]:` append, which is what
   keeps the genuine signal intact; an ordering test pins the position, not merely the presence.
4. `scripts/spec_gate.py`: add `PRESENCE_ONLY_NOTICE` and append it, as its own element, to the
   `Spec-Required` `proceed` branch only.
5. `tests/test_spec_gate.py`: +19 executed cases; re-capture `_PREFIX_RESULTS["colocated_proceed"]`
   (this PR's own pin) for the quoting and the additive notice.
6. **No template changes.** `skills/implement/SKILL.md.tmpl` is untouched, so
   `python3 scripts/gen_skills.py` leaves `git status --porcelain` empty — confirmed by running it.
7. **No registry edit.** `issues.md`, `CHANGELOG.md` and `docs/sprint_state.md` are team-lead's
   under `scripts/registry_edit.sh`; `Spec: docs/specs/SPEC-102.md` and any `Status:` transition
   are owed to that process, not to this diff.

## Rollback

`git revert` the PR. The revert direction is safe in the direction that matters for a gate: every
hunk here is a de-refusal or the deletion of a claim, so reverting cannot turn a refusal into a
pass. It can only turn passes back into refusals.

What a revert actually restores is **worse than the current state**, in three measured ways, which
is why amending is preferred to reverting:

1. The four over-refusals come back, three of them strict regressions against `ce44206`, each
   exiting 1 with a traceback outside the module's documented `{0, 2}` contract.
2. The forged-`INCOMPLETE` channel re-opens, misrouting a genuinely missing SPEC into a fabricated
   environment fault while step 0c is instructed not to re-run `/spec`.
3. The gate resumes emitting a `proceed` that states no bound, which is the false-assurance shape
   this SPEC exists to remove.

A revert must not change any decision for any issue in the live registry: base and head agree on
all **53** measured decision pairs, so a revert that moves a decision has reverted something other
than this PR. The signal that should trigger a rollback is a measured `proceed` that a reader acted
on *because* they believed the SPEC had been validated — which is the failure D1's standing reason
line exists to prevent, and whose recurrence would mean the disclosure is not read where it is
printed.

## Open Questions

Each is a residual this SPEC does **not** close. Carrier ids are **not allocated here** — team-lead
files them in one batch — so each names its owner and the filing occasion instead, and describes the
carrier's content precisely. A PR body is not a durable carrier, and `docs/sprint_state.md` is
archived at each sprint boundary, so it is not one either (review lesson 15).

- [ ] **Give the `INCOMPLETE` signal a structured field, so no consumer greps a control signal out
      of human-readable prose.** This is the architecturally right fix for the whole class this
      SPEC only neutralises: `spec_lookup` already computes `incomplete`, so it should surface as an
      explicit result key that step 0c reads, retiring the grep at
      `skills/implement/SKILL.md:92`. It also closes the unpinned cross-file marker contract —
      mutant `S1` (drift the constant while the skill keeps the old phrase) **SURVIVES**, measured
      on this tree. It is a contract change across `scripts/spec_gate.py`,
      `skills/implement/SKILL.md.tmpl` and `scripts/gen_skills.py`, with no AC in this issue —
      owner: team-lead, by: batched carrier filing after this ships.
- [ ] **The review-lesson-12 ordering pin for step 0c is UNHELD.** Measured as mutant `N9`: in both
      `skills/implement/SKILL.md` and its `.tmpl`, hoisting the "re-run `python3
      scripts/spec_gate.py`" bullet above the "Pass the issue id: `/spec $ARGUMENTS`." bullet leaves
      the suite **green**. In that order the gate is re-run before `/spec` has written anything,
      returns `auto_spec`, and step 0c's STOP — the instruction this PR rewrote to stop firing —
      fires on every `Spec-Required` sprint issue, restoring the defect the PR exists to remove.
      `TestImplementStep0cStopInstruction` is an occurrence-whitelist that pins presence and not
      position. The carrier should add one assertion per file: `text.index("Pass the issue id:
      \`/spec $ARGUMENTS\`.") < text.index("re-run \`python3 scripts/spec_gate.py")`, at a cost of
      +2 executed cases. Not taken here because it is a step-0c ordering property rather than one of
      this rework's hunks — owner: team-lead, by: batched carrier filing after this ships.
- [ ] **Gate-side SPEC content validation — ISSUE-104's adjacent half.** D1 declines it for this
      gate. The open question is whether `proceed` should ever depend on `validate_spec.py`'s
      verdict, and it cannot be answered without ISSUE-104's enforcement holes being closed first,
      since gating on a validator that passes an empty Decision would buy nothing. Note the
      measured asymmetry the carrier must respect: CI runs `validate_spec.py docs/specs/` **without
      `--strict`**, and `main()` ends with `return 1 if args.strict or target.is_file() else 0`, so
      a directory target exits **0 even with violations** — owner: team-lead, by: batched carrier
      filing after this ships.
- [ ] **The remaining triaged mutation survivors, as unexercised-guard pins:** `R2, R4, R5, R9, A1,
      N8, N10` from the preceding cycles' batteries. Recorded with review 2's lesson attached,
      because the lesson is the point: the triage category **"unexercised guard" quietly assumed the
      guard's absence was harmless**, and `R2`/`R4` turned out to be **fatal** on input the widened
      enumeration newly reached — they are sites B and D of Finding 5. A surviving mutant on a guard
      is evidence about the tests, not about the guard. This cycle's own battery is published in
      full below rather than triaged, and its 2 non-carried survivors are named with the reason each
      was left alive — owner: team-lead, by: batched carrier filing after this ships.

### This cycle's mutation battery, reported as a set rather than a count

A matrix is only as strong as its mutant set: review 2's 25-mutant battery found 2 survivors where
a previous 8-mutant matrix claimed zero. So the set is published. **25 mutants, 21 KILLED, 4
SURVIVED**, every probe run on scratchpad copies and never by editing the worktree.

Killed (21): `R1` `_git` tuple reverted; `R2` `_git` tuple drops `FileNotFoundError`; `R3`
`checkout_roots` guard removed; `R4` `_contain` tuple reverted; `R5` `_contain` tuple drops
`ValueError`; `R6` site-D stat moved back outside the guard; `R7` site-D guard deleted entirely —
the FIFO hang, killed only after this cycle added an `os.mkfifo` pin; `M1` `_redact_marker` no-op;
`M2` neutralisation relocated below the genuine append (the ordering pin); `M3` redaction applied
to the PATH value, so a redaction would move a decision; `M4` and `M4b` neutralisation dropped from
the legacy and the multi-checkout present reason respectively; `M5` `MARKER_REDACTION` itself
contains the marker; `M6` neutralisation dropped from the missing reasons; `N1` notice append
removed; `N2` notice folded into the present reason; `N3` notice added to a non-SPEC `proceed`;
`N4` notice drops its SPEC-102 citation; `X1` lookup reverted to `roots[0]` only; `X2` `_contain`
accepts any existing path; `X3` sibling field read drops id-scoping.

Survived (4), each with the reason it was left alive:

- `M3b` — redacting the **returned** `declared` key. An **equivalent mutant**: path resolution reads
  the local variable rather than the dict key, and `_declares_spec` answers the same for a redacted
  value, so no behaviour changes. Recorded rather than counted against the suite. Worth noting
  against this cycle's own method: the first version of `M3` was this same no-op and was briefly
  misread as a test gap; the real mutant (redact at the resolution call) is in the killed list.
- `N5` — the notice minus its "an empty file satisfies it" clause. Left alive **by choice**: the
  citation is pinned (`N4` dies), so a reader always reaches the full bound, and pinning the
  sentence itself would be a phrasing pin on a constant, which this repo deflates rather than adds.
- `S1` — Open Question 1 above. Re-measured against the **full** suite with an unmutated control
  copy, so that copy artifacts are not misread as kills: control and mutant both **4 failed / 2674
  passed, 0 new failures**. The 4 control failures are git-dependent tests failing only because the
  scratchpad copy carries no `.git`.
- `N9` — Open Question 2 above, measured the same way: **0 new failures against control**.
