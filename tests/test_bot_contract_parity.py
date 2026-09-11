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

import ast
import inspect
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

import router

_REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = "contracts/provisioning.json"
REF_PATH = ".ci/pr-review-bot-ref"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _contract() -> dict:
    return json.loads((_REPO_ROOT / CONTRACT_PATH).read_text(encoding="utf-8"))


def _parse_pin_text(text: str) -> str:
    """The parsing rule behind .ci/pr-review-bot-ref's format, given its text.

    Format is pinned by that design's section 5.5: exactly one 40-hex line,
    optional trailing newline, '#'-prefixed comment lines permitted so a
    deliberately-held pin can record why it is held. Anything else is a
    hard error rather than a best-effort parse -- a malformed pin silently
    read as a ref name is how a "pinned" checkout quietly becomes a
    floating one.

    Split out from _pinned_ref() (which reads the real file) so the format
    rule itself can be exercised directly against synthetic text, rather
    than a test re-implementing this logic alongside it and only proving
    the reimplementation agrees with itself.
    """
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert len(lines) == 1, f"{REF_PATH} must hold exactly one sha line, found {len(lines)}"
    assert _SHA_RE.match(lines[0]), f"{REF_PATH} is not 40 lowercase hex characters: {lines[0]!r}"
    return lines[0]


def _pinned_ref() -> str:
    """The single 40-hex sha in .ci/pr-review-bot-ref."""
    return _parse_pin_text((_REPO_ROOT / REF_PATH).read_text(encoding="utf-8"))


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
    calls the real parser (_parse_pin_text), so the format stays usable
    without someone having to discover it by breaking CI."""
    sha = "a" * 40
    text = f"# held: waiting on the bot's next release\n{sha}\n"
    assert _parse_pin_text(text) == sha


def test_the_vendored_contract_carries_the_generators_do_not_edit_marker():
    contract = _contract()
    assert "do not edit" in contract["generated_by"].lower()
    assert "scripts.gen_contract" in contract["generated_by"]


def test_the_vendored_contract_version_is_two_this_repo_understands():
    """A shape change over there bumps contract_version (a new block, a
    renamed key, a changed entry shape) -- never an ordinary content edit.
    Reading a version this repo's assertions were not written against would
    make every subset check below vacuously true rather than wrong, which
    is the failure mode worth a loud stop.

    Version 2 added `model_validation` -- the bot's declaration that Vertex
    and Gemini models must be proven callable by a live probe before being
    written, because Vertex's own catalog listing is not scoped by project
    entitlement. See tests/test_model_validation_conformance.py for this
    repo's implementation of that rule."""
    assert _contract()["contract_version"] == 2


def test_the_vendored_contract_has_every_block_this_repo_reads():
    assert set(_contract()) == {
        "generated_by", "contract_version",
        "env_vars", "providers", "model_validation", "runtime_config", "slot_config",
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
        encoding="utf-8",
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


def _references_env_vars(node: ast.AST) -> bool:
    """Whether an assignment/delete target is (or contains) `env_vars[...]`.
    Recurses into Tuple/List so a target like `(x, env_vars["Y"]) = ...`
    can't hide a write inside a shape _render_push_set doesn't expect."""
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        return node.value.id == "env_vars"
    if isinstance(node, (ast.Tuple, ast.List)):
        return any(_references_env_vars(elt) for elt in node.elts)
    return False


def _render_push_set() -> set[str]:
    """Every env-var name bulk_push_render_env_vars can ever push.

    Recovered by AST from that function's own source rather than by driving
    the endpoint: the names are what the contract constrains, and the values
    all come from visitor session state. Exactly two RECOGNIZED shapes:

      env_vars["LITERAL"] = ...   -> the name, directly
      env_vars[credential_var]    -> the active provider's credential; the
                                     possible names are _LLM_ENV_VAR_NAMES'
                                     own, and the assertion below pins that
                                     there is exactly ONE such dynamic key,
                                     so a second one cannot slip in unnamed
      env_vars.update(NAME)       -> that module constant's keys

    Every OTHER way the function could touch `env_vars` -- a second target
    in a chained/tuple assignment, an augmented assignment (`env_vars |=
    ...`), a `del env_vars[...]`, or any method call on it other than a
    single-Name-argument `.update()` (a dict-literal `.update({...})`,
    `.setdefault(...)`, `.pop(...)`, `.update(_helper())`) -- is treated as
    UNRECOGNIZED and raises loudly, rather than being silently invisible to
    this extractor. A name pushed only through one of those shapes would
    otherwise pass the trespass/coverage tests below with nothing red
    anywhere -- exactly the failure mode this static view exists to avoid.

    tests/test_onboarding_router.py::test_bulk_push_assembles_every_frame_into_one_push_call
    is the behavioural counterpart, pinning the real dict a fully-populated
    session produces -- so this static view cannot drift from the endpoint's
    actual behaviour without one of the two going red.
    """
    tree = ast.parse(inspect.getsource(router))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "bulk_push_render_env_vars"
    )
    names: set[str] = set()
    dynamic = 0
    recognized: set[int] = set()

    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "env_vars"
            ):
                recognized.add(id(node))
                if isinstance(target.slice, ast.Constant):
                    names.add(target.slice.value)
                else:
                    dynamic += 1
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "env_vars"
        ):
            if (
                node.func.attr == "update"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Name)
            ):
                recognized.add(id(node))
                names |= set(getattr(router, node.args[0].id))
            else:
                raise AssertionError(
                    f"unrecognized env_vars.{node.func.attr}(...) call at "
                    f"router.py:{node.lineno} -- _render_push_set only understands "
                    "env_vars[literal] = ..., env_vars[dynamic] = ..., and "
                    "env_vars.update(<a single module-constant name>)"
                )

    for node in ast.walk(function):
        if id(node) in recognized:
            continue
        if isinstance(node, ast.Assign) and any(_references_env_vars(t) for t in node.targets):
            raise AssertionError(
                f"unrecognized assignment touching env_vars at router.py:{node.lineno}"
            )
        if isinstance(node, ast.AugAssign) and _references_env_vars(node.target):
            raise AssertionError(
                f"unrecognized augmented assignment touching env_vars at router.py:{node.lineno}"
            )
        if isinstance(node, ast.Delete) and any(_references_env_vars(t) for t in node.targets):
            raise AssertionError(f"unrecognized `del` touching env_vars at router.py:{node.lineno}")

    assert dynamic == 1, (
        f"expected exactly one dynamically-keyed env_vars[...] write (the active "
        f"provider's credential), found {dynamic} -- a second one is a name this "
        "extractor cannot see, and therefore a name the contract cannot constrain"
    )
    for credential_var, _model_var in router._LLM_ENV_VAR_NAMES.values():
        names.add(credential_var)
    return names


