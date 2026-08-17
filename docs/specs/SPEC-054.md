# SPEC-054: Extract a design system from existing UI code so /uiux can extend instead of replace

> Linked Issue: ISSUE-054
> Status: `draft`
> Date: 2026-08-17
> Author: pillip

## Problem

A team with a shipping UI and no Figma file asks the kit to add three screens that match what they already have. There is no path. `/uiux` globs their stylesheets at Phase 1 step 4 (`skills/uiux/SKILL.md.tmpl`, "read key files to understand current design patterns"), then discards that reading: Phase 2 step 7 unconditionally commits to a new aesthetic direction and Phase 5A stamps a new Signature Move onto every screen. `/figma2proto` needs the Figma API. `/scan` has a conditional frontend branch but it produces `docs/ux_spec.md`, never a design system. The user's only options today are a from-scratch redesign of a product that already shipped, or hand-writing `docs/design_system.md` themselves — and if they pick the first, `/uiux` will actively fight their codebase, because every existing pattern that happens to match a "Specific AI Tell" gets swept out at Phase 5.5.

## Context

- **`/uiux` is create-only by construction.** Phase 2 step 7 ("Commit to a BOLD aesthetic direction"), the Phase 5A pilot gate's specificity check ("Name 3 details that ONLY make sense for THIS product"), and Phase 5.5 step 17.5's Signature-Move-on-every-screen rule all assume the design is being invented in this run. Each is a place `extend` mode has to diverge, not a place it can reuse.
- **`/scan` cannot be the prerequisite.** Its Step 6 runs `scan-planner → issues.md`, regenerating the issue registry. Requiring `/scan` before `/uiux` would mean a user who wants one extra screen gets their `issues.md` rewritten. `/scan` is also gated on `--force` when target docs already exist.
- **`codebase-scanner` already detects frontends.** Pass 2 item 6 checks `pages/`, `components/`, `views/`, `templates/`, CSS/SCSS files, and framework config. Its output contract is explicit: "this is an internal document passed to downstream agents, **NOT** written to disk". It is `effort: low`, tools `Read, Glob, Grep`.
- **Roster growth has a stated bar.** `tests/test_agent_effort.py:60` asserts `len(AGENTS) == 32`. ISSUE-034 cut four dead persona agents and kept the rest on one criterion: "differentiated methodology / separate-context self-grading guard". `README.md:16` and the agents table at `README.md:537` are linted against agent frontmatter (ISSUE-050), so any roster change touches both.
- **The three platforms keep their tokens in different places.** Web: CSS custom properties, `tailwind.config.*`, styled-components. Mobile (`mobile-uiux`, RN/Expo): `StyleSheet.create` objects and `src/theme/` modules, with no cascade and values often inlined at the call site. Desktop (`desktop-uiux`, Electron): renderer CSS plus `src/theme/`, and native chrome that has no token at all. Extraction is one method with three source maps, not three methods.
- **Per-skill resolution already exists.** `scripts/preambles.py` and `scripts/fragments.py` both resolve the same canonical text per skill across `("uiux", "mobile-uiux", "desktop-uiux")` (`fragments.py:32`), which is the seam any three-platform skill text should use rather than a fourth set of copies.
- **The kit's own anti-slop rationale argues against same-context extraction.** Phase 5A step 2.1 states "Generator-as-judge fails: the same context that produced the pilot will not reliably catch its own slop", which is why `design-auditor` runs in a fresh context. Reading what a codebase *is* and deciding what to *build* have the same conflict of interest.
- **The `Brief overrides:` mechanism landed 2026-08-17** (`scripts/fragments.py`, `{{SLOP_CALIBRATION}}`). It is the existing seam for telling the Phase 5.5 sweeps "this tell is deliberate", which `extend` mode needs in order to stop fighting the host codebase.
- `scripts/fragments.py` owns shared uiux-family text; three copies is the failure mode ISSUE-041 fixed.

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line (numeric or +/- comparator). Vague trade-offs ("more flexible") are rejected by the validator.

### Option A: Dedicated `design-scanner` agent, invoked by `/uiux`

