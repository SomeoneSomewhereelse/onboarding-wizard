# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is a visitor who wants to run their own instance of a
separate PR-review bot+dashboard product (a sibling project, deployed via
Render, backed by Supabase). They arrive at this wizard to provision that
deployment themselves: create/validate a GitHub App, provision a Supabase
project, supply an LLM provider credential, set up an UptimeRobot keep-warm
monitor, and trigger the final Render deploy.

This population is **mixed, skewing less technical** — not all visitors
already have accounts with GitHub, Render, Supabase, an LLM provider, or
UptimeRobot, and not all are fluent in what a "GitHub App," "Personal
Access Token," or "service account key" is. The wizard should lean toward
in-line explanation, reassurance, and step-by-step hand-holding copy at
each frame, not just terse pass/fail validation — the visitor may be
encountering several of these concepts for the first time in the same
session.

## Product Purpose

A self-service setup wizard that walks a visitor through provisioning
their own bot+dashboard deployment end to end, in their own browser, using
only their own credentials. It exists so the sibling review-engine
project doesn't require its maintainers to manually onboard every new
self-hoster — the wizard automates validation, cross-service wiring, and
the final deploy trigger.

Success is a visitor reaching a live, working bot+dashboard URL at the end
of the flow, with every external service (GitHub App, Supabase project,
LLM provider, UptimeRobot monitor, Render service) correctly configured
and wired together — without ever having to read the sibling project's own
setup documentation directly.

## Positioning

Unlike a written setup guide or a one-off provisioning script, this wizard
*validates as it goes*: each step calls the real external API to confirm a
credential or configuration is actually correct (not just present) before
letting the visitor proceed, and a doctor-style checklist catches
hand-entered configuration mistakes (e.g. a miskeyed GitHub App permission)
that a copy-paste setup guide cannot.

## Operating Context

The flow is a sequential, accordion-style set of frames, each unlocking
only once its prerequisite frames are done:

1. Render API key
2. Render service creation
3. GitHub App creation + validation (fully manual App creation/install on
   GitHub's own site — this wizard never automates navigation to
   github.com, for reasons documented in CLAUDE.md)
4. Supabase project provisioning (visitor-pasted Personal Access Token)
5. LLM provider credential (Gemini, Groq, or Vertex — model fetched live
   from the provider's catalog, never hardcoded)
6. UptimeRobot keep-warm monitor
7. Dashboard login credentials
8. Finish & Deploy (bulk env-var push + real Render deploy trigger)

A visitor may reload mid-flow, come back later within the session TTL (4
hours), or explicitly "Start over." Progress is held server-side
(`session_store.py`), not in browser storage, specifically because mobile
browsers were observed destroying `sessionStorage` mid-flow (see
CLAUDE.md's session-redesign history).

## Capabilities and Constraints

- Every visitor-supplied credential is relayed to the relevant external
  API for validation/action and is never held by this service as a
  long-lived operator credential — see CLAUDE.md's secret-handling rules,
  which are a hard constraint on any UI or copy change (never surface a
  credential value in the DOM/logs/errors beyond what's already permitted).
- No URL referencing `github.com` may appear anywhere on the page (a
  standing constraint from a real incident — see CLAUDE.md).
- The wizard is a single static page (`static/index.html`) served by a
  FastAPI backend; there is currently no framework/build step and no
  existing `StaticFiles` mount for additional assets (fonts, images) —
  adding one is a real backend change requiring explicit confirmation, not
  a given.
- Frame unlock/relock logic is dependency-based (`FRAME_DEPENDENTS`), not
  purely positional — changing an earlier frame's data may relock several
  specific later frames, not just "everything after it."

## Brand Commitments

None. There is no fixed product name, logo, voice, or palette — the
current page title ("Set up your own reviewer") and gray, unstyled-looking
UI are a functional first pass, not a brand commitment. Visual identity,
including naming, is fully open for design work to decide.

## Evidence on Hand

No real screenshots, testimonials, case studies, or marketing assets exist
for this product yet — it has one existing implementation
(`static/index.html`) with no accompanying design documentation. Do not
fabricate any of the above.

## Product Principles

1. **Validate, don't just collect.** Every credential the visitor provides
   is checked against the real external service before the wizard treats
   the step as done.
2. **Explain, don't assume.** Given the mixed/less-technical audience,
   each step should teach enough about the external service in question
   for a first-time visitor to succeed, not just report pass/fail.
3. **Never hold what isn't needed.** Visitor credentials are relayed and
   persisted only as long as the flow requires, and only where documented
   in CLAUDE.md — this is a trust-sensitive product handling real
   third-party API keys.
4. **Recoverable, not fragile.** A visitor can reload, resume, or start
   over without losing already-validated progress or corrupting
   partially-completed state.
5. **Momentum over perfection.** The sequential unlock model exists to
   give the visitor a clear sense of progress through a long, multi-service
   setup — the design should reinforce "one thing at a time, moving
   forward," not overwhelm with the full eight-step scope at once.

## Accessibility & Inclusion

No formally mandated standard. Follow general good-practice accessibility
(contrast, keyboard navigation, visible focus states) as a baseline given
the mixed-technical-skill audience already documented above.
