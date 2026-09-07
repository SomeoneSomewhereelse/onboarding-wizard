---
name: Onboarding Wizard
description: A passport-control setup wizard — each validated credential earns a hand-inked stamp on a cloth-bound, laid-paper booklet spread.
colors:
  cover-navy: "#1f2a44"
  cover-navy-deep: "#16203a"
  paper-cream: "#efe6cf"
  paper-cream-deep: "#e6dcbf"
  ledger-ink: "#241d12"
  ledger-ink-muted: "#6b5f47"
  ledger-rule: "#c9b98f"
  control-blue: "#2a4d8a"
  gold-foil: "#9c7a1f"
  stamp-red: "#8a1f2b"
  stamp-blue: "#2a4d8a"
  status-ok: "#1f6b3a"
  status-fail: "#8a1f2b"
  page-ground: "#dfe1d9"
typography:
  display:
    fontFamily: "\"Fraunces\", Georgia, \"Iowan Old Style\", \"Palatino Linotype\", \"Book Antiqua\", \"Noto Serif\", \"Liberation Serif\", \"DejaVu Serif\", serif"
    fontSize: "1.7rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "0.01em"
  label:
    fontFamily: "\"Fraunces\", Georgia, \"Iowan Old Style\", \"Palatino Linotype\", \"Book Antiqua\", \"Noto Serif\", \"Liberation Serif\", \"DejaVu Serif\", serif"
    fontSize: "0.95rem"
    fontWeight: 400
    letterSpacing: "0.04em"
  body:
    fontFamily: "-apple-system, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  body-small:
    fontFamily: "-apple-system, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 400
rounded:
  pill: "999px"
  xs: "3px"
  sm: "4px"
  md: "6px"
  lg: "0.75rem"
spacing:
  xs: "0.35rem"
  sm: "0.5rem"
  md: "0.9rem"
  lg: "1.1rem"
  xl: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.control-blue}"
    textColor: "#ffffff"
    rounded: "{rounded.xs}"
    padding: "0.5rem 1.1rem"
  button-secondary:
    backgroundColor: "{colors.paper-cream-deep}"
    textColor: "{colors.ledger-ink}"
    rounded: "{rounded.xs}"
    padding: "0.4rem 0.9rem"
  button-pill-control:
    backgroundColor: "{colors.paper-cream}"
    textColor: "{colors.ledger-ink}"
    rounded: "{rounded.pill}"
    padding: "0.4rem 0.9rem"
  input-field:
    backgroundColor: "{colors.paper-cream-deep}"
    textColor: "{colors.ledger-ink}"
    rounded: "{rounded.md}"
    padding: "0.5rem"
---

# Design System: Onboarding Wizard

## Overview

**Creative North Star: "The Stamped Passport"**

The wizard is a passport control desk, not a progress bar. A visitor doesn't fill out a form; they get cleared, one gate at a time, toward a live deployment on the far side. The whole system is built around one physical object: an open passport booklet spanning the viewport, its left page a stamp grid that fills in as each of eight external services is validated, its right page the currently active frame's form, printed on cream laid paper with ruled baseline lines like an old customs declaration. A navy cloth cover binds the outside edges of the viewport at all times, whatever the scroll position. There is no percentage, no numbered stepper dots, no "step 3 of 8" language doing the progress-communication work — the stamp grid does it visually, legible at a glance before any copy is read.

The material logic is ink-and-paper, not glass-and-shadow: surfaces are flat, cards are transparent panes that let the ruled paper show through rather than opaque tiles stacked on top of it, and the one recurring dimensional cue is the stamp ring's own hand-inked bleed, not a system-wide shadow language. Gold foil is the one ornamental color in the system and its restraint is the point — it marks the certificate underline beneath the page heading, the gutter rule between the two pages, and nothing else. The interactive accent (blue) and the ceremonial accent (gold) are kept strictly separate: gold never sits on a clickable control, and the accent blue never appears in a stamp ring.

