# Onboarding wizard: real browser-behavior tests via Playwright for Python

## 1. Problem and context

`static/index.html` is a single-page wizard with several thousand lines of
inline JS driving frame locking/unlocking, `sessionStorage` continuity state,
and relay `fetch()` calls. Every test of this page
(`tests/test_onboarding_page.py`, `tests/test_onboarding_i18n.py`, and
siblings) is a content-substring/structural check against the served HTML
source — this repo's established convention (see those files' own module
docstrings), chosen because there was no JS execution harness available.
That convention cannot verify *behavior*: it confirms a function or markup
id exists in the source, never that the browser actually does the right
thing when it runs.

This gap was flagged as an open item in `ISSUES.md`'s Parked Issues: a
2026-08-27 spec
(`docs/superpowers/specs/2026-08-27-onboarding-uptimerobot-frame-design.md`
section 6) described a test — "mocked `sessionStorage` without the
Render-URL key renders the blocked message, no form" — that the project's
suite structurally could not execute. Two more existing tests were
separately flagged, in the same Parked Issues section, as weak proxies for
real behavior: `test_restore_from_session_resumes_polling_for_a_ref_without_a_connection_string`
(checks three strings appear somewhere in the page, not that they're in the
same code branch) and `test_language_switch_sets_dir_for_rtl` (pins an exact
source line rather than the actual resulting `dir` behavior, more brittle
than necessary).

## 2. Confirmed decisions

- **Playwright for Python, not a Node.js toolchain.** `pyproject.toml`
  already declares `playwright>=1.62.0` as a dev dependency — a carryover
  from the pre-split monorepo (also present, and equally unused, in the
  sibling `~/pr-review-bot` repo's own `pyproject.toml`) that this project
  never actually wired up. Playwright's Python package drives a real
  headless browser directly from pytest; adopting it means zero new
  toolchain (no `package.json`, no jsdom/vitest, nothing Node-based) and
  fits the project's existing uv/pytest-only workflow exactly. This also
  retires the dependency's current dead-weight status.
- **No `pytest-playwright` plugin.** That plugin's value (CLI flags like
  `--headed`, auto-wired `page`/`browser`/`context` fixtures) isn't worth a
  second dependency for the handful of tests this pass adds — three small,
  explicit fixtures in `tests/conftest.py`, in the same DIY style as the
  existing `db`/`db_url` fixtures, cover it.
- **Real FastAPI app, not a bare static-file server.** The live test server
  is the actual `main:app` (via `uvicorn` in a background thread on an
  ephemeral local port), not `static/index.html` served in isolation —
  closest to how the app is actually served, and leaves the door open for a
  future browser test that needs a real relay endpoint's real routing (not
  just its response shape).
