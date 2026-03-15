---
name: desktop-uiux
description: kickoff 산출물 기반으로 데스크톱 디자인 철학을 수립하고, 데스크톱 디자인 시스템/와이어프레임/Electron 프로토타입을 생성합니다. 권장 흐름: /prd → /kickoff → /desktop-uiux
argument-hint: [PRD.md 경로 (선택)]
disable-model-invocation: false
allowed-tools: Task, Read, Glob, Grep, Write, Edit, Bash, WebSearch, WebFetch
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
2) Read PRD (`$ARGUMENTS` or `PRD.md`) as supplementary context. If `docs/prd_digest.md` exists, read it for quick PRD summary.
3) If `docs/ux_spec.md` does not exist:
   - Stop and tell the user: "kickoff 산출물이 없습니다. 먼저 `/kickoff PRD.md`를 실행해주세요."
   - Exception: if the user explicitly wants to skip kickoff, proceed with PRD only (warn about limited context).
4) Check for existing shared assets:
   - `docs/design_philosophy.md` — 웹 `/uiux`에서 이미 생성되었는지 확인
   - `docs/copy_guide.md` — 웹 `/uiux`에서 이미 생성되었는지 확인
5) Scan the project for existing desktop code:
   - Glob for `**/electron/**`, `**/main.ts`, `**/preload.ts`, `**/electron-builder.*`, `**/forge.config.*`, `**/*.tsx`, `**/*.ts`
   - If found, read key files to understand current patterns, window management, and tech stack.

### Phase 1.5 — Design Interview (조건부)
5.5) Check if `docs/design_philosophy.md` already exists AND contains a "Decision Matrix" section:
   - **If exists with Decision Matrix**: Skip interview — reuse web decisions. Present to user for confirmation.
   - **If not exists or missing Decision Matrix**: Run the Design Interview below.

   Ask the user the following questions to anchor the design direction.
   These answers become binding constraints for Phase 2.
   Present all questions at once (not one-by-one) and wait for answers.
   Also tell the user: "지금 답하기 어려우면 '스킵'이라고 해주세요. 인터뷰 전체를 건너뛸 수도 있습니다."

   a) **Brand Personality**: "이 제품을 사람에 비유하면 어떤 사람인가요?"
      (예: 고급 호텔 컨시어지, 동네 단골 카페 바리스타, 엄격한 수술실 간호사, 장난기 많은 친구)

   b) **Emotional Target**: "사용자가 첫 화면을 봤을 때 느꼈으면 하는 감정 1가지는?"
      (예: 신뢰감, 호기심, 안도감, 흥분, 차분함)

   c) **Anti-Reference**: "절대 이렇게 되면 안 되는 경쟁 제품이나 디자인은?"
      (피하고 싶은 느낌이나 구체적 제품명)

   d) **Aspiration Reference**: "디자인적으로 참고하고 싶은 제품이나 브랜드가 있나요? (같은 도메인이 아니어도 됨)"
      (예: Stripe의 깔끔함, 닌텐도의 장난기, Aesop의 고급스러움)

   e) **Desktop Identity**: "이 앱이 OS의 일부처럼 느껴져야 하나요, 아니면 독자적 세계관을 가져야 하나요?"
      (예: macOS 네이티브 앱처럼 자연스러운 통합 vs Figma/Notion처럼 독자적 UI 세계관)

5.6) Handle user response:

   **Case A — User answers (partially or fully)**:
   Record answers in memory — these become HARD CONSTRAINTS for Phase 2.
   If the user skips individual questions, note them as "unconstrained" but still avoid generic defaults.

   **Case B — User skips the entire interview** (says "스킵", "넘어가", "pass", etc.):
   - Do NOT silently proceed with generic defaults.
   - Instead, the agent MUST auto-derive initial constraints from the PRD/UX spec:
     a) Brand Personality → infer from target user personas and product category in PRD
     b) Emotional Target → infer from the product's core value proposition
     c) Anti-Reference → infer from competitor analysis in PRD (if any), otherwise mark "unconstrained"
     d) Aspiration Reference → mark "unconstrained"
     e) Desktop Identity → infer from product type (productivity tool → native feel, creative tool → branded)
   - Present the auto-derived constraints to the user: "인터뷰를 스킵하셨으므로 PRD에서 다음과 같이 추론했습니다: [constraints]. 이대로 진행할까요?"
   - If approved, proceed with these as soft constraints (not hard).
   - If rejected, re-offer the interview questions or accept corrections.

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Verify Phase 1 outputs: `docs/ux_spec.md` exists, PRD was read, interview answers (or auto-derived/reused constraints) are recorded.
> If any required input is missing: STOP and report to user.

