# SPEC-060: Contract-convert the uiux triplet — keep-list, fragment plan, and sweep wiring

> Linked Issue: ISSUE-060
> Status: `accepted`
> Date: 2026-10-10
> Author: team-lead (sprint auto-spec, KIT_SPRINT_MODE=1)

## Problem

The uiux / mobile-uiux / desktop-uiux skills (568/590/648 generated lines) plus their developer agents (193/241/300 lines) are the kit's largest fast-depreciating surface: craft tutorials (duration-band tables, Expo config pins, Electron perf prescriptions, CSS/typography mechanics lessons) that frontier models absorb release by release, drifting in three near-verbatim copies. The durable value — the pilot gate, the literal_quote / Signature Move / AI-tell sweeps (now scripted in `scripts/verify_design_sweeps.py` per SPEC-056/ISSUE-063), and the anti-slop trio — is buried inside that prose, and the skills still instruct the model to self-execute sweeps a script now owns. Something must decide, prescription by prescription, what is still-failing empirical knowledge (kept, with a depreciation trigger) and what is model-absorbed (deleted) — before the deletion happens.

## Context

- **Validator contract (frozen)**: `scripts/verify_design_sweeps.py` post-ISSUE-063 on main: `all --class NAME` is required (fails closed, exit 2, naming the Signature Move sweep); `all --json` emits exactly ONE JSON object parseable by a single `json.loads`; exit 0 pass / 1 violations / 2 usage. Tell ids: `em-dash`, `100vh`, `flex-calc-width`, `generic-name`, `fake-perfect-number`, `filler-verb`, `scroll-cue`. Screen discovery is `*.html` only (`_discover_screens`) — the validator is a **web-prototype** validator. ISSUE-064 hardens its matcher internals in a parallel worktree; this issue consumes the CLI as a new caller and must not modify the script or loosen the contract (review lesson: contract leniency scopes to the new caller class).
- **Checkpoint wiring (ISSUE-057)**: `verify_checkpoint.py` already covers (`uiux`|`mobile-uiux`|`desktop-uiux`) × (`context`, `philosophy`, `system`). The `philosophy` verifier's docstring defers depth checks "until the ISSUE-056 sweeps are wired in (ISSUE-060)" — that wiring is skill-prose call sites, not a new checkpoint phase, because the signature-move sweep needs the per-run `--class` value a `--skill/--phase` checkpoint invocation cannot carry.
- **Fragment mechanism (ISSUE-041/054)**: `scripts/fragments.py` already resolves `{{DESIGN_PHILOSOPHY}}`, `{{DESIGN_PHILOSOPHY_CHECKPOINT}}`, `{{SLOP_CALIBRATION}}`, `{{DESIGN_EXTEND_MODE}}` per-skill over `UIUX_SKILLS`; `AGENT_DESIGN_FRAGMENTS` drift-guards the agent copies (tests/test_design_fragments.py).
- **Test pins that bound the edit**:
  - `tests/test_agent_dissolution.py` asserts the Phase 4.5 copy contract lines in the RAW tmpl AND generated file → Phase 4.5 stays inline.
  - `tests/test_uiux_reference_fabrication_guard.py` asserts `capture_reference.py` / "Reference Anchor skipped" in the RAW tmpl → Reference Research stays inline.
  - `tests/test_pilot_gate_hardening.py` asserts the 4-substep pilot gate in tmpl text; it predates the fragment mechanism, so extraction requires pointing it at RESOLVED content (the precedent: tests/test_reference_anchor_tuning.py was converted to resolved content when ISSUE-041 tokenized the interview). Every assertion is preserved, none weakened.
  - `tests/test_integration.py` requires ≥3 CHECKPOINT markers per design skill, agent Self-Review sections, and the "review lessons" reference in the triplet agents.
  - `tests/test_scaffolding_residue.py` whitelists the triplet agents' confidence-rating ritual as "owned by ISSUE-060" — this issue empties that whitelist.
