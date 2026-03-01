---
name: uiux
description: kickoff 산출물 기반으로 디자인 철학을 수립하고, 디자인 시스템/와이어프레임/HTML 프로토타입을 생성합니다. 권장 흐름: /prd → /kickoff → /uiux
argument-hint: [PRD.md 경로 (선택)]
disable-model-invocation: false
allowed-tools: Task, Read, Glob, Grep, Write, Edit, Bash
---

## Prerequisites
- `/kickoff`이 먼저 실행되어 아래 파일들이 존재해야 합니다:
  - `docs/ux_spec.md` (핵심 입력 — IA, 플로우, 화면 목록)
  - `docs/requirements.md` (기능/비기능 요구사항)
  - `docs/architecture.md` (기술 스택 참조)
- PRD 파일은 보조 참고용입니다. kickoff 산출물이 없으면 사용자에게 `/kickoff` 실행을 안내합니다.

## Algorithm

### Phase 1 — Context Gathering
1) Read kickoff outputs (필수):
   - `docs/ux_spec.md` — 화면 목록, IA, 플로우 추출
   - `docs/requirements.md` — 기능 요구사항에서 UI 요소 식별
   - `docs/architecture.md` — 기술 스택, API 엔드포인트 확인
2) Read PRD (`$ARGUMENTS` or `PRD.md`) as supplementary context.
3) If `docs/ux_spec.md` does not exist:
   - Stop and tell the user: "kickoff 산출물이 없습니다. 먼저 `/kickoff PRD.md`를 실행해주세요."
   - Exception: if the user explicitly wants to skip kickoff, proceed with PRD only (warn about limited context).
4) Scan the project for existing UI code:
   - Glob for `**/*.html`, `**/*.css`, `**/*.tsx`, `**/*.jsx`, `**/*.vue`, `**/*.svelte`
   - If found, read key files to understand current design patterns and tech stack.

### Phase 2 — Design Philosophy (CRITICAL — before any code)
5) Analyze the product's identity from PRD and UX spec:
   - Who are the users? What's the emotional tone?
   - What category does this product belong to? (SaaS, consumer, creative tool, enterprise, etc.)
   - Are there competitor/reference products mentioned?
6) Commit to a BOLD aesthetic direction. Choose one and execute with precision:
   - Brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined,
     playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel,
     industrial/utilitarian, dark/moody, lo-fi/zine, handcrafted/artisanal.
   - Or create a hybrid direction true to the product's identity.
7) Generate `docs/design_philosophy.md`:
   - Named aesthetic (2-3 words, e.g., "Brutalist Joy", "Chromatic Silence")
   - 2-3 paragraphs: how the philosophy manifests through space/form, color/material, scale/rhythm, composition
   - What makes this design UNFORGETTABLE — the one thing someone will remember
8) Present the design philosophy to the user and ask for approval before proceeding.
   - If rejected, iterate on the direction.

### Phase 3 — Design System
9) Generate `docs/design_system.md` reflecting the chosen aesthetic:
   - **Color palette**: Hex values. Dominant colors with sharp accents — NOT timid, evenly-distributed palettes. Choose a direction: bold/saturated, moody/restrained, or high-contrast/minimal.
     - Ensure no semantic color (warning, error, etc.) shares the exact same hex value as a user-selectable/decorative color
   - **Typography**: Specific Google Fonts choices. Distinctive display font + refined body font. Extreme contrast in scale (3x+ ratio between heading and body). NEVER default to Inter, Roboto, Arial, Open Sans.
   - **Spacing**: 4px-based scale (4, 8, 12, 16, 24, 32, 48, 64)
   - **Components**: Buttons, inputs, cards, modals, navigation, tables, badges, toasts — each with variants and states (default, hover, active, focus, disabled, loading)
     - **ALL button variants** (primary, secondary, destructive, ghost) MUST have full CSS with ALL states — not just the primary variant in CSS and others in prose
     - **App-specific composite components** (e.g., FAB, list items, progress rings, pickers) MUST also be defined with full CSS — not just generic UI primitives
   - **Motion tokens**: Transition durations, easing curves, animation-delay stagger values
     - Performance rules: only `transform` and `opacity` are GPU-composited. Do NOT list `box-shadow`.
   - All values expressed as CSS custom properties