- **Approach**: Add one `agents/design-scanner.md` with tools `Read, Glob, Grep`, parameterized by platform: it takes the target platform and reads that platform's source map (web CSS custom properties / Tailwind / styled-components, RN `StyleSheet` + `src/theme/`, Electron renderer CSS + `src/theme/`), then emits observed tokens and a reverse-engineered Signature Move with a `file:line` per claim. All three uiux skills invoke it via Task in `extend` mode only, the same way `/uiux` already invokes `design-auditor`, `ui-reviewer`, and `copywriter`. It is **not** a `/scan`-family member and does not require `/scan` to have run.
- **Pros**:
  - Extraction runs in a fresh context, so the agent reporting what exists is not the one deciding what to build — the separation ISSUE-013 and the Phase 5A pilot gate already rely on.
  - The three skills stay self-sufficient; `issues.md` is never touched by the brownfield path.
  - One extraction method with three source maps means a provenance or fabrication fix lands once, not three times.
  - `create` mode is untouched by construction on all three platforms.
- **Cons**:
  - Roster 32 → 33, against ISSUE-034's diet direction; needs a justification recorded next to the kept-agent rationale.
  - Touches three lint surfaces: `tests/test_agent_effort.py:60`, `README.md:16`, `README.md:537`.
  - One agent file carries three platform source maps, so it grows with each platform rather than staying single-purpose.
- **Trade-off**: +1 agent (roster 32 → 33), +1 Task hop per extend run, 3 skills wired from 1 shared fragment, 0 changes to `/scan` or `issues.md`.

### Option B: Inline extraction phase inside `/uiux`

- **Approach**: Add a Phase 1.6 to `skills/uiux/SKILL.md.tmpl` that reads the same sources and writes `docs/design_system.md` directly, with no subagent. Phase 2 then branches on whether that file was produced by extraction or by invention.
- **Pros**:
  - No roster change, no README/test lint surface touched.
  - Fewest moving parts and the shortest wall-clock path for a small project.
- **Cons**:
  - Extraction and generation share one context. The model that is about to design the new screens is the one deciding what the existing design "is", and the kit's own Phase 5A rationale says that self-grading does not hold. The concrete failure is extracting the design the model wants to build rather than the one on disk.
  - Compensating for that needs new provenance sweeps in Phase 5.5, which is added surface in the file that is already 500 lines.
  - `mobile-uiux` / `desktop-uiux` parity later means the phase gets written three times unless it is pushed into `scripts/fragments.py` anyway.
- **Trade-off**: +0 agents, -1 Task hop, but 1 shared context across extract-and-generate plus +2 compensating sweeps in a 500-line skill.

### Option C: Extend `codebase-scanner` with a design pass

- **Approach**: Add "Pass 5 — Design System Extraction" to `agents/codebase-scanner.md`, reusing its existing Pass 2 frontend detection. `/uiux` invokes `codebase-scanner` in `extend` mode and consumes the design section of the returned scan context.
- **Pros**:
  - No roster change, and the frontend-detection logic is already written and exercised by `/scan`.
  - Fresh context comes for free, since `codebase-scanner` is already a Task-invoked agent.
- **Cons**:
  - Two unrelated consumers (`/scan`, `/uiux`) end up coupled to one agent's output contract; a design-extraction change can break `/scan`'s four downstream agents.
  - Its contract says the output is "NOT written to disk", but `docs/design_system.md` must be written — so either the contract breaks or `/uiux` reimplements the write, splitting ownership.
  - Every `/scan` run pays for a design pass it does not consume, on an agent deliberately kept at `effort: low`, unless a mode flag is threaded through `/scan` as well.
- **Trade-off**: +0 agents, +1 pass on an agent `/scan` runs every time, 2 consumers coupled to 1 output contract, +1 breaking change to its documented no-disk-write contract.

### Option D: Three platform-specific scanner agents