- **ISSUE-059 debt explicitly assigned here**: the `self_review_confidence` chunk in `AGENT_DESIGN_FRAGMENTS` and its three agent copies.
- Keep/delete comparator from the issue: "spot-check generations with/without the prescription on the current model tier". A full A/B generation study is out of budget for a 1.5d issue; the proxy used below is **ownership**: a prescription is kept iff a named gate can falsify it today (script sweep, deterministic grep pattern in a Phase 5.5 sweep, boot/runnability gate, or checkpoint). A MUST no gate can falsify is exactly the "model self-assertion" class the evolution audit (roadmap 3b) marks A-bucket.

## Options

### Option A: Keep-list conversion with fragment extraction + web sweep wiring (one source, three resolutions)

- **Approach**: Classify every prescription by ownership (table in Decision). Extract the shared surviving blocks — pilot-gate protocol, Specific-AI-Tells list, Phase 5.5 verification sweeps — into three new parameterized `scripts/fragments.py` tokens (`{{PILOT_GATE}}`, `{{AI_TELLS}}`, `{{DESIGN_SWEEPS}}`) over the existing `UIUX_SKILLS` tuple, exactly like `{{DESIGN_EXTEND_MODE}}`. The web `{{DESIGN_SWEEPS}}` resolution replaces the three deterministic sweeps with one `verify_design_sweeps.py all --class <name> [--exempt id ...]` call site; mobile/desktop resolutions keep contract-shaped prose sweeps carrying the K9 trigger ("script-owned the day the validator accepts non-HTML trees"). Delete the D-table craft; shrink the three agents to contract + drift-guarded chunks.
- **Pros**:
  - Shared surviving text exists once; a single-skill edit of it is structurally impossible (gen_skills) and an agent-side edit fails the drift guard — AC2 by construction.
  - The weakest verification point (model self-sweeps at the end of the longest generation) becomes a script exit code on web, the platform with the only deterministic sweep target today.
- **Cons**:
  - `tests/test_pilot_gate_hardening.py` must be re-pointed at resolved template content (mechanical, assertion-preserving).
  - Three new parameterized templates in fragments.py add resolver complexity (~3 param dicts).
- **Trade-off**: −3 drifting copies of ~360 shared lines (one canonical copy survives), +3 resolver functions (+~40 param-dict lines), −~45% generated triplet volume, 1 test file re-pointed with 0 assertions dropped.

### Option B: Delete-in-place, no extraction (three independently trimmed copies)

- **Approach**: Apply the same keep/delete table but leave the surviving shared text as three per-skill copies; wire the web validator call inline.
- **Pros**:
  - No gen_skills/test re-pointing churn; smallest mechanical diff.
- **Cons**:
  - Fails AC2 verbatim ("shared surviving text exists once in scripts/fragments.py and zero times as per-skill copies").
  - The surviving gates — the highest-value text — keep the exact 3-copy drift mode that produced ISSUE-041/054; the next tell added to one skill silently misses the other two.
- **Trade-off**: −1 day of extraction work now, +3 hand-synced copies of the pilot gate and tell list indefinitely (the drift class this sprint exists to close), AC2 unmet.

### Option C: Extend verify_design_sweeps.py to RN/desktop trees so all three skills wire to scripts

- **Approach**: Teach `_discover_screens` about `.tsx`, add string-literal-vs-comment semantics for RN, then replace all three skills' sweeps with validator calls.
- **Pros**:
  - Uniform script ownership across platforms; mobile/desktop sweeps stop being model self-checks.
- **Cons**:
  - Modifies the exact file ISSUE-064 is hardening in a parallel worktree with the CLI contract frozen post-063 — a guaranteed collision plus a contract change (`.tsx` discovery alters the "empty screen set is a violation" semantics for existing callers).
  - JSX string-literal vs comment vs interpolation parsing is a new matcher class 064's edge-hardening would immediately own; landing it mid-flight doubles both reviews.
- **Trade-off**: +1 platform-uniform gate, +1 frozen-contract violation, +1 parallel-worktree merge conflict with ISSUE-064, +~2d matcher work outside this issue's estimate.

## Decision

**Chosen: Option A.** Option B fails AC2 outright and re-litigates the drift liability this conversion exists to close; Option C's trade-off line contains a frozen-contract violation and a guaranteed collision with the in-flight ISSUE-064 worktree. Option A's cost (one assertion-preserving test re-point, three param dicts) is the only one measured in hours, not in standing liabilities.

