---
name: mobile-uiux
description: kickoff 산출물 기반으로 모바일 디자인 철학을 수립하고, 모바일 디자인 시스템/와이어프레임/React Native(Expo) 프로토타입을 생성합니다. 권장 흐름: /prd → /kickoff → /mobile-uiux
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
4) Check for existing shared assets:
   - `docs/design_philosophy.md` — 웹 `/uiux`에서 이미 생성되었는지 확인
   - `docs/copy_guide.md` — 웹 `/uiux`에서 이미 생성되었는지 확인
5) Scan the project for existing mobile code:
   - Glob for `**/*.tsx`, `**/*.ts`, `app.json`, `app.config.js`, `app.config.ts`
   - If found, read key files to understand current patterns, navigation structure, and tech stack.

### Phase 2 — Design Philosophy (조건부 — CRITICAL before any code)
6) Check if `docs/design_philosophy.md` already exists:
   - **If exists**: Read the file, present it to the user, and ask: "웹에서 생성된 디자인 철학이 있습니다. 모바일에도 동일하게 적용할까요, 아니면 모바일에 맞게 수정할까요?"
     - If approved: reuse as-is, proceed to Phase 3.
     - If modification requested: create a mobile-adapted version, updating the philosophy while maintaining brand consistency.
   - **If not exists**: Generate from scratch (same process as web `/uiux`):
7) Analyze the product's identity from PRD and UX spec:
   - Who are the users? What's the emotional tone?
   - What category does this product belong to?
   - Are there competitor/reference apps mentioned?
8) Commit to a BOLD aesthetic direction with mobile lens:
   - Apply the mobile design lens: 한 손 조작감, 첫 3초 인상, 기억에 남는 제스처
9) Generate `docs/design_philosophy.md`:
   - Named aesthetic (2-3 words)
   - 2-3 paragraphs: how the philosophy manifests through space/form, color/material, scale/rhythm, composition
   - What makes this design UNFORGETTABLE
10) Present the design philosophy to the user and ask for approval before proceeding.
    - If rejected, iterate on the direction.

### Phase 3 — Mobile Design System
11) Generate `docs/design_system_mobile.md` reflecting the chosen aesthetic:
    - **Color palette**: TypeScript token objects. Dominant colors with sharp accents. OLED dark mode strategy with pure black backgrounds and incremental surface elevation.
    - **Typography**: Platform font choices (SF Pro/Roboto or custom). Tighter modular scale (1.125 or 1.2). Dynamic Type config (`allowFontScaling`, `maxFontSizeMultiplier`).
    - **Spacing**: 4pt-based scale (xs:4, sm:8, md:12, lg:16, xl:24, xxl:32, xxxl:48, xxxxl:64)
    - **Components**: Mobile-specific — Bottom Sheet, Action Sheet, Swipe Actions, Pull-to-Refresh. States: default, pressed, disabled, loading (NO hover). Touch targets: minimum 48pt.
      - **MUST include**: Text Input (focus/error/placeholder/character count/keyboard type), Segment Control/Toggle (if app has mode switching), Loading indicators (skeleton, pull-to-refresh, button loading)
      - **MUST include**: FlatList/SectionList patterns (ItemSeparator, ListHeader, ListEmpty, key extractor)
      - **MUST include**: Stack header styling (back button, title alignment, header background)
    - **Shadows**: ios (shadowColor/Offset/Opacity/Radius) vs android (elevation) separated
    - **Motion tokens**: Duration (micro 80-120ms to large 400-600ms, max 700ms), spring configs (damping/stiffness/mass), easing (Reanimated), haptic mapping (expo-haptics)
      - **Signature animations**: MUST include full worklet code for at least one signature animation, not just prose descriptions or comment stubs
    - **Loading states**: Skeleton screen spec, pull-to-refresh indicator, cold start visual (splash → skeleton → content → interactive)
    - **Platform tokens**: `ios`/`android` keys for platform-specific values
    - All values expressed as TypeScript objects (NOT CSS custom properties)
