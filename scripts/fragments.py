#!/usr/bin/env python3
"""Canonical UI/UX design-philosophy fragments (ISSUE-041).

The uiux / mobile-uiux / desktop-uiux skill templates and their three
developer agents used to carry six independently drifting copies of the
design-philosophy boilerplate (design interview + derivation, philosophy
checkpoint, token-compliance rule, self-review checklist). This module is
the single source of truth:

- Skill side: ``{{DESIGN_PHILOSOPHY}}``, ``{{DESIGN_PHILOSOPHY_CHECKPOINT}}``
  and ``{{SLOP_CALIBRATION}}`` tokens in the three SKILL.md.tmpl files resolve
  through :func:`design_philosophy_fragment` /
  :func:`design_philosophy_checkpoint` / :func:`slop_calibration_fragment`
  (registered in scripts/gen_skills.py next to ``PREAMBLE``). Resolution is
  per-skill, mirroring preambles.py: the desktop skill gets its two extra
  interview lines (question e, derivation e) and the ``/shortcut`` glyph
  variant injected here because they sit mid-fragment; all other
  platform-specific content stays inline in each tmpl.

- Agent side: the three agent files are static (not generated). They must
  contain every chunk in :data:`AGENT_DESIGN_FRAGMENTS` verbatim
  (whitespace-normalized). tests/test_design_fragments.py enforces this via
  :func:`find_out_of_sync_fragments` — editing a canonical chunk without
  syncing the agent files fails the suite, naming the out-of-sync file.

ISSUE-060 / SPEC-060 extends the mechanism with three contract-conversion
tokens — ``{{PILOT_GATE}}``, ``{{AI_TELLS}}``, ``{{DESIGN_SWEEPS}}`` —
resolved per-skill by :func:`pilot_gate_fragment`, :func:`ai_tells_fragment`
and :func:`design_sweeps_fragment`. The shared surviving text of the pilot
gate, the Specific-AI-Tells list and the Phase 5.5 verification sweeps lives
here exactly once; the web ``{{DESIGN_SWEEPS}}`` resolution wires the
``scripts/verify_design_sweeps.py`` call site, while the mobile/desktop
resolutions stay contract-shaped prose sweeps carrying the K9 handover
trigger.

Content changes here are intentional-by-definition: update the three agent
files in the same commit, then regenerate skills via
``python3 scripts/gen_skills.py``.
"""

from __future__ import annotations

UIUX_SKILLS: tuple[str, ...] = ("uiux", "mobile-uiux", "desktop-uiux")

UIUX_AGENT_FILES: tuple[str, ...] = (
    "agents/uiux-developer.md",
    "agents/mobile-uiux-developer.md",
    "agents/desktop-uiux-developer.md",
)

# ---------------------------------------------------------------------------
# Skill-side fragment: Phase 1.5 design interview + response handling
# ---------------------------------------------------------------------------

# Step number of the "Handle user response:" step (differs per skill flow:
# uiux runs the interview as step 4.5/5, mobile/desktop as 5.5/5.6).
_RESPONSE_STEP: dict[str, str] = {
    "uiux": "5",
    "mobile-uiux": "5.6",
    "desktop-uiux": "5.6",
}

# Desktop-only interview additions (intentional platform specifics that sit
# mid-fragment, so they are injected here rather than kept inline).
_DESKTOP_EXTRA_QUESTION = """\
   e) **Desktop Identity**: "Should this app feel like a native part of the OS, or should it have its own distinct visual identity?"
      (e.g., natural integration like a macOS native app vs distinct UI identity like Figma/Notion)

"""

_DESKTOP_EXTRA_DERIVE = """\
     e) Desktop Identity → infer from product type (productivity tool → native feel, creative tool → branded)
"""

_INTERVIEW_TEMPLATE = """\
Ask the user the following questions to anchor the design direction.
   These answers become binding constraints for Phase 2.
   Present all questions at once (not one-by-one) and wait for answers.
   Also tell the user: "If any of these are hard to answer right now, just say 'skip'. You can also skip the entire interview."

   a) **Brand Personality**: "If this product were a person, who would they be?"
      (e.g., a luxury hotel concierge, a neighborhood cafe barista, a strict operating room nurse, a playful friend)

   b) **Emotional Target**: "What one emotion do you want users to feel when they see the first screen?"
      (e.g., trust, curiosity, relief, excitement, calm)

   c) **Anti-Reference**: "What competing product or design should this absolutely NOT look like?"
      (a feeling you want to avoid, or a specific product name)

   d) **Aspiration Reference**: "Is there a product or brand you'd like to reference for design? (doesn't have to be the same domain)"
      (e.g., Stripe's cleanliness, Nintendo's playfulness, Aesop's luxury)

{desktop_question}{response_step}) Handle user response:

   **Case A — User answers (partially or fully)**:
   Record answers in memory — these become HARD CONSTRAINTS for Phase 2.
   If the user skips individual questions, note them as "unconstrained" but still avoid generic defaults.

   **Case B — User skips the entire interview** (says "skip", "pass", etc.):
   - Do NOT silently proceed with generic defaults.
   - Instead, the agent MUST auto-derive initial constraints from the PRD/UX spec:
     a) Brand Personality → infer from target user personas and product category in PRD
     b) Emotional Target → infer from the product's core value proposition
     c) Anti-Reference → infer from competitor analysis in PRD (if any), otherwise mark "unconstrained"
     d) Aspiration Reference → mark "unconstrained"
{desktop_derive}   - Present the auto-derived constraints to the user: "Since you skipped the interview, here's what I inferred from the PRD: [constraints]. Shall I proceed with these?"
   - If approved, proceed with these as soft constraints (not hard).
   - If rejected, re-offer the interview questions or accept corrections."""

# ---------------------------------------------------------------------------
# Skill-side fragment: Phase 2 design-philosophy checkpoint
# ---------------------------------------------------------------------------

_CHECKPOINT_TEMPLATE = """\
> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Run: `bash scripts/checkpoint.sh --skill {skill} --phase philosophy`
> The script verifies presence: the file, (a)'s Signature Move, (b), and the `literal_quote:` field. If exit code ≠ 0: STOP, fix, re-run. Depth stays model-side — self-verify below (ISSUE-057).
> Verify `docs/design_philosophy.md` exists with:
> (a) a **Signature Move** that is numeric/token-specific (not prose-only);
> (b) either a populated **Reference Anchors** section OR an explicit "Reference Anchors skipped (no image input)" line; AND
> (c) when Reference Anchors is present, exactly **2–3** adopted cues (not 1, not 4+), each citing an image path, plus a `literal_quote:` field with a concrete word/number/glyph{glyph_extra} (NOT an adjective like "luxury"). The literal_quote may only be omitted if Phase 1.5 interview was explicitly skipped — in which case `literal_quote: (skipped — interview not run)` must appear instead of the field being absent.
> If any of (a) / (b) / (c) fails: STOP and fix before proceeding."""


