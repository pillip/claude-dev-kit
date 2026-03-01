# Mobile Design System (React Native)

## Color Palette

### Primary
### Secondary
### Neutral
### Semantic (Success / Warning / Error / Info)

### OLED Dark Mode Strategy
- Pure black (`#000000`) backgrounds for OLED power saving
- Elevated surfaces: incremental white overlay (4%/8%/12%/16%)
- High-contrast text on dark: minimum 7:1 ratio for body, 4.5:1 for large text
- Accent colors may need saturation adjustment for dark mode legibility

## Typography

### Font Strategy
- **iOS**: SF Pro (system) — intentional use with custom weights/tracking, or custom font
- **Android**: Roboto (system) — intentional use with custom weights/tracking, or custom font
- **Fallback**: Platform system font stack
- **Decision**: [system fonts with personality OR custom fonts — justify the choice]

### Font Configuration
```typescript
export const typography = {
  families: {
    ios: {
      display: '[font name]',
      body: '[font name]',
      mono: '[font name]',
    },
    android: {
      display: '[font name]',
      body: '[font name]',
      mono: '[font name]',
    },
  },
};
```

### Scale (modular ratio: [1.125 / 1.2 — tighter than web])
| Token | Size (pt) | Weight | Font | Usage |
|-------|-----------|--------|------|-------|
| display | | | display | Hero text, onboarding |
| h1 | | | display | Screen titles |
| h2 | | | display | Section headers |
| h3 | | | body | Subsection headers |
| body | | | body | Primary content |
| bodySmall | | | body | Secondary content |
| caption | | | body | Metadata, timestamps |
| overline | | | body | Labels, ALL-CAPS wide tracking |

### Dynamic Type / Font Scaling
```typescript
export const dynamicType = {
  allowFontScaling: true,
  maxFontSizeMultiplier: 1.5,  // prevent layout breakage
  // Per-component overrides where layout is constrained:
  // tabBar: { maxFontSizeMultiplier: 1.2 },
  // button: { maxFontSizeMultiplier: 1.3 },
};
```

### Line Heights & Letter Spacing
```typescript
export const leading = {
  tight: 1.2,      // display, headings
  normal: 1.5,     // body (Latin)
  relaxed: 1.7,    // body (CJK/Korean)
};

export const tracking = {
  tight: -0.5,     // large display (letterSpacing in pt)
  normal: 0,
  wide: 0.5,       // small labels
  wider: 1.0,      // overlines, ALL-CAPS
};
```

### CJK/Korean Notes
- Korean body line-height: use `leading.relaxed` (1.6–1.8)
- Word break handled natively by React Native on both platforms

## Spacing

### Base Unit (4pt grid)
```typescript
export const spacing = {
  xs:   4,
  sm:   8,
  md:   12,
  lg:   16,
  xl:   24,
  xxl:  32,
  xxxl: 48,
  xxxxl: 64,
} as const;
```

## Layout

### SafeAreaView Pattern
```typescript
// Always wrap root screens:
import { SafeAreaView } from 'react-native-safe-area-context';
// Use edges prop for selective safe area: edges={['top', 'bottom']}
// Tab screens: edges={['top']} (bottom handled by tab bar)
```

### Device Classes
| Class | Width (pt) | Notes |
|-------|-----------|-------|
| Small Phone | 375 | iPhone SE, older models |
| Standard Phone | 390 | iPhone 14/15 standard |
| Large Phone | 428 | iPhone 14/15 Plus/Max |
| Tablet (optional) | 768+ | iPad, Android tablets |

### Navigation Structure
- [Stack + Bottom Tab / Drawer + Stack / etc.]
- Tab bar items: [max 5, ideally 3-4]
- Stack depth philosophy: [shallow vs deep navigation]

## Components

### Touch Targets
- **Minimum size**: 44pt (iOS) / 48dp (Android) — use the larger value (48pt) as baseline
- **Spacing between targets**: minimum 8pt gap

### Buttons (variants × states)
- States: default, pressed, disabled, loading
- NO hover state (mobile has no cursor)
- Press feedback: opacity reduction or scale animation

