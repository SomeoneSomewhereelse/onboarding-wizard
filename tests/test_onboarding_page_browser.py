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
