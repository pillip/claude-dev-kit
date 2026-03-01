# Mobile Wireframes

## Navigation Architecture

### Navigation Type
- [Stack + Bottom Tab / Drawer + Stack / Tab + Nested Stack / etc.]

### Tab Bar
| Tab | Icon | Label | Stack Root |
|-----|------|-------|------------|
| [tab name] | [icon description] | [label] | [screen name] |

### Stack Hierarchy
```
Tab 1
  └─ Screen A (root)
      ├─ Screen B (push)
      │   └─ Screen C (push)
      └─ Modal D (present)

Tab 2
  └─ Screen E (root)
      └─ Screen F (push)
```

## Screen Inventory

| Screen | Navigation | Type | Priority |
|--------|-----------|------|----------|
| [name] | [tab/stack position] | [list/detail/form/modal/onboarding] | [P0/P1/P2] |

## Screen Details

### Screen: [Name]
- **Navigation**: [Tab N > Stack position, or Modal from X]
- **Safe Area**: [top/bottom/both — which edges need safe area insets]
- **Status Bar**: [light/dark content, translucent/opaque]

#### Layout Zones
```
┌─────────────────────────┐
│ [Status Bar]            │
├─────────────────────────┤
│ [Header / Nav Bar]      │
│  - Title: [text]        │
│  - Left: [back/menu]    │
│  - Right: [action(s)]   │
├─────────────────────────┤
│                         │
│ [Content Area]          │
│  - Scroll: [yes/no]     │
│  - Pull to refresh: [y] │
│                         │
├─────────────────────────┤
│ [Action Zone / Footer]  │
│  - [sticky CTA / input] │
├─────────────────────────┤
│ [Tab Bar / Home Ind.]   │
└─────────────────────────┘
```

#### Components
- [Component name] — [brief description, position]

#### States
| State | Content Area | Header | Action Zone |
|-------|-------------|--------|-------------|
| Default | [normal content] | [title] | [CTA enabled] |
| Loading | [skeleton / spinner] | [title] | [CTA disabled] |
| Empty | [illustration + message + CTA] | [title] | [hidden] |
| Error | [error message + retry] | [title] | [retry CTA] |
| Offline | [cached data + offline banner] | [title + offline indicator] | [CTA disabled] |

#### Gestures
- [Swipe right: back navigation (iOS)]
- [Pull down: refresh]
- [Swipe item: delete/archive]
- [Long press: context menu]

#### Keyboard Behavior
- [Which inputs trigger keyboard]
- [KeyboardAvoidingView: padding/position/height]
- [Dismiss: tap outside / scroll / done button]

#### Orientation
- [Portrait only / Portrait + Landscape / Landscape only]

---

### Screen: [Name]
...

## Responsive Behavior

### Small Phone (375pt)
- [Layout adjustments, font scaling, component sizing]

### Standard Phone (390pt)
- [Baseline design — primary target]

### Large Phone (428pt)
- [Extra horizontal space usage, wider margins or larger touch targets]

### Tablet (768pt+, optional)
- [Split view / master-detail / expanded grid]
- [Sidebar navigation instead of bottom tabs]