# ---------------------------------------------------------------------------
# Skill-side fragment: slop calibration (cluster list + brief override +
# self-similarity check). Shared verbatim with the three developer agents via
# AGENT_DESIGN_FRAGMENTS below, so keep it free of skill-only step numbers.
# ---------------------------------------------------------------------------

_SLOP_CALIBRATION = """\
**Calibration — the three current AI-design clusters.** Independent of subject, \
AI-generated design converges on three looks right now:
1. Warm cream ground (near `#F4F1EA`) + high-contrast serif display + terracotta accent.
2. Near-black ground + one bright acid-green or vermilion accent.
3. Broadsheet layout — hairline rules, zero corner radius, dense newspaper columns.
Each is legitimate for *some* brief. They are banned as **defaults**, not as \
choices: where the brief leaves an axis free, do not spend that freedom on one \
of these three. This list dates faster than the rest of this section — treat it \
as "what everyone is producing this year", not as a permanent ban.

**The brief's own words win.** Where the brief pins a direction, follow it \
exactly, including when it asks for one of the three clusters above and \
including when it contradicts a specific ban in this section. Record each such \
override in `docs/design_philosophy.md` under a `Brief overrides:` line, one \
bullet per overridden rule, quoting the brief. Any later sweep or reviewer \
honors recorded overrides and only recorded overrides — an unrecorded \
violation is still a violation.

**Self-similarity check — run before locking the design plan.** Strip the \
product-specific nouns out of the brief and ask what you would produce for that \
generic version. If your current plan is roughly where you land, it is a default \
wearing this product's content, not a choice made for this product. Revise the \
part that collapsed and say what you changed and why."""


# ---------------------------------------------------------------------------
# Skill-side fragment: create/extend mode branch (ISSUE-054 / SPEC-054)
#
# SPEC-054 chose ONE platform-parameterized design-scanner agent over three
# per-platform scanners: the platform difference is the source map (where a
# token lives), while the risky half — provenance, confidence tagging,
# refusing to invent values — is identical. Only the source map and the
# detection globs vary per skill below.
# ---------------------------------------------------------------------------

_EXTEND_MODE_PLATFORM: dict[str, dict[str, str]] = {
    "uiux": {
        "step": "4",
        "subject": "existing UI code",
        "platform": "web",
        "globs": (
            "`**/*.html`, `**/*.css`, `**/*.tsx`, `**/*.jsx`, `**/*.vue`, "
            "`**/*.svelte`"
        ),
        "source_map": (
            "CSS custom properties in stylesheets, `tailwind.config.*` theme "
            "keys, styled-components / emotion theme objects, and the "
            "component files that consume them"
        ),
        "system_doc": "docs/design_system.md",
        "extracted_doc": "docs/design_system.extracted.md",
    },
    "mobile-uiux": {
        "step": "5",
        "subject": "existing mobile code",
        "platform": "mobile",
        "globs": (
            "`**/*.tsx`, `**/*.ts`, `app.json`, `app.config.js`, "
            "`app.config.ts`"
        ),
        "source_map": (
            "`src/theme/` modules, `StyleSheet.create` objects across screens "
            "and components, and Expo config (`app.json`, `app.config.*`). "
            "React Native has no cascade, so a value applies only where it is "
            "written"
        ),
        "system_doc": "docs/design_system_mobile.md",
        "extracted_doc": "docs/design_system_mobile.extracted.md",
    },
    "desktop-uiux": {
        "step": "5",
        "subject": "existing desktop code",
        "platform": "desktop",
        "globs": (
            "`**/electron/**`, `**/main.ts`, `**/preload.ts`, "
            "`**/electron-builder.*`, `**/forge.config.*`, `**/*.tsx`, "
            "`**/*.ts`"
        ),
        "source_map": (
            "`src/theme/` modules and renderer-process CSS custom properties, "
            "plus the renderer component files that consume them. Native "
            "chrome (title bar, tray, menu structure) carries no token and is "
            "out of scope"
        ),
        "system_doc": "docs/design_system_desktop.md",
        "extracted_doc": "docs/design_system_desktop.extracted.md",
    },
}

_EXTEND_MODE_TEMPLATE = """\
{step}) Scan the project for {subject}, then choose the working mode:
   - Glob for {globs}
   - If found, read key files to understand current design patterns and tech stack.

   **Mode selection — `create` or `extend`** (ISSUE-054):
   - **Nothing found** → mode is `create`. Proceed exactly as this skill always
     has; nothing below applies.
   - **Found {subject}** → ask the user which mode they want, quoting what you
     detected (file count and the token-bearing files you saw):
     - `create` — design a new aesthetic. The existing UI will not constrain it.
     - `extend` — read the design that already ships and add to it.
     **Never switch modes silently.** Detection proposes; the user decides. If the
     user does not answer, default to `create` (today's behaviour) and say so.

   **On `extend` only** — invoke the **design-scanner** agent via the Task tool
   before the design interview. Pass it:
   - the platform: `{platform}`
   - the token-bearing files you detected. On `{platform}` those live in
     {source_map}.

   The agent returns a structured Design Scan report. It has no write tools; **you**
   write `{system_doc}` from its report.

   **Overwrite guard (MANDATORY)** — before writing, check whether `{system_doc}`
   already exists. If it does not, write it and continue. **If that file already
   exists, STOP** and ask the user, quoting its line count and last-modified date so
   they can see what is at stake:
   - `1) overwrite` — replace it; the previous content survives only in git history.
   - `2) write alongside` — write `{extracted_doc}` instead and show a summary of how
     it differs from the current file. Nothing existing is touched.
   - `3) cancel` — stop `extend` mode here.
   **Do not write until the user answers.** A hand-maintained design system is the one
   artifact this mode can destroy, and "it's in git" is not consent.

   When transcribing the report into whichever file you write, preserve its tags
   verbatim:
   - `[CONFIRMED]` claims keep their `file:line` reference. Never promote an
     `[INFERRED]` claim to `[CONFIRMED]`, and never drop a tag when transcribing.
   - Carry over `Dead tokens`, `Gaps`, and undeclared-but-repeated values. These are
     findings about the host product, not noise to tidy away.
   - If the report says `extraction_verdict: insufficient`, tell the user verbatim and
     ask whether to continue in `extend` (mostly-`[INFERRED]` system) or fall back to
     `create`. Do not decide this silently.

   **What `extend` changes downstream** (the mode contract — apply all of it):
   - **Design philosophy**: do NOT commit to a new aesthetic direction. Name the
     aesthetic the codebase already has, and take the Signature Move from the
     agent's `signature_move` field. If it reported `none found`, say so to the user
     and agree on one derived from an existing recurring pattern — never invent one
     the codebase does not already show.
   - **Design interview**: reframe from "what should this be?" to "what should change,
     and what must stay?" Answers are constraints on the delta, not on the whole system.
   - **Pilot gate**: the specificity check becomes a **consistency check** — instead of
     "name 3 details that only make sense for THIS product", ask "name 3 details that
     match the extracted system, citing its `file:line` provenance". A pilot that reads
     as a redesign FAILS the gate even if it is distinctive.
   - **AI Tell sweep**: when the host codebase already uses a listed tell, record it as a
     `Brief overrides:` bullet quoting the source (`existing product convention —
     <file:line>`) instead of rewriting the product's own conventions."""


