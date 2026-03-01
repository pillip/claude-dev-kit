# Mobile Interaction Spec

## User Flows

### Flow: [Name]
- **Trigger**: [tap / swipe / long-press / deep link / push notification]
- **Preconditions**: [auth state, data loaded, permissions granted]
- **Steps**:
  1. [Action] → [system response + animation + haptic]
  2. [Action] → [system response + animation + haptic]
- **Success State**: [outcome, UI change, haptic feedback]
- **Error State**: [outcome, error display, recovery action]
- **Offline Behavior**: [cached response / queue action / block with message]

### Flow: [Name]
...

## Screen Transitions

### Navigation Model
- [Stack-based (push/pop) / Tab-based / Modal presentation / Drawer]
- **iOS back**: swipe-from-left-edge (system gesture, do not override)
- **Android back**: system back button/gesture (handle via `BackHandler` or navigation listener)

### Transition Map
| From → To | Trigger | Animation | Spring Config | Platform Differences |
|-----------|---------|-----------|---------------|---------------------|
| [Screen A] → [Screen B] | [tap] | [slide-from-right (push)] | [default spring] | [iOS: interactive swipe-back; Android: fade] |
| [Screen B] → [Modal] | [tap] | [slide-from-bottom] | [gentle spring] | [iOS: card presentation; Android: slide-up] |
| [Modal] → dismiss | [swipe-down / tap backdrop] | [slide-to-bottom] | [gentle spring] | [same] |
| [Tab A] → [Tab B] | [tab tap] | [cross-fade / none] | — | [same] |

### Shared Element Transitions
- [Element that morphs between screens — e.g., list item image → detail header]
- Technique: [react-native-shared-element / react-navigation shared transitions]
- Elements: [which properties animate — position, size, borderRadius]

## Gesture Specifications

### Swipe Gestures
| Gesture | Direction | Threshold | Action | Haptic | Undo |
|---------|-----------|-----------|--------|--------|------|
| [Swipe to delete] | left | 40% width | delete item | warning | toast + undo (5s) |
| [Swipe to archive] | right | 30% width | archive item | light | toast + undo |
| [Navigate back] | right from edge | 20pt from left edge | pop stack | none (system) | — |

### Long Press
| Element | Duration | Visual Feedback | Haptic | Action |
|---------|----------|----------------|--------|--------|
| [List item] | 500ms | scale 0.97 + dim | heavy | context menu |
| [Image] | 300ms | dim overlay | medium | share sheet |

### Pull to Refresh
- **Trigger**: pull down > 60pt from top of scroll view
- **Visual**: [RefreshControl with custom spinner / branded animation]
- **Haptic**: light impact when threshold reached

### Pinch (if applicable)
- [Pinch to zoom on images/maps]
- Min/max scale: [1x – 3x]

### Pan / Drag (if applicable)
- [Drag to reorder list items]
- Visual: item lifts (shadow + scale 1.03)
- Haptic: medium impact on pickup, light on drop

## Page Load Choreography

### Cold Start (App Launch)
1. Splash screen (native) — [duration based on async init]
2. Skeleton screens appear — instant
3. Content fades in — [duration: 200ms, easing: out]
4. Interactive state — elements become tappable

### Tab Switch
- [Instant content swap / cross-fade 150ms]
- [Preserve scroll position per tab]
- [Lazy load vs. eager load per tab]

### Push Navigation
- [New screen slides from right — spring animation]
- [Previous screen dims slightly / parallax shift left]

### Modal Present
- [Slides from bottom — gentle spring]
- [Backdrop fades in — 200ms opacity]
- [Previous screen scales down slightly (iOS card style)]

## State Management

### Loading States
| Context | Pattern | Details |
|---------|---------|---------|
| Initial screen load | Skeleton screen | Shape matches final layout |
| Pull to refresh | RefreshControl spinner | Native feel per platform |
| Button action | Button loading spinner | Replaces label, disabled |
| Infinite scroll | Footer ActivityIndicator | Appears at list bottom |
| Background operation | Subtle top bar indicator | Non-blocking |

### Empty States
| Screen/Section | Illustration | Headline | Body | CTA |
|---------------|-------------|----------|------|-----|
| [Screen name] | [description or "none"] | [headline] | [body text] | [button label + action] |

### Error States
| Error Type | Display Pattern | Message | Recovery Action |
|-----------|----------------|---------|-----------------|
| Network offline | Persistent banner (top) | [message] | [retry / show cached] |
| API error | Toast or inline | [message] | [retry button] |
| Empty response | Empty state view | [message] | [CTA to create/explore] |
| Permission denied | Blocking modal | [message] | [open settings / explain why] |
| Timeout | Toast with retry | [message] | [retry button] |