_CONSTRAINT_KEYWORDS = ("PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "CONSTRAINT")


def _ddl_column_names(ddl_text: str, table: str) -> list[str]:
    """Column NAMES from a literal CREATE TABLE IF NOT EXISTS block in this
    repo's own DDL constants.

    Deliberately smaller than the type-comparing DDL parser this replaces
    (the retired _parse_ddl_columns): it reads only the wizard's own source,
    never pr-review-bot's, so there is no cross-repo type-string
    normalization to get wrong. Types are the bot's business now -- it widens
    both tables itself at boot with ADD COLUMN IF NOT EXISTS
    (review_queue/store.py::_widen_statements), which is what makes a
    narrower table here harmless.

    Reads the DDL TEXT, never information_schema. The one test Postgres is
    shared across the whole xdist "db" group, and tests/
    test_cross_repo_config_ordering.py drops these tables and lets the bot
    widen them back to its full shape -- so a live-table column list is
    order-dependent and would flake.
    """
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS {re.escape(table)} \((.*?)\n\);",
        ddl_text,
        re.DOTALL,
    )
    assert match, f"no CREATE TABLE IF NOT EXISTS {table} (...) block found"
    columns = []
    for raw_line in match.group(1).split("\n"):
        line = raw_line.strip().rstrip(",")
        if not line:
            continue
        if line.split(None, 1)[0].upper() in _CONSTRAINT_KEYWORDS:
            continue
        columns.append(line.split()[0])
    return columns


def _placed(placement: str) -> set[str]:
    return {n for n, e in _contract()["env_vars"].items() if e["placement"] == placement}


def test_the_push_set_covers_every_always_synced_env_var():
    """Section 6.1: the push-set must COVER the contract's provisioning
    responsibilities -- a superset assertion, not equality. always_synced is
    every credential and identity var the bot's deploy.py pushes on every
    sync; a wizard-provisioned service that is missing one has no other way
    to get it. The push-set is legitimately larger: it also carries the
    active provider's credential, which lives in the contract's `providers`
    block rather than in env_vars."""
    missing = _placed("always_synced") - _render_push_set()
    assert not missing, (
        f"bulk_push_render_env_vars never pushes these always_synced vars: {sorted(missing)} "
        "-- a wizard-provisioned service has no other source for them"
    )


def test_the_push_set_trespasses_on_nothing_db_only():
    """Section 6.1's inverse, and the one that keeps this wizard out of the
    bot's lane. A db_only key pushed as a Render env var is a second source
    of truth for a value the dispatcher only ever reads from runtime_config:
    an operator edits the Render var, redeploys, and cannot explain the
    non-effect (ISSUES.md 2026-08-17, "two sources of truth")."""
    overlap = _placed("db_only") & _render_push_set()
    assert not overlap, f"db_only keys must never be pushed to Render: {sorted(overlap)}"


def test_the_push_set_trespasses_on_nothing_never_synced_or_slot_seeded():
    """never_synced is Render's own or the operator's (RENDER_SERVICE_NAME,
    PUBLIC_BASE_URL); slot_zero_seed is the three model vars, which this
    wizard writes into slot_config directly and must not also push as env
    vars."""
    overlap = (_placed("never_synced") | _placed("slot_zero_seed")) & _render_push_set()
    assert not overlap, f"must not be pushed to Render: {sorted(overlap)}"


