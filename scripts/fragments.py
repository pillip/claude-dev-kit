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
        glyph_extra="/shortcut" if skill_name == "desktop-uiux" else ""
    )


def slop_calibration_fragment(skill_name: str) -> str:
    """Resolve the {{SLOP_CALIBRATION}} token for a uiux-family skill.

    Platform-agnostic by design: the three clusters, the brief-override rule,
    and the self-similarity check apply identically to web / mobile / desktop.
    Platform-specific bans stay inline in each tmpl's NEVER/INSTEAD lists.
    """
    _require_uiux_skill(skill_name)
    return _SLOP_CALIBRATION


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
    "self_review_confidence": """\
- **Confidence rating**: Rate your confidence (High/Medium/Low) and explain why.
  - If Low: re-check prototype and fix issues before finalizing.
  - If Medium: flag specific concerns in deliverable docs.
  - If High: proceed to finalize.""",
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
