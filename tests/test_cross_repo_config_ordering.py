"""The seed-then-boot chronology, against a real ~/pr-review-bot checkout.

This is the one test in this repo that needs both a live Postgres and the
sibling pr-review-bot checkout: it reproduces the actual deploy chronology
(this wizard's provisioning write, then the bot's own first-boot sequence)
end to end, against a real ephemeral database. It is the direct regression
test for ISSUES.md's 2026-09-09 cross-repo ordering incident: this wizard's
`runtime_config` write and the bot's own boot sequence disagreed about who
was responsible for filling the row, and every wizard-deployed instance got
stuck forever behind a "Dispatcher configuration issue" PR comment as a
result.

The static schema/name parity checks that used to live in this file moved to
tests/test_bot_contract_parity.py, and changed shape along the way: instead
of parsing pr-review-bot's own source (a DDL regex, an AST literal-eval),
they read contracts/provisioning.json -- a copy of a file that project
generates and publishes for exactly this purpose (see that project's
docs/superpowers/specs/2026-09-10-cross-repo-contract-direction-design.md).
That file's module docstring explains why these checks are assertions of
COVERAGE rather than equality: this wizard's runtime_config/slot_config DDL
is deliberately narrower than the bot's own declared shape, and the bot's
own boot-time widen-and-backfill (exercised by the one test below) is what
makes that narrowness harmless rather than a hazard.

Skipped (not failed) when no pr-review-bot checkout is available -- true for
an ordinary local `pytest` run without the sibling repo present, never true
in CI (see .github/workflows/ci.yml, which checks one out at a pinned ref
specifically so this runs, and FAILS rather than skips there -- a CI skip
would report a stale vendored contract or a broken checkout step as a pass).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import router


def _pr_review_bot_path() -> Path | None:
    """The sibling repo's checkout, or None if not available this run.

    PR_REVIEW_BOT_PATH lets CI (or a developer) point at a checkout in a
    non-default location; otherwise this falls back to the sibling-directory
    layout every local dev environment for this project actually has
    (`~/onboarding-wizard` next to `~/pr-review-bot`). Gated on the bot's own
    SOURCE being present, not just a `.git` directory -- this test needs to
    `uv run --directory <bot>` the bot's actual code and dependencies, unlike
    tests/test_bot_contract_parity.py's own bot-checkout check, which only
    needs `git show` against the bot's object store. Deliberately not
    unified with that one for this reason."""
    override = os.environ.get("PR_REVIEW_BOT_PATH")
    candidate = (
        Path(override) if override else Path(__file__).resolve().parents[2] / "pr-review-bot"
    )
    if candidate.is_dir() and (candidate / "review_queue" / "store.py").is_file():
        return candidate
    return None


def _require_bot_checkout() -> Path:
    """The sibling pr-review-bot checkout -- FAILING, not skipping, in CI.

    .github/workflows/ci.yml checks the bot out at the pinned ref
    specifically so this test runs; its absence there means the workflow
    broke, and a skip would report that as a pass (that design's section
    6.3: "CI skips must not read as passes")."""
    path = _pr_review_bot_path()
    if path is not None:
        return path
    message = (
        "no pr-review-bot checkout available (set PR_REVIEW_BOT_PATH, or run "
        "with ~/pr-review-bot present as a sibling directory)"
    )
    if os.environ.get("CI"):
        pytest.fail(
            f"{message} -- required in CI, where .github/workflows/ci.yml checks one out "
            "at the pinned ref. A skip here would report a broken checkout step as a pass."
        )
    pytest.skip(f"{message} -- this check only runs where a checkout exists, always true in CI.")


def test_wizard_seed_leaves_bot_boot_ready(db_url, db_exec, db_query):
    """The bot's boot-time widen + backfill makes a MINIMALLY-provisioned
    database boot-ready, against a real Postgres, in the real order.

    This test used to prove something else. Until 2026-09-10 this wizard
    wrote a complete 22-column runtime_config row, and this test proved the
    22 hand-copied values were right. It now proves the opposite direction:
    this wizard creates a deliberately NARROW table (six columns -- see
    router.py's _RUNTIME_CONFIG_SCHEMA) and writes only provider, the chosen
    key-slot index, and updated_at, and pr-review-bot's own
    store.init_pool() must then widen the table (ALTER TABLE ... ADD COLUMN
    IF NOT EXISTS, its _widen_statements) and fill every NULL from its own
    declared Settings defaults (_backfill_runtime_config) before its
    dispatcher tuning gate can pass. See that project's
    docs/superpowers/specs/2026-09-10-cross-repo-contract-direction-design.md
    sections 3 and 7.2.

    The chronology is the whole point and is not negotiable: this wizard
    writes first (as it always must -- the bot's own provider/slot_config
    boot check would otherwise fail), which is what made the wizard the
    row's PRODUCER while the bot's old seeding code still assumed it was.
    That inversion is ISSUES.md's 2026-09-09 incident: 18 of 22 columns NULL
    forever, and every PR review on every wizard-provisioned deployment
    stuck behind a "Dispatcher configuration issue" comment that never
    resolved.

    Two assertions, and the second is what keeps the first honest:
    problems() coming back empty proves the bot can start, and every
    bot_backfilled column coming back NON-NULL proves the backfill is what
    did it -- without that, a wizard that quietly went back to seeding those
    columns itself would leave this test just as green.
    """
    bot_path = _require_bot_checkout()
    db_exec("DROP TABLE IF EXISTS runtime_config, slot_config, tickets, reviews CASCADE")

    ok = router._seed_provider_config(db_url, "groq", "llama-3.3-70b-versatile", None, None)
    assert ok is True

    # The narrow table really is narrow before the bot ever sees it -- so a
    # non-NULL assertion below cannot be satisfied by this wizard.
    declared = router._RUNTIME_CONFIG_SCHEMA
    contract = json.loads(
        (Path(__file__).resolve().parent.parent / "contracts" / "provisioning.json")
        .read_text(encoding="utf-8")
    )
    backfilled = [e["column"] for e in contract["runtime_config"]["bot_backfilled"]]
    assert backfilled, "the vendored contract lists no backfilled columns -- check would be vacuous"
    for column in backfilled:
        assert column not in declared, (
            f"router._RUNTIME_CONFIG_SCHEMA declares {column}, which the bot backfills "
            "-- this test can no longer distinguish a working backfill from a wizard seed"
        )

    result = subprocess.run(
        [
            "uv", "run", "--directory", str(bot_path), "python", "-c",
            "import json\n"
            "from review_queue import store, dispatcher_tuning_config\n"
            "store.init_pool()\n"
            "print(json.dumps(dispatcher_tuning_config.problems("
            "store.get_dispatcher_tuning_config())))\n",
        ],
        env={**os.environ, "DATABASE_URL": db_url},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"bot subprocess failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    problems = json.loads(result.stdout.strip().splitlines()[-1])
    assert problems == [], (
        "pr-review-bot's dispatcher tuning config is not boot-ready after this "
        f"wizard's seed: {problems}"
    )

    row = db_query(f"SELECT {', '.join(backfilled)} FROM runtime_config WHERE id = 1")[0]
    still_null = [name for name, value in zip(backfilled, row) if value is None]
    assert not still_null, (
        f"the bot's backfill left these NULL: {still_null} -- a wizard-provisioned "
        "deployment would boot into exactly ISSUES.md's 2026-09-09 state"
    )
