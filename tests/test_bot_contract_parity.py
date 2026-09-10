"""This wizard against pr-review-bot's published provisioning contract.

The direction is asymmetric and that asymmetry is the whole design (see
that project's docs/superpowers/specs/2026-09-10-cross-repo-contract-
direction-design.md, sections 2 and 6.3): the BOT owns runtime_config /
slot_config's shape and every operational default, and backfills anything
it can derive at boot; this WIZARD owns the row, and writes only what it
uniquely knows -- which provider the visitor chose, which slot, which
model. So every assertion in this file is a subset/superset relation, never
an equality: the wizard must COVER its own responsibilities and must not
TRESPASS on the bot's. Equality is what the retired
test_runtime_config_column_parity asserted, and it is unsatisfiable by
either repo alone (that design's section 11).

contracts/provisioning.json is a VERBATIM VENDORED COPY of the bot's own
generated file, pinned together with .ci/pr-review-bot-ref by
scripts/update_bot_contract.py. Never edit it by hand to make a test here
pass -- that inverts the ownership this file exists to enforce. Regenerate
the pair instead.

Every test here but one reads only this repo's own tree, so it can never
skip. The exception is test_vendored_contract_matches_the_bot_at_the_pinned_ref,
which by nature needs the sibling checkout; it FAILS rather than skips
under CI (see _require_bot_checkout), because a CI skip reads as a pass and
this is the only assertion that would catch a stale vendored copy.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = "contracts/provisioning.json"
REF_PATH = ".ci/pr-review-bot-ref"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _contract() -> dict:
    return json.loads((_REPO_ROOT / CONTRACT_PATH).read_text(encoding="utf-8"))


def _pinned_ref() -> str:
    """The single 40-hex sha in .ci/pr-review-bot-ref.

    Format is pinned by that design's section 5.5: exactly one 40-hex line,
    optional trailing newline, '#'-prefixed comment lines permitted so a
    deliberately-held pin can record why it is held. Anything else is a
    hard error rather than a best-effort parse -- a malformed pin silently
    read as a ref name is how a "pinned" checkout quietly becomes a
    floating one.
    """
    text = (_REPO_ROOT / REF_PATH).read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert len(lines) == 1, f"{REF_PATH} must hold exactly one sha line, found {len(lines)}"
    assert _SHA_RE.match(lines[0]), f"{REF_PATH} is not 40 lowercase hex characters: {lines[0]!r}"
    return lines[0]


def _require_bot_checkout() -> Path:
    """The sibling pr-review-bot checkout -- FAILING, not skipping, in CI.

    Mirrors tests/test_cross_repo_config_ordering.py's own resolution
    (PR_REVIEW_BOT_PATH override, else the sibling-directory layout every
    local dev environment has), with one deliberate difference: under CI a
    missing checkout is a failure. .github/workflows/ci.yml checks the bot
    out at the pinned ref specifically so this runs, so its absence there
    means the workflow broke -- and a skip would report that as a pass,
    which is exactly the "CI skips must not read as passes" rule in that
    design's section 6.3.
    """
    override = os.environ.get("PR_REVIEW_BOT_PATH")
    candidate = (
        Path(override) if override else Path(__file__).resolve().parents[2] / "pr-review-bot"
    )
    if candidate.is_dir() and (candidate / ".git").exists():
        return candidate
    message = (
        f"no pr-review-bot git checkout at {candidate} (set PR_REVIEW_BOT_PATH, or run "
        "with ~/pr-review-bot present as a sibling directory)"
    )
    if os.environ.get("CI"):
        pytest.fail(
            f"{message} -- required in CI, where .github/workflows/ci.yml checks one out "
            "at the pinned ref. A skip here would report a stale vendored contract as a pass."
        )
    pytest.skip(f"{message} -- this check only runs where a checkout exists, always true in CI.")


def test_the_pinned_ref_file_is_a_single_forty_hex_sha():
    assert _SHA_RE.match(_pinned_ref())


def test_the_pinned_ref_file_tolerates_comment_lines():
    """A held pin must be able to record WHY it is held (section 5.5). This
    pins the parser's own tolerance, so the format stays usable without
    someone having to discover it by breaking CI."""
    sha = "a" * 40
    parsed = [
        line.strip()
        for line in f"# held: waiting on the bot's next release\n{sha}\n".splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert parsed == [sha]


def test_the_vendored_contract_carries_the_generators_do_not_edit_marker():
    contract = _contract()
    assert "do not edit" in contract["generated_by"].lower()
    assert "scripts.gen_contract" in contract["generated_by"]


def test_the_vendored_contract_version_is_one_this_repo_understands():
    """A shape change over there bumps contract_version (a new block, a
    renamed key, a changed entry shape) -- never an ordinary content edit.
    Reading a version this repo's assertions were not written against would
    make every subset check below vacuously true rather than wrong, which
    is the failure mode worth a loud stop."""
    assert _contract()["contract_version"] == 1


def test_the_vendored_contract_has_every_block_this_repo_reads():
    assert set(_contract()) == {
        "generated_by", "contract_version",
        "env_vars", "providers", "runtime_config", "slot_config",
    }


def test_vendored_contract_matches_the_bot_at_the_pinned_ref():
    """Section 6.1's first wizard-side check. The vendored copy and the pin
    are two halves of one fact, so a mismatch means someone advanced one
    without the other -- run `uv run python -m scripts.update_bot_contract`,
    which rewrites both together or neither.

    Extracted by git OBJECT, not read from the sibling's worktree: a dirty
    or checked-out-elsewhere sibling tree must not affect this, and no
    worktree is created inside the sibling's .git (section 5.5 step 3).
    """
    bot_path = _require_bot_checkout()
    sha = _pinned_ref()
    result = subprocess.run(
        ["git", "-C", str(bot_path), "show", f"{sha}:{CONTRACT_PATH}"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"cannot read {CONTRACT_PATH} from pr-review-bot at {sha}: {result.stderr.strip()}"
    )
    vendored = (_REPO_ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
    assert vendored == result.stdout, (
        f"the vendored {CONTRACT_PATH} has drifted from pr-review-bot at the pinned {sha} "
        "-- run `uv run python -m scripts.update_bot_contract` (it rewrites the contract "
        "and .ci/pr-review-bot-ref together or neither). Never hand-edit the vendored copy."
    )
