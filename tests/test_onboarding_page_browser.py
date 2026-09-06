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

import json


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


def test_restore_from_session_resumes_polling_for_a_supabase_project_without_a_connection_string(
    page, live_app_url
):
    """Replaces tests/test_onboarding_page.py's
    test_restore_from_session_resumes_polling_for_a_ref_without_a_connection_string,
    which only checked that three unrelated strings each appeared
    somewhere in the page source, not that they were wired together in
    the same code branch -- this drives the real restore-from-session
    flow and checks the actual resulting UI.

    frame-supabase starts locked/closed. showSupabaseProvisioning() sets
    its <details> `.open = true` directly (unlike unlockFrame(), it never
    touches `dataset.locked`), and guardLockedFrames()'s toggle listener
    immediately closes any frame whose dataset.locked is still "true" --
    exactly what real production code never hits, since this restore path
    only ever fires for a frame a visitor already unlocked earlier in the
    same flow. Pre-unlocking via an init script (registered, and so firing,
    before the page's own DOMContentLoaded listener that calls
    restoreFromSession()) reproduces that real precondition instead of
    fighting the guard."""
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

    page.add_init_script(
        "document.addEventListener('DOMContentLoaded', () => {"
        "  document.getElementById('frame-supabase').dataset.locked = 'false';"
        "});"
    )
    page.route(f"{live_app_url}/api/session", handle_session)
    page.route(f"{live_app_url}/api/supabase/project-status", handle_project_status)

    page.goto(live_app_url)

    page.wait_for_selector("#supabase-provisioning-section", state="visible")
    assert not page.is_visible("#supabase-connect-section")
    assert not page.is_visible("#supabase-org-section")


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
