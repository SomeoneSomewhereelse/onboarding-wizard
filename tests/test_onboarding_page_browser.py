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


def test_uptime_pinger_blocked_state_reflects_render_service_url_presence(page, live_app_url):
    """Replaces tests/test_onboarding_page.py's
    test_frame5_blocked_state_reads_the_forward_contract_key, which only
    checked that the relevant function/constant names existed in the page
    source -- this checks the actual resulting visibility.

    frame-uptime-pinger starts locked/closed (a native <details> renders no
    content for a closed section, so is_visible() on anything inside it is
    always False regardless of the display style toggle this test cares
    about) -- unlockFrame() is the real function that opens it, and already
    calls refreshUptimePingerBlockedState() itself as part of unlocking."""
    page.goto(live_app_url)

    page.evaluate("sessionStorage.removeItem('onboarding.renderServiceUrl')")
    page.evaluate("unlockFrame('uptime-pinger')")
    assert page.is_visible("#uptime-pinger-blocked-section")
    assert not page.is_visible("#uptime-pinger-form-section")

    page.evaluate(
        "sessionStorage.setItem('onboarding.renderServiceUrl', 'https://example.onrender.com')"
    )
    page.evaluate("refreshUptimePingerBlockedState()")
    assert not page.is_visible("#uptime-pinger-blocked-section")
    assert page.is_visible("#uptime-pinger-form-section")
