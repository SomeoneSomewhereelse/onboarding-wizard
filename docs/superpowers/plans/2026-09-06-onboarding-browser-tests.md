# Onboarding wizard browser tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real browser-behavior testing (Playwright for Python, sync API) to the onboarding-wizard project, and migrate three tests currently flagged in `ISSUES.md` as weak source-substring proxies to real behavioral checks.

**Architecture:** Three new synchronous pytest fixtures in `tests/conftest.py` (`live_app_url`, `browser`, `page`) boot the real FastAPI app via `uvicorn` in a background thread and drive one headless Chromium instance per test session. A new file, `tests/test_onboarding_page_browser.py`, holds plain `def test_...` functions (not `async def` — Playwright's sync API cannot run inside an active asyncio event loop) that navigate the live app, seed `sessionStorage`/intercept `/api/*` responses via `page.route()`, and assert on real DOM state.

**Tech Stack:** `playwright` (already a declared dev dependency, previously unused), `uvicorn.Server` (programmatic, not the CLI), the project's existing `pytest`/`pytest-xdist` setup.

**Spec:** `docs/superpowers/specs/2026-09-06-onboarding-browser-tests-design.md`

## Global Constraints

- No `pytest-playwright` plugin — DIY fixtures only, matching the existing `db`/`db_url` fixture style in `tests/conftest.py`.
- Every new browser test is a plain synchronous `def test_...` function — never `async def`, never decorated for `pytest-asyncio`.
- `live_app_url` depends on the existing session-scoped `db_url` fixture (needed only so `main.py`'s `lifespan` can boot — see spec section 2's correction) — never on the per-test `db` fixture (no truncation needed).
- Each of the three migrated tests **replaces** its existing substring-only counterpart outright — the old test is deleted in the same commit that adds its browser replacement, never left alongside it.
- New tests get an auto-applied `browser` marker (mirroring the existing `db` marker's `pytest_collection_modifyitems` convention) so `-m "not db and not browser"` stays a fast dev-loop subset.
- Never add a new `playwright` (or `pytest-playwright`) entry to `pyproject.toml` — it's already declared.
- `Dockerfile` is not touched — `uv sync --frozen --no-dev` already excludes every dev dependency, including `playwright`, from the deploy image.

---

### Task 1: Browser-test fixtures, marker, and CI/dev tooling

**Files:**
- Modify: `tests/conftest.py` (add `live_app_url`, `browser`, `page` fixtures; extend `pytest_collection_modifyitems`)
- Modify: `pyproject.toml` (add a `browser` marker declaration)
- Modify: `.github/workflows/ci.yml` (install the Chromium browser binary before running pytest)
- Modify: `README.md` (document the one-time local browser-binary install)
- Create: `tests/test_onboarding_page_browser.py` (smoke test only — the three real migrations are Tasks 2-4)

**Interfaces:**
- Produces: `live_app_url` fixture — session-scoped, depends on `db_url`, yields a `str` base URL like `"http://127.0.0.1:<port>"` serving the real `main:app`.
- Produces: `browser` fixture — session-scoped, yields a `playwright.sync_api.Browser` (headless Chromium).
- Produces: `page` fixture — function-scoped, depends on `browser` and `live_app_url`, yields a `playwright.sync_api.Page` already able to `.goto(live_app_url)`. Every subsequent task's tests consume `page` and `live_app_url` by these exact fixture names.

- [ ] **Step 1: Write the failing smoke test**

Create `tests/test_onboarding_page_browser.py`:

```python
"""Real browser-behavior tests for static/index.html, using Playwright's
sync API against the actual running FastAPI app (see live_app_url/browser/
page fixtures in tests/conftest.py). Plain `def test_...` functions, not
`async def` -- Playwright's sync API refuses to run inside an active
asyncio event loop, which every async test in this project runs inside
(asyncio_mode = "auto"). Complements, not replaces, the source-substring
convention every other onboarding-page test file uses (see
tests/test_onboarding_page.py's own module docstring) -- only tests that
need to verify real DOM/JS behavior belong here."""
from __future__ import annotations


def test_page_title_loads_over_a_real_browser(page, live_app_url):
    page.goto(live_app_url)
    assert page.title() == "Set up your own reviewer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_onboarding_page_browser.py -v`
Expected: FAIL with `fixture 'page' not found` (or `'live_app_url' not found`) — the fixtures don't exist yet.

- [ ] **Step 3: Add the fixtures to `tests/conftest.py`**

Add these imports near the top of `tests/conftest.py` (alongside the existing `import os`/`from urllib.parse import urlsplit`):

```python
import socket
import threading
import time

from cryptography.fernet import Fernet
```

Add these fixtures after the existing `db_query` fixture (i.e. after the line `    return conn.execute(sql, params).fetchall()` and before `def _touches_shared_postgres`):

```python
def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def live_app_url(db_url):
    """Boots the real FastAPI app (main:app) via uvicorn in a background
    thread, bound to a free local port -- for Playwright's browser fixture
    to navigate against. Depends on db_url purely so main.py's lifespan can
    open a real Postgres connection and boot at all (it raises RuntimeError
    otherwise); individual browser tests never touch this database
    directly for their own assertions (they intercept the specific
    /api/* responses they need via page.route()), so this never depends on
    the per-test `db` fixture's truncation. Settings are mutated directly
    (not via monkeypatch) since this is a one-time, session-scoped setup
    with nothing else to restore."""
    import uvicorn

    from config import settings as onboarding_settings

    onboarding_settings.database_url = db_url
    onboarding_settings.onboarding_session_encryption_key = Fernet.generate_key().decode()

    import main as onboarding_main

    port = _free_local_port()
    server = uvicorn.Server(
        uvicorn.Config(onboarding_main.app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        raise RuntimeError("live_app_url: uvicorn server did not start within 10s")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser():
    """One headless Chromium instance for the whole test session. Sync
    Playwright API deliberately, not async -- see this file's module-level
    reasoning in the design doc (docs/superpowers/specs/2026-09-06-onboarding-browser-tests-design.md,
    section 3): the async API cannot run inside an active asyncio event
    loop, which every async test in this project runs inside."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(headless=True)
        yield chromium
        chromium.close()


@pytest.fixture
def page(browser, live_app_url):
    """A fresh incognito-style browser context and page per test -- so
    sessionStorage/cookies never leak between tests, matching the
    isolation every other fixture in this file already gives."""
    context = browser.new_context()
    new_page = context.new_page()
    yield new_page
    context.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_onboarding_page_browser.py -v`
Expected: PASS

- [ ] **Step 5: Auto-apply a `browser` marker**

In `tests/conftest.py`, add this function right after `_touches_shared_postgres`:

```python
def _uses_real_browser(item: pytest.Item) -> bool:
    """True if item's fixture closure includes `page` -- the fixture every
    real browser test requests, directly or (via live_app_url -> db_url)
    transitively also picking up the existing `db` marker/xdist_group
    below, which is intentional: it keeps browser tests grouped onto the
    same xdist worker as other Postgres-touching tests rather than having
    multiple workers each spin up their own live server + Chromium
    instance."""
    return "page" in item.fixturenames
```

Then change the `pytest_collection_modifyitems` function's loop body from:

```python
    for item in items:
        if _touches_shared_postgres(item):
            item.add_marker(pytest.mark.db)
            item.add_marker(pytest.mark.xdist_group(name="db"))
```

to:

```python
    for item in items:
        if _touches_shared_postgres(item):
            item.add_marker(pytest.mark.db)
            item.add_marker(pytest.mark.xdist_group(name="db"))
        if _uses_real_browser(item):
            item.add_marker(pytest.mark.browser)
```

- [ ] **Step 6: Declare the marker in `pyproject.toml`**

In the `[tool.pytest.ini_options]` section's `markers` list, add a new entry alongside the existing `db`/`xdist_meta` ones:

```toml
    "browser: drives a real headless Chromium instance via Playwright against the live app (auto-applied by tests/conftest.py's pytest_collection_modifyitems hook, not meant to be added by hand) -- slower than the rest of the suite, excluded from the fast-iteration `-m` filter",
```

- [ ] **Step 7: Run the full suite to confirm nothing else broke**

Run: `uv run pytest -v`
Expected: PASS (existing tests unaffected, new smoke test passes, `browser`/`db` markers both present on the new test — confirm with `uv run pytest tests/test_onboarding_page_browser.py -v -m browser --collect-only`, expected to show 1 test collected)

- [ ] **Step 8: Add the Chromium install step to CI**

In `.github/workflows/ci.yml`, add this step after "Install dependencies" and before "Lint (ruff)":

```yaml
      - name: Install Playwright's Chromium browser
        run: uv run playwright install --with-deps chromium
```

- [ ] **Step 9: Document the local one-time setup in README**

In `README.md`'s "Local development" section, right after the existing ` ```bash\nuv sync --all-extras --dev\ncp .env.example .env\n``` ` code block, add:

```markdown
The browser-behavior tests (`tests/test_onboarding_page_browser.py`) need
Chromium's binary installed once per machine:

```bash
uv run playwright install chromium
```
```

- [ ] **Step 10: Commit**

```bash
git add tests/conftest.py tests/test_onboarding_page_browser.py pyproject.toml .github/workflows/ci.yml README.md
git commit -m "Add Playwright-based browser test fixtures and CI/dev tooling"
```

---

### Task 2: Migrate the UptimeRobot blocked-state test

**Files:**
- Modify: `tests/test_onboarding_page_browser.py` (add the real behavior test)
- Modify: `tests/test_onboarding_page.py` (delete the substring-only test it replaces)

**Interfaces:**
- Consumes: `page`/`live_app_url` fixtures from Task 1.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_onboarding_page_browser.py`:

```python
def test_uptime_pinger_blocked_state_reflects_render_service_url_presence(page, live_app_url):
    """Replaces tests/test_onboarding_page.py's
    test_frame5_blocked_state_reads_the_forward_contract_key, which only
    checked that the relevant function/constant names existed in the page
    source -- this checks the actual resulting visibility."""
    page.goto(live_app_url)

    page.evaluate("sessionStorage.removeItem('onboarding.renderServiceUrl')")
    page.evaluate("refreshUptimePingerBlockedState()")
    assert page.is_visible("#uptime-pinger-blocked-section")
    assert not page.is_visible("#uptime-pinger-form-section")

    page.evaluate(
        "sessionStorage.setItem('onboarding.renderServiceUrl', 'https://example.onrender.com')"
    )
    page.evaluate("refreshUptimePingerBlockedState()")
    assert not page.is_visible("#uptime-pinger-blocked-section")
    assert page.is_visible("#uptime-pinger-form-section")
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_onboarding_page_browser.py -v -k uptime_pinger_blocked`
Expected: PASS (the underlying `refreshUptimePingerBlockedState()` behavior already exists in `static/index.html` — this is a new *test*, not a new feature)

- [ ] **Step 3: Delete the substring test it replaces**

In `tests/test_onboarding_page.py`, delete this entire test function:

```python
async def test_frame5_blocked_state_reads_the_forward_contract_key():
    """sub-project 6 (not yet built) is obligated to write this key on its
    own completion -- see design doc section 3's forward contract. Frame 5
    only ever reads it."""
    client = await _client()
    body = (await client.get("/")).text
    assert 'const RENDER_SERVICE_URL_KEY = "onboarding.renderServiceUrl";' in body
    assert "function refreshUptimePingerBlockedState" in body
    assert "sessionStorage.getItem(RENDER_SERVICE_URL_KEY)" in body
```

- [ ] **Step 4: Run both test files to confirm the suite is still green**

Run: `uv run pytest tests/test_onboarding_page.py tests/test_onboarding_page_browser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_onboarding_page_browser.py tests/test_onboarding_page.py
git commit -m "Migrate UptimeRobot blocked-state test to real browser behavior"
```

---

### Task 3: Migrate the Supabase restore-from-session polling test

**Files:**
- Modify: `tests/test_onboarding_page_browser.py` (add the real behavior test)
- Modify: `tests/test_onboarding_page.py` (delete the substring-only test it replaces)

**Interfaces:**
- Consumes: `page`/`live_app_url` fixtures from Task 1.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_onboarding_page_browser.py` (add `import json` at the top of the file alongside the existing `from __future__ import annotations`):

```python
def test_restore_from_session_resumes_polling_for_a_supabase_project_without_a_connection_string(
    page, live_app_url
):
    """Replaces tests/test_onboarding_page.py's
    test_restore_from_session_resumes_polling_for_a_ref_without_a_connection_string,
    which only checked that three unrelated strings each appeared
    somewhere in the page source, not that they were wired together in
    the same code branch -- this drives the real restore-from-session
    flow and checks the actual resulting UI."""
    session_body = {
        "frames": {
            "supabase": {
                "complete": False,
                "provisioning": True,
                "display": {"ref": "abcdefghijklmnopqrst", "name": "Test Project"},
            }
        }
    }

    def handle_session(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(session_body),
        )

    def handle_project_status(route):
        # Any non-terminal status -- pollUntilReady() just reschedules
        # itself 5s later on "pending", which this test doesn't wait for.
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"valid": True, "status": "COMING_UP"}),
        )

    page.route(f"{live_app_url}/api/session", handle_session)
    page.route(f"{live_app_url}/api/supabase/project-status", handle_project_status)

    page.goto(live_app_url)

    page.wait_for_selector("#supabase-provisioning-section", state="visible")
    assert not page.is_visible("#supabase-connect-section")
    assert not page.is_visible("#supabase-org-section")
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_onboarding_page_browser.py -v -k restore_from_session_resumes_polling`
Expected: PASS

- [ ] **Step 3: Delete the substring test it replaces**

In `tests/test_onboarding_page.py`, delete this entire test function:

```python
async def test_restore_from_session_resumes_polling_for_a_ref_without_a_connection_string():
    client = await _client()
    body = (await client.get("/")).text
    assert "showSupabaseProvisioning()" in body
    assert "pollUntilReady(Date.now(), supabasePollGeneration)" in body
    assert "function restoreFromSession" in body
```

- [ ] **Step 4: Run both test files to confirm the suite is still green**

Run: `uv run pytest tests/test_onboarding_page.py tests/test_onboarding_page_browser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_onboarding_page_browser.py tests/test_onboarding_page.py
git commit -m "Migrate Supabase restore-from-session polling test to real browser behavior"
```

---

### Task 4: Migrate the RTL language-switch test

**Files:**
- Modify: `tests/test_onboarding_page_browser.py` (add the real behavior test)
- Modify: `tests/test_onboarding_i18n.py` (delete the substring-only test it replaces)

**Interfaces:**
- Consumes: `page`/`live_app_url` fixtures from Task 1.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_onboarding_page_browser.py`:

```python
def test_language_switch_sets_dir_for_rtl(page, live_app_url):
    """Replaces tests/test_onboarding_i18n.py's test of the same name,
    which asserted an exact literal source line rather than the actual
    resulting behavior -- more brittle to a harmless refactor of that
    line, and only a proxy for whether dir actually changes."""
    page.goto(live_app_url)
    assert page.get_attribute("html", "dir") == "ltr"

    page.click("#langToggleBtn")
    page.check('input[name="lang"][value="he"]')

    assert page.get_attribute("html", "dir") == "rtl"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_onboarding_page_browser.py -v -k language_switch_sets_dir_for_rtl`
Expected: PASS

- [ ] **Step 3: Delete the substring test it replaces**

In `tests/test_onboarding_i18n.py`, delete this entire test function:

```python
async def test_language_switch_sets_dir_for_rtl():
    client = await _client()
    body = (await client.get("/")).text
    assert 'document.documentElement.setAttribute("dir", lang === "he" ? "rtl" : "ltr")' in body
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS (all tests, including the three from Tasks 2-4 now living only in `tests/test_onboarding_page_browser.py`)

- [ ] **Step 5: Run ruff**

Run: `uv run ruff check .`
Expected: All checks passed

- [ ] **Step 6: Commit**

```bash
git add tests/test_onboarding_page_browser.py tests/test_onboarding_i18n.py
git commit -m "Migrate RTL language-switch test to real browser behavior"
```

---

### Task 5: Close out the ISSUES.md Parked Issue and confirm the Docker deploy image is unaffected

**Files:**
- Modify: `ISSUES.md` (close the now-resolved Parked Issue)

- [ ] **Step 1: Update the Parked Issues entry**

In `ISSUES.md`, find this entry (added earlier this session):

```
### Spec section 6 (onboarding-uptimerobot-frame-design.md) described a browser-behavior test this project's suite cannot execute
```

Add an `- **Update (<today's date>):** closed —` line beneath its existing `**Follow-up:**` line, stating that `tests/test_onboarding_page_browser.py` now covers the blocked-state behavior via Playwright's sync API (see `docs/superpowers/specs/2026-09-06-onboarding-browser-tests-design.md`), and naming the two other tests migrated alongside it.

- [ ] **Step 2: Confirm the Docker deploy image still builds and boots**

Run: `docker build -f Dockerfile .`
Expected: Build succeeds — `uv sync --frozen --no-dev` excludes `playwright` and every other dev dependency, so this task's changes (all dev/test-only) cannot affect the deploy image. This matches this project's CLAUDE.md convention of confirming the deploy image after merging to `main`.

- [ ] **Step 3: Commit**

```bash
git add ISSUES.md
git commit -m "Close ISSUES.md's browser-test Parked Issue"
```