10) Ask the user if the design system direction looks right before proceeding.

### Phase 4 — Wireframes & Interaction Spec
11) Generate `docs/wireframes.md`:
    - Screen inventory (one section per screen from UX spec)
    - Layout description with component placement
    - Spatial composition: asymmetry, overlap, grid-breaking elements, negative space strategy
    - Content hierarchy and information architecture
    - Responsive behavior per breakpoint (mobile 375px / tablet 768px / desktop 1280px)
    - **PRD feature cross-check**: After writing, verify EVERY PRD feature (including P2) has a corresponding wireframe element. P2 features should show placement with a "P2 — deferred" note.
12) Generate `docs/interactions.md`:
    - User flow diagrams (text-based state machines) — each with Trigger, Preconditions, Steps, Success/Error/Edge Cases
    - Screen transition map with animation descriptions
    - **Shared Element Transitions**: document candidates or explicitly state "none planned" with rationale
    - Loading / empty / error states per screen
    - Form validation rules
    - **Drag & Drop**: if PRD mentions reordering/dragging, include full spec (drag start, drag over, drop, cancel). If not applicable, state "N/A"
    - High-impact motion moments: page-load stagger reveals, scroll-triggered effects, hover surprises
    - **Template completeness check**: verify every section from the template is present. If not applicable, add "N/A — [reason]"

### Phase 4.5 — Copy Guide
12.5) Run the **copywriter** agent to generate `docs/copy_guide.md`:
    - Input: `docs/ux_spec.md`, `docs/design_philosophy.md`, `docs/wireframes.md`, `docs/interactions.md`, PRD
    - Output: Voice & tone definition, copy inventory per screen (labels, placeholders, empty/error/success states, confirmations, toasts), patterns, glossary
    - Include FULL CONTENT of input documents in the subagent prompt.
    - The copy guide must align with the design philosophy's tone (e.g., "Ink & Paper" → restrained, precise language).
    - This step MUST complete before Phase 5 so the prototype uses real copy, not placeholder text.

### Phase 5 — HTML/CSS Prototype
13) Ensure `prototype/` and `prototype/screens/` directories exist.
14) Generate `prototype/styles.css`:
    - CSS custom properties from design system (colors, spacing, typography, radii, shadows, motion tokens)
    - CSS reset / normalize
    - Utility classes (flex, grid, spacing, text alignment)
    - Component styles matching design system — every component with all states
    - Responsive breakpoint media queries (mobile-first)
    - Background & depth effects: gradient meshes, noise textures, layered transparencies, grain overlays (as appropriate for the aesthetic)
    - Dark mode via `prefers-color-scheme` (if appropriate for the aesthetic)
    - CSS keyframe animations for page-load reveals, stagger effects, hover transitions
15) Generate screen HTML files in `prototype/screens/`:
    - One HTML file per screen identified in wireframes
    - Semantic HTML5 structure (`<nav>`, `<main>`, `<section>`, `<article>`, `<aside>`, `<header>`, `<footer>`)
    - Google Fonts loaded via `<link>` tag (single CDN exception — fonts only)
    - `<meta name="viewport">` for responsiveness
    - Linked to `../styles.css`
    - Responsive layout reflecting wireframe spatial composition
    - Use actual copy from `docs/copy_guide.md` — labels, placeholders, empty states, error messages. NOT placeholder text.
    - All states represented AND togglable via a visible state-switcher toolbar:
      - Add a small floating toolbar at the bottom of each screen with buttons: "Default", "Loading", "Empty", "Error"
      - Clicking each button shows the corresponding state — reviewers should NOT need the browser console
    - Accessibility:
      - NEVER use `outline: none` on `:focus` without `:focus-visible` fallback
      - All `role="button"` elements MUST have `keydown` handlers for Enter/Space
      - All `role="radiogroup"` elements MUST support arrow-key navigation
      - Placeholder text contrast >= 3:1
      - `alt` text, form `<label>`s, ARIA attributes, color contrast >= 4.5:1, keyboard navigable
16) Generate `prototype/index.html`:
    - Navigation hub linking to all screen prototypes
    - Product name, design philosophy name, screen list with descriptions
    - Styled consistently with the design system — this IS a designed page, not a plain list