### Inputs (text, select, toggle, checkbox, radio)
- Keyboard type per input: `default`, `email-address`, `numeric`, `phone-pad`, `url`
- Return key type: `done`, `next`, `search`, `send`
- Clear button behavior

### Cards
### Bottom Sheet
### Action Sheet
### Lists (FlatList / SectionList patterns)
### Swipe Actions (swipe-to-delete, swipe-to-reveal)
### Navigation (Stack Header, Tab Bar, Drawer)
### Modals (full-screen vs. centered vs. bottom sheet)
### Badges & Tags
### Toasts & Alerts (in-app vs. native Alert)
### Loading States (skeleton, ActivityIndicator, pull-to-refresh)

## Shadows & Elevation

### iOS
```typescript
export const shadowsIOS = {
  sm: { shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 2 },
  md: { shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4 },
  lg: { shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.15, shadowRadius: 8 },
  xl: { shadowColor: '#000', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.2, shadowRadius: 16 },
};
```

### Android
```typescript
export const shadowsAndroid = {
  sm: { elevation: 2 },
  md: { elevation: 4 },
  lg: { elevation: 8 },
  xl: { elevation: 16 },
};
```

## Border Radius
```typescript
export const radii = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  full: 9999,
};
```

## Motion & Transitions

### Motion Philosophy
- [What motion communicates in this product — entrance, feedback, relationship, delight]
- Spring animations as default (more natural on mobile than easing curves)

### Duration Tokens
```typescript
export const duration = {
  micro: 100,    // press feedback, toggle
  small: 200,    // button state, tab switch
  medium: 350,   // panel expand, modal enter
  large: 500,    // page transition, complex stagger
  // NEVER exceed 700ms for any single animation
};
```

### Spring Configurations (react-native-reanimated)
```typescript
import { withSpring } from 'react-native-reanimated';

export const springs = {
  gentle:  { damping: 20, stiffness: 150, mass: 1 },
  default: { damping: 15, stiffness: 200, mass: 1 },
  bouncy:  { damping: 10, stiffness: 250, mass: 0.8 },
  stiff:   { damping: 20, stiffness: 400, mass: 1 },
};
```

### Easing Tokens (react-native-reanimated)
```typescript
import { Easing } from 'react-native-reanimated';

export const easing = {
  out: Easing.bezier(0.16, 1, 0.3, 1),         // elements entering
  in: Easing.bezier(0.55, 0, 1, 0.45),          // elements leaving
  inOut: Easing.bezier(0.65, 0, 0.35, 1),       // state changes in place
  // Prefer springs over easing for most mobile animations
};
```

### Haptic Feedback Map
```typescript
import * as Haptics from 'expo-haptics';

export const haptics = {
  tap:        Haptics.ImpactFeedbackStyle.Light,
  toggle:     Haptics.ImpactFeedbackStyle.Medium,
  success:    Haptics.NotificationFeedbackType.Success,
  warning:    Haptics.NotificationFeedbackType.Warning,
  error:      Haptics.NotificationFeedbackType.Error,
  selection:  'selectionAsync',  // Haptics.selectionAsync()
  heavyPress: Haptics.ImpactFeedbackStyle.Heavy,
};
```

### Signature Animations
1. **[Name]** — [description, what it communicates]
   ```typescript
   // Reanimated worklet implementation
   ```
2. **[Name]** — [description]
   ```typescript
   // Reanimated worklet implementation
   ```

### Reduced Motion
```typescript
import { useReducedMotion } from 'react-native-reanimated';

// In components:
const reducedMotion = useReducedMotion();
// If true: skip animations, use instant state changes, keep opacity transitions only
```

### Performance Rules
- Use `react-native-reanimated` worklets (run on UI thread)
- Avoid JS-thread animations (`Animated` API) for complex motion
- Use `useAnimatedStyle` instead of inline `transform` arrays
- FlatList: use `getItemLayout` for known-height items to prevent measurement overhead

## Platform-Specific Tokens

### Extensibility Pattern
```typescript
// Token structure supports per-platform overrides:
export const tokens = {
  borderRadius: {
    card: { ios: 12, android: 8 },     // iOS prefers rounder
  },
  statusBar: {
    ios: 'light-content',
    android: 'default',
  },
};
```