# ---------------------------------------------------------------------------
# Skill-side fragment: pilot-gate protocol (ISSUE-060 / SPEC-060 K1).
# Extraction changes location, zero behavior — the full 4-substep protocol
# (neutral observation → separate-context critique → specificity check →
# auto-correction hard cap) is pinned by tests/test_pilot_gate_hardening.py
# against resolved template content.
# ---------------------------------------------------------------------------

_PILOT_GATE_PLATFORM: dict[str, dict[str, str]] = {
    "uiux": {
        "s": "2",
        "render_block": """\
    - **Step 1 — Render**: for each pilot HTML, run:
      ```
      python3 scripts/screenshot_pilot.py prototype/screens/<pilot>.html --viewport 1280x800 --full-page
      ```
      Produces `prototype/screens/<pilot>.png`. If the script exits "no screenshot backend available":
        - DO NOT silently skip the critique. Enter **degraded mode** for Steps 2.0–2.2: critique runs against the HTML/CSS *source* instead of the rendered PNG.
        - Record `pilot_degraded: no_screenshot_backend` in the critique log so the user sees the limitation.""",
        "observe_subject": "what you see in the PNG (or HTML in degraded mode)",
        "screens_dir": "prototype/screens",
        "observation_example": """ Like:
      ```
      1. Top bar 64px tall, dark navy background, four icon buttons right-aligned.
      2. Hero headline reads "조용한", left-aligned, 168pt serif, off-white text.
      3. Below the hero, three cards in a row at 24% / 38% / 38% widths.
      4. Bottom-right floating action button, 56px, orange fill, no border.
      5. Sticky bottom toolbar with four state-switcher buttons.
      ```""",
        "critique_inputs": "the pilot PNG path (or HTML path in degraded mode)",
        "design_system_doc": "docs/design_system.md",
        "philosophy_step": "8",
        "rerun_chain": (
            "re-screenshot (Step 1) → re-observe (Step 2.0) → re-critique "
            "(Step 2.1) → re-specificity (Step 2.2)"
        ),
        "stamp_line": (
            "Record the final scores as a one-line stamp at the top of "
            "`styles.css`: `/* pre-emit critique cycle=N: P5 H4 E5 S4 R5 V5 "
            "specificity=PASS */`."
        ),
    },
    "mobile-uiux": {
        "s": "2.5",
        "render_block": """\
    - **Render inputs**: mobile pilots run live in Expo (no PNG capture in this skill), so the critique inputs are the pilot `.tsx` source + the design system. This is treated as **degraded mode** by default — record `pilot_degraded: no_screenshot_input` in the critique log so the user sees the limitation. DO NOT silently skip the critique.""",
        "observe_subject": "what would render",
        "screens_dir": "prototype-mobile/src/screens",
        "observation_example": "",
        "critique_inputs": "the pilot `.tsx` path",
        "design_system_doc": "docs/design_system_mobile.md",
        "philosophy_step": "9",
        "rerun_chain": (
            "re-observe (Step 2.5.0) → re-critique (Step 2.5.1) → "
            "re-specificity (Step 2.5.2)"
        ),
        "stamp_line": (
            "Record final scores at the top of the pilot screen file: "
            "`// pre-emit critique cycle=N: P5 H4 E5 S4 R5 V5 "
            "specificity=PASS`."
        ),
    },
    "desktop-uiux": {
        "s": "2.5",
        "render_block": """\
    - **Render inputs**: desktop pilots run live in Electron (`npm run dev`). If Playwright + Electron is installed, screenshot the rendered window for the critique inputs. Otherwise critique runs against the pilot `.tsx` source (**degraded mode**) — record `pilot_degraded: no_playwright_electron` in the critique log so the user sees the limitation. DO NOT silently skip the critique.""",
        "observe_subject": (
            "what renders (screenshot) or what the source would render "
            "(degraded)"
        ),
        "screens_dir": "prototype-desktop/src/screens",
        "observation_example": "",
        "critique_inputs": (
            "the pilot screenshot path (if available) AND the pilot `.tsx` "
            "path"
        ),
        "design_system_doc": "docs/design_system_desktop.md",
        "philosophy_step": "9",
        "rerun_chain": (
            "re-screenshot (if available) → re-observe (Step 2.5.0) → "
            "re-critique (Step 2.5.1) → re-specificity (Step 2.5.2)"
        ),
        "stamp_line": (
            "Record final scores at the top of the pilot stylesheet/screen "
            "file: `/* pre-emit critique cycle=N: P5 H4 E5 S4 R5 V5 "
            "specificity=PASS */`."
        ),
    },
}

