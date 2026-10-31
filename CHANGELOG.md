# Changelog

All notable changes to claude-dev-kit. Versions are the plugin `version` field;
release tags are `claude-dev-kit--v<version>`.

## Unreleased

### Decided
- **The disarm-DIRECTION obligation is DECLINED, not deferred again** (ISSUE-088,
  PR #145) — `docs/specs/SPEC-088.md` lands at `Status: accepted` recording
  **DECLINE** for the property that `review/gate-evidence` was built to enforce.
  Its predecessor ISSUE-081 consumed four review cycles and was dropped unmerged;
  this closes the question rather than passing it on, which the issue's own AC-1
  required. **No engine surface changed — zero files under `scripts/`.**

  The measurements that decided it, re-derived rather than quoted: detection
  recall is **1 of 5** against the symbol that actually failed open, so a
  mechanism handing a reviewer the gates a PR adds would present an empty list on
  most historical cases — the 0-of-4 failure of an unassisted prose obligation
  wearing a mechanical badge. `detect_gates` iterates `REFUSAL_PATTERNS` directly
  to decide gate-hood, so "widen detection" and "leave `REFUSAL_PATTERNS`
  byte-unchanged" are **the same bytes**; a widening was measured as a probe and
  rejected rather than landed, because adding `^\s*continue` moves whole-tree
  detected gates 101 → 152 and the +51 are loop-skip idioms, not gates. And
  refusal expressed by **omitting** a line is unreachable by any pattern
  vocabulary at all, since a pattern matches an added line and omission adds
  none — capping a vocabulary-only fix at 3 of 5.

  `docs/specs/SPEC-081.md` is updated in place to stop over-claiming what a
  widening would cost. Residuals carry named issues rather than roles:
  **ISSUE-100** (does the decidable half ship on its own, and does the retained
  15341-insertion branch survive), **ISSUE-101** (re-run the fail-open census, so
  the decline's own failure rate is measured rather than remembered), and
  ISSUE-087 for the three detection-boundary questions.

### Fixed
- Nothing — this release entry is a decision record, not a behaviour change.
  `tests/test_spec_088_decision_contract.py` pins the artifact as structurally a
  decision (≥2 options, each with a measurable comparator, exactly one chosen
  option among those declared) and is mutation-tested in both directions:
  **14 mutants, 13 killed, 1 deliberate negative control** covering the
  does-not-fire-on-honest-input direction.

### Added
- **Review execution context is decided once, with degradations reason-tagged**
  (ISSUE-066, PR #122) — new `scripts/review_context.py` replaces `/review`
  step 3.1's per-dimension `has_skill.py` probe-and-maybe-retry with a single
  `decide` call that resolves both dimensions at once and emits the decision.
  Degradations are now distinguishable: `capability-absent` (the runtime review
  skill genuinely does not exist) vs `context-unreachable` (it exists but no
  skill-invocation tool is present in this context — every /sprint review), so
  the skill stops burning an attempt-then-degrade detour per dimension per
  issue. `review_degraded_path_used` gains a `reason` payload field; pre-066
  lines without it stay valid legacy. An `emit` subcommand is the prose-side
  call site for the delegated events and the `inline-attempt-failed`
  degradation. Per-control equivalence of its hardened writer against the
  ISSUE-058 baseline was verified at review, with two controls *stronger*
  (all-string-value truncation rather than `detail`-only, and coercion inside
  the `try`). Bundled spec: `docs/specs/SPEC-066.md`.
  **Dormant landing — the primary path still does not execute inside /sprint,
  and SPEC-066's stated reason for that was WRONG.** The spec claimed a
  categorical runtime limitation; review established the conclusion is
  **confounded**: inside a Task sub-agent the *sub-agent's* `tools:`
  frontmatter wins over the skill's `allowed-tools`, and although
  `skills/review/SKILL.md` grants `SlashCommand`, neither `agents/reviewer.md`
  nor `agents/team-lead.md` grants `SlashCommand` or `Skill` — no kit agent
  does — while a general-purpose Task sub-agent with full tool access *does*
  receive a `Skill` tool listing both review skills. SPEC-066 measured the
  kit's own configuration, not the runtime; the correction is recorded in that
  spec's Open Questions. **ISSUE-072 is the activation trigger for this
  module** (verify the sub-agent skill-invocation row in
  `docs/cc_feature_matrix.md` first, per the ISSUE-014 rule, then grant on the
  review path) and is what closes this issue's AC-1, which ships unmet.
  **Ship-time reconciliations:** the `skills/review/SKILL.md{,.tmpl}` same-hunk
  conflict with ISSUE-067 was resolved in favour of the decide-once structure —
  ISSUE-067's three `kit_telemetry.py --script review` one-liners were dropped
  as superseded (its `brainstorm`/`bizanalysis` one-liners are untouched) — and
  the `kit_telemetry` adoption SPEC-066 assumed turned out not to be a one-body
  swap, so it is deferred to **ISSUE-075** and recorded in
  `docs/telemetry_schema.md`'s Emit-site inventory rather than left implied.
- **Shared telemetry emitter that announces every skip and fallback**
  (ISSUE-067, PR #123) — new `scripts/kit_telemetry.py` is the single home of
  the ISSUE-058 writer hardening (run-id whitelist, realpath containment
  checked *before* the `mkdir`, 512-char `payload["detail"]` truncation,
  4096-byte event cap, `O_NOFOLLOW` append) and replaces the per-script
  hand-rolled JSONL appenders. Python API
  `emit_event(event_type, payload=None, *, script_name, project_path=None, issue_id=None) -> bool`;
  CLI for skill-prompt call sites:
  `python3 scripts/kit_telemetry.py --script <name> --event <type> [--payload '<json>'] [--issue-id ISSUE-NNN] [--project-path <dir>]`
  (always exits 0 — telemetry is non-blocking). Every skip/fallback path now
  prints one `[kit-telemetry]` stdout line naming its reason, so "no signal"
  can no longer be read as "all clear": `KIT_RUN_ID` unset or failing the
  `[A-Za-z0-9_-]{1,64}` whitelist writes the event under the explicit
  `unattributed` run id with a top-level `run_id_fallback` field instead of
  dropping it silently, and containment refusal, a non-regular target, and the
  size cap each announce rather than no-op. `scripts/synthesize_gate_results.py`
  is migrated off its private appender; the `brainstorm` and `bizanalysis`
  skills' prompt call sites move to the CLI one-liner and their `allowed-tools`
  gained `Bash(python3 scripts/kit_telemetry.py *)` (both grant kit scripts
  per-script, so the new call sites previously matched no pattern). The
  emit-site audit is recorded in `docs/telemetry_schema.md`'s new
  **Emit-site inventory** section.
  **Known gaps carried by follow-ups, not closed here:** **ISSUE-070** — the
  containment check compares two values both derived from the caller-supplied
  root, so it is structurally unfalsifiable for a non-symlinked root; a FIFO
  planted at the predictable run path hangs `os.open`; and the docstring's
  "NEVER raises" is false (reproduced by closing stdout). **ISSUE-071** —
  `KIT_RUN_ID` has no producer anywhere in the kit, so the fallback
  announcement currently fires on *every* run, which makes the genuinely
  exceptional announcements background noise. See
  `docs/review_notes/ISSUE-067.md`.
- **Discovered issues enter the sprint queue's visibility automatically**
  (ISSUE-068, PR #121) — `scripts/sprint_queue.py next-action` auto-considers
  `issues.md` Board-registered `Status: backlog`, non-`Manual` issues that have
  **no row** in the `docs/sprint_state.md` Issue Progress table, so work
  registered mid-sprint can no longer be invisible to the loop. Scoping: an
  issue qualifies only if its numeric ID is strictly above the watermark (the
  max numeric ID among rostered `ISSUE-<digits>` cells); no rostered rows means
  no synthesis, preserving the legacy empty-table `DONE` path. New `next-action`
  JSON fields: `unrostered` (the surfaced IDs) and, when the action would
  otherwise be `DONE`, `stranded` plus an explicit warning appended to `reason`
  — a sprint cannot close silently over actionable Board work. With no such
  issues present the output is byte-identical to the previous behavior, and
  rostered rows keep table-only dependency resolution unchanged (the
  Board-resolved dependency loosening is scoped to synthesized rows only).
  Synthesized IDs are withheld from `implement_ready` while anything is
  in-flight, so discovery cannot pre-empt the `STUCK` escalation — a
  synthesized row rebuilds `attempts: "0"` every call, so that starvation would
  have had no terminating counter. Roster-ID parsing is deliberately bounded
  (`ISSUE-(\d{1,9})`): an unbounded `\d+` handed to `int()` raises an uncaught
  `ValueError` past CPython 3.11's `sys.int_max_str_digits` cap, which would
  replace the sprint engine's JSON with a traceback.
  **Known gap — ships with AC-1 and AC-3 unmet:** the watermark is re-derived
  from the *mutable* Issue Progress table while the queue orders
  `implement_ready` by priority rather than ID, so once a higher-ID discovered
  issue is rostered a lower-ID sibling drops below the new watermark and
  vanishes — no target, no `unrostered`, no `stranded`. Reproduced on this
  issue's own motivating 063/064/065 case (`next-action` returns a bare `DONE`).
  **ISSUE-069 carries AC-1 and AC-3**; see `docs/review_notes/ISSUE-068.md` and
  `docs/test_plan.md` GAP-068a/GAP-068b.

### Fixed

- **The telemetry fallback announcement is scarce again — the unset knob is
  recorded, not announced, and the stream finally has a named consumer**
  (ISSUE-071, PR #143) — the last unresolved High carried out of the ISSUE-067
  review. `KIT_RUN_ID` had **no producer anywhere in the kit**, so ISSUE-067's
  fallback announcement fired on **100% of runs**: every gate checkpoint in
  every project printed one `[kit-telemetry] fallback: KIT_RUN_ID unset …` line
  and appended to a file **no code read on any default path**. A line emitted on
  every run carries zero information, which defeated ISSUE-067's own Goal that
  "'no signal' can no longer be confused with 'all clear'" — that requires the
  signal be **scarce**.
  **Resolution (b), taken to zero lines.** An **unset** knob is the kit's
  default state, so it is now recorded only in the event body
  (`run_id_fallback`) and announced on **no stream at all**. An **invalid**
  value is a human misconfiguration — rare and actionable — so it keeps its
  single stdout line **naming the knob**. Exactly one announcement went quiet:
  an AST diff of announcement sites during review confirmed **12 before and 12
  after**, with one guard changed.
  **Resolution (a) was rejected on a mechanism fact, not a preference.** A
  `SessionStart` hook cannot export an env var into the agent's later Bash
  calls, so a producer would need a run-id **file** read as untrusted workspace
  input, two hook surfaces kept in sync, and — under an installed-plugin layout
  — new lifetime and containment contracts inside the *user's* project.
  Recorded as **GAP-071a**.
  **The stream now has a named consumer.** `scripts/trace_query.py summary`
  reads `.claude/runs/*.jsonl` on its default path and reports script events
  plus an `unattributed events` count, so the file the emitter writes is a file
  something reads. Written-path == read-path is pinned by **object identity**
  between the production constants, not a re-typed literal.
  Review verdict **PASS-with-fixes**, and the review found and fixed a **High**
  on the new reader: `print_summary` interpolated untrusted `session_id` /
  `event_type` **unescaped**, letting a crafted event forge a clean-looking
  aggregate (`unattributed events: 0` while the true count was **2**) with raw
  ANSI — reproduced end-to-end through the real emitter CLI. Per
  `CONTRIBUTING.md`'s Kept-Surface Criterion this is **bucket C (verification
  core)**. On `main` the suite goes **2464 → 2486 passing** with **1 skipped**
  (an unprivileged `mknod` of a character device); the +22 decomposes as 25 new
  ids against 3 renamed away, and the totals are measured on a working copy
  carrying untracked `docs/sprint_state.archive-*.md` files that three
  parametrized classes glob, so they are not a reproducible floor.
  **Known residuals, recorded rather than overstated.** `trace_query.py`'s
  **read** path still lacks the write path's node/symlink hardening — a planted
  FIFO hangs it; nothing auto-invokes it, so it wedges a terminal, not a gate —
  and the emitter and the consumer share the path **layout** constant but not
  the **root**, so worktree-emitted streams are not read by a default invocation
  from the main root. The team-lead is filing carriers for both.

- **The telemetry emitter's containment check can now fail, a planted FIFO can
  no longer hang a gate, and the "NEVER raises" contract is true rather than
  advertised** (ISSUE-070, PR #141) — the three defects carried out of the
  ISSUE-067 review, all in `scripts/kit_telemetry.py::emit_event`.
  **Containment is now falsifiable.** The check compared two values **both
  derived from the caller-supplied `project_path`**, so for a non-symlinked root
  it could not fail — appending into any existing writable directory worked
  (`~` and `~/.ssh` were demonstrated at ISSUE-067's review). The **scope
  decision is shape A**: `project_path` stops being the containment root. A new
  `_containment_root()` derives the root **independently** — the main git
  work-tree root of the process CWD, falling back to `CLAUDE_PROJECT_DIR`, then
  CWD — and an out-of-root `project_path` is refused with a **named reason**.
  ISSUE-067's AC-1 auto-create is **kept inside** that root and **dropped
  outside** it, which is the ISSUE-067-AC-1 vs ISSUE-058-containment tension
  this issue existed to decide.
  **A planted FIFO can no longer hang a gate.** Non-regular targets — FIFO,
  socket, device node, directory, multiply-linked file — are refused with a
  named reason instead of blocking `os.open` forever. A hang matters more than
  an exception here because `verify_checkpoint.py`'s wrapper catches exceptions
  but **not stalls**, so the old behaviour stalled a gate checkpoint rather than
  failing it. The anti-hang leg is `O_NONBLOCK` on the open; the anti-write leg
  is an `fstat` after it (`S_ISREG` plus `st_nlink == 1`). **New *test-harness*
  knob — `KIT_TELEMETRY_PROBE_TIMEOUT`** (default `20` seconds, read by
  `tests/test_kit_telemetry.py`, not by the emitter): it bounds the
  planted-FIFO probe subprocess and classifies a timeout as rc **124**, so a
  HANG is a distinct reported outcome rather than a silent wait or a merely
  different assertion.
  **The contract is now true rather than advertised.** The docstring's "NEVER
  raises" was false — closing stdout raised `ValueError` from the announcement
  itself. The catch set was widened and `_announce` now swallows a failed
  `print`, so **ISSUE-075 can adopt a *tested* promise** instead of an
  advertised one, which was the stated precondition for that migration.
  Review verdict **PASS-with-fixes**, and the review found and fixed a **High**:
  the independently-derived root was itself re-derivable, because
  `_main_repo_root` trusted a linked worktree's `.git` file and the `commondir`
  it points at — writable files *inside* the tree — so the hop is now anchored.
  Per `CONTRIBUTING.md`'s Kept-Surface Criterion this is **bucket C
  (verification core)**. `tests/test_kit_telemetry.py` goes 21 → 53 tests; the
  suite on `main` goes 2428 → 2464 passing with **1 skipped** (an unprivileged
  `mknod` of a character device). Both suite totals are measured on a working
  copy carrying five untracked `docs/sprint_state.archive-*.md` files that three
  parametrized tests glob; on tracked files alone the same run collects 2450.
  **Known residual, recorded rather than overstated — GAP-070e.** `O_NOFOLLOW`
  binds only the **final** path component and `fstat` validates **type**, not
  **location**, so swapping `<project>/.claude` for a directory symlink inside
  the check→open window still escapes containment. It was demonstrated during
  the review and is being filed as its own issue rather than left in a PR body.

- **A remote-only branch resolves to its remote tip in the worktree creator, or
  the creator refuses** (ISSUE-083, PR #139) — `scripts/worktree.sh`'s
  `cmd_create` consulted only `refs/heads/$branch`; when that ref was absent it
  ran `git branch "$branch" "$default_branch"`, never looking at
  `refs/remotes/origin/$branch` and never setting an upstream. Because the
  review phase's cleanup (`cmd_remove`) ends in an unconditional
  `git branch -D`, the **normal** path through a sprint produces exactly that
  state — a branch whose reviewed commits live only on the remote — and
  `wt_setup.sh` then reported success and printed a worktree path rooted on the
  **caller's HEAD** with **no upstream**. Observed first-hand during ISSUE-078's
  ship phase, pre-harm: a push from that worktree would have been a
  non-fast-forward against the reviewed commits (rejected in the benign case,
  destructive under `--force`), and any `git diff` run against it would have
  reported the PR's entire content as missing.
  Branch resolution is now a ladder — `refs/heads/$branch` →
  `refs/remotes/origin/$branch` → default base — that creates the local branch
  **at the remote tip with tracking set**, so HEAD and upstream are both correct
  in one step. When the remote cannot be consulted (offline, unauthenticated,
  `origin` absent, no such remote ref, consultation timed out) the creator
  **refuses** with a named `reason=` on stderr and a **non-zero exit** instead of
  silently re-rooting onto the caller's HEAD. Because the healthy output and the
  defeated output were previously byte-identical, `cmd_create` now announces
  which source supplied the branch — `source=local-ref` / `source=remote-tip` /
  `source=new-from-base` — and names a local/remote divergence with **both short
  shas** rather than resolving it quietly either way.
  **New env knob — `KIT_WORKTREE_FETCH_TIMEOUT`** (default `60`): wall-clock
  seconds allowed for each remote consultation, documented in `README.md` and in
  the `scripts/worktree.sh` header. When no `timeout`/`gtimeout` binary is
  present the script says so on stderr rather than letting the knob look
  effective.
  Review verdict **PASS-with-fixes**, one fix applied: **TC-083m**, pinning the
  remote-only create against a **stale** cached ref (live tip vs stale cache).
  Per `CONTRIBUTING.md`'s Kept-Surface Criterion this is **bucket C
  (verification core)**. `tests/test_worktree.py` goes 11 → 28 tests; the suite
  on `main` goes 2411 → 2428 passing.
  **Four follow-up carriers were filed alongside it rather than left in the PR
  body:** **ISSUE-091** (the ship path deletes neither branch ref — mandated by
  this issue's AC-6), **ISSUE-092** (what the resolver keys on — the ladder reads
  a cache artifact of one hard-coded remote; `Spec-Required`), **ISSUE-093** (the
  fail-closed path's own failure modes), and **ISSUE-094** (the hollow-test
  predicate fails `tests/conftest.py`, reddening a blocking implement gate).

- **The review path can reach the runtime review skills — the SPEC-019 primary
  path now actually executes from a sub-task, and the first delegated review has
  run** (ISSUE-072, PR #135) — no kit agent granted any skill-invocation tool, so
  `/review`'s primary path was unreachable from every `/sprint` review and the
  ~360-line SPEC-066 module landed dormant. SPEC-066 blamed a categorical runtime
  limitation. That is now **refuted by a live run**, not merely by a tool listing:
  a Task sub-agent *does* receive a `Skill` tool (listing bare, non-namespaced
  `code-review` / `security-review`), the sub-agent's `tools:` frontmatter **wins
  over** the invoked skill's `allowed-tools`, and the absence SPEC-066 measured was
  the kit's own configuration. This issue's own review then ran with
  `review_context.py decide` returning **`delegated` for both dimensions with an
  empty reason**, invoking both runtime skills — where every prior review in the
  sprint ran `degraded` / `context-unreachable`.
  Per the ISSUE-014 rule the **verified matrix row landed first**:
  `docs/cc_feature_matrix.md` row 10, Status **`partial`** — runtime capability
  CONFIRMED, whether a *kit agent's* grant MATERIALISES still **UNVERIFIED** — with
  its `Verified` cell naming its own probe build (CC **2.1.224**) rather than the
  file's older global floor, which is untouched. The row deliberately records the
  **negative** results too: `SlashCommand` is absent in every probed sub-agent
  context (not loaded and **not even deferred**), so `Skill` — not `SlashCommand` —
  is the grant token; `Glob`/`Grep` are granted in kit agents and provisioned in
  neither, i.e. **a grant does not imply provisioning**; and the grant does **not**
  re-enable the kit's own `disable-model-invocation` pipeline skills. It also keeps
  four mutually **contradictory** observations about `Glob`/`Grep` rather than
  averaging them, and states the conclusion that follows: *a sub-agent's narration
  of its own tool list is unreliable evidence; an observed tool-call outcome
  outranks a self-description.*
  **The grant alone would have been inert.** `scripts/review_context.py` and
  `/review` step 3.1 both asked the model whether **`SlashCommand`** was in its
  tool list — a token that does not exist in sub-task context — so `decide` would
  have answered `context-unreachable` forever while every file looked correct.
  Naming `Skill` at that call site is what makes the grant live. `SlashCommand` is
  deliberately **kept** in `skills/review/SKILL.md`'s `allowed-tools`, and step 3.1
  still accepts it where a context has one, because the main-session path was never
  probed. The grant is scoped to **`agents/team-lead.md` only**: review removed it
  from `agents/reviewer.md`, which never executes step 3.1 and therefore had no
  call site for it — a symmetry grant the issue's own hygiene clause forbids.
  **Known gaps, carried rather than hidden:** a granted-but-unprovisioned `Skill`
  produces a `degraded` / `context-unreachable` outcome **byte-identical** to the
  pre-grant state, and the telemetry that would record it is a silent no-op when
  `KIT_RUN_ID` is unset — so there is **no distinguishing signal**, recorded
  (GAP-072b) rather than fixed with an unnamed mechanism. The `skills:` frontmatter
  field was never probed against `tools: Skill` (GAP-072a), which matters because
  `tools: Skill` without `skills:` could provision a Skill tool with an **empty
  listing** — materialised but inert. A **live run from a kit agent served by the
  installed plugin** remains unverified, because the agent registry is frozen at
  session start and the installed plugin lags this repo; **ISSUE-082** carries that
  re-probe and the issue's AC-2 ships honestly unchecked.

- **A running sprint can no longer silently lose its roster boundary — the
  one-line deletion that re-opened autonomous dispatch is now refused**
  (ISSUE-078, PR #133) — ISSUE-069 pinned the boundary in
  `docs/sprint_state.md`'s `## Meta` and gated above-boundary dispatch on field
  **presence**, so every *corrupted* form of the field failed closed while the
  **absent** state stayed a deliberate fail-OPEN (its AC-6 backward-compatibility
  contract). Deleting one line from a file that every phase executor rewrites
  every iteration therefore re-opened autonomous dispatch of out-of-scope work
  all the way through to `gh pr merge`, and the only thing in the way was
  model-followed prose in the sprint skill's step 4d. A new leg of
  `scripts/sprint_queue.py validate` — `check_roster_boundary` plus the
  `sprint_status_is_running` arming predicate — now refuses a `Status: running`
  sprint_state carrying no **accepted** `Roster-Watermark`: `valid: false`, a
  machine-readable `roster_boundary` object naming the cause, and a distinct
  exit class `3` that `/sprint` treats as a hard stop even though exit 3 does
  print JSON. The carrier was chosen for **position** — step 4b's `next-action`
  runs before the 4d rewrite and step 4f's `validate` runs after, so 4f is the
  only gate between the mutation that can drop the field and the next dispatch
  decision — and `cmd_next_action`, `parse_roster_watermark` and
  `_meta_section_bounds` are byte-identical to the previous release, so
  ISSUE-069's AC-6 byte-identity pin holds and the *dispatch* gate's behaviour
  (including `KIT_SPRINT_DISPATCH_ABOVE_WATERMARK`) is unchanged. `validate`
  gains an optional `--issues` flag supplying the Board-range check, and now
  warns on stderr when it is omitted or unreadable instead of downgrading the
  verdict in silence.
  **The guard shipped once failing open on itself, and review caught it**: the
  arming predicate was scoped to the first exactly-`## Meta` window, so 22 of 23
  measured inputs disarmed it — exit 0 / `state: "not-running"` for files
  containing the literal line `- Status: running`, while `next-action` on the
  same bytes dispatched three out-of-scope issues. That is a *new false
  attestation* rather than a new dispatch, since before this change `validate`
  said nothing about the boundary at all. Fixed by scanning the document in the
  arming predicate only, at zero verdict change across every real
  `sprint_state*.md` file, the template and both fixtures; the field's
  acceptance window is deliberately left narrow, because widening it would
  loosen acceptance.
  **Two fail-open classes ship open and are carried by ISSUE-080** (with
  GAP-078h..p in `docs/test_plan.md`): an unrecognised `Status:` value still
  yields the `not-running` attestation — its fix invents a new `state` value
  that no ISSUE-078 criterion names — and a `## Meta` example inside a fenced
  code block, placed above a live field-less `## Meta`, yields a false
  **`accepted`** verdict naming a watermark the live block never declared. The
  fence-blind locator is inherited ISSUE-069 behaviour; the attestation built on
  top of it is what is new here. Operator docs were corrected to match: the
  README `KIT_SPRINT_DISPATCH_ABOVE_WATERMARK` bullet and
  `docs/troubleshooting.md` now scope the old "absent = fail-open" statement to
  the dispatch gate and bound the residual — inside a `/sprint` run the open
  gate survives at most one iteration, because a state file that is already
  field-less when 4b runs can still dispatch once before 4f halts the loop.

- **The registry-lock contract is satisfiable by the actor it names, so an
  `issues.md` write can no longer succeed without the lock** (ISSUE-074,
  PR #132) — `agents/team-lead.md` forbade itself every `issues.md` write and
  routed them all to the **planner**, whose `tools:` line carries no `Bash` —
  so the designated lock-taker could not invoke `flock_edit.sh` /
  `registry_edit.sh` at all. The contract resolved to a **silently unlocked
  write**: the planner reaches for `Edit`, the lock is never taken, the write
  **succeeds**, and nothing errors anywhere. That is the inverse of sibling
  ISSUE-072 and strictly harder to notice, because there is no failure to
  attribute — and concurrent `issues.md` writes can clobber each other in
  exactly the parallel-sprint scenario the kit is built for. The invariant
  restored: **every registry write either holds the lock or is impossible** —
  never "succeeds without it."
  The write now splits in two. The planner **prepares** an idempotent apply
  script (`agents/planner.md` Append Mode step 5) whose anchor guard must match
  **line-anchored** `^### ISSUE-NNN:` and must **announce its no-op on
  stderr**, because a silent skip is indistinguishable from a successful write;
  a Bash-capable caller — the invoking skill, or team-lead — **commits** it
  under the lock via
  `bash scripts/registry_edit.sh issues.md -- bash -c '<apply script>'`.
  The planner stays `Bash`-free on purpose: both wrappers execute their argv
  verbatim (`"$@"` in `scripts/flock_edit.sh`), so any prefix-scoped grant on
  them is arbitrary code execution wearing a narrow-looking prefix.
  Both contracts now mandate a **quoted heredoc** (`<<'KIT_EOF'` … `KIT_EOF`)
  for the payload: the previously prescribed bare `bash -c '…'` form breaks on
  an apostrophe — routine in issue titles and ACs — closing the argument early,
  dropping the heredoc delimiter, and appending a **truncated** block while
  holding the lock with no error raised, after which the truncated anchor
  satisfies the idempotence guard on every retry.
  `skills/issue/SKILL.md{,.tmpl}` gains **step 7c** so the handoff has a
  receiver. It had none — `grep -rn "apply script" skills/` returned 0, and
  batch-mode `/issue` still told the Bash-free planner to use `flock_edit.sh`,
  so under the new no-`Edit`-fallback rule it would have written **nothing**
  while step 10 reported the issues as created. The skill is the committing
  actor (it already holds bare `Bash`; no grant changed) and carries the
  rejection rule for a guardless apply script.
  `agents/developer.md`'s registry step now names the wrapper and forbids
  `Write`/`Edit`. The developer holds `Bash`, so the guard passed on
  **capability, not compliance**, while the file named no lock anywhere; and an
  `Edit` from a worktree is worse than merely unlocked — `registry_edit.sh`
  resolves the registry against the **main** repo root while the `Edit` hits
  the worktree copy the kit forbids committing, so the field updates are
  silently **lost**.
  The planner's single-writer exemption is gated on the **file's absence**
  rather than on the invoking skill, which excludes evidence-mode `/scan` of a
  brownfield repo: the old justification ("greenfield, so no concurrent
  writer") was false for that path and licensed a `Write`/`Edit`-only agent to
  overwrite a live 4,100-line registry with no lock. Its `STATUS.md` step is
  scoped to projects that already carry one, and never creates one.
  `tests/test_registry_lock_contract.py` derives both halves from the files —
  capability from each agent's parsed `tools:` line, responsibility from the
  audited instruction text — and pins whole **lines** rather than slices, so an
  escape clause appended to an audited line cannot pass; a duplicate
  frontmatter `tools:` key is refused, since YAML resolves a duplicate mapping
  key to the **last** occurrence while the oracle read the **first**.
  **Residuals, all carried:** GAP-074a was closed during review; GAP-074b..k
  plus `GAP-074-ruff` in `docs/test_plan.md` carry eleven open items, each also
  written up in `docs/review_notes/ISSUE-074.md`. The two that most want a
  follow-up: the guard still keys on **capability rather than compliance**
  (a `lock_named` assertion needs a per-occurrence operative/pointer
  classification first), and the `bash -c` payload is **unbounded** — the
  planner holds `Write`, so emitting the apply script to a file and committing
  `-- bash <script-path>` would bound it and remove the quoting hazard
  entirely.
- **The sprint roster boundary is pinned once at sprint start, and out-of-scope
  Board work is flagged instead of auto-dispatched** (ISSUE-069, PR #129) —
  `scripts/sprint_queue.py::augment_roster_from_board` re-derived
  `watermark = max(rostered_nums)` from the **mutable** `docs/sprint_state.md`
  Issue Progress table on *every* `next-action` call, while
  `compute_queues`/`choose_action` order `implement_ready` by **priority, not
  ID**. One mechanism, two High harms, both now closed. **Harm A — the control
  re-hid what it surfaced:** once a higher-ID discovered issue was rostered, a
  lower-ID sibling fell below the new watermark and vanished entirely — no
  target, no `unrostered`, no `stranded`. Replayed on ISSUE-068's own motivating
  case (063 + 065 rostered, 064 still `backlog` with its dependency Board-done),
  `next-action` returned a bare `DONE`. **Harm B — above-boundary backlog was
  auto-TARGETED, not merely flagged:** a sprint deliberately scoped on older debt
  pulled everything newer into `implement_ready` and drove it through
  implement → review → `gh pr merge`.
  The boundary now lives in the sprint_state `## Meta` block as
  `- Roster-Watermark: ISSUE-NNN`, written once at sprint creation (new field in
  `templates/sprint_state.md`; write instruction in `skills/sprint/SKILL.md.tmpl`
  step 1 — the skill is **AUTO-GENERATED**, so regenerate with
  `python3 scripts/gen_skills.py` and never hand-edit `skills/sprint/SKILL.md`).
  New `parse_roster_watermark(sprint_text, issues_meta) -> (num, rejection_detail,
  present)` reads it as **untrusted workspace input** — `ISSUE-[0-9]{1,9}`
  fullmatch (ASCII digits only; `\d` admitted Arabic-Indic, fullwidth and
  Devanagari lookalikes), range sanity with a floor of 1 and a ceiling clamped to
  `_MAX_PLAUSIBLE_BOARD_ID = 9999` so one inert `### ISSUE-999999999:` heading
  cannot forge a boundary above the whole Board, and refusal of duplicated,
  mis-cased, decorated, blockquoted, emphasis-wrapped, `+`-bulleted,
  NBSP/ZWSP-indented, outside-`## Meta` and U+2028-smuggled variants. Every
  refusal falls back to the legacy derivation, **names the refusing guard in
  `reason`**, and never crashes or silently empties `unrostered_ids` (the
  GAP-068h shape). An accepted pin is announced unconditionally with
  counter-evidence — `[roster-watermark: pinned at ISSUE-068 — 5 of 5 Board
  backlog issue(s) are above it]` — so `0 of 0` (a finished sprint) is
  distinguishable from `0 of 12` (a pin that silenced the control).
  Harm B is gated by a new opt-in knob, **`KIT_SPRINT_DISPATCH_ABOVE_WATERMARK`**
  — default OFF: above-boundary issues are surfaced in `unrostered`/`stranded`
  but withheld from `implement_ready`. Set `1`/`true`/`yes`/`on`
  (case-insensitive; everything else, including `0` and `false`, is fail-closed
  OFF) and they are dispatched **with the knob's literal name echoed in
  `reason`**, so a deliberately widened sprint is distinguishable from a runaway
  one in the sprint log. It is read at call time, not import time. The
  annotations report the gate's **outcome**, not its intention: `withheld_ids`
  records what was actually removed and the note is omitted entirely when the
  knob was not the lever holding anything back. The top-level JSON key set stays
  frozen at `{action, targets, reason, unrostered, stranded}` — no new key.
  With **no** `Roster-Watermark` line, behaviour is byte-identically the legacy
  `max(rostered_nums)` derivation plus one named fallback note (AC-6; verified at
  ship by differential against post-ISSUE-076 main over 8 no-field fixtures).
  `tests/test_sprint_queue.py` is untouched by this change, so ISSUE-068's
  TC-068d/TC-068i pins are provably unmodified; the 190 new tests live in
  `tests/test_sprint_queue_watermark.py` and are built on a **two-iteration
  replay harness** (invoke, apply the roster mutation to the on-disk fixture,
  invoke again) — the structural gap that let both harms ship, since every
  pre-existing test was a single invocation against a roster whose max was also
  the global max. Closes GAP-068a and GAP-068b, and GAP-068h incidentally.
  **This also closes ISSUE-068's unmet AC-1 and AC-3.**
  **Known fail-open, shipped deliberately and carried by follow-ups:** the
  dispatch gate keys on field **presence**, so every *corrupted* form of the
  field fails closed — but a **deleted** field does not. A sprint_state with no
  `Roster-Watermark` auto-targets above-boundary work exactly as before
  (re-measured at ship: pinned → `DONE`/`targets: []`, absent → `PIPELINE` on all
  five), and that state is reachable by removing one line from a file every phase
  executor rewrites. AC-6 mandates it and closing it would break ISSUE-068's
  tests, so it is documented as a fail-open in three operator-facing places
  rather than described as safe — the implement phase's prose had claimed the
  opposite and was corrected during review. Carrier: **ISSUE-078** (+ GAP-069a).
  Separately, `diagnose_carry_forward_gaps` (~22% of the engine diff, which only
  *explains* a carry-forward stall — the rostered-row dependency-contract
  relaxation was explicitly **declined** per review lesson 8, leaving TC-068d
  intact) is named by no AC, In, Out or Test, and both engine defects the review
  found lived in it; it shipped rather than being cut because deleting ~250 lines
  of green, provably inert code on a ship-last PR was the larger risk. Carrier:
  **ISSUE-079** (+ GAP-069b). Full evidence in `docs/review_notes/ISSUE-069.md`.
- **The sprint queue reads the Issue Progress table and nothing else — and
  refuses to dispatch off a roster it could not fully read** (ISSUE-076,
  PR #128) — `scripts/sprint_queue.py`'s `parse_sprint_table` scoped its capture
  with `## Issue Progress\s*\n(.*?)(?=\n## |\Z)`, which terminates only on an
  **h2**. A phase executor's `### Review outcomes` h3 subsection table therefore
  fell *inside* the capture and its rows were parsed as roster rows; because
  that table has 6 columns, `cells[4]` resolved to its "High unresolved" cell
  instead of "Phase". Live on 2026-10-11 this made
  `validate --action SHIP --targets ISSUE-066,ISSUE-067,ISSUE-068` report all
  three correctly-shipped issues as **stuck** with
  `Phase is '0 (6 medium, 8 low)'`, while the real rows all read
  `done | 1 | - | shipped`. The capture now ends at the table's own end — the
  first blank line after its contiguous pipe rows, or any ATX heading of any
  level, whichever comes first — and a row must have **exactly** 5 columns
  (`ROSTER_COLUMN_COUNT`) to be parsed, replacing a `len(cells) < 5` guard that
  admitted 6+ and index-read the wrong cell. The real 2026-10-11 file is frozen
  byte-identically as `tests/fixtures/sprint_state/`
  `issue_progress_with_h3_subsection.md` and replayed as the regression.
  **Shipped beyond the issue's stated Scope, deliberately — read this before
  trusting the parse:** the issue asked only for scoping, but tightening the
  parse made it fail **OPEN**, which is strictly worse than the false negative
  it fixes. A single invisible whitespace-only line, a prose note, or a
  `Last Error` cell containing an unescaped `|` silently **truncated or dropped**
  roster rows, and `augment_roster_from_board` then re-materialized each dropped
  row as fresh backlog work with `attempts` reset to `0` — so a finished issue
  was re-implemented from scratch and the >=3-attempt escalation could never
  fire (measured: main `SHIP ISSUE-200` exit 0 -> pre-fix branch
  `PIPELINE ISSUE-200` exit 0, empty stderr). The module's integrity guard only
  failed closed at **zero** rows, so a *partial* capture was structurally
  invisible. Two defences were therefore added in review: a new public
  `unparsed_roster_rows()` reporting both off-shape and truncated-away
  roster-shaped rows, with `cmd_next_action` now **refusing to dispatch
  (exit 2)** and `cmd_validate` warning on stderr without changing its verdict
  contract; and `_unfenced()` + `_FENCE_RE`, which blank fenced lines so a
  fenced `## Issue Progress` example can no longer win the section (one half of
  that was pre-existing on main, the other a regression this PR introduced).
  Zero false positives across all 6 real `docs/sprint_state*.md` files, the
  template and the frozen fixture; mutation-pinned in 6 directions.
  **Known residual, verified at ship:** an h3 heading sitting *between*
  `## Issue Progress` and the real roster table zeroes the whole roster
  (main parses 1 row, this engine 0). No real doc or template has that shape
  (7/7 checked at ship), and it fails **loud** — exit 2 via the zero-row
  diagnostic, re-measured at ship as main `SHIP ISSUE-100` exit 0 vs this engine
  exit 2 — but the terminator should derive from the matched heading's own level
  rather than from "any heading". Fixing it reverses an explicitly spec'd and
  tested Scope bullet, so it is a planner decision and is deliberately
  test-locked by `test_heading_before_any_table_yields_no_rows` meanwhile.
  Eight further Mediums/Lows are recorded in `docs/review_notes/ISSUE-076.md`
  and enumerated in this issue's registry entry rather than filed, including two
  pre-existing items the live incident also depended on (duplicate roster IDs
  are last-row-wins and unvalidated; `agents/team-lead.md` teaches a 4-column
  roster this 5-column reader discards).
- **The sprint queue validates a PR reference before handing it to `gh`**
  (ISSUE-073, PR #127) — `scripts/sprint_queue.py`'s `_gh_pr_merge_state` now
  refuses a non-conforming PR reference *before* invoking `gh`, and passes `--`
  ahead of the reference so a value can never be re-read as a flag:
  `["gh", "pr", "view", "--json", "state,mergedAt", "--", <ref>]`. The accepted
  forms are exactly the three the `issues.md` `PR:` field actually carries —
  `123`, `#123`, and `https://github.com/<owner>/<repo>/pull/123` — matched by
  `fullmatch` with bounded digit and path-segment runs. Anything option-shaped
  (`--repo attacker/evil`) or otherwise non-conforming returns *indeterminate*
  with a warning naming both the rejected value and the `PR:` field it was read
  from, and never raises, so the never-raises contract from ISSUE-052 is intact.
  The guard sits at the chokepoint **both** entry points share — the Board `PR:`
  field read by `classify_ship_ready`, and the model-chosen
  `ship-merge-decision --pr` CLI argument — so neither can reach `gh` unchecked.
  Before this, `PR: --repo attacker/evil` was consumed by `gh` as a flag and a
  `MERGED` answer from the attacker-chosen repo made the queue emit FINALIZE
  instead of SHIP. Refusal is fail-safe in a single direction: it degrades
  toward SHIP/`merge`, never toward FINALIZE/`skip`, so the real `gh pr merge`
  always surfaces the truth. The two live compound `PR:` values
  (`#108 https://…/pull/108` and the same shape for PR 122) are deliberately
  refused rather than normalized; `docs/troubleshooting.md` explains how to
  normalize a refused field and records that `scripts/verify_checkpoint.py`
  reads the same field more permissively.
  **Scope — read this before trusting the queue's MERGED verdict:** what ships
  here is validated **shape**, not **provenance**. A conforming but *wrong-target*
  reference still resolves to MERGED (`gh pr view … -- '#93'` returns
  `{"state":"MERGED"}` for any issue), so an unmerged PR can still be finalized
  as `shipped` through a mis-set `PR:` field, and `verify_checkpoint.py`'s ship
  gate passes on it too. That residual is a different defect class and is
  carried by **ISSUE-077** (binding the probe to the issue's own `Branch:` via
  `--json state,mergedAt,headRefName`, free in the same `gh` call), recorded as
  GAP-073a in `docs/test_plan.md`.

## 0.7.0 — 2026-10-10

The SPEC-055 repositioning release: the kit's surface is reorganized around
the verification & delegation control plane — deterministic sweep validators,
script checkpoints for every long-prose skill, the dormant test-execution
delegation layer with provenance binding, scaffolding deflation (agent roster
32 → 22), and the uiux triplet converted to contract + gates. All ten sprint
issues (ISSUE-056..065) shipped with zero unresolved Critical/High findings.

### Added
- **Deterministic sweep validators** (ISSUE-056, PR #101) — the four
  model-executed verification sweeps are promoted to scripts with exit codes:
  `scripts/verify_design_sweeps.py` (`literal-quote`, `signature-move`,
  `ai-tell` subcommands plus an `all` aggregate) and
  `scripts/verify_hollow_tests.py`. Ships with pinned, mutation-tested
  fixtures under `tests/fixtures/sweeps/` and the bundled spec
  `docs/specs/SPEC-056.md` (sprint auto_spec flow). SPEC-055 / evolution
  audit roadmap item 2.
- **Script checkpoints for the five zero-checkpoint skills** (ISSUE-057,
  PR #102) — `scripts/verify_checkpoint.py` gains 14 new phases (kickoff x5,
  scan x6 including a conditional data-model phase, desktop-uiux
  context/philosophy/system), every surviving CHECKPOINT block in
  kickoff/scan/uiux/mobile-uiux/desktop-uiux now invokes `checkpoint.sh`,
  and an `ISSUELESS_SKILLS` fail-closed guard rejects unknown skills.
  Ships with the bundled spec `docs/specs/SPEC-057.md` (sprint auto_spec
  flow). SPEC-055 / evolution audit roadmap item 2.
- **Dormant test-execution delegation layer** (ISSUE-058, PR #100) —
  `scripts/synthesize_gate_results.py` lands a probe + untrusted-artifact
  validation + a deterministic mapper to the `verify_gates.GateResult`
  contract, emitting telemetry events `gates_delegated_to_runtime` /
  `gates_degraded_path_used`. `verify_checkpoint.py::_run_verify_gates` gains
  a fail-safe consult with a byte-identical degraded fallback and an
  unconditional `GATES DELEGATED` stdout marker. Ships with
  `docs/telemetry_schema.md`, README env knobs (`KIT_GATE_RESULTS_FILE`,
  `KIT_RUN_ID`), and the bundled spec `docs/specs/SPEC-058.md`. The delegation
  branch lands DORMANT — no runtime capability sets the env var yet; the
  activation trigger is documented and ISSUE-065 gates activation on
  provenance binding. SPEC-055 roadmap item 4 / SPEC-019 follow-up.

- **Provenance / freshness / consume-once binding for the gate-delegation
  handoff** (ISSUE-065, PR #112) — closes the ISSUE-058 review's unresolved
  High finding: the `KIT_GATE_RESULTS_FILE` artifact is no longer a forgeable
  attestation. `scripts/synthesize_gate_results.py` gains a per-run ephemeral
  HMAC-SHA256 key (`secrets.token_bytes(32)`, in-process only — no new env
  knob), a `<artifact>.sig` sidecar verified via `hmac.compare_digest` (the
  sidecar is itself untrusted input: containment, regular-file, 1 KiB cap,
  hex whitelist), an mtime-vs-process-start freshness check, and consume-once
  semantics (successful delegated ingest renames the artifact to
  `<artifact>.consumed`, so byte-perfect replays refuse). Binding materials
  are required keyword-only parameters of `decide_gate_path`, so unbound
  wiring raises `TypeError`; every binding refusal degrades to running the
  real gates with telemetry reason `binding-rejected` and one loud stdout
  line. The delegated branch stays DORMANT — binding, not env-var presence,
  is now the activation precondition; the producer-side key handoff is owed
  by the activation PR (SPEC-058 Open Questions). 29 new tests in
  `tests/test_gate_binding.py`; `tests/test_gate_delegation.py` migrated to
  the bound API with both stdout pins untouched.

### Changed
- **Scan/greenfield sibling agents consolidated behind an evidence-mode
  flag** (ISSUE-061, PR #107) — all 5 pairs merge: requirement-analyst,
  qa-designer, architect, data-modeler, and planner absorb their scan twins
  (scan-analyst, scan-qa-designer, scan-architect, scan-data-modeler,
  scan-planner are deleted); roster 32 → 27. Each merged agent carries a
  gated `Evidence Mode (scan invocations only)` section activated solely by
  the literal `Mode: evidence` sentinel in the calling skill's own
  instruction text — `/scan` injects it on every Task prompt (including
  Phase 4 retries), agents never infer the mode from context, and `Mode:`
  lines inside passed document content are data, never the sentinel
  (injection guard). Golden-output fixtures under
  `tests/fixtures/evidence_mode/` pin both modes' section contracts
  (`tests/test_evidence_mode_consolidation.py`), and
  `scripts/verify_checkpoint.py` scan retry hints name the merged agents.
  Ships with the bundled spec `docs/specs/SPEC-061.md`. SPEC-055 /
  evolution audit roadmap item 5.

### Removed
- **Scaffolding residue — persona blocks, confidence-rating ritual, inline
  figma prompt** (ISSUE-059, PR #106) — deletes the four
  `Execution Principles (absorbed from the <persona> — ISSUE-034)` blocks
  (prd/diagnose/refactor/migrate) plus /diagnose's step 5.5 six-item cognitive
  checklist, removes the Self-Review confidence-rating (High/Med/Low)
  boilerplate from 18 agents (SPEC-010 recorded self-grading as a defect;
  documented exceptions: the uiux triplet and `scripts/fragments.py`
  `self_review_confidence`, both owned by ISSUE-060), and replaces
  /implement's ~50-line inline figma-converter prompt with a reference
  contract to `agents/figma-converter.md` (single source). Reintroduction is
  guarded by occurrence-whitelist lint tests in
  `tests/test_scaffolding_residue.py` (7 tests, RED-verified pre-deletion).
  SPEC-055 / evolution audit roadmap item 3a.

- **A-bucket conversational agents dissolved into their skill contracts**
  (ISSUE-062, PR #108) — deletes the five remaining conversation-shaping
  roster agents: brainstormer, business-analyst, devops, documenter, and
  copywriter; roster 27 → 22. Each agent's enforced invariants survive as
  contract lines in the calling skill (/brainstorm, /bizanalysis, /devops,
  /ship, and the uiux triplet). Where a skill used the agent for context
  isolation rather than expertise, the call survives as a separate-context
  general-purpose Task invocation with an inline contract and an explicit
  toolset restriction (Read/Glob/Grep/Write/Edit only — no Bash, no web):
  the documenter call in /ship step 3.5 and the copywriter call in
  uiux/mobile-uiux/desktop-uiux Phase 4.5. Agent absence and invariant
  absorption are pinned by `tests/test_agent_dissolution.py`. Ships with
  the bundled spec `docs/specs/SPEC-062.md`. SPEC-055 / evolution audit
  roadmap item 6.

### Fixed
- **verify_design_sweeps SPEC-056 contract conformance** (ISSUE-063, PR #111)
  — three `all`-mode deviations fixed behind golden pins: the flex-calc-width
  ai-tell now scans comment-blanked, whitespace-collapsed file text at
  declaration level (multi-line and comment-split declarations no longer
  evade; violations report the declaration's starting line), `all --json`
  emits exactly ONE top-level JSON object keyed by sweep (usage errors go to
  stderr so nothing interleaves with the JSON document), and `all` without
  `--class` fails closed with exit 2 naming the unenforceable signature-move
  sweep. Pinned by `tests/test_sweep_contract_conformance.py` (8 RED tests +
  6 golden pins; `all --class` text output byte-identical). SPEC-056
  contracts 3 and 5; ISSUE-056 review follow-up.
- **verify_design_sweeps matcher-edge hardening** (ISSUE-064, PR #115) —
  closes the five adjacent robustness findings from the ISSUE-056 review plus
  the ISSUE-063 review's HTML CSS-contexts Medium, all behind the post-063
  CLI/schema freeze (golden text/JSON pins byte-identical, no new flags):
  ai-tell matching HTML-entity-decodes (`html.unescape`) and case-folds
  before comparison so encoded/case-variant tells are caught; the bare
  `mock`-anywhere-in-name rule is dropped from `verify_hollow_tests.py`
  (dated SPEC-056 contract-4 amendment, not silent drift); the literal-quote
  validator blanks `<script>` bodies — including unterminated-to-EOF, a
  bypass found and fixed in review — and `data-*` attribute values so
  non-rendered quote placements no longer satisfy it; the ai-tell sweep
  fails on zero screen files regardless of CSS inputs (no vacuous
  half-pass); inputs are realpath-contained to the target tree (breach =
  exit 2 usage error on stderr, file never read); and the HTML
  declaration-level scan now blanks CSS comments inside `<style>` blocks
  and inline `style=""` attributes. 29 new tests in
  `tests/test_sweep_validators.py`; the
  `tests/test_sweep_contract_conformance.py` golden pins are untouched and
  passing. ISSUE-056/063 review follow-up.
- **Contract-converted uiux triplet** (ISSUE-060, PR #116) — the
  uiux/mobile-uiux/desktop-uiux skills and their developer agents shrink
  to contract + gates. Craft-tutorial prose (CSS mechanics lists,
  duration-band tables, Expo dependency pins, Electron perf prescriptions)
  is deleted; the shared surviving text (anti-slop trio, pilot-gate
  protocol, cross-document consistency contracts) now lives once as
  `scripts/fragments.py` tokens over the `UIUX_SKILLS` tuple instead of
  three near-verbatim copies; and the Phase 5.5 model-executed sweep
  instructions are replaced with `scripts/verify_design_sweeps.py`
  validator calls (web call site at terminal step 22.4, downstream of all
  content-mutating steps). Gate behaviour is the regression surface:
  parity fixtures pin that every gate passes/fails identically pre/post
  conversion (`tests/test_uiux_contract_conversion.py`). Ships with the
  bundled spec `docs/specs/SPEC-060.md`. SPEC-055 / evolution audit
  roadmap item 3b.

## 0.6.0 — 2026-09-02

Machinery deflation. Of ISSUE-036..054, 16 of 19 issues came from two
self-generators — a repo self-audit sweep and the sprint runner's own discovery
— and cost +4,456 net lines while adding no user-facing capability. This release
removes the layers that produced them and adds a gate so the pattern does not
regenerate, here or in any project the plugin is installed into.

### Removed
- **`review-merge-auditor` agent** (roster 33 → 32) — a separate-context LLM
  agent auditing the output of `synthesize_review_notes.py`. That synthesizer is
  deterministic (severity copied verbatim from the intermediate, findings never
  dropped) and covered by its own 16 unit tests, so the audit graded a mapping
  that cannot drift. Its `review/synthesis-audit` checkpoint phase was an alias
  for `review/review`; the structural gate on review notes is unchanged and
  still runs at step 5. (PR #92)
- **`/ship` step 8, the review-quality eval** — `scripts/eval_review.py` and
  `templates/review_eval_rubric.md`, an LLM-as-judge grading the review of a PR.
  Its own outputs (`docs/review_eval_*.md`) were never committed in eight runs.
  Removing it drops the `claude -p` subprocess from the ship path. (PR #92)
- **autotest hook cache + debounce** — reverted to the pre-cache hook. The
  optimization was never measured as needed and introduced a workspace-writable
  index that had to be validated as untrusted input on every read. The hook's
  behavior is otherwise identical. (ISSUE-038 reverted, PR #92)
- **Document-consistency tests and the facts they policed.** The README stated
  its agent count in four places and its test count in a badge; every roster
  change drifted them and each drift failed the build while nothing was broken
  for a user. The counts and badge are gone, and with them
  `test_stated_agent_counts_match_roster`,
  `test_readme_count_matches_effort_test_roster` (which regex-parsed another
  test file's source to compare a pinned number against prose),
  `TestRosterSurfaces`, `tests/test_env_knob_docs.py` (ISSUE-053), and the
  ISSUE-050 agents-table-vs-frontmatter linter. The env-knob **documentation**
  stays; only the test policing it is gone. `test_agent_effort.py`'s roster pin
  is now a non-empty guard against vacuous per-agent passes. (PR #92)

### Added
- **`record` tag on the review minimality axis** (`agents/reviewer.md`) — flags
  a test whose assertions land on document text (README, docs, agent or skill
  markdown, a changelog) rather than on the result of executing code. The
  prescribed fix is never a better linter: generate the derived fact from its
  source, or delete the sentence that states it, and drop the guard with it.
  Explicitly excludes documents the product consumes at runtime (config, schema,
  prompt templates) and non-empty/fixture-pin guards. (PR #92)
- **User-impact gate before issue creation** (`agents/team-lead.md`, Review
  Artifact Triage step 5c) — for each candidate finding: *if this is never
  fixed, what breaks for someone using this project?* When the only answer is
  that a document disagrees with the code, the finding is logged in
  `sprint_state.md` as `not-filed: record-only` instead of becoming a backlog
  item. Previously every unresolved Critical/High finding was filed
  unconditionally. (PR #92)
- **Learning-loop guard** (`/review` step 5.5) — the loop may no longer store a
  lesson that teaches a better document guard; such a lesson widens what every
  future review checks. Three of this repo's six accumulated lessons were
  exactly that. (PR #92)

### Fixed
- **`team-lead` lessons escalation keyed on a field that no longer exists.** The
  rule escalated any lesson with `Frequency >= 3`, but ISSUE-033 moved lessons
  to Claude Code native memory, which stores one fact per entry updated in place
  and carries no Frequency counter — the string appears zero times in the store,
  so the rule could never match. Recurrence is now read from the observed-issues
  list inside the entry. (PR #92)

### Notes
- Suite: 1424 → 1385 tests, runtime ~35s → ~21s, coverage 82.69%.
- The three additions are model-followed prompt rules, not script-enforced
  gates. No test accompanies them by design: asserting that a phrase appears in
  an agent markdown file is precisely the `record` class being introduced.

## 0.5.0 — 2026-08-17

Brownfield design support. The three uiux skills could only ever *create* a
design; they can now *read* the one a codebase already ships and extend it.

### Added
- **`extend` mode across `/uiux`, `/mobile-uiux`, and `/desktop-uiux`.** Each
  skill globbed existing UI files at Phase 1 and then discarded the reading —
  Phase 2 unconditionally committed to a new aesthetic and the pilot gate
  stamped a new Signature Move onto every screen. A project with a shipping UI
  and no Figma file had no path to "read the design that exists, then add
  screens that match", and running the skill anyway fought the codebase because
  existing patterns matching a listed AI Tell got swept out at Phase 5.5.
  Detection now proposes a mode and the user decides; modes never switch
  silently, and with no UI detected the `create` path is unchanged.
  (ISSUE-054, SPEC-054, PR #89)
- **`design-scanner` agent** (roster 32 → 33) — one platform-parameterized
  extraction agent, read-only by tool set (`Read, Glob, Grep`), carrying three
  source maps over one shared method: web CSS custom properties /
  `tailwind.config.*` / CSS-in-JS, React Native `StyleSheet` + `src/theme/`,
  and Electron renderer CSS + `src/theme/`. Provenance is non-negotiable:
  `[CONFIRMED]` requires a `file:line`, `[INFERRED]` requires a stated reason,
  and values are never invented. A codebase too thin to extract from returns
  `extraction_verdict: insufficient` rather than a padded system, and the
  Signature Move is derived by recurrence count or honestly reported as
  `none found` — a fabricated one would silently redesign the host product.
  (ISSUE-054, PR #89)
- **Overwrite guard on the extracted design system doc.** `extend` halts before
  writing when `docs/design_system[_mobile|_desktop].md` already exists and
  offers overwrite / write-alongside (`.extracted.md` plus a diff summary) /
  cancel, quoting the file's line count and last-modified date. A
  hand-maintained design system is the one artifact this mode can destroy, and
  "it's in git" is not treated as consent. (SPEC-054 open question 1, PR #89)
- **Slop calibration in the Anti-AI-Slop rules**, harvested from a comparison
  against the official `frontend-design` plugin: the three AI-design clusters
  currently produced regardless of subject (cream/serif/terracotta,
  near-black + acid accent, broadsheet hairline), banned as *defaults* rather
  than as choices; a self-similarity check before locking a design plan; and a
  CSS selector-specificity rule for web and the Electron renderer.
  Landed as a shared `{{SLOP_CALIBRATION}}` fragment plus three guarded agent
  chunks, so the three uiux skills and their developer agents cannot drift.
  (PR #86)

### Changed
- **`Brief overrides:` resolves a standing contradiction in the slop rules.**
  The "Specific AI Tells" header already allowed a brief to call for a banned
  pattern, while the Phase 5.5 sweep enforced zero tolerance — the two
  disagreed. Brief-pinned directions now win, recorded as `Brief overrides:`
  bullets in `docs/design_philosophy.md`, and each skill's AI Tell sweep exempts
  exactly the recorded tells and no others. An unrecorded violation is still a
  violation. `extend` mode reuses this seam so the sweeps stop rewriting the
  host product's own conventions. (PR #86, PR #89)

## 0.4.0 — 2026-08-12

### Added
- Documented the `KIT_ALLOW_BROWSER_INSTALL` (ISSUE-049) and
  `KIT_SPRINT_QUEUE_GH_TIMEOUT` (ISSUE-052) behaviour-control env knobs in
  README.md (new "Behaviour-control environment variables" subsection) and
  docs/troubleshooting.md, alongside the existing `KIT_CHECKPOINT_TEST_TIMEOUT`
  documentation. A drift-guard test (`tests/test_env_knob_docs.py`) fails if a
  knob is referenced in code but absent from both docs. (ISSUE-053, PR #85)
- Made the sprint queue crash-recovery aware of already-merged PRs. A ship-phase
  interruption (API/spend limit) between the squash-merge and the post-merge smoke
  checkpoint used to leave an issue at sprint_state phase `reviewed`/`shipping` while
  its PR was already merged; `sprint_queue.py next-action` re-proposed SHIP (risking a
  double-merge). It now probes the PR merge state (`gh pr view --json state,mergedAt`,
  timeout-guarded via `KIT_SPRINT_QUEUE_GH_TIMEOUT`, cached, `--no-check-merged` opt-out)
  and emits a new **FINALIZE** action (smoke + registry only) for already-merged reviewed
  issues — never a re-merge. An idempotent ship-merge guard (`ship-merge-decision`
  subcommand / `ship_merge_decision()`) makes the ship merge step a no-op when the PR is
  already merged. Wired end-to-end (queue → sprint orchestrator routing + team-lead
  FINALIZE handler → ship SKILL guard). Degrades gracefully when `gh` is
  missing/unauthenticated/offline (phase-only decision + logged warning, never crashes).
  (ISSUE-052, PR #83)
- Added unit tests for six previously untested checkpoint-gate scripts — the
  Figma visual-diff family (`verify_visual_diff.py`, `verify_computed_styles.py`,
  `verify_structural_match.py`, `verify_layout.py`, `generate_figma_css.py`) and
  the `validate_frontmatter.py` CI gate. Tests run without Chromium or network
  (browser boundaries mocked; synthetic PNG/JSON fixtures under
  `tests/fixtures/figma/`), pin both visual-diff thresholds (1% same-renderer,
  5% Figma-PNG fallback) so silent drift fails, and lift combined statement
  coverage of the six scripts to ~69% (each non-zero). (ISSUE-045, PR #73)

### Changed
- Deduplicated the UI/UX design-philosophy boilerplate that was copy-pasted across
  the three `uiux` / `mobile-uiux` / `desktop-uiux` skill templates and their three
  developer agents. The shared text now lives once as a canonical fragment in
  `scripts/fragments.py`, resolved into the skill templates via `{{DESIGN_PHILOSOPHY}}`
  / `{{DESIGN_PHILOSOPHY_CHECKPOINT}}` tokens (alongside `{{PREAMBLE}}`); platform
  deltas stay inline. The static agent copies are held in sync by a drift-guard
  test (`tests/test_design_fragments.py`) that names any out-of-sync agent file.
  Regenerated `SKILL.md` output is semantically identical to before (mobile/desktop
  byte-identical; a few accidental wording divergences unified). (ISSUE-041, PR #72)

### Removed
- Removed four dead scripts and their orphaned tests — `ensure_permissions.py`
  and `ensure_gh.sh` (zero callers), `kit_root.sh` (referenced only by its own
  test; wrappers inline their own root resolution), and
  `lint_skill_cache_order.py` (wired to neither CI nor any skill; deleted per
  the repo-audit default rather than wired into `ci.yml`). Gitignored the
  `.claude/run/` session-telemetry subpath (only `run/`; `.claude/` stays
  visible) and added an ISSUE-027-style grep guard
  (`tests/test_dead_script_removal.py`) that blocks re-references to the removed
  names and asserts no tracked `__pycache__`/`.pyc`. (ISSUE-043, PR #68)

### Fixed
- De-conflict the parallel-review `docs/.review` scratch path. The review layer's
  fixed-path scratch artifacts (`code-review.md`, `findings.json`, `minimality.md`,
  `security-review.md`) were tracked, so parallel review branches merging in
  sequence conflicted on exactly these files every sprint (PRs #58/#64/#65/#72).
  Fix (option b): gitignore `docs/.review/` and untrack the scratch — it is
  regenerated and consumed within a single `/review` invocation (the canonical
  committed record stays `docs/review_notes/ISSUE-XXX.md`); no checkpoint reads it
  from a commit. A guard test asserts the path is ignored and no scratch remains
  tracked. (ISSUE-051, PR #81)
- Lint the README agents-table Tools/Effort cells against agent frontmatter.
  A new row-by-row test in `tests/test_readme_consistency.py` compares each
  row's Tools (set-equal, normalized) and Effort cell against the corresponding
  `agents/*.md` frontmatter, naming any offending row, so future drift fails the
  build. Reconciled the drift the test surfaced (frontmatter is the oracle):
  `brainstormer`/`business-analyst` dropped spurious `WebSearch, WebFetch`;
  `ui-reviewer` and `a11y-auditor` gained the missing `Bash`; `design-auditor`
  dropped spurious `Edit, Write`. (ISSUE-050, PR #79)
- Gated the Figma visual-diff browser auto-install behind an explicit opt-in.
  `_check_playwright()` in `verify_visual_diff.py` and `verify_computed_styles.py`
  shelled out to `pip install playwright` + `playwright install chromium`
  (~180s, network) on any import-failure path — a review/CI gate silently
  mutating its env and reaching the network. The heavy provisioning now runs
  only when `KIT_ALLOW_BROWSER_INSTALL=1`; unset, the gate reports "browser
  unavailable" to stderr and returns via the existing skip/degrade path. The
  no-browser-at-collection lazy-import guarantee is preserved. (ISSUE-049, PR #78)
- Scoped the implement-phase checkpoints (`verify_implement_tests_written`,
  `verify_implement_red`, `verify_implement_code`) to the branch's own delta.
  They diffed the worktree against `main` directly, so a worktree built on a
  stale `main` surfaced files a newer `main` added/deleted after the fork point
  (absent from the worktree tree) and `_has_real_tests` manufactured a phantom
  hollow-test FAIL (ISSUE-041/044 hit this). Now they diff against
  `git merge-base HEAD main` and intersect the classified set with files that
  exist in the worktree, falling back to the old behavior when the fork point
  is unresolvable. (ISSUE-048, PR #77)
- CI now fails loudly on dependency-install problems and runs under one
  consistent toolchain: `ci.yml` migrated from pip to uv (`astral-sh/setup-uv`
  + `uv sync --locked --extra dev`, every step via `uv run`), dropping the
  `2>/dev/null || true` swallow so a broken dev-extras spec fails the job; the
  dead `asyncio_mode = "strict"` config and unused `pytest-asyncio` dep were
  removed (no more PytestConfigWarning) and `uv.lock` regenerated.
  `gate_server.sh` now starts the server in its own process group (`set -m`)
  and its cleanup trap signals the whole group (graceful TERM then KILL,
  best-effort so the 124/125/passthrough exit-code contract is preserved), so
  forking servers no longer leak orphans. (ISSUE-044, PR #70)
- `verify_checkpoint.py` test-phase gates no longer false-fail on multi-minute
  suites: the implement `red`/`test` and ship `smoke` subprocess timeouts are
  env-configurable via `KIT_CHECKPOINT_TEST_TIMEOUT` (seconds; default 600,
  previously hard-coded 60s/120s). A RED-phase run that hits the timeout
  (exit 124) is now reported as an inconclusive FAIL instead of being
  mistaken for a genuinely failing suite. (ISSUE-046, PR #54)
- `verify_gates.py`'s blocking `unit` gate no longer false-fails on
  multi-minute suites: both pytest/npm subprocess timeouts (previously
  hard-coded 120s) honor the same `KIT_CHECKPOINT_TEST_TIMEOUT` env var
  (seconds; default 600) as `verify_checkpoint.py`. Also isolated two
  `verify_implement_test` tests that left the gate-runner seam unmocked
  and recursively spawned the full pytest suite inside itself.
  (ISSUE-047, PR #56)
- `/review` skill steps are now a single strictly increasing sequence: the
  duplicated 3.8–3.10 cluster (ui-review/design-audit/a11y) is renumbered to
  3.11–3.13 and synthesize/merge-audit shift to 3.14/3.15, so the synthesis
  step's "Figma 3.5–3.10" cross-reference is unambiguous. The brainstorm
  degraded path now names `docs/references/research/` explicitly instead of
  "snapshot directory". A step-number monotonicity regression guard was added.
  (ISSUE-036, PR #57)
- The SessionStart hook no longer bakes version-pinned plugin-cache paths
  into the contributor-mode instruction it injects into session context.
  The instruction now defers path resolution to the Kit Script Root shown
  in the active skill preamble, so it survives plugin updates and cache GC
  (no ENOENT, no silently stale `contributor_report.py`); standalone-layout
  behavior is unchanged. (ISSUE-037, PR #58)
- The autotest PostToolUse hook no longer re-walks the whole tests tree on
  every Write/Edit: related-test lookups use a disk-persisted module-to-test
  index under `.claude/run/` (invalidated by tests-dir mtime scan; warm hits
  re-validated on read so a poisoned or stale cache can never execute
  non-test paths), and repeat edits to the same module within the debounce
  window skip identical passing runs — failures are never debounced into
  silence. Behavior knobs (MAX_RELATED_TESTS, timeouts, block-on-failure)
  unchanged; corrupt/missing cache rebuilds fail-soft. (ISSUE-038, PR #59)
- The `secret_guard` and `dangerous_command_guard` hooks no longer traceback
  on malformed hook stdin: the JSON parse is guarded (invalid JSON, empty
  stdin, and valid-JSON-but-non-dict payloads all covered), and on parse
  failure the guard skips loudly — a one-line stderr diagnostic
  (`<guard>: malformed hook payload — guard skipped`) and exit 0 — instead
  of a silent fail-open traceback. stdout stays a pure JSON decision channel
  and blocking semantics are unchanged; an in-file comment documents the
  stdout-JSON blocking mechanism and the `|| true` / exit-code-2 footgun.
  (ISSUE-039, PR #63, merged cd7511d)
- The `/sprint` skill now sets `disable-model-invocation: true`, closing
  the 2026-08-10 repo-audit gap where the heaviest autonomous orchestrator
  (implements, reviews, and ships every backlog issue) was the only
  repo-mutating skill the model could auto-invoke without an explicit
  user command. Sprint is now explicit-user-invocation only, matching
  implement/review/ship/kickoff/scan; a frontmatter lint test
  (tests/test_orchestrator_disable_model_invocation.py, 6 cases) guards
  the invariant for all repo-mutating orchestrators.
  (ISSUE-042, PR #64, merged f254227)
- README.md no longer drifts from shipped reality: version pin dropped in
  favor of the `VERSION` file, agent roster corrected to 32 with the three
  auditor agents added to the table, stale model-mix line replaced with the
  inherit-model + effort-tier description, retired `.claude-kit/` submodule
  install diagrams replaced with plugin-first layouts, and a /spec Usage
  section added. A consistency test suite (tests/test_readme_consistency.py)
  guards version, roster count, and layout claims against future drift; the
  Tests badge was reconciled to the canonical dev-extras count (1190).
  (ISSUE-040, PR #65, merged 5990c93)

## 0.3.0 — 2026-08-09

### Removed
- **Sales pack removed entirely** — the `claude-dev-kit-sales` plugin, the whole
  `packs/` subtree (5 agents, 5 skills, 7 templates, manifest), `docs/sales-pipeline.md`,
  `templates/poc_results.md`, and `scripts/find_shared.sh`. It saw no real use and
  only added complexity to the kit.
- **Pack infrastructure removed with it** (sales was the only pack):
  `scripts/validate_pack_manifest.py` + its tests, the CI pack-manifest step,
  the marketplace `claude-dev-kit-sales` entry, and all `packs/*/` discovery
  globs in `gen_skills.py`, `validate_frontmatter.py`, and the lint tests.
- README/docs no longer document packs: install commands, the Packs section,
  sales team-scale patterns, and the sales rows in `docs/README.md` are gone.

### Migration
- New installs simply won't see `claude-dev-kit-sales` in the marketplace after
  `/plugin marketplace update claude-dev-kit`.
- If you had it installed, remove it manually: `claude plugin uninstall claude-dev-kit-sales`.
  Historical releases remain available at the `claude-dev-kit-sales--v*` tags.

## 0.2.1 — 2026-07-26

- Sync the root `VERSION` file with the plugin version (it was left at 0.1.0
  by the 0.2.0 release, breaking the CI version-match test and the
  `kit_update_check` local/remote comparison).

## 0.2.0 — 2026-07-26

The "harness fits modern Claude Code" release: the kit now installs purely as a
Claude Code plugin, delegates to platform capabilities where they're stronger,
and trims harness overhead that no longer earns its keep.

### Platform & install
- **Plugin is the only install path.** The bespoke `install_project.sh` +
  symlink installer is removed; install via `/plugin install claude-dev-kit@claude-dev-kit`
  (ISSUE-027). Skills are namespaced — `/claude-dev-kit:implement`, etc.
- **Scripts resolve under plugin install** via `${CLAUDE_PLUGIN_ROOT}` load-time
  substitution — no files copied into your project (ISSUE-035). Also fixed a
  manifest bug that was silently dropping skill frontmatter.
- **Removed the passive `WorktreeCreate` hook** — it's a creator contract that
  broke native worktree creation for plugin users (ISSUE-027).

### Behavior changes to know about
- **Checkpoints are two-tier** (ISSUE-031): existence checks (issue/worktree/
  code/registry/push/pr) are now **advisory** (report + continue), while
  behavior gates (tests, TDD red, hollow-test, Figma suite) stay blocking.
- **Review lessons moved to native memory** (ISSUE-033): `/review` records
  preventable patterns in Claude Code's persistent memory; the never-used
  `docs/review_lessons.md` registry is retired (existing files are inert).
- **Agents inherit the session model** (ISSUE-030): no more per-agent model
  pins. Pin once at the project/session level for deterministic deploys.
- **/review, /brainstorm, /bizanalysis delegate to platform skills** when
  available (`/code-review`, `/security-review`, `/deep-research`), with a
  degraded fallback (ISSUE-029).
- **4 unused persona agents absorbed** into their skills (ISSUE-034); roster 32.

### New
- **Run telemetry** (ISSUE-001): shape-only `.claude/run/events.jsonl` +
  `scripts/trace_query.py summary`.
- **SessionStart hook** runs kit checks once per session; skill preambles
  slimmed 56% (ISSUE-032).
- **Review-quality eval** (ISSUE-002): optional non-blocking `/ship` step runs
  an LLM-as-judge over review notes via `claude -p` (no separate billing).

## 0.1.0

Initial kit — 32 agents / 28 skills, GitHub-first sprint workflow, worktree
orchestration, checkpoint gates, design/uiux pipeline, sales pack.