Confirmed rejection: the category default of a horizontal progress bar of gray circles/steps. This system replaces that pattern's entire vocabulary (linear stepper, percentage counter, numbered dots) with the stamp grid, and no numbered-stepper affordance should be reintroduced alongside it.

**Key Characteristics:**
- A physical, bound-booklet metaphor carried in real materials (cloth weave, laid paper, foil, hand-inked stamps) rather than illustrated once and abandoned.
- Progress is a spatial, cumulative artifact (the filling stamp grid) rather than a numeric readout.
- Flat surfaces; the only dimensional texture is the stamp ring's own ink bleed and the cloth cover's cross-hatch weave.
- Gold foil is rare by design — headers and the center gutter rule only, never a control.
- The layout physically mirrors under RTL (the stamp grid moves to the reading-first side), not just text-direction flipping.

## Colors

An ink-and-paper palette: warm cream paper and navy cloth as the two large fields, red and blue reserved for stamp ink, gold foil held back for ceremonial marks only.

### Primary
- **Control Blue** (`#2a4d8a`; dark theme `#7ba7d9`): the interactive-control color — links, focus/active states, `accent-color` on native radio/checkbox controls. Never used for the gold-foil ornament role, even though both are "accents" — the code comments in `static/index.html` explicitly separate these two roles. In light theme this also happens to equal Stamp Blue below (`--stamp-blue: var(--accent)`'s light value), but the two are independent tokens, not one shared role — see Stamp Blue's own dark-theme value.
- **Primary Button Fill** (`--btn-primary-bg`, light theme = Control Blue `#2a4d8a`; dark theme `#7d6438`, a warm brass/brown): decoupled from Control Blue in dark theme only (revised 2026-09) — a bright sky-blue button read as out of place against the warm brown card/paper world, and the brass tone also measures ~5.6:1 contrast with white button text versus the prior ~2.7:1.

### Secondary
- **Gold Foil** (`#9c7a1f`; dark theme `#c9a227`): ceremonial only — the underline beneath the page `<h1>`, the vertical gutter rule between the two passport pages (and its horizontal equivalent on the mobile stacked layout), the "YOUR PASSPORT" label, and the dashed gold thread suggested at the cloth cover's inner seam. Used sparingly by design; it never appears on a button, input, or any other clickable surface.

### Tertiary
- **Stamp Blue** (`#2a4d8a`; dark theme `#4d7ab3`) and **Stamp Red** (`#8a1f2b`; dark theme `#b5495c`): the two stamp-ink colors, alternating across the eight stamp-grid cells (fixed per frame, not randomized). In light theme Stamp Blue equals Control Blue; **in dark theme they're deliberately independent and both were revised 2026-09** — the original dark values (`#7ba7d9`/`#d97583`) matched Control Blue/a bright pink almost exactly, and combined with a `mix-blend-mode: screen` on the ink ring (also removed), read as neon glow against the near-black cover panel rather than lamplit ink. Neither stamp color is coupled to `--fail` (`#e08086` dark) despite superficial similarity to Stamp Red — they're separate tokens that happen to sit in the same red family.

### Neutral
- **Page Ground** (`#dfe1d9`; dark `#10131c`): the `body` background outside the passport spread itself.
- **Paper Cream** (`#efe6cf`; dark `#2a2418`): the passport page surface — both the right-page form panel (`main`) and the stamp-grid cell background before it's earned.
- **Paper Cream Deep** (`#e6dcbf`; dark `#221d13`): input fields, the locked "Change" button, and other slightly-recessed surfaces against Paper Cream.
- **Ledger Ink** (`#241d12`; dark `#ecdfc0`): body text.
- **Ledger Ink Muted** (`#6b5f47`; dark `#a89968`): secondary copy — lede text, frame badges, muted stamp glyphs before they're earned.
- **Ledger Rule** (`#c9b98f`; dark `#4a4128`): borders, the ruled-paper baseline lines, dashed stamp-slot borders.
- **Cover Navy** (`#1f2a44`) / **Cover Navy Deep** (`#16203a`) (dark theme `#0d1220` / `#070a13`): the cloth-bound cover strips at the outer viewport edges — pure chrome, `pointer-events: none`, never a background a control sits on.
- **Status Ok** (`#1f6b3a`; dark `#5fbf87`): a completed/done frame's badge and detail text.

### Named Rules
**The Ceremonial-vs-Interactive Rule.** Gold foil marks ceremony (headers, the gutter rule, the passport label); Control Blue marks interactivity (links, buttons, focus, one stamp ink). The two never trade places — a control never turns gold, and the gutter rule never turns blue.

**The Dark-Mode-Warms Rule.** Dark theme is lamplight, not inversion: the paper surface shifts to a warm dark brown (`#2a2418`), not a cold gray or a flipped-white, and gold foil (`--gold`) actually intensifies toward its most saturated value (`#c9a227`) rather than dimming, matching how foil catches lamplight.

## Typography

**Display Font:** Fraunces (self-hosted, weights 400/600/700; falls back to Georgia, "Iowan Old Style", "Palatino Linotype", "Book Antiqua", "Noto Serif", "Liberation Serif", "DejaVu Serif", serif)
**Body Font:** -apple-system (with "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif)

**Character:** A certificate serif for anything that reads as officially stamped or headed (the page title, frame titles, the stamp-grid label), paired with a plain, highly-portable system sans for everything a visitor actually reads and fills in — instructions, form labels, status text. This is a functional constraint as much as a stylistic one: the serif face does not reliably render Hebrew, so the sans stays the one body face across both languages rather than swapping per-locale.

**The One-Serif-Surface Rule.** Fraunces is self-hosted via `/static/fonts` (`main.py`'s `StaticFiles` mount, same pattern as the sibling review-engine project's dashboard font) rather than left to system-font fallback — the fallback chain above is a defensive floor, not the intended rendering. Its `unicode-range` is Latin-only by design: Hebrew display/label text falls through past Fraunces and the Latin system serifs to `"Noto Serif"`/`"Liberation Serif"`/`"DejaVu Serif"`, unchanged from before self-hosting. Never widen Fraunces onto body or i18n text.

### Hierarchy
- **Display** (700, 1.7rem, line-height ~1.15): the page `<h1>` only — set in the display serif, underlined in gold foil.
- **Label** (400, 0.95rem, letter-spacing 0.04em, uppercase): the stamp-grid title ("YOUR PASSPORT") and frame titles — display serif, used for anything with a certificate/heading feel even at small size.
- **Body** (400, 1rem, line-height 1.5): frame instructions and lede copy, in the sans body face.
- **Body Small** (400, 0.85rem): frame badges, frame detail lines (account/owner names, URLs), error text.

### Named Rules
**The One-Serif-Surface Rule.** The display serif appears only on headings and certificate-style labels (`h1`, `.frame-title`, `.stamp-slot .stamp-label`) — never on body copy, form fields, or any i18n string that must also render in Hebrew. This is why the sans stays the single body face across both languages rather than swapping per-locale.

## Layout

The desktop layout is a two-page spread (`.passport-spread`, max-width 1040px, centered): a fixed-width (300px) sticky stamp-grid "left page," a 3px gold-foil gutter, and a flexible-width (max 640px) "right page" (`main`) holding the active frame's form. Under `dir="rtl"`, the spread is not manually reversed — because the stamp grid is the first DOM child and `flex-direction: row` already follows inline direction, RTL places it on the reading-first (right) side automatically, a real physical mirror rather than a text-alignment flip. The gutter rule stays centered in both directions.

Below 860px the spread collapses to a single column: stamp grid first (as a compact 4-column overview), then the form below it, separated by a horizontal gold-foil rule replacing the vertical gutter. Below 480px the stamp grid stays 4-columns and header controls center instead of right-align.

The right page's ruled-paper background is two independent repeating gradients at different frequencies: wide-spaced horizontal baseline lines (every 2.1rem) and tighter vertical "chain lines" (every 5-6px). Revised 2026-09-07: frame cards (`details.frame`) are now opaque (Paper Cream) and lifted rather than transparent — the ruled paper shows only in the margins around and between cards, not through their form fields and text. The line opacity was also lowered (45%/30% color-mix against the previous 100%/55%) so the ambient texture stays a quiet paper-grain cue in those margins rather than competing for attention.

## Elevation & Depth

Revised 2026-09-07: frame cards now float, deliberately. The original flat-by-default system read as one continuous ruled sheet with seams cut into it rather than a set of distinct pages a visitor works through one at a time — corrected after direct user feedback on the live build. Inputs and the header/tooltip/popup overlays are unchanged; buttons and frame cards now carry real elevation.

### Shadow Vocabulary
- **Overlay** (`box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2)`): modal-style popups (theme/language pickers) that visually detach from the page.
- **Tooltip** (`box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15)`): the copy-confirmation tooltip.
- **Card Lift** (`box-shadow: 0 2px 10px rgba(0, 0, 0, 0.09), 0 1px 0 rgba(0, 0, 0, 0.04)`): every frame card, opaque and raised above the passport-page texture — the system's primary elevation cue.
- **Ink Press** (`box-shadow: inset 0 1px 0 rgba(255,255,255,0.16), 0 1px 2px rgba(0,0,0,0.22)`): primary action buttons, an embossed/pressed-ink depth rather than a flat fill; gains a thin gold ring (`0 0 0 2px color-mix(in srgb, var(--gold) 45%, transparent)`) on hover, echoing the gold-foil ceremonial accent without turning the button gold itself.

### Named Rules
**The Ink-Not-Elevation Rule (narrowed).** The stamp ring's blurred "bleed" layer is still the one place depth comes from ink soaking into paper rather than a lifted surface — that rule holds for the Stamp Grid specifically. It no longer describes the whole system: frame cards and primary buttons carry real elevation (Card Lift, Ink Press above), because in this world "floaty and opaque" reads as the passport's individual pages/stamps, not as a violation of a flat-by-default doctrine that was never load-bearing outside the Stamp Grid.

## Shapes

Radii are small and utilitarian, not a decorative rounding language: 3px on labeled task-action buttons (revised 2026-09-07 from 6px, tightened toward a stamped-block feel), 4px on the tightest icon chrome (copy-button, tooltip), 6px on inputs, stamp-slot cells, and frame cards (revised 2026-09-07 from 4px, alongside the move to an opaque/lifted card), and a full pill (999px) reserved for the header's control buttons (Start Over, theme, language) — the one place a fully rounded shape appears. Popups get a slightly larger 0.75rem (12px) radius, marking them as a distinct, floating layer rather than in-page chrome.

Borders are a consistent single hairline (`1px solid var(--border)`) throughout, except the stamp-grid cell's own 1.5px dashed border (signaling "not yet filled," a slot waiting for its stamp) which turns solid and stamp-colored once earned. The perforated corner tab (`main::before`) is built from four small radial-gradient "holes" plus a dashed border, using logical properties (`inset-inline-end`, `border-inline-start`) so it mirrors sides correctly under RTL without separate rules. The cloth cover edges use two overlaid diagonal repeating-gradients (a cross-hatch weave, not straight thread lines) plus a dashed gold-adjacent inset border a few pixels from the true edge, reading as bound cloth rather than a flat color bar.

## Components

### Buttons
- **Shape:** 3px radius on primary/secondary form buttons (revised 2026-09-07 from a plain 6px SaaS radius — tighter, closer to a stamped ink block than a rounded corporate button); full pill (999px) on the header's control buttons, unchanged.
- **Primary:** Control Blue background (`#2a4d8a`), white text, the Ink Press shadow (see Elevation & Depth), a certificate-style label — `font-family: var(--font-display)` (Fraunces), 600 weight, `0.05em` tracking, uppercase, `0.85rem` — instead of the body sans, `padding: 0.5rem 1.1rem`, min-height 2.5rem. Hover adds the thin gold ring; active presses down 1px; disabled drops the shadow and dims to 0.55 opacity. Used for every frame's validate/submit action.
- **Secondary (Change):** Paper Cream Deep background, Ledger Ink text, 1px border, same 3px radius and tracked-uppercase display-font label as Primary (no shadow — it stays visually quieter, appropriate to a "redo this" action); hover shifts the border to gold. Appears only once a frame is `done`.
- **Header controls:** pill-shaped, Paper Cream background, hairline border; hover shifts the border to Control Blue. No fill change on hover — the border is the only hover cue. Unchanged; deliberately a different register from the in-frame buttons (chrome, not task action).
- **Icon buttons (copy, password-reveal):** no background at rest, `border-radius: 4px`, transparent until hover, when they gain a muted-to-full text-color shift (and, for copy, a subtle background tint); a distinct `.copied` state turns the icon Status Ok green. Explicitly excluded from the Primary/Secondary treatment above (`:not(.password-toggle):not(.copy-btn)`) — they stay minimal, icon-only chrome.

### Named Rules
**The Certificate-Label Rule.** Every button a visitor acts on to move the wizard forward (Validate, Create, Deploy, Change) carries its label in the display serif, tracked and uppercase — the same lettering register as the stamp-grid title and frame headers — so the interactive layer reads as part of the same certificate world as the ceremonial one, not a bolted-on generic UI kit. Icon-only chrome buttons (copy, password-reveal, header controls) are exempt; this rule is for labeled task actions only.

### Inputs / Fields
- **Style:** Paper Cream Deep background, 1px Ledger Rule border, 6px radius, min-height 2.5rem, full width within the frame body.
- **Password field:** the reveal toggle sits inside the input via `position: relative`/`inset-inline-end`, so it flips sides automatically under RTL rather than needing a mirrored rule.
- **Focus:** relies on the browser's native focus ring (no custom focus treatment observed in the stylesheet) — a baseline-accessibility choice, not a designed glow.

### Cards / Containers (Frames)
- **Corner Style:** 6px radius (revised 2026-09-07 from 4px, alongside the move to an opaque, lifted card).
- **Background:** opaque Paper Cream (`var(--surface)`) — revised 2026-09-07 from transparent. The transparent version let the page's ruled/laid-paper texture bleed through every card's form fields and text, which read as one continuous busy sheet rather than a set of distinct pages; the texture now only shows in the margins around and between cards.
- **Shadow Strategy:** the Card Lift shadow (see Elevation & Depth) — a real soft lift, not the barely-there paper-edge hairline this world shipped with initially. Each card now reads as its own sheet floating above the passport page.
- **Border:** 1px solid Ledger Rule; locked frames additionally drop to 0.55 opacity and switch the cursor to not-allowed.
- **Internal Padding:** summary row `0.9rem 1.1rem`; body `0 1.1rem 1.1rem`.
- **Signature behavior:** a frame's body hinges open like a book cover on expand, and hinges shut in reverse on collapse (`rotateX(-20deg)` with `perspective(700px)` — perspective is required for a real 3D tilt, a bare `rotateX` with no perspective just renders as a flat vertical squash — plus a slight `translateY(-8px)` settle and an opacity fade from 0.3, transform-origin top-center, 600ms ease), not a generic accordion slide. Revised 2026-09 from an open-only, CSS-`animation`-driven 0.3s version: native `<details>` can't animate its own collapse, and the CSS-only open animation also proved unreliable depending on how `open` was toggled, so both directions are now driven explicitly via the Web Animations API (`wireFrameHingeAnimations()`), disabled under `prefers-reduced-motion`. Two load-bearing details found while tuning this: `.frame-body`'s own `padding-bottom`/`border-top` must animate to `0` in lockstep with `height` (animating `height` alone leaves them as a residual sliver that pops at the boundary), and each animation needs `fill: "forwards"` plus explicit cancellation of the frame's own previous animation (otherwise repeated toggling stacks conflicting held states).

### Navigation
- **Header controls** (Start Over / theme / language) are the page's only nav-adjacent chrome: right-aligned pill buttons (centered on narrow mobile), opening a small anchored popup (radio-group pattern) rather than a native `<select>`.

### The Stamp Grid (signature component)
A 2×4 grid of square cells (`.stamp-slot`, 1:1 aspect ratio), one per wizard frame, each holding an SVG with two layers: a flat, muted `.stamp-glyph` (a small generic icon — key, database cylinder, shield, asterisk, etc. — always visible, opacity 0.22 until earned) and a `.stamp-ring` group that stays fully transparent until the frame validates. The ring itself is three concentric hand-perturbed closed paths at different stroke widths and opacities (a blurred "bleed" copy, a crisp outer ring, a thinner inner ring) plus two small ink-spatter dots placed just outside the ring — reproducing how a real rubber stamp deposits ink unevenly, rather than a clean vector recolor. Each cell carries a fixed per-frame rotation (`--stamp-tilt`, roughly ±5–8°) and scale, baked in as inline custom properties, so stamps read as individually hand-applied rather than uniformly placed. On earning, the SVG plays a one-shot land animation (scale 2.2 → 0.9 → 1, 0.45s) and the cell's border/background tint to the stamp's own ink color; `prefers-reduced-motion` disables both the land animation and the hover transform.

### The Passport Page (signature component)
The right-page form surface (`main`) combines three material cues at once: the ruled-paper background (see Layout), a perforated corner tab in the top inline-end corner (see Shapes), and a hairline `border-inline-start` marking the page's spine edge (removed below the 860px collapse breakpoint, where there's no facing page left to bind against).

## Do's and Don'ts

### Do:
- **Do** keep gold foil (`--gold`) to ceremonial marks only — header underline, gutter rule, the passport label — never a clickable surface.
- **Do** build any new mirrored-layout element (like the perforated corner tab) with logical CSS properties (`inset-inline-*`, `border-inline-*`) so it flips correctly under `dir="rtl"` without a duplicated rule.
- **Do** let frame/card backgrounds stay transparent so the ruled-paper texture continues to read through new components added to `main`.
- **Do** give any new stamp-grid glyph a fixed per-frame tilt and scale (inline custom properties), matching the existing hand-applied irregularity — a perfectly upright, uniformly scaled new stamp would visibly break the set.
- **Do** keep the sans body face as the only face carrying i18n strings; reserve the display serif for headings/labels that don't need to render Hebrew.

### Don't:
- **Don't** reintroduce a numbered-stepper or percentage-progress affordance alongside the stamp grid — the direction contract explicitly rejects the horizontal-progress-bar category default this system replaces.
- **Don't** add box-shadow-based elevation to cards, inputs, or buttons as a default lift/hover effect — this system's few shadows are reserved for genuine overlays (popup, tooltip) and one hairline paper-edge cue, not general polish.
- **Don't** use any real trademarked service logo (GitHub's octocat, Supabase's logo, etc.) in a stamp glyph — glyphs are original generic marks (a key, a shield, interlocking rings) by design, per the direction contract.
- **Don't** manually reverse the passport spread's flex order for RTL (e.g. adding `flex-direction: row-reverse`) — the physical mirror already happens for free from DOM order under `row`, and an explicit reverse would un-mirror it back to LTR's layout.
