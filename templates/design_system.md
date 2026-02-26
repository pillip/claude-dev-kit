# Design System

## Color Palette

### Primary
### Secondary
### Neutral
### Semantic (Success / Warning / Error / Info)

## Typography

### Font Pairing
- **Display font**: [name] — [why this font, what personality it brings]
- **Body font**: [name] — [why this pairs well with the display font]
- **Mono font** (if needed): [name] — [usage context]
- **Pairing principle**: [contrast type — serif+sans, slab+humanist, etc.]

### Font Stack (with fallbacks)
```css
--font-display: '[Display]', [metric-compatible-fallback], [generic];
--font-body: '[Body]', [metric-compatible-fallback], [generic];
--font-mono: '[Mono]', [metric-compatible-fallback], monospace;
```
- `font-display`: swap (body) / optional (decorative)
- Variable font axes: [wght, ital, opsz — if applicable]

### Scale (modular ratio: [1.25 / 1.333 / 1.5])
| Token | Size | Weight | Font | Usage |
|-------|------|--------|------|-------|
| --text-display | | | display | |
| --text-h1 | | | | |
| --text-h2 | | | | |
| --text-h3 | | | | |
| --text-body | | | body | |
| --text-small | | | body | |
| --text-caption | | | body | |
| --text-overline | | | body | ALL-CAPS, wide tracking |

### Responsive Typography
```css
/* Fluid display: min 1.5rem @ 375px → max 3rem @ 1280px */
--text-display: clamp(1.5rem, [calc], 3rem);
```

### Line Heights & Letter Spacing
```css
--leading-tight: 1.2;    /* display, headings */
--leading-normal: 1.5;   /* body (Latin) */
--leading-relaxed: 1.7;  /* body (CJK/Korean — needs more breathing room) */
--tracking-tight: -0.02em;  /* large display text */
--tracking-normal: 0;
--tracking-wide: 0.05em;    /* small labels */
--tracking-wider: 0.1em;    /* overlines, ALL-CAPS */
```

### CJK/Korean Notes
- word-break: keep-all (prevent mid-word breaks)
- Korean body line-height: use --leading-relaxed
- Korean font fallback: [specific Korean font if display font lacks Korean]

## Spacing

### Base Unit (4px grid)
### Scale (4, 8, 12, 16, 24, 32, 48, 64)

## Layout

### Breakpoints (mobile / tablet / desktop)
### Grid System
### Container Widths

## Components

### Buttons (variants × states)
### Inputs (text, select, checkbox, radio, toggle)
### Cards
### Navigation (header, sidebar, breadcrumbs, tabs)
### Modals & Drawers
### Tables
### Badges & Tags
### Toasts & Alerts
### Loading States (skeleton, spinner)

## Iconography

## Shadows & Elevation

## Border Radius

## Motion & Transitions

### Motion Philosophy
- [What motion communicates in this product — entrance, feedback, relationship, delight]

### Duration Tokens
```css
--duration-instant: 50ms;   /* hover, focus ring */
--duration-fast: 150ms;     /* color change, icon swap */
--duration-normal: 300ms;   /* expand, toggle, checkbox */
--duration-slow: 500ms;     /* modal, drawer, page transition */
```

### Easing Tokens
```css
--ease-out: cubic-bezier(0.16, 1, 0.3, 1);        /* elements entering */
--ease-in: cubic-bezier(0.55, 0, 1, 0.45);         /* elements leaving */
--ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);     /* state changes in place */
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);  /* playful overshoot */
```
- Why each easing was chosen for this product's personality

### Stagger Pattern
```css
--stagger-delay: [30-50]ms;  /* per item in lists */
--stagger-max: 300ms;        /* cap total spread */
```

### Signature Animations
1. **[Name]** — [description, what it communicates]
   ```css
   @keyframes [name] { ... }
   ```
2. **[Name]** — [description]
   ```css
   @keyframes [name] { ... }
   ```

### Hover Choreography
- [Multi-property hover pattern — what shifts, translates, fades, and at what timing]

### Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

### Performance Rules
- Animate ONLY: `transform`, `opacity` (GPU-composited)
- NEVER animate: `width`, `height`, `top`, `left`, `margin`, `padding`
- `will-change`: apply only to elements about to animate, remove after
