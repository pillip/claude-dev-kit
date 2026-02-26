# Interaction Spec

## User Flows

### Flow: [Name]
- **Trigger**: [user action — click, swipe, keyboard shortcut, URL navigation]
- **Preconditions**: [auth state, data loaded, feature flags]
- **Steps**:
  1. [Action] → [system response + animation]
  2. [Action] → [system response + animation]
- **Success State**: [outcome, UI change, toast/notification]
- **Error State**: [outcome, error display, recovery action]
- **Edge Cases**: [empty data, network failure, concurrent edits, timeout]

### Flow: [Name]
...

## Screen Transitions

### Navigation Model
- [SPA routing / page reload / modal stack / drawer overlay]
- Back button behavior: [browser history, in-app back, modal dismiss]

### Transition Map
| From → To | Trigger | Animation | Duration | Easing |
|-----------|---------|-----------|----------|--------|
| [Screen A] → [Screen B] | [click/swipe] | [slide-left / fade / morph] | [300ms] | [ease-out] |
| [Screen B] → [Modal] | [click] | [fade-in + scale-up from 0.95] | [300ms] | [ease-out] |
| [Modal] → dismiss | [click overlay / ESC] | [fade-out + scale-down to 0.95] | [200ms] | [ease-in] |

### Shared Element Transitions
- [Element that morphs between screens — e.g., card expanding to detail view]
- Technique: [View Transitions API / FLIP animation / CSS shared-axis]

## Page Load Choreography

### Initial Load
1. [Shell/skeleton appears] — instant
2. [Hero content fades in] — [duration, easing]
3. [Secondary elements stagger in] — [delay per item, max spread]
4. [Interactive elements become active] — [after content settles]

### Subsequent Navigation
- [Lighter animation than initial load — cross-fade or slide]
- [Skeleton screens vs. spinner vs. optimistic UI]

## State Management

### Loading States
| Context | Pattern | Duration Threshold | Details |
|---------|---------|-------------------|---------|
| Initial page load | Skeleton screen | 0ms (immediate) | [shape matches final layout] |
| Action feedback | Inline spinner | 0ms | [replaces trigger button/area] |
| Long operation | Progress bar + message | >2s | [estimated time if available] |
| Background sync | Subtle indicator | — | [non-blocking, dismissible] |

### Empty States
| Screen/Section | Illustration | Headline | Body | CTA |
|---------------|-------------|----------|------|-----|
| [Screen name] | [description or "none"] | [headline] | [body text] | [button label + action] |

### Error States
| Error Type | Display Pattern | Message | Recovery Action |
|-----------|----------------|---------|-----------------|
| Network offline | Banner (persistent, top) | [message] | [retry / cache fallback] |
| 404 / Not found | Full page | [message] | [go home / search] |
| Validation error | Inline (per field) | [message] | [focus first error field] |
| Server error (5xx) | Toast (auto-dismiss 5s) | [message] | [retry button] |
| Auth expired | Modal (blocking) | [message] | [re-login redirect] |

### Success States
| Action | Feedback Pattern | Duration | Details |
|--------|-----------------|----------|---------|
| [Form submit] | [toast / inline / redirect] | [auto-dismiss timing] | [animation] |
| [Item created] | [optimistic insert + toast] | — | [undo available for Ns] |
| [Item deleted] | [optimistic remove + undo toast] | [5s undo window] | [animation: slide-out] |

## Form Behavior

### Validation Strategy
- **When to validate**: [on blur / on change / on submit / hybrid]
- **Error display**: [inline below field / tooltip / summary at top]
- **Error animation**: [shake + border-color change, duration, easing]
- **Success indication**: [checkmark icon / green border / none]

### Validation Rules
| Field | Rule | Error Message | Trigger |
|-------|------|---------------|---------|
| [field name] | [required / min-length / pattern / custom] | [user-friendly message] | [on blur / on submit] |

### Submission Flow
1. User clicks submit → button enters loading state (spinner, disabled)
2. Validation runs → if errors, scroll to first error, shake animation
3. API call → optimistic UI update (if applicable)
4. Success → [redirect / toast / inline confirmation]
5. Failure → [error toast / inline error / retry prompt]

