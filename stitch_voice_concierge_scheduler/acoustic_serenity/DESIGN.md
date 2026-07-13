---
name: Acoustic Serenity
colors:
  surface: '#f7fafa'
  surface-dim: '#d7dbdb'
  surface-bright: '#f7fafa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f1f4f4'
  surface-container: '#ebeeee'
  surface-container-high: '#e6e9e9'
  surface-container-highest: '#e0e3e3'
  on-surface: '#181c1d'
  on-surface-variant: '#3f4848'
  inverse-surface: '#2d3131'
  inverse-on-surface: '#eef1f1'
  outline: '#707978'
  outline-variant: '#bfc8c8'
  surface-tint: '#2a6767'
  primary: '#0c5252'
  on-primary: '#ffffff'
  primary-container: '#2d6a6a'
  on-primary-container: '#abe8e7'
  inverse-primary: '#95d1d1'
  secondary: '#516165'
  on-secondary: '#ffffff'
  secondary-container: '#d1e3e7'
  on-secondary-container: '#556569'
  tertiary: '#115339'
  on-tertiary: '#ffffff'
  tertiary-container: '#2f6c50'
  on-tertiary-container: '#aaebc7'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b1eeed'
  primary-fixed-dim: '#95d1d1'
  on-primary-fixed: '#002020'
  on-primary-fixed-variant: '#074f4f'
  secondary-fixed: '#d4e6e9'
  secondary-fixed-dim: '#b8cacd'
  on-secondary-fixed: '#0e1e21'
  on-secondary-fixed-variant: '#39494d'
  tertiary-fixed: '#b0f1cd'
  tertiary-fixed-dim: '#95d4b2'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#0d5137'
  background: '#f7fafa'
  on-background: '#181c1d'
  surface-variant: '#e0e3e3'
typography:
  display-brand:
    fontFamily: Playfair Display
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Playfair Display
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: Playfair Display
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Playfair Display
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  body-lg:
    fontFamily: Fira Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Fira Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Fira Sans
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Fira Sans
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 48px
  xl: 80px
  container-max: 1140px
  gutter: 24px
---

## Brand & Style
The design system is built on a foundation of professional calm and quiet authority. It targets a demographic that values efficiency without the frantic energy often associated with AI tools. The visual language balances high-end editorial sophistication with the precision of a modern SaaS tool.

The design style is a hybrid of **Minimalism** and **Soft-Layered Modernism**. It avoids the "plastic" look of standard web apps in favor of a tactile, paper-like quality achieved through subtle acoustic grain textures and muted gradients. The interface should feel "heard" rather than just "seen," using generous whitespace to create a sense of breathing room during the scheduling process.

## Colors
The palette is grounded in "Mist Ground" (#F4F7F7) to reduce eye strain and provide a sophisticated alternative to pure white. 

- **Primary (Teal Trust):** Used for primary actions, active voice states, and key navigational highlights.
- **Secondary (Deep Ink):** Reserved for primary headings and high-contrast text to ensure maximum legibility.
- **Tertiary (Soft Pine):** Utilized exclusively for success states, completed appointments, and "confirmed" indicators.
- **Neutral (Mist Ground):** The canvas for all UI elements. Use tonal variations of this hex for container backgrounds.
- **Warning (Amber Caution):** Applied sparingly to disclaimers or rescheduling conflicts where user attention is critical.

A "Quiet Acoustic Grain" should be applied as a subtle SVG overlay (opacity 3-5%) on "Mist Ground" surfaces to add texture and depth.

## Typography
The typographic system relies on the interplay between the elegant, high-contrast **Playfair Display** and the functional, humanist **Fira Sans**.

- **Brand Wordmarks & Page Headers:** Use Playfair Display to establish a premium, "boutique" feel. 
- **Functional UI & Inputs:** Use Fira Sans for all interactive elements, body text, and captions to ensure clarity and accessibility.
- **Voice Transcription:** Real-time voice-to-text should be rendered in `body-lg` to prioritize readability.
- **Hierarchy:** Maintain a clear distinction by using Deep Ink for Playfair Display elements and a slightly desaturated version of Deep Ink (85% opacity) for Fira Sans body text.

## Layout & Spacing
The layout follows a **Fixed Grid** philosophy on desktop to maintain a contained, focused experience, transitioning to a fluid model on mobile devices.

- **Desktop:** 12-column grid with a 1140px max-width. Content is centered with large `xl` (80px) top/bottom margins to emphasize the "voice orb" as the centerpiece.
- **Mobile:** 4-column fluid grid with 16px side margins. 
- **Rhythm:** Use an 8px base unit. Vertical spacing between different sections should be generous (`lg` or `xl`) to prevent the UI from feeling cluttered, which is vital for a voice-first application.

## Elevation & Depth
In alignment with the "professional and calm" directive, this design system avoids heavy drop shadows. Depth is communicated through **Tonal Layering** and **Subtle Outlines**.

- **Surface Tiers:** Backgrounds use Mist Ground (#F4F7F7). Secondary containers (like cards or input areas) use a slightly lighter "Paper White" (#FFFFFF) with a very thin (1px) border in a muted teal-grey.
- **Voice Orb:** The primary voice signature is the only element allowed to use a "Soft Ambient Glow" — a multi-layered, low-opacity Teal Trust shadow that simulates a gentle light source rather than a physical elevation.
- **Active States:** Instead of raising elements via shadows, active states are indicated by a subtle shift in background hue or a 2px solid Teal Trust left-border.

## Shapes
The shape language is **Soft (Level 1)**. 

While the "Voice Orb" is a perfect circle to represent fluidity, the rest of the UI uses 0.25rem (4px) corner radii. This choice balances the warmth of the brand with the precision of a professional scheduler. Avoid pill-shaped buttons; use rectangular buttons with soft corners to maintain a structured, grounded aesthetic.

## Components
- **Buttons:** Primary buttons use Teal Trust background with white text. Secondary buttons use a transparent background with a 1px border in Deep Ink. Padding should be consistent: 12px vertical, 24px horizontal.
- **The Voice Signature (Orb):** A centered, expressive waveform or orb. When "listening," it should expand with a soft Teal Trust gradient pulse. When "processing," it should transition to a slow, breathing opacity cycle.
- **Cards:** Used for appointment summaries. White background, 1px border (#E2E8E8), and 24px internal padding. No shadows.
- **Input Fields:** Minimalist design with only a bottom border (2px) that transforms from Grey to Teal Trust on focus.
- **Appointment Chips:** Use Soft Pine for "Confirmed" and Amber Caution for "Tentative." Chips should be rectangular with 4px radius and 12px horizontal padding.
- **Lists:** Use generous line-height and Deep Ink for primary list items. Separate items with a subtle 1px horizontal rule in Mist Ground's darker variant.