### Phase 5.5 — Verification (REQUIRED before presenting to user)
17) **Component cross-check**:
    - Every component referenced in `wireframes.md` MUST have a definition in `design_system.md`
    - List any gaps and add missing component definitions before proceeding
18) **PRD feature cross-check**:
    - Every feature in the PRD (F1, F2, ... including P2) MUST appear in wireframes and/or interactions
    - List any gaps and add missing features (P2 features as "deferred" notes)
19) **Token compliance check**:
    - CSS custom properties used in `styles.css` MUST match values in `design_system.md`
    - Check for hardcoded hex colors, font sizes, or spacing in `styles.css` that should use `var(--token)`
20) **Cross-document consistency check**:
    - Color token references in wireframes/interactions use CSS custom property names (not prose descriptions)
    - Hover/interaction states in interactions.md match component states in design_system.md
    - Container widths and breakpoints are consistent across all docs and CSS
21) **Accessibility check**:
    - No `outline: none` on `:focus` without `:focus-visible` coverage
    - Placeholder text contrast >= 3:1
    - All interactive elements have keyboard handlers
22) **State demo check**:
    - Every screen has a visible state-switcher toolbar
    - Loading, empty, and error states are implemented and togglable

### Phase 6 — Review & Iterate
23) Present deliverables summary to the user:
    - List all generated files with brief descriptions
    - Highlight the design philosophy and key aesthetic choices
    - Report verification results from Phase 5.5 (component coverage, PRD coverage, token compliance)
    - Suggest: `open prototype/index.html` to view in browser
    - Ask for feedback on any screen
24) Iterate based on user feedback:
    - Modify specific screens, adjust design system, add missing states
    - Each iteration updates both docs and prototype files consistently
    - If aesthetic direction needs major change, go back to Phase 2

## Shared Registry Files
- None. This skill produces standalone deliverables — no `issues.md` or `STATUS.md` updates.
- `/kickoff`이 이미 이슈를 생성했으므로, UI/UX 관련 추가 이슈가 필요하면 수동으로 `issues.md`에 추가하거나 `/kickoff`을 다시 실행.

## Error Handling
- If `docs/ux_spec.md` not found: stop and suggest running `/kickoff` first (unless user explicitly opts to skip).
- If PRD file not found: stop immediately, report missing path.
- If `docs/` cannot be created: stop and report filesystem error.
- If existing UI code uses a framework (React, Vue, etc.): note the framework in `docs/design_system.md` for future `/implement` reference. Prototypes are still pure HTML/CSS for portability.
- If PRD is too vague for UI design (no user stories, no features): ask the user targeted questions about screens and user flows before proceeding.

## Rollback
- This skill is additive (writes new files/directories). No destructive rollback needed.
- Re-running `/uiux` overwrites all outputs — safe to retry.
- Prototype directory (`prototype/`) can be safely deleted if not needed.

## Anti-AI-Slop Rules (CRITICAL)

These rules prevent Claude from converging on generic, forgettable defaults:

**NEVER:**
- Inter, Roboto, Arial, Open Sans as primary display font
- Purple gradients on white backgrounds
- Predictable centered layouts with uniform rounded corners
- Cookie-cutter component patterns without context-specific character
- Solid white/gray backgrounds without depth or texture
- Evenly-distributed, timid color palettes
- Space Grotesk as a "safe creative" choice

**INSTEAD:**
- Distinctive, characterful fonts that match the product's personality
- Cohesive color palette with dominant colors and sharp accents
- Unexpected spatial composition — asymmetry, overlap, diagonal flow, grid-breaking
- Atmosphere and depth — gradients, noise, textures, layered transparencies, dramatic shadows
- High-impact motion moments over scattered micro-interactions
- Implementation complexity matched to aesthetic vision

## Guidelines
- **Self-contained prototypes**: Opens via `file://` — no build tools, no npm, no frameworks.
- **One CDN exception**: Google Fonts `<link>` tags are allowed for typography.
- **Accessibility first**: WCAG 2.1 AA — contrast ratios, keyboard navigation, screen reader support.
- **Mobile-first**: Design for 375px first, then scale up.
- **Realistic content**: Domain-appropriate placeholder text, not lorem ipsum.
- **Intentional design**: Every choice (font, color, spacing, animation) must serve the design philosophy. No defaults.
