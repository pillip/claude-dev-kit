# Issues

> SSOT: Progress and completion are tracked by the Status field in this document (not inferred from code analysis)
> Rule: **1 Issue = 1 PR** (GitHub-first)
> Context: claude-dev-kit dogfoods itself — these issues build the "AI dev team control plane" layer (telemetry → eval → memory → spec → release) on top of the existing agent/skill primitive set (the roster shrinks by design; counts are deliberately not pinned — tests/test_agent_effort.py guards hygiene, not headcount).

## Conventions
- Track: `product` | `platform`
- Status: `backlog` | `doing` | `waiting` | `done` | `drop`
- Priority: `P0` (blocks everything) | `P1` (core) | `P2` (nice-to-have)
- Estimate: `0.5d` | `1d` | `1.5d` (> 1.5d must be split)
- Platform: `web` (default) | `mobile` | `desktop`
- Manual: `true` = task requires human action; `false` = fully automatable
- Branch: `issue/ISSUE-<NNN>-<slug>`
- GitHub: **/implement creates a GH Issue (if missing) + PR and links them (Closes #N)**
- Spec PR exception: a `Spec-Required: true` issue produces **2 PRs in non-sprint mode** (spec-only PR `issue/ISSUE-NNN-spec` then impl PR `issue/ISSUE-NNN`), and **1 bundled PR in sprint mode** (single branch carrying both the SPEC commit and impl commits). See ISSUE-006/007.

---

## Board

> **Work order (agreed 2026-07-21, revised 2026-07-22):** 035 (plugin-resolved skill commands) → 027 (re-verify parity item 2, then delete) → 001 (minimal baseline re-scope) → 030 → 032 → 031 → 029 → 002 → 033 → 034. Constraints: 001 must land **and capture a before-baseline run** before 030 starts; 002 follows 029 so the judge grades platform /code-review output; 002→033 is synergy only, NOT a hard dep — do not block 033 if 002 slips.
> Revision rationale: the 027 live parity check ran 2026-07-22 (scriptable via `claude plugin` CLI — no manual session needed after all). Items 1/3/4/5 pass (after two manifest fixes); **item 2 fails** — skills' `bash scripts/...` commands don't resolve in a plugin-only project — spawning ISSUE-035 as the new first step.

### Backlog
- [x] ISSUE-036: Renumber duplicated /review steps 3.8–3.10 + name the brainstorm snapshot directory _(track: platform, P1, 0.5d — 2026-08-10 repo audit findings 1+12)_
- [x] ISSUE-037: Stop injecting version-pinned plugin paths from the SessionStart hook _(track: platform, P1, 0.5d — audit finding 2)_
- [x] ISSUE-038: Cache the autotest hook's test index + debounce repeat runs _(track: platform, P1, 1d — audit finding 3)_
- [x] ISSUE-039: Harden security-guard hooks against malformed stdin _(track: platform, P1, 0.5d — audit finding 4)_
- [x] ISSUE-040: Sweep README staleness — version, roster, retired install diagrams _(track: platform, P1, 1d — audit finding 5)_
- [x] ISSUE-041: Extract shared UI/UX design-philosophy fragment — dedupe uiux/mobile/desktop boilerplate _(track: platform, P2, 1d — audit finding 6; depends on 036)_
- [x] ISSUE-042: Set disable-model-invocation: true on the sprint skill _(track: platform, P1, 0.5d — audit finding 7)_
- [x] ISSUE-043: Remove dead scripts, untrack committed __pycache__, gitignore .claude/run/ _(track: platform, P2, 0.5d — audit findings 8+11)_
- [x] ISSUE-044: Fix CI environment mismatch + gate_server.sh process-group cleanup _(track: platform, P1, 1d — audit findings 9+13)_
- [x] ISSUE-045: Add tests for the Figma visual-diff family + validate_frontmatter.py _(track: platform, P2, 1.5d — audit finding 10)_
- [x] ISSUE-048: Scope implement checkpoints to the branch's own delta (merge-base diff) _(track: platform, P2, 0.5d — 2026-08-11 sprint discovered, iter8)_
- [x] ISSUE-049: Gate the Figma visual-diff browser auto-install behind an explicit opt-in _(track: platform, P2, 0.5d — sprint discovered, iter8)_
- [x] ISSUE-050: Lint the README agents-table Tools/Effort cells against agent frontmatter _(track: platform, P2, 0.5d — sprint discovered, iter6)_
- [x] ISSUE-051: De-conflict the parallel-review docs/.review scratch path _(track: platform, P3, 0.5d — sprint discovered, iter5/6/7)_
- [x] ISSUE-052: Make sprint_queue crash-recovery aware of already-merged PRs _(track: platform, P2, 1d — sprint discovered, iter7/8)_
- [x] ISSUE-053: Document the KIT_ALLOW_BROWSER_INSTALL + KIT_SPRINT_QUEUE_GH_TIMEOUT env knobs _(track: platform, P3, 0.5d — sprint 2 discovered, iter1/2)_
- [ ] ISSUE-069: Pin the sprint roster boundary at sprint start — stop the watermark ratchet from re-hiding and auto-dispatching Board issues _(track: platform, P1, 1.5d — ISSUE-068 review triage, 2 unresolved High (GAP-068a/b); depends on 068)_
- [ ] ISSUE-070: Contain the telemetry emitter's write target and make its no-raise/no-hang contract true _(track: platform, P1, 1d — ISSUE-067 review triage, unresolved High + 2 same-module Medium; depends on 067)_
- [ ] ISSUE-071: Give KIT_RUN_ID a producer or stop announcing its absence on every run _(track: platform, P1, 1d — ISSUE-067 review triage, unresolved High: the fallback announcement fires on 100% of runs; depends on 067)_
- [ ] ISSUE-072: Verify sub-agent skill invocation in the feature matrix and grant it on the review path if supported _(track: platform, P1, 0.5d — ISSUE-066 review triage: the kit's own agent `tools:` frontmatter confounds SPEC-066's categorical conclusion; depends on 066)_
- [ ] ISSUE-073: Validate the PR ref before the `gh` merge-state probe — an option-shaped Board `PR:` value forges a MERGED verdict _(track: platform, P1, 0.5d — GAP-068j: pre-existing argument injection from ISSUE-052, live on main, reviewer-reproduced on the rostered path; depends on none)_
- [ ] ISSUE-074: Reconcile the registry-lock contract so the actor instructed to take the `issues.md` lock can actually invoke it _(track: platform, P1, 0.5d — iter-1 review triage: team-lead is forbidden to write issues.md and planner is told to use flock_edit.sh but has no Bash, so the contract resolves as a silently unlocked write that still succeeds; mirror of ISSUE-072; depends on none)_
- [ ] ISSUE-075: Migrate review_context.py's private telemetry appender onto the shared kit_telemetry emit seam _(track: platform, P2, 0.5d — ISSUE-066 ship-time deferral: SPEC-066 pre-committed to adopting ISSUE-067's shared emitter, deferred because `emit_event`'s "NEVER raises" contract is false today (ISSUE-070) and two existing tests pin the opposite silent-skip contract; duplication debt, not a hardening regression; depends on 066, 067)_

### Doing

### Waiting

### Done
- [x] ISSUE-004: Sales pack file move + manifest schema _(track: platform, P1, 1d)_
- [x] ISSUE-005: README sync — reflect counts + positioning + post-sales-boundary layout + team-scale usage _(track: platform, P1, 1d)_
- [x] ISSUE-006: /spec skill — RFC pattern + Spec-Required metadata + non-sprint HOLD gate _(track: platform, P1, 1.5d)_
- [x] ISSUE-007: /implement spec gate — sprint auto-run + non-sprint HOLD + signal detection _(track: platform, P1, 1d)_
- [x] ISSUE-009: Install script --pack flag + merge_settings + tests _(track: platform, P1, 1.5d)_
- [x] ISSUE-010: Pilot Gate hardening — separate-context critic + auto-cycle + neutral observation + specificity check _(track: platform, P2, 1.5d)_
- [x] ISSUE-011: Kill WebFetch reference fabrication — image-grounded references only _(track: platform, P1, 0.5d)_
- [x] ISSUE-012: Reference Anchor tuning — 2-3 strong cues + 1 literal quote _(track: platform, P2, 0.5d)_
- [x] ISSUE-013: Consolidate ui-reviewer / design-auditor agents — sharpen role boundaries _(track: platform, P2, 1d)_
- [x] ISSUE-014: Verify Claude Code feature/version support matrix (spike) _(track: platform, P1, 0.5d)_
- [x] ISSUE-015: Adopt agent effort tiers + refresh model references _(track: platform, P2, 1d)_
- [x] ISSUE-016: Worktree/session lifecycle hooks — auto-freeze + run/ cleanup _(track: platform, P2, 1d)_
- [x] ISSUE-017: Migrate kit packaging to Claude Code plugin system (SPEC) _(track: platform, P1, 1.5d — spec)_
- [x] ISSUE-022: Plugin manifests + skill-hook path hygiene _(track: platform, P1, 1.5d)_
- [x] ISSUE-023: Resolve scripts/ root via ${CLAUDE_PLUGIN_ROOT} (closes #34 bug class) _(track: platform, P1, 1d)_
- [x] ISSUE-025: Model the sales pack as a dependent plugin (kit-sales → core) _(track: platform, P2, 1.5d)_
- [x] ISSUE-026: Plugin distribution (marketplace.json) + namespacing docs _(track: platform, P2, 1d)_
- [x] ISSUE-018: Over-engineering/simplicity review axis (ponytail benchmark) _(track: platform, P1, 1d)_
- [x] ISSUE-019: Decision-ladder preamble for implement developer subagent (ponytail benchmark) _(track: platform, P2, 0.5d)_
- [x] ISSUE-020: Tech-debt marker convention + harvester + review checkpoint (ponytail benchmark) _(track: platform, P2, 1d)_
- [x] ISSUE-021: PyYAML-dependent tests should skip cleanly when the dep is absent _(track: platform, P2, 0.5d)_
- [x] ISSUE-028: Remove lint enforcement from the kit (autoformat hook + linter configs) _(track: platform, P2, 0.5d)_
- [x] ISSUE-035: Plugin-resolved skill entry commands — make `scripts/` invocations work under plugin install _(track: platform, P1, 1d — done 2026-07-22: Kit Script Root preamble section rides CC's load-time `${CLAUDE_PLUGIN_ROOT}` text substitution; plugin-root allowlist patterns added; AUTO-GEN header moved below frontmatter (byte-0 rule — frontmatter was silently dropped for all 25 generated skills). Live-verified headless: checkpoint + kit_update_check execute via absolute prefix in a plugin-only project)_
- [x] ISSUE-027: Deprecate install_project.sh after plugin parity _(track: platform, P2, 1d — done 2026-07-22: all parity items live-verified. The WorktreeCreate probe exposed a creator-contract mismatch — docs say the hook must CREATE the worktree and print its path, so the kit's passive freeze hook was breaking native worktree creation; hook removed (platform-first), guard test added. Installer + install_packs/merge_settings removed with their tests; README/packs docs flipped plugin-first; grep-guard test blocks re-references. Deviations: validate_pack_manifest.py kept (pack-authoring lint), install_user.sh kept (user-scope statusline, not the project installer))_
- [x] ISSUE-001: Run telemetry MVP — JSONL trace from agent_state hook _(track: platform, P1, 0.5d minimal re-scope — done 2026-07-23: agent_state.py emits SHAPE-ONLY events (the old full-payload dump leaked tool inputs/file contents into the trace), with checkpoint pass/fail extraction + UserPromptSubmit turn counting; scripts/trace_query.py `summary` derives turns/tool-calls/failures/spawns/checkpoints/duration per session. **Baseline captured** (docs/baselines/2026-07-23-diagnose-baseline.md): headless /diagnose fixture run — 74s, 10 API turns, 6.8k in / 4.4k out / 262k cache-read, $1.01, and 0 checkpoints + 0 subagents actually exercised (harness bypassed — direct before-signal for 031/032). Full spec (flock guarantees, schema doc, lead-time query) stays follow-up)_
- [x] ISSUE-030: Remove agent model pins — default to `inherit` _(track: platform, P1, 0.5d — done 2026-07-23: all 33 core + 5 sales agents now inherit the session model (zero surviving pins); effort tiers stay as the per-agent knob. README agent table shows Effort instead of Model and documents the single-point deterministic pin (project `model` setting / `--model`) — the predictability guard. test_agent_effort.py rewritten: any future pin requires an adjacent `# pin:` rationale comment; xhigh valid under inherit (auto-fallback); matrix rows 2/3 updated)_
- [x] ISSUE-032: Move per-skill startup checks to a SessionStart hook + slim skill preambles _(track: platform, P2, 1d — done 2026-07-23: new session_start.py hook (plugin hooks.json + standalone snippet) runs kit_update_check + contributor-mode detection once per session, stdout injected into context — **live-verified under plugin install**. Preamble diet: dropped Kit Update Check / Contributor Mode / Self-Review, slimmed Behavioral Rules→Kit Rules, compressed Kit Script Root — **1385 → 618 total preamble lines (56% cut, AC ≥50%)** with a 700-line budget lint; kit_update_check dropped from 10 allowlists; orphan-reference guard test; matrix row 4e (SessionStart) added)_
- [x] ISSUE-031: Checkpoint diet — demote existence-check gates to advisory _(track: platform, P2, 1d — done 2026-07-23: 18 existence-style phases (implement issue/worktree/code/push/pr/registry, review checkout/push, generic worktree/push ×5 skills) now print `ADVISORY:` and exit 0 — report, self-correct, continue; 30 behavior gates (test/red/tests-written/test-quality, Figma suite, ship, uiux) stay hard-blocking. Skill text converted per-tier (18 blocks + intro rules in 8 skills + preamble pattern); checkpoint names/plumbing unchanged. **Predictability guard**: test_verify_checkpoint_contract.py enumerates the full 48-phase partition — any silent tier change is a build failure)_
- [x] ISSUE-029: Platform-first delegation of /review, /brainstorm, /bizanalysis to runtime skills _(track: platform, P2, 1.5d — done 2026-07-24: reconciled the hold branch (SPEC-018/019) onto current main rather than git-rebasing (issues.md/test/skill divergence too large). /review probes runtime via has_skill.py → primary path delegates correctness to /code-review + security to /security-review (per-dimension, mixed-mode) → synthesize_review_notes.py merges verbatim into the 2-section+Over-Engineering SSOT → review-merge-auditor (separate-context, refute-first) blocks on drops/downgrades/distortions; degraded path = reworked reviewer agent per dimension. /brainstorm + /bizanalysis delegate research to /deep-research (primary) or capture_source+validate_research_claim (degraded), synthesizer-auditor/research-auditor gate fabrication. 3 new auditor agents (inherit model per ISSUE-030 → roster 33→36). Reconciled with 030 (pins stripped), 031 (review checkout/push advisory + new synthesis-audit blocking gate), 032 (preamble auto-regen, kit_update_check allowlist dropped), 035 (plugin-root allowlists). synthesizer now always renders Over-Engineering. 106 delegation guard tests + telemetry_schema events. **Live-verified 2026-07-26**: `/code-review` fires and returns structured findings on a planted-bug diff — primary path confirmed exposed and working)_
- [x] ISSUE-033: Learning loop on Claude Code native memory — supersedes ISSUE-003 _(track: platform, P2, 1d — done 2026-07-24: /review Learning Extraction now records preventable patterns as **review lessons in Claude Code native memory** (topic file + MEMORY.md index, dedup-in-place, no RL-NNN/Frequency), replacing the never-used docs/review_lessons.md registry (retired; template + [RL-NNN] flow removed). Confirmed via claude-code-guide: memory dir `~/.claude/projects/<project>/memory/` (overridable `autoMemoryDirectory`), MEMORY.md auto-loads at session start, **but Task subagents get NO auto-recall** — so the 26 consuming agents + kickoff/sprint/implement/testgen skills were reworded to "apply recalled/injected review lessons", and /review injects relevant lessons into separate-context subagent prompts. README/docs/roadmap updated; test_integration flipped to assert the native convention + guard against re-wiring the legacy registry. **Live-verified 2026-07-26**: a headless session wrote a review lesson to the native memory dir + MEMORY.md index; a fresh session in the same project auto-recalled the index entry — write + main-session recall confirmed)_
- [x] ISSUE-034: Agent roster diet — consolidate thin persona agents _(track: platform, P2, 1d — done 2026-07-24: full classification found the audit's "~16 thin" over-counted — most "thin personas" are inline skills or sprint routing labels, not live orchestration hops. Absorbed the **4 genuinely-dead persona files** (diagnostician/migrator/refactorer/prd-writer — never Task-invoked, their skills have no Task at all) into their skills as "Execution Principles" grafts (root-cause discipline, one-major-bump migrations, behavior-preserving refactor, PRD completeness); roster 36→32; team-lead test-failure path rerouted to /diagnose. **Kept with rationale**: 3 auditors + reviewer/developer/architect/planner/uiux-developers (differentiated methodology / separate-context self-grading guard — the predictability guard), scan-family (real 4-pass per-domain pipeline; merging loses separate context), brainstormer/business-analyst (029 degraded-path research agents, freshly guard-tested). test_agent_effort roster+HEAVY, test_integration param lists/self-review/sprint-table + README/issues-header updated)_
- [x] ISSUE-002: Workflow eval gate MVP — LLM-as-judge for review_notes quality _(track: platform, P1, 1.5d — done 2026-07-26: `scripts/eval_review.py` runs a fresh `claude -p` judge over review_notes + the PR diff, scoring coverage/false-positive/actionability/traceability (rubric in `templates/review_eval_rubric.md`), emitting `docs/review_eval_<pr>.md`. Wired as a **non-blocking** step 8 in /ship — always exits 0; missed Critical/High or a dimension ≤2 → `concerns`, else `pass`. **No separate billing** (session auth, not ANTHROPIC_API_KEY); degraded-mode skips silently if the CLI/notes are absent. Determinism via `--runs N` (Critical/High Jaccard overlap; ≥80% is the floor — CLI has no temperature control). 17 unit tests cover rubric contract, verdict derivation (judge "pass" + missed High → concerns), determinism math, degraded mode, never-blocks-on-error, and the /ship wiring. Judge grades the platform /code-review-fed notes post-029, sidestepping self-grading. **Live-verified 2026-07-26**: the judge round-trip produced valid JSON and correctly caught a deliberately-missed SQL-injection (coverage 0, verdict `concerns`, missed Critical flagged with diff_ref) — rubric → parseable verdict confirmed end-to-end)_
- [x] ISSUE-046: Fix verify_checkpoint.py's 60s pytest timeout breaking the GREEN gate and hollowing the RED gate on 4-minute suites _(track: platform, P0, 0.5d — done 2026-08-11: test-phase subprocess timeouts (implement red/test, ship smoke; were hard-coded 60s/120s) now env-configurable via KIT_CHECKPOINT_TEST_TIMEOUT (seconds; default 600) through a _test_timeout() helper; RED-phase exit-124 reported as inconclusive FAIL instead of being mistaken for a failing suite; absorbed verify_ship_smoke full-suite + no-runner-fallback caps (reviewer-accepted scope). Squash-merged PR #54 @ c04b78b 2026-08-10; ship smoke initially blocked solely by the pre-filed ISSUE-047 verify_gates 120s unit-gate cap — retried post-ISSUE-047 on 2026-08-11: GATE PASS unit [blocking] 14.5s, smoke PASS; review 0 Critical/High, 6 Low; eval artifacts in docs/review_notes/ISSUE-046.md)_
- [x] ISSUE-047: Fix verify_gates.py hard-coded 120s unit-gate timeout (and sibling short caps) breaking blocking ship-smoke gates on multi-minute suites _(track: platform, P0, 0.5d — done 2026-08-11: env-configurable unit-gate timeout via KIT_CHECKPOINT_TEST_TIMEOUT (seconds; default 600) mirroring verify_checkpoint.py::_test_timeout, _run() timeout-mock contract (rc 124) preserved; absorbed test-isolation fix for two verify_implement_test tests whose unmocked gate-runner seam recursively spawned the full suite — the source of the false "~5-min suite" premise (true base ~21s). Squash-merged PR #56 @ b0d8bb3; post-merge smoke: GATE PASS unit [blocking] 14.6s, suite 1145 passed / 2 skipped ~11s; review 0 Critical/High/Medium, 6 Low; eval: pass)_
- [x] ISSUE-054: Brownfield design path — extract a design system from existing UI code so /uiux can extend instead of replace _(track: platform, P2, 1.5d — 2026-08-17 official-plugin comparison; no platform capability covers it)_
- [x] ISSUE-056: Promote the four model-executed verification sweeps to deterministic validators _(track: platform, P1, 1.5d — SPEC-055 / evolution audit finding 3; numbering note: 055 skipped — consumed by ad-hoc SPEC-055)_
- [x] ISSUE-057: Add script checkpoints to the five zero-checkpoint skills _(track: platform, P1, 1.5d — SPEC-055 / audit finding 2)_
- [x] ISSUE-058: Delegation idiom expansion — test execution _(track: platform, P2, 1d — SPEC-019 flagged candidate; SPEC-055 / audit roadmap 4)_
- [x] ISSUE-059: Deflate scaffolding residue — persona blocks, confidence-rating boilerplate, inline prompts _(track: platform, P2, 1d — SPEC-055 / audit roadmap 3a)_
- [x] ISSUE-060: Contract-convert the uiux triplet — strip craft tutorials, keep gates and anti-slop contracts _(track: platform, P1, 1.5d — SPEC-055 / audit roadmap 3b; depends on 056, 059)_
- [x] ISSUE-061: Consolidate the scan-*/greenfield sibling agent pairs behind an evidence-mode flag _(track: platform, P2, 1.5d — SPEC-055 / audit roadmap 5)_
- [x] ISSUE-062: Dissolve A-bucket conversational agents into their skill contracts _(track: platform, P2, 1d — SPEC-055 / audit roadmap 6)_
- [x] ISSUE-063: Fix verify_design_sweeps SPEC-056 contract deviations — multi-line CSS evasion, concatenated `all --json`, fail-open `all` without `--class` _(track: platform, P1, 0.5d — ISSUE-056 review triage, docs/review_notes/ISSUE-056.md; depends on 056)_
- [x] ISSUE-064: Harden verify_design_sweeps matcher edges — encoded/case tell variants, non-rendered quote placements, zero-screen vacuity, input containment _(track: platform, P2, 1d — ISSUE-056 review triage, adjacent Medium findings; depends on 063)_
- [x] ISSUE-065: Add provenance, freshness, and consume-once binding to the KIT_GATE_RESULTS_FILE delegation handoff _(track: platform, P1, 1d — ISSUE-058 review triage, unresolved High finding in docs/review_notes/ISSUE-058.md; activation precondition per SPEC-058 Open Questions / test-plan GAP-058a; depends on 058)_
- [x] ISSUE-066: Make the SPEC-019 primary path reachable inside /sprint — runtime review skills are uninvokable from sub-task context _(track: platform, P1, 1.5d — 2026-10 sprint retro: all 6 sprint reviews ran degraded; the flagship idiom is interactive-only today)_
- [x] ISSUE-067: Silent-skip instrumentation must announce itself — unify the telemetry emitter and announce its fallback paths _(track: platform, P1, 1d — 2026-10 sprint retro, premise corrected 2026-10-10: the eval gate did not skip — PR #92 (2a93d09) had removed it before the sprint, so zero review_eval artifacts meant "component absent", which still proved no-signal reads as all-clear; telemetry emits remain inconsistent (hand-appended JSONL vs silent no-op))_
- [x] ISSUE-068: Discovered issues must enter the sprint queue's visibility automatically _(track: platform, P1, 0.5d — 2026-10 sprint retro: 063/064/065 were invisible to sprint_queue until the orchestrator hand-added Issue Progress rows)_

### Drop
- [x] ISSUE-024: Move runtime state to ${CLAUDE_PLUGIN_DATA} — **dropped 2026-06-22** (premise invalid: PLUGIN_DATA is a single global dir, wrong for per-project/per-worktree state) _(track: platform, P2, 1d)_
- [x] ISSUE-003: Cumulative learning memory MVP — promote review_lessons to structured store — **dropped 2026-07-16** (superseded by ISSUE-033: CC native persistent memory replaces the patterns.jsonl + preamble-injection design; review_lessons.md never accumulated an entry) _(track: platform, P1, 1.5d)_
- [x] ISSUE-008: Virtual monorepo wrapper — polyrepo team support — **dropped 2026-07-26** (speculative until a real polyrepo team hits friction; building it now is YAGNI. The virtual-monorepo *layout* pattern stays documented for teams that want it — see the ISSUE-008 detail; only the code-level routing support is dropped. Re-open with a fresh number if a team actually requests it) _(track: platform, P2, 1.5d)_

---

## Issue Detail

### ISSUE-001: Run telemetry MVP — JSONL trace from agent_state hook

> **Deferred 2026-06-14.** Telemetry needs N>1 sprint usage to produce meaningful signal — at single-user sub-monthly cadence, the data is a diary not a statistic. Un-defer when (a) sprint usage produces ≥10 runs/week, OR (b) a felt diagnostic gap appears ("which agent fails most often?" can't be answered by feel), OR (c) ISSUE-002 / ISSUE-008 actually moves to doing and needs telemetry as a prerequisite.
> **Un-deferred 2026-07-21 (condition (b) met), re-scoped to a minimal baseline.** The 030–033 harness changes need a before/after measurement, which is exactly the diagnostic gap clause (b) describes. Minimal scope for this pass: per-run tokens, turn count, checkpoint failures, and user-intervention count — enough to compare a benchmark issue run before and after each harness change. Out (moved to follow-up): flock/PIPE_BUF concurrency guarantees, `docs/telemetry_schema.md`, and the full `trace_query.py` query set (lead-time only). **Definition of done for work-order purposes: the hook lands AND one benchmark-issue baseline run is captured before ISSUE-030 starts.**
> **Done 2026-07-23 (minimal scope).** Delivered: (1) `agent_state.py` now appends **shape-only** events to `.claude/run/events.jsonl` — the previous version dumped the full hook payload, which leaked tool inputs (file contents, commands) into the trace; the slim schema keeps ts/event/session_id/agent_type/tool_name plus checkpoint arg extraction (`--skill/--phase/--issue`) with pass/fail from PostToolUse(Failure), guaranteeing <4KB lines and zero PII. (2) `UserPromptSubmit` wired into both hook surfaces (plugin `hooks.json` + standalone `settings.snippet.json`) for turn counting. (3) `scripts/trace_query.py summary [--json]` — per-session turns, tool calls/failures, subagent spawns by type, checkpoint runs/failures by phase, wall-clock. Lead-time-per-issue replaced by session wall-clock as the baseline proxy (issue-id events don't exist yet — follow-up). Tokens are not hook-visible: recorded from `claude -p --output-format json` usage alongside the trace, documented in the baseline. (4) **Baseline captured**: `docs/baselines/2026-07-23-diagnose-baseline.md` with the exact re-run recipe. Headline finding: the headless /diagnose run **bypassed the harness** (0 checkpoints, 0 subagents) while carrying 262k cache-read tokens of skill/preamble context — the clearest before-signal yet for 031 (gates don't bind) and 032 (context cost without behavior shaping). ISSUE-030's subagent-pin effect is NOT exercised by this benchmark; measure it on a /review or /implement run.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30)
- Priority: P1
- Estimate: 0.5d (minimal re-scope 2026-07-21; original full spec was 1.5d)
- Status: done
- Owner:
- Branch: issue/ISSUE-001-telemetry-minimal
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Every agent invocation, tool call, and skill phase emits a structured trace event to `.claude/runs/<run-id>.jsonl` (project-side, installed via install_project.sh — NOT in the `.claude-kit/` submodule source), enabling later metric extraction (lead time, retry rate, finding density) without touching agent prompts.

#### Scope (In/Out)
- In:
  - Extend `project/.claude/hooks/agent_state.py` to append JSONL trace events (agent_start, agent_end, tool_call, phase_transition).
  - New `scripts/trace_query.py` with basic queries: `lead-time <run-id>`, `agent-stats <run-id>`, `phase-histogram <run-id>`.
  - Trace schema documented in `docs/telemetry_schema.md`.
  - Unit tests for hook emission + query CLI.
- Out:
  - Dashboard / visualization (separate follow-up).
  - Cross-run aggregation / time-series DB (follow-up).
  - LLM-based event interpretation.

#### Acceptance Criteria (DoD — minimal re-scope; original full-spec ACs moved to follow-up)
- [x] Given any hooked session, when agents/tools run, then `.claude/run/events.jsonl` records SubagentStart/Stop, tool events, and UserPromptSubmit with `ts`/`session_id` — shape-only, no content fields. *(tests/test_run_telemetry.py)*
- [x] Given a trace, when `trace_query.py summary` runs, then per-session turns, tool calls/failures, subagent spawns, checkpoint runs/failures, and wall-clock are reported. *(session wall-clock stands in for lead-time in the minimal scope)*
- [x] Given the existing test suite, when run, then no existing test regresses; new hook tests cover emission + schema (PII-leak guard, checkpoint verdicts, CLI smoke).
- [x] Given ISSUE-030, when it starts, then a baseline run exists — `docs/baselines/2026-07-23-diagnose-baseline.md` (recipe + metrics + caveats).

#### Implementation Notes
- Reuse the existing `agent_state.py` hook plumbing — do not introduce a new hook surface.
- Append-safety under concurrent worktrees: POSIX `O_APPEND` only guarantees atomicity for writes ≤ `PIPE_BUF` (typically 4 KB on macOS/Linux). Cap each event payload to **< 4 KB** (schema validator enforces) **or** acquire `flock` on the run file before write. Document the chosen approach in `docs/telemetry_schema.md` and add a unit test that proves no line interleave under the chosen guarantee.
- Run-id = sprint start timestamp + short slug; surface it in `sprint_state.md` for cross-reference.
- Keep PII out of payloads — never log message bodies, only event shapes.

#### Tests
- [ ] Hook emits well-formed JSONL on agent start/end (unit).
- [ ] Concurrent worktrees writing to same run file do not corrupt lines (integration with 2 worktrees).
- [ ] `trace_query.py lead-time` returns correct value on a synthetic trace fixture.
- [ ] Schema validator rejects malformed events.

#### Rollback
Revert the hook patch and delete `scripts/trace_query.py` + `docs/telemetry_schema.md`. No data migration required since traces are append-only files.

---

### ISSUE-002: Workflow eval gate MVP — LLM-as-judge for review_notes quality

> **Deferred 2026-06-14.** Cluster D's role split (ISSUE-013) + Pilot Gate hardening (ISSUE-010) already raised reviewer signal quality through structural changes, not eval scoring. Eval gate adds ANTHROPIC_API_KEY dependency + token cost + self-grading loop risk (kit eval-ing kit's review). Un-defer when (a) a regression in review quality is felt and not explainable by the existing scope split, OR (b) a multi-reviewer setup needs an automated tie-break, OR (c) eval signal becomes the bottleneck blocking a downstream decision.
> **Design updated 2026-07-21 (no separate billing).** The judge runs via `claude -p` (headless CLI) on the user's existing Claude Code auth — NOT the Anthropic API. This removes the ANTHROPIC_API_KEY + `anthropic` SDK dependency and the separate-billing objection above; the remaining un-defer conditions stand. Recommended sequencing: after ISSUE-029, so the judge grades platform /code-review output rather than the kit grading its own review.
> **Done 2026-07-26.** Un-deferred once 029 landed (judge grades platform /code-review-fed notes, not the kit's own single-agent review — self-grading concern resolved). `scripts/eval_review.py`: I/O (gh pr diff, `claude -p`) split from pure functions (rubric load, verdict parse+derive, determinism overlap, report render) so the CLI path is thin and the logic is unit-tested without invoking the model. Rubric `templates/review_eval_rubric.md` (4 dimensions, JSON output contract). Verdict is **derived**, not trusted: a judge that returns "pass" while listing a missed Critical/High — or any dimension ≤2 — is normalized to `concerns`. Wired as non-blocking /ship step 8 (always exit 0; degraded-skip on missing CLI/notes; never fails the gate). Determinism `--runs N` = mean pairwise Jaccard overlap of Critical/High finding keys (≥80% floor; no temperature control on the CLI). 17 tests. **Live judge invocation not exercised in CI** (would call the model) — the report seeds ISSUE-033's memory layer schema as intended.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30)
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-002-eval-gate
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
A new `scripts/eval_review.py` runs an LLM-as-judge pass on a `review_notes.md` against the PR diff and emits a quality score + missed-finding list, wired into `/ship` as a non-blocking advisory.

#### Scope (In/Out)
- In:
  - `scripts/eval_review.py` that takes `(pr_number, review_notes_path)` and outputs a structured report (`docs/review_eval_<pr>.md`).
  - Rubric covering: critical/high finding coverage, false-positive rate, actionability, traceability to diff lines.
  - Wire as **non-blocking** advisory at the end of `skills/ship/SKILL.md` (warning only, never fails the gate).
  - Determinism check: re-run on the same input twice; report variance.
  - Unit tests for rubric parsing + advisory output formatting.
- Out:
  - Blocking enforcement (separate follow-up after we have baseline scores).
  - Eval for other artifacts (`design_audit.md`, `a11y_audit.md`) — follow-up issues.
  - Auto-improvement of `reviewer` agent prompt based on findings (follow-up).

#### Acceptance Criteria (DoD)
- [x] Given a PR with a known critical bug intentionally missed by the reviewer, when `eval_review.py` runs, then it flags the missed finding with severity + diff line reference. *(verdict derivation + missing-critical test; report renders severity + `diff_ref`)*
- [x] Given `/ship` runs on a PR, when complete, then the run log shows the eval advisory section (pass/concerns) without changing exit code. *(non-blocking step 8; always exit 0; wiring test)*
- [x] Given the same input run twice, when reports are compared, then critical/high findings overlap ≥80% (determinism floor documented). *(`--runs N` Jaccard overlap; floor in rubric + issue)*
- [x] Given `docs/review_eval_<pr>.md`, when read, then every concern cites a diff line range + rubric category. *(rubric output contract requires `diff_ref` + `rubric` on every entry; render includes them)*

#### Implementation Notes
- Judge invocation: `claude -p` headless with `--model` pinned and structured (JSON) output — a fresh process/context, so judge independence from the harness session holds without the API. **No separate billing**: never introduce an ANTHROPIC_API_KEY / `anthropic` SDK path (user decision 2026-07-21).
- Determinism caveat: the CLI exposes no temperature control, so the ≥80% overlap AC is the operative determinism floor — do not tighten it to exact-match.
- **Prerequisite + degraded mode**: requires the `claude` CLI on PATH with working auth. If missing, `/ship` prints a one-line warning (`eval skipped: claude CLI not available`) and **continues without blocking**. Never fail the ship gate on a missing eval dependency.
- Keep the rubric in `templates/review_eval_rubric.md` so it can be versioned and tuned without touching code.
- This eval is the seed for ISSUE-003's anti-pattern DB — design the report schema so memory layer can ingest it.

#### Tests
- [x] Rubric loader requires the 4 dimension headers, tolerates extra prose; rejects a truncated rubric.
- [x] "good review" fixture → pass; "missing critical" fixture → concerns with the flagged High + diff_ref.
- [x] Degraded mode: main() exits 0 with a warning when the CLI or notes are absent, and never blocks on a judge error.
- [x] Determinism harness: 2 mocked runs, overlap math correct; report renders the percentage.
- [x] /ship advisory wiring test (references eval_review.py, non-blocking, no-separate-billing).

#### Rollback
Remove the advisory block from `skills/ship/SKILL.md`, delete `scripts/eval_review.py` + `templates/review_eval_rubric.md`. No persistent state to clean up.

---

### ISSUE-003: Cumulative learning memory MVP — promote review_lessons to structured store

> **Dropped 2026-07-16 — superseded by ISSUE-033.** Claude Code shipped a native persistent memory directory; the patterns.jsonl + preamble-injection design below is obsolete, and `docs/review_lessons.md` never accumulated a single entry. Kept for design history.
> **Deferred 2026-06-14.** `docs/review_lessons.md` already exists as a markdown accumulation surface and `reviewer` reads it. Promoting to `patterns.jsonl` + preamble injection is a structure bet — the hypothesis is that structured-ness improves reviewer behavior, but the hypothesis is unverified. Also depends on ISSUE-002. Un-defer when (a) `review_lessons.md` grows past ~20 entries and contributors complain about navigating it, OR (b) preamble token budget for reviewer becomes a measured constraint, OR (c) a real pattern keeps recurring despite being in `review_lessons.md`, suggesting the markdown surface isn't getting consumed.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30)
- Priority: P1
- Estimate: 1.5d
- Status: drop (superseded by ISSUE-033, 2026-07-16)
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-002 (eval reports feed pattern extraction)

#### Goal
`docs/review_lessons.md` is replaced by a structured store (`.claude/memory/patterns.jsonl` + `docs/decision_log.md`) — same project-side location as ISSUE-001's traces, NOT inside the `.claude-kit/` submodule — that accumulates anti-patterns and architecture decisions across sprints, and `reviewer` + `planner` agents consume it as context.

#### Scope (In/Out)
- In:
  - Schema for two record types: `anti_pattern` (frequency, severity, last_seen, exemplar PRs) and `decision` (context, choice, trade-off, date).
  - `scripts/memory_promote.py` that scans `review_notes.md` + `review_eval_<pr>.md` outputs and promotes findings with Frequency ≥ 3 + Critical/High into `patterns.jsonl`.
  - Inject top-N relevant patterns into `reviewer` and `planner` agent context via a preamble hook (reuse `scripts/preambles.py`).
  - `decision_log.md` template + manual entry workflow (this MVP does not auto-extract decisions).
  - Tests for promotion thresholds + preamble injection.
- Out:
  - Per-codebase preference learning (functional vs OOP, etc.) — follow-up.
  - Semantic search over patterns (this MVP uses recency + frequency ranking).
  - Auto-extraction of decisions from PR descriptions (follow-up).
  - Migration of legacy `review_lessons.md` content — call it out in release notes, leave as-is.

#### Acceptance Criteria (DoD)
- [ ] Given 3+ `review_notes.md` files **from distinct PR numbers** with the same Critical finding category, when `memory_promote.py` runs, then `patterns.jsonl` contains exactly one consolidated `anti_pattern` record with frequency = 3 and exemplar PR list. Multiple findings in a single PR count as frequency = 1 for that PR.
- [ ] Given `patterns.jsonl` with ≥1 record, when `reviewer` agent runs on a new PR, then its preamble contains the top-N patterns (configurable, default N=5) selected by recency × frequency.
- [ ] Given `docs/decision_log.md`, when a new entry is appended manually, then format validator passes (date, context, choice, trade-off all present).
- [ ] Given a fresh repo with no memory, when agents run, then preamble injection degrades silently (no errors).

#### Implementation Notes
- Store path `.claude/memory/` is per-repo (project-side, populated by `install_project.sh`), gitignored by default (user can opt-in to commit). Document the trade-off in `README.md` memory section.
- **Frequency = distinct PR count**, not raw occurrence count. A single noisy PR repeating the same finding 5 times still contributes frequency 1 for that pattern. This prevents one bad PR from inflating rankings.
- Ranking function = `frequency × severity_weight × recency_decay` — keep it in one pure function so it's testable and tunable.
- Preamble injection must respect token budget — cap at ~500 tokens of memory context per agent.
- ISSUE-002's eval report is the highest-quality signal source; weight it higher than raw review_notes when promoting.

#### Tests
- [ ] Promotion threshold: 2 occurrences → not promoted, 3 → promoted, 3 with mixed severities → severity = max.
- [ ] Ranking function unit tests across edge cases (zero frequency, ancient last_seen).
- [ ] Preamble injection: agent context includes patterns when memory exists, omits cleanly when absent.
- [ ] Decision log validator rejects malformed entries.

#### Rollback
Delete `.claude-kit/memory/` and `scripts/memory_promote.py`; revert preamble hook changes. `review_lessons.md` is untouched so existing workflow continues.

---

### ISSUE-004: Sales pack file move + manifest schema
- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-004.md
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30 — sales pack is off-thesis vs "trustworthy code / AI dev team control plane" positioning. Split from original ISSUE-004 — install script work is ISSUE-009.)
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Sales-domain agents, skills, and templates are physically relocated into a `packs/sales/` subtree with a manifest declaring contents and dependencies. **No install script change yet** — that is ISSUE-009. This issue is a pure relocation + schema definition so the boundary exists on disk and future install changes have a stable target.

#### Scope (In/Out)
- In:
  - Move sales agents (`account-researcher`, `champion-mapper`, `discovery-coach`, `meeting-synthesizer`, `proposal-writer`) under `packs/sales/agents/` via `git mv`.
  - Move sales skills (`account-brief`, `discovery-prep`, `followup`, `meeting-capture`, `proposal`) under `packs/sales/skills/` via `git mv`.
  - Move sales-only templates (`account_brief.md`, `discovery_plan.md`, `meeting_notes.md`, `proposal.md`, `sales_email_persona.md`, `sales_lessons.md`, `followup.md`) under `packs/sales/templates/` via `git mv`.
  - Write `packs/sales/manifest.yaml` listing the moved files with explicit paths (agents / skills / templates / optional settings.snippet.json) and a top-level `depends_on: [core]`.
  - Write `packs/sales/README.md` describing the pack purpose, which core skills it expects (`/prd`, `/kickoff`, `/issue`, `/sprint`), and that opt-in install is provided by ISSUE-009.
  - Write `packs/README.md` (root-level pack guide) documenting the manifest schema, the `depends_on` model, and the additive-only rule (packs never substitute core).
  - `scripts/validate_pack_manifest.py` — pure parser/validator with no install side effects. Validates: YAML well-formed, each listed file exists, `depends_on` references exist (only `core` for now), no duplicate entries across packs.
  - Unit tests for the manifest validator (4 cases: valid manifest, missing file, unknown dep, duplicate entry).
- Out:
  - `install_project.sh` / `install_user.sh` changes — ISSUE-009.
  - `merge_settings.py` extension — ISSUE-009.
  - README counts / Packs section in top-level README — ISSUE-005.
  - **Spin-off to a separate `claude-sales-kit` repo — deliberately not pursued.** This kit is a monorepo with install-time pack boundaries, not a transitional state toward multi-repo. Shared primitives (`/prd`, `/kickoff`, `/issue`, `/sprint`, hooks, templates, install scripts) are heavily reused by sales workflows; splitting them would require version-matrix management between repos and lose the ability to fix cross-cutting changes in a single PR. Revisit only if (a) sales evolves into a self-contained workflow that barely uses core, (b) audience/compliance forces a hard separation, or (c) release cadences diverge sharply.
  - Per-pack version pinning.
  - Deletion of sales code — this is a move, not a remove.

#### Acceptance Criteria (DoD)
- [ ] Given the repo, when `ls packs/sales/agents/ packs/sales/skills/ packs/sales/templates/` runs, then it shows exactly the moved entries listed above.
- [ ] Given `agents/` and `skills/` at the top level, when listed, then no sales-named entry remains there (move is complete, not duplicated).
- [ ] Given `packs/sales/manifest.yaml`, when `scripts/validate_pack_manifest.py` runs, then it exits 0 and prints the parsed file list.
- [ ] Given a manifest pointing to a nonexistent file, when validator runs, then it exits non-zero with the missing path named.
- [ ] Given a manifest with `depends_on: [nonexistent]`, when validator runs, then it exits non-zero naming the missing dep.
- [ ] Given `git log --follow packs/sales/agents/proposal-writer.md`, when run, then prior history at the old path is preserved.
- [ ] Given existing integration tests for agents/skills frontmatter, when run, then they still pass under the new layout (they should walk all directories, including `packs/`).

#### Implementation Notes
- Use `git mv` for every file so blame survives — never copy+delete.
- Manifest schema (documented in `packs/README.md`):
  ```yaml
  name: sales
  depends_on: [core]
  agents: [account-researcher.md, champion-mapper.md, ...]
  skills: [account-brief, discovery-prep, ...]
  templates: [account_brief.md, ...]
  settings_snippet: settings.snippet.json   # optional
  ```
- The validator is the single source of truth for the schema — ISSUE-009's install script imports/calls it rather than re-parsing.
- Status line (`cc-statusline.py`) and any other consumer that walks `agents/` must also walk `packs/*/agents/` after this move. Audit and fix in this issue (small grep job).
- Existing CONTRIBUTING.md and PRD docs may reference sales agents at the old path — grep and update.
- This issue does NOT touch the main README — ISSUE-005's job.

#### Tests
- [ ] Validator: valid manifest passes.
- [ ] Validator: missing file path fails with the path named.
- [ ] Validator: unknown `depends_on` fails with the missing dep named.
- [ ] Validator: duplicate entry across packs fails (future-proofing — for now sales is alone, but the rule should be active).
- [ ] Agent/skill frontmatter walker discovers entries under `packs/sales/`.
- [ ] `cc-statusline.py` runs without error when sales agents live under `packs/sales/`.

#### Rollback
`git revert` the move commit; the manifest validator and `packs/` directory become orphaned but inert. No installer behavior is changed yet (ISSUE-009 hadn't landed) so no user-facing regression.

---

### ISSUE-005: README sync — reflect actual counts + new positioning + post-sales-boundary layout
- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-005.md
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30)
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-004 (file move must land before counts and Packs section are accurate), ISSUE-009 (install flag must exist before Installation section can document `--pack`)

#### Goal
`README.md` accurately reflects the post-boundary kit: correct agent/skill counts, sharpened positioning ("trustworthy code in collaboration → AI dev team control plane"), brainstorm/bizanalysis demoted to optional pre-PRD, sales pack documented as an opt-in pack with its own install flag, and a new **Team-scale usage** section explaining how teams adopt the kit at monorepo and polyrepo scale.

#### Scope (In/Out)
- In:
  - Update opening tagline + "Why claude-kit?" to match the new positioning.
  - Replace stale counts ("33 agents / 22 skills") with current values after ISSUE-004 split (core count + sales pack count separately).
  - Add a "Packs" section explaining core (default) vs sales (opt-in via `--pack=sales`).
  - Update agent table and skill table to mark sales entries clearly (or move to a sub-table inside the Packs section).
  - Demote `/brainstorm` and `/bizanalysis` to an "Optional pre-PRD" sub-section (still listed, but golden path starts at `/prd`).
  - Add a brief "Roadmap" subsection referencing ISSUE-001/002/003/006/007 as the upcoming control plane + spec layer (telemetry → eval → memory → spec/release).
  - Update Installation section to document `--pack` flag.
  - Sync Decision Tree to match (sales workflows either removed from main tree or routed via opt-in pack note).
  - **Team-scale usage section** documenting two adoption patterns and the rationale for NOT introducing a separate "team layer":
    - **Pattern (a) Monorepo**: engineering teams put services under `services/<name>/` in one repo; sales teams put accounts under `accounts/<company>/` in one repo. The repo IS the team boundary; the kit installs once at the root.
    - **Pattern (b) Virtual monorepo wrapper** (polyrepo teams): a top-level wrapper directory contains `.claude-kit/` + shared state (`issues.md`, `sprint_state.md`, `STATUS.md`) at its root, and each git repo lives as an immediate subdir (`auth-service/`, `gateway-service/`, ...). Per-service work routes to the right subdir; the wrapper itself is also a git repo with the service subdirs in `.gitignore`. Cross-reference ISSUE-008 for the code-level support.
    - **Why no separate "team layer"**: an additional layer would raise onboarding cost (more concepts, more install steps) without adding capability the subdirectory pattern doesn't already provide. The existing core+sales additive model + the wrapper pattern cover both adoption shapes. Document this explicitly so future contributors don't re-propose a "team pack".
- Out:
  - CONTRIBUTING.md rewrite (separate follow-up).
  - Translated versions / docs site.
  - Logo / branding refresh.
  - Sales pack's own README (lives in `packs/sales/README.md`, handled in ISSUE-004).

#### Acceptance Criteria (DoD)
- [ ] Given the updated README, when agent/skill counts are checked against `ls agents/ skills/` (excluding `packs/`), then the numbers match exactly.
- [ ] Given the README, when the opening section is read, then the words "trustworthy" and "control plane" (or Korean equivalents if bilingual) appear in the positioning paragraph.
- [ ] Given the Decision Tree, when followed top-to-bottom, then no sales-specific entry appears in the default engineering path; sales appears only under an explicit "Sales pack (opt-in)" branch.
- [ ] Given the Installation section, when read, then `--pack=core|sales|all` is documented with examples.
- [ ] Given the Roadmap section, when read, then it references ISSUE-001/002/003/006/007 without committing to dates.
- [ ] Given the Team-scale usage section, when read, then both patterns (monorepo, virtual monorepo wrapper) are shown with concrete directory examples, and the rationale for not adding a "team layer" is stated.

#### Implementation Notes
- Do not rewrite from scratch — surgical edits to preserve existing structure that already works (Core Use Cases, Workflow, Skill Orchestration sections).
- Counts: when ISSUE-004 lands, run `ls agents/ skills/ packs/sales/agents/ packs/sales/skills/` and use those numbers literally. Avoid hand-counting.
- "Roadmap" subsection should be 3 bullets max — telemetry / eval / memory, one sentence each. Link to the issue IDs, not to dates.
- Keep `docs/PRD_agent_system_v0.md` reference in Project Structure — that's a kit-internal PRD and stays.
- Verify badge counts at top of README (e.g., "530 tests passing") — re-run `pytest` and update if stale.

#### Tests
- [ ] Markdown link checker: no broken internal links in README after edit.
- [ ] Count assertion script: parses the README's claimed counts and compares to filesystem; fails if mismatch (consider adding as a CI check).
- [ ] Manual smoke: read the README top-to-bottom as a new user; confirm the engineering golden path is obvious within the first screenful.

#### Rollback
`git revert` the README commit. No code or config depends on README content, so revert is purely cosmetic.

---

### ISSUE-006: /spec skill — RFC pattern + Spec-Required metadata + non-sprint HOLD gate
- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-006.md
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — tech spec layer between PRD and implement for cross-team features)
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
A new `/spec` skill writes `docs/specs/SPEC-NNN.md` (Problem / Options ≥2 / Trade-offs / Decision / Migration / Rollback / Open Questions) for features flagged `Spec-Required: true`. Adds the metadata fields to the issue template, the conventions exception (2 PRs non-sprint vs 1 bundled PR sprint), and a non-sprint HOLD gate when invoked standalone without a SPEC for a required issue.

#### Scope (In/Out)
- In:
  - New `skills/spec/SKILL.md` reading the target issue from `issues.md` plus relevant context (`docs/architecture.md`, `docs/ux_spec.md`, related code via grep) and producing a SPEC document.
  - `templates/spec.md` with required sections: Problem / Options (≥2 named, each with measurable trade-off statements like "+20% write latency, -1 service dependency") / Decision / Trade-offs accepted / Migration / Rollback / Open Questions.
  - Issue template additions: `Spec-Required: true | false` (default false), `Spec: <path | none>`.
  - `scripts/validate_issues.py` enforces: if `Spec-Required: true` AND issue Status in `{doing, waiting, done}`, then `Spec:` must reference an existing file.
  - `/spec ISSUE-NNN` standalone invocation: if SPEC exists, refuses without `--rewrite`; with `--rewrite`, regenerates.
  - `/spec` with no arg: creates `docs/specs/SPEC-NNN.md` with auto-incremented number, no issue linkage.
  - Conventions block in `issues.md` documents the 2-PR-non-sprint / 1-PR-sprint exception.
  - Branch convention recorded: spec PR uses `issue/ISSUE-NNN-spec`, impl PR uses `issue/ISSUE-NNN`.
  - Unit tests for spec template renderer + `validate_issues.py` Spec-Required enforcement.
- Out:
  - `/implement` spec gate logic — ISSUE-007.
  - Auto-detection of "should this issue be Spec-Required" — ISSUE-007.
  - Spec-on-spec (RFC of RFC) recursion.
  - Backfilling SPECs for already-merged issues.

#### Acceptance Criteria (DoD)
- [ ] Given an issue with `Spec-Required: true` and no SPEC file, when user runs `/spec ISSUE-NNN`, then `docs/specs/SPEC-NNN.md` is written with all required sections, ≥2 named options, and each option carries an explicit measurable trade-off line.
- [ ] Given a SPEC already exists, when `/spec ISSUE-NNN` runs again without `--rewrite`, then the skill refuses with a message naming the existing file and the `--rewrite` flag; with `--rewrite` it proceeds.
- [ ] Given `/spec` with no argument, when run, then a SPEC with auto-incremented number is written and no issue field is mutated.
- [ ] Given an issue is `done` with `Spec-Required: true` but `Spec: none`, when `validate_issues.py` runs, then it exits non-zero with a clear error naming the issue.
- [ ] Given the `issues.md` conventions block, when read, then the 2-PR exception for non-sprint Spec-Required issues and the branch naming rule are documented.

#### Implementation Notes
- SPEC numbering matches the issue when linked (SPEC-007 ↔ ISSUE-007); ad-hoc SPECs use their own monotonic `SPEC-` counter independent of issues.
- The template renderer MUST reject options that lack a measurable trade-off statement (heuristic: at least one numeric or "+/-" comparator in the trade-off line). This is the slop-prevention guarantee that keeps SPECs useful.
- The skill must NOT modify any file beyond the SPEC itself and the target issue's metadata (to set `Spec:`).
- When sprint mode auto-runs `/spec` (per ISSUE-007), the commit message must be `docs(spec): SPEC-NNN — <decision summary>` so the bundled PR's history is readable.
- `/review` reads SPEC when present and adds a "Spec compliance" section to `review_notes.md` (this hook lives here, not in ISSUE-007, so review behavior follows the skill even without the implement gate).

#### Tests
- [ ] Template renders fully when all input fields present.
- [ ] Template renderer rejects an options list with fewer than 2 entries.
- [ ] Template renderer rejects an option missing a measurable trade-off line.
- [ ] `validate_issues.py`: `Spec-Required: true` + `done` + `Spec: none` → fail.
- [ ] `validate_issues.py`: `Spec-Required: true` + `doing` + `Spec: docs/specs/SPEC-007.md` (exists) → pass.
- [ ] `/spec` with no argument: produces auto-numbered SPEC.
- [ ] `/spec ISSUE-NNN` against existing SPEC: refuses; with `--rewrite`: proceeds.

#### Rollback
Delete `skills/spec/`, `templates/spec.md`, revert `validate_issues.py` and `issues.md` conventions changes. Existing SPECs under `docs/specs/` remain on disk (harmless) but are no longer enforced.

---

### ISSUE-007: /implement spec gate — sprint auto-run + non-sprint HOLD + signal detection
- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-007.md
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — decision table for sprint vs non-sprint Spec-Required handling)
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-006

#### Goal
`/implement ISSUE-NNN` gates on the issue's `Spec-Required` field. In sprint mode, missing SPEC for a required issue triggers auto-run of `/spec` then continues (single bundled PR). In non-sprint mode, the same condition triggers a 3-way HOLD prompt. Signal-based recommendations (API/schema/migration keywords, estimate-at-cap, new dep) surface but never auto-block.

#### Scope (In/Out)
- In:
  - `/implement` Phase 0 (pre-context) gate logic implementing the full decision table from conversation 2026-06-13.
  - Mode detection: sprint mode = env `KIT_SPRINT_MODE=1` (set by `/sprint` before invoking `/implement`); otherwise non-sprint.
  - Signal scanner: regex/keyword detection on issue body for `api`, `schema`, `migration`, `breaking`, `protocol`, `데이터모델`, new-dependency mentions (`add`, `new package`, etc.); plus estimate-equals-cap (`Estimate: 1.5d`).
  - Sprint auto-mode: when `Spec-Required: true` and SPEC missing, invoke `/spec ISSUE-NNN` inline on the same branch, then continue with `/implement`. Single PR carries both the SPEC commit (`docs(spec): SPEC-NNN — ...`) and the impl commits.
  - Non-sprint HOLD: present a 3-way choice via `AskUserQuestion` — (1) run `/spec` now and resume; (2) flip `Spec-Required` to false with a recorded reason; (3) cancel.
  - `--skip-spec-gate` CLI flag bypasses both gates in any mode and emits a `spec_gate_bypassed` telemetry event (uses ISSUE-001 schema).
  - Telemetry events added: `spec_gate_triggered`, `spec_gate_hold`, `spec_gate_auto_ran`, `spec_gate_bypassed` — documented in `docs/telemetry_schema.md`.
  - Unit tests covering every row in the decision table.
- Out:
  - `/spec` skill itself — ISSUE-006.
  - Auto-mutation of `Spec-Required` based on signals (signals only recommend; they never write to the field unless the user picks option 2 in the HOLD).
  - Bundling spec + impl in non-sprint mode (non-sprint deliberately keeps the 2-PR pattern).

#### Acceptance Criteria (DoD)
- [ ] Given sprint mode (`KIT_SPRINT_MODE=1`) + `Spec-Required: true` + no SPEC, when `/implement` runs, then `/spec` is invoked first on the same branch, SPEC-NNN.md is created, and `/implement` continues without user prompt.
- [ ] Given non-sprint mode + same inputs, when `/implement` runs, then it HOLDs with a 3-way prompt. On (1) it runs `/spec` then resumes; on (2) it sets `Spec-Required: false` with the recorded reason in issue notes; on (3) it exits cleanly.
- [ ] Given `Spec-Required: false` + ≥1 signal detected + sprint mode, when `/implement` runs, then a recommendation event is logged to telemetry and execution proceeds without prompting.
- [ ] Given `Spec-Required: false` + ≥1 signal detected + non-sprint mode, when `/implement` runs, then the user is prompted (no default) and the choice is recorded.
- [ ] Given `--skip-spec-gate` in any mode, when `/implement` runs, then both gates are bypassed and a `spec_gate_bypassed` telemetry event is emitted.
- [ ] Given the decision table, when the test suite runs, then every row has a passing test.

#### Implementation Notes
- `KIT_SPRINT_MODE` is set by the `/sprint` skill (single-line export before invoking implement). Document in `skills/sprint/SKILL.md`.
- The HOLD prompt must use `AskUserQuestion`-style structured choice — do not parse free text.
- Sprint auto-run commit sequence: `docs(spec): SPEC-NNN — <decision summary>` (from `/spec`) → impl commits (from `/implement`). PR description must include a SPEC excerpt at the top.
- `/review` (from ISSUE-006) reads SPEC and adds "Spec compliance" findings; this issue does NOT modify `/review`.
- Signal scanner returns a list of `{signal, evidence}` pairs — the recommendation log includes this list verbatim so users can see WHY a spec was recommended.

#### Tests
- [ ] Decision table coverage: one test per row.
- [ ] Sprint auto-run produces a single PR with both spec commit and impl commits in correct order.
- [ ] Non-sprint HOLD: simulate user choices (1, 2, 3) and verify the resulting state transitions and on-disk effects.
- [ ] Signal scanner unit tests: api / schema / migration / breaking / protocol / cap-estimate / new-dep.
- [ ] `--skip-spec-gate` emits the bypass event regardless of mode.
- [ ] No prompt fires when `Spec-Required: false` and no signal hits.

#### Rollback
Revert `/implement` gate logic; the signal scanner and `--skip-spec-gate` flag become inert. `/spec` skill (ISSUE-006) continues to work standalone. No issue-metadata migration needed since `Spec-Required` defaults to false.

---

### ISSUE-008: Virtual monorepo wrapper — polyrepo team support

> **Deferred 2026-06-14.** Already gated on ISSUE-001 telemetry, which itself is now deferred. The wrapper pattern is **documented** in README's Team-scale usage section (ISSUE-005) — users who want it today can adopt the pattern manually without code support. Un-defer when (a) a real polyrepo team adopts the kit and surfaces friction with the manual pattern, OR (b) ISSUE-001 lands and produces signal showing polyrepo path-resolution errors.
> **Dropped 2026-07-26.** Building code-level polyrepo routing before any team hits friction is YAGNI — the manual virtual-monorepo *layout* (documented below + in README) is enough for anyone who wants it today, and ISSUE-001 landed without producing a single polyrepo path-resolution error. The design notes below stay as a reference for a future re-open (fresh number) if a real team requests it.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- PRD-Ref: none (kit self-development; rationale in conversation 2026-05-30 — polyrepo team friction; deferred until measured)
- Priority: P2
- Estimate: 1.5d
- Status: drop (2026-07-26 — YAGNI; manual layout suffices; re-open with a fresh number on real demand)
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-001 (telemetry signal needed before justifying this work)

#### Goal
Polyrepo teams can wrap multiple independent git repos in a top-level "virtual monorepo" directory that holds shared kit state (`issues.md`, `sprint_state.md`, `STATUS.md`) and the `.claude-kit/` installation at the wrapper root. Each service subdir stays an independent git repo. Per-service work routes to the right subdir automatically.

#### Scope (In/Out)
- In:
  - "Wrapper root" detection concept: walk upward from `pwd` to find the closest ancestor containing `.claude-kit/`. If that ancestor is distinct from `git rev-parse --show-toplevel`, it is the wrapper root; otherwise the layout is a normal single repo and wrapper-aware code falls back transparently.
  - Issue template field `Target-Service: <subdir-name | none>` (default none = single-repo behavior).
  - `scripts/worktree.sh` `--service <name>` flag: when set, the worktree is created at `<wrapper-root>/<service>/.worktrees/issue-NNN/` against that service's git repo; `gh pr create` runs in that service repo.
  - `scripts/list_services.sh`: enumerates wrapper-root immediate subdirs that contain `.git/` and prints their names.
  - `scripts/flock_edit.sh` corrected to lock files at wrapper root (issues.md, sprint_state.md, STATUS.md) regardless of which service subdir `pwd` is in.
  - `docs/wrapper_usage.md` documenting the structure with the `~/work/my-team/` example tree and the wrapper's own `.gitignore` rules (service subdirs ignored, kit state tracked).
- Out:
  - Auto-creating service git repos (user does this manually).
  - Cross-service git operations (each service PR is independent).
  - Migrating an existing monorepo into wrapper form.
  - Wrapper-level CI orchestration (out of scope for this MVP).

#### Acceptance Criteria (DoD)
- [ ] Given a wrapper-root layout with 3 service subdirs each holding `.git/`, when `scripts/list_services.sh` runs, then it lists exactly those 3 services and skips non-repo subdirs.
- [ ] Given ISSUE-NNN with `Target-Service: auth-service`, when `/implement` runs in wrapper mode, then the worktree is created at `<wrapper-root>/auth-service/.worktrees/issue-NNN/` and `gh pr create` is invoked in that service's repo.
- [ ] Given two concurrent `/implement` calls editing `issues.md` from different service subdirs, when both complete, then `issues.md` at the wrapper root contains both edits (flock at wrapper root, not at service-repo toplevel).
- [ ] Given a non-wrapper layout (`.claude-kit/` parent equals `git rev-parse --show-toplevel`), when wrapper-aware scripts run, then they fall back to today's single-repo behavior with no errors.
- [ ] Given `docs/wrapper_usage.md`, when read, then the directory example, the `.gitignore` rules, and the per-service work routing flow are all present.

#### Implementation Notes
- Wrapper-root detection lives in a single helper (`scripts/find_wrapper_root.sh` or Python equivalent) so every consumer uses the same logic. Tests live alongside.
- `Target-Service:` field default = none → routing helpers no-op → single-repo behavior preserved.
- This issue is **P2 and gated**: do not pick up until ISSUE-001 telemetry shows real polyrepo friction (e.g., a meaningful number of `flock` resolution errors or path mismatches from polyrepo users).
- Do NOT introduce a "team layer" concept — the wrapper directory is itself the team boundary; adding another abstraction would add onboarding cost without capability gain (rationale documented in ISSUE-005's Team-scale usage section).

#### Tests
- [ ] Wrapper-root detection: nested layout returns wrapper root; flat layout returns git toplevel; mixed cases handled.
- [ ] `list_services.sh`: skips subdirs without `.git/`; finds direct-child `.git/` dirs; ignores `.worktrees/` and similar.
- [ ] `worktree.sh --service`: worktree path correct; worktree registered in correct service repo.
- [ ] `flock_edit.sh`: lock file path resolves to wrapper root when running from a service subdir.
- [ ] Single-repo fallback: existing single-repo tests pass unchanged.

#### Rollback
Revert wrapper-root detection across scripts. `Target-Service:` becomes vestigial metadata that downstream code ignores. No file moves or data migrations are required.

---

### ISSUE-009: Install script --pack flag + merge_settings + tests
- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-009.md
- PRD-Ref: none (kit self-development; split from original ISSUE-004 — installer behavior layer on top of ISSUE-004's file move)
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-004

#### Goal
`install_project.sh` and `install_user.sh` gain a `--pack=<core|sales|all>` flag (default `core`). They read each `packs/<name>/manifest.yaml` (using ISSUE-004's validator), enforce `depends_on`, and copy only the manifest-listed files. `merge_settings.py` merges pack-scoped `settings.snippet.json` after core's in a documented order. A migration note is printed when a legacy top-level sales path is detected.

#### Scope (In/Out)
- In:
  - `--pack=<name>` flag with values `core` | `sales` | `all` (extensible). Default `core`. Multiple `--pack` flags allowed but de-duplicated; selecting any non-core pack always includes core (because every pack has `depends_on: [core]`).
  - Install flow ordering: core first, then non-core packs in alphabetical order (deterministic). Settings overlay follows the same order.
  - `merge_settings.py` extended to merge `packs/<name>/settings.snippet.json` if present, with pack values **overriding** core values on key collision. Override policy documented in `packs/README.md`.
  - Error paths:
    - Unknown pack name → list available packs and exit non-zero.
    - Unsatisfied `depends_on` → name the missing dep and exit non-zero.
    - Manifest entry pointing at a missing file → name the path and exit non-zero (delegates to ISSUE-004 validator).
  - Re-install migration note: when a sales-named agent or skill is found at the legacy top-level path (`agents/account-researcher.md` etc.), print a one-line note telling the user to delete the old file (do NOT auto-delete).
  - Telemetry hook (uses ISSUE-001 schema): emit `install_pack` event per pack installed so adoption can be measured.
  - Integration tests over a tmpdir: default (no flag), `--pack=sales`, `--pack=all`, `--pack=unknown`, depends_on failure, settings collision, settings non-collision, legacy-path migration note.
- Out:
  - Pack uninstall (follow-up).
  - Per-pack version pinning.
  - Mid-session pack switching.
  - File moves themselves (ISSUE-004 owns this).
  - Top-level README updates (ISSUE-005).

#### Acceptance Criteria (DoD)
- [ ] Given a fresh tmpdir, when `bash install_project.sh` (no flag) runs, then `.claude/agents/` and `.claude/skills/` contain core entries only.
- [ ] Given `--pack=sales`, when run, then `.claude/` contains both core entries AND every sales pack entry listed in `packs/sales/manifest.yaml`.
- [ ] Given `--pack=all`, when run, then `.claude/` contains the union of every declared pack.
- [ ] Given `--pack=unknown`, when run, then the script exits non-zero and the error message lists the available packs.
- [ ] Given a manifest with `depends_on: [nonexistent]`, when install runs, then it exits non-zero and names the missing dep.
- [ ] Given core and sales each declaring an overlapping settings key, when `merge_settings.py` runs after install, then the merged settings file shows the pack value (sales) winning, and `packs/README.md` documents that this is the rule.
- [ ] Given a tmpdir with a legacy `agents/account-researcher.md` present, when install runs with default flag, then a one-line migration note is printed naming the legacy path; the file is NOT auto-deleted.
- [ ] Given the test suite, when run, then every existing test passes and every new install-flag test case passes.

#### Implementation Notes
- Use a tiny Python YAML parser (PyYAML — already an acceptable dep in the kit) rather than shelling out to `yq` to keep the install path dependency-light on fresh machines.
- Reuse ISSUE-004's `scripts/validate_pack_manifest.py` from the installer rather than re-implementing parsing.
- Symmetric handling in `install_user.sh` only if a user-level sales asset turns up during impl; otherwise document that user-level installs are core-only for now.
- The install_pack telemetry event lets ISSUE-001 measure adoption — without it we cannot prioritize future packs based on data.

#### Tests
- [ ] Default flag → core only, sales paths absent.
- [ ] `--pack=sales` → core + sales together (dependency satisfied).
- [ ] `--pack=all` → union of all declared packs.
- [ ] `--pack=unknown` → exits non-zero with usable error.
- [ ] Unsatisfied `depends_on` → exits non-zero, names missing dep.
- [ ] `merge_settings`: colliding keys → pack value wins, documented behavior.
- [ ] `merge_settings`: non-colliding keys → both present in output.
- [ ] Legacy-path migration note printed when `agents/account-researcher.md` exists at top level.
- [ ] `install_pack` telemetry event emitted for each pack installed.

#### Rollback
Revert install script changes. Old default ("install everything") was already replaced once by ISSUE-004's file move (no top-level sales files remain), so reverting THIS issue's installer changes simply makes the installer ignore packs entirely — a no-op for core, and sales becomes uninstalled but the files still exist under `packs/sales/`. Re-running with the reverted installer is safe.

---

### ISSUE-010: Pilot Gate hardening — separate-context critic + auto-cycle + neutral observation + specificity check
- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-010.md
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — Phase 5A self-critique has sycophancy + leading-question + closed-loop + missing-specificity defects identified by external reviewer)
- Priority: P2
- Estimate: 1.5d
- Status: done
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none (relies on `design-auditor` name, which ISSUE-013 explicitly preserves)

#### Goal
Phase 5A pilot critique is rebuilt to (1) precede judgment with a neutral observation pass, (2) run the visual critique in a **separate-context** `design-auditor` Task invocation, (3) add a product-specificity check requiring ≥3 details uniquely meaningful to this product/domain/user, and (4) enforce up to 3 automatic critique→patch→re-render cycles before the user gate fires.

#### Scope (In/Out)
- In:
  - Phase 5A Step 2 rewritten with 4 sub-steps:
    - **Step 2.0 — Neutral observation**: critic agent describes 5 visible facts from each pilot PNG **without referencing the design philosophy, signature move, aesthetic name, or archetype**. Output: `observations.md` per pilot. Banned vocabulary listed inline in the prompt.
    - **Step 2.1 — Separate-context critique**: invoke `design-auditor` via the Task tool (`subagent_type: design-auditor`) with the PNG + observations as input. The auditor does NOT inherit the generator's context. Returns a scored critique with evidence citing specific observations.
    - **Step 2.2 — Specificity check**: critique agent answers: "Name 3 details in this screen that ONLY make sense for THIS specific product/domain/user. Generic UI primitives don't count. If 0–1 → FAIL." Domain artifacts qualify (e.g., the literal_quote from ISSUE-012, domain-specific units, real entity names).
    - **Step 2.3 — Auto-correction cycle**: if any critique dimension fails OR specificity FAILs, the generator patches at the correct level (philosophy/tokens/CSS), re-renders, and the loop repeats. **Hard cap N=3 cycles.** After cycle 3, surface to the user with the cycle-by-cycle history.
  - Skill doc (`skills/uiux/SKILL.md`) updated Phase 5A section to reflect the 4 sub-steps; same change propagated to mobile and desktop variants.
  - Telemetry events (uses ISSUE-001 schema): `pilot_observation`, `pilot_critique`, `pilot_specificity`, `pilot_cycle_n`, `pilot_user_gate`, `pilot_degraded` (no-backend fallback).
  - **No-backend degraded mode**: if `screenshot_pilot.py` cannot capture, fall back to text-only critique reading the HTML source, with a `pilot_degraded` telemetry tag. **Never silently skip** the critique step.
  - Unit tests per sub-step prompt contract + cycle counter + degraded mode.
- Out:
  - Multi-direction parallel pilots (issue #1 in critique — deliberately deferred; reviewer's strongest call but conflicts with prior decision).
  - Token extraction inversion (issue #6 in critique — separate refactor scope).
  - Reference Anchor changes (ISSUE-012).
  - WebFetch correctness (ISSUE-011).

#### Acceptance Criteria (DoD)
- [ ] Given a pilot PNG, when Step 2.0 runs, then `observations.md` contains 5 facts and the banned-vocabulary lint (no `signature`, `aesthetic`, `archetype`, `philosophy` tokens) passes.
- [ ] Given observations + PNG, when Step 2.1 runs, then a Task invocation with `subagent_type: design-auditor` returns a structured critique; the critique's evidence field references at least one observation by index.
- [ ] Given Step 2.2, when the critique agent runs the specificity check, then it returns either exactly 3+ named product-specific details OR an explicit FAIL with a reason; never a vague pass.
- [ ] Given a failing critique on cycle 1, when Step 2.3 runs, then a patch is applied at one of {philosophy, tokens, CSS}, the pilot re-renders, and re-critiques. The cycle counter increments and stops at N=3.
- [ ] Given 3 cycles all failing, when the user gate fires, then the user sees the cycle history (what was tried each cycle and what still fails).
- [ ] Given no screenshot backend, when Phase 5A runs, then text-only critique runs with `pilot_degraded` telemetry tag — never a silent skip.
- [ ] Given existing Phase 5B tests, when run, then none regresses.

#### Implementation Notes
- The separate-context critic must be a real Task invocation — NOT an inline sub-prompt sharing the conversation. The `design-auditor` agent file already exists; ISSUE-013 sharpens its role but preserves the name.
- Step 2.0 prompt must explicitly list banned vocabulary; a simple regex post-check catches violations.
- Specificity FAIL: 0 or 1 named details = FAIL. Naming must be concrete (e.g., "the order ID 47.2-A in mono", "the unit '회' in the quantity selector") — not roles ("primary CTA", "user avatar").
- Hard 3-cycle cap is a backstop against runaway auto-correction. Telemetry surfaces 3-cycle-fail rates so we can later tune the patch quality.
- Patch level inference: dimension-based — if color/scale fails → tokens; if vocabulary/voice fails → philosophy; if composition fails → CSS. Document the mapping.

#### Tests
- [ ] Step 2.0 banned-vocabulary regex enforcement.
- [ ] Step 2.1: Task tool invoked with correct `subagent_type` and inputs.
- [ ] Step 2.2 FAIL on 0/1 details; PASS on 3+ properly-named details.
- [ ] Cycle counter increments through 3, hard-stops at 3.
- [ ] User gate fires with cycle history when 3 cycles fail.
- [ ] Degraded mode emits `pilot_degraded` event and runs text-only critique without raising.
- [ ] All three uiux skills (web/mobile/desktop) updated consistently.

#### Rollback
Revert Phase 5A changes in `skills/uiux/SKILL.md` (+ mobile/desktop). Step 2 reverts to single-pass self-critique. Telemetry events become inert. No data migration.

---

### ISSUE-011: Kill WebFetch reference fabrication — image-grounded references only
- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-011.md
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — WebFetch returns parsed text only; asking the model to extract hex values "from a Dribbble URL" via WebFetch is fabrication regardless of the "(indirect)" label)
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Phase 2 step 6.5 (Reference Anchor research) stops using WebFetch to "read" visual references. References must arrive as actual pixels — either user-provided image inputs or headless-captured screenshots of a page URL — and the Reference Anchor step is **skipped explicitly with a warning** when no image is available, never filled in with WebFetch text.

#### Scope (In/Out)
- In:
  - Phase 2 step 6.5 rewritten with two input paths:
    - **Path (a) — user-provided images**: 1–3 image URLs or local paths; `/uiux` reads them via the Read tool (image input) and extracts visual facts from actual pixels.
    - **Path (b) — auto-captured pages**: if the user provides a non-image URL (HTML page), invoke `scripts/capture_reference.py <url>` to headless-capture the page to PNG, then Read the PNG.
  - **Path (c) — neither available**: Reference Anchor step is **skipped entirely** with a one-line warning to the user explaining what to provide. Design philosophy proceeds without an anchor section.
  - New `scripts/capture_reference.py`: thin wrapper over `screenshot_pilot.py` capture logic. Takes URL + output path, saves to `docs/references/<slug>.png`.
  - Remove the "(indirect)" labeling from Phase 2 step 6.5 in `skills/uiux/SKILL.md` and mobile/desktop equivalents — the category does not exist anymore.
  - `templates/design_philosophy.md` updated: each cited anchor MUST reference an image file path under `docs/references/`. Empty `cues_to_adopt` is acceptable (means anchor step skipped); fabricated cues are not.
  - Unit tests for capture wrapper + the skip-with-warning behavior + grep test ensuring no WebFetch call remains in any uiux skill for the purpose of reference description.
- Out:
  - Reference Anchor tuning (5 → 2-3 + literal quote) — ISSUE-012.
  - Pilot Gate critique restructuring — ISSUE-010.
  - Interview skip-path hardening (issue #8 in critique — not requested).

#### Acceptance Criteria (DoD)
- [ ] Given user provides 2 image URLs, when Phase 2 step 6.5 runs, then both images are Read directly and extracted facts cite actual image content.
- [ ] Given user provides an HTML page URL, when Phase 2 runs, then `capture_reference.py` is invoked, the PNG is saved under `docs/references/`, and Read is called on the PNG (not on the URL).
- [ ] Given neither images nor URLs are provided, when Phase 2 runs, then the Reference Anchor step prints a one-line warning naming what to provide and proceeds without anchor section.
- [ ] Given `grep -RE 'WebFetch' skills/uiux/ skills/mobile-uiux/ skills/desktop-uiux/`, when run after this issue lands, then no result mentions reference description (WebFetch may remain for unrelated purposes — must be re-verified by hand).
- [ ] Given `docs/references/` is populated, when `design_philosophy.md` is validated, then every cited anchor points to an existing file under that directory.

#### Implementation Notes
- `screenshot_pilot.py` already has a headless capture backend probe — reuse, do not duplicate.
- The skip warning must be explicit ("Reference Anchor skipped: no image provided. Pass 1–3 image paths or a page URL to populate this section.") — silent fallback is the bug we are fixing.
- If no screenshot backend is available, `capture_reference.py` exits with a clear "install Playwright OR provide image paths directly" message. Pairs with ISSUE-010's degraded mode.
- Mobile and desktop uiux skills have analogous step — patch all three SKILL.md files in this single PR.

#### Tests
- [ ] Image-URL path: 2 image URLs → both Read as images, extracted facts present.
- [ ] Page-URL path: HTML URL → captured to PNG → Read invoked on PNG.
- [ ] Skip path: no inputs → warning printed, no WebFetch invoked, anchor section absent.
- [ ] Backend missing: `capture_reference.py` exits with install hint.
- [ ] All three uiux skills updated; reference-description WebFetch usage gone.

#### Rollback
Revert SKILL.md changes in the three uiux skills. Delete `scripts/capture_reference.py`. Reference Anchor returns to the WebFetch (indirect) flow — this restores the fabrication issue, so rollback should be a last resort.

---

### ISSUE-012: Reference Anchor tuning — 2-3 strong cues + 1 literal quote
- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-012.md
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — 5 anchors create averaging pressure; a single literal quote injects product-specific concreteness at Phase 2)
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-011 (image-grounded references must land first so anchor citations point to real images, not WebFetch text)

#### Goal
Phase 2's Reference Anchor section is reduced from "5 cues to adopt + 3–5 to avoid" to "2–3 strong cues + 1 mandatory literal quote + 3–5 anti-cues". The literal quote is a specific word, number, or glyph from the brand or domain that MUST appear verbatim in the prototype.

#### Scope (In/Out)
- In:
  - Phase 2 step 6.5 output spec updated:
    - 2–3 **strong** cues to adopt, each with image evidence (from ISSUE-011's image-grounded path).
    - 1 **literal quote** — a specific word, number, or glyph from the brand/domain. Examples: "the word *조용한* set in 168pt Fraunces in the hero", "the order ID 47.2-A shown in mono", "the unit *회* in the quantity selector".
    - 3–5 cues to **avoid** stays as-is (anti-references already worked).
  - `templates/design_philosophy.md` gains `literal_quote:` field that must be populated when Phase 1.5 interview was NOT skipped.
  - Validator (called from Phase 5A pilot gate): if `literal_quote:` is empty AND Phase 1.5 was not flagged as skipped, fail with a message naming the missing field.
  - Verbatim-render check: at Phase 5B exit, grep `prototype/screens/*.html` for the literal string; if absent, fail with a pointer to which screen should include it.
  - ISSUE-010's specificity check (Step 2.2) treats the literal_quote as 1 of the 3 required product-specific details — never sufficient alone (still need 2 more domain-grounded details).
  - Same change in mobile + desktop uiux SKILL.md.
  - Unit tests for anchor count, literal_quote presence, verbatim render.
- Out:
  - Image grounding mechanism (ISSUE-011).
  - Pilot Gate restructuring (ISSUE-010).
  - Interview skip-path hardening (#8 — not requested).

#### Acceptance Criteria (DoD)
- [ ] Given Phase 2 runs with image-grounded references available, when complete, then `design_philosophy.md` has exactly 2–3 strong cues, exactly 1 literal_quote, and 3–5 anti-cues.
- [ ] Given `literal_quote:` empty AND Phase 1.5 not skipped, when Phase 5A gate runs, then it fails naming the missing field.
- [ ] Given a non-empty literal_quote, when Phase 5B completes, then the literal string appears verbatim in at least one HTML file under `prototype/screens/`.
- [ ] Given ISSUE-010 Step 2.2, when it evaluates a pilot, then the literal_quote counts as exactly 1 of the required 3 product-specific details (not 0, not 2+).
- [ ] Given mobile + desktop variants, when their pilots run, then the same literal_quote requirement applies and the verbatim check covers all platform prototypes.

#### Implementation Notes
- Literal quote must be a string the prototype can render verbatim — word, short phrase, number, or glyph. Reject abstract concepts ("luxury", "trust") in a soft-fail with a hint about concreteness.
- The verbatim grep is over rendered HTML, not source templates — easier to verify and stricter (ensures the string actually appears in user-facing output).
- Anti-cues unchanged at 3–5: anti-references work in the current design and removing pressure there is not requested.
- Pair with ISSUE-010: when both ship, the specificity check has a concrete artifact (literal_quote) to lean on for one of its 3 required details.

#### Tests
- [ ] Anchor count enforcement: 0/1/4/5 strong cues → fail; 2–3 → pass.
- [ ] Literal quote presence: empty + interview not skipped → fail with field named.
- [ ] Literal quote presence: empty + interview skipped → pass with skip flag honored.
- [ ] Verbatim render check: literal_quote absent from all prototype HTML → fail with screen names suggested.
- [ ] ISSUE-010 specificity-check integration: literal_quote counted as 1 detail (not 0, not 2+) when present.

#### Rollback
Revert Phase 2 output spec, restore 5-cues template. Delete `literal_quote:` field validator and verbatim-render check. ISSUE-010's specificity check continues working without the literal-quote bonus (specificity still requires 3 domain-grounded details, just not bootstrapped by an explicit anchor).

---

### ISSUE-013: Consolidate ui-reviewer / design-auditor agents — sharpen role boundaries
- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-013.md
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-13 — current ui-reviewer and design-auditor have overlapping prerequisites and checklist scope)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
`design-auditor` and `ui-reviewer` agents are refactored so that `design-auditor` owns **system-level audit** (philosophy, tokens, components at the system level, cross-platform alignment) and `ui-reviewer` owns **per-screen UI audit** (state coverage, copy compliance, token USAGE in implementation, accessibility at the implementation level). Overlapping checklist items are removed. The `design-auditor` name is preserved so ISSUE-010's Pilot Gate wiring is unaffected.

#### Scope (In/Out)
- In:
  - Open-section rewrite in both `agents/design-auditor.md` and `agents/ui-reviewer.md` declaring the role boundary explicitly with a mirrored "Owned by this agent / owned by the other" table.
  - **design-auditor scope** (owns):
    - Token consistency (color/typography/spacing/radius scales)
    - Component completeness at the SYSTEM level (does `design_system.md` define every component referenced by wireframes?)
    - Cross-platform alignment (web/mobile/desktop token consistency)
    - Philosophy compliance (does the system reflect the stated philosophy + signature move?)
    - Outputs `docs/design_audit.md`
  - **ui-reviewer scope** (owns):
    - Per-screen state coverage (default / loading / empty / error)
    - Copy compliance against `copy_guide.md`
    - Token USAGE in implementation (hex literals or magic numbers in HTML/CSS → flag)
    - Accessibility at the IMPLEMENTATION level (focus rings, ARIA, touch targets in code)
    - Outputs `docs/ui_review_notes.md`
  - Remove every duplicated checklist item from each agent (the consolidation: each category belongs to exactly one agent).
  - Cross-link: each agent file mentions the other and which categories live there.
  - Update Phase 5A (ISSUE-010 wiring) to call `design-auditor` for system-level critique and `ui-reviewer` for per-screen critique — two distinct concerns at different inputs.
  - Update `docs/design_audit.md` + `docs/ui_review_notes.md` templates if they exist; otherwise create per-output templates documenting the new ownership.
  - Non-overlap unit test: feed the same synthetic fixture to both agents and assert disjoint flagged-category sets.
- Out:
  - Renaming either agent (NOT done — ISSUE-010 wires to the `design-auditor` name).
  - Merging both into a single agent (deliberately rejected — two distinct concerns at different abstraction levels).
  - Adding new audit categories beyond the existing ones.

#### Acceptance Criteria (DoD)
- [ ] Given the two agent files after this issue, when their checklist categories are diffed, then no category appears in both (set intersection = ∅).
- [ ] Given a synthetic project with a missing token reference in `design_system.md`, when `design-auditor` runs, then it flags the missing token; when `ui-reviewer` runs in isolation, then it does NOT flag it (out of scope for that agent now).
- [ ] Given a synthetic project with a missing loading state in `prototype/screens/list.html`, when `ui-reviewer` runs, then it flags the missing state; when `design-auditor` runs, then it does NOT (out of scope).
- [ ] Given Phase 5A in ISSUE-010, when it invokes critics, then both `design-auditor` (system input) and `ui-reviewer` (screen input) are invoked with distinct prompt contexts.
- [ ] Given the existing test suite, when run, then no test for either agent regresses.

#### Implementation Notes
- The `design-auditor` name stays — ISSUE-010 wires Phase 5A's separate-context critic to that name specifically.
- The ownership table at the top of each file must be mirrored — a contributor reading either agent file sees the same partition.
- The non-overlap test is implemented by feeding the same synthetic fixture (a tiny project with one token-level bug + one screen-level bug) to both agents and comparing their flagged-category sets; they should be disjoint.
- This issue does NOT block ISSUE-010; both can proceed in parallel as long as the `design-auditor` name is preserved (which is a hard scope rule here).

#### Tests
- [ ] Category-set diff: design-auditor categories ∩ ui-reviewer categories = ∅.
- [ ] Token-mismatch synthetic: design-auditor catches it, ui-reviewer doesn't.
- [ ] Missing-state synthetic: ui-reviewer catches it, design-auditor doesn't.
- [ ] Cross-link: each agent's doc mentions the other by name + categories.
- [ ] No regression in existing per-agent tests.

#### Rollback
Revert both agent files. Both agents resume with overlapping checklists (today's behavior). ISSUE-010 continues to work because the `design-auditor` name is preserved across this issue's lifecycle — rollback does not break wiring.

---

### ISSUE-014: Verify Claude Code feature/version support matrix (spike)

> Prerequisite spike for ISSUE-015/016/017. Claude Code has added many capabilities (new hook events, plugin system, model effort levels, Fable 5) over the last ~6 months. Before the kit adopts any of them we must confirm what the *targeted* Claude Code version actually supports — feature briefings from docs can drift from a given installed build.

- Track: platform
- UI: false
- Platform: web
- Manual: true
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-16)
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-014-cc-feature-matrix
- GH-Issue:
- PR: #38
- Depends-On: none

#### Goal
A documented support matrix (`docs/cc_feature_matrix.md`) records the minimum Claude Code version the kit targets and, for each capability ISSUE-015/016/017 depend on, whether it is supported at that version.

#### Scope (In/Out)
- In:
  - Decide and document the minimum supported Claude Code version (and where that's enforced — e.g. README prerequisites, optionally `requiredMinimumVersion`).
  - Verify against that version: agent `effort:` frontmatter; agent `model: inherit`; current model aliases (`opus`→4.8, `sonnet`, `haiku`, `fable`/`best`); `WorktreeCreate`/`WorktreeRemove`/`SessionEnd`/`PreCompact` hook events; plugin manifest schema (`.claude-plugin/plugin.json`) + `hooks.json`; whether plugin subagents really drop `hooks`/`mcpServers`/`permissionMode`.
  - Record verified-vs-unverified status per feature with the evidence (doc link or local `claude` probe).
- Out:
  - Any actual adoption of the features (that is ISSUE-015/016/017).

#### Acceptance Criteria (DoD)
- [ ] Given the matrix doc, when read, then it states the targeted CC version and lists each dependent feature with one of {supported, unsupported, needs-newer-version}.
- [ ] Given each "supported" row, when checked, then it cites how it was verified (doc URL or command output), not memory.
- [ ] Given ISSUE-015/016/017, when they start, then their implementation notes can reference this matrix instead of re-investigating.

#### Implementation Notes
- This is investigation + documentation only; no code changes expected beyond the new doc (and possibly a README prerequisites line).
- Probe the locally installed build where possible (`claude --version`, trying an `effort:`/`model: inherit` agent, a no-op `WorktreeCreate` hook) rather than trusting the briefing.

#### Tests
- [ ] N/A (doc spike) — verification evidence captured inline in the matrix doc.

#### Rollback
Delete `docs/cc_feature_matrix.md`. No runtime impact.

---

### ISSUE-015: Adopt agent effort tiers + refresh model references

> Agents already use forward-compatible model *aliases* (`opus`/`sonnet`), but don't use the newer per-agent `effort` lever, and a stale `claude-opus-4-6` appears in a README example. Tune cost/quality by tier and fix the doc drift.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-16)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-015-effort-tiers
- GH-Issue:
- PR: #39
- Depends-On: ISSUE-014

#### Goal
Judgment-heavy agents run at high reasoning effort and extraction agents at low/medium, model references in docs are current, and a `fallbackModel` is configured for resilience — all gated on what ISSUE-014 confirms is supported.

#### Scope (In/Out)
- In:
  - Add `effort:` frontmatter to `agents/*.md`: high/xhigh for architect, developer, reviewer, diagnostician, refactorer, planner, *-uiux-developer; low/medium for scan-*, documenter, issue-writer, requirement-analyst, a11y-auditor.
  - Refresh the stale `claude-opus-4-6` example in `README.md` to the current default.
  - Add `fallbackModel` to `project/.claude/settings.snippet.json` (verified-supported only).
  - Optionally introduce an opt-in pack/flag that sets the orchestrator (`team-lead`) to `model: fable` / `best`.
- Out:
  - Pinning full version IDs in agent frontmatter (keep aliases for forward-compat).
  - Changing agent prompts/behavior.

#### Acceptance Criteria (DoD)
- [ ] Given every agent file, when its frontmatter is parsed, then `effort` is one of the values ISSUE-014 confirmed for that model, and the heavy/light split matches the scope list.
- [ ] Given the README, when grepped, then no retired model ID (e.g. `claude-opus-4-6`) remains as a current example.
- [ ] Given a session where the `opus` model is unavailable, when an agent runs, then the configured `fallbackModel` is used (or documented as unsupported on the target version).
- [ ] Given the existing agent/skill tests, when run, then none regress.

#### Implementation Notes
- Effort-value vocabularies differ by model (e.g. `xhigh` may be Opus-4.7/4.8-only) — honor the ISSUE-014 matrix.
- Fable 5 is not the default on any tier and needs a recent CC build; keep it opt-in, never the kit default.
- Aliases (`opus`/`sonnet`) intentionally stay so the kit tracks provider defaults without edits.

#### Tests
- [ ] Frontmatter lint: every agent has a valid `effort` for its `model`.
- [ ] README grep: no retired model IDs presented as current.
- [ ] settings snippet parses and merges cleanly (extend existing merge_settings tests).

#### Rollback
Revert agent frontmatter and settings snippet changes. Agents fall back to default effort; no behavioral dependency.

---

### ISSUE-016: Worktree/session lifecycle hooks — auto-freeze + run/ cleanup

> The kit manages worktrees (`wt_setup.sh`) and writes per-project runtime state under `.claude/run/`, but does this imperatively from skills. Newer lifecycle hook events line up exactly with that work, letting the harness drive it.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-16)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-016-lifecycle-hooks
- GH-Issue:
- PR: #40
- Depends-On: ISSUE-014

#### Goal
Worktree creation auto-writes the freeze marker via a `WorktreeCreate` hook (removing the manual step in `wt_setup.sh`), and `.claude/run/` trace/state files are cleaned up on `SessionEnd`/`Stop`.

#### Scope (In/Out)
- In:
  - `WorktreeCreate` hook that writes `.claude-kit/freeze-dir.txt` for the new worktree (already gitignored per the recent fix).
  - `SessionEnd` (or `Stop`) hook that prunes/rotates `.claude/run/agent-state.json` and `events.jsonl`.
  - Wire these in `project/.claude/settings.snippet.json`; drop the now-redundant freeze-write from `wt_setup.sh` (keep a fallback if the hook event is unsupported on the target version).
  - Tests for the new hook scripts.
- Out:
  - `PreCompact`/`PostCompact` state preservation (separate follow-up if needed).
  - Telemetry schema changes (that's ISSUE-001).

#### Acceptance Criteria (DoD)
- [ ] Given a worktree created through the kit on a version that supports `WorktreeCreate`, when it is created, then `.claude-kit/freeze-dir.txt` exists with the worktree's absolute path without any manual skill step.
- [ ] Given `wt_setup.sh` on a version WITHOUT the hook, when run, then it still writes the marker (graceful fallback — no regression).
- [ ] Given a session that ends, when the `SessionEnd`/`Stop` hook fires, then stale `.claude/run/` files are pruned/rotated per the documented policy.
- [ ] Given the hook scripts, when unit-tested, then they no-op safely on malformed/missing payloads.

#### Implementation Notes
- Reuse the existing worktree-root resolution pattern (the `commondir`-aware inline hook in settings.snippet.json) so hooks work inside worktrees.
- Only remove the imperative freeze-write once ISSUE-014 confirms `WorktreeCreate` is supported on the target version; otherwise keep both paths and prefer the hook when present.

#### Tests
- [ ] WorktreeCreate hook writes freeze-dir.txt given a synthetic payload.
- [ ] SessionEnd/Stop hook prunes run/ files per policy; no-ops when absent.
- [ ] wt_setup.sh fallback still writes the marker when the hook path is disabled.

#### Rollback
Remove the new hook entries from the settings snippet and restore the freeze-write in `wt_setup.sh`. Behavior returns to today's manual flow.

---

### ISSUE-017: Migrate kit packaging to Claude Code plugin system

> The kit hand-rolls a plugin/marketplace: `install_project.sh` + `install_packs.py` + `packs/*/manifest.yaml` + `merge_settings.py` + per-entry symlinks. Claude Code now ships this natively (`.claude-plugin/plugin.json`, `hooks.json`, namespaced skills, `/plugin install`, versioning). Several recently-fixed bugs (scripts/ wiring, freeze-dir.txt tracking) were artifacts of the bespoke installer. This issue produces the migration SPEC; implementation issues are carved out from it.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-017.md
- PRD-Ref: none (kit self-development; rationale in conversation 2026-06-16)
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-017-plugin-spec
- GH-Issue:
- PR: #41
- Depends-On: ISSUE-014

#### Goal
A reviewed SPEC (`docs/specs/SPEC-017.md`) defines how the kit is packaged as a Claude Code plugin (or coexists with the current installer during a transition), with a concrete migration plan and the implementation issues it decomposes into.

#### Scope (In/Out)
- In (the SPEC must cover):
  - Mapping current layout → plugin layout: `agents/`, `skills/`, `hooks/` → plugin root + `.claude-plugin/plugin.json` + `hooks.json` + `.mcp.json`.
  - How `${CLAUDE_PLUGIN_ROOT}` replaces the repo-root `scripts/` symlink (root cause of the #1 fix) and the `.claude-kit/` markers (#5).
  - Handling the constraint that **plugin subagents ignore `hooks`/`mcpServers`/`permissionMode`** — specifically the `/freeze`, `/careful`, `/guard` skills that embed `hooks:` in frontmatter must move to `hooks.json`.
  - Skill namespacing impact (`/implement` → `/kit:implement`) and whether to keep short names via a standalone-install option.
  - The `packs/` selection model under plugins (multiple plugins vs. one plugin with optional components) and what happens to `install_packs.py`/`merge_settings.py`/`validate_pack_manifest.py`.
  - Distribution: private git marketplace vs. skills-directory plugin; team install UX (`/plugin install kit@…`).
  - Migration/transition plan (can both installers coexist? deprecation path?) and the decomposed implementation issues.
- Out:
  - The actual migration code (separate issues spawned from the SPEC).

#### Acceptance Criteria (DoD)
- [ ] Given SPEC-017, when reviewed, then it specifies the plugin layout, the hooks.json migration for `/freeze` `/careful` `/guard`, the namespacing decision, the fate of the bespoke install scripts, and a transition plan.
- [ ] Given SPEC-017, when read, then it lists the concrete implementation issues (ISSUE-NNN stubs) the migration decomposes into, each ≤1.5d.
- [ ] Given the plugin-subagent restriction, when the SPEC addresses it, then no current hook-bearing skill is silently broken by the migration.
- [ ] Given the spec gate (per ISSUE-006/007), when this issue reaches `done`, then SPEC-017 exists and is approved.

#### Implementation Notes
- This follows the `Spec-Required` workflow established by ISSUE-006/007 — produce the SPEC/RFC first; do not migrate code under this issue.
- The whole motivation is reducing maintenance surface and eliminating the bug class behind the recent install fixes — the SPEC should explicitly tie each removed script to the failure mode it caused.
- Verify plugin-system specifics against ISSUE-014's matrix before finalizing.

#### Tests
- [ ] N/A under this issue (SPEC deliverable). Implementation issues carry their own tests.

#### Rollback
Abandon SPEC-017 (or mark `drop`). No runtime impact — the current installer remains in place until a future implementation issue replaces it.

---

### ISSUE-018: Over-engineering/simplicity review axis (ponytail benchmark)

> Benchmarked from [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) (2026-06-22). The kit's review pipeline audits correctness, security, UI, a11y, and Figma fidelity — but has **no axis for over-engineering / minimal-code**. The kit's own TDD + Figma + multi-auditor structure is biased toward *adding* code, so a counterweight that flags unnecessary complexity is the missing dimension. ponytail's `/ponytail-review` proves the format works as a single compact pass.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec:
- PRD-Ref: none (kit self-development; ponytail benchmark, conversation 2026-06-22)
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch: chore/issues-ponytail-benchmark
- GH-Issue:
- PR: #36
- Depends-On: none

#### Goal
`reviewer` produces a dedicated **Over-Engineering** finding set (alongside Code Review / Security), and `/review` surfaces it in `docs/review_notes/$ARGUMENTS.md`, so PRs are graded on minimality as a first-class axis — not just correctness.

#### Scope (In/Out)
- In:
  - Add an "Over-Engineering" checklist section to `agents/reviewer.md` using ponytail's tag taxonomy: **delete** (dead/speculative), **stdlib** (reinvented stdlib), **native** (dep doing the platform's job), **yagni** (abstraction with one impl), **shrink** (same logic, fewer lines).
  - One-line-per-finding output format: `path:line: <tag> <what to cut> → <replacement>`, ending with net removable LOC; emit "Lean already. Ship." when nothing to cut.
  - Add an **Over-Engineering** section to the review_notes output contract in `skills/review/SKILL.md.tmpl` (regenerate SKILL.md via `gen_skills.py`).
  - Update `templates/review_notes.md` and (if present) `templates/review_lessons.md` to carry the new axis; allow review_lessons classification to include an `Over-Engineering` category.
- Out:
  - Auto-applying simplifications (reviewer still only fixes clear bugs per its existing NEVER-rewrite rule; over-engineering findings are reported, not auto-cut, unless trivial).
  - A standalone `/simplify`-style skill (Claude Code already ships one; this is the *pipeline* axis, not an ad-hoc command).
  - Quantitative LOC telemetry (that's ISSUE-020-adjacent / future).

#### Acceptance Criteria (DoD)
- [ ] Given a PR with a speculative abstraction used once, when `/review` runs, then the review notes contain a `yagni` finding naming the file:line and a concrete replacement.
- [ ] Given a PR that reimplements a stdlib helper, when reviewed, then a `stdlib` finding is emitted.
- [ ] Given a genuinely lean PR, when reviewed, then the Over-Engineering section reads "Lean already. Ship." (no false-positive padding).
- [ ] Given the regenerated `skills/review/SKILL.md`, when diffed against the template, then it is in sync (gen_skills.py produces no further changes).
- [ ] Given `agents/reviewer.md`, when read, then the new axis does not override the existing "NEVER rewrite/refactor during review" rule — findings are reported with severity, fixes limited to clear bugs.

#### Implementation Notes
- Reuse ponytail's exact audit phrasing as the seed prompt; adapt "L<line>" to the kit's `path:line` convention since reviews span multiple files.
- Keep it a **section within `reviewer`**, not a new agent — avoids another subagent hop and keeps the single-pass review contract. (Revisit only if the combined prompt degrades focus.)
- Severity mapping: `delete`/`stdlib`/`native` of risky surface → up to Medium; pure `shrink`/`yagni` → Low/advisory. Over-engineering is rarely a merge blocker by itself.

#### Tests
- [ ] reviewer prompt change is covered by a fixture review (if the repo has agent-output fixtures) OR a doc-lint test asserting the Over-Engineering section + tag taxonomy exist in `agents/reviewer.md`.
- [ ] `gen_skills.py` round-trip test: regenerating leaves `skills/review/SKILL.md` unchanged (template is the source of truth).

#### Rollback
Remove the Over-Engineering section from `agents/reviewer.md` and the review_notes contract, regenerate SKILL.md. Review reverts to the current 4-axis behavior.

---

### ISSUE-019: Decision-ladder preamble for implement developer subagent (ponytail benchmark)

> Benchmarked from ponytail (2026-06-22). `skills/implement` Phase 8 says "write minimal code" but gives no operational test for *minimal*. ponytail's six-rung Decision Ladder (YAGNI → stdlib → native → installed-dep → one-line → minimal) turns "minimal" into checkable gates. It complements — does not conflict with — the kit's TDD: ponytail's own rule is "lazy code without its check is unfinished," which is exactly the kit's RED/GREEN requirement.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec:
- PRD-Ref: none (kit self-development; ponytail benchmark, conversation 2026-06-22)
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: chore/issues-ponytail-benchmark
- GH-Issue:
- PR: #36
- Depends-On: none

#### Goal
The developer subagent (`agents/developer.md`) and the implement Phase 8 prompt carry an explicit Decision Ladder the model must walk before generating code, so implementations default to the smallest correct change.

#### Scope (In/Out)
- In:
  - Add the six-rung ladder + over-engineering prohibitions ("no abstractions not explicitly requested", "no new dependency if avoidable", "deletion over addition") to `agents/developer.md`.
  - Add a short "Minimality gate" note to `skills/implement/SKILL.md.tmpl` Phase 8 (Implement minimal code), regenerate SKILL.md.
  - Preserve the existing Figma structure-source prohibition and TDD ordering verbatim — the ladder is additive, placed before "write the code".
- Out:
  - Any change to the test-first ordering or checkpoints.
  - Enforcement tooling (this is prompt guidance; measurement is future work).
  - The mobile/desktop UI developer agents (can adopt the same block in a follow-up if it proves out on `developer.md` first).

#### Acceptance Criteria (DoD)
- [ ] Given `agents/developer.md`, when read, then it contains the six-rung ladder and the over-engineering prohibitions, positioned before code generation and after the TDD/check requirement.
- [ ] Given the regenerated `skills/implement/SKILL.md`, when diffed against the template, then it is in sync.
- [ ] Given the new block, when read alongside the existing "Self-Review Requirements" and Figma prohibition, then there is no contradictory instruction (ladder never licenses skipping tests, validation, or Figma fidelity).

#### Implementation Notes
- Keep the wording tight — the developer prompt is already long; a 6-line ladder + 3-line prohibition list, not a lecture.
- Explicitly carve out the ponytail exception ("laziness never extends to validation/security/a11y/explicitly-requested work") so it cannot be read as license to cut corners on trust boundaries.

#### Tests
- [ ] Doc-lint/round-trip: `gen_skills.py` regeneration leaves `skills/implement/SKILL.md` in sync; assertion that the ladder block exists in `agents/developer.md`.

#### Rollback
Remove the ladder block from `agents/developer.md` and Phase 8; regenerate SKILL.md. No behavioral dependency elsewhere.

---

### ISSUE-020: Tech-debt marker convention + harvester + review checkpoint (ponytail benchmark)

> Benchmarked from ponytail's `/ponytail-debt` (2026-06-22). The kit has no structured convention for marking *intentionally deferred* simplifications, so deferrals become silent rot. ponytail requires each debt marker to carry a **ceiling** (the constraint that holds today) and an **upgrade trigger** (the condition that forces a revisit); markers without a trigger are flagged as silent-rot risk. This fits the kit's checkpoint philosophy: make the obligation explicit and machine-checkable.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec:
- PRD-Ref: none (kit self-development; ponytail benchmark, conversation 2026-06-22)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: chore/issues-ponytail-benchmark
- GH-Issue:
- PR: #36
- Depends-On: none

#### Goal
A documented `KIT-DEBT:` marker convention (with mandatory ceiling + upgrade trigger), a `scripts/debt_harvest.py` that produces a ledger, and a non-blocking review checkpoint that flags markers missing a trigger as silent-rot risk.

#### Scope (In/Out)
- In:
  - Define the marker grammar (e.g. `# KIT-DEBT(ceiling=…, trigger=…): <what was simplified>`) in `docs/` (or CONTRIBUTING.md) — choose a kit-namespaced token, not `ponytail:`.
  - `scripts/debt_harvest.py`: grep the tree (excluding `.git`, `.venv`, `node_modules`, build output), parse markers, emit a ledger (location, simplification, ceiling, trigger); flag `no-trigger` entries; print "No KIT-DEBT. Clean ledger." when empty. Mirror the existing script conventions (argparse, exit codes, stdlib-only).
  - A `/review` checkpoint phase (`debt`) wired through `verify_checkpoint.py` that runs the harvester as a **non-blocking warning** — surfaces no-trigger markers in review notes; does not fail the build.
  - Unit tests under `tests/` following existing patterns.
- Out:
  - Auto-creating issues from debt markers (possible future link to issues.md).
  - Making the checkpoint blocking (start advisory; promote later only if it earns it).
  - Back-filling markers across the existing codebase.

#### Acceptance Criteria (DoD)
- [ ] Given source files with valid `KIT-DEBT(ceiling=…, trigger=…)` markers, when `debt_harvest.py` runs, then the ledger lists each with its location, ceiling, and trigger.
- [ ] Given a marker with no `trigger=`, when harvested, then it is flagged `no-trigger` in the ledger and counted in the summary.
- [ ] Given a clean tree, when harvested, then it prints "No KIT-DEBT. Clean ledger." and exits 0.
- [ ] Given `/review`, when the `debt` checkpoint runs, then no-trigger markers appear as a warning in `docs/review_notes/$ARGUMENTS.md` without failing the review.
- [ ] Given malformed markers, when harvested, then the script does not crash (reports them as malformed, exits non-zero only on its own usage error, not on content).

#### Implementation Notes
- Reuse the excludes and grep approach already used elsewhere in `scripts/`; keep it stdlib-only (consistent with the kit's pyyaml-is-the-only-hard-dep stance).
- Wire the checkpoint via the existing `verify_checkpoint.py --skill review --phase debt` dispatch so the SKILL template stays a single prefix-matchable command.
- Keep it advisory first — a blocking debt gate on a young convention would just train people to omit markers.

#### Tests
- [ ] `debt_harvest.py`: valid markers parsed; no-trigger flagged; clean tree message; malformed markers handled.
- [ ] `verify_checkpoint.py` review/debt phase returns warning (exit 0) and writes the ledger summary where review notes can pick it up.

#### Rollback
Delete `scripts/debt_harvest.py`, remove the `debt` checkpoint phase and the convention doc. No runtime dependency — markers are inert comments if the harvester is gone.

---

### ISSUE-021: PyYAML-dependent tests should skip cleanly when the dep is absent

> Discovered 2026-06-22 while running the full suite during the ISSUE-018~020 work. On a venv without PyYAML, `tests/test_validate_pack_manifest.py` and `tests/test_install_packs.py` produce **23 hard failures**, all tracing to the lazy-fail guard added in #33 (`PyYAML is required for pack manifest parsing`). With PyYAML installed, all 36 tests pass. CI is unaffected (it `pip install`s pyyaml explicitly), but a contributor running bare `pytest` sees a misleading wall of red and cannot tell it apart from a real regression. This is the exact confusion that cost time this session.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec:
- PRD-Ref: none (kit self-development; discovered during ISSUE-018~020, conversation 2026-06-22)
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-021-pyyaml-skip
- GH-Issue:
- PR: #37
- Depends-On: none

#### Goal
Running `pytest` without PyYAML yields clean **skips** (with a clear reason) for the pyyaml-dependent tests instead of 23 failures, so a bare local run is trustworthy and distinguishable from a real regression.

#### Scope (In/Out)
- In:
  - Guard the pyyaml-dependent tests with `pytest.importorskip("yaml", reason="PyYAML not installed; install dev extras")` (module-level in `test_validate_pack_manifest.py` and `test_install_packs.py`, or via a shared fixture/conftest marker).
  - Document the dev-dependency install path (`pip install -e '.[dev]'` / `uv sync`) in CONTRIBUTING's "Running Tests" section so the dep is obvious.
- Out:
  - Making PyYAML a hard runtime dependency (deliberately rejected in #33 — it lazy-fails at parse time by design; this issue is about *test* ergonomics, not runtime).
  - Changing the production lazy-fail message or behavior.

#### Acceptance Criteria (DoD)
- [ ] Given a venv WITHOUT PyYAML, when `pytest` runs, then the pack-manifest/install tests report as skipped (not failed) with a reason naming PyYAML, and the overall run shows 0 failures attributable to a missing pyyaml.
- [ ] Given a venv WITH PyYAML, when `pytest` runs, then those tests execute and pass exactly as today (no behavior change).
- [ ] Given CONTRIBUTING.md, when read, then the dev-extras install command is documented in the test section.

#### Implementation Notes
- Prefer `importorskip` at module top — least invasive, no per-test edits, and the skip reason is visible in `-v` output.
- Confirm no other test files import `yaml` indirectly through a helper; if so, guard those too.
- Verify the coverage gate still holds (skipped tests don't execute their target code, but those modules are already exercised in CI where pyyaml is present).

#### Tests
- [ ] Meta: a check (or manual verification documented in the PR) that the suite reports skips, not failures, when `yaml` is uninstallable. A monkeypatch-based test that simulates `ModuleNotFoundError` for `yaml` is acceptable but optional.

#### Rollback
Remove the `importorskip` guards; behavior reverts to today's hard failures when PyYAML is absent. No runtime impact.

---

### ISSUE-022: Plugin manifests + skill-hook path hygiene

> SPEC-017 step 1. First, independently-revertable step of the phased-hybrid plugin migration. Adds native plugin packaging alongside the existing installer — no installer change yet.
>
> **Scope correction (2026-06-22):** the original premise — "move `/freeze`,`/careful`,`/guard` hooks to `hooks.json`" — was wrong. Per `hooks.md`, plugin **skills** DO honor frontmatter `hooks:` (the restriction is **agents-only**), so the skill hooks **stay in frontmatter**. The real defect was their use of the **undocumented `${CLAUDE_SKILL_DIR}`** variable; this issue fixes that resolution and corrects SPEC-017 + the feature matrix.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: docs/specs/SPEC-017.md
- PRD-Ref: none (kit self-development; decomposed from SPEC-017)
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-022-plugin-manifests
- GH-Issue:
- PR: #43
- Depends-On: none

#### Goal
The kit carries a valid `.claude-plugin/plugin.json` and `hooks/hooks.json` (the already-always-on `settings.snippet.json` hooks, in plugin form), and `/freeze`,`/careful`,`/guard` keep their frontmatter hooks but resolve their guard scripts via documented variables (`${CLAUDE_PLUGIN_ROOT}` first, `${CLAUDE_PROJECT_DIR}` fallback) instead of the undocumented `${CLAUDE_SKILL_DIR}`.

#### Scope (In/Out)
- In:
  - Author `.claude-plugin/plugin.json` (name, version=VERSION, description) and `hooks/hooks.json` porting the always-on `settings.snippet.json` hooks via `${CLAUDE_PLUGIN_ROOT}`.
  - Fix the `/freeze`,`/careful`,`/guard` skill hook commands to resolve the guard script via a documented-variable fallback chain (keeps `${CLAUDE_SKILL_DIR}` as one fallback so it can never regress).
  - Correct `docs/specs/SPEC-017.md` and `docs/cc_feature_matrix.md` (agent-vs-skill: plugin skills DO support frontmatter hooks).
  - Tests for manifest validity + skill-hook robustness.
- Out:
  - `.mcp.json` — the kit ships no MCP servers (YAGNI).
  - Path/root changes for `scripts/` (`${CLAUDE_PLUGIN_ROOT}` resolution is ISSUE-023).
  - Removing or changing `install_project.sh` (ISSUE-027).

#### Acceptance Criteria (DoD)
- [x] Given the repo, when validated, then `.claude-plugin/plugin.json` (version matches VERSION) + `hooks/hooks.json` parse and declare the kit's always-on hook events.
- [x] Given the skill hooks, when inspected, then they prefer `${CLAUDE_PLUGIN_ROOT}` and retain a `${CLAUDE_PROJECT_DIR}` fallback, and the referenced guard scripts exist.
- [x] Given the standalone (`.claude/`) install, when used, then hook behavior is unchanged (the fallback chain still includes the prior resolution).

#### Implementation Notes
- Skill hooks stay in frontmatter (supported for plugin skills); only the script-path resolution changed.
- `hooks.json` references scripts at their current `project/.claude/hooks/` location under `${CLAUDE_PLUGIN_ROOT}`; relocating them to a cleaner path is deferred to ISSUE-024.

#### Tests
- [x] `tests/test_plugin_manifest.py`: plugin.json valid + versioned; hooks.json declares events; skill hooks prefer documented vars; guard scripts exist; skill hooks NOT moved into hooks.json.

#### Rollback
Delete `.claude-plugin/plugin.json` + `hooks/hooks.json`, restore the `${CLAUDE_SKILL_DIR}` skill commands. Standalone install is unaffected.

---

### ISSUE-023: Resolve scripts/ root via ${CLAUDE_PLUGIN_ROOT}

> SPEC-017 step 2. Replaces the repo-root `scripts/` symlink assumption that caused the #34 bug class. Also the place to finally exercise `WorktreeCreate` (ISSUE-014/016 `needs-verify`) under a plugin layout.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: docs/specs/SPEC-017.md
- PRD-Ref: none (kit self-development; decomposed from SPEC-017)
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-023-plugin-root
- GH-Issue:
- PR: #44
- Depends-On: ISSUE-022

#### Goal
`checkpoint.sh`, `worktree.sh`, and skill commands resolve the kit's `scripts/` location via `${CLAUDE_PLUGIN_ROOT}` when present, falling back to the current symlink resolution when it is not — so the kit works under both the plugin and standalone layouts and the #34 symlink bug class is closed.

#### Scope (In/Out)
- In:
  - Introduce a single root-resolution helper that prefers `${CLAUDE_PLUGIN_ROOT}` and falls back to the existing `worktree.sh root` / symlink logic.
  - Update `checkpoint.sh`, `worktree.sh`, and any skill command that assumes a repo-root `scripts/` symlink.
  - Exercise `WorktreeCreate` under the plugin layout and flip the `docs/cc_feature_matrix.md` row from `needs-verify` to `local`.
- Out:
  - Runtime state relocation (ISSUE-024).

#### Acceptance Criteria (DoD)
- [ ] Given `${CLAUDE_PLUGIN_ROOT}` is set, when a checkpoint runs, then it resolves `scripts/` under the plugin root (no symlink needed).
- [ ] Given `${CLAUDE_PLUGIN_ROOT}` is unset (standalone), when a checkpoint runs, then it resolves via the current symlink logic (no regression).
- [x] Given the matrix, when ISSUE-023 lands, then the `WorktreeCreate` row is updated with local-probe evidence.

#### Implementation Notes
- Keep the command prefix-matchable for permission allowlists (the reason `checkpoint.sh` exists).
- Single helper, two callers minimum — avoid duplicating the resolution logic.
- **Done as:** added `scripts/kit_root.sh` (plugin-first kit-root resolver) and made `checkpoint.sh`/`wt_setup.sh`/`wt_cleanup.sh`/`registry_edit.sh` prefer `${CLAUDE_PLUGIN_ROOT}` (fallback to script dir). The wrapper-internal wiring was already SCRIPT_DIR-based since #34; this makes it explicitly plugin-aware.
- **Deferred to ISSUE-026:** rewriting the skill *entry* command strings (`bash scripts/checkpoint.sh ...`) to a plugin-resolved form — that is coupled to the `/kit:` namespacing and the prefix-matchable allowlist regeneration. WorktreeCreate live-event probe also deferred to 026 (when the plugin is actually installed).

#### Tests
- [ ] Root helper prefers `${CLAUDE_PLUGIN_ROOT}` when set; falls back otherwise.
- [ ] checkpoint.sh resolves verify_checkpoint.py under both layouts.

#### Rollback
Revert to `worktree.sh root` resolution everywhere; the symlink path remains. No data impact.

---

### ISSUE-024: Move runtime state to ${CLAUDE_PLUGIN_DATA}

> SPEC-017 step 3. Relocates per-project runtime state so it survives plugin updates. Composes with the ISSUE-016 lifecycle hooks.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: docs/specs/SPEC-017.md
- PRD-Ref: none (kit self-development; decomposed from SPEC-017)
- Priority: P2
- Estimate: 1d
- Status: drop
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-023

> **Dropped 2026-06-22.** Verified (claude-code-guide vs official docs): `${CLAUDE_PLUGIN_DATA}` resolves to a **single global dir per plugin** (`~/.claude/plugins/data/{id}/`), shared across all projects, intended for persistent tooling (deps/caches) — **not** per-project ephemeral state. Moving `.claude/run/` state there would collide across projects; the `.claude-kit/` freeze marker is worktree-scoped and must stay in the worktree (freeze_guard reads `repo_root/.claude-kit/`). The kit's state is already correctly placed, so this issue is a no-op and is dropped. SPEC-017 + cc_feature_matrix corrected accordingly.

#### Goal
`.claude-kit/` markers and `.claude/run/` state write under `${CLAUDE_PLUGIN_DATA}` when present (surviving plugin updates), with the current paths as fallback.

#### Scope (In/Out)
- In:
  - Resolve the state directory via `${CLAUDE_PLUGIN_DATA}` with fallback to `.claude/run/` and worktree `.claude-kit/`.
  - Update `agent_state.py`, `worktree_freeze.py`, `run_cleanup.py`, and `wt_setup.sh` resolution accordingly.
- Out:
  - Telemetry schema (ISSUE-001).

#### Acceptance Criteria (DoD)
- [ ] Given `${CLAUDE_PLUGIN_DATA}` is set, when state is written, then it lands under that directory.
- [ ] Given it is unset, when state is written, then it lands under the current paths (no regression).
- [ ] Given a plugin update, when it occurs, then prior run state is preserved (manual or simulated verification noted).

#### Implementation Notes
- Reuse the ISSUE-023 root helper pattern for consistency.
- Keep the freeze marker discoverable by `/freeze`/`/guard` under both layouts.

#### Tests
- [ ] State path resolution prefers `${CLAUDE_PLUGIN_DATA}`; falls back otherwise.
- [ ] Lifecycle hooks write/cleanup under the resolved directory.

#### Rollback
Revert to `.claude/run/` + worktree `.claude-kit/`. No data migration needed.

---

### ISSUE-025: Model packs/ as plugin components; retire bespoke pack scripts

> SPEC-017 step 4. Replaces the hand-rolled pack selection (`install_packs.py` + `merge_settings.py` + `validate_pack_manifest.py` + `packs/*/manifest.yaml`) with native plugin components.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: docs/specs/SPEC-017.md
- PRD-Ref: none (kit self-development; decomposed from SPEC-017)
- Priority: P2
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-025-packs-components
- GH-Issue:
- PR: #47
- Depends-On: ISSUE-022

> **Scope correction (2026-06-22):** plugins are all-or-nothing — "optional components within one plugin" is **not supported** (verified vs docs). So the sales pack becomes its **own plugin** (`claude-dev-kit-sales`) declaring `dependencies: ["claude-dev-kit"]`. This issue adds that manifest; the marketplace that lists both plugins is **ISSUE-026**, and retiring `install_packs.py`/`merge_settings.py`/`validate_pack_manifest.py` is **ISSUE-027** (they must keep working during coexistence).

#### Goal
The `packs/` selection model is expressed via the plugin system (optional components or sub-plugins), and `install_packs.py`/`merge_settings.py`/`validate_pack_manifest.py` are adapted or retired — each retired script tied to the failure mode it caused.

#### Scope (In/Out)
- In:
  - Decide and implement: one plugin with optional components vs. multiple plugins (resolve SPEC-017 Open Question 1).
  - Migrate the sales pack accordingly; adapt or delete the three bespoke pack scripts.
  - Update or remove `tests/test_install_packs.py` / `tests/test_validate_pack_manifest.py` (the ISSUE-021 `importorskip` guards may become moot).
- Out:
  - Removing `install_project.sh` itself (ISSUE-027).

#### Acceptance Criteria (DoD)
- [ ] Given the plugin packaging, when a pack is selected, then its components install via the plugin mechanism (no `merge_settings.py`).
- [ ] Given each retired script, when removed, then the SPEC/PR notes which failure mode it caused (e.g. ISSUE-021 PyYAML hard-fail).
- [ ] Given the test suite, when run, then pack tests reflect the new mechanism (no orphaned tests).

#### Implementation Notes
- This is where the PyYAML manifest dependency (ISSUE-021) can disappear entirely if `manifest.yaml` is replaced by `plugin.json` component declarations.
- Preserve the sales pack's current file set; only the selection/wiring changes.

#### Tests
- [ ] Pack component install/selection under the plugin mechanism.
- [ ] No dead references to retired scripts remain (grep guard).

#### Rollback
Restore the bespoke pack scripts + `manifest.yaml`; revert component declarations. The installer path returns.

---

### ISSUE-026: Plugin distribution + /kit: namespacing + standalone short-name option

> SPEC-017 step 5. Establishes how teams install the kit as a plugin and documents the namespacing change.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: docs/specs/SPEC-017.md
- PRD-Ref: none (kit self-development; decomposed from SPEC-017)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-026-distribution
- GH-Issue:
- PR: #48
- Depends-On: ISSUE-022

> **Resolved (2026-06-22):** the repo itself is the marketplace (`.claude-plugin/marketplace.json` listing core + sales). Namespace is the plugin name (`/claude-dev-kit:<skill>`); the submodule install keeps short names (`/implement`). Bespoke-script retirement remains ISSUE-027.

#### Goal
The kit is installable via `/plugin install` from a chosen distribution channel, the `/kit:` skill namespace is documented, and a standalone-install path that preserves short skill names is offered for the deprecation window.

#### Scope (In/Out)
- In:
  - Set up distribution (resolve SPEC-017 Open Question 3: private git marketplace vs. skills-directory channel).
  - Document `/plugin install kit@…`, the `/kit:` namespace (`/kit:implement` etc.), and the standalone short-name option in `README.md`.
- Out:
  - Retiring the installer (ISSUE-027).

#### Acceptance Criteria (DoD)
- [ ] Given the chosen channel, when a user runs `/plugin install`, then the kit installs and `/kit:*` skills are available.
- [ ] Given the README, when read, then it documents the namespace and the standalone short-name alternative.
- [ ] Given a standalone install, when used, then short names (`/implement`) still work during the window.

#### Implementation Notes
- Namespacing is mandatory for plugins — set expectations clearly so the `/implement`→`/kit:implement` change doesn't surprise users.

#### Tests
- [ ] N/A automated for distribution; document the manual install-verification steps in the PR. A manifest/namespace lint is acceptable.

#### Rollback
Remove the marketplace/distribution config and README plugin section; standalone install remains the documented path.

---

### ISSUE-027: Deprecate install_project.sh after plugin parity

> SPEC-017 step 6 (final). Removes the bespoke installer once the plugin path reaches parity, closing the coexistence window.
> **Live parity run 2026-07-22** (headless, `claude plugin` CLI on 2.1.193 — no interactive session needed):
> - **Item 1 ✓** — marketplace add (local dir source) + core install succeed, *after two manifest fixes surfaced by the run*: (a) `plugin.json` `author` must be an object, not a string (both core + sales); (b) `hooks.json` must wrap events in a top-level `"hooks": {}` object — the flat form loaded as **Hooks (0)** with "Status: failed to load". Post-fix inventory: Skills 23 / Agents 33 / Hooks 8.
> - **Item 2 ✗ FAIL** — headless probe in the plugin-only project: `$CLAUDE_PLUGIN_ROOT` is empty in the model's shell and `bash scripts/checkpoint.sh` → "No such file or directory". Skill *bodies* still instruct project-relative `scripts/` paths (the ISSUE-023 rewrite deferred to 026 and dropped). → **ISSUE-035**, now a hard dep.
> - **Item 3 ✓ (partial)** — hooks.json hooks fire live under the plugin: secret_guard blocked a Write with the canonical message; agent_state wrote `.claude/run/events.jsonl`. WorktreeCreate freeze-marker remains test-verified only (needs an in-session worktree; re-probe during the item-2 re-run).
> - **Item 4 ✓** — `/claude-dev-kit:guard` invoked headlessly; skill-frontmatter hooks fired via the `$CLAUDE_PLUGIN_ROOT` fallback chain: in-boundary Write passed, out-of-boundary Write blocked with the `[freeze]` message.
> - **Item 5 ✓** — installing the sales pack alone auto-installs + enables core ("+ 1 dependency: claude-dev-kit").
> - Extra finding: `claude plugin validate ./packs/sales` warns all 5 sales skills lack frontmatter — folded into ISSUE-035 scope.
> **Done 2026-07-22** (post-ISSUE-035). Item 2 re-verified: checkpoint + kit_update_check executed via the substituted absolute prefix in a plugin-only headless session (checkpoint failed on *phase logic*, not path). **WorktreeCreate probe verdict**: official docs confirm a CREATOR contract — *"The hook is responsible for creating the worktree… It replaces default git behavior"*; a configured hook that prints no path **aborts creation with no fallback**. The kit's passive `worktree_freeze.py` was therefore breaking native worktree creation for plugin users (probe reproduced it live, then confirmed creation works after removal). Hook + handler + wiring removed (platform-first: creation belongs to CC; freeze markers stay on the `wt_setup.sh` skill path); `test_plugin_manifest.py` now fails if a WorktreeCreate hook is re-added; matrix row 4 rewritten. Deletion executed: `install_project.sh`, `install_packs.py`, `merge_settings.py` + their tests removed; README installation section, pack table, repo tree, Updating section, `packs/README.md`, `packs/sales/README.md` flipped plugin-first with a migration note; `tests/test_no_installer_references.py` grep guard over active surfaces (docs/specs + issues.md exempt as history). **Deviations from the checklist**: `validate_pack_manifest.py` kept — it is the pack-authoring lint (packs/README step 5), not installer-only; `install_user.sh` kept — user-scope statusline install, independent of the project installer.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: docs/specs/SPEC-017.md
- PRD-Ref: none (kit self-development; decomposed from SPEC-017)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-027-deprecate-install-project
- GH-Issue:
- PR:
- Depends-On: ISSUE-022, ISSUE-023, ISSUE-025, ISSUE-026, ISSUE-035

#### Goal
`install_project.sh` and the now-dead install scripts are removed, and the docs are flipped to plugin-first, after the plugin path is validated at parity with the installer.

#### Scope (In/Out)
- In:
  - Remove `install_project.sh` and any install scripts made dead by ISSUE-022–026.
  - Flip README/CONTRIBUTING install instructions to plugin-first.
  - Final grep/CI guard that no doc or script references the removed installer.
- Out:
  - Any new packaging behavior (all landed in ISSUE-022–026).

#### Acceptance Criteria (DoD)
- [x] Given the repo, when searched, then `install_project.sh` and dead install scripts are gone and nothing references them. *(grep guard enforces; docs/specs + issues.md exempt as history)*
- [x] Given the docs, when read, then plugin install is the primary documented path. *(README Installation/Updating/pack table/tree + both pack READMEs)*
- [x] Given ISSUE-022/023/025/026, when all are done, then this issue proceeds (gated on parity). *(plus ISSUE-035, added after the first parity run)*

#### Implementation Notes
- This is the only destructive step; do not start it until ISSUE-022/023/025/026 have landed (they have) AND a live parity check passes (below).

**Parity checklist (final statuses, 2026-07-22):**
1. ✅ `claude plugin marketplace add` + `claude plugin install claude-dev-kit@claude-dev-kit` succeed (after the author-object + hooks-wrapper manifest fixes).
2. ✅ Checkpoint flow works under the plugin: the Kit Script Root rule (ISSUE-035) resolves the substituted absolute prefix; `checkpoint.sh` reached `verify_checkpoint.py` and failed on phase logic, not path.
3. ✅ Always-on hooks fire (secret_guard blocked a Write; agent_state wrote `.claude/run/events.jsonl`). WorktreeCreate: **contract mismatch found** — creator contract, passive hook removed; native worktree creation confirmed working after removal.
4. ✅ `/freeze`,`/careful`,`/guard` frontmatter hooks block correctly under the plugin (`${CLAUDE_PLUGIN_ROOT}` fallback chain).
5. ✅ Sales pack install auto-installs + enables core ("+ 1 dependency").
6. ✅ Removed `install_project.sh`, `install_packs.py`, `merge_settings.py` (+ tests); docs flipped plugin-first. `validate_pack_manifest.py` deliberately kept (pack-authoring lint, not installer-only). Failure modes tied: install_project (symlink drift — #34 bug class, config overrides per ISSUE-028), install_packs/merge_settings (dead once packs became dependent plugins in ISSUE-025).

#### Tests
- [x] Grep guard: `tests/test_no_installer_references.py` — removed scripts stay gone; no active-surface references.

#### Rollback
`git revert` the removal commit to restore `install_project.sh`. Because the plugin path is already in place, both install methods work again immediately.

---

### ISSUE-028: Remove lint enforcement from the kit

> The kit imposed its own lint/format tooling on every consuming project, which caused friction project-to-project: the `autoformat.py` PostToolUse hook ran `ruff`/`prettier` on every edit and **blocked the edit** (`decision: block`) on any residual lint error, and `install_project.sh` symlinked the kit's `linters/ruff.toml` + `.prettierrc.json` into each project root — overriding the project's own config. Decision (conversation 2026-06-22): the kit should not impose lint; remove it entirely.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec:
- PRD-Ref: none (kit self-development; conversation 2026-06-22)
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: chore/remove-lint
- GH-Issue:
- PR: #45
- Depends-On: none

#### Goal
The kit no longer ships, installs, runs, or instructs lint/format tooling. No consuming project is auto-formatted, has edits blocked on lint, or gets kit lint configs symlinked into it.

#### Scope (In/Out)
- In:
  - Delete `project/.claude/hooks/autoformat.py` and remove its wiring from `project/.claude/settings.snippet.json` and `hooks/hooks.json`.
  - Delete `linters/` (`ruff.toml`, `.prettierrc.json`).
  - Remove the ruff/prettier install block and the linter-config symlinks from `scripts/install_project.sh`.
  - Scrub lint instructions from prose: `CONTRIBUTING.md`, `templates/contributing.md`, `templates/test_plan.md`, `agents/qa-designer.md`, `docs/PRD_agent_system_v0.md`.
- Out:
  - `agents/codebase-scanner.md` lint *detection* — kept deliberately. The scanner *reading* a target project's existing lint setup is read-only analysis, not the kit imposing lint; removing it would blind a useful capability.
  - `autotest.py` (tests, not lint) — unchanged.

#### Acceptance Criteria (DoD)
- [x] Given a project the kit installs into, when files are edited, then no autoformat/lint hook runs and no edit is blocked on lint.
- [x] Given `install_project.sh`, when run, then it neither installs ruff/prettier nor symlinks any linter config.
- [x] Given the repo, when grepped, then no lint *tooling* references remain except codebase-scanner's detection list.
- [x] Given the test suite, when run, then it passes (no test depended on lint tooling).

#### Implementation Notes
- `autoformat.py` had no tests, so removal is clean.
- `settings.snippet.json` and `hooks.json` keep `agent_state` + `autotest` PostToolUse hooks; only the autoformat matcher was removed.

#### Tests
- [x] Existing suite green after removal (no lint-specific test existed).

#### Rollback
`git revert` the removal commit to restore `autoformat.py`, `linters/`, the install wiring, and the prose. No data impact.

---

### ISSUE-029: Platform-first delegation of /review, /brainstorm, /bizanalysis to runtime skills

> Held work from a divergent local line (2026-07-16). The local branch implemented these as its own ISSUE-018/019/020 while the remote line spent the same numbers on the ponytail minimality work — main returned to origin, and this issue re-registers the local work under a fresh number.
> **Un-held 2026-07-16** (same-day harness audit): the runtime's /code-review + /security-review (effort tiers, --fix/--comment, ultra) outclass the kit's single-pass reviewer agent, making this the largest platform-overlap in the kit. Moved to Backlog.
> **Done 2026-07-24 — reconciled, not rebased.** The hold branch predated the plugin migration (022–027) and 001/030/031/032, so a git-rebase would have collided across issues.md (729 lines), test_agent_effort.py, and every touched skill template. Instead the 20 net-new delegation artifacts (has_skill/synthesize_*/validate_research_claim/capture_source/lint_skill_cache_order, SPEC-018/019, research_claim template, 3 auditor agents, their tests) were brought over clean, and the reworked skill templates + reviewer/brainstormer/business-analyst agents + telemetry_schema were hand-reconciled onto current main. Reconciliation points: model pins stripped from all 6 touched/new agents (ISSUE-030) → roster 33→36 (test updated); review checkout/push demoted to advisory + new **synthesis-audit** blocking gate added to VERIFIERS and the 031 contract partition; preamble auto-regenerated (032) and the stale `kit_update_check` allowlist dropped; plugin-root allowlists added to the 3 templates (035); the synthesizer now **always** renders the Over-Engineering section (fed by `minimality_findings`) to satisfy main's `verify_review_review` SSOT contract, and the template routes minimality findings there instead of folding into `code_findings`. has_skill.py comment de-referenced the deleted installer (027). 106 delegation guard tests green + full suite.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-018.md, docs/specs/SPEC-019.md
- PRD-Ref: none (kit self-development)
- Priority: P2
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-029-platform-first-delegation
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Where the Claude Code runtime exposes an equivalent skill, kit skills delegate instead of reimplementing: `/review` → `/code-review` + `/security-review`, `/brainstorm` and `/bizanalysis` → `/deep-research`. Each delegation keeps a degraded-path fallback (probe via `scripts/has_skill.py`) plus a thin synthesis layer that preserves the kit's output contracts.

#### Scope (In/Out)
- In (all already implemented on the hold branch):
  - `scripts/has_skill.py` runtime probe + per-dimension primary/degraded branching.
  - `/review`: runtime delegation, `scripts/synthesize_review_notes.py` (findings.json → canonical review notes), `review-merge-auditor` agent, degraded-path `reviewer` rewrite.
  - `/brainstorm`, `/bizanalysis`: `/deep-research` delegation + `research-auditor` / `synthesizer-auditor` agents.
  - Cache-friendly authoring lint + caching audit guide; feature-matrix S1–S8 / C1–C6 rows documenting the runtime-skill and caching evidence.
- Out:
  - The minimality (over-engineering) axis and tech-debt ledger — already landed on main via the remote ISSUE-018~020 line.

#### Acceptance Criteria (DoD)
- [x] Given a runtime exposing /code-review and /security-review, when /review runs, then both are invoked and their findings survive synthesis verbatim (merge-auditor green). *(synthesize_review_notes preserves severity+evidence verbatim; review-merge-auditor blocks on drops/downgrades/distortions)*
- [x] Given a runtime missing either skill, when /review runs, then the degraded reviewer agent covers exactly the missing dimension(s). *(reviewer.md reworked to per-dimension degraded-only; mixed-mode supported)*
- [x] Given the hold branch, when reconciled onto current main, then the remote minimality axis + tech-debt ledger are reconciled into the delegation flow. *(minimality → always-on Over-Engineering section; debt ledger advisory phase intact)*
- [x] **Predictability guard**: given any probe outcome (both/one/none of the runtime skills present), when /review runs, then a test asserts every review dimension is covered by exactly one path (runtime or degraded) — delegation may never silently no-op a dimension on runtime drift. *(test_review_delegation_guard)*

#### Implementation Notes
- Un-hold = rebase `hold/spec-019-platform-first-delegation` onto main. The branch tip already contains a reviewed semantic merge with the ponytail work (minimality axis as a third reviewer dimension); reuse it rather than re-deriving.
- Known open design question at hold time: whether the minimality axis stays a kit reviewer dimension on the primary path or maps /code-review's simplification findings into the kit tag taxonomy instead (dedupe concern).

#### Tests
- [x] Probe/branching, synthesizer contract, and auditor tests brought over (`test_has_skill.py`, `test_synthesize_review_notes.py`, `test_synthesize_from_deep_research.py`, `test_validate_research_claim.py`, `test_capture_source.py`, `test_research_fabrication_guard.py`, `test_review_delegation_guard.py`, `test_lint_skill_cache_order.py`) — 106 pass; `verify_review_synthesis_audit` added to the 031 contract partition.

#### Rollback
`git revert` the reconciliation commit; the hold branch remains as historical reference.

---

### ISSUE-030: Remove agent model pins — default to `inherit`

> Harness audit 2026-07-16. All 33 agents pin `model: opus` (16) or `model: sonnet` (17); zero use `inherit`/omission. Pins were a guarantee when written; on modern Claude Code they are a ceiling — a session running a stronger model (e.g. Fable 5) spawns subagents that silently downgrade. The kit's own feature matrix (row 2) confirms `inherit` is the CC default.
> **Done 2026-07-23.** Removed `model:` from all 33 core agents (21 opus / 12 sonnet at removal time) **and the 5 sales pack agents** — zero surviving pins, so no rationale comments were needed; the decision "no pin survives" is itself the deliberate one: `effort` tiers (low/medium on extraction agents) are the cost knob, and a cheaper-model pin would re-introduce the ceiling the issue exists to remove. README agent table now shows **Effort** instead of Model, with the inherit rationale and the deterministic-deployment note (single `model` setting / `--model` replaces the old 33 pins — predictability guard). test_agent_effort.py rewritten: pins now require an adjacent `# pin: <rationale>` frontmatter comment to pass; `xhigh` is valid under inherit (auto-fallback, matrix row 1); sales agents included in the lint. Matrix rows 2/3 updated. Note: the ISSUE-001 baseline exercised 0 subagent spawns, so 030's quality effect is unmeasured by that benchmark — evaluate on a /review or /implement run when one occurs.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; harness audit 2026-07-16)
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-030-model-inherit
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Agents follow the session model by default. `model:` appears in an agent file only where a pin is a deliberate, documented decision (e.g. cost control on high-volume extraction agents), not as boilerplate.

#### Scope (In/Out)
- In:
  - Remove `model:` from agent frontmatter (CC defaults to `inherit`), or set `model: inherit` explicitly where self-documentation is preferred.
  - Decide per-agent whether any sonnet pins stay for cost reasons; document each surviving pin with a one-line rationale comment in the agent file.
  - Keep `effort:` tiers as the per-agent knob (they compose with any session model).
  - Update `tests/test_agent_effort.py` (currently asserts every agent has a model in VALID_BY_MODEL) to accept omitted/inherit.
  - Update the feature-matrix consumer note (row 2) and README agent docs if they state pins.
- Out:
  - Effort tier values (landed in ISSUE-015; unchanged).
  - fallbackModel chain (unchanged).

#### Acceptance Criteria (DoD)
- [x] Given a session on any model, when a kit agent spawns, then it runs the session model unless its file documents a deliberate pin. *(zero pins remain)*
- [x] Given the agents/ dir, when grepped for `model:`, then every remaining pin has an adjacent rationale. *(vacuously true; lint enforces `# pin:` for any future pin)*
- [x] Given the test suite, when run, then it passes with omitted/inherit models accepted.
- [x] **Predictability guard**: given a production deployment that needs deterministic agent behavior, when it sets the model once in project settings (single control point, documented in README), then all inherit-agents follow it — restoring the old 33-pin guarantee from one place. *(README "Deterministic deployments" note)*

#### Implementation Notes
- Bedrock/Vertex caveat (matrix row 3): `opus` alias resolves differently there; `inherit` sidesteps the alias-drift problem entirely.
- `xhigh` effort on a session model that caps at `high` auto-falls-back (matrix row 1) — no guard needed.

#### Tests
- [x] test_agent_effort.py updated: model omitted/inherit is valid; surviving pins require `# pin:` rationale and validate against VALID_BY_MODEL; sales agents covered; README table asserted Effort-not-Model.

#### Rollback
`git revert` — pins are plain frontmatter lines.

---

### ISSUE-031: Checkpoint diet — demote existence-check gates to advisory

> Harness audit 2026-07-16. 61 "CHECKPOINT — MANDATORY — NEVER SKIP" gates across skills (11 each in /implement and /review). The behavior gates (tests run, TDD red, hollow-test detection, Figma computed-style suite) verify things a model cannot self-certify — keep them blocking. The existence checks (GH issue field populated, worktree exists, code changed, registry status set) verify steps modern models perform reliably, and their hard-STOP semantics forbid autonomous recovery: one false negative halts the whole pipeline instead of letting the model fix and continue.
> **Done 2026-07-23.** Final partition of the 48 registered (skill, phase) verifiers: **18 advisory** — implement issue/worktree/code/push/pr/registry, review checkout/push, and worktree/push in each of diagnose/refactor/devops/migrate/testgen — vs **30 blocking** (implement test-plan/figma/tests-written/red/test, the full review artifact+Figma suite, all ship phases, generic test/validate, uiux context/philosophy/system; review/debt stays advisory-by-internal-design outside ADVISORY_PHASES). Mechanism: verify_checkpoint.py `ADVISORY_PHASES` — a failed advisory verifier prints `ADVISORY: … report, self-correct, then continue` and exits 0; verifier internals and names untouched (telemetry comparability preserved — the ISSUE-001 trace records checkpoint pass/fail either way). Skill text converted mechanically per tier: 18 block headers → "CHECKPOINT — ADVISORY (report & continue)" with continue-wording, per-block STOP lines swapped, two-tier Checkpoint Rules intro in 8 skills + the tier-2/3 preamble pattern. **Predictability guard delivered**: tests/test_verify_checkpoint_contract.py enumerates the exact 48-phase partition (exact-set equality on both tiers), asserts exit-code behavior for both tiers, and lints generated skill text wording per tier — no gate can change tier silently.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; harness audit 2026-07-16)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-031-checkpoint-diet
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Blocking checkpoints exist only where they verify behavior the model cannot self-certify. Existence-style checks become advisory (report-and-continue, modeled on the ISSUE-020 debt checkpoint: always exit 0, surface findings) or are folded into the nearest behavior gate.

#### Scope (In/Out)
- In:
  - Classify all 61 checkpoints as behavior vs existence (starting split from the audit: keep test/red/tests-written/test-quality/figma-compliance/computed-styles/structural-match/layout/visual-diff blocking; demote issue/worktree/code/registry/checkout/push/pr).
  - Demoted phases: verify_checkpoint.py returns 0 with a warning line; SKILL.md.tmpl text changes from "STOP immediately" to "report and self-correct, then continue".
  - Regenerate skills via gen_skills.py.
- Out:
  - Removing checkpoint.sh plumbing (the advisory path reuses it).
  - Sprint orchestration logic (sprint has no checkpoints).

#### Acceptance Criteria (DoD)
- [x] Given a demoted phase that fails, when the skill runs, then the model is instructed to fix and continue rather than halt. *(ADVISORY line + exit 0; skill text per-tier)*
- [x] Given a behavior gate that fails, when the skill runs, then it still hard-blocks. *(exit 1, STOP wording kept)*
- [x] Given verify_checkpoint tests, when run, then advisory phases assert exit 0 + warning output.
- [x] **Predictability guard**: given the blocking set (test/red/tests-written/test-quality/figma-compliance/computed-styles/structural-match/layout/visual-diff), when any phase's blocking/advisory classification changes, then a test enumerating the full set fails — no gate can be demoted silently. *(exact-partition + wording lint in test_verify_checkpoint_contract.py)*

#### Implementation Notes
- Precedent: the `debt` phase (ISSUE-020) already implements the advisory pattern ("Always exits 0 ... Does NOT block").
- Keep the checkpoint *names* stable so telemetry (ISSUE-001, if un-deferred) can compare before/after failure rates. *(kept; ISSUE-001 landed first — its trace records checkpoint verdicts either way)*

#### Tests
- [x] test_verify_checkpoint_contract.py: exact-partition contract table + exit-code behavior per tier + generated-text wording lint; legacy marker-count tests updated to count both tiers.

#### Rollback
`git revert`; checkpoint.sh interface is unchanged.

---

### ISSUE-032: Move per-skill startup checks to a SessionStart hook + slim skill preambles

> Harness audit 2026-07-16. Every one of the 28 generated SKILL.md files embeds a 35–85 line preamble (~1.3k duplicated lines), and every skill invocation re-runs `kit_update_check.py` and the contributor-mode config check. On modern CC these are session-level concerns: run them once in a SessionStart hook, keep skill bodies as task instructions.
> **Done 2026-07-23.** (1) `project/.claude/hooks/session_start.py`: runs kit_update_check (prints only when an update exists) + contributor-mode detection (injects the field-report instructions only when ON — zero context cost when off); kit-root resolution is plugin-first (`CLAUDE_PLUGIN_ROOT` → `HOOK_ROOT` → own-location fallback for the standalone kit repo); never blocks session start. Wired into plugin `hooks.json` and standalone `settings.snippet.json`. **Live-verified**: a plugin-installed headless session quoted the injected CONTRIBUTOR MODE line from its context. (2) Preamble diet: dropped Kit Update Check + Contributor Mode (moved to hook) and Self-Review Requirements (generic for modern models; /review's own mandatory self-review lives in the reviewer flow), slimmed Behavioral Rules to the one kit-specific line (gh auth) as "Kit Rules", compressed Kit Script Root wording. **Total preamble duplication 1385 → 618 lines (56%)**; tier1 46→17, tier2 83→47, tier3 96→60. Budget lint (≤700 lines) prevents regression; orphan-reference guard asserts no generated skill still mentions the moved sections; `kit_update_check` removed from 10 allowed-tools lists. Matrix row 4e records SessionStart (doc + local, fires headless).

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; harness audit 2026-07-16)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-032-sessionstart-preamble-diet
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Skill bodies contain task instructions only. Session-level startup (update check, contributor mode detection, project context detection) runs once per session via hooks; per-skill preamble shrinks to the patterns the specific tier actually uses (checkpoint/worktree/registry for pipeline skills).

#### Scope (In/Out)
- In:
  - Add a SessionStart hook entry (hooks/hooks.json + project/.claude/settings.snippet.json) running kit_update_check.py and contributor-mode detection once.
  - Trim preambles.py: drop Kit Update Check + Contributor Mode from all tiers; drop Behavioral Rules lines that duplicate CLAUDE.md-level guidance; keep tier-2/3 operational patterns (checkpoint, worktree, registry, self-review) where the skill uses them.
  - Regenerate all skills; verify no skill lost an instruction it references (grep for orphaned mentions of removed sections).
- Out:
  - The gen_skills.py generation mechanism itself (kept).
  - hooks.json always-on guards (agent_state, secret/dangerous — unchanged).

#### Acceptance Criteria (DoD)
- [x] Given a new session, when it starts, then the update check runs exactly once (hook), and no skill invocation re-runs it. *(preamble no longer instructs it; allowlists cleaned)*
- [x] Given the generated skills, when line-counted, then total preamble duplication drops by ≥50%. *(1385 → 618 lines, 56%; ≤700 budget lint)*
- [x] Given contributor mode enabled, when any skill runs, then field-report behavior still works (detection moved, behavior preserved). *(hook injects the instructions once per session; live-verified in a plugin-installed session)*

#### Implementation Notes
- Plugin path: SessionStart hook must resolve scripts via ${CLAUDE_PLUGIN_ROOT} (ISSUE-023 pattern).
- Matrix row 4c confirms SessionEnd/Stop exist; verify SessionStart is available at the targeted build and add a matrix row for it as part of this issue. *(done — row 4e, fires in headless too)*
- Deviation: Project Context Detection stayed in the preamble (6 lines, skill-relevant at task time); Self-Review Requirements was dropped rather than kept (generic modern-model behavior; /review's own self-review flow is in the reviewer instructions).

#### Tests
- [x] test_lifecycle_hooks.py extended: SessionStart entries in both configs; session_start.py unit-tested (silent path, update+contributor path, no-kit-root no-op).
- [x] gen_skills output test: orphan-reference guard over all generated skills; preamble budget lint in test_preambles.py.

#### Rollback
`git revert` + regenerate skills; hook entry removal restores per-skill checks.

---

### ISSUE-033: Learning loop on Claude Code native memory — supersedes ISSUE-003

> Harness audit 2026-07-16. The kit's learning surface (`docs/review_lessons.md` + planned patterns.jsonl promotion, ISSUE-003) never accumulated a single [RL-NNN] entry, while Claude Code shipped a native persistent per-project memory directory with an index (MEMORY.md) that loads across sessions. Redesign the loop on the platform primitive instead of a bespoke store.
> **Done 2026-07-24.** Mechanism confirmed via claude-code-guide against official docs: native memory lives at `~/.claude/projects/<project>/memory/` (overridable by the `autoMemoryDirectory` setting); `MEMORY.md` (first 200 lines / 25KB) auto-loads at session start; memory files are written with the normal Write/Edit tools and auto-indexed. **Critical caveat verified**: subagents spawned via Task do NOT inherit the main conversation's auto memory — so the loop cannot rely on recall alone for the kit's separate-context agents. Implementation: (1) /review step 5.5 records each preventable pattern as a **review lesson in native memory** (topic file `review-lessons.md` + a `## Review Lessons` pointer in MEMORY.md; one fact per entry with Why + How-to-apply; dedup-in-place against the index; no RL-NNN IDs, no Frequency counter, no `registry_edit.sh`). (2) The 26 consuming agents + the kickoff/sprint/implement/testgen skills were reworded from "read docs/review_lessons.md (if exists)" to "apply recalled review lessons (native memory); when running as a separate-context subagent, the calling skill injects the relevant lessons into your prompt". (3) ui-reviewer's own RL-NNN learning flow converted to the native convention; planner/team-lead RL-NNN references retitled to lesson-by-title. (4) `docs/review_lessons.md` registry + `templates/review_lessons.md` retired (0 entries ever); README/docs/roadmap updated.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; supersedes ISSUE-003)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-033-native-memory-learning
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Review learnings persist in Claude Code's native memory (one fact per file + MEMORY.md index) instead of docs/review_lessons.md, and get recalled automatically in later sessions without kit-side preamble injection.

#### Scope (In/Out)
- In:
  - /review Learning Extraction step writes preventable patterns as native memory files (type: feedback/project) with Why/How-to-apply, replacing the review_lessons.md registry_edit flow.
  - reviewer/planner agent prompts drop "read docs/review_lessons.md" in favor of relying on recalled memories (plus an explicit memory-dir read where separate-context agents don't get recall).
  - Migration note: review_lessons.md format retired; no data to migrate (0 entries).
- Out:
  - ISSUE-002's eval gate (still independent).
  - Cross-project/team-shared memory (out of scope; native memory is per-project).

#### Acceptance Criteria (DoD)
- [x] Given a review that finds a preventable pattern, when Learning Extraction runs, then a memory entry + MEMORY.md pointer are written and no review_lessons.md write occurs. *(step 5.5 rewritten; legacy-registry guard test)*
- [x] Given a later session reviewing similar code, when the reviewer runs, then the stored pattern is available to it (recall in main session; injected by the skill for separate-context subagents — the verified no-auto-recall caveat).
- [x] Given the kit docs, when grepped, then review_lessons.md references are gone or marked historical. *(only retired-mentions remain; template removed; README/docs updated)*

#### Implementation Notes
- Caveat CONFIRMED: subagents spawned via Task do not receive automatic memory recall (official sub-agents docs) — the calling skill injects relevant lessons into the subagent prompt; agent text updated to expect that.
- Duplicate-prevention: native convention (check the MEMORY.md index before writing; update in place) — no [RL-NNN] Frequency counter.
- On-disk path is documented but not API-guaranteed; skill text routes through the model's memory capability / the `autoMemoryDirectory` setting rather than hard-coding, to stay portable across the plugin install.

#### Tests
- [x] test_integration: template retired; legacy-registry guard (no `registry_edit.sh docs/review_lessons` / `[RL-NNN]`); agent/skill references assert the native "review lessons" convention.

#### Rollback
Revert skill/agent text; memory files already written are inert data.

---

### ISSUE-034: Agent roster diet — consolidate thin persona agents

> Harness audit 2026-07-16 (registered 2026-07-21). Roughly 16 of the 33 agents are thin personas — a role header plus a generic checklist in 60–100 lines (e.g. diagnostician, prd-writer, migrator, brainstormer, devops, business-analyst) — with no instructions a modern session model doesn't already follow. Each separate agent costs an orchestration hop (spawn + context handoff + result relay) and a maintenance surface (frontmatter, effort tier, tests) without a measurable quality contribution. ISSUE-013 (ui-reviewer/design-auditor merge) is the precedent: consolidation raised quality by sharpening boundaries.
> **Done 2026-07-24.** Investigation corrected the premise: the "~16 thin" count assumed each persona is a live orchestration hop, but the coupling map showed most are NOT Task-invoked — they are either **inline skills** (`/diagnose`, `/migrate`, `/refactor`, `/prd` carry the full workflow and have no `Task` in allowed-tools, so they *cannot* spawn their persona) or **sprint routing labels** (the routing table dispatches the *skill*, not the agent). So the real cost is maintenance surface, not spawn overhead. **Absorbed 4 genuinely-dead persona files** — `diagnostician`, `migrator`, `refactorer`, `prd-writer` (verified: no `subagent_type:` spawn, no Task caller, skills carry the work) — grafting each one's distinctive discipline into its skill as an "Execution Principles" section (root-cause-before-fix + fail-before/pass-after regression test; one-major-bump + per-step rollback migrations; behavior-preserving one-transformation-per-commit refactor; PRD section-completeness + no-invented-requirements). Roster **36→32**. team-lead's test-failure path rerouted from "invoke diagnostician agent" to "run /diagnose". **Kept, with rationale** (classification table below).
>
> | Agent(s) | Verdict | Rationale |
> |---|---|---|
> | diagnostician, migrator, refactorer, prd-writer | **absorb** | dead files — never invoked; skill carries the workflow; discipline grafted in |
> | research-auditor, review-merge-auditor, synthesizer-auditor | keep | separate-context refute-first graders — the predictability guard forbids collapsing a grader into the graded |
> | reviewer, developer, architect, planner, team-lead | keep | substantive differentiated methodology + separate-context/effort control |
> | uiux-developer, mobile-uiux-developer, desktop-uiux-developer, figma-converter | keep | large design-system/prototype methodology; sprint dispatches the first two by name |
> | ui-reviewer, design-auditor, a11y-auditor, qa-designer, test-generator | keep | distinct review/QA lenses with separate-context value (ISSUE-013 precedent) |
> | scan-analyst, scan-architect, scan-data-modeler, scan-qa-designer, scan-planner | keep | /scan's real 4-pass per-domain pipeline; merging would lose separate context per pass |
> | codebase-scanner, data-modeler, requirement-analyst, ux-designer, issue-writer, documenter, copywriter, devops | keep | invoked by name from kickoff/scan/ship/uiux/issue skills; carry per-domain methodology |
> | brainstormer, business-analyst | keep | ISSUE-029 degraded-path research agents, freshly guard-tested (removing them would fight 029) |

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; harness audit 2026-07-16)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-034-agent-roster-diet
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
An agent file exists only where it carries differentiated instructions the calling skill cannot express inline (distinct tool restrictions, a real methodology, or an adversarial/separate-context role). Thin personas are absorbed into their calling skill's prompt or merged into a neighboring substantive agent.

#### Scope (In/Out)
- In:
  - Classify all 33 agents: **keep** (differentiated methodology or separate-context guarantee — e.g. reviewer, developer, architect, the auditor family, uiux developers), **absorb** (persona folds into the calling skill's Task prompt), **merge** (two near-duplicate roles become one, per ISSUE-013).
  - Apply absorb/merge; regenerate skills; update HEAVY/LIGHT sets and the roster count in `tests/test_agent_effort.py`.
  - Update README agent roster docs and the issues.md header count.
- Out:
  - Adding new agents or changing kept agents' instructions beyond merge reconciliation.
  - Skill-level flow changes (which phases run) — this issue only changes who executes them.

#### Acceptance Criteria (DoD)
- [x] Given the classification table (above), when reviewed, then every removed agent has a stated absorb target and every kept agent a one-line differentiation rationale.
- [x] Given a skill whose agent was absorbed, when it runs, then the same phase executes inline with no output-contract change (the 4 skills were already inline; discipline grafted; skill-text test added).
- [x] Given the test suite, when run, then roster-count (32) and HEAVY assertions match the new roster.
- [x] **Predictability guard**: separate-context roles that prevent self-grading (the 3 auditors, pilot-gate critic) are all in the keep set — no grader collapsed into the graded.

#### Implementation Notes
- Sequenced after ISSUE-030 (pins already stripped) and ISSUE-029 (auditors added, brainstormer/business-analyst reworked) — so this diff is purely the 4 absorptions + reroute.
- Absorb-not-delete honored: each persona's Quality-Criteria/Self-Review essence grafted into its skill as "Execution Principles".
- Scan-family and brainstormer/business-analyst evaluated and **kept** (see table) — the audit's merge suggestions were higher-risk/lower-value than estimated, or entangled with freshly-landed 029 work.

#### Tests
- [x] test_agent_effort.py: roster 32 + HEAVY minus diagnostician/refactorer.
- [x] test_integration: absorbed agents dropped from param lists; diagnostician self-review test → diagnose-skill-carries-principles test; sprint-table assertion updated.

#### Rollback
`git revert` restores agent files and skill text; no state migration.

---

### ISSUE-035: Plugin-resolved skill entry commands — make `scripts/` invocations work under plugin install

> ISSUE-027's live parity run (2026-07-22) proved this empirically: in a plugin-only project, a headless session sees `$CLAUDE_PLUGIN_ROOT` **empty in the model's shell** and `bash scripts/checkpoint.sh` fails with "No such file or directory". Every generated skill instructs project-relative `scripts/` commands (checkpoint/wt_setup/wt_cleanup/registry_edit/kit_update_check), so all 10 checkpoint-bearing skills are broken for plugin users. This is the rewrite ISSUE-023 explicitly deferred to ISSUE-026 ("rewriting the skill *entry* command strings to a plugin-resolved form"), which 026 never picked up. Contrast: skill-*frontmatter* hooks DO resolve — the guard skill's `$CLAUDE_PLUGIN_ROOT`-first fallback chain was verified live. The gap is model-shell-facing skill text only.
> **Done 2026-07-22.** Spike answer: CC substitutes `${CLAUDE_PLUGIN_ROOT}` (braces form only) as **load-time text replacement** in plugin skill bodies; `$CLAUDE_PLUGIN_ROOT` stays literal and the env var is never exported to the shell. Implementation: (1) new **Kit Script Root** preamble section in all tiers — shows `Kit root: ${CLAUDE_PLUGIN_ROOT}`, which becomes an absolute path under plugin install, with the rule "absolute path → prefix all kit script commands; literal placeholder → standalone, run as written" (absolute prefix also fixes worktree cwd); (2) plugin-root patterns appended to 11 templates' allowed-tools; (3) **bonus root-cause fix**: gen_skills.py put the AUTO-GENERATED header *above* frontmatter — CC requires frontmatter at byte 0, so all 25 generated skills' frontmatter (name/description/allowed-tools) was being silently dropped under the plugin; header now goes below the block. Sandbox note: executing plugin-root scripts via absolute path works headless (only directory *listing* outside workdir was sandbox-blocked). Copy/materialize design (SessionStart hook) was probed viable but rejected — scripts referencing kit-root resources (templates/ etc.) would break outside the full tree. Live AC run: kit skill preamble showed the substituted absolute root; kit_update_check exit 0; checkpoint.sh reached verify_checkpoint.py and failed on *phase logic* ("issues.md not found"), not ENOENT. `claude plugin validate` clean for core + sales.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; ISSUE-027 parity run 2026-07-22)
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-035-plugin-resolved-skill-commands
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
The script invocations that generated skills instruct the model to run resolve the kit root under both layouts — plugin install (no project `scripts/`) and standalone (symlinked `scripts/`) — so a plugin-only project can execute every checkpoint/worktree/registry command end-to-end.

#### Scope (In/Out)
- In:
  - **Spike first (~1h)**: determine whether CC substitutes `${CLAUDE_PLUGIN_ROOT}` inside SKILL.md *body* text at load time. If yes → gen_skills.py emits substituted absolute commands with a standalone fallback. If no → materialize a stable kit-root pointer once per session (e.g. a SessionStart hook or preamble step writes `.claude-kit/kit_root`) and route commands through it.
  - Update the gen_skills.py command constants (CHECKPOINT_CMD, WORKTREE_SETUP, WORKTREE_CLEANUP, REGISTRY_UPDATE) + the preamble's `kit_update_check.py` / `kit_config.py` invocations; regenerate all 28 skills.
  - Keep every command **prefix-matchable** for `allowed-tools` allowlists (the reason checkpoint.sh exists) and regenerate the frontmatter allowlists to match.
  - Add frontmatter to the 5 sales pack skills (`claude plugin validate` warnings from the parity run).
- Out:
  - Deleting install_project.sh (ISSUE-027 — unblocked by this issue).
  - Checkpoint blocking/advisory semantics (ISSUE-031).

#### Acceptance Criteria (DoD)
- [x] Given a plugin-only scratch project, when a headless session runs the skill-instructed checkpoint command, then verify_checkpoint.py executes (exit reflects phase logic, not ENOENT). *(live-verified 2026-07-22)*
- [x] Given a standalone project (symlinked scripts/), when the same commands run, then behavior is unchanged — no regression. *(commands unchanged for standalone; full suite green)*
- [x] Given the regenerated skill frontmatter, when permission allowlists are checked, then every script command remains prefix-matchable. *(relative forms kept; plugin-root forms are additional prefix patterns)*
- [x] Given `claude plugin validate ./packs/sales`, when run, then zero frontmatter warnings. *(root cause was the header-above-frontmatter bug, not missing frontmatter)*

#### Implementation Notes
- Evidence probe (reproduce): `claude plugin marketplace add <repo>` → install into a scratch project (`--scope local`) → `claude -p 'run: echo "[$CLAUDE_PLUGIN_ROOT]" && bash scripts/checkpoint.sh'` → `[]` + ENOENT.
- checkpoint.sh itself is already plugin-aware (KIT_ROOT prefers `${CLAUDE_PLUGIN_ROOT}`, ISSUE-023) — the wrappers are fine; only the *instructions telling the model where the wrappers live* are stale.
- Coordinate with ISSUE-032: if its SessionStart hook lands first, that hook is the natural place to write the kit-root pointer; don't build a second session-init surface.

#### Tests
- [x] Skill-text lint (tests/test_plugin_root_resolution.py): every generated skill instructing `scripts/` commands carries the Kit Script Root section + placeholder; allowed-tools carry plugin-root patterns; frontmatter at byte 0.
- [x] Root-resolution unit test covers both layouts (CLAUDE_PLUGIN_ROOT set / unset) via checkpoint.sh subprocess probes.

#### Rollback
`git revert` the gen_skills change + regeneration commit; standalone layout keeps working throughout.

---

### ISSUE-036: Renumber duplicated /review steps 3.8–3.10 + name the brainstorm snapshot directory

> 4-way repo audit 2026-08-10 (findings 1 + 12). `skills/review/SKILL.md.tmpl` reuses step numbers 3.8–3.10 twice: the Figma cluster (layout tmpl:75, visual-diff tmpl:82, debug-images tmpl:90) and the UI/design/a11y cluster (ui-review tmpl:100, design-audit tmpl:111, a11y tmpl:118). The synthesis step's "Figma 3.5–3.10" cross-reference is therefore ambiguous — a model following the skill can conflate the two clusters. Finding 12 is homed here as the same class of skill-text precision fix: brainstorm tmpl:23 passes the research-auditor a vague "snapshot directory" where bizanalysis names the canonical `docs/references/research/`.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-10 repo audit)
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-036-review-step-renumber
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/50
- PR: https://github.com/pillip/claude-dev-kit/pull/57
- Depends-On: none

#### Goal
The /review skill has a single strictly increasing step sequence with unambiguous cross-references, and the brainstorm degraded path names `docs/references/research/` explicitly.

#### Scope (In/Out)
- In:
  - Renumber the second 3.8/3.9/3.10 cluster in `skills/review/SKILL.md.tmpl` (ui-review tmpl:100, design-audit tmpl:111, a11y tmpl:118) to 3.11–3.13; shift synthesize (tmpl:124) and merge-audit (tmpl:129) from 3.11/3.12 to 3.14/3.15.
  - Verify the synthesis step's "Figma 3.5–3.10" cross-reference is exact after renumbering (it becomes unambiguous once the UI cluster moves); update any other in-file step references.
  - Update the "Figma 3.5-3.10" mention in `tests/test_review_delegation_guard.py` docstring/comments to match.
  - Finding 12 (homed here): `skills/brainstorm/SKILL.md.tmpl:23` — replace "snapshot directory" in the research-auditor inputs with the canonical `docs/references/research/` (matching bizanalysis tmpl:33).
  - Regenerate via `python3 scripts/gen_skills.py`.
- Out:
  - Checkpoint phase names/plumbing — phases are name-based (`--phase ui-review` etc.), untouched.
  - Any flow/ordering change to what the steps do.

#### Acceptance Criteria (DoD)
- [ ] Given the regenerated `skills/review/SKILL.md`, when all `3.N)` step numbers are extracted in document order, then the sequence is strictly increasing with no duplicates.
- [ ] Given the synthesis step (now 3.14), when its cross-references are read, then "Figma 3.5–3.10" resolves to exactly the Figma cluster and the UI/design/a11y outputs are referenced by their new numbers.
- [ ] Given the regenerated `skills/brainstorm/SKILL.md`, when the degraded-path research-auditor invocation is read, then its inputs name `docs/references/research/` and the phrase "snapshot directory" no longer appears.

#### Implementation Notes
- Edit the `.tmpl` files only; `SKILL.md` files are generated artifacts (regenerate, never hand-edit — CI's `gen_skills.py --dry-run` freshness gate catches divergence).
- `capture_source.py` already writes to `docs/references/research/`, so the brainstorm wording change is documentation-of-truth, not behavior.
- Grep the tmpl for every `3.8`/`3.9`/`3.10`/`3.11`/`3.12` occurrence before and after — cross-references may hide in checkpoint blockquotes and NEVER-lists.

#### Tests
- [ ] New assertion in `tests/test_review_delegation_guard.py` (or a small new test): parse generated `skills/review/SKILL.md` step numbers, assert strict monotonicity / no duplicates — a regression guard for future step insertions.
- [ ] Text assertion: brainstorm SKILL.md degraded path contains `docs/references/research/`.

#### Rollback
`git revert` — text-only change to templates + regenerated skills.

---

### ISSUE-037: Stop injecting version-pinned plugin paths from the SessionStart hook

> 4-way repo audit 2026-08-10 (finding 2). `project/.claude/hooks/session_start.py:62-71` resolves the kit root (which under plugin install is the version-pinned cache dir, e.g. `…/cache/claude-dev-kit/claude-dev-kit/0.2.0/`) and bakes that absolute path into the contributor-mode instruction it prints into session context. When the plugin updates and old cache dirs are GC'd, the injected command hits ENOENT; when the old dir survives, the model silently runs a stale copy of `contributor_report.py`.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-10 repo audit)
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-037-session-start-unpinned-path
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/51
- PR: https://github.com/pillip/claude-dev-kit/pull/58
- Depends-On: none

#### Goal
The SessionStart hook's injected contributor-mode instruction contains no version-pinned absolute path, so the invocation always resolves to the currently installed kit version under both plugin and standalone layouts.

#### Scope (In/Out)
- In:
  - Rework the contributor-mode branch of `project/.claude/hooks/session_start.py` so the printed instruction is version-stable (see Implementation Notes for the resolution options).
  - Keep standalone behavior working (repo-path kit roots are not version-pinned; today's output is fine there).
  - Unit test guarding against version-pinned paths in hook output.
- Out:
  - The kit-update-check branch of the hook (prints informational text only, no command).
  - Contributor-report mechanics (`scripts/contributor_report.py` itself unchanged).

#### Acceptance Criteria (DoD)
- [ ] Given `CLAUDE_PLUGIN_ROOT` pointing at a version-pinned cache dir (fake fixture), when the hook prints contributor-mode instructions, then the output contains no `/cache/…/<semver>/` absolute path segment.
- [ ] Given the plugin was updated and the old cache dir removed, when the model follows the injected instruction later in the session, then it resolves the current version's `contributor_report.py` (no ENOENT, no stale copy).
- [ ] Given a standalone kit checkout (no `CLAUDE_PLUGIN_ROOT`), when the hook runs with contributor mode ON, then the instruction still yields a working invocation — no regression.

#### Implementation Notes
- **Caveat from ISSUE-035 (verified)**: `${CLAUDE_PLUGIN_ROOT}` load-time text substitution applies to plugin *skill bodies* only, and the env var is NOT exported to the model's shell — so printing a literal `$CLAUDE_PLUGIN_ROOT` in hook stdout will NOT resolve in Bash. The naive fix is a non-fix; verify whatever you emit actually executes.
- Candidate approaches: (a) reference the skill preamble's **Kit Script Root** section ("run `python3 <kit-root>/scripts/contributor_report.py` where <kit-root> is the Kit Script Root shown in your active skill preamble") — skills already carry the load-time-substituted absolute root; (b) print an instruction that re-resolves at command time through a stable, non-versioned location if the marketplace cache exposes one (verify before relying on it). Pick the option that survives cache GC and degrades gracefully standalone.
- The hook must keep its "never fail, every path exits 0" contract.

#### Tests
- [ ] Subprocess test: run the hook with a fake version-pinned `CLAUDE_PLUGIN_ROOT` fixture (containing `scripts/kit_update_check.py` + contributor mode ON) and assert stdout matches no `cache/.+/\d+\.\d+\.\d+/` pattern.
- [ ] Standalone-layout test: hook output still names a resolvable invocation for the repo layout.

#### Rollback
`git revert` the hook change; the old behavior is degraded but functional within a single un-GC'd version.

---

### ISSUE-038: Cache the autotest hook's test index + debounce repeat runs

> 4-way repo audit 2026-08-10 (finding 3). `project/.claude/hooks/autotest.py` pays a heavy per-edit cost: on EVERY Write/Edit it re-walks the tests tree and reads every test file to find related tests (`find_related_python_tests` lines 195-233 — full `os.walk` + `open().read()` per test file; `find_related_js_tests` lines 236-271 walks the whole project minus node_modules), then synchronously runs up to 5 unit tests (30s timeout each) + 2 E2E (60s). A busy editing session pays this repeatedly for the same modules.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-10 repo audit)
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-038-autotest-index-cache
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/52
- PR: https://github.com/pillip/claude-dev-kit/pull/59
- Depends-On: none

#### Goal
Repeated Write/Edit events reuse a cached module-to-test-file index instead of re-walking and re-reading the test tree, and rapid successive edits to the same module do not re-run identical tests within a debounce window.

#### Scope (In/Out)
- In:
  - Build a cached index (module name → related test files) for both the Python and JS paths, persisted per project (e.g. under `.claude/run/`, which ISSUE-043 gitignores) with invalidation by tests-dir mtime scan or a short TTL.
  - Debounce: skip re-running the same (module → test set) pair when the previous run completed within the window and the test files are unchanged.
  - Keep existing behavior knobs: `MAX_RELATED_TESTS = 5`, per-test timeouts, block-on-failure semantics.
- Out:
  - Changing WHICH tests are selected (matching semantics stay: module-name containment).
  - Async/background execution — runs stay synchronous; this issue only removes redundant work.

#### Acceptance Criteria (DoD)
- [ ] Given a warm index, when a Write/Edit event fires for an already-indexed module, then the hook performs no full tests-tree walk (assert via monkeypatched `os.walk` call count in unit tests).
- [ ] Given a test file added or modified after the index was built, when the next event fires past the invalidation boundary, then the index refreshes and the new/changed test is discoverable.
- [ ] Given two edits to the same module within the debounce window with unchanged tests, when the second event fires, then the duplicate test execution is skipped.
- [ ] Given a test failure on the first edit, when the module is edited again, then the tests DO re-run (failures must never be debounced into silence).

#### Implementation Notes
- Files: `project/.claude/hooks/autotest.py` (find_related_python_tests / find_related_js_tests + a new small cache module or inline helpers).
- Cache keying: project root + tests-dir mtimes is cheap and correct enough; do not hash file contents on the hot path.
- The hook runs as a fresh process per event, so the index must live on disk, not in memory; keep reads/writes best-effort (corrupt/missing cache → rebuild, never crash — same fail-soft contract as the other hooks).
- Debounce state can live in the same run-dir file; store (module, test-set hash, last-run ts, last result).

#### Tests
- [ ] Unit tests with `tmp_path` project fixtures: warm-index walk-count assertion (monkeypatched os.walk), invalidation on new test file, debounce skip, failure-is-never-debounced.
- [ ] Corrupt-cache test: garbage index file → rebuild, exit clean.

#### Rollback
`git revert`; delete stale `.claude/run/` index files (inert data).

---

### ISSUE-039: Harden security-guard hooks against malformed stdin

> 4-way repo audit 2026-08-10 (finding 4). `secret_guard.py:45` and `dangerous_command_guard.py:35` call `json.loads(sys.stdin.read())` unguarded — a malformed payload raises an unhandled traceback and the guard is silently skipped (fail-open with no signal). `run_cleanup.py`/`session_start.py` already wrap their stdin parse. Latent footgun to document while in here: these guards block via **stdout JSON** (`{"decision": "block"}`), so a shell `|| true` wrapper around them is currently harmless — but if anyone converts them to exit-code-2 blocking, that wrapper would silently neutralize the guard.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-10 repo audit)
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-039-guard-stdin-hardening
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/60
- PR: https://github.com/pillip/claude-dev-kit/pull/63
- Depends-On: none

#### Goal
Both security guards survive malformed stdin without a traceback, emit a visible stderr diagnostic when they skip (so fail-open is loud, not silent), and carry an in-file comment documenting the stdout-JSON blocking mechanism and the `|| true` / exit-code-2 footgun.

#### Scope (In/Out)
- In:
  - Wrap the stdin parse in `project/.claude/hooks/secret_guard.py` main() and `project/.claude/hooks/dangerous_command_guard.py` main(): on parse failure, print a one-line diagnostic to stderr (e.g. "secret_guard: malformed hook payload — guard skipped") and exit 0.
  - Add a comment block in both files documenting: blocking happens via stdout JSON, exit code stays 0; therefore `|| true` wrappers are harmless today, and converting to exit-code-2 blocking requires removing any such wrappers first.
- Out:
  - Changing detection patterns or blocking semantics.
  - Converting to exit-code-2 blocking (explicitly NOT doing that — just documenting the trap).

#### Acceptance Criteria (DoD)
- [ ] Given malformed or empty stdin, when either guard runs, then it exits 0 with no traceback and prints a parse-failure diagnostic to stderr.
- [ ] Given a valid Write payload containing a secret pattern, when secret_guard runs, then the stdout block JSON is emitted exactly as before — no regression.
- [ ] Given a valid Bash payload with a dangerous command, when dangerous_command_guard runs, then blocking works exactly as before — no regression.

#### Implementation Notes
- Mirror the existing pattern in `run_cleanup.py`/`session_start.py` (try/except around the parse), but do NOT swallow silently — these are security guards; the skip must leave a trace on stderr.
- Keep stderr (not stdout) for the diagnostic: stdout is the hook's decision channel and must stay clean JSON-or-nothing.

#### Tests
- [ ] Subprocess tests: pipe garbage (`not-json`, empty, truncated JSON) into each guard → assert rc 0, empty stdout, stderr contains the skip diagnostic.
- [ ] Existing happy-path tests (secret detected / dangerous command blocked) still pass unchanged.

#### Rollback
`git revert` — two small hook files, no state.

---

### ISSUE-040: Sweep README staleness — version, roster, retired install diagrams

> 4-way repo audit 2026-08-10 (finding 5). README.md drifted across several landed issues: title says "claude-kit (v0.1)" (lines 1, 732) while the plugin is at 0.3.0; claims 33 agents but 32 exist (ISSUE-034); the agents table omits research-auditor / review-merge-auditor / synthesizer-auditor (ISSUE-029); a stale model-mix line "opus (21 agents) … sonnet (12 agents)" survives at line 740 despite ISSUE-030 removing all model pins; team-layout diagrams still show the retired `.claude-kit/` submodule install (lines 273, 290; retired by ISSUE-027); the spec skill has no Usage section.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-10 repo audit)
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-040-readme-staleness-sweep
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/62
- PR: https://github.com/pillip/claude-dev-kit/pull/65
- Depends-On: none

#### Goal
README.md matches the shipped reality: current version, 32-agent roster including the three auditors, inherit-model + effort-tier description, plugin-first team layouts, and a Usage section for every skill including /spec.

#### Scope (In/Out)
- In:
  - Title/version mentions (README.md:1, 732): reference the current version (0.3.0) or drop the hardcoded pin in favor of pointing at `VERSION` — pick one and apply consistently.
  - Agent count 33 → 32 everywhere; add research-auditor, review-merge-auditor, synthesizer-auditor rows to the agents table.
  - Replace the model-mix line (README.md:740) with the post-ISSUE-030 truth: all agents inherit the session model; effort tiers are the per-agent knob.
  - Update the team-layout diagrams (README.md:273, 290) from `.claude-kit/` submodule to the plugin-first install.
  - Add a Usage section for the spec skill, format-consistent with the other skills' entries.
- Out:
  - Repositioning/marketing rewrite; structural README reorganization.

#### Acceptance Criteria (DoD)
- [ ] Given the updated README, when grepped for "v0.1", "33 agents", "opus (21", and ".claude-kit/", then zero matches remain (or only mentions explicitly marked as historical context).
- [ ] Given the agents table, when compared against `agents/*.md`, then every agent file has a row (including the 3 auditors) and the stated total matches the roster count asserted by `tests/test_agent_effort.py`.
- [ ] Given the skills documentation section, when the spec skill entry is read, then it includes a Usage section consistent in format with the other skills.

#### Implementation Notes
- Cross-check counts against the generators, not by hand: roster = `ls agents/*.md | wc -l` and the count assertions in `tests/test_agent_effort.py`; skills = the gen_skills.py skill list.
- The issues.md header (line 5) also states the counts — that header was updated by ISSUE-034 and should already say 32/28; do not touch existing issue blocks.
- ISSUE-005 is the precedent for this sweep; reuse its verification approach.

#### Tests
- [ ] Lightweight consistency test (new or extended in test_integration): README's stated agent count equals `len(glob("agents/*.md"))`; README contains no ".claude-kit/" submodule reference outside explicitly-historical text.
- [ ] Grep-assertions for the removed stale strings ("opus (21", "33 agents").

#### Rollback
`git revert` — docs-only.

---

### ISSUE-041: Extract shared UI/UX design-philosophy fragment — dedupe uiux/mobile/desktop boilerplate

> 4-way repo audit 2026-08-10 (finding 6). The uiux / mobile-uiux / desktop-uiux skill templates and their three developer agents each carry 60–70 parallel lines of near-identical boilerplate (design-philosophy derivation, token compliance rules, self-review checklist). Six copies drift independently — the same class of duplication the `{{PREAMBLE}}` token in gen_skills.py/preambles.py already solved for skill preambles.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-10 repo audit)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-041-uiux-philosophy-dedup
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/69
- PR: https://github.com/pillip/claude-dev-kit/pull/72
- Depends-On: ISSUE-036 (serialize gen_skills.py regeneration — both issues regenerate overlapping generated skill files)

#### Goal
The shared design-philosophy/token-compliance/self-review boilerplate exists exactly once as a canonical fragment; the three uiux skill templates consume it via a token, and the three agent copies are drift-guarded against it.

#### Scope (In/Out)
- In:
  - Extract the shared lines from `skills/{uiux,mobile-uiux,desktop-uiux}/SKILL.md.tmpl` into a canonical fragment resolved by gen_skills.py (e.g. a `{{DESIGN_PHILOSOPHY}}` token alongside `{{PREAMBLE}}`, sourced from preambles.py or a sibling fragments module). Platform-specific deltas stay inline in each tmpl.
  - Reconcile `agents/{uiux-developer,mobile-uiux-developer,desktop-uiux-developer}.md`: agents are static (not generated), so align their copies verbatim with the canonical fragment and add a drift-guard test comparing agent text against the canonical constant.
  - Regenerate all skills via `python3 scripts/gen_skills.py`.
- Out:
  - Changing the philosophy/token-rule CONTENT itself (wording unification of accidental divergence is allowed; note each unification in the PR).
  - figma-converter, design-auditor, ui-reviewer texts.
  - Introducing agent-file generation infrastructure (drift-guard test is the cheap sufficient mechanism).

#### Acceptance Criteria (DoD)
- [ ] Given the three uiux tmpls, when diffed after extraction, then the shared boilerplate appears only as the fragment token — no inline copy survives in any tmpl.
- [ ] Given the regenerated SKILL.md files, when compared against pre-change output, then every rule/checklist item present before is still present (semantic equivalence; deliberate wording unifications listed in the PR description).
- [ ] Given a future edit to the canonical fragment without syncing agent files, when the test suite runs, then the drift-guard test fails and names the out-of-sync agent file.

#### Implementation Notes
- Follow the existing token mechanism: `scripts/gen_skills.py` maps `"PREAMBLE": _resolve_preamble` — add the fragment resolver next to it; keep the fragment text in `scripts/preambles.py` or a new `scripts/fragments.py` importable by both gen_skills.py and the drift-guard test.
- Before extracting, three-way-diff the six copies to catalog existing divergence — some deltas are intentional platform specifics (keep inline), some are drift (unify into the fragment).
- CI's `gen_skills.py --dry-run` freshness gate protects the skill side; the drift-guard test protects the agent side.

#### Tests
- [ ] Drift-guard test: each of the three agent files contains the canonical fragment text verbatim (normalized whitespace).
- [ ] Generated-output test: each of the three generated SKILL.md files contains the fragment content exactly once; no duplicated section headers.

#### Rollback
`git revert` the extraction + regeneration commit; the inline copies return.

---

### ISSUE-042: Set disable-model-invocation: true on the sprint skill

> 4-way repo audit 2026-08-10 (finding 7). Every other repo-mutating orchestrator (implement/review/ship/kickoff/scan) sets `disable-model-invocation: true`; `skills/sprint/SKILL.md.tmpl` has no such line at all — leaving the HEAVIEST autonomous orchestrator (implements, reviews, and ships every backlog issue) model-invocable without an explicit user command.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-10 repo audit)
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-042-sprint-disable-model-invocation
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/61
- PR: https://github.com/pillip/claude-dev-kit/pull/64
- Depends-On: none

#### Goal
The sprint skill can only be triggered by an explicit user invocation, and a lint test guarantees every repo-mutating orchestrator keeps `disable-model-invocation: true`.

#### Scope (In/Out)
- In:
  - Add `disable-model-invocation: true` to `skills/sprint/SKILL.md.tmpl` frontmatter; regenerate via gen_skills.py.
  - New lint test enumerating the repo-mutating orchestrator set {implement, review, ship, kickoff, scan, sprint} and asserting each generated SKILL.md frontmatter sets the flag true — so a future orchestrator can't silently omit it.
- Out:
  - Any change to sprint's workflow body or allowed-tools.
  - Flipping the flag on non-orchestrator skills (migrate/devops/etc. stay `false` deliberately).

#### Acceptance Criteria (DoD)
- [ ] Given the regenerated `skills/sprint/SKILL.md`, when its frontmatter is parsed, then `disable-model-invocation` is `true`.
- [ ] Given the new lint test, when any of the six orchestrators' frontmatter lacks the flag or sets it false, then the test fails naming the offending skill.

#### Implementation Notes
- Frontmatter lives at tmpl lines 1-6 (name/description/argument-hint/allowed-tools — the flag line is currently absent entirely, unlike skills that set it `false`).
- Reuse the frontmatter parsing already available to tests (same approach as `scripts/validate_frontmatter.py`); keep the orchestrator set as an explicit constant in the test so additions are a conscious decision.

#### Tests
- [ ] Lint test as above (six orchestrators, flag true).
- [ ] `python3 scripts/gen_skills.py --dry-run` clean (CI freshness gate).

#### Rollback
`git revert` — one frontmatter line + regeneration + test.

---

### ISSUE-043: Remove dead scripts, untrack committed __pycache__, gitignore .claude/run/

> 4-way repo audit 2026-08-10 (findings 8 + 11). Dead code: `scripts/ensure_permissions.py` and `scripts/ensure_gh.sh` have zero callers; `scripts/kit_root.sh` is referenced only by its own test (all wrappers inline their own root resolution); `scripts/lint_skill_cache_order.py` is wired to neither CI nor any skill. Build artifacts: `scripts/__pycache__/` is tracked with 46 .pyc files — including compiled remains of DELETED modules (install_packs, validate_pack_manifest install-path variant) — despite `.gitignore` line 1 already listing `__pycache__/` (committed before the ignore). Finding 11: `.claude/run/` telemetry files show up as untracked noise in every `git status`.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-10 repo audit)
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-043-dead-code-gitignore-hygiene
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/66
- PR: https://github.com/pillip/claude-dev-kit/pull/68
- Depends-On: none

#### Goal
No dead scripts, no tracked build artifacts, and no `.claude/run/` noise in `git status`.

#### Scope (In/Out)
- In:
  - Delete `scripts/ensure_permissions.py` and `scripts/ensure_gh.sh` (re-verify zero callers by grepping scripts/skills/agents/tests/docs/hooks first).
  - Delete `scripts/kit_root.sh` plus its test (test-only surface; wrappers inline their own resolution per ISSUE-023).
  - `scripts/lint_skill_cache_order.py`: default is delete per the audit; the alternative is wiring it into ci.yml as a step — pick ONE in the PR and state why. Do not leave it orphaned.
  - `git rm -r --cached scripts/__pycache__/` (ignore rule already exists — this only untracks).
  - Add `.claude/run/` to `.gitignore`.
- Out:
  - Any behavior change to live scripts; `validate_pack_manifest.py` (the live pack-authoring lint kept by ISSUE-027) stays.

#### Acceptance Criteria (DoD)
- [ ] Given the repo after cleanup, when grepping for `ensure_permissions|ensure_gh|kit_root.sh|lint_skill_cache_order` across the tree, then zero live references remain (or, if the wiring alternative was chosen for lint_skill_cache_order, it appears exactly once as a ci.yml step).
- [ ] Given `git ls-files`, when filtered for `__pycache__` or `.pyc`, then zero tracked paths remain.
- [ ] Given a session that writes `.claude/run/` telemetry, when `git status` runs afterward, then those files do not appear as untracked.

#### Implementation Notes
- Deleting kit_root.sh requires removing/adjusting its test file — run the full suite after; nothing else imports it.
- `git rm --cached` (not plain `rm`) for the pycache so local interpreter caches keep working; the directory regenerates ignored.
- Note the house pre-commit WATCH_PATTERNS convention: if this repo's rule-sync hook is active, a `.gitignore`-class change may want a docs sync commit — check before pushing.

#### Tests
- [ ] Existing suite green after deletions (kit_root.sh test removed with its subject).
- [ ] Grep-guard assertion (extend the ISSUE-027-style guard test) blocking re-references to the removed script names.

#### Rollback
`git revert` restores the files; untracked-cache state is harmless either way.

---

### ISSUE-044: Fix CI environment mismatch + gate_server.sh process-group cleanup

> 4-way repo audit 2026-08-10 (findings 9 + 13, folded — two small infra-hygiene fixes, one PR). CI: `ci.yml` installs via pip while the house standard is uv; `pip install -e ".[dev]" 2>/dev/null || true` (ci.yml:28) swallows dev-extras failure entirely; pyproject's `asyncio_mode = "strict"` is dead config (pytest-asyncio absent → PytestConfigWarning on every run); `python` vs `python3` mixed across ci.yml:35-49. gate_server: `cleanup()` (gate_server.sh:52-61) kills only `$SERVER_PID` despite its comment claiming "kill process group to catch child processes" — servers that fork (npm dev servers, uvicorn --reload) leak orphans.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-10 repo audit)
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-044-ci-env-gate-server-cleanup
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/67
- PR: https://github.com/pillip/claude-dev-kit/pull/70
- Depends-On: none

#### Goal
CI fails loudly on install problems, runs warning-clean under a consistent interpreter/tooling setup, and gate_server.sh actually terminates the server's whole process group on exit.

#### Scope (In/Out)
- In:
  - ci.yml: migrate dependency install to uv (house standard) OR minimally keep pip but remove the `2>/dev/null || true` swallow — either way, a failed dev-extras install must fail the job.
  - Resolve the asyncio config mismatch: add pytest-asyncio to dev deps OR delete `asyncio_mode = "strict"` from pyproject — whichever matches actual usage (no async tests today → delete is likely right).
  - Unify interpreter invocation style (`python` vs `python3`) across ci.yml:35-49.
  - gate_server.sh: start the server in its own process group (e.g. `setsid` / `set -m`) and make `cleanup()` signal the group (`kill -- -"$SERVER_PID"`), preserving the existing graceful-then-`kill -9` escalation and the exit-code contract (125 on immediate exit, health-check timeout behavior).
- Out:
  - Raising `--cov-fail-under`; adding new CI jobs; changing gate semantics or health-check polling.

#### Acceptance Criteria (DoD)
- [ ] Given a broken dev-extras spec, when the CI install step runs, then the job fails instead of continuing silently.
- [ ] Given the CI pytest run, when its warnings are inspected, then no PytestConfigWarning about asyncio_mode appears.
- [ ] Given ci.yml, when interpreter invocations are grepped, then a single consistent form is used throughout.
- [ ] Given a START_CMD that spawns a child process (e.g. a shell wrapper forking a worker), when gate_server.sh exits via its cleanup trap, then both the server and its children are terminated — no orphan survives.
- [ ] Given a normal single-process server, when gate_server.sh runs its happy path, then behavior and exit codes are unchanged.

#### Implementation Notes
- uv migration keeps the local/CI environments aligned with the ground rules (`uv sync` / `uv run pytest`); if staying on pip for runner-speed reasons, say so in the PR — but the failure-swallowing goes regardless.
- Per the house pre-commit convention, ci.yml/pyproject changes are WATCH_PATTERNS files — include the rules-doc sync commit if that hook is active in your checkout.
- gate_server portability: macOS ships no `setsid` by default — `set -m` + `kill -- -$!`, or a `perl -e 'setpgrp...'`/python wrapper, are the portable options; the kit runs on darwin (dev) and linux (CI), so test both signal paths.
- Careful with `eval "$START_CMD" &`: the process group leader must be the eval'd shell, and `kill -0` liveness checks in the retry loop need updating to probe the group.

#### Tests
- [ ] Bash-level test: launch gate_server.sh with a fixture command that forks a child (`bash -c 'sleep 60 & sleep 60'` style), terminate, assert neither PID survives.
- [ ] Existing gate_server tests (health-check success/timeout/immediate-exit) still pass.
- [ ] CI changes are self-validating on the PR run: green job + zero PytestConfigWarning in the log.

#### Rollback
`git revert`; both files are self-contained (workflow + one script).

---

### ISSUE-045: Add tests for the Figma visual-diff family + validate_frontmatter.py

> 4-way repo audit 2026-08-10 (finding 10). The Figma visual-diff family — `verify_visual_diff.py`, `verify_computed_styles.py`, `verify_structural_match.py`, `verify_layout.py`, `generate_figma_css.py` (~100KB combined, several wired as BLOCKING review checkpoints) — has zero tests. `validate_frontmatter.py` is a CI gate with no unit coverage: a regression there silently weakens the gate for every PR.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-10 repo audit)
- Priority: P2
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-045-figma-verify-frontmatter-tests
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/71
- PR: https://github.com/pillip/claude-dev-kit/pull/73
- Depends-On: none

#### Goal
The six untested scripts have unit coverage of their core comparison/generation/validation logic, runnable without Chromium or network, so checkpoint-gate regressions fail the build instead of silently passing reviews.

#### Scope (In/Out)
- In:
  - `validate_frontmatter.py`: fixture-driven unit tests — valid frontmatter, malformed YAML, missing required keys, frontmatter-not-at-byte-0 (the ISSUE-035 failure mode), and the exit-code contract CI relies on.
  - Visual-diff family: unit/characterization tests for the pure logic — diff-threshold math and image comparison on tiny synthetic PNGs (verify_visual_diff), token-vs-computed-style comparison on fixture dicts (verify_computed_styles), element-presence matching against fixture design_data.json (verify_structural_match), spatial-relationship assertions on synthetic layouts (verify_layout), CSS output from fixture design data (generate_figma_css).
  - Chromium/rendering/network paths stay behind mocks or `-m integration` marks per the pytest ground rules — the default suite must not launch a browser.
  - Minimal behavior-preserving seams only where a script is untestable as-is (e.g. extracting a compare function from an inline `main`); no logic changes.
- Out:
  - Raising the global `--cov-fail-under`; refactoring the family's architecture; testing actual Figma API fetch (figma_fetch.py is out of scope).

#### Acceptance Criteria (DoD)
- [ ] Given the frontmatter fixture set (valid / malformed YAML / missing keys / frontmatter below byte 0), when the validate_frontmatter tests run, then each case asserts the intended pass/fail and exit code.
- [ ] Given synthetic fixtures (tiny PNGs, design_data.json, computed-style dicts), when the visual-diff family tests run, then each of the five scripts' core comparison/generation functions is exercised and the default suite completes without launching Chromium or touching the network.
- [ ] Given the coverage report scoped to the six scripts, when the suite runs, then every script reports non-zero coverage and the combined statement coverage of the six is at least 40%.

#### Implementation Notes
- Threshold semantics are load-bearing: visual-diff blocks at 1% (same-renderer) with a 5% Figma-PNG fallback — encode both numbers in tests so silent threshold drift becomes a failure (same predictability-guard spirit as test_verify_checkpoint_contract.py).
- Reuse fixture style from existing tests; a shared `tests/fixtures/figma/` design_data.json fixture serves structural-match, layout, and CSS-generation tests.
- Image fixtures: generate 4x4-pixel PNGs in-test (stdlib or whatever imaging lib the scripts already use) rather than committing binaries where possible.
- Mind the ISSUE-021 lesson: if any test needs an optional dep (Pillow etc.), skip cleanly when absent rather than erroring.

#### Tests
- [ ] tests/test_validate_frontmatter.py — fixture matrix + exit codes.
- [ ] tests/test_figma_verify_family.py (or per-script files) — comparison math, matching, CSS generation, threshold constants, no-browser guarantee (assert no playwright/chromium import at collection on the default path).

#### Rollback
Tests-only PR — revert freely; no runtime surface touched.

---

### ISSUE-046: Fix verify_checkpoint.py's 60s pytest timeout breaking the GREEN gate and hollowing the RED gate on 4-minute suites

> Critical infrastructure finding, verified live during ISSUE-036's IMPLEMENT phase (2026-08-10). `scripts/verify_checkpoint.py` hard-codes `timeout=60` on its full-suite pytest subprocess runs, but this repo's suite now takes ~4.5 minutes (1122 passed, 2 skipped). Consequence 1 — **blocking GREEN gate can never pass**: `verify_implement_test` → `_run_python_tests_with_coverage(cwd)` runs `python3 -m pytest -q --tb=short --cov=. ...` with `timeout=60`; on timeout `_run()` returns the sentinel exit 124, which is treated as "pytest failed" → `bash scripts/checkpoint.sh --skill implement --phase test --issue <ID>` exits 1 deterministically, regardless of code state. This blocks EVERY implement pipeline in this repo (ISSUE-036 hit it; ISSUE-037/038 will hit it identically). The fallback plain-pytest run carries the same `timeout=60`. Consequence 2 — **RED gate passes spuriously**: `verify_implement_red` has inverted logic (non-zero pytest exit = "tests fail as expected" = PASS); the same 60s timeout → exit 124 → RED "passes" even if the new tests would actually pass, so the gate no longer verifies genuine RED for suites >60s. Related weaknesses: the verifier invokes bare `python3 -m pytest` (whatever interpreter is on PATH — here anaconda) instead of the repo's declared runner (`uv run pytest`, per CLAUDE.md/pyproject), and there is no CLI flag or env var to override the timeout (`checkpoint.sh` passes args straight through; argparse only has --skill/--phase/--issue).

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; discovered during ISSUE-036 implement, 2026-08-10)
- Priority: P0
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-046-checkpoint-test-timeout
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/53
- PR: https://github.com/pillip/claude-dev-kit/pull/54
- Depends-On: none

#### Goal
Test-related checkpoint timeouts fit the repo's real suite duration — env-configurable (e.g. `KIT_CHECKPOINT_TEST_TIMEOUT`) with a raised sensible default (≥ 600s) for full-suite runs — and the RED gate distinguishes "timed out" (exit 124 → inconclusive → FAIL with a clear message) from a genuine failing-test exit, while `_run()`'s 124 sentinel contract stays intact.

#### Scope (In/Out)
- In:
  - Raise the full-suite test timeout default to ≥ 600s and make it overridable via an env var (e.g. `KIT_CHECKPOINT_TEST_TIMEOUT`, seconds) in `scripts/verify_checkpoint.py`: `_run_python_tests_with_coverage()` (both the `--cov` run and the plain fallback), `verify_implement_red()`, and `_run_js_tests_in_worktree()` (same 60s cap on npm test).
  - RED-gate timeout handling in `verify_implement_red()`: branch on exit 124 explicitly BEFORE the generic non-zero → PASS branch; report "timed out — inconclusive" and FAIL the phase.
  - Keep `_run()`'s exit-124-on-`TimeoutExpired` sentinel contract unchanged (`tests/test_verify_checkpoint.py::test_timeout_returns_124` must keep passing).
  - Unit tests mocking slow subprocesses (no real multi-minute runs in the test suite).
- Out:
  - Mandating the runner switch to `uv run pytest` — consider it (repo's declared runner per CLAUDE.md/pyproject; bare `python3 -m pytest` picks up whatever interpreter is on PATH), but if not verified live in this pass, note it as a follow-up instead.
  - Changing any non-test checkpoint phase, the advisory/blocking tier partition (`test_verify_checkpoint_contract.py`), or checkpoint.sh plumbing.
  - Speeding up the test suite itself.

#### Acceptance Criteria (DoD)
- [x] Given the repo's real, healthy ~4.5-minute suite, when `bash scripts/checkpoint.sh --skill implement --phase test --issue <ID>` runs with the new default timeout, then the pytest subprocess completes (no exit-124 sentinel) and the GREEN gate passes — verified live once on the actual repo.
- [x] Given a full-suite pytest run that exceeds the configured timeout (mocked in tests), when `verify_implement_red` evaluates the result, then exit 124 is reported as timed-out/inconclusive and the RED phase FAILS instead of passing spuriously.
- [x] Given a genuinely failing test run (non-zero, non-124 exit, mocked), when `verify_implement_red` runs, then it still PASSes — the inverted-logic contract for real failures is preserved.
- [x] Given `KIT_CHECKPOINT_TEST_TIMEOUT` set to a custom value, when a test-phase verifier invokes its subprocess (mocked), then the timeout passed to the subprocess call equals the override; when unset, it equals the new default (≥ 600s) — covered by unit tests mocking slow subprocesses, with no real 4-minute runs in the tests.
- [x] Given the existing sentinel test `tests/test_verify_checkpoint.py::test_timeout_returns_124`, when the suite runs, then it passes unchanged — `_run()` still returns 124 on `subprocess.TimeoutExpired`.

#### Implementation Notes
- Affected locations, all in `scripts/verify_checkpoint.py`: `_run()` (timeout sentinel 124 — do not change the contract), `_run_python_tests_with_coverage()` (timeout=60 on both the cov and fallback runs), `verify_implement_red()` (timeout=60 + inverted pass logic), `verify_implement_test()` (consumer of the cov helper), `_run_js_tests_in_worktree()` (same 60s cap for npm test).
- `checkpoint.sh` passes argv straight through and the verifier's argparse only knows --skill/--phase/--issue — an env-var override read inside the verifier needs **no shell changes** and no argparse addition; a single module-level helper (env value → int, fallback default) keeps it one seam.
- RED-gate fix ordering matters: check `rc == 124` before the generic `rc != 0 → PASS` branch; emit a distinct message so a timed-out RED is never mistaken for genuine RED.
- Runner consideration (not mandated): `uv run pytest` matches the house standard and pins the interpreter; if adopted, live-verify under both standalone and plugin layouts before relying on it.
- Verified evidence 2026-08-10: 60s cap → deterministic exit 1 from the implement test phase on a 1122-test/4.5-min suite, independent of code state — this deterministically blocks the active sprint's implement pipeline for ALL issues, hence P0 and no dependency on ISSUE-036 (fix is in scripts/, independent of the in-flight batch).

#### Tests
- [x] `tests/test_verify_checkpoint.py` additions with `_run`/subprocess mocked (fast — no real pytest child runs): GREEN verifier passes on a mocked successful full-suite run and fails on a mocked genuine-failure exit.
- [x] RED verifier distinction matrix (mocked): exit 124 → FAIL with the timed-out/inconclusive message; exit 1 (genuine failing tests) → PASS; exit 0 (tests unexpectedly green) → FAIL.
- [x] Env override: `KIT_CHECKPOINT_TEST_TIMEOUT` set → subprocess receives the override value; unset → the ≥600s default; non-numeric value → falls back to default without crashing.
- [x] Sentinel guard: existing `test_timeout_returns_124` passes unchanged.

#### Rollback
`git revert` — isolated to `scripts/verify_checkpoint.py` + its tests; no state, no generated artifacts, no shell changes.

---

### ISSUE-047: Fix verify_gates.py hard-coded 120s unit-gate timeout (and sibling short caps) breaking blocking ship-smoke gates on multi-minute suites

> High-severity infrastructure finding, verified live during ISSUE-046's IMPLEMENT phase (PR #54, 2026-08-10). `scripts/verify_gates.py` hard-codes short subprocess timeouts that cannot fit this repo's real ~5-minute suite (1133 passed, 2 skipped, ~290s): `run_gate_unit` runs `python3 -m pytest -q --tb=short` with `timeout=120` (line ~330; the npm-test branch at line ~332 carries the same cap), and `_run()` (line 44, default timeout=120) returns a mock CompletedProcess on `TimeoutExpired` (rc 124, stderr `timed out after {timeout}s`) → the unit gate deterministically FAILs on this suite. Live evidence from ISSUE-046's GREEN checkpoint run: `GATE FAIL: unit [blocking] (120.1s) python3: timed out after 120s` (gates were non-blocking in the implement context, so that phase still passed). Ship impact — why P0: post-ISSUE-046, `verify_checkpoint.py::verify_ship_smoke` calls `_run_verify_gates(root, blocking=True)` (line ~1610) and gate failures BLOCK ship, so every SHIP smoke checkpoint on this repo deterministically fails on the unit-gate timeout even after PR #54 merges — verify_gates.py is a separate file, explicitly out of ISSUE-046's scope. This blocks ISSUE-046's own ship-smoke retry AND the parked ISSUE-036/037/038 ships. Like ISSUE-046, the fix self-heals its own ship: post-merge smoke runs the merged (fixed) verify_gates.py.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; discovered during ISSUE-046 implement, 2026-08-10)
- Priority: P0
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-047-verify-gates-unit-timeout
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/55
- PR: https://github.com/pillip/claude-dev-kit/pull/56
- Depends-On: ISSUE-046

#### Goal
The unit gate's subprocess timeouts in `scripts/verify_gates.py` fit the repo's real suite duration — overridable via the SAME `KIT_CHECKPOINT_TEST_TIMEOUT` env var and same ≥600s default that ISSUE-046 introduces in `verify_checkpoint.py` — so blocking ship-smoke gate runs no longer fail deterministically on multi-minute suites, while `_run()`'s timeout-mock contract stays intact.

#### Scope (In/Out)
- In:
  - Raise/env-override the two 120s caps in `run_gate_unit` (`scripts/verify_gates.py` lines ~330-332: the `python3 -m pytest -q --tb=short` run and the `npm test` run) via the SAME seam as ISSUE-046: `KIT_CHECKPOINT_TEST_TIMEOUT` (seconds) with a ≥600s default, so both harness files stay consistent.
  - Keep `_run()`'s timeout-mock contract intact: `TimeoutExpired` → mock CompletedProcess with rc 124 and stderr `timed out after {N}s` (and the rc-127 `command not found` path untouched).
  - Unit tests with mocked subprocesses — no real multi-minute runs in the test suite.
- Out:
  - Other gates' timeouts (lint 15s, e2e 300s, docker 60s, `server_timeout` config) unless trivially unified via the same helper.
  - Speeding up the test suite itself (the ~244s `test_verify_checkpoint.py` slow-test optimization is a separately logged candidate).
  - Changing the blocking/advisory partition of gates.

#### Acceptance Criteria (DoD)
- [x] Given the repo's real, healthy ~5-minute suite (1133 passed, 2 skipped, ~290s), when a blocking ship-smoke gate run executes (`verify_ship_smoke` → `_run_verify_gates(root, blocking=True)` → unit gate) with the new default timeout, then the pytest subprocess completes (no `timed out after Ns` mock result) and the unit gate passes — verified live once on the actual repo.
- [x] Given `KIT_CHECKPOINT_TEST_TIMEOUT` set to a custom value (subprocess mocked), when `run_gate_unit` invokes pytest or npm test, then the timeout passed to the subprocess call equals the override; when unset, it equals the new default (≥ 600s); a non-numeric value falls back to the default without crashing — matching ISSUE-046's semantics exactly.
- [x] Given a gate subprocess that exceeds its configured timeout (mocked `TimeoutExpired`), when `_run()` handles it, then the timeout-mock contract is preserved — rc 124 with stderr `timed out after {N}s` → gate status `fail` — and the existing `tests/test_verify_gates.py` suite passes unchanged.

#### Implementation Notes
- Affected locations, all in `scripts/verify_gates.py`: `run_gate_unit()` (line ~330 pytest `timeout=120`, line ~332 npm-test `timeout=120` — these two call sites are the fix); `_run()` (line 44, default `timeout=120`, `TimeoutExpired` → mock rc 124 + `timed out after {timeout}s` stderr — do NOT change this contract; leave the module default alone and change only the unit-gate call sites, so other gates keep their current behavior).
- Consistency seam (Depends-On rationale): ISSUE-046 (PR #54) introduces the `_test_timeout()` helper reading `KIT_CHECKPOINT_TEST_TIMEOUT` with a ≥600s default in `verify_checkpoint.py`. Reuse the SAME env var name and the SAME default here. verify_gates.py is standalone (invoked as a subprocess by verify_checkpoint's ship-smoke), so **replicate the small helper locally** rather than importing across scripts — the ~5-line duplication is cheaper than cross-script coupling; add a cross-reference comment in both files (`# keep in sync with verify_checkpoint.py::_test_timeout / verify_gates.py`) so drift is visible. Merge PR #54 first (or rebase on it) to confirm the exact helper name/default before mirroring.
- Verified evidence 2026-08-10 (live, during ISSUE-046's GREEN checkpoint run): `GATE FAIL: unit [blocking] (120.1s) python3: timed out after 120s` — the full suite under a 120s cap is a deterministic timeout, independent of code state.
- Ship-blocking chain: `verify_checkpoint.py::verify_ship_smoke` → `_run_verify_gates(root, blocking=True)` (line ~1610 post-ISSUE-046) → unit `GateResult(blocking=True)` fails → SHIP smoke fails for every issue on this repo. Self-healing property: this issue's own post-merge ship-smoke runs the fixed verify_gates.py, same as ISSUE-046.
- Env-var read inside the verifier needs no shell/CLI changes (same finding as ISSUE-046: no argparse addition required).

#### Tests
- [x] Extend `tests/test_verify_gates.py` (already covers `run_gate_unit` with mocked `_run`): assert the `timeout` kwarg passed to `_run` for BOTH the pytest branch and the npm-test branch — override set → override value; unset → ≥600s default; non-numeric → default without crashing.
- [x] Timeout-contract guard (mocked): a `TimeoutExpired` subprocess yields rc 124 + `timed out after Ns` stderr and the unit gate reports status `fail` — locks the mock contract against regression.
- [x] Existing `tests/test_verify_gates.py` cases pass unchanged (no real multi-minute pytest child runs anywhere in the suite).

#### Rollback
`git revert` — isolated to `scripts/verify_gates.py` + `tests/test_verify_gates.py`; no state, no generated artifacts, no shell changes.

---

### ISSUE-048: Scope implement checkpoints to the branch's own delta (merge-base diff)

> Sprint 2026-08-11 discovered (iteration 8, from ISSUE-044/041 recovery implements). `verify_checkpoint.py`'s `verify_implement_tests_written` computes changed files via `git diff --name-only main`. A recovery worktree based on an OLD main (e.g. 5990c93) lists files that a newer main has since deleted (e.g. `tests/test_dead_script_removal.py` from the ISSUE-043 ship) — they appear in `git diff --name-only main` yet are absent from the worktree tree, so `_has_real_tests` returns False and the implement `tests-written`/hollow-test gate produces a phantom FAIL. Both ISSUE-041 and ISSUE-044 hit this and worked around it by fast-forwarding the worktree to current main before the checkpoints.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-11 sprint discovered)
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-048-checkpoint-merge-base-diff
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/74
- PR: https://github.com/pillip/claude-dev-kit/pull/77
- Depends-On: none

#### Goal
Implement-phase checkpoints judge only the branch's own delta, so a worktree based on a stale main cannot manufacture false hollow-test failures from files the newer main deleted.

#### Scope (In/Out)
- In:
  - Change the changed-file computation in `verify_checkpoint.py` (`verify_implement_tests_written` and any sibling that diffs against `main`) from `git diff --name-only main` to `git diff --name-only $(git merge-base HEAD main)` — the merge-base diff scopes the set to the branch's own commits.
  - Belt-and-suspenders: intersect the diffed-file set with files that actually exist in the worktree before classifying them, so a stale base can never inject a phantom path.
- Out:
  - Changing what counts as a "real test" (the `_has_real_tests` heuristic itself is unchanged).
  - Any other checkpoint's diff semantics beyond the tests-written/hollow-test gate unless it shares the same base bug.

#### Acceptance Criteria (DoD)
- [ ] Given a branch whose merge-base with main predates a main-side file deletion, when the implement tests-written checkpoint runs, then the deleted file does not appear in the changed set and no phantom hollow-test FAIL occurs.
- [ ] Given a normal branch that adds a source file plus its test, when the checkpoint runs, then the test is still detected exactly as before (no regression).

#### Implementation Notes
- `git merge-base HEAD main` is the standard "fork point"; guard for the detached/edge case where merge-base is empty and fall back to the current behavior rather than crashing.
- The worktree-existence intersection also protects the non-recovery path cheaply (a rename showing as delete+add cannot phantom-fail).

#### Tests
- [ ] Fixture-repo test: base commit deletes a test file, branch commits an unrelated source+test; assert the checkpoint passes and the deleted file is absent from the classified set.
- [ ] Existing verify_checkpoint tests pass unchanged.

#### Rollback
`git revert` — isolated to `scripts/verify_checkpoint.py` + its tests.

---

### ISSUE-049: Gate the Figma visual-diff browser auto-install behind an explicit opt-in

> Sprint 2026-08-11 discovered (iteration 8, from ISSUE-045 implement). `_check_playwright()` in `scripts/verify_visual_diff.py` (~47-63) and the equivalent in `scripts/verify_computed_styles.py` (~29-41) shell out to `pip install playwright` + `playwright install chromium` (up to ~180s, network) as an implicit side effect on any import-failure path. A review/CI gate that silently mutates its environment and reaches the network is the same "gate with an unexpected heavy side effect" class as the k6/brew-install and cold-install-timeout findings from earlier iterations.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-11 sprint discovered)
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-049-figma-browser-install-optin
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/75
- PR: https://github.com/pillip/claude-dev-kit/pull/78
- Depends-On: none

#### Goal
The visual-diff family never installs a browser or touches the network as a side effect of being imported/run; heavy auto-provisioning happens only when an operator explicitly opts in, and otherwise the gate skips cleanly with a clear diagnostic.

#### Scope (In/Out)
- In:
  - Put the auto-install path in both scripts behind an explicit opt-in (e.g. `KIT_ALLOW_BROWSER_INSTALL=1`); with the flag unset, `_check_playwright()` reports "browser unavailable — skipping visual diff" and exits via the existing skip/degrade path instead of installing.
  - Keep the network/install code reachable when the flag is set, so opted-in environments behave exactly as today.
- Out:
  - Changing the diff/threshold logic or the skip semantics when the browser genuinely is present.
  - figma_fetch.py / real Figma API paths.

#### Acceptance Criteria (DoD)
- [ ] Given the opt-in flag unset and Playwright missing, when either script runs, then no `pip install` / `playwright install` subprocess is spawned and no network call is made — the gate skips with a diagnostic.
- [ ] Given the opt-in flag set and Playwright missing, when either script runs, then the auto-install path runs exactly as it does today.
- [ ] Given Playwright already present, when either script runs, then behavior is unchanged regardless of the flag.

#### Implementation Notes
- Mock the subprocess boundary in tests — never actually install in the suite (ISSUE-045's tests already mock this boundary; extend them).
- Emit the diagnostic to stderr; keep stdout clean for the gate's machine-readable output.

#### Tests
- [ ] Mocked-subprocess tests: flag off + missing import → install NOT called, skip path taken; flag on + missing import → install called once.
- [ ] Present-Playwright path unchanged.

#### Rollback
`git revert` — two scripts + their tests; no state.

---

### ISSUE-050: Lint the README agents-table Tools/Effort cells against agent frontmatter

> Sprint 2026-08-11 discovered (iteration 6, from ISSUE-040 review). The README staleness sweep (ISSUE-040) fixed the roster count and added the three missing auditor rows, but pre-existing drift remains in rows the sweep did not touch: a11y-auditor and ui-reviewer omit `Bash`; design-auditor lists `Edit, Write` that its frontmatter lacks. The newly added auditor rows were verified correct; the drift is in the older rows and is currently unguarded, so it will silently re-accumulate.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-11 sprint discovered)
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-050-readme-agents-tools-lint
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/76
- PR: https://github.com/pillip/claude-dev-kit/pull/79
- Depends-On: none

#### Goal
The README agents table's Tools (and Effort) cells provably match each agent file's frontmatter, enforced by a test so future drift fails the build.

#### Scope (In/Out)
- In:
  - Extend `tests/test_readme_consistency.py` to parse each agents-table row's Tools/Effort cell and compare it against the corresponding `agents/*.md` frontmatter (`allowed-tools` / effort), naming any mismatching row.
  - Fix the current drift the test surfaces (a11y-auditor / ui-reviewer missing `Bash`; design-auditor's spurious `Edit, Write`) so the new test passes.
- Out:
  - Changing any agent's actual frontmatter/toolset — this is a docs-vs-source reconciliation, source wins.
  - Reformatting the table beyond the cells under test.

#### Acceptance Criteria (DoD)
- [ ] Given the agents table, when each row's Tools cell is compared to that agent's frontmatter `allowed-tools`, then they match exactly (set-equal), and the same for the Effort cell where present.
- [ ] Given a future edit that desyncs a Tools cell from frontmatter, when the suite runs, then the consistency test fails naming the offending row.

#### Implementation Notes
- Reuse the frontmatter parsing already available to tests (`scripts/validate_frontmatter.py` approach); normalize tool-list ordering/whitespace before comparison.
- Treat the agent frontmatter as the oracle; only the README is edited to reconcile.

#### Tests
- [ ] Row-by-row Tools/Effort equality assertion (new in test_readme_consistency.py).
- [ ] The three current drift rows corrected and asserted.

#### Rollback
`git revert` — README rows + one test; docs-only.

---

### ISSUE-051: De-conflict the parallel-review docs/.review scratch path

> Sprint 2026-08-11 discovered (iterations 5/6/7, process friction). The kit's review layer writes scratch artifacts to a FIXED path `docs/.review/{code-review,findings.json,minimality,security-review}.md`. When two or more review branches run in parallel and merge in sequence, every later PR goes CONFLICTING on exactly these files (observed three sprints running: PRs #58, #64, #65, #72, and others — each resolved by `merge origin/main` + `checkout --ours`, ~2 min + a merge commit apiece). The canonical review record already lives per-issue at `docs/review_notes/ISSUE-XXX.md`; only the scratch path collides.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-11 sprint discovered)
- Priority: P3
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-051-review-scratch-path-deconflict
- PR: https://github.com/pillip/claude-dev-kit/pull/81
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/80
- Depends-On: none

#### Goal
Parallel review branches no longer collide on review scratch artifacts — either the scratch path is per-issue, or it is untracked entirely, while the canonical `docs/review_notes/ISSUE-XXX.md` record is preserved.

#### Scope (In/Out)
- In:
  - Pick ONE and state why in the PR: (a) move the scratch artifacts to a per-issue path (e.g. `docs/.review/ISSUE-XXX/…`), or (b) gitignore `docs/.review/` so the scratch files never enter a commit.
  - Update every producer/consumer of the scratch path (reviewer agent, team-lead, review skill, review-merge-auditor, and any checkpoint that reads it) to the chosen scheme.
- Out:
  - Changing the canonical per-issue `docs/review_notes/ISSUE-XXX.md` location or the review findings themselves.
  - Altering review gate semantics.

#### Acceptance Criteria (DoD)
- [ ] Given two review branches created from the same main that both produce scratch artifacts, when the second merges after the first, then there is no conflict on the review scratch path.
- [ ] Given the review flow end-to-end, when a review runs, then the merge-audit / synthesis steps still find their inputs (no broken producer/consumer wiring).

#### Implementation Notes
- Grep the whole tree for `docs/.review` before changing the scheme — the path is referenced across skills, agents, and checkpoints.
- If gitignoring, confirm no checkpoint depends on the file being committed (they are read within a single review invocation, so working-tree presence should suffice).

#### Tests
- [ ] Guard/integration assertion that the review flow writes to the chosen (per-issue or ignored) location; if gitignored, a `git status` after a review shows no scratch artifacts as tracked/untracked-noise.
- [ ] Existing review-layer tests pass unchanged.

#### Rollback
`git revert`; scratch-path scheme reverts, canonical records unaffected.

---

### ISSUE-052: Make sprint_queue crash-recovery aware of already-merged PRs

> Sprint 2026-08-11 discovered (iterations 7/8). Twice this session a ship-phase team-lead died on an API limit BETWEEN the squash-merge and the post-merge smoke checkpoint (ISSUE-043 on spend-limit, ISSUE-045 on session-limit). The issue's `sprint_state.md` phase was still `reviewed`/`shipping` while its PR was already merged and its GH issue CLOSED. `sprint_queue.py next-action` reads only the sprint_state phase cells, so it re-proposed SHIP and the orchestrator had to manually detect "already merged — only smoke + registry finalization remain". Crash recovery in the ship window is currently hand-driven and error-prone (risk of a double-merge attempt).

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-11 sprint discovered)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-052-sprint-queue-recovery-aware
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/82
- PR: https://github.com/pillip/claude-dev-kit/pull/83
- Depends-On: none

#### Goal
When a ship-phase interruption leaves an issue's PR already merged, the queue recognizes it and proposes a finalize-only action (smoke + registry) instead of a full SHIP, so recovery is deterministic and no re-merge is attempted.

#### Scope (In/Out)
- In:
  - In `sprint_queue.py` (and/or a thin recovery helper), for issues at `reviewed`/`shipping`, check the PR's merge state (`gh pr view --json state,mergedAt` / GH issue CLOSED) before emitting a SHIP action; if already merged, emit a `FINALIZE` (smoke + registry) action instead.
  - Make the ship-phase executor idempotent at the merge step: if the PR is already merged, skip merge and proceed to smoke + registry rather than failing.
- Out:
  - Changing the normal (non-crash) SHIP flow.
  - Recovering interruptions outside the ship window (implement/review recovery already works via phase reset).

#### Acceptance Criteria (DoD)
- [ ] Given an issue at phase=reviewed whose PR is already merged (GH state MERGED / issue CLOSED), when `next-action` runs, then it proposes finalize-only (smoke + registry), not SHIP, and never a re-merge.
- [ ] Given a genuinely un-merged reviewed issue, when `next-action` runs, then it still proposes SHIP exactly as today.
- [ ] Given `gh` unavailable or unauthenticated, when the recovery check runs, then it degrades gracefully (falls back to the phase-only decision with a logged warning), never crashing the queue.

#### Implementation Notes
- Keep the GH call optional and cached — the queue runs frequently; one `gh pr view` per reviewed/shipping issue is acceptable, but guard latency and offline use.
- The idempotent merge step is the safety net even if the queue's classification is stale.

#### Tests
- [ ] Unit test with a mocked GH response: reviewed issue + merged PR → FINALIZE; reviewed issue + open PR → SHIP; gh error → graceful phase-only fallback.
- [ ] Ship-executor idempotency test: already-merged PR → merge step is a no-op, smoke+registry still run.

#### Rollback
`git revert` — `scripts/sprint_queue.py` + ship-executor guard + tests; queue reverts to phase-only decisions.

---

### ISSUE-053: Document the KIT_ALLOW_BROWSER_INSTALL + KIT_SPRINT_QUEUE_GH_TIMEOUT env knobs

> Sprint 2 discovered (iterations 1 & 2, from ISSUE-049 and ISSUE-052 reviews). Two behaviour-control env knobs shipped this sprint are documented only in code (module docstrings / a runtime stderr hint): `KIT_ALLOW_BROWSER_INSTALL` (ISSUE-049 — unset by default; set to `1` to let the Figma visual-diff family auto-install Playwright + Chromium instead of skipping) and `KIT_SPRINT_QUEUE_GH_TIMEOUT` (ISSUE-052 — seconds for the sprint_queue merge-state probe, default 10). Neither appears in a user-facing doc. The repo already documents `KIT_CHECKPOINT_TEST_TIMEOUT` (ISSUE-046/047) in both README.md and docs/troubleshooting.md — the same section is the natural home for these two. This is the recurring env-knob-documentation review-lesson pattern (~4 occurrences, all Low), gathered here so the fix is one small docs pass rather than repeated per-knob follow-ups.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- PRD-Ref: none (kit self-development; 2026-08-11 sprint 2 discovered)
- Priority: P3
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-053-env-knob-docs
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/84
- PR: https://github.com/pillip/claude-dev-kit/pull/85
- Depends-On: none

#### Goal
All kit behaviour-control env knobs are documented consistently in the user-facing docs, so an operator can discover `KIT_ALLOW_BROWSER_INSTALL` and `KIT_SPRINT_QUEUE_GH_TIMEOUT` the same way they already find `KIT_CHECKPOINT_TEST_TIMEOUT`.

#### Scope (In/Out)
- In:
  - Add `KIT_ALLOW_BROWSER_INSTALL` and `KIT_SPRINT_QUEUE_GH_TIMEOUT` to the existing env-knob documentation location(s) that already cover `KIT_CHECKPOINT_TEST_TIMEOUT` (README.md and docs/troubleshooting.md), in the same format: name, default, effect, and (for the browser knob) the opt-in-to-install semantics.
  - Source the default values from the code so the docs match the canonical constants (`KIT_SPRINT_QUEUE_GH_TIMEOUT` default 10s; `KIT_ALLOW_BROWSER_INSTALL` unset = skip, `=1` = auto-install).
- Out:
  - Changing any knob's behaviour or default; introducing new knobs.
  - Restructuring the docs beyond adding the two entries (and, if trivial, aligning the three into one consistent list).

#### Acceptance Criteria (DoD)
- [ ] Given the user-facing docs, when `KIT_ALLOW_BROWSER_INSTALL` is searched, then its name, default (unset = visual-diff skips), and the `=1` auto-install opt-in are documented.
- [ ] Given the user-facing docs, when `KIT_SPRINT_QUEUE_GH_TIMEOUT` is searched, then its name, default (10s), and effect (sprint_queue merge-state probe timeout) are documented.
- [ ] Given the documented default values, when they are compared against the code constants, then each matches the canonical source (no drift).

#### Implementation Notes
- Use the current `KIT_CHECKPOINT_TEST_TIMEOUT` entry as the format oracle; place the two new knobs alongside it.
- Canonical values live at `scripts/sprint_queue.py` (`KIT_SPRINT_QUEUE_GH_TIMEOUT`, default "10") and `scripts/verify_visual_diff.py` / `scripts/verify_computed_styles.py` (`KIT_ALLOW_BROWSER_INSTALL != "1"` gate) — read them, do not hand-copy from memory (canonical-env-numbers lesson).

#### Tests
- [ ] Lightweight docs-consistency assertion (extend an existing docs test or add a small one): the user-facing docs mention both new knob names; optionally assert the documented default `10` for the queue timeout matches the code constant so future drift fails.

#### Rollback
`git revert` — docs-only (README.md + docs/troubleshooting.md) plus a small consistency test; no runtime surface touched.

---

### ISSUE-054: Brownfield design path — extract a design system from existing UI code so /uiux can extend instead of replace

> `/uiux` only ever *creates*. Phase 1 step 4 globs existing UI files and reads them "to understand current design patterns and tech stack", but nothing downstream consumes that: Phase 2 unconditionally commits to a new aesthetic direction and a new Signature Move, and Error Handling states prototypes stay pure HTML/CSS regardless of the framework detected. `/scan` has no design dimension (no design_system / design_philosophy output anywhere in its agent chain). `/figma2proto` needs the Figma API. Net effect: a project that already ships a UI but has no Figma file has **no kit path** to "read the design that exists, then add screens that match it" — the user's only options are a from-scratch redesign or hand-writing the design docs.
>
> Verified 2026-08-17 against the installed official plugin catalog: `frontend-design` (Anthropic, single 55-line skill) is greenfield aesthetic guidance with no codebase-extraction mechanism; the only catalog plugin that reads a codebase for design context is `superdesign` (3rd-party, ties output to a hosted canvas product). The platform-native `DesignSync` tool + `/design-sync` skill sync a local component library **to** a claude.ai design-system project — a publish/sync surface, not an extraction one. So no platform capability covers this and, per the platform-first rule, the kit owns it. (The same comparison also produced the ISSUE-041-fragment slop-calibration harvest, landed separately.)

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-054.md
- PRD-Ref: none (kit self-development; 2026-08-17 official-plugin comparison)
- Priority: P2
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-054-brownfield-design-extract
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/88
- PR: https://github.com/pillip/claude-dev-kit/pull/89
- Depends-On: none

#### Goal
Running `/uiux`, `/mobile-uiux`, or `/desktop-uiux` on a project that already has UI code produces design docs that **describe the design already shipping** and new screens that visually belong to it, instead of a fresh aesthetic that contradicts the existing product.

#### Scope (In/Out)
- In:
  - An extraction step that reads existing UI sources (CSS custom properties, Tailwind/theme config, styled-components / RN `StyleSheet` / Electron theme files, component files) and emits `docs/design_system.md` with **observed** tokens — colors, type scale, spacing scale, radii, motion — each tagged with the file it came from.
  - An inferred `docs/design_philosophy.md`: aesthetic name, Signature Move reverse-engineered from what the codebase actually repeats, and an explicit confidence tag per claim (mirroring `/scan`'s CONFIRMED / INFERRED convention).
  - A `create` vs `extend` mode branch across **all three** uiux skills (`/uiux`, `/mobile-uiux`, `/desktop-uiux`): in `extend` mode Phase 2 does not invent a new direction, the design interview reframes to "what should change / what must stay", and each skill's pilot gate judges *consistency with the extracted system* rather than distinctiveness.
  - One platform-parameterized `design-scanner` agent covering all three source maps (web CSS custom properties / Tailwind / styled-components, RN `StyleSheet` + `src/theme/`, Electron renderer CSS + `src/theme/`), not three agents.
  - The shared `create`/`extend` skill text lands as a fragment in `scripts/fragments.py` resolving over the existing `UIUX_SKILLS` tuple, not as three copies.
  - Mode selection: auto-detect existing UI, then confirm with the user (never silently switch modes).
- Out:
  - Refactoring or rewriting the existing UI code.
  - Screenshot/visual-regression comparison against the running app (that is the existing Figma visual-diff family's surface; reuse it later if it fits, do not extend it here).
  - Desktop native chrome (title-bar style, tray, menu structure) as extractable design facts — it has no token to read and stays out of the extracted system (SPEC-054 open question).
  - Any claude.ai `/design-sync` integration.

#### Acceptance Criteria (DoD)
- [ ] Given a project with an existing stylesheet or theme config and no `docs/ux_spec.md`, when any of the three uiux skills runs, then it detects the existing UI, offers `extend` mode, and on confirmation emits `docs/design_system.md` whose token values match the source files (spot-checked, no invented values).
- [ ] Given extraction output, when any token or philosophy claim cannot be traced to a file, then it is tagged INFERRED with its reasoning; every CONFIRMED claim carries a `file:line` reference.
- [ ] Given `extend` mode, when Phase 2 runs, then no new aesthetic direction is invented — the Signature Move is derived from a pattern that already recurs in the codebase, and the pilot gate's specificity check is replaced by a consistency check against the extracted system.
- [ ] Given a project with **no** existing UI code, when any of the three uiux skills runs, then behaviour is byte-identical to that skill's current `create` path (no regression on any platform).
- [ ] Given the same extraction method run against a web, an RN, and an Electron fixture, when the outputs are compared, then all three carry the same provenance and confidence-tagging contract — the platform difference is confined to which files were read.

#### Implementation Notes
- Decided in SPEC-054: **Option A** — one platform-parameterized `design-scanner` agent invoked directly by the three uiux skills, deliberately NOT a `/scan`-family member (`/scan` Step 6 regenerates `issues.md`, too destructive to make a prerequisite for adding a screen). Rejected: inline extraction (shares one context with generation — the failure the Phase 5A pilot gate exists to prevent), extending `codebase-scanner` (couples two consumers to one output contract and breaks its documented no-disk-write rule), and three per-platform scanners (roster 32 → 35, triplicates the provenance contract).
- Roster goes 32 → 33. Update `tests/test_agent_effort.py:60` and both README surfaces (`README.md:16` prose count, agents table at `README.md:537`) — ISSUE-050's linter checks the table against agent frontmatter.
- The `Brief overrides:` mechanism just added to Anti-AI-Slop is the natural place to record "the existing product already does X, and X is a listed tell" so each skill's AI Tell sweep does not fight the codebase.
- Do NOT hand-copy token values into docs — read them from source at generation time (canonical-env-numbers lesson: generated numbers must come from the canonical environment, not memory).
- `scripts/fragments.py` already owns the shared uiux-family design boilerplate and resolves per skill over `UIUX_SKILLS`; the `create`/`extend` branch goes there as a new token, not into three copies.

#### Tests
- [ ] One extraction fixture per platform (web CSS custom properties + component file; RN `StyleSheet` + `src/theme/`; Electron renderer CSS) → extraction produces the expected token set; assert against a pinned fixture, not a smoke "it ran".
- [ ] Mode-detection unit tests per skill: UI present → `extend` offered; no UI → `create`, and each skill's `create` path output is unchanged from its current baseline.
- [ ] Provenance guard: every CONFIRMED claim in generated `design_system.md` resolves to a real `file:line` in the fixture (mutation-test it by deleting the source line and asserting the claim flips or fails). Run it against all three fixtures — this is the shared contract the one-agent decision is betting on.
- [ ] Fragment drift guard: the `create`/`extend` text resolves from `scripts/fragments.py` for all three skills, so a single-skill edit fails the suite (extend the existing `tests/test_design_fragments.py` pattern).

#### Rollback
`git revert` — additive (new mode branch + extraction step/agent). The `create` path is unchanged, so reverting restores today's behaviour exactly.

---

### ISSUE-056: Promote the four model-executed verification sweeps to deterministic validators

> Evolution audit finding 3 (docs/evolution_audit.md): four falsifiable gates live as model-executed grep instructions inside skill prose — the `literal_quote` verbatim check and the Signature Move presence check (uiux/mobile-uiux/desktop-uiux Phase 5.5), the AI Tell sweep (same skills), and the hollow-test predicate (testgen step 3d, test-generator agent). Each is already a checkable predicate; leaving them to model self-assertion is the weakest verification exactly where generation is longest. Promoting them turns A-bucket prose into C-bucket assets and is a prerequisite for cutting the surrounding prose (ISSUE-060).
> (Numbering: ISSUE-055 skipped — the number was consumed by ad-hoc SPEC-055, and a linked `/spec` run on a future ISSUE-055 would collide with that file.)

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-056.md
- PRD-Ref: none (kit self-development; SPEC-055 / docs/evolution_audit.md roadmap item 2)
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-056-sweeps-to-validators
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/97
- PR: https://github.com/pillip/claude-dev-kit/pull/101
- Depends-On: none

#### Goal
The four sweeps run as scripts with exit codes, callable from `checkpoint.sh` phases, so a skipped or hallucinated model self-check can no longer pass the gate.

#### Scope (In/Out)
- In:
  - `literal_quote` verbatim validator: the exact characters of each `literal_quote` appear in rendered prototype HTML (whitespace-insensitive per the existing skill rule; not in comments).
  - Signature Move validator: the named reusable class exists in `styles.css` and is applied on every screen file.
  - AI Tell sweep validator: occurrence-whitelist mechanics per the review lesson (lint for the presence of banned *rendered* patterns, not phrasing blacklists over prose).
  - Hollow-test validator: the existing predicate (`def test_` + assertion/mock/raises; `it(`/`test(` + `expect`/`toBe`/`toEqual`) as a script over a test directory.
  - Unit tests per validator, including mutation-style fixtures (remove the quote/class/assertion → validator fails).
- Out:
  - Wiring the validators into skill prose/checkpoint phases (ISSUE-057 and ISSUE-060 own the call sites).
  - Any new sweep categories beyond the four named.

#### Acceptance Criteria (DoD)
- [ ] Given a prototype fixture whose HTML contains the `literal_quote` characters, when the validator runs, then it exits 0; given the quote is altered by one character or moved into a comment, then it exits non-zero naming the missing quote.
- [ ] Given a screens fixture where one screen lacks the Signature Move class, when the validator runs, then it exits non-zero naming the screen file.
- [ ] Given a test-file fixture containing one assertion-free test function, when the hollow-test validator runs, then it exits non-zero naming the function; given every test asserts, then it exits 0.
- [ ] Given each validator, when its target defect is introduced into the fixture (mutation test), then the validator fails — no validator passes vacuously on an empty input set.

#### Implementation Notes
- Follow the existing verify_* family conventions (exit 0/1/2, `--json` where useful); these land in `scripts/` beside `verify_figma_compliance.py`.
- The AI Tell sweep must use occurrence-whitelists, not phrasing blacklists (review lesson: absence-guards get mutation-tested with actually-removed strings).
- SPEC should decide: one `verify_design_sweeps.py` with subcommands vs four small scripts (measurable comparator: call-site count in ISSUE-057/060 vs file count).

#### Tests
- [ ] Pinned fixtures per validator (pass case + one mutation each), following the verify-family test pattern from ISSUE-045.

#### Rollback
`git revert` — purely additive scripts + tests until ISSUE-057/060 wire them in.

---

### ISSUE-057: Add script checkpoints to the five zero-checkpoint skills

> Evolution audit finding 2: `checkpoint.sh` is invoked by only 8 of 23 skills, and the five skills with the longest prose (kickoff, scan, uiux, mobile-uiux, desktop-uiux) have zero script checkpoints — their "CHECKPOINT — MANDATORY" blocks are model self-assertions. `verify_checkpoint.py` (the engine) already serves 8 other skills; this issue extends its phase coverage to the five orchestration/design skills so artifact presence and structure are verified outside the model.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-057.md
- PRD-Ref: none (kit self-development; SPEC-055 / docs/evolution_audit.md roadmap item 2)
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-057-zero-checkpoint-skills
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/98
- PR: https://github.com/pillip/claude-dev-kit/pull/102
- Depends-On: none

#### Goal
Every prose `CHECKPOINT — MANDATORY` block in kickoff, scan, uiux, mobile-uiux, and desktop-uiux is backed by (or replaced with) a `checkpoint.sh --skill <name> --phase <phase>` call that verifies the phase's artifacts deterministically.

#### Scope (In/Out)
- In:
  - New `verify_checkpoint.py` phase definitions for the five skills (artifact existence + required-section presence, mirroring what the prose blocks currently assert).
  - `.tmpl` edits replacing or backing each prose checkpoint with the script call (two-tier blocking/advisory per the ISSUE-031 convention).
  - Conditional-phase handling for scan (data-model phase only when DB detected) and the uiux extend mode.
- Out:
  - The four design sweeps (ISSUE-056 builds them; wiring them into uiux phases may land here only if 056 has merged, otherwise follows in 060).
  - Changing what the phases require — this issue scripts the existing assertions, it does not strengthen them.

#### Acceptance Criteria (DoD)
- [ ] Given a kickoff run that produced all phase artifacts, when each new checkpoint runs, then it exits 0; given one required file or section is missing, then the checkpoint exits non-zero naming it.
- [ ] Given the five skills' generated SKILL.md files, when grepped, then every `CHECKPOINT` block contains a `checkpoint.sh` invocation (no bare prose self-assertion remains).
- [ ] Given a scan run on a fixture without database usage, when the data-model checkpoint phase runs, then it reports skip (not fail), matching the skill's conditional contract.

#### Implementation Notes
- `verify_checkpoint.py` already encodes per-skill/phase expectations for 8 skills — follow its existing table structure; this is extension, not redesign.
- Keep the blocking/advisory tier assignment conservative: artifact-presence = blocking; cross-document consistency checks stay advisory (they are judgment-shaped).
- Update the team-lead checkpoint-coverage table (agents/team-lead.md) for the new phases.

#### Tests
- [ ] verify_checkpoint unit tests for each new skill/phase pair: full-artifact fixture passes, one-missing-artifact fixture fails, scan's conditional phase skips (extend the existing test_verify_checkpoint pattern).

#### Rollback
`git revert` — checkpoint additions are independent per skill; a single skill's phase set can be reverted without touching the engine's existing 8-skill coverage.

---

### ISSUE-058: Delegation idiom expansion — test execution

> SPEC-019 explicitly flagged test execution as the next delegation candidate ("probe → runtime delegation → synthesizer → merge-auditor → degraded fallback" named "a reusable kit idiom worth investing in"). Today the kit owns test execution end-to-end via `verify_gates.py` (1,014 lines: platform detection + gate running). If the Claude Code runtime exposes a test-execution capability, the kit should probe for it and delegate, keeping `verify_gates.py` as the degraded fallback and its gate-result contract as the synthesis target.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-058.md
- PRD-Ref: none (kit self-development; SPEC-055 / docs/evolution_audit.md roadmap item 4; SPEC-019 follow-up signal from ISSUE-014)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-058-delegate-test-execution
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/99
- PR: https://github.com/pillip/claude-dev-kit/pull/100
- Depends-On: none

#### Goal
Test execution follows the same five-stage idiom as review/research: probe for a runtime capability, delegate when present, synthesize results into the existing gate-result contract, fall back to `verify_gates.py` when absent — with telemetry tagging which path ran.

#### Scope (In/Out)
- In:
  - SPEC first (Spec-Required): survey what runtime capability actually exists for test execution (the SPEC-019 signal predates current runtime builds); if none exists yet, the SPEC documents the probe contract and lands only the `has_skill.py` probe + telemetry, deferring delegation until the capability ships.
  - Probe wiring in the ship/review paths that currently call `verify_gates.py`.
  - Synthesis: runtime results map into the existing per-gate pass/fail/skip/warn + blocking contract consumed by checkpoints.
- Out:
  - Rewriting `verify_gates.py` — it remains the degraded fallback unchanged.
  - CI-side test execution (GitHub Actions) — this is about local gate runs.

#### Acceptance Criteria (DoD)
- [ ] Given the runtime capability is absent (probe exit 1), when `/ship` runs its smoke checkpoint, then behaviour is byte-identical to today's `verify_gates.py` path and telemetry records the degraded tag.
- [ ] Given the runtime capability is present (probe exit 0/2), when the gates run, then the synthesized result carries the same per-gate schema (pass/fail/skip/warn + blocking) the checkpoint already consumes — no consumer change.
- [ ] Given the SPEC finds no runtime capability currently exists, when this issue closes, then the probe + telemetry + documented contract have still landed and the delegation branch is marked dormant with its activation trigger named.

#### Implementation Notes
- Mirror the SPEC-018/019 structure: `has_skill.py` probe semantics (0/2 = attempt, 1 = degrade), telemetry event names analogous to `review_delegated_to_code_review` / `review_degraded_path_used`.
- The gate-result contract is the synthesis target — the deterministic mapper owns schema fidelity, unit-tested like `synthesize_review_notes.py` (no separate merge-auditor; results are structured data, not prose).

#### Tests
- [ ] Probe-absent path: fixture run asserts the verify_gates fallback executes and the degraded telemetry event is emitted.
- [ ] Synthesis mapper unit tests: runtime-shaped fixture input → exact gate-result schema out, including blocking-flag preservation.

#### Rollback
`git revert`; with the probe short-circuiting to the degraded path, reverting only removes the delegation branch — `verify_gates.py` behaviour was never modified.

---

### ISSUE-059: Deflate scaffolding residue — persona blocks, confidence-rating boilerplate, inline prompts

> Evolution audit roadmap 3a: three classes of pure capability-scaffolding (A-bucket) survive across the surface. (1) `## Execution Principles (absorbed from the <persona> — ISSUE-034)` blocks in prd/diagnose/refactor/migrate plus diagnose's step 5.5 six-item cognitive checklist. (2) Self-Review confidence-rating (High/Med/Low) boilerplate in ~22 of 32 agents — SPEC-010 already recorded self-grading sycophancy as a defect, and business-analyst itself declares its Self-Review "not the load-bearing gate"; the load-bearing checks are separate-context auditors and scripts. (3) `/implement`'s ~50-line inline figma-converter prompt duplicating the agent file it invokes.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; SPEC-055 / docs/evolution_audit.md roadmap item 3a)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-059-deflate-scaffolding-residue
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/103
- PR: https://github.com/pillip/claude-dev-kit/pull/106
- Depends-On: none

#### Goal
The three scaffolding classes are removed with behaviour-relevant invariants preserved: prompts shrink, no gate weakens, and the deleted self-checks are demonstrably owned by an external check (auditor, validator, or checkpoint) or acknowledged as dropped.

#### Scope (In/Out)
- In:
  - Delete the four persona blocks and diagnose step 5.5; keep each skill's actual invariants (regression-test rule, one-major-bump rule, behaviour-preserving rule) stated as contract lines where not already.
  - Remove the Self-Review confidence-rating boilerplate from agents where a downstream script/auditor owns the check; keep genuinely distinctive self-checks (e.g., reviewer's false-positive/blind-spot scan, developer's blast-radius check) as explicit exceptions listed in the PR.
  - Replace `/implement`'s inline figma-converter prompt with a reference to the agent definition (single source).
- Out:
  - The uiux triplet skills/agents (ISSUE-060 owns them).
  - Any change to auditors, validators, or checkpoint behaviour.

#### Acceptance Criteria (DoD)
- [ ] Given the edited skills/agents, when grepped, then no `Execution Principles (absorbed from` block and no confidence-rating boilerplate remains outside the documented exception list.
- [ ] Given the full test suite (including preamble/fragment/frontmatter lint tests), when run after the deletions, then it passes — tests that pinned deleted boilerplate are updated in the same PR, not weakened.
- [ ] Given `/implement`'s SKILL.md.tmpl, when the figma loop section is read, then the subagent contract is a reference to `agents/figma-converter.md` plus call parameters, not a duplicated prompt body.

#### Implementation Notes
- Several tests pin agent prompt structure (test_agent_effort, test_design_fragments, test_preambles) — update assertions alongside, never delete a failing test to make the diff pass.
- Where a deleted self-check has no external owner, say so in the PR description (honest-drop list) rather than silently removing the only check.

#### Tests
- [ ] A lint test asserting the persona-block marker and the confidence-rating boilerplate pattern do not reappear (occurrence-whitelist for the documented exceptions).

#### Rollback
`git revert` per file class; deletions are independent across the three classes.

---

### ISSUE-060: Contract-convert the uiux triplet — strip craft tutorials, keep gates and anti-slop contracts

> Evolution audit: the uiux/mobile-uiux/desktop-uiux skills (568/590/648 lines) plus their developer agents (193/241/300 lines) are the kit's largest fast-depreciating surface — craft tutorials (CSS mechanics, motion duration bands, Expo config pins, Electron perf rules) that frontier models absorb release by release. The durable value is the falsifiable gates (pilot gate with separate-context critique, literal_quote, Signature Move, 2–3 cues), the anti-slop trio (banned-defaults, Brief-overrides ledger, self-similarity check), and the cross-document consistency contracts. Depends on ISSUE-056 (sweeps must be scripted before the prose that hosts them is cut) and ISSUE-059 (boilerplate classes removed first so this diff is purely the triplet).

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-060.md
- PRD-Ref: none (kit self-development; SPEC-055 / docs/evolution_audit.md roadmap item 3b)
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-060-uiux-triplet-contract-conversion
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/114
- PR: https://github.com/pillip/claude-dev-kit/pull/116
- Depends-On: ISSUE-056, ISSUE-059

#### Goal
The three uiux skills and their developer agents shrink to contract + gates — platform knowledge the model already has is deleted; every surviving MUST is either a script-checked gate or a named contract — without weakening any existing gate.

#### Scope (In/Out)
- In:
  - Extract the shared surviving text (anti-slop trio, pilot-gate protocol, cross-doc consistency rules) into `scripts/fragments.py` tokens over the existing `UIUX_SKILLS` tuple (the ISSUE-041/054 mechanism), deleting the three near-verbatim copies.
  - Delete craft-tutorial prose: CSS mechanics lists, duration-band tables, Expo dependency pins, Electron perf prescriptions — except items the SPEC explicitly marks as still-failing empirical knowledge, which stay with a KIT-DEBT-style depreciation trigger.
  - Replace Phase 5.5 model-executed sweep instructions with ISSUE-056 validator calls (via ISSUE-057's checkpoint wiring where it exists).
- Out:
  - The pilot gate's separate-context structure (unchanged — it is C-bucket).
  - figma2proto/figma-converter (different pipeline, different issue if ever).
  - Behaviour of `create` vs `extend` modes (ISSUE-054 contract preserved).

#### Acceptance Criteria (DoD)
- [ ] Given the converted skills, when a design run executes on a fixture brief, then every gate that passed/failed before conversion passes/fails identically — gate behaviour is the regression surface, not prose similarity.
- [ ] Given the three SKILL.md.tmpl files, when diffed against main, then shared surviving text exists once in `scripts/fragments.py` and zero times as per-skill copies (extend `tests/test_design_fragments.py`).
- [ ] Given the deleted tutorial content, when the SPEC's keep-list is read, then every retained prescription names its depreciation trigger; everything else is gone (no orphaned MUSTs without an owner gate).

#### Implementation Notes
- SPEC decides the keep-list: which prescriptions are still-failing empirical knowledge (kept with trigger) vs model-absorbed (deleted). Measurable comparator for the decision: spot-check generations with/without the prescription on the current model tier.
- Line counts are an outcome, not a target — do not chase a number; chase "every MUST has an owner".

#### Tests
- [ ] Fragment drift guard extension (single-skill edit of shared text fails the suite).
- [ ] Gate-parity fixture: pilot gate + sweeps produce identical verdicts pre/post conversion on the same fixture.

#### Rollback
`git revert` of the triplet PR restores current prose; ISSUE-056 validators and 057 checkpoints are independent and unaffected.

---

### ISSUE-061: Consolidate the scan-*/greenfield sibling agent pairs behind an evidence-mode flag

> Evolution audit roadmap 5: five agent pairs are near-duplicates by design — planner/scan-planner, qa-designer/scan-qa-designer, architect/scan-architect, data-modeler/scan-data-modeler, requirement-analyst/scan-analyst. Each scan twin deliberately mirrors its greenfield sibling's output template "for downstream compatibility", differing only in the evidence contract (CONFIRMED/INFERRED tags, Evidence fields, audit-not-redesign stance). The output contracts being already identical makes consolidation cheap; the risk is losing the scan twins' forensic posture, which must survive as an explicit mode.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-061.md
- PRD-Ref: none (kit self-development; SPEC-055 / docs/evolution_audit.md roadmap item 5)
- Priority: P2
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-061-scan-sibling-consolidation
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/104
- PR: https://github.com/pillip/claude-dev-kit/pull/107
- Depends-On: none

#### Goal
One agent per domain serves both greenfield and scan invocations, with the evidence contract (provenance tags, Evidence fields, as-is-not-to-be stance) activated by an explicit mode — roster shrinks by up to 5 with zero change to either mode's output contract.

#### Scope (In/Out)
- In:
  - SPEC first: per pair, merge vs keep — ISSUE-034's criterion applies (separate context is a valid reason to keep a twin; the SPEC must argue each pair, not blanket-merge).
  - For merged pairs: an `evidence-mode` section in the unified agent gating the scan-only rules; `/scan` and `/kickoff` invocation prompts updated to select the mode.
  - Roster/test/README sync (test_agent_effort roster, agents table, issues.md header counts are generated or updated per the record-tests lesson).
- Out:
  - codebase-scanner and design-scanner (no greenfield twin; unchanged).
  - Any change to either mode's output document templates — downstream compatibility is the invariant that makes this safe.

#### Acceptance Criteria (DoD)
- [ ] Given a `/kickoff` run on a PRD fixture, when the merged agents produce their documents, then output is template-identical to the current greenfield agents' output (section-level diff, no evidence-mode artifacts leaking in).
- [ ] Given a `/scan` run on a code fixture, when the merged agents run in evidence mode, then every claim carries CONFIRMED/INFERRED + source citation and issues carry Evidence fields — the scan contract survives verbatim.
- [ ] Given the SPEC keeps any pair split, when the decision is read, then it cites which ISSUE-034 criterion applied (not "felt safer").

#### Implementation Notes
- The scan twins' distinctive content is mostly their evidence rules, which read as a self-contained block — extraction into a shared mode section should be mechanical; the hard part is prompt-length budget per agent, which the SPEC should measure.
- Mode selection must come from the calling skill explicitly, never inferred by the agent from context (predictability guard).

#### Tests
- [ ] Per-domain golden-output comparison for both modes against current-main fixtures (template-structure assertions, not byte equality).

#### Rollback
Pairs are independent — revert any single pair's merge without touching the others; the retired twin files restore from git.

---

### ISSUE-062: Dissolve A-bucket conversational agents into their skill contracts

> Evolution audit roadmap 6: five agents' remaining value is invariants their calling skills already state or can absorb — brainstormer and business-analyst (SPEC-018 made the skills own the delegation routing and claim-provenance invariants; the agents' conversational technique is native capability), devops (generic best-practice checklist), documenter ("commands must exist" verification rule + ship-scoped early exit), copywriter (per-screen × per-state inventory contract). Dissolving them continues the ISSUE-034 roster diet with the SPEC-055 criterion: conversation-shaping prompts are A-bucket; only their invariants survive, as skill contract lines.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-062.md
- PRD-Ref: none (kit self-development; SPEC-055 / docs/evolution_audit.md roadmap item 6)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-062-dissolve-a-bucket-agents
- GH-Issue: #105 https://github.com/pillip/claude-dev-kit/issues/105
- PR: #108 https://github.com/pillip/claude-dev-kit/pull/108
- Depends-On: none

#### Goal
Each of the five agents is either dissolved (invariants absorbed into the calling skill, agent file deleted, callers rewired) or kept with a recorded ISSUE-034/SPEC-055 justification — ending with every surviving roster entry holding a stated bucket.

#### Scope (In/Out)
- In:
  - SPEC first, arguing each agent separately (the ISSUE-034 precedent: a blanket audit over-counted; per-agent analysis found fewer true dissolutions).
  - For dissolved agents: invariant absorption into the skill `.tmpl`, caller rewiring (team-lead dispatch table, kickoff/scan orchestration), agent file deletion, roster/test/README sync.
  - Separate-context needs survive dissolution: where a skill used the agent for context isolation (not expertise), the skill keeps a subagent call with an inline contract instead of a roster agent.
- Out:
  - The three uiux developer agents (ISSUE-060 shrinks them in place; dissolution is a later question).
  - architect (plan-mode delegation is its own future idiom candidate, not a dissolution).

#### Acceptance Criteria (DoD)
- [ ] Given a dissolved agent's calling skill, when its workflow runs on a fixture, then every invariant the agent enforced (e.g., business-analyst's no-data literal and single-source range rendering) is still observably enforced — cite where each landed.
- [ ] Given the final roster, when the SPEC's decision table is read, then all five agents have an explicit dissolve-or-keep verdict with the criterion that decided it.
- [ ] Given the full test suite after rewiring, when run, then it passes with roster-pinning tests updated in the same PR.

#### Implementation Notes
- brainstormer/business-analyst were explicitly kept by ISSUE-034 as "029 degraded-path research agents, freshly guard-tested" — the SPEC must address why SPEC-018's landing changes that verdict (the skills now own the degraded path routing) or keep them.
- Deletion order: rewire callers first, delete files last, one agent per commit for revert granularity.

#### Tests
- [ ] Per-dissolved-agent invariant tests at the skill level (the absorbed contract lines are asserted by the same fixtures that previously exercised the agent).

#### Rollback
One commit per agent — revert restores any single agent and its wiring independently.

---

### ISSUE-063: Fix verify_design_sweeps SPEC-056 contract deviations — multi-line CSS evasion, concatenated `all --json`, fail-open `all` without `--class`

> ISSUE-056 review follow-up (docs/review_notes/ISSUE-056.md on branch issue/ISSUE-056-sweeps-to-validators, PR #101): of the 8 Medium findings left unfixed under the minimal-fix policy, three deviate from the SPEC-056 contract itself and sit directly on the invocation surface ISSUE-057/ISSUE-060 will wire: (1) a flex-calc-width declaration split across lines evades detection — SPEC-056 contract 3 deviation (the scan is line-wise where the oracle, the browser's CSS parser, is declaration-wise); (2) `all --json` emits concatenated JSON objects no single `json.loads` can read — contract 5 deviation (machine-readable output); (3) `all` without `--class` exits 0 with the Signature Move sweep silently unenforced — recreating exactly the skipped-self-check hole the validators exist to close. The reviewer recommended batching these into one follow-up so the checkpoint wiring does not inherit them.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: docs/specs/SPEC-056.md (existing — this issue conforms the implementation to it; no new spec)
- PRD-Ref: none (review follow-up; review lesson "hand-rolled parser mirroring an oracle must match its edge cases" — native memory review-lessons.md, ISSUE-042 class)
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-063-sweeps-contract-conformance
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/109
- PR: https://github.com/pillip/claude-dev-kit/pull/111
- Depends-On: ISSUE-056

#### Goal
`scripts/verify_design_sweeps.py` matches SPEC-056 contracts 3 and 5 exactly — multi-line declarations detected, `all --json` parseable in one `json.loads`, and `all` without `--class` fails closed — before ISSUE-057/060 wire it into checkpoint phases.

#### Scope (In/Out)
- In:
  - Normalize CSS to declaration level before the flex-calc-width scan (strip comments, collapse whitespace/newlines) instead of adding a second line-wise regex.
  - `all --json` aggregates every sweep's result into a single parseable JSON document (one top-level object keyed by sweep, matching SPEC-056 contract 5's per-sweep result shape).
  - `all` without `--class` exits non-zero — either a usage error demanding `--class` or an explicit opt-out flag; never a silent 0 with Signature Move unenforced, and the output names the unenforced sweep.
  - Mutation-pair fixtures per fix (defect present → non-zero; defect removed → 0).
- Out:
  - Detection-robustness hardening of the tell/quote matchers (ISSUE-064).
  - Wiring into skill prose/checkpoint phases (ISSUE-057/060 own the call sites).
  - `verify_hollow_tests.py` (no contract deviations recorded against it).

#### Acceptance Criteria (DoD)
- [ ] Given a styles fixture whose flex-calc-width declaration is split across multiple lines (including a variant with an interleaved CSS comment), when the sweep runs, then it exits non-zero naming the declaration exactly as it does for the single-line form; given the declaration is removed, then it exits 0.
- [ ] Given any fixture set, when `verify_design_sweeps.py all --json` runs, then stdout parses with a single `json.loads` call and contains every sweep subcommand's result (SPEC-056 contract 5).
- [ ] Given `all` invoked without `--class`, when it runs, then it exits non-zero and the output names the Signature Move sweep as unenforced — no code path lets `all` report success while silently skipping a sweep.
- [ ] Review-lesson prevention: given each fixed check, when its mutation pair runs (defect present vs removed), then the result flips in both directions — no fix is validated only on the positive fixture.

#### Implementation Notes
- Provenance: docs/review_notes/ISSUE-056.md Medium findings (the three SPEC-contract ones); SPEC-056 contracts 3 and 5.
- Review lesson (native memory, ISSUE-042 class): a hand-rolled parser that mirrors an oracle must match its edge cases — the CSS scan mirrors the browser's declaration-level parsing, so normalize to declarations rather than patching the line regex per evasion variant.
- Keep the verify_* family exit-code conventions (0/1/2) and the per-sweep CLI unchanged; only `all`'s aggregation and the CSS normalization change. Landing before ISSUE-057/060 means the `--json` shape change has zero call-site migrations — hence P1 and the Depends-On ordering.

#### Tests
- [ ] Multi-line and comment-interleaved flex-calc-width fixtures detected identically to single-line; removal flips to pass (extend the ISSUE-056 fixture set).
- [ ] `all --json` output round-trips through `json.loads`; asserted keys cover every sweep subcommand.
- [ ] `all` without `--class` exits non-zero naming Signature Move; with `--class`, behaviour is byte-identical to today.

#### Rollback
`git revert` — self-contained edits to `scripts/verify_design_sweeps.py` + tests; no call sites exist until ISSUE-057/060 wire them.

---

### ISSUE-064: Harden verify_design_sweeps matcher edges — encoded/case tell variants, non-rendered quote placements, zero-screen vacuity, input containment

> ISSUE-056 review follow-up, second batch: the five adjacent Medium robustness findings from docs/review_notes/ISSUE-056.md that are detection-quality issues rather than SPEC-contract deviations — the ai-tell check false-passes on `mock` appearing anywhere in a name; HTML-entity-encoded and case-variant tells go unmatched; the literal-quote validator is satisfied by quote text placed in `data-*` attributes or `<script>` blocks (not rendered text); the ai-tell sweep half-passes vacuously when zero screen files are found; symlinked/out-of-tree inputs are scanned without containment. Split from ISSUE-063 to keep the contract-conformance fix small; same file, so sequenced behind it.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: docs/specs/SPEC-056.md (existing — hardening within its contracts; no new spec)
- PRD-Ref: none (review follow-up; review lessons "occurrence-whitelist over phrasing blacklist" + "mutation-test absence-guards with actually-removed strings" — native memory review-lessons.md)
- Priority: P2
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-064-sweeps-matcher-hardening
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/113
- PR: https://github.com/pillip/claude-dev-kit/pull/115
- Depends-On: ISSUE-063

#### Goal
The design-sweep matchers detect the recorded evasion/false-pass variants and refuse vacuous or out-of-tree input, closing the five robustness findings from the ISSUE-056 review.

#### Scope (In/Out)
- In:
  - Tell matching normalizes HTML entities and case before comparison (decode via `html.unescape`, case-fold), so encoded/case-variant tells are detected like literal ones.
  - Fix the `mock`-anywhere-in-name false pass recorded in the review notes (word-boundary/context-aware match, per the repro in docs/review_notes/ISSUE-056.md).
  - Literal-quote matching counts only rendered text — quote characters appearing solely in `data-*` attributes or `<script>` blocks do not satisfy it (extends the existing not-in-comments rule).
  - Zero screen files → the ai-tell sweep exits non-zero reporting an empty input set (SPEC-056's no-vacuous-pass AC applied uniformly, not half-passed).
  - Input containment: symlinks or paths resolving outside the target tree are skipped-with-report or fail the run — never silently scanned.
- Out:
  - The SPEC-056 contract 3/5 deviations (ISSUE-063).
  - New sweep categories or checkpoint wiring (ISSUE-057/060).

#### Acceptance Criteria (DoD)
- [ ] Given a screens fixture where a banned tell appears HTML-entity-encoded or case-varied, when the ai-tell sweep runs, then it exits non-zero naming the tell, identically to the literal form; removing it flips to pass.
- [ ] Given the review-notes repro where a name merely containing `mock` satisfied the check, when the hardened matcher runs, then the repro fixture no longer false-passes, and a fixture with legitimate usage still passes.
- [ ] Given a prototype whose literal_quote characters appear only inside a `data-*` attribute or a `<script>` block, when the literal-quote validator runs, then it exits non-zero naming the quote as not rendered.
- [ ] Given an input set resolving to zero screen files, when the ai-tell sweep runs, then it exits non-zero reporting the empty input set — no vacuous half-pass.
- [ ] Given a fixture tree containing a symlink that resolves outside the tree, when any sweep runs, then the out-of-tree target is not scanned and the run reports the containment decision.

#### Implementation Notes
- Provenance: docs/review_notes/ISSUE-056.md adjacent Medium findings (branch issue/ISSUE-056-sweeps-to-validators, PR #101).
- Review lessons (native memory): keep occurrence-whitelist mechanics — normalize the haystack (entity-decode, case-fold) rather than multiplying blacklist phrasings; mutation-test every new guard in both directions with the actually-inserted/actually-removed string. Entity handling uses `html.unescape`, not a hand-rolled entity table (oracle-mirroring lesson).
- Same file as ISSUE-063 (`scripts/verify_design_sweeps.py`) — sequenced behind it to avoid conflicting edits; keep each finding's fix a separate commit for revert granularity.

#### Tests
- [ ] Fixture pair per finding (evasion variant detected; removal passes), extending the ISSUE-056/063 fixture set.
- [ ] Containment test: symlink-out-of-tree fixture asserts the target is skipped/failed and the decision is reported.

#### Rollback
`git revert` per finding commit — hardening is additive detection logic; no call-site or output-schema changes.

---

### ISSUE-065: Add provenance, freshness, and consume-once binding to the KIT_GATE_RESULTS_FILE delegation handoff

> ISSUE-058 review follow-up (docs/review_notes/ISSUE-058.md, unresolved High finding; branch issue/ISSUE-058-delegate-test-execution, PR #100): the `KIT_GATE_RESULTS_FILE` handoff artifact has no provenance, freshness, or one-shot binding — a schema-valid forged artifact plus env-var control activates the delegated branch, and probe gating is structurally a no-op because `verify` sits permanently in `RUNTIME_BUILTIN_SKILLS`. Shape validation is not provenance. The risk is bounded while the branch is dormant (nothing sets the env var; the bypass is loud via the unconditional `GATES DELEGATED` stdout marker; the artifact cannot be a committed file), but SPEC-058's Open Questions and test-plan GAP-058a name binding as a REQUIRED precondition before any activation PR wires the delegated branch into a blocking checkpoint. The review-hardening commit 64e4401 already landed shape-validation strictness, `.claude/run/` containment, the unconditional marker, and telemetry hardening — this issue adds the missing provenance layer and keeps activation blocked until it holds.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: docs/specs/SPEC-058.md (existing, lands with PR #100 — this issue closes its Open Questions binding precondition; no new spec)
- PRD-Ref: none (review follow-up; review lessons "workspace-persisted state read by hooks/gates is untrusted input — validate at read time" (ISSUE-038 class) + new "delegation handoff artifacts are forgeable attestations — shape validation is not provenance" — native memory review-lessons.md)
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-065-gate-results-provenance-binding
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/110
- PR: https://github.com/pillip/claude-dev-kit/pull/112
- Depends-On: ISSUE-058

#### Goal
`scripts/synthesize_gate_results.py` accepts a `KIT_GATE_RESULTS_FILE` artifact only when its provenance, freshness, and single-use are verified — refusing and degrading to `verify_gates.py` otherwise — so the binding check, not env-var presence, is the enforced precondition any future activation PR must build on.

#### Scope (In/Out)
- In:
  - Evaluate and implement the three SPEC-058-named mechanisms: (1) token/HMAC binding between the gate invoker and the artifact producer — the invoker (`scripts/verify_checkpoint.py::_run_verify_gates`) generates a per-run nonce/secret before delegation and the artifact must carry a valid MAC over its body; (2) freshness — artifact mtime >= gate-process start time; (3) consume-once — the artifact is deleted/invalidated after a successful read.
  - Refusal guard: when `KIT_GATE_RESULTS_FILE` is set but any binding check fails (missing/invalid MAC, stale mtime, already consumed), `synthesize_gate_results.py` refuses the artifact and degrades to `verify_gates.py`, with a distinct telemetry tag (`binding-rejected` vs the existing capability-absent degradation) and a loud stdout line naming the failed check.
  - Activation-blocked guard test: no blocking checkpoint phase consumes the delegated branch output unless the binding check sits in its path — wiring delegation into a blocking checkpoint without binding must fail the suite.
  - SPEC-058 append (Open Questions resolution): record that binding has landed and is the activation precondition; keep the dormant/activation-trigger documentation accurate.
- Out:
  - Actually activating the delegated branch in any blocking checkpoint (that is the future activation PR this issue gates).
  - Any change to `verify_gates.py` fallback behaviour or the `verify_gates.GateResult` contract consumed by checkpoints.
  - Probe (`has_skill.py`) redesign — binding supersedes the probe as the effective gate; probe exit codes are never treated as authorization.

#### Acceptance Criteria (DoD)
- [ ] Given `KIT_GATE_RESULTS_FILE` points at a schema-valid artifact with a missing or forged MAC, when `synthesize_gate_results.py` runs, then it refuses the artifact, degrades to `verify_gates.py`, returns the degraded path's result, prints the failed binding check, and emits the `binding-rejected` telemetry event — a forged artifact never yields delegated GateResults.
- [ ] Given a validly MACed artifact whose mtime predates the gate-process start time, when it runs, then the artifact is refused as stale and the degraded path executes, identically to the forged case except the named check.
- [ ] Given a valid, fresh, bound artifact consumed once, when a second invocation targets the same artifact, then it is refused (consumed/invalidated after first read) and the degraded path executes.
- [ ] Given a valid, fresh, bound artifact on first use, when synthesis runs, then the produced `GateResult` output and the `GATES DELEGATED` stdout marker are byte-identical to the pre-binding delegated path — no consumer change in `verify_checkpoint.py::_run_verify_gates`.
- [ ] Given the repo after this issue, when the activation-blocked guard test runs, then it verifies no blocking checkpoint path consumes the delegated branch without the binding check, and a fixture simulating unbound wiring fails the test (review-lesson prevention: workspace-persisted state read by gates is untrusted input — validated at read time, in both mutation directions).

#### Implementation Notes
- Provenance of this issue (cited by content; branch files not yet on main): docs/review_notes/ISSUE-058.md High finding — "no provenance/freshness/one-shot binding on the KIT_GATE_RESULTS_FILE handoff; schema-valid forgery + env control activates the delegated branch; probe gating structurally a no-op (`verify` permanently in `RUNTIME_BUILTIN_SKILLS`); shape validation is not provenance". SPEC-058 Open Questions + test-plan GAP-058a: binding is REQUIRED before any activation PR wires the delegated branch into a blocking checkpoint.
- Files: `scripts/synthesize_gate_results.py` (binding verification + refusal/degrade), `scripts/verify_checkpoint.py::_run_verify_gates` (nonce generation, process-start freshness reference, consume-after-read), telemetry schema (new `binding-rejected` event alongside the existing delegated/degraded tags from ISSUE-058).
- Mechanism sketch: HMAC key is per-run and ephemeral (never persisted to the workspace — the artifact lives under `.claude/run/` per the 64e4401 containment, and `.claude/run/` contents are untrusted input at read time, per the ISSUE-038 review lesson). Freshness uses the invoker's own process start, not wall-clock heuristics. Consume-once via unlink or rename-to-`.consumed` after a successful read, checked before parse.
- Review lessons (native memory review-lessons.md): "hook/gate-read workspace cache is untrusted input — validate at read time" (ISSUE-038 cache-poisoning class) and the new lesson from this finding, "delegation handoff artifacts are forgeable attestations — shape validation is not provenance". Mutation-test every guard in both directions (forged → refused, bound → accepted) — never validate on the positive fixture alone.
- The delegated branch stays DORMANT throughout: no runtime sets the env var today, and this issue's guard keeps it that way until the activation PR can point at a passing binding check.

#### Tests
- [ ] Mutation pair: schema-valid artifact with forged/missing MAC → degraded path + `binding-rejected` telemetry; same artifact correctly MACed → delegated path + `GATES DELEGATED` marker.
- [ ] Stale-mtime artifact (mtime < process start) refused; fresh artifact accepted.
- [ ] Consume-once: second read of the same artifact refused; artifact removed/invalidated after the first successful read.
- [ ] Degradation parity: the binding-rejected degraded run's checkpoint-visible result is identical to the capability-absent degraded run (only the telemetry tag differs).
- [ ] Activation-blocked guard: contract test fails when a blocking checkpoint phase is wired to consume delegated results without the binding check in its path.

#### Rollback
`git revert` — binding is additive in `synthesize_gate_results.py`/`verify_checkpoint.py` and the branch is dormant either way, so revert restores the pre-binding dormant state, not an activated unsafe path. The activation-blocked guard test couples any future activation PR to the binding check, so this issue must not be reverted after an activation PR lands without reverting that PR too.

---

### ISSUE-066: Make the SPEC-019 primary path reachable inside /sprint — runtime review skills are uninvokable from sub-task context

> 2026-10 sprint retrospective: all 6 review runs across the SPEC-055 sprint executed the DEGRADED path despite `has_skill.py` probes returning 2 (attempt) — runtime slash-skills (`/code-review`, `/security-review`) are not invokable from sub-task (Task tool) context, where every /sprint review actually runs. The flagship probe → delegate → synthesize → audit → degrade idiom (SPEC-019) is therefore interactive-only today: the kit's main loop never exercises its primary path. The degraded reviewer held up (0 unresolved Critical/High across 10 ships), but the architecture story and the dominant execution path disagree, and every sprint burns the attempt-then-degrade detour per dimension per issue.

<!-- ### ISSUE-066 SHIP NOTE -->
> **Shipped 2026-10-11 (PR #122). Review verdict PASS, 0 Critical / 0 High. AC-2 and AC-3 are met and mutation-pinned; AC-1 is met only in its dormant-landing form and its live-execution clause is NOT satisfied — the checkbox stays unchecked.** SPEC-066 deliberately took the dormant-landing branch (its Option C): the decision module, the `capability-absent` vs `context-unreachable` reason split, and the documented activation trigger all land, but the SPEC-019 primary path still does not execute inside /sprint today, so AC-1's "verified in a live sprint iteration" clause is outstanding.
> 
> **The review CORRECTED the stated cause of that dormancy, and the correction narrows the work left.** SPEC-066 claimed a categorical runtime limitation (no mechanism can reach the primary path from sub-task context). That conclusion is **confounded**: inside a Task sub-agent the *sub-agent's* `tools:` frontmatter wins over the skill's `allowed-tools`, and while `skills/review/SKILL.md` does grant `SlashCommand`, neither `agents/reviewer.md` nor `agents/team-lead.md` grants `SlashCommand` or `Skill` — no kit agent does. A general-purpose Task sub-agent with full tool access *does* receive a `Skill` tool listing both review skills. So SPEC-066 measured the kit's own configuration, not the runtime. The correction is appended to SPEC-066's Open Questions rather than left wrong inside an accepted spec. **ISSUE-072 is the activation trigger for this module** (verify the sub-agent skill-invocation row in `docs/cc_feature_matrix.md` first per the ISSUE-014 rule, then grant on the review path) — and it is what closes AC-1.
> 
> Shipping regresses nothing: the review gave a per-control equivalence verdict on this module's hardened writer and found two controls **stronger** than the baseline. Two ship-time reconciliations are recorded rather than hidden: the `skills/review/SKILL.md{,.tmpl}` same-hunk conflict with ISSUE-067 was resolved in favor of the decide-once structure (ISSUE-067's three `--script review` one-liners dropped as superseded; its brainstorm/bizanalysis one-liners untouched), and the `kit_telemetry` adoption SPEC-066 assumed turned out NOT to be a one-body swap, so it is deferred to **ISSUE-075** — see `docs/telemetry_schema.md`'s Emit-site inventory.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: true
- Spec: docs/specs/SPEC-066.md
- PRD-Ref: none (kit self-development; sprint retro finding; extends SPEC-019)
- Priority: P1
- Estimate: 1.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-066-sprint-primary-path-delegation
- GH-Issue: #119 https://github.com/pillip/claude-dev-kit/issues/119
- PR: #122 https://github.com/pillip/claude-dev-kit/pull/122
- Depends-On: none

#### Goal
A /sprint review runs the SPEC-019 primary path when the runtime capability exists for the session, with the degraded path reserved for genuine capability absence — and telemetry distinguishes "capability absent" from "capability present but unreachable from this context".

#### Scope (In/Out)
- In:
  - SPEC first: enumerate and decide between candidate mechanisms — (a) hoist the review dimensions to the orchestrator level, where slash-skills are invokable, with results handed to the team-lead via an artifact contract (the ISSUE-065 binding pattern is the precedent for safe handoffs); (b) a probe mode that detects sub-task context and reports "unreachable-from-context" distinctly, so skills stop burning attempt-then-degrade detours; (c) any runtime capability that makes slash-skills reachable from sub-tasks, if one exists by implementation time.
  - Telemetry: new event tag separating `capability-absent` from `context-unreachable` degradations.
  - The degraded reviewer path remains fully intact as the fallback.
- Out:
  - Changing review content/dimensions or the synthesizer contract (SPEC-019 scope stands).
  - The research delegation path (/brainstorm, /bizanalysis) — interactive-invoked, unaffected today; follows whatever pattern this SPEC lands, later.

#### Acceptance Criteria (DoD)
- [ ] Given a /sprint review iteration in a session where the runtime review skills are available, when the review phase runs, then the primary path executes (runtime findings reach `synthesize_review_notes.py`) and telemetry records the delegated tag — verified in a live sprint iteration, not only unit fixtures.
- [x] Given a session where the capability is genuinely absent, when the review phase runs, then the degraded path executes unchanged and telemetry records `capability-absent`.
- [x] Given a sub-task context that cannot reach the runtime skills under the chosen design, when the review phase runs, then the detour is not silently retried per dimension — the context decision is made once and recorded as `context-unreachable`.

#### Implementation Notes
- Sprint-retro evidence: iteration 4 review report ("both reviews ran the degraded path despite probes returning 2 — runtime slash-skills uninvokable from sub-task context"); same pattern in iterations 1, 2, 9.
- If option (a) wins, the orchestrator-level run must preserve review independence (separate context from implement) — that constraint is why reviews live in sub-tasks today; the SPEC must address it explicitly.
- Handoff artifacts, if any, follow the ISSUE-065 precedent: provenance-bound, fresh, consume-once — never bare env-var trust.

#### Tests
- [x] Probe/context-detection unit tests for the three telemetry outcomes (delegated / capability-absent / context-unreachable).
- [x] If an artifact handoff lands: binding tests mirroring tests/test_gate_binding.py's mutation pairs.

#### Rollback
`git revert` — the degraded path is never modified, so reverting restores today's degraded-always sprint behaviour.

---

### ISSUE-067: Silent-skip instrumentation must announce itself — unify the telemetry emitter and announce its fallback paths

> 2026-10 sprint retrospective, corrected 2026-10-10. Original reading: two instances of instrumentation silently doing nothing — (1) the ISSUE-002 eval gate skipping on all 10 ships, (2) inconsistent telemetry emission. Instance (1) was mis-attributed: the eval gate (`scripts/eval_review.py`, rubric template, tests, /ship step 8 wiring) was deleted wholesale by PR #92 (commit 2a93d09 — "all 8 review_eval_*.md outputs it produced were never committed") before the 0.6.0 release and therefore before the SPEC-055 sprint. Zero `docs/review_eval_*.md` artifacts means "component removed by design", not "silent skip" — current `skills/ship/SKILL.md` has no eval step; only stale `scripts/__pycache__/` .pyc residue remains. The mis-reading itself is the strongest evidence for the thesis: an instrument's absence produced no signal, and for a full retro cycle that no-signal was confusable with "live gate silently skipping". Instance (2) stands unchanged: ISSUE-065's review `review_degraded_path_used` event was a silent no-op (no shared emitter, `KIT_RUN_ID` unset in sub-task env) while ISSUE-063's sub-task hand-appended JSONL events. An instrument that can no-op without saying so reads as "covered" when it did not run — SPEC-056's no-vacuous-pass rule, applied to the kit's own instrumentation.

> **Amended 2026-10-10** (team-lead pre-implement premise check, commit 2a93d09): evidence paragraph rewritten; Scope In item 1 and AC #1 re-targeted from the removed eval gate to instruments that exist today (the telemetry emit surface). Resurrecting the eval gate is explicitly out of scope — PR #92's deflation decision stands.

<!-- ### ISSUE-067 SHIP NOTE -->
> **Shipped 2026-10-11 (PR #123). All three ACs met; two unresolved High findings are carried by filed follow-ups, not closed here.** Review verdict PASS-with-fixes (3 findings fixed in-review, 0 Critical). Carried gaps: **ISSUE-070** — `emit_event`'s containment check compares two values both derived from the caller-supplied root, so it is structurally unfalsifiable for a non-symlinked root; a planted FIFO at the predictable run path hangs `os.open`; and the docstring's "NEVER raises" is false (reproduced by closing stdout). **ISSUE-071** — `KIT_RUN_ID` has no producer anywhere in the kit, so the fallback announcement fires on 100% of runs (observed live on this ship's own post-merge gate run), which is the shipped instrument re-creating the no-signal-reads-as-all-clear shape one level up. Neither gap blocks the capability this issue delivers.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; sprint retro finding, premise corrected 2026-10-10; extends the ISSUE-001 telemetry surface — the ISSUE-002 eval gate it originally named was removed by PR #92)
- Priority: P1
- Estimate: 1d
- Status: done
- Owner:
- Branch: issue/ISSUE-067-silent-skip-instrumentation
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/120
- PR: https://github.com/pillip/claude-dev-kit/pull/123
- Depends-On: none

#### Goal
Every existing non-blocking instrument — today, the kit's telemetry emits — either runs or announces its skip/fallback with a named reason (the knob or condition in the message), in stdout where the phase report can see it and in the event body where one is written, so "no signal" can no longer be confused with "all clear".

#### Scope (In/Out)
- In:
  - One shared emit helper for kit scripts (append JSONL under `.claude/run/` honoring the existing writer hardening — O_NOFOLLOW, dir containment, truncation per ISSUE-058): hand-rolled per-script emitters and silent no-ops both migrate to it.
  - The helper's own skip/fallback paths each announce instead of silently no-op'ing: absent `KIT_RUN_ID` → documented fallback (generate-and-print, or an explicit `unattributed` run id) with the fallback visible in the event body; containment-violation rejection → named-reason announcement (nothing written outside `.claude/run/`).
  - Audit the existing emit call sites (review/bizanalysis/brainstorm delegation tags, ship, checkpoint) for the same silent-drop shape: every site uses the shared helper or carries a recorded justification.
- Out:
  - Resurrecting the ISSUE-002 eval gate (removed by design in PR #92 / commit 2a93d09 — the deflation principle stands; do not re-add self-referential machinery no user hits).
  - Making any instrument blocking (emits stay advisory/non-blocking).
  - New telemetry dimensions or the deferred ISSUE-001 analytics scope.

#### Acceptance Criteria (DoD)
- [x] Given a kit script emitting through the shared helper, when one of the helper's skip/fallback paths triggers (`KIT_RUN_ID` absent; containment violation rejected), then the condition is announced with the named knob/reason in stdout and — where an event is still written — reflected in the event body; a silent no-op is no longer possible (mutation test both directions: force each path and assert the announcement; clean path asserts no announcement line).
- [x] Given any kit script emitting a telemetry event without `KIT_RUN_ID`, when it emits, then the event is written under the documented fallback instead of silently dropped, and the fallback is visible in the event body.
- [x] Given the emit-call-site audit, when it completes, then every site either uses the shared helper or carries a recorded justification — no hand-rolled appender remains unexamined.

#### Implementation Notes
- Premise correction (2026-10-10): the original "eval gate skipped silently on all 10 ships" evidence was wrong — PR #92 (commit 2a93d09) deleted the gate before the sprint. Do not reference or restore `scripts/eval_review.py`; the stale `scripts/__pycache__/` .pyc files are residue, not a live surface.
- Surviving evidence: iteration 4 report "065's `review_degraded_path_used` telemetry was a silent no-op while 063's sub-task hand-appended JSONL events".
- Review lessons: print the knob name in the failure message it remediates (the `KIT_RUN_ID` fallback and containment-rejection messages must name the condition); workspace-writable event files follow the ISSUE-058 writer hardening; mutation-test announcements in both directions (fallback → announced; clean emit → no announcement line).
- A rejected containment violation cannot carry its announcement in the event (nothing is written) — the stdout/stderr line is the only signal on that path; test it as such.

#### Tests
- [x] Shared-emitter unit tests: with and without `KIT_RUN_ID` (fallback id present in the event body), containment violations rejected with a named-reason announcement, truncation preserved, O_NOFOLLOW honored.
- [x] Per-fallback-path mutation fixtures: force each skip/fallback cause and assert the announcement; clean-path fixture asserts no announcement line (hollow-pass guard).
- [x] Migration pins: each migrated call site emits a schema-identical event through the shared helper (fixture-pin at the delegation seam).

#### Rollback
`git revert` — announcements and the shared helper are additive; instruments stay non-blocking throughout.

---

### ISSUE-068: Discovered issues must enter the sprint queue's visibility automatically

> 2026-10 sprint retrospective: ISSUE-063/064/065 were created mid-sprint by the planner (correctly registered in issues.md Board + Detail) but `sprint_queue.py next-action` never surfaced them — the queue's roster is the sprint_state Issue Progress table, and nothing added rows for the new issues. The orchestrator noticed by cross-reading the Board and hand-added three rows; without that, the sprint would have reported DONE with two P1 review follow-ups (one an unresolved-High security precondition) silently stranded in backlog. State-contract gap between the planner's registration surface (issues.md) and the queue's visibility surface (sprint_state.md).

<!-- ### ISSUE-068 SHIP NOTE -->
> **Shipped 2026-10-11 (PR #121) with UNMET acceptance criteria — AC-1 and AC-3 FAIL.** `augment_roster_from_board` re-derives `watermark = max(rostered_nums)` from the **mutable** sprint_state Issue Progress table while `compute_queues`/`choose_action` order `implement_ready` by **priority, not ID**, so the control re-hides what it surfaced. Replayed on this issue's own motivating case (063/064/065 with the two P1s rostered and 064 still `backlog`): `next-action` returns a bare `DONE`. AC-2 holds only for IDs **above** the watermark. Merged regardless because the rostered-row engine is byte-identical to main (independently verified on the live sprint files) and the PR carries two confirmed High fixes — the huge-ID `int()` crash via CPython's `sys.int_max_str_digits` cap, and discovery starving the STUCK escalation with no terminating counter. **ISSUE-069 carries AC-1 and AC-3; the goal of this issue is NOT reached.** The AC checkboxes below stay unchecked deliberately.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; sprint retro finding; extends ISSUE-052's queue semantics)
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner:
- Branch: issue/ISSUE-068-discovered-issue-queue-visibility
- GH-Issue: https://github.com/pillip/claude-dev-kit/issues/118
- PR: https://github.com/pillip/claude-dev-kit/pull/121
- Depends-On: none

#### Goal
An issue registered in issues.md during a running sprint becomes visible to `sprint_queue.py next-action` without manual state-table surgery — either the queue derives its roster from issues.md directly, or row-creation is an enforced step of the finding-to-issue path.

#### Scope (In/Out)
- In:
  - Decide the mechanism (small enough to not need a SPEC; record the choice in the PR): (a) `sprint_queue.py next-action` treats issues.md as the roster source of truth and auto-considers Board-registered backlog issues absent from the state table (emitting a visibility note), or (b) the team-lead finding-to-issue protocol gains a mandatory "add Issue Progress row" step enforced by `sprint_queue.py validate`.
  - A regression test reproducing this sprint's exact case: Board has a backlog issue with resolved deps, state table lacks its row → next-action must surface it (or validate must fail), not return DONE.
  - DONE-safety: the queue must not report DONE while any Board-registered, non-Manual, dep-resolved backlog issue exists.
- Out:
  - Any change to phase ordering, FINALIZE semantics, or the IRON LAW (ISSUE-052 contract untouched).

#### Acceptance Criteria (DoD)
- [ ] Given a running sprint whose state table lacks a row for a Board-registered backlog issue with resolved dependencies, when `next-action` runs, then the issue is surfaced (targeted or flagged) — never silently ignored.
- [ ] Given the same situation at sprint end, when the queue computes DONE, then DONE is refused or annotated until the stranded issue is acknowledged — a sprint cannot close over invisible ready work.
- [ ] Given the previous sprint's recorded sequence (063/064/065 created in iteration 1, rows absent), when replayed as a fixture, then the fix surfaces all three without orchestrator intervention.

#### Implementation Notes
- Evidence: sprint_state.md recovery log, iteration 2→3 transition (orchestrator hand-added rows 2026-10-09).
- Review lesson 8 applies: loosening the queue's input contract (reading the Board) must be scoped so existing callers' failure modes stay pinned — add fixtures for the legacy exact-table path alongside.

#### Tests
- [ ] Fixture replay of the 063/064/065 case (row-less Board backlog issue → surfaced).
- [ ] DONE-refusal fixture (stranded ready issue at sprint end).
- [ ] Legacy-path pins: existing next-action fixtures unchanged.

#### Rollback
`git revert` — queue/validate changes are self-contained; the manual row-surgery workaround remains documented in the sprint recovery log.

---

### ISSUE-069: Pin the sprint roster boundary at sprint start — stop the watermark ratchet from re-hiding and auto-dispatching Board issues

> ISSUE-068 review triage (2026-10-10; docs/review_notes/ISSUE-068.md + docs/test_plan.md GAP-068a/GAP-068b, PR #121): the discovered-issue visibility control ISSUE-068 added has one mechanism with two High-severity harms. `scripts/sprint_queue.py::augment_roster_from_board` re-derives `watermark = max(rostered_nums)` from the **mutable** sprint_state Issue Progress table on every invocation, while `compute_queues`/`choose_action` order `implement_ready` by **priority, not ID**. **Harm A — the control re-hides what it surfaced**: once a higher-ID discovered issue is rostered, a lower-ID sibling drops below the new watermark and vanishes entirely — no target, no `unrostered` annotation, no `stranded` warning. Replayed on ISSUE-068's own motivating case: with ISSUE-063 and ISSUE-065 rostered (the two P1s dispatched first) and ISSUE-064 still `Status: backlog` with its dependency Board-done, `next-action` returns a bare `DONE` — ISSUE-068's AC-1 and AC-3 failing in exactly the scenario it was filed for. The same shape appears whenever priority inverts ID order (a P0 ISSUE-070 dispatched before a P1 ISSUE-069, independently verified). **Harm B — above-boundary pre-existing backlog is auto-TARGETED, not merely flagged**: the watermark excludes only IDs *below* the roster max, so a sprint deliberately scoped on older debt auto-pulls everything newer into `implement_ready` and drives it through implement -> review -> `gh pr merge`. Verified: roster ISSUE-010..011 with 040/055/066-068 open -> main returns `DONE`, the branch returns `PIPELINE` on three out-of-scope issues. ISSUE-068's AC-1 only requires *flagging*, so autonomous *targeting* of unscoped work is a choice, not a requirement. Every existing CLI test is a single invocation against a hand-written roster whose max is also the global max, so the suite is structurally blind to both harms.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; ISSUE-068 review triage, GAP-068a + GAP-068b; review lessons "Workspace-persisted state consumed by auto-running hooks is untrusted input — validate on read" and "Relaxing a shared CLI/engine contract for a new caller class must be scoped to that class" — native memory review-lessons.md)
- Priority: P1
- Estimate: 1.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-068

#### Goal
`sprint_queue.py` computes Board visibility against a boundary pinned **once at sprint start**, so an issue surfaced in one iteration stays surfaced in the next, and issues newer than a deliberately-scoped roster are flagged without being dispatched.

#### Scope (In/Out)
- In:
  - Persist the boundary: a `- Roster-Watermark: ISSUE-<max rostered ID at sprint start>` line in the sprint_state `## Meta` block — field added to `templates/sprint_state.md`, written by the orchestrator at sprint creation per an instruction in `skills/sprint/SKILL.md.tmpl` step 1 (the skill is **AUTO-GENERATED** — edit the `.tmpl` and regenerate with `python3 scripts/gen_skills.py`; never hand-edit `skills/sprint/SKILL.md`).
  - `augment_roster_from_board` reads the pinned value instead of re-deriving `max(rostered_nums)`; absent or unusable value -> falls back to today's derivation with the fallback named in `reason` (backward compatibility for sprints already in flight).
  - Treat the parsed value as **untrusted workspace input**: canonical-ID fullmatch with a bounded digit count, range sanity against the live Board, duplicate/mis-cased/decorated `## Meta` field variants rejected -> fallback, never a crash and never a silently emptied `unrostered_ids` (the GAP-068h "one bad ID disables the whole control" shape).
  - Dispatch scoping for Harm B: rows synthesized from the Board **above** the pinned boundary are surfaced in `unrostered` but are NOT placed into `implement_ready` unless an explicit opt-in knob is set; the knob gets one line of docs in the owning module docstring and in `skills/sprint/SKILL.md.tmpl` (env-knob lesson).
  - A **two-iteration replay** test harness: invoke `next-action`, apply the resulting roster mutation to the fixture state, invoke again, assert on the second result. This harness is the structural gap — single-invocation tests cannot catch either harm.
- Out:
  - Phase ordering, FINALIZE semantics, the IRON LAW, or any other part of the ISSUE-052 contract.
  - The remaining ISSUE-068 review Mediums recorded as GAP-068c..GAP-068j (row-creation contract for synthesized targets, `stranded` consumer/exit class, `Manual` parse fail-open, fence-blind issue split, raw-roster-cell identity, `gh pr view` positional-ref injection) — triaged separately; do not absorb them here.
  - Renaming the `unrostered` / `stranded` JSON keys the sprint skill and team-lead read.

#### Acceptance Criteria (DoD)
- [ ] Given a sprint whose `## Meta` pins `Roster-Watermark: ISSUE-062` and whose roster has since grown to include ISSUE-063 and ISSUE-065, when `next-action` runs with ISSUE-064 still `backlog` and its dependency Board-done, then ISSUE-064 is surfaced in `unrostered` and named in `reason` — not the bare `DONE` today's re-derived watermark returns.
- [ ] Given any sprint fixture replayed across two consecutive invocations where the first invocation's targets are marked rostered before the second runs, when the second invocation runs, then every issue the first invocation surfaced is still surfaced or targeted by the second — visibility is monotonic within a sprint, and the test fails if the pinned boundary is reverted to the `max()` derivation.
- [ ] Given a priority-inverted pair in one sprint (a P0 whose ID is higher than an open P1's, so priority order inverts ID order), when `next-action` runs after the P0 has been rostered, then the lower-ID P1 is still surfaced — the harm is fixed as a class, not only for the 063/064/065 shape.
- [ ] Given a roster whose pinned boundary is ISSUE-011 while five higher-ID Board issues are open (the reviewer's verified fixture: 040/055/066-068), when `next-action` runs without the dispatch opt-in, then those newer issues appear in `unrostered` and no action targets them — out-of-scope work is flagged, never auto-driven through implement -> review -> merge.
- [ ] Given the same roster with the dispatch opt-in explicitly set, when `next-action` runs, then the above-boundary issues ARE targeted and the opt-in knob's name appears in the emitted `reason`, so the broadened scope is visible in the sprint log rather than inferred.
- [ ] Given a sprint_state `## Meta` with no `Roster-Watermark` line, when `next-action` runs, then behaviour matches the current `max(rostered_nums)` derivation (the TC-068i legacy byte-pins still pass) except for one named fallback note.
- [ ] Given a `Roster-Watermark` value that is malformed, decorated (`**ISSUE-101**`, `ISSUE-101 (retry)`), out of the live ID range, or duplicated in `## Meta`, when the queue reads it, then the value is rejected with the rejection named in output and the derivation falls back — mutation-tested per variant, in both directions (bad value -> rejected + fallback, good value -> honoured).

#### Implementation Notes
- Provenance (branch files not yet on main — cite by content): docs/review_notes/ISSUE-068.md Highs, mirrored as `docs/test_plan.md` GAP-068a (watermark ratchet) and GAP-068b (above-watermark auto-targeting). Both name this exact candidate fix; GAP-068h names the pinned `## Meta` boundary as its remedy too, so it is closed incidentally.
- Files: `scripts/sprint_queue.py` (`augment_roster_from_board` boundary read + validation; `compute_queues`/`choose_action` dispatch scoping), `templates/sprint_state.md` (`## Meta` field), `skills/sprint/SKILL.md.tmpl` (sprint-start write instruction; regenerate via `python3 scripts/gen_skills.py` — the AUTO-GEN header must stay **below** the frontmatter per ISSUE-035's byte-0 rule), `tests/test_sprint_queue*.py` (two-iteration harness).
- No minimal in-file alternative exists for Harm A: the sprint-start boundary is simply not recoverable from mutable state. The opt-in dispatch gate alone fixes Harm B but not Harm A, so land the pinned boundary and use the gate for scoping.
- Review lesson (untrusted workspace input): the `## Meta` block is a workspace-writable file the queue reads back and acts on — validate at read time, treat any violation as "fall back + announce", never as data. Parse the field by collecting **all** occurrences and matching the name case-insensitively (ISSUE-042 duplicate-key pattern), since a duplicate benign-first field is exactly how this control would silently loosen.
- Review lesson (contract relaxation scoped to the new caller class): the legacy exact-table path must keep its pinned failure modes — add the backward-compat fixtures alongside, and keep TC-068d/TC-068i green unmodified.

#### Tests
- [ ] Two-iteration replay of the 063/064/065 case: iteration 1 surfaces/targets 063+065, the fixture is mutated to roster them, iteration 2 still surfaces 064 (the test that fails on main's derivation).
- [ ] Priority-inversion replay (P0 above a P1) across two iterations.
- [ ] Harm B pair: pinned boundary ISSUE-011 with newer issues open -> flagged, never targeted without the opt-in; with the opt-in -> targeted plus the knob named in `reason`.
- [ ] Backward compatibility: `## Meta` without the field -> output equals the legacy derivation (TC-068i byte-pins intact).
- [ ] Untrusted-input matrix: malformed / decorated / out-of-range / duplicated / mis-cased field variants each rejected with a named reason and a fallback, asserted per variant plus a positive control.

#### Rollback
`git revert` — the boundary field is additive in `templates/sprint_state.md` and read with a fallback, so a revert returns to today's derivation without invalidating any sprint_state file already carrying the field (the field becomes an ignored comment-like line). Regenerate skills after the revert (`python3 scripts/gen_skills.py`) so `skills/sprint/SKILL.md` matches its `.tmpl`.

---

### ISSUE-070: Contain the telemetry emitter's write target and make its no-raise/no-hang contract true

> ISSUE-067 review triage (2026-10-10; PR #123): one unresolved High plus two same-module Mediums, all in `scripts/kit_telemetry.py::emit_event`. **High — containment cannot fail**: `emit_event` accepts `project_path`, does `mkdir(parents=True, exist_ok=True)` under it, then appends; the containment check compares two values **both derived from the attacker-supplied root**, so for a non-symlinked root it is structurally unfalsifiable. The review's partial fix (refuse when the project root is not an existing directory) closed only the non-existent-path case — the reviewer re-tested and appending into any existing writable directory still works (`~` and `~/.ssh` demonstrated). Closing it needs a **scope decision** between ISSUE-067's AC-1 ("auto-create, never silently skip") and ISSUE-058's containment invariant ("only ever write inside the kit project"); that decision is this issue. **Medium — a planted FIFO hangs the gate**: the target path `.claude/runs/<run-id>.jsonl` is predictable, and a FIFO planted there blocks `os.open` forever (exit 124). Unlike a raised exception, a hang is not caught by `verify_checkpoint.py`'s wrapper, so it stalls a gate checkpoint. **Medium — the documented contract is false**: the docstring says the helper "NEVER raises", reproduced false by closing stdout (`ValueError: I/O operation on closed file`), where main's pre-extraction emitter returned cleanly. This lands on a deadline: ISSUE-066 is explicitly instructed to adopt this helper at its ship-time rebase and to trust that contract. No FIFO / hardlink / device-node / TOCTOU / stdout-closed test exists anywhere in `tests/`.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; ISSUE-067 review triage — unresolved High + 2 Mediums in the same module; review lesson "Workspace-persisted state consumed by auto-running hooks is untrusted input — validate on read", write-side corollary from the ISSUE-058 review — native memory review-lessons.md)
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-067

#### Goal
`emit_event` writes only inside the kit project it was invoked for, cannot be made to hang by anything planted at its target path, and either honours the "never raises" contract its docstring advertises or stops advertising it.

#### Scope (In/Out)
- In:
  - Make the scope decision and record it in the PR: either `project_path` stops being the containment root (the root is derived independently — `bash scripts/worktree.sh root` / `CLAUDE_PROJECT_DIR` — and a caller-supplied path outside it is refused with a named reason), or auto-create is dropped for non-kit roots. Either way the containment check must compare the resolved target against a root the caller did not supply, so the check is falsifiable.
  - Non-regular-file hardening at the open: refuse FIFOs, device nodes and multiply-linked files (e.g. `O_NONBLOCK` on the open, or `fstat` after `O_NOFOLLOW` with an `S_ISREG` + link-count check) with a named-reason announcement instead of blocking — keeping the existing `O_NOFOLLOW`, dir containment and truncation behaviour from ISSUE-058/067 intact.
  - Make the contract true or true-by-wording: either widen the catch set so "NEVER raises" actually holds (closed streams -> `ValueError`, `OSError`, and `RecursionError`, which is not a `ValueError`), or narrow the docstring to name the raising conditions and pin a handler at every call site. Pick one; pin the chosen contract in tests so ISSUE-066's adopt-at-rebase instruction rests on a tested promise.
- Out:
  - The `KIT_RUN_ID` producer / fallback-noise decision (ISSUE-071) — same module, different defect, separate PR.
  - Making emits blocking, or adding telemetry dimensions.
  - Re-deriving the event schema: the clean-path event body stays byte-schema-identical to what ISSUE-067 ships.

#### Acceptance Criteria (DoD)
- [ ] Given `emit_event` called with a `project_path` outside the kit project that is an existing writable directory (`~`, `~/.ssh`), when it runs, then nothing is created or appended anywhere under that path, the refusal is announced with the named reason, and the same call against the real kit root succeeds — the containment check is proven falsifiable in both directions.
- [ ] Given a FIFO planted at the resolved `.claude/runs/<run-id>.jsonl` target (and, as separate cases, a symlink and a non-regular device node), when `emit_event` runs, then it returns within the test's timeout with the refusal announced and nothing written through the planted node; removing the non-regular-file guard makes this test hang/time out rather than merely assert differently.
- [ ] Given stdout closed by the caller, when `emit_event` runs, then the behaviour matches the module's documented contract — returns without raising if the docstring claims "never raises", or raises exactly the documented exception with a pinned call-site handler if the docstring is narrowed — and the test asserts the chosen contract, not both.
- [ ] Given a normal kit-rooted invocation on the clean path, when `emit_event` runs, then the appended event is schema-identical to ISSUE-067's shipped shape and no refusal or announcement line is printed (hollow-pass guard: the hardening must not make the happy path chatty).

#### Implementation Notes
- Provenance (branch files not yet on main — cite by content): ISSUE-067 review, High "containment compares two attacker-derived values; appending into any existing writable dir still works after the partial fix (`~`, `~/.ssh` demonstrated)"; Mediums "planted FIFO at the predictable run path hangs `os.open` (exit 124), and a hang is not caught by `verify_checkpoint.py`'s wrapper" and "docstring claims NEVER raises; closing stdout raises `ValueError`".
- Files: `scripts/kit_telemetry.py` (containment root derivation, open hardening, contract), its call sites audited by ISSUE-067, and `tests/` (no FIFO / hardlink / device-node / TOCTOU / stdout-closed coverage exists today — this issue creates that family).
- A hang is strictly worse than an exception here because the only wrapper that would have caught it catches exceptions, not stalls: write the FIFO test so the guard's removal is observable as a timeout (bounded `subprocess` timeout or `pytest-timeout`), per the hard-coded-timeout lesson's "handle 124 as a distinct outcome" rule.
- Review lesson (write-side untrusted-input corollary, ISSUE-058): `O_NOFOLLOW` on the open, realpath-contain the target dir, whitelist attacker-influenced name components, truncate attacker-derived payload text rather than dropping the event. This issue adds the missing leg: the containment root itself must not be attacker-supplied.
- Review lesson (forgeable-attestation lesson, point 6): run every `exists()`/`stat` probe of a caller-derived path **after** containment — a pre-containment probe whose refusal reason diverges observably is a filesystem-existence oracle. Keep refusal reasons uniform across the two classes or document the divergence.

#### Tests
- [ ] Containment mutation pair: outside-root existing writable dir -> nothing written + named refusal; real kit root -> event appended.
- [ ] Planted-node family: FIFO (timeout-bounded), symlink, device node, multiply-linked regular file — each refused with a named reason; guard-removal mutation makes the FIFO case hang.
- [ ] Contract test for the chosen no-raise/narrowed-docstring decision, with stdout closed; plus a call-site pin if the docstring is narrowed.
- [ ] Clean-path pin: schema-identical event, zero announcement lines.
- [ ] TOCTOU: target replaced with a non-regular node between the containment check and the open -> refused, not written.

#### Rollback
`git revert` — the hardening is additive inside `emit_event` and emits stay non-blocking either way, so a revert restores ISSUE-067's shipped emitter. If the docstring was narrowed rather than the catch set widened, revert the call-site handlers in the same commit so the contract and its consumers never disagree.

---

### ISSUE-071: Give KIT_RUN_ID a producer or stop announcing its absence on every run

> ISSUE-067 review triage (2026-10-10; PR #123), unresolved High: `KIT_RUN_ID` has **no producer**, so ISSUE-067's fallback announcement fires on 100% of runs and re-creates the failure mode it was built to fix, one level up. Verified: nothing in the kit *sets* the knob (grepped `scripts/ project/ skills/ agents/ templates/ hooks.json settings.snippet.json .github/`), and nothing *reads* `.claude/runs/*.jsonl` on any default path (`scripts/trace_query.py` reads the different `.claude/run/events.jsonl` stream). Net effect: every gate checkpoint in every project prints one `[kit-telemetry] fallback: KIT_RUN_ID unset ...` line and appends to a file no code consumes. A line emitted on every single run carries zero information, so the genuinely exceptional announcements ISSUE-067 added become background noise — against ISSUE-067's own Goal ("'no signal' can no longer be confused with 'all clear'" requires that signal be scarce).

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; ISSUE-067 review triage, unresolved High; review lesson "New env-var knobs need one line of docs at introduction time" — the knob's producer and consumer are the other half of that lesson — native memory review-lessons.md)
- Priority: P1
- Estimate: 1d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-067

#### Goal
A default gate-checkpoint run produces no telemetry fallback announcement, because either `KIT_RUN_ID` has a real producer or the unset-knob path is no longer announced per emit on stdout — leaving the exceptional announcements scarce enough to mean something.

#### Scope (In/Out)
- In:
  - Pick ONE resolution and record it in the PR: (a) **give the knob a producer** — ISSUE-067's own named alternative: generate a run id once per session (the existing once-per-session surface is `session_start.py`; the existing per-project state dir is `.claude/run/`) and export/print it so emits attribute to it; or (b) **demote the always-on path** — the unset-knob notice becomes at-most-once-per-process and/or stderr, while genuinely exceptional announcements (containment refusal, non-regular target, truncation) stay on stdout where the phase report sees them.
  - Either way the always-on stdout line stops: the announcement budget on a clean default run is zero lines.
  - Preserve ISSUE-067's no-silent-no-op property: under (b) the fallback stays visible **in the event body**, which is the durable record; the stdout channel is reserved for conditions a human should act on.
  - Decide and record the fate of the written stream: either a kit script reads `.claude/runs/*.jsonl` on a default path (named in the PR), or the stream is unified with the already-consumed `.claude/run/events.jsonl` that `trace_query.py` queries. A write-only artifact must not be the only thing this instrument produces.
- Out:
  - The containment / FIFO / no-raise defects in the same module (ISSUE-070).
  - New telemetry dimensions or the deferred ISSUE-001 analytics scope.
  - Making emits blocking.

#### Acceptance Criteria (DoD)
- [ ] Given a default project with no kit env knobs set, when a gate checkpoint runs and emits telemetry, then stdout contains zero `KIT_RUN_ID`-unset fallback lines, while forcing an exceptional condition (containment refusal) in the same fixture still prints its announcement — scarcity is asserted alongside retained signal.
- [ ] Given 20 emits within one process and `KIT_RUN_ID` unset, when they run, then at most one unset-knob notice is produced in total across the process (zero if resolution (a) supplies an id), and a per-emit notice fails the test.
- [ ] Given resolution (a), when a session starts, then a run id is produced once and subsequent emits in that session carry it in the event body; given resolution (b), when an emit falls back, then the fallback marker is still present in the event body — the ISSUE-067 "an instrument never no-ops silently" property is asserted under whichever branch ships.
- [ ] Given the stream written after this issue, when the recorded decision is applied, then either a named kit script reads it on a default path or it is unified with `.claude/run/events.jsonl`, and a test pins that the path written is the path read — no write-only artifact survives.

#### Implementation Notes
- Provenance (branch files not yet on main — cite by content): ISSUE-067 review High "`KIT_RUN_ID` has no producer, so the fallback announcement fires on 100% of runs"; producer grep covered `scripts/ project/ skills/ agents/ templates/ hooks.json settings.snippet.json .github/`; consumer grep confirmed `trace_query.py` reads `.claude/run/events.jsonl`, a different stream from `.claude/runs/<run-id>.jsonl`.
- Files: `scripts/kit_telemetry.py` (announcement policy / id resolution), `project/hooks/session_start.py` + `hooks.json` + `settings.snippet.json` if resolution (a) is chosen (both hook surfaces must stay in sync — ISSUE-032 precedent), `scripts/trace_query.py` if the streams are unified.
- Resolution (a) is the stronger fix but touches two hook surfaces and the session contract; resolution (b) is contained to one module. Either satisfies the Goal — the PR must state which and why, so the decision is auditable later.
- Review lesson (env-var knobs): whichever resolution lands, `KIT_RUN_ID` gets one line in the owning module docstring and one in the most relevant user-facing doc, and any surviving message names the knob it remediates.
- Parallelism note: ISSUE-070 edits the same module (containment, open hardening, raise contract) but a disjoint defect — no dependency either way; whichever lands second rebases on the first. Do not absorb the other's scope to avoid a rebase.
- Deflation check (PR #92 precedent): the point of this issue is behavioural — stdout noise on every gate checkpoint in every project, plus writes to an unread file. If the honest resolution is that neither a producer nor a consumer is worth building, then the correct outcome is to remove the stream and the announcement rather than to document the drift; record that as the decision and close the issue on the removal.

#### Tests
- [ ] Clean default run: zero fallback lines on stdout; forced containment refusal in the same fixture still announces (mutation pair, both directions).
- [ ] Repeat-emit budget: 20 emits with the knob unset -> at most one notice; reverting to per-emit announcement fails the test.
- [ ] Branch-specific pin: (a) session-produced id appears in the event body of subsequent emits; (b) fallback marker present in the event body with no stdout line.
- [ ] Path-identity pin: the path written by the emitter is the path the named consumer reads (or the unified `.claude/run/events.jsonl`), asserted from the production constants rather than a re-typed literal.

#### Rollback
`git revert` — under resolution (b) the change is a message-policy diff inside one module; under (a) revert the hook-surface edits together with the emitter change so the id's producer and consumer never disagree. Emits stay non-blocking throughout, so neither direction can break a gate.

---

### ISSUE-072: Verify sub-agent skill invocation in the feature matrix and grant it on the review path if supported

> ISSUE-066 review triage (2026-10-10; PR #122), reviewer-rated Medium but filed at P1 because it is the activation trigger for a dormant ~360-line module and the highest-leverage finding of this batch. **The kit's own agent `tools:` frontmatter is a cause of the SPEC-019 primary path being unreachable — the absence SPEC-066 measured was partly the kit's own configuration, not a runtime limitation.** Independently confirmed by team-lead: `skills/review/SKILL.md` DOES grant `SlashCommand` in `allowed-tools`; but when `/review` runs inside a Task sub-agent the **sub-agent's `tools:` frontmatter wins**, and neither `agents/reviewer.md` (`tools: Read, Glob, Grep, Edit, Bash, Write`) nor `agents/team-lead.md` (`tools: Read, Glob, Grep, Write, Edit, Bash, Task`) grants `SlashCommand` or `Skill` — **no kit agent does**. Meanwhile a general-purpose Task sub-agent with full tool access **does** receive a `Skill` tool listing both review skills; the ISSUE-066 reviewer observed exactly this from inside its own sub-task. `docs/cc_feature_matrix.md` has **no** verified sub-agent skill-invocation row (confirmed), so SPEC-066's activation trigger remains correctly gated on the ISSUE-014 "verify in the matrix first" rule — and SPEC-066's categorical conclusion ("no mechanism can make the primary path execute from the sub-task review context on today's runtime") is **confounded**: the grant was never present during the observation.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: docs/specs/SPEC-066.md (existing, lands with PR #122 — this issue tests its activation trigger and records the result; no new spec: a verification plus a two-line grant is not a design)
- PRD-Ref: none (kit self-development; ISSUE-066 review triage; ISSUE-014 "verify in the feature matrix before relying" rule; review lesson "allowed-tools grants in skill frontmatter must map to actual call sites" — general form of this finding — native memory review-lessons.md)
- Priority: P1
- Estimate: 0.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-066

#### Goal
`docs/cc_feature_matrix.md` carries a locally-verified row for skill/slash-command invocation from Task sub-agent context, and the review path either carries the grant that activates SPEC-066's primary path or carries a recorded refutation that justifies the dormant landing.

#### Scope (In/Out)
- In:
  - Probe and record the matrix row per the ISSUE-014 rule: does a Task sub-agent expose a `Skill` / `SlashCommand` tool, and does the sub-agent's `tools:` frontmatter override the invoked skill's `allowed-tools`? The row states Status, a `local` verification note naming the probe and date, and the consumer issues.
  - If supported: add the grant on the review path only (`agents/reviewer.md`, `agents/team-lead.md`, plus their `.tmpl` sources if generated — regenerate via `python3 scripts/gen_skills.py` where applicable) and confirm `review_context.decide` returns `delegated` from inside a sub-task review, activating SPEC-066's primary path with zero further kit change (its stated activation property).
  - If not supported: record the refutation in the matrix row and append it to SPEC-066, so the dormant landing rests on a measurement rather than an unmeasured assumption.
  - Grant hygiene either way: the grant is added only where a real call site consumes it, and no symmetry grants ride along.
- Out:
  - Changing review dimensions, the synthesizer contract, or the degraded reviewer path (SPEC-019/066 scope stands).
  - Granting `Skill`/`SlashCommand` to any agent outside the review path.
  - The research delegation path (/brainstorm, /bizanalysis) — it follows whatever this measurement establishes, later.

#### Acceptance Criteria (DoD)
- [ ] Given the probe has run, when `docs/cc_feature_matrix.md` is read, then it contains a row for "skill / slash-command invocation from Task sub-agent context" with a Status, a `local` verification note naming the probe and its date, and ISSUE-066/072 as consumers — the ISSUE-014 rule is satisfied before any grant lands.
- [ ] Given the probe shows a sub-agent CAN invoke skills, when the grant is added to the review-path agents and `/review` runs inside a Task sub-agent, then `review_context.decide` returns `delegated` and runtime findings reach `synthesize_review_notes.py` — evidenced by a live run recorded in the PR, not by a unit fixture alone.
- [ ] Given the probe shows a sub-agent CANNOT invoke skills, when the issue closes, then the refutation is recorded in the matrix row and appended to SPEC-066, no grant is added, and a guard test pins that no review-path agent carries an unusable `SlashCommand`/`Skill` grant.
- [ ] Given a grant landed under branch 2, when the grant-hygiene test runs, then every granted tool form has a real call site on the review path and deleting that call site fails the test — the allowed-tools-maps-to-call-sites lesson, applied in the direction this finding exposes (a missing grant that silently disables a path, not an unused grant that widens one).

#### Implementation Notes
- Provenance (branch files not yet on main — cite by content): ISSUE-066 review Medium plus team-lead's independent confirmation of the three facts — `skills/review/SKILL.md` line 6 grants `SlashCommand`; `agents/reviewer.md` line 4 is `tools: Read, Glob, Grep, Edit, Bash, Write` and `agents/team-lead.md` line 4 is `tools: Read, Glob, Grep, Write, Edit, Bash, Task`; `docs/cc_feature_matrix.md` has no sub-agent skill-invocation row (the matrix stops at row 9).
- Sequence matters: the matrix row comes FIRST. Adding the grant before the row would be exactly the ISSUE-014 violation the kit's own rule exists to prevent, and the row is the deliverable that survives even if the grant turns out to be impossible.
- Plugin-shipped agents support `tools:`/`disallowedTools:`/`skills:` per matrix row 6 — check whether the `skills:` field, rather than a `SlashCommand` grant, is the supported mechanism; the probe should distinguish them, because they imply different grant text.
- This refutes a categorical SPEC claim, so the probe transcript (or a reproducible recipe) belongs in the PR: SPEC-066's conclusion is the thing being corrected, and a later reader needs the evidence, not the verdict.
- Review lesson (grants map to call sites): the general form covers both directions — an unused grant widens privilege, a missing grant silently disables a documented path and gets mis-attributed to the runtime. Note the second direction in the lesson when this closes.

#### Tests
- [ ] Matrix-row presence/shape guard: the new row exists with a non-empty Status and a `local` verification note (the row is the ISSUE-014 artifact and must not be droppable silently).
- [ ] Branch 2 (supported): `review_context.decide` returns `delegated` for a sub-task context fixture once the grant is present, and `capability-absent`/`context-unreachable` when it is not — mutation-paired on the grant's presence.
- [ ] Branch 3 (refuted): guard test asserting no review-path agent frontmatter carries a `SlashCommand`/`Skill` grant, with the matrix row and SPEC-066 appendix as the recorded justification.
- [ ] Grant-hygiene pin: each granted tool form on the review path maps to a real call site; deleting the call site fails.

#### Rollback
`git revert` — the matrix row and SPEC-066 appendix are additive records, and the grant is two frontmatter tokens. Reverting the grant returns the review path to the degraded-always behaviour SPEC-066 lands with, which is the fallback either way; keep the matrix row even on a revert, since the measurement stays true independently of whether the kit chooses to use it.

---

### ISSUE-073: Validate the PR ref before the `gh` merge-state probe — an option-shaped Board `PR:` value forges a MERGED verdict

> GAP-068j (docs/test_plan.md, ISSUE-068 review 2026-10-10 / PR #121; **pre-existing from ISSUE-052, live on main today**, hence its own issue rather than a finding against PR #121). The Board `PR:` field value flows into `gh pr view` as a **bare positional** at `scripts/sprint_queue.py:228`, so a value like `PR: --repo attacker/evil` is consumed by `gh` as a **flag**, not a PR reference. A `MERGED` answer sourced from the attacker-chosen repo makes `classify_ship_ready` emit **FINALIZE** instead of SHIP, and `ship_merge_decision` return `skip` through the same poisoned ref — so an **unmerged PR is finalized as `shipped`** and the sprint records as done work that was never merged. Reviewer-reproduced with a logging fake `gh` on the **live rostered** `reviewed` path (`GH-INVOKED: pr view --repo attacker/evil --json state,mergedAt`); ISSUE-068's synthesized rows provably cannot reach it (zero invocations), which is why this is not a PR #121 finding. The injection is reachable from two sources: the Board field via `classify_ship_ready`, and the **model-chosen** `ship-merge-decision --pr` CLI argument the ship skill passes (`cmd_ship_merge_decision`, line 626). This is the same leading-dash class that review lesson "Relaxing a shared CLI/engine contract for a new caller class must be scoped to that class" names at point (3), and whose sibling instance ISSUE-057's SEC-3 already fixed.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; GAP-068j from the ISSUE-068 / PR #121 review; review lesson "Relaxing a shared CLI/engine contract for a new caller class must be scoped to that class" point (3), leading-dash class — native memory review-lessons.md)
- Priority: P1
- Estimate: 0.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
A Board- or CLI-supplied PR reference can never be re-interpreted as a `gh` flag: `_gh_pr_merge_state` refuses option-shaped and non-conforming refs **before** invoking `gh`, passes `--` ahead of the ref, and an unmerged PR therefore can no longer be finalized as `shipped`.

#### Scope (In/Out)
- In:
  - Validate the ref inside `_gh_pr_merge_state` — the **chokepoint both callers share** — before the `runner(...)` call: a `fullmatch` whitelist of the forms the field actually carries (`\d{1,9}`, `#\d{1,9}`, `https://github\.com/[\w.-]{1,64}/[\w.-]{1,64}/pull/\d{1,9}`), with bounded digit/segment runs rather than `\d+`. Anything option-shaped or non-conforming returns `None` (indeterminate) with a warning naming the rejected value **and the `PR:` field it came from**, and never raises — the existing never-raises contract from ISSUE-052 is preserved.
  - Pass `--` as an argument separator at the call site so a value can never be re-interpreted as a flag, which requires moving `--json state,mergedAt` **ahead** of the separator: `["gh", "pr", "view", "--json", "state,mergedAt", "--", ref]`.
  - **Sibling sweep of `scripts/sprint_queue.py`, recorded result: exactly ONE subprocess/`gh` call site exists in the file** (line 228; grep-verified across `"gh"`, `subprocess.`, `runner(`), so there are no sibling positional-ref invocations in this module to fix. What the sweep does find is two *entry points* feeding that one site — `classify_ship_ready` (Board `PR:`, line 286) and `cmd_ship_merge_decision` (`args.pr`, line 626) — both covered by guarding at the chokepoint rather than at the Board-parse site.
  - Update the argv fixture pin in `tests/test_sprint_queue.py` and add the injection / accept-form / mutation tests below.
- Out:
  - `scripts/verify_checkpoint.py`'s five `gh` call sites: they read the **same** Board `PR:` field but extract through `re.search(r"(\d+)\s*$", pr_field)` in `_extract_pr_number` (line 200), i.e. trailing digits only, so they are structurally immune. Verified, no change needed — recorded here so the absence is auditable.
  - ISSUE-069's watermark/dispatch scope and the remaining GAP-068c..GAP-068i Mediums.
  - Hardening `gh pr merge` in the ship skill, and any change to FINALIZE/SHIP semantics, the `--no-check-merged` flag, or the IRON LAW.
  - Broadening the whitelist to `gh`'s branch-name ref form — unattested in every live `PR:` value, so excluding it is a deliberate narrowing, not an oversight.

#### Acceptance Criteria (DoD)
- [ ] Given a rostered `reviewed` issue whose Board `PR:` value is `--repo attacker/evil`, when `next-action` runs with a logging fake supplied as `runner`, then the fake records zero invocations, the probe degrades to indeterminate, the emitted action is `SHIP` rather than `FINALIZE`, and the warning text names both the rejected value and the `PR:` field it was read from.
- [ ] Given the same option-shaped value passed through the model-chosen CLI path as `sprint_queue.py ship-merge-decision --pr '--repo attacker/evil'`, when the command runs, then the decision is `merge` with zero `gh` invocations, proving the guard sits at the `_gh_pr_merge_state` chokepoint and not only at the Board-parse site.
- [ ] Given the three ref forms the probe must keep accepting (a bare `123` as its own tests use, a `#123` as the historical Board rows carry, and a full `https://github.com/<owner>/<repo>/pull/123` URL as every recent row carries), when `_gh_pr_merge_state` runs against a fake runner answering `MERGED`, then each still resolves to `merged` with the ref string reaching the argv unchanged, and `classify_ship_ready` still emits `FINALIZE` for each exactly as on main.
- [ ] Given the two compound values the live Board already carries (`#108 https://github.com/pillip/claude-dev-kit/pull/108` and the same shape for PR 122), when the probe runs on them, then the outcome matches the handling explicitly recorded in the PR — refused-as-indeterminate, which reproduces today's observable result since `gh` cannot parse a two-token ref, unless the PR records a normalization decision instead — and the test asserts the branch that shipped by name.
- [ ] Given the validation helper deleted or weakened to a pass-through, when the injection test re-runs, then it fails with the fake recording the `--repo attacker/evil` invocation, so the guard is proven load-bearing rather than merely present.
- [ ] Given the argv the probe builds, when the argv pin asserts it, then the pinned list is `["gh", "pr", "view", "--json", "state,mergedAt", "--", "<ref>"]` with every flag ahead of the `--` separator and the ref last, and the fixture's old `PR-REF` placeholder is replaced by a ref the validator accepts.

#### Implementation Notes
- Provenance: `docs/test_plan.md` GAP-068j, whose named candidate is "validate the ref against `#?\d+|https://github\.com/[\w.-]+/[\w.-]+/pull/\d+` and insert `--` before it". This issue bounds that pattern's quantifiers and places it at the chokepoint.
- Files: `scripts/sprint_queue.py` (`_gh_pr_merge_state`, lines 209-233 — the guard plus the argv reorder; the callers `classify_ship_ready` 272-297 and `ship_merge_decision` 300-322 need no edit if the guard sits at the chokepoint), `tests/test_sprint_queue.py` (`TestGhPrMergeState`, the `_runner` argv-recording fixture at ~515, and `test_argv_is_fixed_and_shell_free` at 563-566).
- **Precedent to cite in the PR:** ISSUE-057's SEC-3 (`docs/review_notes/ISSUE-057.md:41-43`) fixed the sibling instance of this exact class — the `-` sentinel reaching `_find_worktree_path`, whose compiled `\-(?:-|/|$)` could match an unrelated worktree — by **rejecting the option-shaped value before any downstream consumer ran**, not by sanitizing inside it. Same shape, same remedy.
- The existing argv pin passes the placeholder `"PR-REF"`, which a strict whitelist rejects. Update the fixture to a legitimate ref; do **not** loosen the validator to keep the old placeholder green — that is precisely how review lesson 8's fail-open direction gets reintroduced.
- Tests that inject `merge_state_fn=` replace the probe and so bypass the guard by design (see `TestShipMergeDecision`, which passes `"pull/1"`). Drive the injection and mutation tests through `runner=` instead, so they traverse the production code path (mock-at-the-delegation-seam lesson); leave the `merge_state_fn` doubles alone.
- Census first (review lesson 8 sub-class): every non-empty `PR:` value in the live file is one of three shapes — bare `#N` (the historical rows), a full `https://github.com/.../pull/N` URL (every recent row), and two compound `#N <url>` values (ISSUE-062/PR #108, ISSUE-066/PR #122). No bare-number-without-`#` value is live today, though `_gh_pr_merge_state`'s own tests use one, so it stays in the whitelist.
- Fail-safe direction is already attested: a refusal yields `None` -> `classify_ship_ready` keeps the issue on `still_ship` -> `ship_merge_decision` returns `merge` -> the real `gh pr merge` surfaces the truth. That is the same observable mode the existing `--no-check-merged` flag produces, so the refusal path is not a novel behaviour. Normalizing a compound value instead would move it toward FINALIZE (the unsafe direction) and therefore needs explicit justification in the PR if chosen.
- `--` must come **after** the flags: `gh`'s cobra parser treats everything following `--` as positional. Verify against the installed `gh` (`gh pr view --json state,mergedAt -- 121`) and record the version in the PR; if the installed `gh` does not honour the separator, the validation remains the load-bearing control and the separator's status is recorded rather than assumed.
- Bound the digit runs (`\d{1,9}`, not `\d+`) and the URL's owner/repo segments — same family as ISSUE-068's `_ROSTER_ID_RE` fix and the widened-window quantifier lesson, since the pattern runs over text the kit does not author.
- Run the AC-5 mutation matrix with `PYTHONDONTWRITEBYTECODE=1` and validate the harness with one known-killing mutant before trusting any SURVIVED verdict (bytecode-cache lesson) — that AC is a mutation verdict, so the harness is part of the evidence.

#### Tests
- [ ] Injection pin (Board path): `PR: --repo attacker/evil` on a rostered `reviewed` issue -> zero recorded `gh` invocations, action `SHIP` not `FINALIZE`, warning naming the `PR:` field.
- [ ] Injection pin (CLI path): `ship-merge-decision --pr '--repo attacker/evil'` -> `merge`, zero invocations.
- [ ] Accept-form matrix: bare `123`, `#123`, full URL -> `merged` under a `MERGED` fake with the ref unchanged in argv, plus `classify_ship_ready` -> `FINALIZE` for each.
- [ ] Compound-value pin for the two live Board values, asserting the recorded branch by name.
- [ ] Mutation pair: guard removed -> the injection test fails with the invocation recorded; guard present -> the accept-form matrix stays green.
- [ ] Argv pin: `["gh", "pr", "view", "--json", "state,mergedAt", "--", "121"]` — flags before `--`, ref last.
- [ ] Degradation unchanged: empty ref, non-zero exit, `OSError`, `TimeoutExpired`, unparseable JSON, and valid-but-non-object JSON all still return `None` without raising, so the new early return does not regress the ISSUE-052 contract.

#### Rollback
`git revert` — the change is one validation helper plus an argv reorder inside `_gh_pr_merge_state`, with no schema, output-key, or phase-semantics surface. Note that a revert **restores a live argument injection**, so it must be paired with disabling the probe (`next-action --no-check-merged`, which forces phase-only SHIP) until the guard is re-landed; reverting the argv pin alone is not sufficient.

---

### ISSUE-074: Reconcile the registry-lock contract so the actor instructed to take the `issues.md` lock can actually invoke it

> Sprint iter-1 review triage (2026-10-10). The kit's registry-lock contract is **unsatisfiable by any actor as written**, attested at four sites: `agents/team-lead.md:165` ("All issues.md modifications go through planner + flock_edit.sh. Team-lead NEVER edits issues.md directly", reinforced at :18 "Delegate all issues.md changes to planner agent" and :252 "Edit issues.md directly — always delegate to planner agent"); `agents/planner.md:126-127`, the planner's own Append Mode, which says to append to `issues.md` via `flock_edit.sh` and update `STATUS.md` via `flock_edit.sh`; and `agents/planner.md:4`, `tools: Read, Glob, Grep, Write, Edit` — **no Bash**. Team-lead is forbidden to write the registry; planner is instructed to take the lock but cannot invoke it. The contract therefore resolves one of two ways: as a **silently unlocked write** (planner uses `Edit`, the lock is never taken, the write **succeeds**, and nothing errors anywhere — the dangerous resolution), or as a Bash-capable caller running the wrapper over planner-prepared content (done manually five times during this triage — safe but undocumented). **This is a product defect, not doc drift:** concurrent `issues.md` writes can clobber each other and lose registry data, in exactly the parallel-sprint scenario the kit is built for. Not theoretical — during this review phase two concurrent review sub-tasks appended to `docs/test_plan.md` and one observed the file had grown underneath it mid-run, so the flock demonstrably earns its keep on the path that *does* take it. Note the asymmetry: `scripts/preambles.py:85-93` injects the `registry_edit.sh` pattern into **skill** preambles, which run where Bash exists, so the instruction is satisfiable there. The gap is specific to the **agent** layer — which is also the layer the team-lead contract routes every `issues.md` write through. Mirror of review lesson 9 and of its sibling ISSUE-072: ISSUE-072 is the *missing grant silently disables a documented path* direction; this is the *missing grant silently removes a safety guarantee while the operation still succeeds* direction, which is strictly harder to notice because there is no failure to attribute.

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; sprint iter-1 review triage 2026-10-10; review lesson "allowed-tools grants in skill frontmatter must map to actual call sites" — native memory review-lessons.md — in its inverse direction; sibling ISSUE-072)
- Priority: P1
- Estimate: 0.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: none

#### Goal
Whichever actor the contract instructs to write `issues.md` under the lock can actually invoke the lock, and no agent is instructed to write `issues.md` with a toolset that can only produce an unlocked write.

#### Scope (In/Out)
- In:
  - **Pick fix 2 and record why.** Change both contracts so the planner *prepares* the registry edit and the invoking skill / team-lead commits it under the lock, keeping the planner Bash-free. Concretely: `agents/planner.md:126-127` instructs the planner to emit the prepared Board line + detail block (or an apply script) as its output rather than to invoke `flock_edit.sh`; `agents/team-lead.md:165` (and :18, :252) states that team-lead never *authors* `issues.md` content — planner does — but **does** commit planner-prepared content via `bash scripts/registry_edit.sh issues.md -- ...`, which its `tools:` line already permits (`Bash` is granted at `agents/team-lead.md:4`).
  - **Why not fix 1** (grant the planner `Bash(bash scripts/flock_edit.sh:*)` + `Bash(bash scripts/registry_edit.sh:*)` and nothing else): both wrappers execute an arbitrary command supplied after `--` — `flock_edit.sh` runs `"$@"` at lines 29 and 83, `registry_edit.sh` ends in `exec bash "$KIT_ROOT/scripts/flock_edit.sh" "$ROOT/$FILE" "$@"` at line 30, and the documented call form is literally `-- bash -c '<update command>'`. A prefix-scoped grant on these wrappers is therefore **arbitrary code execution wearing a narrow-looking prefix**: it satisfies the letter of the grants-map-to-call-sites lesson while voiding its intent, and it hands a planning agent full shell. Fix 1 becomes defensible only alongside a new non-exec'ing, content-only wrapper (e.g. one that takes a prepared-content file and appends it under the lock, with no command argument) — that is a design, not a 0.5d contract reconciliation, so it is recorded here as the follow-up path if fix 2's handoff proves awkward.
  - A guard test that reads agent frontmatter and contract text together, so the two can never drift apart again silently.
  - **Reconcile the `STATUS.md` half of `agents/planner.md:126-127`:** `STATUS.md` **does not exist in this repo** and per the current sprint contract must not be created, so that instruction is stale on its own terms, independent of the Bash gap. Remove it, or scope it explicitly to projects that already carry a `STATUS.md`.
- Out:
  - Changing `flock_edit.sh` / `registry_edit.sh` behaviour, the locking algorithm, or the stale-lock threshold.
  - Building the content-only wrapper that fix 1 would require.
  - The `STATUS.md` references outside the planner's instruction — `agents/team-lead.md:119` ("Update STATUS.md: Reflect progress (via flock_edit.sh)") and `:211`, plus the usage examples at `scripts/preambles.py:87` and `scripts/registry_edit.sh:10`. Audited and recorded here so the absence is auditable; :119 is the one closest to being in scope and may be folded in if the same edit touches it, but the file-existence question is a separate decision from the actor-capability one.
  - `CHANGELOG.md` and any other registry file's write path.

#### Acceptance Criteria (DoD)
- [ ] Given the reconciled contracts, when each agent file that instructs a write to `issues.md` is read together with its own `tools:` frontmatter, then the actor named as taking the lock has a toolset that can invoke `scripts/registry_edit.sh` or `scripts/flock_edit.sh`, and the guard test derives both halves by parsing the files rather than from a hand-maintained constant.
- [ ] Given the full set of kit agents, when the guard test scans for any instruction to modify `issues.md`, then no agent is instructed to write it while holding only `Write`/`Edit`, so no silently-unlocked write path is instructed anywhere in the agent layer.
- [ ] Given the fix reverted to its pre-fix text, that is `agents/planner.md` carrying both the "append via `flock_edit.sh`" instruction and `tools: Read, Glob, Grep, Write, Edit`, when the guard test re-runs, then it fails and names `agents/planner.md` plus the missing invocation capability, proving the test is load-bearing rather than merely present.
- [ ] Given fix 2 as the recorded choice, when `agents/planner.md` frontmatter is read, then its `tools:` line contains no `Bash` entry in any form, so the reconciliation adds zero privilege to the planner.
- [ ] Given a future decision to adopt fix 1 instead, when the planner's grants are read, then every granted form is prefix-scoped to a specific wrapper with no blanket `Bash`, each maps to a real call site in the planner's own Append Mode steps, and the arbitrary-command objection recorded in Scope is answered in the PR.
- [ ] Given `agents/planner.md`'s reconciled Append Mode and the fact that no `STATUS.md` exists in this repo, when the text is read, then the `STATUS.md` step is removed or explicitly scoped to projects that already carry one, and a test asserts that no kit agent instructs creating `STATUS.md` in this repo.

#### Implementation Notes
- Files: `agents/planner.md` (frontmatter line 4; Append Mode steps 5-6 at lines 126-127), `agents/team-lead.md` (lines 18, 165, 252, and 119 if the `STATUS.md` reconciliation is folded in), plus their `.tmpl` sources if these agents are generated — check and regenerate via `python3 scripts/gen_skills.py` rather than hand-editing a generated artifact, and verify the `.tmpl`/output pair does not re-diverge.
- The guard test is the deliverable that survives either fix choice. Shape it as: for each `agents/*.md`, parse `tools:` from frontmatter; if the body instructs an `issues.md` modification, assert the instructed actor's capability. Keep the instruction-detection an **occurrence whitelist** (the specific sentences, cited by file and content) rather than a phrasing blacklist — the absence-guard lesson from ISSUE-040: a blacklist passes hollowly the moment someone rewords the sentence.
- Mutation-test the guard per AC-3 with `PYTHONDONTWRITEBYTECODE=1`, and validate the harness with one known-killing mutant before trusting any SURVIVED verdict (bytecode-cache lesson). AC-3 is a mutation verdict, so the harness is part of the evidence.
- Cite ISSUE-072 as the sibling in the PR and note both directions when the review lesson is next updated: an unused grant widens privilege; a missing grant either silently disables a documented path (ISSUE-072) or silently removes a safety guarantee while the operation still succeeds (this issue). The second is the worse failure mode precisely because the write returns success.
- The handoff is the real design question in fix 2: planner output is text in a transcript, and the committing actor has to get it into the file byte-exactly. What worked manually five times today was planner-authored idempotent apply scripts, each guarded to no-op if its `### ISSUE-NNN:` anchor was already present, run by a Bash-capable caller under `registry_edit.sh`. Document that as the prescribed handoff shape, including the idempotence guard, since an apply script re-run without a guard is itself a duplicate-registry-entry bug.
- Do not "fix" this by relaxing the team-lead prohibition into a direct `Edit` — that is the silently-unlocked resolution promoted to policy, and it is the specific outcome this issue exists to close off.

#### Tests
- [ ] Capability pin: for every agent instructed to write `issues.md`, the instructed lock-taker's parsed `tools:` can invoke `registry_edit.sh`/`flock_edit.sh`.
- [ ] No-unlocked-write-instructed pin: no agent is instructed to modify `issues.md` with only `Write`/`Edit` available.
- [ ] Mutation pair: pre-fix planner text plus Bash-free `tools:` fails the guard naming `agents/planner.md`; post-fix text passes.
- [ ] Planner-privilege pin (fix 2): `agents/planner.md` `tools:` contains no `Bash` entry.
- [ ] `STATUS.md` staleness pin: no kit agent instructs creating `STATUS.md`, and the planner's Append Mode no longer references it unconditionally.
- [ ] Template-parity check: if `agents/*.tmpl` sources exist for planner/team-lead, the generated output matches after `gen_skills.py`.

#### Rollback
`git revert` — the change is contract text in two agent files plus one guard test, with no script, schema, or runtime surface. A revert restores the unsatisfiable contract and therefore re-opens the silently-unlocked write, so pair it with the interim rule that every `issues.md` write goes through a Bash-capable caller running `registry_edit.sh` over planner-prepared content (the practice this triage already followed) until the reconciliation re-lands.

---

### ISSUE-075: Migrate review_context.py's private telemetry appender onto the shared kit_telemetry emit seam

> ISSUE-066 ship-time deferral, recorded 2026-10-11. ISSUE-067 (PR #123, merged) shipped `scripts/kit_telemetry.py::emit_event` as the kit's **single shared telemetry emit seam**, carrying the ISSUE-058 writer hardening in one place. ISSUE-066 (PR #122) landed `scripts/review_context.py`, which carries its **own** private hardened appender `_emit_event` plus five module constants (`RUN_ID_ENV`, `_RUN_ID_RE`, `_MAX_EVENT_BYTES`, `_MAX_DETAIL_CHARS`, `_SCRIPT_NAME`) — and SPEC-066 had pre-committed to adopting ISSUE-067's helper at ISSUE-066's ship-time rebase. **At ISSUE-066's ship the migration was deliberately DEFERRED, not forgotten**, for three reasons: (1) `emit_event`'s documented "NEVER raises" contract is currently **FALSE** — reproduced by closing stdout (`ValueError: I/O operation on closed file`) — whereas `review_context._emit_event`'s blanket `except Exception: return` makes the guarantee hold today, so adopting now would trade a working promise for a known-broken one *inside the review gate*; (2) ISSUE-070 is already rewriting `emit_event`'s containment check and its raise contract, so migrating first would mean migrating twice; (3) ISSUE-067 deliberately replaced silent-skip semantics with announce-and-write-to-`unattributed.jsonl` semantics, so **two existing tests pin the opposite contract** and must be rewritten in the same commit as the migration — `tests/test_review_context.py::test_unset_run_id_is_silent_noop_exit_0` and `::test_invalid_run_id_refused` (the latter asserts the runs dir is empty) — and doing that inside a merge-conflict resolution would have been an unreviewed test rewrite. Hence this issue. This is **duplication debt, NOT a hardening regression**: the ISSUE-066 review gave a per-control equivalence verdict and found **two controls stronger** than the baseline (all-string-value truncation rather than `payload["detail"]`-only, and type coercion inside the `try` so it never raises).

- Track: platform
- UI: false
- Platform: web
- Manual: false
- Spec-Required: false
- Spec: none
- PRD-Ref: none (kit self-development; ISSUE-066 ship-time deferral, pre-committed in SPEC-066 and recorded in its Open Questions; consumes the ISSUE-067 shared emit seam; review lesson "an instrument's documented contract must be true or narrowed to what holds, and a shared seam's consumers must not rest on an untested promise" — native memory review-lessons.md)
- Priority: P2
- Estimate: 0.5d
- Status: backlog
- Owner:
- Branch:
- GH-Issue:
- PR:
- Depends-On: ISSUE-066, ISSUE-067

#### Goal
`scripts/review_context.py` emits telemetry exclusively through `kit_telemetry.emit_event`, its private appender and the five now-unused constants are deleted, the two tests that pinned the pre-ISSUE-067 silent-skip contract assert the announce-and-fallback contract instead, and the three in-repo provenance notes that point at this issue by name are closed out.

#### Scope (In/Out)
- In:
  - **Delete** `_emit_event` and the now-unused module constants (`RUN_ID_ENV`, `_RUN_ID_RE`, `_MAX_EVENT_BYTES`, `_MAX_DETAIL_CHARS`, `_SCRIPT_NAME`) rather than leaving a fourth hardened copy of the appender in the repo; every emit routes through the shared seam.
  - Map the call sites onto the shared API exactly: `emit_event(event_type, payload=None, *, script_name, project_path=None, issue_id=None) -> bool`. `script_name` is required keyword-only; `review_context`'s `--issue` maps to the **TOP-LEVEL** `issue_id=` parameter, NOT into `payload`; `reason` stays **INSIDE** `payload`; `project_path` is passed explicitly (it defaults to `Path.cwd()` and review runs from a worktree); a `False` return is a **skip, not an error**.
  - Preserve review_context's stronger all-string-value truncation **at the call site** — the shared emitter truncates only `payload["detail"]`, so this control must move with the migration rather than be dropped on the way.
  - Rewrite the two tests that pin the superseded contract in the same commit as the migration: `tests/test_review_context.py::test_unset_run_id_is_silent_noop_exit_0` and `::test_invalid_run_id_refused`, so both assert announce-and-write-to-`unattributed.jsonl` instead of silence / an empty runs dir.
  - Update `docs/telemetry_schema.md`: the **Emit-site inventory** row for `scripts/review_context.py` (currently reads "NOT YET migrated — ISSUE-075") and the `### ISSUE-019` blockquote.
  - Tick the now-resolved Open Question in `docs/specs/SPEC-066.md`.
- Out:
  - Changing the event schema, or the `capability-absent` / `context-unreachable` / `inline-attempt-failed` reason vocabulary.
  - Any change to the decide-once decision contract.
  - Fixing `emit_event`'s own containment / FIFO / no-raise defects — that is **ISSUE-070**. This issue *consumes* the fixed contract, it does not produce it.

#### Acceptance Criteria (DoD)
- [ ] Given the migration has landed, when `scripts/review_context.py` is searched for its own appender, then `_emit_event` and all five module constants (`RUN_ID_ENV`, `_RUN_ID_RE`, `_MAX_EVENT_BYTES`, `_MAX_DETAIL_CHARS`, `_SCRIPT_NAME`) are absent and every emit call goes through `kit_telemetry.emit_event`, so no fourth hardened copy of the appender remains in the repo.
- [ ] Given a review-context run invoked with `--issue ISSUE-NNN` from a worktree, when the migrated emit runs, then the appended event line carries `issue_id` as a **top-level** field (never inside `payload`), keeps `reason` **inside** `payload`, and is written under the explicitly passed `project_path` rather than under `Path.cwd()`.
- [ ] Given `KIT_RUN_ID` is unset, when the migrated review_context emits, then the event is written under the `unattributed` run id with the `run_id_fallback` field plus one `[kit-telemetry]` stdout announcement and the process still exits 0, and `tests/test_review_context.py::test_unset_run_id_is_silent_noop_exit_0` has been rewritten to assert that announce-and-fallback contract instead of a silent no-op.
- [ ] Given `KIT_RUN_ID` is set to an invalid value, when the migrated review_context emits, then the event lands under the `unattributed` run id with the named fallback reason announced, and `::test_invalid_run_id_refused` has been rewritten so it no longer asserts that the runs directory is empty.
- [ ] Given a payload whose over-long strings sit in keys other than `detail`, when the migrated emit runs, then every string value is truncated at the call site before `emit_event` is reached and the serialized line stays under the 4 KB append cap, so the stronger-than-baseline all-string truncation credited by the ISSUE-066 review survives the migration.
- [ ] Given `emit_event` returns `False` for a skipped emit, when review_context observes that return value, then the decide-once decision result and the process exit code are unchanged, because a `False` return is a skip rather than an error.
- [ ] Given the migration has landed, when `docs/telemetry_schema.md` and `docs/specs/SPEC-066.md` are read, then the Emit-site inventory row for `scripts/review_context.py` no longer reads "NOT YET migrated — ISSUE-075", the `### ISSUE-019` blockquote reflects the shared seam, and SPEC-066's Open Question about adopting ISSUE-067's helper is ticked as resolved.

#### Implementation Notes
- **Ordering constraint, stated plainly: land ISSUE-070 first.** Adopting the shared seam before ISSUE-070 fixes `emit_event`'s raise contract would move the review gate from a guarantee that holds (review_context's blanket `except Exception: return`) onto a docstring that is known false, and would also mean migrating twice once ISSUE-070 rewrites the containment check. This issue rests on a *tested* promise, not on an advertised one.
- Three in-repo provenance sites already point here by name and are the checklist for "done": `scripts/review_context.py`'s module docstring "Migration status" paragraph, `docs/telemetry_schema.md`'s **Emit-site inventory** row for `scripts/review_context.py`, and `docs/specs/SPEC-066.md`'s **Open Questions**. (Branch files not yet on main at filing time — cite by content and re-locate after PR #122 merges.)
- Shared-seam API, for the diff: `emit_event(event_type, payload=None, *, script_name, project_path=None, issue_id=None) -> bool` in `scripts/kit_telemetry.py`. `issue_id` becomes a top-level event field; `script_name` becomes `skill_or_script`; `project_path` defaults to `Path.cwd()`, which is wrong for a worktree review run, so pass it. `scripts/synthesize_gate_results.py`'s thin `_emit_telemetry` delegation is the precedent shape for the call-site wrapper.
- Review lesson (native memory): an instrument's documented contract must be **true or narrowed to what holds**, and a shared seam's consumers must not rest on an untested promise. The whole reason this is a separate issue rather than a rebase chore is that the promise was not yet true at adoption time — record that reasoning in the PR so the deferral does not read as oversight later.
- The ISSUE-066 review's per-control equivalence verdict is the baseline to migrate against, not the shared emitter's current behaviour alone: two of review_context's controls were *stronger*, and a migration that silently levels them down is a regression wearing a dedupe hat.
- Mutation-test with `PYTHONDONTWRITEBYTECODE=1` and validate the harness with one known-killing mutant before trusting any SURVIVED verdict (bytecode-cache lesson).

#### Tests
- [ ] Control-survival mutation check: after the migration, each of the five ISSUE-058 writer controls (run-id whitelist, `O_NOFOLLOW` open, realpath directory containment, 4 KB cap with truncation, never-raise containment) still fails at least one test when individually broken — the controls move to the shared seam, so their pins must move with them and not evaporate.
- [ ] All-string truncation pin: an over-long string in a non-`detail` payload key is truncated and the line stays under the 4 KB cap; removing the call-site truncation fails this test.
- [ ] Top-level `issue_id` pin: `--issue` produces a top-level `issue_id` field and no `payload["issue_id"]`; `reason` stays inside `payload`.
- [ ] Rewritten contract tests: unset and invalid `KIT_RUN_ID` both write under `unattributed` with the announcement and exit 0 (replacing the silent-noop / empty-runs-dir assertions).
- [ ] Clean-path pin: a normal rostered review emit is schema-identical to the pre-migration event body, and `project_path` is the kit worktree rather than `Path.cwd()`.
- [ ] Absence pin: `_emit_event` and the five removed constants are gone from `scripts/review_context.py`, asserted as an occurrence check on the removed names rather than a phrasing blacklist.

#### Rollback
`git revert` — restores `scripts/review_context.py`'s private appender. The emit contract and the event schema are unchanged either way, so no consumer breaks on a revert; the only cost is the duplicated hardened appender coming back, which is the state this issue was filed against.