_PILOT_GATE_TEMPLATE = """\
Generator-as-judge fails: the same context that produced the pilot will not \
reliably catch its own slop. This gate routes the critique through a separate \
sub-agent context and runs up to 3 auto-correction cycles before presenting \
to the user. Do not auto-proceed past Step 3.

{render_block}

    - **Step {s}.0 — Neutral observation** (mandatory; do this BEFORE any judgment).
      For each pilot, write 5 plain factual statements about {observe_subject}.
      **Banned vocabulary in this step**: `signature move`, `aesthetic`, `archetype`, `philosophy`, `direction`, `taste`, `slop`, `generic`, `bold`, `restrained`, `premium`, brand names, the chosen aesthetic name. Use only colors, sizes, shapes, positions, counts, content categories.
      Output to `{screens_dir}/<pilot>.observations.md`.{observation_example}
      If you catch yourself reaching for a banned word, restart Step {s}.0 — the observation is the input that prevents the critique from agreeing with itself.

    - **Step {s}.1 — Separate-context critique** (mandatory). Invoke `design-auditor` via the Task tool to evaluate the pilot from a fresh context. **Do NOT inline-critique in the generator's context.**
      Pass the auditor:
        - {critique_inputs}
        - `{screens_dir}/<pilot>.observations.md`
        - `docs/design_philosophy.md` (so it knows the system claim it should check)
        - `{design_system_doc}`
      Ask it to return:
        - the 6-axis score (Philosophy / Hierarchy / Execution / Specificity / Restraint / Variety), each 1–5
        - one piece of cited evidence per axis, referencing observation indices (e.g., "Specificity 2 — observations 2,3 are interchangeable with any landing page")
        - a list of slop signals it flags
      Where ui-reviewer's scope applies (state coverage in pilots, copy usage), also invoke `ui-reviewer` via the Task tool with the same inputs. The two sub-agents' scopes are disjoint (per ISSUE-013) — do not deduplicate findings, surface both.
      Save the structured output to `{screens_dir}/<pilot>.critique.md`.

    - **Step {s}.2 — Specificity check** (mandatory). Ask the design-auditor (still in its separate context) to answer:
      *"Name 3 details visible in this pilot that ONLY make sense for THIS specific product / domain / user. Generic UI primitives ('a card', 'a hero', 'a button') do not count. Domain content does count (real entity names, the literal_quote from Reference Anchors, domain-specific units, brand-specific shortcuts). If you can list fewer than 3, the pilot FAILs specificity."*
      The literal_quote (from ISSUE-012) counts as exactly **1** of the 3 — not 0, not 2+. The other 2 must come from independent product/domain details.
      Specificity FAIL → treat as a critique failure feeding Step {s}.3.

    - **Step {s}.3 — Auto-correction cycle** (hard cap N=3 rounds). If any axis score < 3, OR Step {s}.2 returns FAIL, OR slop signals are flagged:
      1. Identify the correct layer to patch:
         - Philosophy / Specificity < 3 → revisit Phase 2 step {philosophy_step} (`docs/design_philosophy.md`).
         - Hierarchy / Execution / Restraint < 3 → revisit the Phase 3 design system (`{design_system_doc}`) or Phase 4 numeric layout commitments.
         - Variety < 3 → re-pick the pilot archetype or restructure the pilot itself.
         - Specificity FAIL → either add concrete product details to the pilot or, if Phase 1.5 was skipped, document that and proceed.
      2. Apply the patch.
      3. Re-run the gate: {rerun_chain}.
      4. Increment the cycle counter. Append a one-line summary to `{screens_dir}/<pilot>.cycles.log`:
         `cycle N: layer=<L> change="<short summary>" scores=P5 H4 E5 S3 R5 V4 specificity=PASS|FAIL`.
      5. **Hard stop at N=3**. After the third unsuccessful cycle, freeze the pilot and surface to the user with the full cycle history. Do NOT loop indefinitely.
      {stamp_line}"""


# ---------------------------------------------------------------------------
# Skill-side fragment: Specific AI Tells (ISSUE-060 / SPEC-060 K3).
# One canonical tell list; the per-tell depreciation trigger is named in the
# {{DESIGN_SWEEPS}} block that executes the sweep.
# ---------------------------------------------------------------------------