def test_generic_operational_env_defaults_are_all_render_pushable():
    """Section 7.1: _GENERIC_OPERATIONAL_ENV_DEFAULTS stays hand-written, but
    becomes asserted against the vendored contract -- which is what catches a
    rename or a placement move (section 5.1's exact hazard: rename
    GITHUB_TARGET_REPO over there and this wizard keeps pushing the old name
    forever, on every provisioned deployment, with nothing red anywhere)."""
    for name in router._GENERIC_OPERATIONAL_ENV_DEFAULTS:
        entry = _contract()["env_vars"].get(name)
        assert entry is not None, (
            f"{name} is not in the bot's contract at all -- it was renamed or removed "
            "over there; re-vendor the contract and update this dict to match"
        )
        assert entry["placement"] == "always_synced", (
            f"{name} is {entry['placement']} in the contract, not a Render env var"
        )


def test_llm_env_var_names_match_the_contracts_providers_block():
    """Replaces the retired test asserting against ~/pr-review-bot's
    providers/registry.py directly, which skipped silently without a
    sibling checkout."""
    providers = _contract()["providers"]
    assert set(router._LLM_ENV_VAR_NAMES) == set(providers)
    for provider, (credential_var, model_var) in router._LLM_ENV_VAR_NAMES.items():
        assert credential_var == providers[provider]["credential_var"]
        assert model_var == providers[provider]["model_var"]


def test_key_index_columns_match_the_contracts_providers_block():
    """Section 6.1. This dict is also the injection guard for the column name
    _seed_provider_config interpolates into its INSERT (see router.py's own
    comment), so a wrong entry is both a correctness and a safety defect."""
    providers = _contract()["providers"]
    assert set(router._KEY_INDEX_COLUMNS) == set(providers)
    for provider, column in router._KEY_INDEX_COLUMNS.items():
        assert column == providers[provider]["key_index_column"]
    assert set(router._KEY_INDEX_COLUMNS.values()) == set(
        _contract()["runtime_config"]["provisioner_required_one_of"]
    )


def test_the_wizards_runtime_config_ddl_covers_every_provisioner_required_column():
    """Section 6.1's coverage check, replacing the retired ordered-equality
    test_runtime_config_column_parity. COVERAGE, not equality: this wizard's
    table is deliberately narrower than the bot's declared shape, and the
    bot's boot-time widening is what makes that harmless (that design's
    section 3.1). All three of provisioner_required_one_of must be declared
    even though only one is written per visitor -- the column has to exist
    before the INSERT can name it."""
    declared = set(_ddl_column_names(router._RUNTIME_CONFIG_SCHEMA, "runtime_config"))
    block = _contract()["runtime_config"]
    required = set(block["provisioner_required"]) | set(block["provisioner_required_one_of"])
    missing = required - declared
    assert not missing, (
        f"router._RUNTIME_CONFIG_SCHEMA declares no {sorted(missing)} -- the bot refuses "
        "to boot without these and cannot derive them (main.py's provider gate)"
    )


def test_the_wizards_slot_config_ddl_covers_required_plus_optional():
    """Section 7.1 leaves _SLOT_CONFIG_SCHEMA full DELIBERATELY, not by
    omission: all six columns are either required or in `optional`, and this
    wizard writes five of them itself, so shrinking it would buy nothing.
    Replaces the retired test_slot_config_column_parity and its duplicate."""
    declared = set(_ddl_column_names(router._SLOT_CONFIG_SCHEMA, "slot_config"))
    block = _contract()["slot_config"]
    missing = set(block["provisioner_required"]) - declared
    assert not missing, f"router._SLOT_CONFIG_SCHEMA declares no {sorted(missing)}"
    assert declared == set(block["provisioner_required"]) | set(block["optional"]), (
        "_SLOT_CONFIG_SCHEMA is intentionally the contract's full slot_config shape "
        "(that design's section 7.1) -- if a column was added over there, re-vendor "
        "the contract and add it here too"
    )


def test_the_wizard_declares_no_column_the_bot_backfills():
    """The claim that makes section 7.1's deletion safe, asserted rather than
    assumed. A tuning column declared here is one this wizard would create
    (as NULL) and then be tempted to seed -- which is how it came to
    hand-copy 15 of the bot's default values, including a "04:00:00" string
    literal, whose only guard was a pinned test in the other repo."""
    declared = set(_ddl_column_names(router._RUNTIME_CONFIG_SCHEMA, "runtime_config"))
    backfilled = {e["column"] for e in _contract()["runtime_config"]["bot_backfilled"]}
    overlap = declared & backfilled
    assert not overlap, (
        f"the bot backfills {sorted(overlap)} at boot -- this wizard must not declare "
        "or seed them (that design's section 7.1)"
    )