### Phase 2 — Design Philosophy (조건부 — CRITICAL before any code)
6) Check if `docs/design_philosophy.md` already exists:
   - **If exists**: Read the file, present it to the user, and ask: "웹에서 생성된 디자인 철학이 있습니다. 데스크톱에도 동일하게 적용할까요, 아니면 데스크톱에 맞게 수정할까요?"
     - If approved: reuse as-is, proceed to Phase 3.
     - If modification requested: create a desktop-adapted version, updating the philosophy while maintaining brand consistency.
   - **If not exists**: Generate from scratch (same process as web `/uiux`):
7) Analyze the product's identity from PRD and UX spec:
   - Who are the users? What's the emotional tone?
   - What category does this product belong to?
   - Are there competitor/reference apps mentioned?
7.5) **Reference Research** (uses WebSearch):
   - Search for the aspiration reference's design (if provided): "[brand/product] UI design"
   - Search for the anti-reference to understand what to avoid: "[anti-reference] UI criticism"
   - Search for the product domain's design trends: "[domain] desktop app design 2025/2026"
   - Synthesize 3-5 concrete design cues to adopt and 3-5 to explicitly avoid
   - Document these in the design philosophy as "Reference Anchors"
8) Commit to a BOLD aesthetic direction with desktop lens:
   - Apply the desktop design lens: 정보 밀도, 키보드 워크플로우, 멀티 윈도우 경험
9) Generate `docs/design_philosophy.md`:
   - Named aesthetic (2-3 words)
   - 2-3 paragraphs: how the philosophy manifests through space/form, color/material, scale/rhythm, composition
   - What makes this design UNFORGETTABLE
10) Present the design philosophy to the user and ask for approval before proceeding.
    - If rejected, iterate on the direction.

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Verify `docs/design_philosophy.md` exists with Decision Matrix and Reference Anchors populated.
> If missing or incomplete: STOP and fix before proceeding.

### Phase 3 — Desktop Design System
11) Generate `docs/design_system_desktop.md` reflecting the chosen aesthetic:
    - **Color palette**: TypeScript/CSS token objects. Dominant colors with sharp accents. Strong dark mode optimized for long work sessions, reduced eye strain.
    - **Typography**: System fonts (SF Pro/Segoe UI/Ubuntu) or custom. Wider modular scale (1.25 or 1.333 — large screens can afford dramatic jumps). Monospace for code/data views. Minimum 12px allowed (desktop precision).
    - **Spacing**: 4px-based scale (xs:4, sm:8, md:12, lg:16, xl:24, xxl:32, xxxl:48, xxxxl:64) + large-scale tokens for panel gaps, sidebar width, toolbar height
    - **Components**: Desktop-specific — Sidebar, Split Pane, Command Palette, Context Menu, Toast/Notification, Data Table, Tree View, Tab Bar, Toolbar, Status Bar, Dialog/Modal, Breadcrumb, Dropdown Select
      - States: default, hover, active, focus, disabled, loading (hover IS included for desktop!)
      - **MUST include**: Text Input (focus/error/placeholder/character count), Keyboard Shortcut Badge, Resizable Panel, Search/Filter Bar
      - **MUST include**: Data Table patterns (sortable headers, row selection, virtual scrolling, column resize)
      - **MUST include**: Window chrome spec (title bar, traffic lights/window controls, frameless vs custom)
    - **Keyboard shortcuts tokens**: Cmd/Ctrl modifier mapping per platform (`darwin`→Cmd, `win32`/`linux`→Ctrl)
    - **Window chrome**: Title bar customization (frameless or custom titlebar), traffic light / window control integration, draggable regions
    - **Motion tokens**: Duration (micro 60-100ms to large 300-500ms, max 700ms), easing curves, transition types. Faster and more restrained than web — desktop is efficiency-first.
      - **GPU-composited only**: All motion tokens MUST target `transform`, `opacity`, or `filter`. NEVER animate layout properties (`width`, `height`, `top`, `left`).
      - **`will-change` budget**: Max 5 concurrent elements with `will-change`. Overuse creates GPU memory pressure. Apply on interaction start, remove on end.
      - **SplitPane resize strategy**: Prefer CSS flexbox/grid `fr` units over JS-driven width changes. If JS-driven, throttle via `requestAnimationFrame`.
    - **Dark/Light mode**: `nativeTheme` integration, system preference detection, manual override
    - **Platform tokens**: `darwin`/`win32`/`linux` keys for platform-specific values (fonts, shortcuts, window chrome, file paths)
    - All values expressed as TypeScript objects AND CSS custom properties
