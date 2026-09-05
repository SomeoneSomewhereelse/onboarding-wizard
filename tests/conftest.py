"""Shared Postgres test harness. Uses DATABASE_URL if the environment already
provides one (CI's `services: postgres`); otherwise spins a throwaway Postgres
via testcontainers (local dev — Docker required). Never touches Supabase."""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest

# Hosts treated as "local/CI Postgres, safe for tests to TRUNCATE". Anything
# else (e.g. a Supabase pooler hostname) is refused unless the operator
# explicitly opts in via ALLOW_REMOTE_TEST_DB=1 -- this guard exists solely so
# an accidentally-exported DATABASE_URL pointing at a real Supabase database
# can never get truncated by a test run.
_LOCAL_TEST_DB_HOSTS = {"localhost", "127.0.0.1"}


def _looks_like_local_test_db(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host in _LOCAL_TEST_DB_HOSTS or host.endswith(".internal")


def _close_onboarding_pool() -> None:
    """Best-effort close of session_store's pool -- a no-op if `db` was
    never requested this session/worker (the module may not even be
    importable in a worker that never touched it)."""
    try:
        import session_store as onboarding_store
    except ImportError:
        return
    onboarding_store.close_pool()


@pytest.fixture(scope="session")
def db_url() -> str:
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        if not _looks_like_local_test_db(env_url) and not os.environ.get(
            "ALLOW_REMOTE_TEST_DB"
        ):
            raise AssertionError(
                "DATABASE_URL does not look like a local/CI Postgres (host must be "
                "'localhost', '127.0.0.1', or end in '.internal'). Refusing to run "
                "destructive tests (TRUNCATE) against it -- this guard protects a real "
                "database (e.g. Supabase) from being wiped by a test run. If this really "
                "is an intentional, disposable local/CI Postgres on an unusual "
                "hostname, set ALLOW_REMOTE_TEST_DB=1 to bypass."
            )
        yield env_url
        # Matches the testcontainers branch below: whichever pool the `db`
        # fixture built against this session's db_url gets closed exactly
        # once, here, rather than per-test -- see `db`'s docstring.
        # _close_onboarding_pool() is a no-op if `db` was never requested
        # this session.
        _close_onboarding_pool()
        return
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        # driver=None gives a bare "postgresql://" scheme for raw psycopg3.
        # driver="psycopg" (the previous value) builds a SQLAlchemy-style
        # "postgresql+psycopg://" dialect+driver URL, which psycopg3's own
        # parser cannot read at all ('missing "=" after "postgresql+psycopg:...'"').
        # This was masked until now: CI's services:postgres sets DATABASE_URL
        # directly and never calls this method, and every local run before
        # Docker/WSL integration was enabled failed earlier on
        # docker.errors.DockerException, before this code path ever ran.
        yield pg.get_connection_url(driver=None)
        _close_onboarding_pool()


@pytest.fixture
def db(db_url, monkeypatch):
    """Points session_store at the test Postgres and truncates its one
    table (wizard_sessions) before each test that requests this fixture."""
    import session_store as onboarding_store
    from config import settings as onboarding_settings

    monkeypatch.setattr(onboarding_settings, "database_url", db_url)
    onboarding_store.init_pool()
    with onboarding_store._require_pool().connection() as conn:
        conn.execute("TRUNCATE wizard_sessions")
    yield


@pytest.fixture
def db_exec(db_url):
    """Run a raw statement against the test DB (replaces test-side sqlite3.connect)."""
    import psycopg

    def _exec(sql: str, params: tuple = ()):
        with psycopg.connect(db_url) as conn:
            conn.execute(sql, params)
            conn.commit()

    return _exec


@pytest.fixture
def db_query(db_url):
    """Run a raw query and return the rows (list of tuples)."""
    import psycopg

    def _query(sql: str, params: tuple = ()):
        with psycopg.connect(db_url) as conn:
            return conn.execute(sql, params).fetchall()

    return _query


def _touches_shared_postgres(item: pytest.Item) -> bool:
    """True if item's fixture closure includes db_url -- the root fixture
    that db, db_exec, and db_query all depend on, and that some tests
    request directly. Checking the root rather than the three derived
    names means a test can't slip through by requesting db_url on its
    own."""
    return "db_url" in item.fixturenames


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-tag every Postgres-touching test with `db` (for `pytest -m "not
    db"` fast iteration) and `xdist_group(name="db")` (so pytest-xdist
    schedules them all onto the same worker, avoiding cross-worker TRUNCATE
    races against the one shared Postgres instance). See the 2026-08-19
    test-suite-performance design doc, section 3c, for why this is keyed off
    db_url specifically.

    `tryfirst=True` is load-bearing, not decoration. `--dist=loadgroup` never
    reads the `xdist_group` marker: pytest-xdist's worker-side
    `WorkerInteractor.pytest_collection_modifyitems` stamps an `@<group>`
    suffix onto `item._nodeid`, and that nodeid *string* is the only thing the
    scheduler groups on. That stamping hookimpl is undecorated, so pluggy
    orders it by registration LIFO -- and this file is an *initial* conftest
    (loaded as an initial conftest because `tests/` is the sole `testpaths`
    entry) registered before `WorkerInteractor`, so
    without `tryfirst` xdist stamps first, while no item carries the marker
    yet, and every db test ends up its own singleton group spread across every
    worker (each spinning its own testcontainers Postgres). The failure is
    silent -- all tests still pass and `-m db` still selects correctly, since
    marker selection is evaluated after both hooks have run.
    `tests/test_xdist_group_ordering.py` is the regression guard."""
    for item in items:
        if _touches_shared_postgres(item):
            item.add_marker(pytest.mark.db)
            item.add_marker(pytest.mark.xdist_group(name="db"))