12) Ask the user if the design system direction looks right before proceeding.

### Phase 4 — Wireframes & Interaction Spec
13) Generate `docs/wireframes_mobile.md`:
    - Navigation architecture (Stack + Bottom Tab / Drawer hierarchy, tab bar items, stack depth)
    - Screen inventory with navigation position and type
    - Per-screen details: navigation context, safe area handling, layout zones (header/content/action), components, states (default/loading/empty/error/offline), gestures, keyboard behavior, orientation
    - Responsive behavior per device class (375pt / 390pt / 428pt / tablet optional)
14) Generate `docs/interactions_mobile.md`:
    - User flows with trigger (tap/swipe/long-press/deep link/push), steps with animation + haptic, offline behavior
    - Screen transitions with navigation model, back behavior (iOS swipe vs Android system), transition map with spring configs
    - Gesture specs: swipe (direction/threshold/action/haptic), long press, pull-to-refresh, pinch, pan/drag
    - Page load choreography: cold start (splash→skeleton→content→interactive), tab switch, push, modal
    - State management: loading (skeleton/refresh/button), empty, error (network/permission), permission prompts (pre-prompt→system→denial)
    - Form behavior: KeyboardAvoidingView, keyboard dismiss, input focus flow, keyboard type per input
    - Haptic feedback map: interaction → haptic type table
    - Platform differences: iOS vs Android table (back, alerts, date picker, share, haptics)
    - Accessibility: VoiceOver/TalkBack, Dynamic Type, reduced motion

### Phase 4.5 — Copy Guide (조건부)
15) Check if `docs/copy_guide.md` already exists:
    - **If exists**: Read the file. Check if it already has a `## Mobile Adaptations` section.
      - If no mobile section: append a `## Mobile Adaptations` section covering:
        - Shorter labels for constrained mobile UI (tab bar, buttons, headers)
        - Push notification copy templates
        - Permission request pre-prompt copy
        - Offline state messaging
        - Haptic-paired feedback copy (e.g., success messages that pair with success haptic)
      - If mobile section exists: review and update if needed.
    - **If not exists**: Run the **copywriter** agent to generate `docs/copy_guide.md`:
      - Input: `docs/ux_spec.md`, `docs/design_philosophy.md`, `docs/wireframes_mobile.md`, `docs/interactions_mobile.md`, PRD
      - Output: Voice & tone definition, copy inventory per screen, patterns, glossary, mobile adaptations section
      - Include FULL CONTENT of input documents in the subagent prompt.
      - This step MUST complete before Phase 5 so the prototype uses real copy.
16-a) **Accessibility labels (REQUIRED)**: Ensure `copy_guide.md` includes `accessibilityLabel` for EVERY interactive element (buttons, toggles, list items, navigation items, form inputs). Also include state-change announcement strings for VoiceOver/TalkBack (e.g., "달리기 완료", "달리기 체크 해제"). This is mandatory per NFR accessibility requirements.

### Phase 5 — React Native Prototype
16) Create the `prototype-mobile/` directory structure:
    ```
    prototype-mobile/
      App.tsx
      app.json
      package.json
      babel.config.js
      tsconfig.json
      .gitignore
      src/
        types/
          index.ts (shared types)
        theme/
          tokens.ts
          typography.ts
          spacing.ts
          colors.ts
        components/
          Button.tsx
          Card.tsx
          Input.tsx
          ... (as needed per design system)
        screens/
          ... (one .tsx per screen from wireframes)
        navigation/
          index.tsx
    ```