### Permission Prompts
1. **Pre-prompt screen**: explain WHY the permission is needed (before system dialog)
2. **System dialog**: [Camera / Location / Notifications / etc.]
3. **Denial fallback**: [reduced functionality + link to Settings]

## Form Behavior

### KeyboardAvoidingView
- **iOS**: `behavior="padding"` with `keyboardVerticalOffset` for header height
- **Android**: `android:windowSoftInputMode="adjustResize"` in AndroidManifest (preferred) or `behavior="height"`

### Keyboard Dismiss
- Tap outside input: `<ScrollView keyboardDismissMode="on-drag">` or `Keyboard.dismiss()`
- Scroll: keyboard dismisses on scroll start
- Done button: for number/phone keyboards that lack return key

### Input Focus Flow
| Input Order | Field | Keyboard Type | Return Key | Next Focus |
|------------|-------|---------------|------------|------------|
| 1 | [field name] | [default/email/numeric] | next | Field 2 |
| 2 | [field name] | [type] | next | Field 3 |
| 3 | [field name] | [type] | done | Submit |

### Validation
- **When**: [on blur / on submit / hybrid]
- **Error display**: inline below field, red border, shake animation (100ms, spring)
- **Success**: [checkmark icon / green border / none]

## Haptic Feedback Map

| Interaction | Haptic Type | Notes |
|------------|------------|-------|
| Button tap | `ImpactFeedbackStyle.Light` | All primary/secondary buttons |
| Toggle switch | `ImpactFeedbackStyle.Medium` | On state change |
| Destructive action | `NotificationFeedbackType.Warning` | Delete, archive |
| Success completion | `NotificationFeedbackType.Success` | Form submit, task complete |
| Error | `NotificationFeedbackType.Error` | Validation fail, network error |
| Selection change | `selectionAsync()` | Picker, segment control |
| Pull-to-refresh threshold | `ImpactFeedbackStyle.Light` | When pull passes activation point |
| Long press activate | `ImpactFeedbackStyle.Heavy` | Context menu trigger |

## Platform Differences

| Behavior | iOS | Android |
|----------|-----|---------|
| Back navigation | Swipe from left edge (system) | System back button/gesture |
| Alerts | Native `Alert` (centered) | Native `Alert` (centered, Material) |
| Action Sheet | `ActionSheetIOS` (bottom sheet) | Custom bottom sheet or `Alert` |
| Date Picker | Inline spinner or compact | Material date picker dialog |
| Share | `UIActivityViewController` | `Intent.ACTION_SEND` |
| Haptics | Full `UIFeedbackGenerator` API | Limited vibration patterns |
| Status bar | Per-screen control | Global, limited per-screen |
| Safe areas | Notch + home indicator | Status bar + nav bar + cutouts |

## Accessibility

### VoiceOver (iOS) / TalkBack (Android)
- All interactive elements: `accessibilityLabel` + `accessibilityRole`
- Images: `accessibilityLabel` describing content (decorative images: `accessibilityElementsHidden`)
- Custom gestures: provide accessible alternatives (buttons, actions)
- Announcements: `AccessibilityInfo.announceForAccessibility()` for dynamic changes
- Focus order: logical reading order via `accessibilityViewIsModal` and grouping

### Dynamic Type
- All text respects `allowFontScaling: true`
- Test at largest accessibility size — layouts must not break
- Use `maxFontSizeMultiplier` where layout constraints are tight (tab bar, buttons)

### Reduced Motion
```typescript
import { useReducedMotion } from 'react-native-reanimated';
// If true:
// - Replace spring/timing animations with instant state changes
// - Keep opacity transitions only (short duration)
// - Disable parallax, stagger, and complex choreography
// - Auto-play animations → manual trigger
```

### Color & Contrast
- Minimum 4.5:1 contrast ratio for body text
- Minimum 3:1 for large text (>= 18pt or 14pt bold)
- Do not convey information by color alone — use icons, patterns, or labels
- Test with iOS "Increase Contrast" and Android "High contrast text"

## Prototype Implementation Priority

Mark each interaction as P0 (must be in prototype) or P1 (nice-to-have in prototype):

| Interaction | Priority | Rationale |
|-------------|----------|-----------|
| [Core user flow gestures] | P0 | [Defines the app's primary experience] |
| [Signature animation] | P0 | [The "unforgettable" moment from design philosophy] |
| [Screen transitions] | P0 | [Navigation must work to demo the app] |
| [Loading/empty/error states] | P0 | [Required for completeness — blank screens are unacceptable] |
| [Secondary gestures (swipe-to-delete, drag-reorder)] | P1 | [Enhances UX but not critical for demo] |
| [Complex choreography (stagger, parallax)] | P1 | [Polish layer, can be added incrementally] |

Note: ALL P0 interactions MUST be implemented in the prototype. P1 interactions should be implemented if time permits.