_AI_TELLS_PLATFORM: dict[str, dict[str, str]] = {
    "uiux": {
        "emdash_scope": (
            "everywhere visible (headlines, labels, body, captions, "
            "attribution)"
        ),
        "fake_ui_rule": (
            "build a fake product UI out of styled `<div>` rectangles (fake "
            "dashboard, terminal, task list, chart) to fill a hero or "
            "preview. This is the #1 design tell."
        ),
        "fake_ui_alt": " preview",
        "version_footer_tail": " inside previews",
        "dot_scope": "nav/list/badge",
        "decorative_extra": """\
- No three identical equal-width feature cards in a row → 2-col zig-zag, asymmetric grid, or scroll-pinned alternative.
- No fake photo-credit captions (`Frame XII · 35mm`, `Plate 03`) — real photographer credit only.
""",
        "italic_rule": (
            "`font-style: italic` on `h1`–`h6` / display / wordmark / hero "
            "stat / `<em>` inside a heading is a top tell."
        ),
        "toast_kind": "toast",
        "interaction_extra": """\
- Tooltip delays differ by input: hover delays 800–1000ms, keyboard focus shows at 0ms (never equal).
- Auto-rotating content (carousel, banner, stat ticker) must pause on hover AND focus (WCAG 2.2.2).
""",
        "mechanics_block": """\
*CSS mechanics (web):*
- Full-height hero: use `min-height: 100dvh`, NEVER `100vh` / `height: 100vh` (iOS Safari address-bar jump).
- Multi-column layouts: use CSS Grid (`grid-template-columns`), NEVER flex percentage math (`width: calc(33% - 1rem)`).
- Selector-specificity collisions: a section-level class (`.section`) and an element-level class (`.cta`) that both set the same box property silently cancel each other out by source order. Section-to-section `padding`/`margin` is where this bites most. Give each box property exactly ONE owning selector; when two must coexist, raise the intended winner's specificity explicitly instead of relying on rule order.
- Full deterministic layout/motion/input rules live in Phase 5A step 14 ("Layout-safety / Motion / Input-state mechanics") and are swept in Phase 5.5.""",
    },
    "mobile-uiux": {
        "emdash_scope": (
            "in all visible text (titles, labels, body, empty/error copy)"
        ),
        "fake_ui_rule": (
            "fake a product surface out of styled `<View>` rectangles (fake "
            "chart, fake feed, fake map) to fill a hero/onboarding slide."
        ),
        "fake_ui_alt": "",
        "version_footer_tail": " as decoration",
        "dot_scope": "list row/tab/badge",
        "decorative_extra": "",
        "italic_rule": (
            "`fontStyle: 'italic'` on title/display/hero-stat `<Text>` is a "
            "top tell."
        ),
        "toast_kind": "toast/haptic",
        "interaction_extra": """\
- Auto-advancing carousels/banners must be pausable and never the only way to reach content.
""",
        "mechanics_block": """\
*Motion & input mechanics (React Native):*
- Animate only `transform` / `opacity` in Reanimated worklets; never animate layout props (`width`, `height`, `margin`, `padding`, `top`, `left`) that trigger re-layout per frame.
- Reserve overshoot/bouncy springs for **gesture-driven / physical** interactions (press, drag, pull-to-refresh, sheet) — not for incidental state changes (colour, opacity, content swaps).
- No stacking multiple simultaneous effects (scale + translate + shadow + rotate) on one element.
- `TextInput` states: keep `borderWidth` constant across default/focus/error (change `borderColor`/background, never width — it shifts layout); input height == adjacent button height (44pt floor); reserve the helper/error slot height so an appearing error doesn't push content; disabled needs three channels — dimmed style + `editable={false}` + `accessibilityState={{ disabled: true }}` (never opacity alone).""",
    },
    "desktop-uiux": {
        "emdash_scope": (
            "in all visible text (titles, labels, menu items, body, "
            "empty/error copy)"
        ),
        "fake_ui_rule": (
            "fake a product surface out of styled `<div>` rectangles (fake "
            "chart, fake terminal, fake data table) to fill a welcome/empty "
            "screen."
        ),
        "fake_ui_alt": "",
        "version_footer_tail": (
            " as decoration (a real app-version readout in About/status bar "
            "is fine)"
        ),
        "dot_scope": "list row/tab/badge",
        "decorative_extra": "",
        "italic_rule": (
            "`font-style: italic` on `h1`–`h6` / display / wordmark / `<em>` "
            "inside a heading is a top tell."
        ),
        "toast_kind": "toast",
        "interaction_extra": """\
- Tooltip delays differ by input: hover delays 800–1000ms, keyboard focus shows at 0ms (never equal).
- Auto-rotating content (carousel, banner, ticker) must pause on hover AND focus (WCAG 2.2.2).
""",
        "mechanics_block": """\
*CSS mechanics (renderer) — deterministic, all mandatory:*
- Multi-column / split-pane layouts: use CSS Grid (`grid-template-columns`), NEVER flex percentage math (`width: calc(33% - 1rem)`), which breaks on gap rounding.
- Selector-specificity collisions: a pane/section-level class (`.section`) and an element-level class (`.cta`) that both set the same box property silently cancel each other out by source order. Pane-to-pane `padding`/`margin` is where this bites most. Give each box property exactly ONE owning selector; when two must coexist, raise the intended winner's specificity explicitly instead of relying on rule order.
- `overflow-x: clip` on BOTH `html` and `body` (use `clip`, not `hidden` — preserves descendant `sticky`/`fixed`); no horizontal scroll at any window width down to 320px.
- Any grid track holding an image uses `minmax(0, 1fr)`, never bare `1fr`.
- Display headers set `overflow-wrap: anywhere; min-width: 0`; all-caps display type uses `line-height ≥ 1.0`.
- At most ONE `position: sticky; top: 0` (the top chrome/toolbar); other sticky elements offset to `top: var(--banner-height)` with a lower z-index than the toolbar.
- Flex rows mixing height-different children set `align-items: center`.
- No `transition: all` / `transition-all` — name properties. Focus rings appear instantly (no `transition` on `outline`) and use `outline`, never `border`. Reserve overshoot easings for drag/physical interactions only.
- Input/select 8-state rules: constant `border-width` across states (change `outline`/`box-shadow`/`border-color`); `outline`-based focus ring; input height == adjacent button height; reserve helper/error slot with `min-height: 1lh`; disabled = `opacity` + `cursor: not-allowed` + `disabled`/`aria-disabled` (never opacity alone).""",
    },
}

_AI_TELLS_TEMPLATE = """\
**Specific AI Tells (hard bans — sweep every screen before presenting).**
Concrete signatures LLMs default to. Banned unless the brief explicitly \
calls for one. Per-tell depreciation trigger: named in the Phase 5.5 sweep \
block.

*Content & data:*
- Generic person names ("John Doe", "Sarah Chan") or startup-slop brand names ("Acme", "Nexus", "SmartFlow", "Cloudly") → invent contextual, locale-appropriate, real-sounding names.
- Fake-perfect numbers (`99.99%`, round `50%`, `1,234,567`) → organic messy values (`47.2%`, `+1 (312) 847-1928`).
- Filler verbs ("Elevate", "Seamless", "Unleash", "Next-Gen", "Revolutionize") → concrete verbs only.
- **Em-dash (`—`) and en-dash-as-separator (`–`): zero tolerance** {emdash_scope}. Use a regular hyphen `-`, comma, period, colon, or line break. The single most-violated tell.

*Fake product UI:*
- NEVER {fake_ui_rule} Use a real screenshot, generated image, real component{fake_ui_alt}, or skip it.
- No fake version footers / sync stamps (`v0.6.2-rc.1`, `last sync 4s ago`){version_footer_tail}.

*Decorative meta:*
- No section-number eyebrows (`001 · Capabilities`) or `01 / 4` pagination labels — name the topic in plain language.
- No version labels (`V0.6`, `BETA`, `EARLY ACCESS`, `ALPHA`) unless the brief is explicitly a launch/preview.
- No decorative status dots before every {dot_scope} (only for real semantic state, sparingly).
- No locale/time/weather strips (`Lisbon 14:23 · 18°C`), no scroll cues (`↓ Scroll to explore`), no mono-caps decoration strips (`BRAND. MOTION. SPATIAL.`).
- Ration the middle dot `·` to max 1 per metadata line; never as a universal separator.
{decorative_extra}
*Typography & interaction tells:*
- **No italic headings.** {italic_rule} Emphasis = weight, accent colour, or a drawn underline. Italic only inside running body copy.
- No celebratory success {toast_kind} for an action whose effect is already visible (silent success; reserve toasts for failures and invisible effects).
{interaction_extra}
{mechanics_block}"""


# ---------------------------------------------------------------------------
# Skill-side fragment: Phase 5.5 verification sweeps (ISSUE-060 / SPEC-060).
# Web: the deterministic literal-quote / signature-move / ai-tell sweeps are
# ONE scripts/verify_design_sweeps.py call site (the ISSUE-057 deferral
# closed). Mobile/desktop: contract-shaped prose sweeps carrying the K9
# handover trigger. Contrast (K6) and mechanics (K4/K5) sweeps stay prose on
# all platforms until their named validator successors land.
# ---------------------------------------------------------------------------