12) Ask the user if the design system direction looks right before proceeding.

### Phase 4 — Wireframes & Interaction Spec
13) Generate `docs/wireframes_desktop.md`:
    - Window layout architecture (single window vs multi-window, sidebar+content+panel structure)
    - Screen inventory with window position and panel assignment
    - Per-screen details: window context, panel layout, resize behavior, layout zones (sidebar/toolbar/content/panel/statusbar), components, states (default/loading/empty/error), keyboard focus order
    - Multi-window configuration: main window, auxiliary windows (settings, inspector, detached panels), window-to-window communication patterns
    - Responsive behavior per window size (min-width, comfortable, max/full-screen)
14) Generate `docs/interactions_desktop.md`:
    - User flows with trigger (click/keyboard shortcut/drag/context menu/system tray), steps with animation, system integration
    - Keyboard shortcut map: complete mapping of all shortcuts, organized by category (file, edit, view, navigation, custom), platform variants (Cmd vs Ctrl)
    - Command Palette flow: activation (Cmd+K), search/filter behavior, action execution, recent items
    - Drag & Drop spec: file system ↔ app (drop zone styling, file type validation, progress feedback), intra-app drag (reorder, move between panels)
    - Context menu spec: right-click menus per context (sidebar item, content area, table row, tab), keyboard activation (Shift+F10 or Menu key)
    - Focus management: tab order, focus trap in modals/dialogs, focus restoration on close, skip navigation
    - Window interactions: resize behavior (min/max constraints, content reflow), snap zones, multi-monitor support
    - System tray integration: icon, tooltip, context menu, notification badge
    - State management: loading (skeleton/spinner), empty, error (with retry), permission prompts
    - App launch choreography (cold start): splash window (lightweight BrowserWindow) → main window create → skeleton UI → data hydration → interactive. Target: under 3 seconds to interactive.
    - Background task lifecycle: system tray persistence, graceful shutdown, auto-update flow
    - Accessibility: screen reader support, keyboard-only navigation, high contrast mode, reduced motion

### Phase 4.5 — Copy Guide (조건부)
15) Check if `docs/copy_guide.md` already exists:
    - **If exists**: Read the file. Check if it already has a `## Desktop Adaptations` section.
      - If no desktop section: append a `## Desktop Adaptations` section covering:
        - Menu bar labels (File, Edit, View, Window, Help — platform conventions)
        - Keyboard shortcut hint text (tooltip format, menu item format)
        - System notification copy (title, body, action buttons — OS notification constraints)
        - Dialog copy (confirmation dialogs, destructive action warnings, save/discard patterns)
        - Status bar messages (connection status, sync status, background task progress)
        - Context menu labels (concise, action-oriented, with shortcut hints)
        - Command Palette action labels (verb + noun pattern)
      - If desktop section exists: review and update if needed.
    - **If not exists**: Run the **copywriter** agent to generate `docs/copy_guide.md`:
      - Input: `docs/ux_spec.md`, `docs/design_philosophy.md`, `docs/wireframes_desktop.md`, `docs/interactions_desktop.md`, PRD
      - Output: Voice & tone definition, copy inventory per screen, patterns, glossary, desktop adaptations section
      - Include FULL CONTENT of input documents in the subagent prompt.
      - This step MUST complete before Phase 5 so the prototype uses real copy.
