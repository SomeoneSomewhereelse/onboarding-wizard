---
version: 1
slug: "static-index-html"
primary_target: "static/index.html"
related_targets: []
---

## Scope

Whole wizard page (`static/index.html`): all 8 frames (Render key, Render
service, GitHub App, Supabase, LLM provider, UptimeRobot, Dashboard login,
Finish & Deploy) plus shared chrome (theme toggle, language toggle,
header). Mode: Operate. Functionality is fair game to change, not just
restyled in place — same job (validate credentials, unlock frames in
order, push env vars, trigger deploy), interaction details are open.

## Audience and job

A mixed, skewing-less-technical visitor provisioning their own bot
deployment. Many are meeting "GitHub App," "Personal Access Token," or
"service account key" for the first time. Copy must teach, not just
validate pass/fail. Primary task: get every external service correctly
configured and wired, ending at a live dashboard URL.

## Constraints (hard, from CLAUDE.md)

- No `github.com` URL/link anywhere on the page.
- Visitor credentials: relay-only, never logged, never echoed beyond a
  boolean/enum/short display name.
- Sequential frame-unlock/relock logic (`FRAME_DEPENDENTS`) is a real
  dependency graph, not purely positional — preserve its behavior even if
  interaction chrome changes.
- Existing fetch-endpoint-audit tests (one exit path per credential) must
  still pass — a redesign must not add second fetch call sites.
- Must support English (LTR) and Hebrew (RTL), light and dark theme.
- A static-asset mount now exists (`main.py`'s `app.mount("/static/fonts", ...)`,
  added 2026-09-07 with the user's explicit confirmation, same pattern as
  the sibling review-engine project's dashboard font). It serves only
  self-hosted font files — do not grow it into a general asset dump
  without the same kind of explicit sign-off a new backend surface
  deserves.

## Direction contract

THESIS: A setup wizard is a passport control desk, not a stepper — the
visitor is not "filling out a form," they are being cleared, one gate at a
time, to reach the far side (a live deployment). The category default this
refuses is a horizontal progress bar of gray circles.

OWN-WORLD: An open passport booklet spanning the viewport. Left page holds
a 2×4 stamp grid (one cell per frame — Render key, Render service, GitHub
App, Supabase, LLM provider, UptimeRobot, Dashboard login, Finish &
Deploy), each cell blank until its frame validates, then filled with a
hand-inked rubber-stamp mark (unique per frame, e.g. a small wrench for
Render, an octocat-free generic key glyph for GitHub, etc. — no real
trademarked logos). Right page holds the active frame's form on cream
laid paper with a visible perforated corner tab. Cloth-bound cover edges
frame the far left/right margins at rest. Palette: cover navy #1f2a44,
paper cream #efe6cf, stamp red #8a1f2b, stamp blue #2a4d8a, gold foil
#c9a227 (used sparingly, headers/dividers only). Type: a humanist serif
for stamp/certificate-style headers, a plain workhorse sans for body/form
text and all i18n strings (serif faces do not reliably carry Hebrew;
sans stays the Hebrew-safe body face throughout).

STORY: the visitor opens their passport to a blank left page and a live
right page; each validated credential lands a stamp; the booklet visibly
fills up left to right, top to bottom, across the whole session, so
progress is legible from the stamp grid alone even before reading any
copy.

FIRST VIEWPORT: full-bleed passport spread. Left third: navy cover edge,
then the cream left page with the 2x4 stamp grid, generous margins.
Center-right: the cream right page holding the current frame's heading,
explanatory copy, and form fields on ruled baseline lines (like a form
printed on lined paper). A slim gold foil rule separates the two pages
down the center gutter. In RTL (Hebrew), the whole spread mirrors: stamp
grid moves to the right page, active-frame page to the left, gutter rule
stays centered — this is a real layout mirror, not just text alignment.

FORM: model-pick (customs/immigration passport control), seed key
9d921a68.

FINISH: unreviewed and undocumented is unfinished; this build ends with
the finish review, the verdict, DESIGN.md, and every shipping raster
carrying its provenance.

## Unresolved decisions

- Exact per-frame stamp glyph designs (8 small ink-stamp marks) — author
  as simple geometric/generic marks, nothing resembling a real trademarked
  logo (GitHub's octocat, Supabase's logo, etc. are off-limits).
- Whether the stamp grid is a static SVG per frame or an inline-drawn
  mark; decide during build based on what stays crisp at mobile width.
- Mobile layout: the two-page spread must collapse to a single column
  (stamp grid above, active frame below) — the passport metaphor should
  survive the collapse, not just disappear into a generic mobile stack.

## Build-path note (2026-09-07)

Comp `.impeccable/mocks/comp-1.png` was approved as the direction's decision
comp, but the user explicitly downgraded its authority from a measured
pixel-diff spec to a north-star reference: "Comp as strong north star,
code-led execution." Reason: this surface has 8 materially different
frame states, 2 languages (including RTL), 2 themes, and mobile — a single
static comp cannot represent all of them, and region-by-region pixel
diffing against one illustrative placeholder state (invented "CURRENT
STEP" text, a decorative ruled line) would measure fidelity to an AI
artifact's own guesses rather than to real functional UI. The build
proceeds code-led: palette, material language, and composition come from
the comp and the Direction contract above; the finish reviewer audits
those promises in behavior, not via `comp-diff` region scoring.