_DESIGN_SWEEPS_PLATFORM: dict[str, dict[str, str]] = {
    "uiux": {
        "lead": """\
- **Script-owned sweeps — literal-quote / Signature Move / AI-tell (deterministic subset)**: run from the project root:
  ```
  python3 scripts/verify_design_sweeps.py all --class <signature-move-class> [--exempt <tell-id> ...]
  ```
  - `<signature-move-class>` is the Signature Move's reusable class from the Phase 5A step 14 encoding (`docs/design_philosophy.md` states the move with numeric/token specificity; `prototype/styles.css` implements it as that reusable class). `all` without `--class` fails closed (exit 2, naming the signature-move sweep) — never drop a sweep to get past a usage error.
  - `--exempt` tell-ids map 1:1 from the recorded `Brief overrides:` bullets in `docs/design_philosophy.md`, and only from those — an unrecorded violation is never exempt. Script-owned tell ids: `em-dash`, `100vh`, `flex-calc-width`, `generic-name`, `fake-perfect-number`, `filler-verb`, `scroll-cue`.
  - Exit 0 → the literal-quote / signature-move / ai-tell gates pass. Exit 1 → fix the listed `file:line` violations and re-run. The validator's verdict is final — no prose re-adjudication.
  - The **Literal quote verbatim render check** is script-owned here (the `literal-quote` sweep). Fix path on failure: inject the quote verbatim into the screen named by the anchor's "where it appears" hint, then re-run — never widen the match (no substring or partial matches).
- **AI Tell sweep (judgment subset — model-executed)**: sweep `prototype/screens/` and `prototype/styles.css` for the tells the script does not own: `<div>`-based fake product UI, section-number eyebrows, hero version labels, three equal feature cards, decorative status dots, locale/time strips, mono-caps decoration strips, middle-dot rationing, italic headings, celebratory success toasts, unpausable auto-rotating content. Exempt exactly the recorded `Brief overrides:` bullets and no others; report each as `exempt: <tell> — <brief quote>`. Zero tolerance on div-based fake product UI. List every violation as `file:line`, fix, re-sweep.""",
        "contrast_body": """\
  - For every `(color, background-color)` pair on a screen, verify the WCAG ratio against its *computed* background: body text (<24px regular / <18px bold) needs ≥ 4.5:1; large text (≥24px / ≥18px bold), icons, and focus rings need ≥ 3:1.
  - Fail on any of: **button text ≈ button fill** (text colour within ~5% lightness of the fill — the black-on-black bug); `--color-accent` filling a text-bearing surface without a defined, verified `--color-accent-ink`; any **dark section** (background lightness < 50%) that did not also flip its text colour (ink-on-ink). Most-missed: text in a card that switched `background` but inherited `color`; muted text on a tinted surface.
  - List failing pairs as `file:selector`, fix, and re-check before proceeding.""",
        "mech_label": " (deterministic — grep `prototype/styles.css` and screens)",
        "mechanics_body": """\
  - Flag and fix: `transition: all` / `transition-all`; animating `width`/`height`/`top`/`left`/`margin`/`padding`; bare `1fr` tracks on image-bearing grids (must be `minmax(0, 1fr)`); `font-style: italic` on heading/display selectors; a second `position: sticky; top: 0` (only the nav may sit there); all-caps display with `line-height` < 1.0.
  - Confirm present: `overflow-x: clip` on BOTH `html` and `body`; a `prefers-reduced-motion: reduce` media block that reduces non-essential motion (the reduced-motion requirement is this one contract line); input fields satisfy the 8-state rules (constant `border-width`, `outline`-based focus ring, reserved helper slot, multi-channel disabled) from Phase 5A step 14.
  - Match patterns **whitespace-insensitively** (normalize spaces first, and ignore matches inside CSS comments): `transition:all` ≡ `transition: all`, `top:0` ≡ `top: 0`, `overflow-x:clip` ≡ `overflow-x: clip`.
  - List every violation as `file:line`, fix, and re-sweep.""",
    },
    "mobile-uiux": {
        "lead": """\
- **Script handover (K9 trigger)**: these sweeps stay model-executed contract prose — stated as deterministic grep procedures, not vibes — because `scripts/verify_design_sweeps.py` discovers `*.html` screens only. The day the validator accepts non-HTML prototype trees (a post-ISSUE-064 successor), replace them with validator call sites; the web skill already runs one.
- **Signature Move sweep**: `docs/design_philosophy.md` must contain a Signature Move with numeric/token specificity (not prose-only), implemented as a reusable component/hook/HOC under `src/components/` or `src/theme/`. Grep `src/screens/*.tsx`: every screen (including the pilots) must reference that reusable primitive at least once. On any failure: list violations, fix, and re-verify.
- **Literal quote verbatim render check** (skip only if Phase 1.5 was explicitly skipped): read `literal_quote:` from `docs/design_philosophy.md` Reference Anchors; grep `src/screens/*.tsx` — the string MUST appear verbatim in at least one screen's string literal (NOT inside a comment, NOT interpolated from a variable). If absent: inject it into the screen named by the anchor's "where it appears" hint and re-grep — never widen the match.
- **AI Tell sweep** (CRITICAL): sweep every `.tsx` file in `src/screens/` and `src/components/` for the banned tells in "Specific AI Tells": em-dash (`—`/`–`) in any string literal, generic person/brand names, fake-perfect numbers, section-number eyebrows, version labels, `<View>`-based fake product UI, decorative status dots, locale/time strips, scroll cues. Exempt exactly the recorded `Brief overrides:` bullets in `docs/design_philosophy.md` and no others; report each as `exempt: <tell> — <brief quote>` — an unrecorded violation is never exempt. Zero tolerance on em-dash and View-based fake product UI. List every violation as `file:line`, fix, re-sweep.""",
        "contrast_body": """\
  - For every text/icon color vs its computed background, verify WCAG ratio: body text needs ≥ 4.5:1; large text (≥24pt / ≥18pt bold), icons, and focus indicators need ≥ 3:1.
  - Fail on any of: **button label ≈ button fill** (the black-on-black bug — label colour within ~5% lightness of the fill); an accent-filled surface carrying text without a verified accent-ink colour; any **dark surface** (lightness < 50%) that did not flip its `<Text>` color (ink-on-ink). Most-missed: text in a card that switched `backgroundColor` but kept the default ink color.
  - List failing pairs as `file:component`, fix, and re-check before proceeding.""",
        "mech_label": " (state & motion)",
        "mechanics_body": """\
  - `TextInput` fields satisfy the state rules from Anti-AI-Slop ("Motion & input mechanics"): constant `borderWidth`, input height == button height, reserved helper/error slot, multi-channel disabled.
  - Reanimated worklets animate only `transform`/`opacity` (no layout props); overshoot springs appear only on gesture-driven interactions, not incidental state changes; no element stacks multiple simultaneous effects.
  - `useReducedMotion()` is respected globally, not just in one component.
  - List violations as `file:line`, fix, and re-sweep.""",
    },
    "desktop-uiux": {
        "lead": """\
- **Script handover (K9 trigger)**: these sweeps stay model-executed contract prose — stated as deterministic grep procedures, not vibes — because `scripts/verify_design_sweeps.py` discovers `*.html` screens only. The day the validator accepts non-HTML prototype trees (a post-ISSUE-064 successor), replace them with validator call sites; the web skill already runs one.
- **Signature Move sweep**: `docs/design_philosophy.md` must contain a Signature Move with numeric/token specificity (not prose-only), implemented as a reusable component/class/CSS-custom-property primitive under `src/components/` or `src/theme/`. Grep `src/screens/*.tsx`: every screen (including the pilots) must reference that reusable primitive at least once. On any failure: list violations, fix, and re-verify.
- **Literal quote verbatim render check** (skip only if Phase 1.5 was explicitly skipped): read `literal_quote:` from `docs/design_philosophy.md` Reference Anchors; grep `src/screens/*.tsx` — the string MUST appear verbatim in at least one screen's string literal (NOT inside a comment, NOT interpolated from a variable). If absent: inject it into the screen named by the anchor's "where it appears" hint and re-grep — never widen the match.
- **AI Tell sweep** (CRITICAL): sweep every `.tsx`/`.css` file in `src/screens/`, `src/components/`, and theme/style files for the banned tells in "Specific AI Tells": em-dash (`—`/`–`) in any string literal, flex `calc()` column math, generic person/brand names, fake-perfect numbers, section-number eyebrows, decorative version labels, `<div>`-based fake product UI, decorative status dots, locale/time strips. Exempt exactly the recorded `Brief overrides:` bullets in `docs/design_philosophy.md` and no others; report each as `exempt: <tell> — <brief quote>` — an unrecorded violation is never exempt. Zero tolerance on em-dash and div-based fake product UI. List every violation as `file:line`, fix, re-sweep. Match CSS patterns whitespace-insensitively (`height:100vh` ≡ `height: 100vh`).""",
        "contrast_body": """\
  - For every `(color, background-color)` pair on a screen, verify the WCAG ratio against its *computed* background: body text needs ≥ 4.5:1; large text (≥24px / ≥18px bold), icons, and focus rings need ≥ 3:1.
  - Fail on any of: **button text ≈ button fill** (text within ~5% lightness of fill — the black-on-black bug); `--color-accent` filling a text-bearing surface without a defined, verified `--color-accent-ink`; any **dark panel** (background lightness < 50%) that did not flip its text colour (ink-on-ink). Most-missed: text in a panel that switched `background` but inherited `color`; muted text on a tinted surface.
  - List failing pairs as `file:selector`, fix, and re-check before proceeding.""",
        "mech_label": " (deterministic — grep `.css`/theme/screens)",
        "mechanics_body": """\
  - Flag and fix: `transition: all` / `transition-all`; bare `1fr` tracks on image-bearing grids (must be `minmax(0, 1fr)`); `font-style: italic` on heading/display selectors; a second `position: sticky; top: 0`; all-caps display with `line-height` < 1.0.
  - Confirm present: `overflow-x: clip` on `html`+`body`; input/select fields satisfy the 8-state rules (constant `border-width`, `outline`-based focus ring, reserved helper slot, multi-channel disabled) from Anti-AI-Slop "CSS mechanics (renderer)".
  - Match patterns **whitespace-insensitively** (normalize spaces first, and ignore matches inside CSS comments): `transition:all` ≡ `transition: all`, `top:0` ≡ `top: 0`, `overflow-x:clip` ≡ `overflow-x: clip`.
  - List violations as `file:line`, fix, and re-sweep.""",
    },
}