16-a) **Accessibility labels (REQUIRED)**: Ensure `copy_guide.md` includes `aria-label` for EVERY interactive element (buttons, inputs, menus, panels, dialogs). Also include keyboard shortcut announcements for screen readers.

> **CHECKPOINT — MANDATORY — NEVER SKIP**
> Verify `docs/design_system_desktop.md`, `docs/wireframes_desktop.md`, `docs/interactions_desktop.md`, and `docs/copy_guide.md` all exist.
> Cross-check: every component in wireframes has a definition in design_system_desktop.md.
> If any output is missing: STOP and generate it before proceeding.

### Phase 5 — Electron Prototype
16) Create the `prototype-desktop/` directory structure:
    ```
    prototype-desktop/
      package.json
      tsconfig.json
      .gitignore
      electron/
        main.ts        (메인 프로세스)
        preload.ts     (preload 스크립트)
      src/
        types/
          index.ts (shared types)
        theme/
          tokens.ts
          colors.ts
          spacing.ts
          typography.ts
        components/
          Sidebar.tsx
          CommandPalette.tsx
          SplitPane.tsx
          ContextMenu.tsx
          DataTable.tsx
          ... (as needed per design system)
        screens/
          ... (one .tsx per screen from wireframes)
        App.tsx
        main.tsx       (renderer entry)
      index.html
    ```
17) Generate `prototype-desktop/package.json`:
    - **Required dependencies** (MUST include all of these):
      - `electron` — runtime
      - `react`, `react-dom` — framework
      - `typescript` — language
      - `vite`, `@vitejs/plugin-react` — bundler
      - `electron-builder` or `@electron-forge/cli` — packaging
    - **Required dev dependencies**:
      - `@types/react`, `@types/react-dom` — type definitions
      - `electron-vite` or `vite-plugin-electron` — Electron + Vite integration
    - Scripts: `dev` (development with hot reload), `build` (production build), `preview` (preview build)
    - **Bundle optimization**: Configure Vite to externalize Electron built-in modules (`electron`, `path`, `fs`). Use `build.rollupOptions.output.manualChunks` to split vendor libraries (react, react-dom) from app code.
    - After generating package.json, run: `cd prototype-desktop && npm install` to install dependencies
17-a) Generate `prototype-desktop/tsconfig.json`:
    - Strict mode enabled
    - JSX: react-jsx
    - Module resolution: bundler
    - Path aliases for `@/` → `src/`
17-b) Generate `prototype-desktop/.gitignore`:
    - Standard Electron gitignore: node_modules, dist, dist-electron, out, .vite, *.log
17-c) Generate `prototype-desktop/electron/main.ts`:
    - BrowserWindow creation with appropriate defaults (width, height, webPreferences)
    - Preload script path configuration
    - App lifecycle (ready, window-all-closed, activate)
    - Menu bar setup (platform-aware: darwin vs win32/linux)
    - Optional: system tray setup if specified in wireframes
    - **Cold start optimization**: Show a lightweight splash BrowserWindow immediately on `ready`, then create the main window in background. Swap when renderer is ready (`did-finish-load`).
    - **Main process hygiene**: NEVER run heavy I/O (file read, DB query, network) on the main process event loop. Offload to `utilityProcess` (Electron 22+) or Node worker_threads.
    - `backgroundThrottling: false` only for windows that need real-time updates; leave default (`true`) for auxiliary windows to save resources.
17-d) Generate `prototype-desktop/electron/preload.ts`:
    - contextBridge.exposeInMainWorld for IPC
    - Type-safe API exposure
    - **Preload weight**: Keep preload script minimal — only expose IPC bridge functions. Heavy logic belongs in the renderer bundle.
17-e) Generate `prototype-desktop/index.html`:
    - Minimal HTML shell for Vite + React entry