- **Route interception for test-relevant responses, but the live app still
  needs a real (test) Postgres to boot.** Any test needing an `/api/*`
  response uses Playwright's `page.route()` to intercept the request and
  return a canned JSON body, rather than exercising the real Postgres-backed
  session store's business logic — keeping individual test *assertions*
  consistent with this project's "no real network call in the test suite"
  convention. **Correction (caught during plan-writing, before any code was
  written):** the spec originally claimed browser tests need no
  `db`/`testcontainers` fixture *at all*. That's wrong at the fixture-setup
  level: `main.py`'s `lifespan` eagerly calls `session_store.init_pool()`
  (a real Postgres connection + schema DDL) and raises `RuntimeError` if
  `DATABASE_URL`/`ONBOARDING_SESSION_ENCRYPTION_KEY` are unset or
  unreachable, so the live server itself cannot start at all without a real
  reachable Postgres and a valid Fernet key — independent of whether any
  single test's own assertions touch the database. See section 3's
  `live_app_url` fixture for the corrected shape (it depends on the
  existing `db_url` fixture for boot purposes only, never the per-test `db`
  fixture's truncation).
- **Replace, don't duplicate.** The three tests named in section 4 below
  are converted outright — their substring-check version is deleted, not
  kept alongside the new browser version. Every other existing test in
  `tests/test_onboarding_page.py`/`tests/test_onboarding_i18n.py` and
  friends is untouched; the substring-check convention remains this
  project's default for everything not migrated here.
- **A new `browser` pytest marker**, auto-applied via
  `pytest_collection_modifyitems` (mirroring the existing `db` marker's
  `_touches_shared_postgres`-style detection) to any test using the new
  `page` fixture — keeps `-m "not db and not browser"` a fast dev-loop
  subset as the browser-test count grows.

## 3. Architecture and test flow

Three new fixtures in `tests/conftest.py`:

- **`live_app_url`** (session-scoped, depends on the existing `db_url`
  fixture): monkeypatches `config.settings.database_url` to `db_url` and
  `config.settings.onboarding_session_encryption_key` to a freshly
  generated Fernet key (needed purely so `main.py`'s `lifespan` boots
  without raising — see the correction in section 2), then starts
  `uvicorn.Server` running `main:app` in a background thread, bound to
  `127.0.0.1` on an OS-assigned free port (port `0`), waits for it to
  accept connections, yields the base URL, and shuts the server down at
  session end. Never depends on the per-test `db` fixture — no table
  truncation needed, since route interception keeps test assertions off
  the real session store's data.
- **`browser`** (session-scoped): launches one headless Chromium instance
  via **Playwright's sync API**
  (`playwright.sync_api.sync_playwright()`), closed at session end. The
  sync API, not the async one, is a deliberate correction from an earlier
  draft of this section: this project's existing tests are all `async def`
  under `pytest-asyncio`'s `asyncio_mode = "auto"`, but Playwright's sync
  API refuses outright to run from inside a thread with an active asyncio
  event loop — exactly what every existing async test runs inside. Rather
  than fight `pytest-asyncio`'s per-test event-loop scoping to make the
  *async* Playwright API's session-scoped fixtures work, the three new
  fixtures and every test in the new file are **plain, synchronous** (no
  `async`/`await`, no `asyncio_mode` involvement at all) — pytest runs sync
  and async tests side by side in the same session without conflict, so
  this is purely a per-file style choice, not a project-wide one.
- **`page`** (function-scoped): opens a fresh incognito-style browser
  context and page from `browser` against `live_app_url`, yields it, and
  closes the context after the test — so `sessionStorage`/cookies never
  leak between tests, matching the isolation every other test fixture in
  this file already gives.

A typical migrated test: use `page.route("**/api/session", ...)` (if it
needs a backend response) or `page.evaluate(...)` (if it only needs to seed
`sessionStorage`) *before* navigating, `page.goto(live_app_url)`, interact
with real UI elements (`page.click(...)`, `page.select_option(...)`), then
assert on real, live DOM state (`page.is_visible(...)`,
`page.eval_on_selector(...)`) — never on the page's source text.

## 4. Scope: which tests move, and where

New file: `tests/test_onboarding_page_browser.py`, using the fixtures above.
Its tests are plain synchronous `def test_...` functions (see section 3's
sync-API correction) — `pytest-asyncio`'s `asyncio_mode = "auto"` only wraps
`async def` tests, so it has no effect on this file and needs no
configuration change.

Three tests move from substring checks to real browser behavior, each
replacing (not duplicating) its existing substring-only counterpart:

1. **UptimeRobot blocked state** (the item `ISSUES.md` flagged as open):
   seed `sessionStorage` without `onboarding.renderServiceUrl`, navigate,
   assert `#uptime-pinger-blocked-section` is visible and
   `#uptime-pinger-form-section` is not; repeat with the key present and
   assert the inverse. Replaces the source-presence assertions currently in
   `tests/test_onboarding_page.py` around
   `uptime-pinger-blocked-section`/`uptime-pinger-form-section`/
   `refreshUptimePingerBlockedState`.
2. **Supabase restore-from-session polling**: intercept `GET /api/session`
   to return a canned response shaped like "a project ref exists, no
   `database_url` yet," navigate, assert the actual polling UI element
   becomes visible — replaces
   `test_restore_from_session_resumes_polling_for_a_ref_without_a_connection_string`'s
   three-separate-strings-anywhere-in-the-page check.
3. **RTL language switch**: click the real language selector, assert
   `document.documentElement`'s `dir` attribute — replaces
   `test_language_switch_sets_dir_for_rtl`'s exact-literal-source-line
   assertion with a check of the actual resulting behavior (fixes both the
   brittleness and the weak-proxy problem the two `ISSUES.md` entries
   separately raised).

Everything else in `tests/test_onboarding_page.py`,
`tests/test_onboarding_i18n.py`, and `tests/test_dashboard_page.py` is
untouched.

## 5. Tooling / CI changes

- `.github/workflows/ci.yml`: one new step, `uv run playwright install
  chromium --with-deps`, inserted between "Install dependencies" and "Test
  (pytest)".
- `README.md`'s local-development section gets the same one-liner as a
  one-time setup step, next to the existing `uv sync --all-extras --dev`
  instruction.
- `Dockerfile` is unaffected — it runs `uv sync --frozen --no-dev`, so
  `playwright` (a dev-only dependency) and its browser binary are never
  part of the deploy image.
- No change to `pyproject.toml`'s dependency list — `playwright>=1.62.0`
  is already declared; this pass is what starts actually using it.

## 6. Out of scope

- Migrating any test beyond the three named in section 4. Every other
  substring-check test stays as-is; the convention itself isn't being
  replaced project-wide, just supplemented for cases where real behavior
  verification is the concrete gap.
- `pytest-playwright` or any other Playwright test-runner plugin.
- Non-Chromium browsers (Firefox/WebKit) — this project has no
  cross-browser-compatibility requirement to justify the added CI time.
- Visual/screenshot regression testing — a different feature entirely, not
  what this gap is about.
- Removing the also-dead `playwright` dependency from `~/pr-review-bot` — a
  separate repo with its own conventions; the user has decided to keep it
  there (it's used ad hoc for debugging, outside that repo's own test
  suite) and it's out of scope for this repo's spec regardless.