- **Approach**: Ship `design-scanner-web`, `design-scanner-mobile`, and `design-scanner-desktop`, each owning one platform's source map, mirroring how `uiux-developer` / `mobile-uiux-developer` / `desktop-uiux-developer` are already split three ways.
- **Pros**:
  - Each agent stays single-purpose and its prompt never carries source maps it will not use.
  - Matches the existing three-way split of the uiux developer agents, so the roster shape stays legible.
- **Cons**:
  - Roster 32 → 35 against ISSUE-034's diet, which cut four agents on exactly this kind of growth.
  - The provenance contract, confidence tagging, and fabrication guards are identical across platforms, so the part most likely to have bugs gets triplicated — the failure ISSUE-041 fixed for the design-philosophy boilerplate.
  - A fix to extraction fidelity is 3 edits and 3 test fixtures instead of 1.
- **Trade-off**: +3 agents (roster 32 → 35), 3 copies of 1 provenance contract, +2 extra files per fidelity fix.

## Decision

**Chosen: Option A**

The trade-off line that decides it is Option B's "1 shared context across extract-and-generate". The kit already paid for this lesson once — Phase 5A step 2.1 exists because the generator could not judge its own output — and brownfield extraction has the identical conflict of interest, so re-introducing it to save one Task hop is the wrong direction. That eliminates B. Between A and C, C's "+0 agents" is real but is bought with "2 consumers coupled to 1 output contract" plus a documented-contract break, which is a worse long-term shape than A's "+1 agent"; and ISSUE-034's own kept-agent criterion — differentiated methodology, separate-context guard — is exactly what a `design-scanner` satisfies, so the roster growth is on-policy rather than against it.

D is rejected on its own trade-off line: "+3 agents, 3 copies of 1 provenance contract". The platform differences are the *source maps* — where a token lives — while the part that carries risk (provenance, confidence tagging, refusing to invent values) is identical on all three. Triplicating the risky half to avoid parameterizing the trivial half is the exact shape ISSUE-041 already removed from the design-philosophy boilerplate, and it costs three roster slots to do it.

## Trade-offs Accepted

- Roster goes 32 → 33 and the ISSUE-034 diet direction is deliberately relaxed for this one agent. The justification is recorded in the agent file itself, not only here.
- `extend` mode costs one extra Task round-trip versus inline extraction. Accepted: correctness of what gets extracted dominates latency on a path that runs once per project.
- `/scan` gains nothing from this work. A user who wants design extraction runs `/uiux`, not `/scan`, and the two stay unaware of each other.
- **All three platforms land in one change, so there is no web-first proving ground.** The three pilot gates get repointed from a distinctiveness check to a consistency check together, and a flaw in that repointing surfaces on `uiux`, `mobile-uiux`, and `desktop-uiux` at once instead of on one skill with two intact. This was a deliberate call (2026-08-17) — the alternative shipped a create/extend inconsistency across the three skills for at least one release, and that was judged the worse cost. Mitigation is that the platform-varying part is data (source maps) while the shared method is exercised by all three fixtures.
- Extraction quality is bounded by what is legible in source, and it is bounded differently per platform. Web CSS custom properties and `tailwind.config.*` are declarative and extract cleanly; RN designs that inline values at the call site instead of centralizing in `src/theme/` will extract thinly and get tagged INFERRED rather than guessed at. Desktop native chrome (traffic lights, tray, menu bar) has no token to extract at all and stays out of the extracted system.

## Migration

No schema, no data, no runtime state. Ordered steps:

1. Add `agents/design-scanner.md` (tools `Read, Glob, Grep`), taking the platform as an input and carrying one source map per platform. Record the ISSUE-034 roster justification in the file.
2. Update `tests/test_agent_effort.py:60` `32 → 33`, and the two README surfaces (`README.md:16` prose count, agents table at `README.md:537`) that ISSUE-050's linter checks against frontmatter.
3. Add a `{{DESIGN_EXTEND_MODE}}` fragment to `scripts/fragments.py` and register it in `scripts/gen_skills.py` alongside `SLOP_CALIBRATION`, resolving per skill over the existing `UIUX_SKILLS` tuple. This is the `create` / `extend` branch: auto-detect existing UI, confirm the mode with the user (never switch silently), and on `extend` invoke `design-scanner` with the skill's platform before the design interview.
4. Insert the token in all three templates — `skills/uiux/SKILL.md.tmpl`, `skills/mobile-uiux/SKILL.md.tmpl`, `skills/desktop-uiux/SKILL.md.tmpl` — at each one's Phase 1 UI-scan step.
5. Reframe the design interview for `extend` ("what should change / what must stay") and make Phase 2 consume the extracted philosophy instead of inventing one. The interview already resolves through `design_philosophy_fragment`, so this is one edit in `fragments.py`, not three.
6. Repoint each skill's pilot gate specificity check to a consistency check against the extracted system when mode is `extend` — `uiux` Phase 5A step 2.2, `mobile-uiux` step 20.5, `desktop-uiux` step 19.5.
7. Emit `Brief overrides:` entries for existing-codebase patterns that collide with a listed AI Tell, so each skill's AI Tell sweep (`uiux` 22.7, `mobile-uiux` 29.5, `desktop-uiux` 30.5) exempts them instead of rewriting the host product's conventions.
8. Regenerate with `python3 scripts/gen_skills.py`; add mode-detection and provenance tests plus one extraction fixture per platform (CSS custom properties, RN `StyleSheet` + `src/theme/`, Electron renderer CSS).

Existing projects need no migration: with no UI detected, mode resolves to `create` on all three platforms and behaviour is unchanged.

## Rollback

`git revert` the range. The change is additive — a new agent file plus a mode branch whose `create` arm is today's code path — so reverting restores current behaviour exactly, with no data or state to unwind. Roll back if either signal appears: (a) extraction produces token values that do not appear in the source files (fabrication, which the provenance test should catch first), or (b) the `create` path regresses, measured by the byte-identical-output assertion in the issue's fourth acceptance criterion. Rollback is a revert plus one `scripts/gen_skills.py` run, under 30 minutes, and cannot strand a user mid-flow because the design docs it writes are plain files.

## Open Questions

Resolved 2026-08-17 (pillip), before implementation shipped. Recorded here rather than deleted, because three of the four confirm a default that is otherwise invisible in the diff:

- [x] **Overwrite an existing design system doc?** → **No. Stop and ask.** When `{system_doc}` already exists, `extend` halts before writing and offers overwrite / write-alongside (`docs/design_system[.platform].extracted.md` plus a diff summary) / cancel, quoting the file's line count and last-modified date. This was the only one of the four that was genuinely unhandled — the fragment wrote unconditionally. "It's in git" was rejected as a substitute for consent, since a hand-maintained design system is the one artifact this mode can destroy.
- [x] **Tailwind parsing depth?** → **`theme` / `theme.extend` keys only.** No plugin output, no merged-default resolution. Resolving the full theme would require executing config JS or inferring Tailwind's defaults, and neither produces a value that can carry a `file:line` — so neither could ever be tagged `[CONFIRMED]`. Fidelity to what is written beats fidelity to what renders.
- [x] **RN floor when styles are inlined at the call site?** → **Report and let the user decide.** The agent returns `extraction_verdict: insufficient` below ~5 distinct reusable tokens with no value repeating across 3+ component files, and the skill surfaces that verbatim with a create/extend choice. Not a hard refusal: a thin extraction can still beat nothing, and the caller has context the threshold does not.
- [x] **Desktop native chrome as design facts?** → **Excluded.** Title bar, tray, and menu structure carry no token; admitting them would put un-citable entries in a provenance-tagged document.

Still open:

- [ ] Are the `insufficient` thresholds (~5 distinct tokens, 3+ file recurrence) right? They are uncalibrated magic numbers in a prompt, chosen by judgement with no sample of real projects behind them. Revisit once `extend` has run against a handful of real codebases. — owner: pillip, by: after first real-world `extend` runs
- [ ] Should `/scan` eventually surface "this project has a design system worth extracting" as a next-step hint, given the two skills deliberately stay unaware of each other here? — owner: pillip, by: next kit audit