17) Generate `prototype-mobile/package.json`:
    - `"main"`: MUST be `"node_modules/expo/AppEntry.js"` (NOT `"App.tsx"`)
    - **Required dependencies** (MUST include all of these):
      - `expo`, `babel-preset-expo`, `expo-asset` — core Expo runtime
      - `react`, `react-native` — framework
      - `@react-navigation/native`, `@react-navigation/native-stack`, `@react-navigation/bottom-tabs` — navigation
      - `react-native-reanimated`, `react-native-worklets` — animation (worklets is required for Reanimated v4+)
      - `react-native-gesture-handler`, `react-native-safe-area-context`, `react-native-screens` — navigation native deps
      - `expo-haptics`, `expo-status-bar` — interaction/UI
      - `expo-font` (only if custom fonts are used)
    - Use the latest stable Expo SDK — do NOT pin to an older version for Expo Go compatibility
    - Use `~` ranges for Expo ecosystem packages
    - After generating package.json, run: `cd prototype-mobile && npm install && npx expo install --fix` to resolve exact compatible versions
17-a) Generate `prototype-mobile/babel.config.js`:
    - ONLY use `babel-preset-expo` as preset
    - Do NOT manually add `react-native-reanimated/plugin` — babel-preset-expo handles it automatically (SDK 54+)
17-b) Generate `prototype-mobile/.gitignore`:
    - Standard Expo gitignore: node_modules, .expo, dist, *.jks, *.keystore, .env
17-c) Generate `prototype-mobile/tsconfig.json`:
    - Extends `expo/tsconfig.base`
    - If using path aliases, also configure `babel-plugin-module-resolver` (Metro ignores tsconfig paths)
18) Generate `prototype-mobile/app.json`:
    - Expo config with app name, slug, orientation, userInterfaceStyle
    - Do NOT reference asset files (icon, splash.image) unless they physically exist in the project
    - `plugins` array: ONLY include packages that provide a config plugin (e.g., `expo-font`). Do NOT include `expo-haptics` (it has no config plugin)
19) Generate `prototype-mobile/src/theme/`:
    - `colors.ts` — color palette from design system
    - `spacing.ts` — spacing scale
    - `typography.ts` — font families, scale, Dynamic Type config
    - `tokens.ts` — re-exports all theme tokens + shadows, radii, motion config
20) Generate `prototype-mobile/src/components/`:
    - Reusable components matching the design system
    - Each component uses theme tokens, supports pressed/disabled/loading states
    - Haptic feedback integrated where specified in interaction spec
21) Generate `prototype-mobile/src/screens/`:
    - One .tsx file per screen from wireframes
    - Uses design system components and theme tokens
    - Implements all states: default, loading (skeleton), empty, error
    - Uses actual copy from `docs/copy_guide.md`
22) Generate `prototype-mobile/src/navigation/index.tsx`:
    - React Navigation structure matching wireframe navigation architecture
    - Stack navigators nested in bottom tab navigator (or as specified)
    - Screen options: header config, tab bar config, transition animations
23) Generate `prototype-mobile/App.tsx`:
    - SafeAreaProvider, NavigationContainer, theme provider setup
    - Status bar configuration

### Phase 5.5 — Prototype Verification (REQUIRED before presenting to user)
24) **Expo project setup check**:
    - `package.json` `"main"` is `"node_modules/expo/AppEntry.js"` (NOT `"App.tsx"`)
    - `babel-preset-expo` and `expo-asset` are in dependencies
    - `react-native-worklets` is in dependencies (required for Reanimated v4+)
    - `babel.config.js` uses ONLY `babel-preset-expo` preset (no manual reanimated plugin)
    - `app.json` does NOT reference non-existent asset files
    - `app.json` `plugins` does NOT include packages without config plugins (e.g., `expo-haptics`)
    - `tsconfig.json` exists with `"extends": "expo/tsconfig.base"`
    - `.gitignore` exists
25) **Token compliance check**:
    - Scan all files in `src/screens/` and `src/components/` for hardcoded style values
    - Every color, spacing, font size, border radius, and shadow MUST use imports from `src/theme/`
    - Fix any hardcoded values found before proceeding
26) **Screen coverage check**:
    - Count screens defined in `docs/wireframes_mobile.md`
    - Count .tsx files in `src/screens/`
    - Every wireframe screen (except explicitly P2+ deferred screens) MUST have a corresponding screen file
