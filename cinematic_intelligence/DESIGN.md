---
name: Cinematic Intelligence
colors:
  surface: '#111417'
  surface-dim: '#111417'
  surface-bright: '#37393d'
  surface-container-lowest: '#0c0e12'
  surface-container-low: '#191c1f'
  surface-container: '#1d2023'
  surface-container-high: '#282a2e'
  surface-container-highest: '#323539'
  on-surface: '#e1e2e7'
  on-surface-variant: '#cbc3d7'
  inverse-surface: '#e1e2e7'
  inverse-on-surface: '#2e3134'
  outline: '#958ea0'
  outline-variant: '#494454'
  surface-tint: '#d0bcff'
  primary: '#d0bcff'
  on-primary: '#3c0091'
  primary-container: '#a078ff'
  on-primary-container: '#340080'
  inverse-primary: '#6d3bd7'
  secondary: '#4cd7f6'
  on-secondary: '#003640'
  secondary-container: '#03b5d3'
  on-secondary-container: '#00424e'
  tertiary: '#d0bcff'
  on-tertiary: '#37265e'
  tertiary-container: '#9987c6'
  on-tertiary-container: '#301f57'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e9ddff'
  primary-fixed-dim: '#d0bcff'
  on-primary-fixed: '#23005c'
  on-primary-fixed-variant: '#5516be'
  secondary-fixed: '#acedff'
  secondary-fixed-dim: '#4cd7f6'
  on-secondary-fixed: '#001f26'
  on-secondary-fixed-variant: '#004e5c'
  tertiary-fixed: '#e9ddff'
  tertiary-fixed-dim: '#d0bcff'
  on-tertiary-fixed: '#210f48'
  on-tertiary-fixed-variant: '#4d3d76'
  background: '#111417'
  on-background: '#e1e2e7'
  surface-variant: '#323539'
  void-black: '#000000'
  surface-deep: '#05070A'
  electric-violet: '#8B5CF6'
  cyber-cyan: '#06B6D4'
  glass-stroke: rgba(255, 255, 255, 0.1)
typography:
  display-xl:
    fontFamily: Geist
    fontSize: 80px
    fontWeight: '700'
    lineHeight: '1.0'
    letterSpacing: -0.05em
  display-lg:
    fontFamily: Geist
    fontSize: 56px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.04em
  headline-lg:
    fontFamily: Geist
    fontSize: 40px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 28px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  body-base:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
    letterSpacing: 0em
  label-code:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.0'
    letterSpacing: 0.05em
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '700'
    lineHeight: '1.0'
    letterSpacing: 0.1em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  gutter: 32px
  margin-desktop: 64px
  container-max: 1600px
  section-gap: 80px
---

## Brand & Style

The design system is engineered for a premium desktop experience, leaning into a style described as **Futuristic Glassmorphism**. It is tailored for "The Oracle" brand personality—sophisticated, powerful, and immersive. The aesthetic targets high-end technical users, providing a cinematic control center environment that prioritizes deep focus and high-fidelity data visualization.

The visual narrative is driven by deep layers of transparency, high-density typography, and "cyber-nebula" lighting effects. The UI leverages the expansive canvas of desktop displays to create a sense of infinite depth through atmospheric gradients and localized glowing points, ensuring the interface feels like a living, breathing intelligence.

## Colors

The palette is optimized for OLED and high-resolution desktop monitors, utilizing a "Void" foundation to maximize the luminosity of accent colors.

- **Primary (Electric Violet):** The core intelligence color, used for primary actions and "active" AI states.
- **Secondary (Cyber Cyan):** Used for technical data points, success indicators, and secondary highlights.
- **Neutral (Deep Navy/Black):** Pure Black (#000000) acts as the base background, while Deep Navy (#05070A) provides the tonal structure for surface containers.
- **Atmospheric Gradients:** Backgrounds and interactive states should utilize linear gradients transitioning from Electric Violet to Cyber Cyan at 45-degree angles to simulate cinematic energy.

## Typography

The typography scale is expanded for desktop canvases, focusing on high-contrast hierarchy. **Geist** provides a geometric, technical skeleton for large display moments, where tight letter-spacing is essential for a premium feel. **Inter** handles the density of professional data with high legibility. **JetBrains Mono** is utilized for metadata and "technical whispers"—labels that reinforce the software's intelligence. For desktop rendering, use `antialiased` or `grayscale` font smoothing to maintain the sharpness of the light-on-dark text.

## Layout & Spacing

This design system uses a **Fluid Grid** model optimized for wide-format desktop viewing.

- **Desktop Layout:** A 12-column grid with a 1600px max-container width to ensure content remains legible on ultra-wide monitors. 
- **Margins & Gutters:** Generous 64px outer margins and 32px gutters create a breathable, minimalist aesthetic.
- **Spacing Rhythm:** Based on an 8px scale. Significant negative space (80px+) is encouraged between major functional blocks to maintain the "cinematic" focus and prevent visual clutter.

## Elevation & Depth

Depth is not achieved through shadows but through light and transparency. 

1.  **Level 0 (Background):** Pure Black (#000000).
2.  **Level 1 (Panels):** Deep Navy (#05070A) at 70% opacity with a `backdrop-filter: blur(24px)`.
3.  **Edge Treatment:** All glass panels must feature a 1px inner border (`rgba(255, 255, 255, 0.1)`) on the top and left sides to simulate a light source from the top-left.
4.  **Luminous Depth:** Interactive elements use an ambient glow—a `box-shadow` using the Primary color at 15% opacity with a large 40px-60px blur radius to create a "halo" effect.

## Shapes

The shape language balances technical precision with organic flow. 
- **Standard UI (0.5rem):** Buttons, inputs, and standard cards.
- **Structural Containers (1rem):** Large dashboard sections and main navigation panels.
- **Data & Tags (Full):** Status indicators and tags use pill shapes to contrast against the rigid structural grid.

## Components

- **Glass Containers:** Primary surfaces use a background of `rgba(5, 7, 10, 0.6)` with a `backdrop-filter: blur(20px)`. Edge lighting is mandatory for depth.
- **Buttons:** 
  - *Primary:* Gradient fill (Violet to Cyan) with a subtle pulse glow on hover.
  - *Secondary:* Ghost style with 1px white border (20% opacity) and background brightening on hover.
- **Inputs:** Minimalist bottom-border style. Upon focus, the border expands to 2px Primary color with a 10px outer glow.
- **Lists:** High-density rows with 1px `outline-variant` separators. Hover states trigger a 3px Cyber Cyan "active" bar on the far left.
- **AI Shimmers:** Use animated gradients on borders or text for "processing" states.
- **Scrollbars:** Custom slim, dark-grey tracks with a Cyber Cyan thumb that appears only on hover to maintain visual purity.