_DESIGN_SWEEPS_TEMPLATE = """\
{lead}
- **Contrast sweep** (CRITICAL — catches the failures that ship most):
{contrast_body}
- **Mechanics sweep**{mech_label}:
{mechanics_body}
- **Depreciation triggers**: per tell/rule, two consecutive design runs whose sweep reports zero hits delete that prose line (script-side entries stay — script lines are cheap, prose lines cost context). The whole mechanics block is replaced by a validator call the day `scripts/verify_design_sweeps.py` grows a mechanics sweep; the contrast prose is replaced by a computed-style validator call when one lands."""


def _require_uiux_skill(skill_name: str) -> None:
    if skill_name not in UIUX_SKILLS:
        raise ValueError(
            f"design-philosophy fragments are only defined for {UIUX_SKILLS}; "
            f"got {skill_name!r}"
        )


def design_philosophy_fragment(skill_name: str) -> str:
    """Resolve the {{DESIGN_PHILOSOPHY}} token for a uiux-family skill."""
    _require_uiux_skill(skill_name)
    desktop = skill_name == "desktop-uiux"
    return _INTERVIEW_TEMPLATE.format(
        desktop_question=_DESKTOP_EXTRA_QUESTION if desktop else "",
        response_step=_RESPONSE_STEP[skill_name],
        desktop_derive=_DESKTOP_EXTRA_DERIVE if desktop else "",
    )


def design_philosophy_checkpoint(skill_name: str) -> str:
    """Resolve the {{DESIGN_PHILOSOPHY_CHECKPOINT}} token."""
    _require_uiux_skill(skill_name)
    return _CHECKPOINT_TEMPLATE.format(
        skill=skill_name,
        glyph_extra="/shortcut" if skill_name == "desktop-uiux" else "",
    )


def slop_calibration_fragment(skill_name: str) -> str:
    """Resolve the {{SLOP_CALIBRATION}} token for a uiux-family skill.

    Platform-agnostic by design: the three clusters, the brief-override rule,
    and the self-similarity check apply identically to web / mobile / desktop.
    Platform-specific bans stay inline in each tmpl's NEVER/INSTEAD lists.
    """
    _require_uiux_skill(skill_name)
    return _SLOP_CALIBRATION


def design_extend_mode_fragment(skill_name: str) -> str:
    """Resolve the {{DESIGN_EXTEND_MODE}} token for a uiux-family skill.

    One method, three source maps (SPEC-054). The mode contract, the
    provenance-transcription rules, and the downstream overrides are identical
    across platforms; only the detection globs and the source map vary.
    """
    _require_uiux_skill(skill_name)
    return _EXTEND_MODE_TEMPLATE.format(**_EXTEND_MODE_PLATFORM[skill_name])