18) Generate `prototype-desktop/src/theme/`:
    - `colors.ts` — color palette from design system, dark/light mode tokens
    - `spacing.ts` — spacing scale + large-scale tokens (panel gaps, sidebar width)
    - `typography.ts` — font families, modular scale, platform-specific fonts
    - `tokens.ts` — re-exports all theme tokens + shadows, radii, motion config, keyboard shortcut tokens
19) Generate `prototype-desktop/src/components/`:
    - Reusable components matching the design system
    - Each component uses theme tokens, supports all 6 states (default, hover, active, focus, disabled, loading)
    - Keyboard navigation support on every interactive component
    - Context menu integration where specified
20) Generate `prototype-desktop/src/screens/`:
    - One .tsx file per screen from wireframes
    - Uses design system components and theme tokens
    - Implements all states: default, loading (skeleton), empty, error
    - Uses actual copy from `docs/copy_guide.md`
    - Keyboard shortcut bindings per screen
    - **Code splitting**: Secondary screens and heavy panels (settings, inspector) MUST use `React.lazy` + `Suspense` to avoid loading everything upfront
21) Generate `prototype-desktop/src/App.tsx`:
    - Router setup (react-router or custom)
    - Theme provider (dark/light mode with system preference detection)
    - Keyboard shortcut global handler
    - Window chrome / custom title bar integration
    - **IPC pattern**: All renderer→main IPC calls go through a single typed API layer (from preload). Batch rapid-fire calls (e.g., window resize events) with debounce/throttle. NEVER send large objects over IPC — use references or chunked transfer.
    - **Memory cleanup**: Register cleanup in `useEffect` returns for event listeners, IPC subscriptions, and timers. Use `AbortController` for fetch calls.
22) Generate `prototype-desktop/src/main.tsx`:
    - React DOM entry point
    - Root render with StrictMode

### Phase 5.5 — Prototype Verification (REQUIRED before presenting to user)
23) **Electron project setup check**:
    - `package.json` has correct scripts (`dev`, `build`)
    - `electron/main.ts` exists with proper BrowserWindow setup
    - `electron/preload.ts` exists with contextBridge
    - `index.html` exists as renderer entry
    - `tsconfig.json` exists with strict mode
    - `.gitignore` exists
24) **Token compliance check**:
    - Scan all files in `src/screens/` and `src/components/` for hardcoded style values
    - Every color, spacing, font size, border radius, and shadow MUST use imports from `src/theme/`
    - Fix any hardcoded values found before proceeding
25) **Screen coverage check**:
    - Count screens defined in `docs/wireframes_desktop.md`
    - Count .tsx files in `src/screens/`
    - Every wireframe screen (except explicitly P2+ deferred screens) MUST have a corresponding screen file
26) **State coverage check**:
    - Every screen MUST implement at least default + one additional state (loading, empty, or error as applicable)
    - Empty state MUST use copy from `docs/copy_guide.md`, not placeholder text
27) **Keyboard navigation check**:
    - Every interactive component MUST be keyboard-accessible (tab focus, enter/space activation)
    - Command Palette (Cmd+K / Ctrl+K) MUST be implemented if specified in design system
    - At least 5 keyboard shortcuts from `docs/interactions_desktop.md` MUST be functional
28) **Performance check**:
    - List/table item components MUST use `React.memo`
    - Event handlers passed to memoized children MUST use `useCallback`
    - Large data sets MUST use virtualization (e.g., react-window or tanstack-virtual)
    - Secondary screens/panels MUST use `React.lazy` + `Suspense` for code splitting
    - Animations MUST only use GPU-composited properties (`transform`, `opacity`, `filter`) — never animate `width`, `height`, `top`, `left`
    - `will-change` MUST NOT be applied to more than 5 elements simultaneously (excessive use increases memory)
    - CSS `contain: layout style paint` SHOULD be applied to independently-updating panels (sidebar, content, detail)
    - SplitPane resize MUST use `requestAnimationFrame` throttle or CSS-based resize (flexbox/grid) — never unthrottled mousemove