### Multi-step Forms
- Progress indicator: [stepper / progress bar / fraction "2/4"]
- Back navigation: [preserve entered data]
- Validation: [per-step or all-at-once]

## Micro-interactions

### Hover Effects
| Element | Property Changes | Duration | Easing | Notes |
|---------|-----------------|----------|--------|-------|
| [Button primary] | [bg-color, shadow, translate-y -1px] | [150ms] | [ease-out] | [multi-property choreography] |
| [Card] | [shadow elevation, border-color, scale 1.01] | [200ms] | [ease-out] | — |
| [Link] | [color, underline-offset] | [100ms] | [ease-out] | — |
| [Icon button] | [bg-color, icon rotate/scale] | [150ms] | [ease-out] | — |

### Focus States
- **Visible focus ring**: [outline style, offset, color — must be visible on all backgrounds]
- **Focus-within**: [container highlight when child is focused]
- **Keyboard vs. mouse**: [:focus-visible only for keyboard, no ring on click]

### Active/Press States
- [Scale down 0.97 + darken for buttons]
- [Duration: 50ms, ease-out]

### Toggle & Checkbox Animations
- [Toggle knob slide: 200ms, spring easing]
- [Checkbox check draw: SVG stroke-dashoffset, 250ms]
- [Radio dot scale-in: 150ms, ease-out]

### Scroll Interactions
- **Scroll-reveal**: [elements fade/slide in on entering viewport]
  - Technique: [IntersectionObserver / scroll-driven animation]
  - Threshold: [10% visible triggers animation]
  - Animation: [fade-up 20px, 400ms, ease-out, stagger 50ms per item]
- **Sticky elements**: [header, sidebar, action bar — behavior on scroll]
- **Scroll progress**: [reading progress bar / section indicators]

### Drag & Drop (if applicable)
- **Drag start**: [element lifts (shadow + scale 1.02), ghost opacity 0.7]
- **Drag over**: [drop zone highlight, placeholder gap animation]
- **Drop**: [element settles into position, 200ms spring easing]
- **Cancel**: [element returns to origin, 300ms ease-out]

### Feedback Patterns
| Type | Pattern | Auto-dismiss | Position | Animation |
|------|---------|-------------|----------|-----------|
| Success toast | [text + icon] | [3s] | [bottom-center] | [slide-up + fade-in] |
| Error toast | [text + icon + action] | [manual / 5s] | [bottom-center] | [slide-up + fade-in] |
| Confirmation modal | [title + body + actions] | [manual] | [center overlay] | [fade + scale from 0.95] |
| Inline notification | [text + dismiss] | [manual] | [contextual] | [expand height, 200ms] |
| Tooltip | [text] | [on mouse-leave] | [above/below element] | [fade-in, 150ms delay] |

## Keyboard & Accessibility

### Keyboard Shortcuts (if applicable)
| Shortcut | Action | Scope |
|----------|--------|-------|
| [key combo] | [action] | [global / screen-specific] |

### Focus Management
- **Modal open**: [trap focus inside, focus first interactive element]
- **Modal close**: [return focus to trigger element]
- **Dynamic content**: [announce via aria-live, move focus if destructive]
- **Tab order**: [follows visual order, skip hidden elements]

### Screen Reader Announcements
| Event | aria-live | Message |
|-------|-----------|---------|
| [Item added] | polite | ["{item} added to list"] |
| [Error occurred] | assertive | [error message text] |
| [Loading complete] | polite | ["Content loaded"] |

## Responsive Behavior

### Touch Adaptations (mobile)
- **Tap targets**: minimum 44×44px
- **Swipe gestures**: [swipe-to-delete, swipe-to-reveal-actions, pull-to-refresh]
- **Long press**: [context menu, drag initiation — with haptic feedback hint]
- **Bottom sheet**: [replaces modal on mobile, drag-to-dismiss]

### Breakpoint-specific Interactions
| Interaction | Mobile (<768px) | Tablet (768-1279px) | Desktop (≥1280px) |
|-------------|----------------|--------------------|--------------------|
| Navigation | [hamburger → slide drawer] | [sidebar collapsed] | [sidebar expanded] |
| List actions | [swipe-to-reveal] | [hover-to-reveal] | [hover-to-reveal] |
| Multi-select | [long-press to enter mode] | [checkbox column] | [checkbox column] |