### Keep-list (every kept prescription names its owner gate and depreciation trigger)

| # | Kept prescription (class) | Owner gate (what falsifies it) | Depreciation trigger (delete when…) |
|---|---------------------------|--------------------------------|--------------------------------------|
| K1 | Pilot gate protocol: neutral observation (banned vocabulary) → separate-context design-auditor critique → specificity check (3 details, literal_quote = exactly 1) → auto-correction hard cap N=3 → user HOLD; degraded mode never silently skips | The gate itself (separate-context structure, C-bucket per SPEC-055) + tests/test_pilot_gate_hardening.py | None — C-bucket, explicitly Scope-Out for weakening. Extraction to `{{PILOT_GATE}}` changes location, zero behavior. |
| K2 | Anti-slop trio: banned-default clusters, Brief-overrides ledger, self-similarity check | `{{SLOP_CALIBRATION}}` fragment + ai-tell sweep's `--exempt` protocol (only recorded overrides exempt) | The cluster list carries its own dating note ("what everyone is producing this year") — refresh/replace clusters when a design run's critique stops flagging them; the ledger and self-similarity check are contract, no trigger. |
| K3 | Specific AI Tells list (generic names, fake-perfect numbers, filler verbs, em-dash zero tolerance, fake `<div>`/`<View>` product UI, section-number eyebrows, version labels, decorative status dots, locale/time strips, middle-dot ration, italic headings, silent success, carousel pause) | Web: `verify_design_sweeps.py ai-tell` for the deterministic subset (em-dash, 100vh, flex-calc-width, generic-name, fake-perfect-number, filler-verb, scroll-cue); judgment subset + mobile/desktop: Phase 5.5 model sweep in `{{DESIGN_SWEEPS}}` / `{{AI_TELLS}}` | Per tell: two consecutive design runs whose sweep reports zero hits for a tell → delete that prose line (script-side entries stay — script lines are cheap, prose lines cost context). |
| K4 | Layout-safety + motion mechanics (deterministic grep patterns): `overflow-x: clip` on html+body; `minmax(0, 1fr)` on image tracks; `overflow-wrap: anywhere` on display headers; all-caps `line-height ≥ 1.0`; single `position: sticky; top: 0`; `align-items: center` on mixed-height flex rows; `min-height: 100dvh` never `100vh`; CSS Grid never flex-calc columns; no `transition: all`; animate only `transform`/`opacity`/`filter`; overshoot easings only on physical interactions; instant `outline` focus rings; selector-specificity one-owner rule | Phase 5.5 mechanics sweep (whitespace-insensitive greps, in `{{DESIGN_SWEEPS}}`); `100vh` + flex-calc additionally script-owned on web (ai-tell) | A rule whose mechanics sweep reports zero violations across two consecutive design runs is deleted; the whole block is replaced by a validator call the day `verify_design_sweeps.py` grows a mechanics sweep. |
| K5 | Input-state 8-state rules: constant `border-width` across states; `outline`-based focus ring; input height == adjacent button height; reserved helper/error slot; multi-channel disabled (never opacity alone) | Phase 5.5 mechanics sweep (in `{{DESIGN_SWEEPS}}`) | Same as K4. |
| K6 | Contrast sweep: button text ≈ button fill (black-on-black); accent surface without verified accent-ink; dark surface that didn't flip ink | Phase 5.5 contrast sweep procedure (in `{{DESIGN_SWEEPS}}`) — "the failures that ship most" | Replace prose with a computed-style contrast validator call when one lands (the `verify_computed_styles.py` renderer seam exists for the Figma pipeline); delete the prose then. |
| K7 | Reference-research anti-fabrication protocol: image-grounded only (no WebFetch extraction), Paths a/b/c, 2–3 strong cues with image citations, `literal_quote:` format + abstract-concept rejection, ≈-marking | tests/test_uiux_reference_fabrication_guard.py + tests/test_reference_anchor_tuning.py + philosophy checkpoint + `literal-quote` sweep | None — contract, not craft. Stays inline per tmpl (raw-tmpl test pins + genuine per-platform example deltas). |
| K8 | Electron security pins: `contextIsolation: true`, `nodeIntegration: false`, contextBridge-only typed IPC, main/preload/renderer separation | Named contract line in desktop skill + agent (security review dimension owns violations) | None — security invariant, not craft. |
| K9 | Mobile/desktop Phase 5.5 sweeps stay model-executed contract prose (signature-move reference check, literal-quote string-literal check, AI-tell sweep, contrast, mechanics) | `{{DESIGN_SWEEPS}}` per-skill resolution; the sweep text states the procedure as deterministic greps, not vibes | The day `verify_design_sweeps.py` accepts non-HTML prototype trees (post-064 successor), replace the prose sweeps with validator calls — the trigger line is embedded in the fragment so the next editor sees it. |
| K10 | Prototype runnability contract (replaces the pin lists): mobile — generate a valid Expo project, run `npm install && npx expo install --fix`, prototype must boot on simulator; desktop — valid Electron+Vite project, `npm run dev` must launch | The boot itself (an empirical gate that catches every config-pin failure the deleted lists memorized, including ones the lists didn't know yet) | None — contract. The deleted pins (D3/D4) depreciate against it: any pin the boot gate catches is never re-documented. |

### Delete-list (model-absorbed; absence is mutation-tested on actually-removed strings)

| # | Deleted prescription (class) | Where it lived |
|---|------------------------------|----------------|
| D1 | Motion duration-band tables (web 100–150/200–300/300–500/500–800ms; mobile 80–120…max 700ms; desktop 60–100…max 700ms), easing-selection guides, stagger-pattern recipes, hover-choreography and gesture-choreography essays | 3 agents §Motion & Interaction (deep); skill Phase 3 motion-token band prose |
| D2 | Typography tutorials: font-pairing strategy lists, modular-scale personality theory, weight-exploitation bands, letter-spacing rules, `clamp()` recipes, CJK line-height numbers, variable-font / `font-display` advice, minimum-size notes | 3 agents §Typography (deep) |
| D3 | Expo dependency/config pins: `"main": "node_modules/expo/AppEntry.js"`, babel-preset-expo file body, plugins-array warnings (expo-haptics), dependency roster bullets, tsconfig extends pin, SDK-version strategy, `React.memo`/`useCallback` checklist, Phase 5.5 "Expo project setup check" pin list | mobile skill steps 17–17c & Phase 5.5 step 24/29; mobile agent §Prototype Quality Rules 1 & 6 |
| D4 | Electron perf prescriptions: `will-change` ≤5 budget, `contain: layout style paint`, IPC debounce/size numbers, 500KB-gzip bundle target, `manualChunks` vendor split, `utilityProcess` offload, virtualization/`React.lazy` checklists, cold-start ms targets, memory-cleanup checklists, Phase 5.5 steps 28–30 perf/IPC/bundle checklists | desktop skill steps 17/20–21 & Phase 5.5 steps 28–30; desktop agent §Performance / §Motion craft |
| D5 | Confidence-rating ritual (`**Confidence rating**` High/Medium/Low tail) — ISSUE-059 class, 060-owned | 3 agents §Self-Review + `self_review_confidence` chunk in fragments.py; tests/test_scaffolding_residue.py whitelist emptied |
| D6 | `WebFetch` tool grant in the three agents (no call site; skills already ban WebFetch extraction) | 3 agents frontmatter `tools:` |
| D7 | Mood-board craft: §Spatial Composition, §Backgrounds & Depth, §Color & Theme essays, desktop §Keyboard (deep) tutorial (the Command-Palette/shortcut MUSTs survive as contract lines in skill + agent) | 3 agents |
| D8 | GPU-composited trivia ("box-shadow is NOT GPU-composited"), `prefers-reduced-motion` how-to essays (the reduced-motion requirement itself survives as one contract line owned by the Phase 5.5 check), scroll-driven-effects recipes | web agent §6 / skill Phase 3; agents §Motion |

### Sweep wiring (web /uiux Phase 5.5, the ISSUE-057 deferral closed)

The web skill's deterministic sweeps become one call site (in `{{DESIGN_SWEEPS}}`):

```
python3 scripts/verify_design_sweeps.py all --class <signature-move-class> [--exempt <tell-id> ...]
```

- `--class` comes from the Signature Move's reusable class (Phase 5A step 14 encoding); `all` without it fails closed (exit 2) — never drop a sweep to get past a usage error.
- `--exempt` ids map 1:1 from recorded `Brief overrides:` bullets only (K2 ledger); an unrecorded violation is never exempt.
- Exit 0 → the literal-quote / signature-move / ai-tell gates pass; exit 1 → fix the listed `file:line` violations and re-run; the validator's verdict is final (no prose re-adjudication).
- Gate parity (AC1): the script is the same predicate the prose asserted (SPEC-056 promoted it verbatim; ISSUE-063 fixed the contract deviations) — parity is pinned by fixture tests driving the exact call shape the skill instructs (`all --class X --json`) over pass/fail prototype trees.

## Trade-offs Accepted

- Mobile/desktop sweeps remain model-executed until a post-064 validator accepts non-HTML trees (K9) — accepted because the alternative (Option C) collides with an in-flight worktree and a frozen contract.
- Scan-time effort: tests/test_pilot_gate_hardening.py now imports `gen_skills.process_template` (same pattern as test_reference_anchor_tuning), coupling it to the resolver registry. Accepted: that coupling is the mechanism under test.
- Deleted pins (D3/D4) may let a prototype misconfiguration reach the boot gate instead of being prevented upfront — accepted: the boot gate catches the class (including future unknown pins), the lists only caught their snapshot.
- The three agents keep their platform NEVER-lists and deliverable/quality contracts inline (not fragment-guarded) — accepted: they are genuinely platform-specific; only text shared across all three belongs in `AGENT_DESIGN_FRAGMENTS`.

## Migration

1. `scripts/fragments.py`: add `{{PILOT_GATE}}`, `{{AI_TELLS}}`, `{{DESIGN_SWEEPS}}` templates + per-skill param dicts + resolver functions; remove the `self_review_confidence` chunk from `AGENT_DESIGN_FRAGMENTS`; register the new resolvers in `scripts/gen_skills.py`.
2. Rewrite the three `SKILL.md.tmpl` files: swap the shared blocks for tokens, delete the D-table prose, keep K-table blocks (with trigger lines where the table says so), wire the web sweep call site; keep every ISSUE-057 checkpoint invocation and every raw-tmpl test pin (Phase 4.5 contract, Reference Research, extend-mode token) intact.
3. Shrink the three agent files per the D-table; agents keep every surviving `AGENT_DESIGN_FRAGMENTS` chunk verbatim; drop `WebFetch` from `tools:`.
4. Regenerate: `python3 scripts/gen_skills.py`.
5. Tests: extend tests/test_design_fragments.py (new tokens, once-only sentinels); empty the whitelist in tests/test_scaffolding_residue.py; re-point tests/test_pilot_gate_hardening.py at resolved content; add tests/test_uiux_contract_conversion.py (gate-parity fixtures over the exact `all --class X --json` call shape, call-site wiring pins, D-table absence guards with actually-removed strings, K-table trigger pins).
6. No checkpoint-engine change: `verify_checkpoint.py` phases (context/philosophy/system) are untouched (one stale-comment touch allowed: the philosophy verifier docstring's "until ISSUE-060" note may be updated to past tense).

## Rollback

`git revert` of the triplet PR restores the current prose, the whitelist, and the agent files in one commit; `scripts/verify_design_sweeps.py` and the ISSUE-057 checkpoints are untouched by this issue, so they need no action. Rollback signal: a design run where the converted skills demonstrably miss a violation the old prose sweeps caught (gate-parity regression), or the pilot-gate hardening tests go red against resolved content. Rollback time: one revert commit + `python3 scripts/gen_skills.py`.

## Open Questions

- [ ] Should a post-064 issue extend `verify_design_sweeps.py` to RN/desktop trees (K9 trigger) — owner: next evolution-audit pass, by: the sprint after ISSUE-064 ships.
- [ ] Do the K4/K5 mechanics deserve script promotion (a `mechanics` sweep subcommand) — owner: same post-064 issue, by: same milestone (the K4 trigger line already names the condition).