29) **IPC & memory check**:
    - Main process MUST NOT contain synchronous file I/O or heavy computation
    - Preload script MUST be lightweight — only IPC bridge, no business logic
    - Rapid IPC calls (resize, scroll, drag) MUST be debounced/throttled
    - All `useEffect` hooks MUST return cleanup functions for event listeners, IPC subscriptions, and timers
    - Multi-window: auxiliary BrowserWindows MUST set `backgroundThrottling: true` (default) unless real-time updates are required
30) **Bundle size check**:
    - Renderer bundle SHOULD be under 500KB gzip (excluding node_modules externalized by Vite)
    - Vendor chunk (react, react-dom) MUST be split from app code via `manualChunks`
    - Electron built-in modules (`electron`, `path`, `fs`) MUST be externalized, not bundled

### Phase 6 — Review & Iterate
31) Present deliverables summary to the user:
    - List all generated files with brief descriptions
    - Highlight the design philosophy and key aesthetic choices
    - Report verification results from Phase 5.5 (token compliance, screen coverage, state coverage, keyboard navigation)
    - Suggest running the development server:
      ```bash
      cd prototype-desktop
      npm run dev
      ```
    - Note: dependencies are already installed during Phase 5 (`npm install`)
    - Ask for feedback on any screen
32) Iterate based on user feedback:
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
- If existing desktop code uses a different framework (Tauri, CEF, native): adapt the prototype to match that framework instead of defaulting to Electron. Note the framework in `docs/design_system_desktop.md`.
- If PRD is too vague for desktop UI design (no user stories, no features): ask the user targeted questions about screens and user flows before proceeding.

## Rollback
- This skill is additive (writes new files/directories). No destructive rollback needed.
- Re-running `/desktop-uiux` overwrites all outputs — safe to retry.
- Prototype directory (`prototype-desktop/`) can be safely deleted if not needed.

## Anti-AI-Slop Rules (CRITICAL)

These rules prevent Claude from converging on generic, forgettable desktop defaults:

**NEVER:**
- A web app wrapped in Electron with browser-like UI (address bar feel, no native integration)
- Touch-target-sized buttons on desktop (48px buttons waste screen real estate)
- Mobile hamburger menu on desktop (you have a full menu bar and sidebar)
- Pro tools without keyboard shortcuts (desktop users expect keyboard efficiency)
- Ignoring the system menu bar with only a custom in-app menu
- Single-window-only design when the content naturally benefits from multi-window
- Ignoring OS theme preferences (light/dark mode, accent color)
- Generic placeholder illustrations for empty states
- Electron apps that feel like a website in a frame

**INSTEAD:**
- Native window controls integrated with custom title bar (platform-aware traffic lights / window buttons)
- Information density that leverages the large screen — sidebars, split panes, data tables, tree views
- Keyboard-first interaction: every action reachable via shortcut, Command Palette for discoverability
- Multi-window support for workflows that benefit from side-by-side views
- OS theme integration via `nativeTheme` — automatic dark/light switching
- System tray presence for background tasks, notifications, quick actions
- Context menus that match OS conventions while expressing app personality
- Desktop-appropriate component sizing: smaller click targets (24-32px), denser spacing, more visible information

## Guidelines
- **Electron + React + TypeScript first**: Prototype targets Electron with Vite for fast development. Main/renderer process separation is mandatory.
- **No mobile patterns**: No bottom sheets, no swipe gestures as primary navigation, no hamburger menus. Use desktop idioms (menu bar, sidebar, split pane, context menu).
- **Accessibility first**: aria-label, aria-role, keyboard navigation, focus management, screen reader support.
- **Multi-platform aware**: Design for macOS, Windows, and Linux. Use platform tokens for OS-specific behaviors (Cmd vs Ctrl, traffic lights vs window buttons, system fonts).
- **Realistic content**: Domain-appropriate placeholder text, not lorem ipsum.
- **Intentional design**: Every choice (font, color, spacing, shortcut, animation) must serve the design philosophy. No defaults.
- **Shared assets**: Reuse `docs/design_philosophy.md` and `docs/copy_guide.md` from web `/uiux` when they exist. Don't duplicate, extend.
