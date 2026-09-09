"""Cross-repo checks against the sibling ~/pr-review-bot checkout.

This wizard and pr-review-bot are developed together but never share code
(everything touching `runtime_config`/`slot_config` is duplicated-not-imported
by convention, kept in sync by hand -- see router.py's comments above
`_RUNTIME_CONFIG_SCHEMA`/`_SLOT_CONFIG_SCHEMA`/`_RUNTIME_CONFIG_DEFAULTS`).
That hand-sync has already drifted once in a way plain unit tests on either
side couldn't catch: this wizard's provisioning write and pr-review-bot's own
boot sequence disagreed about who was responsible for a fully-seeded
`runtime_config` row, and every wizard-deployed instance got stuck forever
behind a "Dispatcher configuration issue" PR comment as a result (ISSUES.md
2026-09-09, both repos).

Two tiers, both skipped (not failed) when no pr-review-bot checkout is
available -- true for an ordinary local `pytest` run without the sibling repo
present, never true in CI (see .github/workflows/ci.yml, which checks one out
at a pinned ref specifically so these run):

1. Structural DDL parity (`test_runtime_config_column_parity`,
   `test_slot_config_column_parity`) -- pure static source parsing, no bot
   code executed, no bot dependencies/env needed. Catches the schema hazard
   router.py's own comment already warns about: a column added to the bot's
   `RUNTIME_CONFIG_COLUMNS` without a matching addition here makes this
   wizard's `CREATE TABLE IF NOT EXISTS` permanently narrower than the bot's,
   which would break the bot's own first-boot schema check against a
   wizard-provisioned database.

2. The real regression test (`test_wizard_seed_leaves_bot_boot_ready`) --
   reproduces the actual deploy chronology (this wizard's seed write, then
   the bot's own store.init_pool()) against a real ephemeral Postgres, and
   asserts the bot's dispatcher_tuning_config.problems() comes back empty
   afterward. This is the test that would have caught the original ordering
   bug directly, and the one worth trusting most if the other two ever have
   to be simplified or dropped.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

import router


def _pr_review_bot_path() -> Path | None:
    """The sibling repo's checkout, or None if not available this run.

    PR_REVIEW_BOT_PATH lets CI (or a developer) point at a checkout in a
    non-default location; otherwise this falls back to the sibling-directory
    layout every local dev environment for this project actually has
    (`~/onboarding-wizard` next to `~/pr-review-bot`)."""
    override = os.environ.get("PR_REVIEW_BOT_PATH")
    candidate = (
        Path(override) if override else Path(__file__).resolve().parents[2] / "pr-review-bot"
    )
    if candidate.is_dir() and (candidate / "review_queue" / "store.py").is_file():
        return candidate
    return None


def _skip_if_bot_checkout_missing() -> Path:
    path = _pr_review_bot_path()
    if path is None:
        pytest.skip(
            "no pr-review-bot checkout available (set PR_REVIEW_BOT_PATH, or run "
            "with ~/pr-review-bot present as a sibling directory) -- this check "
            "only runs where a checkout exists, always true in CI."
        )
    return path


_CONSTRAINT_KEYWORDS = ("PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "CONSTRAINT")


def _parse_ddl_columns(ddl_text: str, table: str) -> list[tuple[str, str]]:
    """(name, normalized type+constraint string) pairs for a literal
    `CREATE TABLE IF NOT EXISTS <table> (...)` block found in `ddl_text`.
    Skips standalone table-level constraint lines (PRIMARY KEY (...), etc.)
    -- those aren't columns. Whitespace inside each column's type/constraint
    text is collapsed to single spaces so differing column-alignment padding
    between the two hand-typed copies doesn't register as a difference."""
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS {re.escape(table)} \((.*?)\n\);",
        ddl_text,
        re.DOTALL,
    )
    assert match, f"no CREATE TABLE IF NOT EXISTS {table} (...) block found"
    columns: list[tuple[str, str]] = []
    for raw_line in match.group(1).split("\n"):
        line = raw_line.strip().rstrip(",")
        if not line:
            continue
        first_word = line.split(None, 1)[0].upper()
        if first_word in _CONSTRAINT_KEYWORDS:
            continue
        name, _, rest = line.partition(" ")
        columns.append((name, " ".join(rest.split())))
    return columns


def _bot_runtime_config_columns(bot_path: Path) -> list[tuple[str, str]]:
    """Statically parses RUNTIME_CONFIG_COLUMNS out of the bot's store.py --
    pure AST literal-eval of the assignment's value, no import, so this needs
    none of the bot's own dependencies or environment. Deliberately not
    parsed via the DDL-column regex above: unlike slot_config's DDL,
    runtime_config's CREATE TABLE text in the bot's _SCHEMA is built at
    runtime (an f-string join() over this exact tuple), not literal source
    text, so there is nothing for a source-level DDL regex to find there."""
    source = (bot_path / "review_queue" / "store.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # RUNTIME_CONFIG_COLUMNS carries a `tuple[tuple[str, str], ...]`
        # type annotation, so it's an AnnAssign node, not a plain Assign.
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "RUNTIME_CONFIG_COLUMNS"
            and node.value is not None
        ):
            columns = ast.literal_eval(node.value)
            return [(name, " ".join(sql_type.split())) for name, sql_type in columns]
    raise AssertionError("RUNTIME_CONFIG_COLUMNS assignment not found in store.py")


def test_runtime_config_column_parity():
    bot_path = _skip_if_bot_checkout_missing()
    wizard_columns = _parse_ddl_columns(router._RUNTIME_CONFIG_SCHEMA, "runtime_config")
    bot_columns = _bot_runtime_config_columns(bot_path)
    assert wizard_columns == bot_columns, (
        "router.py's hand-copied _RUNTIME_CONFIG_SCHEMA has drifted from "
        "pr-review-bot's review_queue/store.py::RUNTIME_CONFIG_COLUMNS -- "
        "update router.py's copy (see its own comment for why this can't be "
        "imported directly)."
    )


def test_slot_config_column_parity():
    bot_path = _skip_if_bot_checkout_missing()
    wizard_columns = _parse_ddl_columns(router._SLOT_CONFIG_SCHEMA, "slot_config")
    bot_schema_source = (bot_path / "review_queue" / "store.py").read_text(encoding="utf-8")
    bot_columns = _parse_ddl_columns(bot_schema_source, "slot_config")
    assert wizard_columns == bot_columns, (
        "router.py's hand-copied _SLOT_CONFIG_SCHEMA has drifted from "
        "pr-review-bot's review_queue/store.py's slot_config table -- update "
        "router.py's copy."
    )


def test_wizard_seed_leaves_bot_boot_ready(db_url, db_exec):
    """Reproduces the real deploy chronology end to end against a real
    Postgres: this wizard's provisioning write runs first (as it always must,
    to satisfy the bot's own provider/slot_config boot check), then the bot's
    own store.init_pool() runs exactly as it does on first boot. Asserts the
    bot's dispatcher_tuning_config.problems() comes back empty afterward --
    i.e. the bot is actually able to start. This is the direct regression
    test for ISSUES.md's 2026-09-09 cross-repo ordering bug: before the fix
    on both sides, this would have failed with 9 "<knob> is not set" problems
    (the bot's old ON CONFLICT (id) DO NOTHING seed silently no-opped against
    the row this wizard had already created)."""
    bot_path = _skip_if_bot_checkout_missing()
    db_exec("DROP TABLE IF EXISTS runtime_config, slot_config, tickets, reviews CASCADE")

    ok = router._seed_provider_config(db_url, "groq", "llama-3.3-70b-versatile", None, None)
    assert ok is True

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