27) **State coverage check**:
    - Every screen MUST implement at least default + one additional state (loading, empty, or error as applicable)
    - Empty state MUST use copy from `docs/copy_guide.md`, not placeholder text
28) **Animation completeness check**:
    - At least ONE signature animation from `docs/design_philosophy.md` MUST be fully implemented with Reanimated worklet code
    - `useReducedMotion()` MUST be respected globally, not just in one component
29) **Performance check**:
    - List item components used in FlatList MUST use `React.memo`
    - Event handlers passed to memoized children MUST use `useCallback`

### Phase 6 — Review & Iterate
30) Present deliverables summary to the user:
    - List all generated files with brief descriptions
    - Highlight the design philosophy and key aesthetic choices
    - Report verification results from Phase 5.5 (token compliance, screen coverage, state coverage)
    - Suggest running on simulator (NOT Expo Go — SDK version mismatch issues):
      ```bash
      cd prototype-mobile
      npx expo start --ios      # iOS Simulator (requires Xcode)
      npx expo start --android  # Android Emulator (requires Android Studio)
      ```
    - Note: dependencies are already installed during Phase 5 (`npm install && npx expo install --fix`)
    - Ask for feedback on any screen
31) Iterate based on user feedback:
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
- If existing mobile code uses a different framework (Flutter, SwiftUI, etc.): adapt the prototype to match that framework instead of defaulting to React Native. Note the framework in `docs/design_system_mobile.md`.
- If PRD is too vague for mobile UI design (no user stories, no features): ask the user targeted questions about screens and user flows before proceeding.

## Rollback
- This skill is additive (writes new files/directories). No destructive rollback needed.
- Re-running `/mobile-uiux` overwrites all outputs — safe to retry.
- Prototype directory (`prototype-mobile/`) can be safely deleted if not needed.

## Anti-AI-Slop Rules (CRITICAL)

These rules prevent Claude from converging on generic, forgettable mobile defaults:

**NEVER:**
- Uncustomized default navigation bar with system back button and plain title
- Personality-free Material Design 3 components straight from the library
- iOS patterns on Android or Android patterns on iOS without intentional design
- 16px uniform padding on all sides of every screen
- 5 identical-weight icons in a tab bar with no visual hierarchy
- Ignoring safe areas (notch, home indicator, status bar)
- Hardcoded pixel values that don't scale across device sizes
- Generic potted plant / astronaut / magnifying glass illustrations for empty states
- System default keyboard and picker styles without customization context

**INSTEAD:**
- Platform-appropriate custom design that respects conventions while expressing personality
- Intentional system font usage (custom weights, tracking, sizing) OR well-chosen custom fonts
- Dynamic Type support with `allowFontScaling` and `maxFontSizeMultiplier`
- Haptic feedback mapped to interaction meaning, not sprinkled randomly
- Spring animations as the default (more natural than timed easing on mobile)
- OLED-aware dark mode with true black and incremental surface elevation
- Thumb-zone-aware layout: primary actions in the bottom third
- Signature gesture or interaction that defines the app's personality

## Guidelines
- **React Native (Expo) first**: Prototype targets Expo managed workflow. No bare workflow or native modules unless absolutely necessary.
- **No web patterns**: No CSS, no `<div>`, no media queries. Use React Native primitives (View, Text, Pressable, FlatList, etc.).
- **Accessibility first**: accessibilityLabel, accessibilityRole, Dynamic Type, VoiceOver/TalkBack support.
- **Mobile-first responsive**: Design for 390pt standard, adapt down to 375pt and up to 428pt.
- **Realistic content**: Domain-appropriate placeholder text, not lorem ipsum.
- **Intentional design**: Every choice (font, color, spacing, haptic, spring config) must serve the design philosophy. No defaults.
- **Shared assets**: Reuse `docs/design_philosophy.md` and `docs/copy_guide.md` from web `/uiux` when they exist. Don't duplicate, extend.