def pilot_gate_fragment(skill_name: str) -> str:
    """Resolve the {{PILOT_GATE}} token for a uiux-family skill.

    SPEC-060 K1: the 4-substep pilot-gate protocol (neutral observation →
    separate-context critique → specificity check → auto-correction hard cap
    N=3) with degraded mode that never silently skips. Extraction changes
    location, zero behavior — only the render inputs, artifact paths, step
    labels and patch-layer step numbers vary per platform.
    """
    _require_uiux_skill(skill_name)
    return _PILOT_GATE_TEMPLATE.format(**_PILOT_GATE_PLATFORM[skill_name])


def ai_tells_fragment(skill_name: str) -> str:
    """Resolve the {{AI_TELLS}} token for a uiux-family skill.

    SPEC-060 K3: one canonical Specific-AI-Tells list; platform deltas
    (container element, visibility scope, platform mechanics tail) are
    injected per skill. The per-tell depreciation trigger lives in the
    {{DESIGN_SWEEPS}} block that executes the sweep.
    """
    _require_uiux_skill(skill_name)
    return _AI_TELLS_TEMPLATE.format(**_AI_TELLS_PLATFORM[skill_name])


def design_sweeps_fragment(skill_name: str) -> str:
    """Resolve the {{DESIGN_SWEEPS}} token for a uiux-family skill.

    SPEC-060 sweep wiring: on web the deterministic literal-quote /
    signature-move / ai-tell sweeps are one `scripts/verify_design_sweeps.py
    all --class` call site; mobile/desktop keep contract-shaped prose sweeps
    carrying the K9 handover trigger (the day the validator accepts non-HTML
    prototype trees, the prose sweeps become validator calls too). Contrast
    (K6) and mechanics (K4/K5) sweeps carry their own named triggers.
    """
    _require_uiux_skill(skill_name)
    return _DESIGN_SWEEPS_TEMPLATE.format(**_DESIGN_SWEEPS_PLATFORM[skill_name])


# ---------------------------------------------------------------------------
# Agent-side canonical chunks (drift guard)
# ---------------------------------------------------------------------------

# Each chunk must appear verbatim (whitespace-normalized containment) in all
# three UIUX_AGENT_FILES. Chunks end where intentional platform-specific text
# begins (e.g. the Constraints tail, the platform design lens, the WebSearch
# domain phrase, the token-location tail) — those deltas stay inline in the
# agent files and are NOT guarded.
AGENT_DESIGN_FRAGMENTS: dict[str, str] = {
    "design_thinking_core": """\
## Design Thinking (CRITICAL — do this BEFORE any code)

Before writing a single line of code, commit to a BOLD aesthetic direction:

0. **Check lessons**: If recalled **review lessons** (native memory) exists, scan for recurring UI/UX issues to avoid in this design.
1. **Purpose**: What problem does this interface solve? Who uses it?
2. **Tone**: Commit to a distinct direction — brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian, dark/moody, lo-fi/zine, handcrafted/artisanal. Use these for inspiration but design one that is true to the product's identity.""",
    "differentiation": """\
4. **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember?""",
    "intentionality": """\
Bold maximalism and refined minimalism both work — the key is **intentionality, not intensity**.""",
    "interview_direction": """\
### Interview-Driven Direction
The Design Interview answers are HARD CONSTRAINTS, not suggestions:
- Brand Personality metaphor → drives typography weight, spacing density, animation energy
- Emotional Target → drives color temperature, whitespace ratio, transition speed
- Anti-Reference → explicit exclusion list checked against every design decision
- Aspiration Reference → research and extract 3-5 concrete visual cues""",
    # Prefix chunk: desktop appends ", Desktop Identity from product type."
    # to the first bullet (intentional platform delta).
    "interview_skip": """\
**If the user skips the interview entirely:**
- Auto-derive constraints from PRD: infer Brand Personality from user personas, Emotional Target from core value proposition, Anti-Reference from competitor analysis""",
    "interview_skip_tail": """\
- Present derivations for user confirmation before proceeding.
- Treat auto-derived values as soft constraints (open to deviation) vs user-provided values which are hard constraints.""",
    # Step 3 ("[product domain] ... design trends") is an intentional
    # platform delta and stays inline.
    "reference_research": """\
### Reference Research Protocol
Before committing to an aesthetic direction:
1. WebSearch the aspiration reference's UI/design
2. WebSearch the anti-reference to understand patterns to avoid""",
    "reference_research_synthesis": """\
4. Synthesize into concrete Adopt/Avoid lists in design_philosophy.md""",
    "self_review_alignment": """\
## Self-Review (Mandatory before finalizing deliverables)

- **Design philosophy alignment**: Does every screen, component, and animation reflect the named aesthetic direction? Check 3 random components against the philosophy.""",
    # Prefix chunk: the token location tail is platform-specific
    # (web: "CSS custom properties?", mobile/desktop: "`src/theme/`?").
    "self_review_token_rule": """\
- **Token compliance**: Are there any hardcoded colors, font sizes, or spacing values outside of""",
    # self_review_confidence deleted in ISSUE-060 (SPEC-060 D5, the ISSUE-059
    # debt): SPEC-010 recorded self-grading sycophancy as a defect — the
    # load-bearing gates are separate-context auditors and checkpoint scripts.
    # Same text the skills get via {{SLOP_CALIBRATION}}. Split into three
    # chunks so a drift report names which block moved.
    "slop_calibration_clusters": _SLOP_CALIBRATION.split("\n\n")[0],
    "slop_calibration_brief_wins": _SLOP_CALIBRATION.split("\n\n")[1],
    "slop_calibration_self_similarity": _SLOP_CALIBRATION.split("\n\n")[2],
    "guidelines_read_first": """\
- Always read the PRD and existing UX spec first before generating anything.""",
    "guidelines_realistic_content": """\
- Realistic placeholder content — domain-appropriate text, not lorem ipsum.
- State assumptions clearly when the PRD is ambiguous — do NOT invent requirements.""",
}


def _normalize(text: str) -> str:
    return " ".join(text.split())


def find_out_of_sync_fragments(
    agent_text: str, fragments: dict[str, str] | None = None
) -> list[str]:
    """Return the names of canonical chunks NOT contained in agent_text.

    Comparison is whitespace-normalized (line reflow never trips the guard;
    any content change does).
    """
    if fragments is None:
        fragments = AGENT_DESIGN_FRAGMENTS
    haystack = _normalize(agent_text)
    return [
        name
        for name, frag in fragments.items()
        if _normalize(frag) not in haystack
    ]
