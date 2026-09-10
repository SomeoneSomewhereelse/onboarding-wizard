# Cross-Repo Contract Stage 3 (Wizard Side) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop hand-duplicating `pr-review-bot`'s `runtime_config` schema and its 15 operational defaults in `router.py`. Vendor the bot's generated `contracts/provisioning.json`, pin it atomically alongside `.ci/pr-review-bot-ref`, assert this wizard's provisioning responsibilities against it, and only then shrink `_RUNTIME_CONFIG_SCHEMA` to what this wizard uniquely knows and retire the superseded cross-repo tests.

**Architecture:** A verbatim copy of the bot's contract lands at `contracts/provisioning.json`, paired with `.ci/pr-review-bot-ref` — two halves of one fact ("which bot contract are we built against"), rewritten together or not at all by a new `scripts/update_bot_contract.py`. A new `tests/test_bot_contract_parity.py` reads that vendored copy out of this repo's own tree and asserts subset/superset relations against `router.py`'s remaining hand-written constants: the Render push-set covers every `always_synced` name, pushes nothing `db_only`, and `_KEY_INDEX_COLUMNS`/`_LLM_ENV_VAR_NAMES` match the contract's `providers` block. With those replacements green, `_RUNTIME_CONFIG_DEFAULTS` is deleted, `_RUNTIME_CONFIG_SCHEMA` shrinks from 22 hand-typed columns to 6, and the DDL-regex/AST-literal-eval machinery in `tests/test_cross_repo_config_ordering.py` comes out — leaving that file holding only the live-Postgres seed-then-boot chronology test it was always named for.

**Tech Stack:** Python 3.12, `json`/`ast`/`re`/`subprocess` (stdlib), psycopg 3, pytest (+ pytest-xdist, pinned `-n 4 --dist=loadgroup`), ruff (`line-length = 100`), GitHub Actions.

**Spec:** `~/pr-review-bot/docs/superpowers/specs/2026-09-10-cross-repo-contract-direction-design.md` — this plan implements **Stage 3 only** (that spec's §10 rollout step 3). Read §5.5, §6.1's wizard-side bullet list, §6.3 and §7 in full before starting; every task below argues from them. Stage 2's bot-side plan (`~/pr-review-bot/docs/superpowers/plans/2026-09-10-cross-repo-provisioning-contract.md`) documents the artifact this plan vendors.

## Global Constraints

- **PREREQUISITE (already satisfied as of this plan's writing):** Stage 2 landed on the bot's `origin/main` at commit `3fee149` (merge of `cross-repo-contract-stage-2`, pushed 2026-09-10). `contracts/provisioning.json` exists there. Re-verify before Task 1 with `git -C ~/pr-review-bot fetch origin && git -C ~/pr-review-bot show origin/main:contracts/provisioning.json | head -3` — if that errors, **stop and report**, do not vendor from any branch tip.
- **This is a WIZARD-ONLY stage. Make zero changes in `~/pr-review-bot`** — not to `contracts/provisioning.json`, not to `scripts/gen_contract.py`, not to its CI, not to its `CLAUDE.md`. It is a separate repository and a separate rollout stage. Reading it (and `git -C` against it) is expected; writing to it is out of scope. If a task seems to require a bot-side edit, **stop and report** rather than editing.
- **Never edit the vendored `contracts/provisioning.json` by hand.** It carries a `"generated_by": "scripts.gen_contract -- do not edit by hand"` marker. The only legitimate ways it changes here are the initial `git show` extraction (Task 1) and `scripts/update_bot_contract.py` (Task 2). Resolving a red parity test by editing the vendored copy inverts the entire direction this stage exists to establish.
- **Never commit on someone else's behalf without being asked** (`CLAUDE.md`, Conventions). Every task below ends with an explicit commit step; that is the request. `scripts/update_bot_contract.py` itself must **never** `git add` or `git commit` (spec §8: "No automatic committing of a bumped pin or vendored contract").
- **Fail, don't skip, under CI** (spec §6.3). Any test that needs the sibling checkout must call `pytest.fail(...)` — not `pytest.skip(...)` — when `os.environ.get("CI")` is set and the checkout is absent. A green CI run that silently skipped the only cross-repo assertion is worse than a red one. Locally (no `CI`), skipping is still correct.
- **Before pushing: `uv run pytest -v` and `uv run ruff check .` must both be clean** (`CLAUDE.md`, Conventions), and **any push to `main` requires the `deploy-verify` skill first**. This plan ends with commits on a branch — **never `git push`**.
- Fast iteration while working: `uv run pytest -m "not db and not browser" -n 4`. Full suite before each commit — `addopts` already pins `-n 4 --dist=loadgroup`, do not override it.
- **Never assert on a live table's column list.** The one Postgres is shared across the whole `xdist_group("db")`, and tier-2 DROPs the tables then lets the bot widen them back to 22 columns. Any "the wizard's table has exactly N columns" assertion is order-dependent and will flake. Assert against `router._RUNTIME_CONFIG_SCHEMA`'s DDL **text** instead.
- **Secret handling overrides everything here** (`CLAUDE.md`, first section). The vendored contract carries env-var *names*, SQL types, and non-secret operational defaults only. Before committing it in Task 1, read it once and confirm no string in it looks like a key, a DSN with credentials, or a PEM fragment. If one does: **stop, do not commit, name the value, and recommend rotation.** Never modify `.claude/hooks/check_env_access.py` or `redact_output.py`.
- **`static/index.html` is not touched by this plan** — no `ui-visual-review` invocation is needed, and if a task appears to require a markup/CSS change, that is a signal the task has drifted.
- **Out of scope, do not do here:** spec §9's `CLAUDE.md` sections (Stage 5); spec §6.2's advisory scheduled job (Stage 4, and it lives in the bot anyway); any change to `_SLOT_CONFIG_SCHEMA`, which §7.1 leaves full **deliberately, not by omission**; client-side input validation (§4.4).

---

### Task 1: Vendor the contract, bump the pin, prove the copy is honest

The two halves of one fact land together, and the first of spec §6.1's wizard-side assertions lands with them so the copy cannot go stale unnoticed. This task deliberately adds no `router.py` change: nothing shrinks until Task 4.

`.ci/pr-review-bot-ref` currently pins `eb3b062278055d1fd8bf1374ebe88ffa637146c3`, which predates Stage 1 *and* Stage 2. It moves to the Stage-2 merge commit on the bot's `origin/main` (`3fee149` as of this writing — re-resolve `origin/main` fresh rather than hard-coding this sha, in case more commits land before this task runs).

The pin file's format becomes normative here (spec §5.5): **40 lowercase hex characters on one line, optional trailing newline, `#`-prefixed comment lines permitted** so a deliberately-held pin can record why. Permitting comments is what breaks CI's current `cat`-based read, so that changes in the same commit.

**Files:**
- Create: `contracts/provisioning.json` (extracted verbatim — never hand-edited)
- Modify: `.ci/pr-review-bot-ref`
- Create: `tests/test_bot_contract_parity.py`
- Modify: `.github/workflows/ci.yml` (the "Read pinned pr-review-bot ref" step)
- Read (do not modify): `~/pr-review-bot/contracts/provisioning.json` at `origin/main`, `tests/test_cross_repo_config_ordering.py:50-74` (the existing bot-path convention this mirrors)

**Interfaces:**
- Produces: `contracts/provisioning.json` — the vendored artifact every later task's assertions read.
- Produces: `.ci/pr-review-bot-ref` in §5.5's pinned format.
- Produces, in `tests/test_bot_contract_parity.py`, module-level helpers Tasks 2-3 also use: `CONTRACT_PATH`, `REF_PATH`, `_REPO_ROOT`, `_contract() -> dict`, `_pinned_ref() -> str`, `_require_bot_checkout() -> Path` (fail-don't-skip).

- [ ] **Step 1: Confirm the prerequisite**

```bash
git -C ~/pr-review-bot fetch origin
git -C ~/pr-review-bot rev-parse origin/main
git -C ~/pr-review-bot show origin/main:contracts/provisioning.json | head -3
```

Expected: a 40-hex sha, then the contract's first lines including `"generated_by": "scripts.gen_contract -- do not edit by hand"`.

If `git show` errors with `path 'contracts/provisioning.json' does not exist`, **stop and report: Stage 2 has not landed on `origin/main`.** Do not vendor from any local branch tip.

- [ ] **Step 2: Extract the contract and the pin, together**

```bash
BOT_SHA=$(git -C ~/pr-review-bot rev-parse origin/main)
mkdir -p contracts
git -C ~/pr-review-bot show "$BOT_SHA:contracts/provisioning.json" > contracts/provisioning.json
printf '%s\n' "$BOT_SHA" > .ci/pr-review-bot-ref
```

Extraction by git object, not by copying the sibling's worktree file — a dirty sibling tree must be irrelevant (spec §5.5 step 3).

- [ ] **Step 3: Read the vendored file once, before committing it**

Run: `cat contracts/provisioning.json`

Confirm by reading:
- `"generated_by"` and `"contract_version": 1` are the first two keys.
- Every `env_vars` entry is `{"placement": "..."}` and nothing else — a name and a placement word, no value.
- `runtime_config.provisioner_required` is `["id", "provider", "updated_at"]`, and `provisioner_required_one_of` is the three `*_key_index` columns.
- `runtime_config.bot_backfilled` carries 15 entries whose `default`s are numbers, `false`, and the string `"04:00:00"` — and confirm that `"04:00:00"` is present, since removing this wizard's own hand-typed copy of that literal is one of §7.1's named wins.
- `slot_config.optional` is the two `vertex_gcp_*` columns.
- **No string anywhere looks like a credential, a DSN with a password, or a PEM fragment.** If one does: stop, do not commit, and follow the secret-handling constraint above.

- [ ] **Step 4: Write the failing tests**

Create `tests/test_bot_contract_parity.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_bot_contract_parity.py -v`
Expected: PASS, all 6 tests.

There is no red-green cycle for this task and pretending to one would be dishonest: Step 2 already put the artifact and the pin in place, and these are *conformance* assertions against them. A failure here is a real defect in Step 2's extraction — most likely the sha and the extracted bytes came from different commits. **Stop and report rather than loosening an assertion or editing the vendored file.**

To confirm the freshness assertion is not vacuous, observe it firing once:

```bash
python3 -c "
from pathlib import Path
p = Path('contracts/provisioning.json')
p.write_text(p.read_text(encoding='utf-8').replace('\"contract_version\": 1', '\"contract_version\": 1 '), encoding='utf-8', newline='\n')
"
uv run pytest tests/test_bot_contract_parity.py -k pinned_ref -v ; echo "exit=$?"
git checkout contracts/provisioning.json
```

Expected: red on `test_vendored_contract_matches_the_bot_at_the_pinned_ref` (a one-byte whitespace difference is enough), then clean after the `git checkout`. If it stayed green, the comparison is not byte-exact — that is a defect in Step 4, **stop and report**.

- [ ] **Step 6: Teach CI to read the pinned ref in its declared format**

Comment lines are now legal in `.ci/pr-review-bot-ref`, and `.github/workflows/ci.yml`'s existing `echo "sha=$(cat .ci/pr-review-bot-ref)"` would feed a comment line straight into `actions/checkout`'s `ref:`. Replace that one step's `run:` with a read that matches `_pinned_ref()`'s own rule:

```yaml
      # The pin's format is fixed by pr-review-bot's docs/superpowers/specs/
      # 2026-09-10-cross-repo-contract-direction-design.md section 5.5:
      # exactly one 40-hex line, plus optional '#' comment lines so a
      # deliberately-held pin can record why. A plain `cat` would hand a
      # comment line to actions/checkout as a ref -- grep the sha line
      # itself, and fail loudly if there isn't exactly one.
      - name: Read pinned pr-review-bot ref
        id: pr_review_bot_ref
        run: |
          sha="$(grep -m1 -E '^[0-9a-f]{40}$' .ci/pr-review-bot-ref)"
          test -n "$sha" || { echo "no 40-hex sha line in .ci/pr-review-bot-ref"; exit 1; }
          echo "sha=$sha" >> "$GITHUB_OUTPUT"
```

Leave the surrounding comment block above it, and the `Checkout pr-review-bot` step, as they are — Task 5 revises that comment's description of what the cross-repo tests now do.

- [ ] **Step 7: Run the full suite and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: all green. Nothing existing changes behaviour in this task; the three tests in `tests/test_cross_repo_config_ordering.py` now run against a *newer* pinned bot and must still pass — `test_runtime_config_column_parity` in particular, since the bot's 22-column `RUNTIME_CONFIG_COLUMNS` is unchanged by Stages 1-2. If it goes red, **stop and report**: a bot-side column change landed that this stage's Task 4 shrink would resolve, and doing Task 4 early to unblock it inverts the plan's dependency order.

- [ ] **Step 8: Commit**

```bash
git add contracts/provisioning.json .ci/pr-review-bot-ref tests/test_bot_contract_parity.py .github/workflows/ci.yml
git commit -m "Vendor pr-review-bot's provisioning contract, pinned to the ref it came from"
```

---

### Task 2: `scripts/update_bot_contract.py` — both files or neither

Task 1 did the extraction by hand, once. This task makes it repeatable and atomic, implementing spec §5.5's five numbered steps. The contract and the pin are two halves of one fact, so a run that advanced one and not the other would leave the repo in a state Task 1's freshness test correctly calls broken — the script must make that state unreachable.

Step 4 of §5.5 ("run the wizard's parity tests against the extracted copy") is why this task follows Task 1 rather than preceding it: there has to be a parity test file for the script to gate on.

This repo has no `scripts/` directory yet. It is a namespace package — no `__init__.py`, matching how the bot runs `python -m scripts.gen_contract` — and `pyproject.toml`'s `pythonpath = [".", "tests"]` already makes it importable from the repo root. Verify this in the current `pyproject.toml` before assuming it; if the wizard's own layout differs, adapt to what is actually there rather than to this assumption.

**Files:**
- Create: `scripts/update_bot_contract.py`
- Create: `tests/test_update_bot_contract.py`
- Modify: `.dockerignore`
- Modify: `README.md` (one line documenting the command)
- Read (do not modify): `tests/test_bot_contract_parity.py` (Task 1)

**Interfaces:**
- Consumes: `contracts/provisioning.json` and `.ci/pr-review-bot-ref` (Task 1).
- Produces:
  - `scripts.update_bot_contract.CONTRACT_PATH: str` — `"contracts/provisioning.json"`
  - `scripts.update_bot_contract.REF_PATH: str` — `".ci/pr-review-bot-ref"`
  - `scripts.update_bot_contract.PARITY_TESTS: str` — `"tests/test_bot_contract_parity.py"`
  - `scripts.update_bot_contract.resolve_bot_path(override: str | None) -> Path`
  - `scripts.update_bot_contract.read_pinned_ref(root: Path) -> str` — the writer-side twin of the test's `_pinned_ref()`, same format rule
  - `scripts.update_bot_contract.resolve_origin_main(bot_path: Path) -> str`
  - `scripts.update_bot_contract.extract_contract(bot_path: Path, sha: str) -> str`
  - `scripts.update_bot_contract.main(argv: list[str] | None = None) -> int` — `--bot-path`, `--root`
- Produces nothing importable by `router.py`. This is a developer tool; the running service never reads it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_update_bot_contract.py`. Test the pure pieces directly and the atomicity via a fake bot repo built with real `git` in `tmp_path`:

```python
"""scripts/update_bot_contract.py -- the vendor-and-pin updater.

The property worth testing hardest is ATOMICITY: contracts/provisioning.json
and .ci/pr-review-bot-ref are two halves of one fact ("which bot contract
are we built against"), so a run whose parity check fails must leave BOTH
files exactly as it found them. A run that advanced the contract but not
the pin produces precisely the state
tests/test_bot_contract_parity.py::test_vendored_contract_matches_the_bot_at_
the_pinned_ref exists to catch, and having the tool that maintains the pair
be the thing that breaks it would be worse than having no tool.
"""
```

Tests to write (names are the specification; the executing agent writes the bodies against the interfaces above):

- `test_read_pinned_ref_accepts_a_bare_sha`
- `test_read_pinned_ref_accepts_comment_lines_above_the_sha`
- `test_read_pinned_ref_rejects_two_shas` — a second sha line is ambiguous, not a "take the first" situation
- `test_read_pinned_ref_rejects_a_ref_name` — `"main"` must raise, not be passed through to `git`
- `test_read_pinned_ref_rejects_uppercase_hex` — the format is lowercase; normalizing here would let two spellings of one pin coexist
- `test_resolve_origin_main_never_returns_local_head` — build a `tmp_path` git repo whose local `HEAD` is ahead of `origin/main`, assert the resolved sha is `origin/main`'s (spec §5.5 step 2: a squash-merged branch tip becomes an un-dangling-able pin)
- `test_extract_contract_reads_by_git_object_not_worktree` — commit a contract, then overwrite the worktree file with junk; the extraction must return the committed bytes
- `test_extract_contract_raises_when_the_path_is_absent_at_that_sha` — the Stage-2-hasn't-landed case, and it must name the path and the sha
- `test_a_green_run_writes_both_files_and_prints_old_to_new`
- `test_a_red_parity_run_writes_neither_file` — the central one. Monkeypatch the parity-test invocation to fail; assert both files are byte-identical to before, and that the failure output is printed rather than swallowed
- `test_it_refuses_to_run_with_either_file_already_dirty` — the restore-on-failure path writes remembered bytes back, so a pre-existing uncommitted edit to either file could be clobbered by it. Refusing up front means `git checkout` is always a sufficient recovery
- `test_it_never_invokes_git_add_or_git_commit` — AST-parse the module and assert no string literal in it is `"add"` or `"commit"` in a `git` argument list (spec §8: "No automatic committing … staging and committing stay explicit, per CLAUDE.md's 'never commit on someone else's behalf'")
- `test_every_file_call_declares_encoding_and_newline` — `.gitattributes` pins this working tree to `eol=lf`; a locale-default write would produce a CRLF contract that fails Task 1's byte-compare on a Windows operator's machine and nowhere else

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_update_bot_contract.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'scripts'`.

- [ ] **Step 3: Write the script**

Create `scripts/update_bot_contract.py`. Structure — spec §5.5's five steps in order, with the sixth thing the spec implies (restore on failure) made explicit:

```python
"""Re-vendor pr-review-bot's provisioning contract and its pin, together.

    uv run python -m scripts.update_bot_contract

contracts/provisioning.json is a VERBATIM COPY of a file generated in the
sibling pr-review-bot repository (its scripts/gen_contract.py, byte-compared
by its own CI). .ci/pr-review-bot-ref records which commit that copy came
from. These are two halves of one fact -- which bot contract this wizard is
built against -- so this script rewrites BOTH or NEITHER. See that project's
docs/superpowers/specs/2026-09-10-cross-repo-contract-direction-design.md
section 5.5.

Five steps, in order:

  1. git -C <bot> fetch origin
  2. resolve origin/main -- never local HEAD, never a feature-branch tip. A
     squash-merged branch tip becomes a pin that can never be resolved again
     once the branch is deleted.
  3. git -C <bot> show <sha>:contracts/provisioning.json -- extraction by git
     OBJECT, so no worktree is created inside the sibling's .git and a dirty
     sibling tree is irrelevant.
  4. run this repo's own parity tests against the extracted copy.
  5. green: write both files, print old -> new. red: write neither, print the
     failures.

This script NEVER stages and NEVER commits. Reviewing and committing a
contract bump is a deliberate act (that design's section 8, and this repo's
CLAUDE.md: never commit on someone else's behalf). It also never edits the
contract's contents -- the file carries a do-not-edit marker and the bot's
CI byte-compares it against its generator.
"""
```

Implementation notes the executing agent must honour:

- `resolve_origin_main` = `git -C <bot> rev-parse origin/main`, and it must **reject** a sha that does not match `^[0-9a-f]{40}$` rather than pass it on.
- Step 4 runs `[sys.executable, "-m", "pytest", PARITY_TESTS, "-q", "-p", "no:cacheprovider"]` with `cwd=root`; do **not** pass `-n`, so `addopts`' pinned `-n 4` is inherited unchanged (a bespoke worker count here could mask an xdist-only failure the real suite would hit). Capture and print the output on failure.
- Atomicity is implemented as *remember, write, restore*: refuse via `git status --porcelain -- <both paths>` if either is already dirty; read both files' bytes into memory; write the candidates; run step 4; on failure write the remembered bytes back and return non-zero. Document that ordering in the function's docstring, including why the dirty-tree refusal is what makes the restore safe.
- `read_pinned_ref` must be the same format rule as `tests/test_bot_contract_parity.py::_pinned_ref`. **Duplicate it deliberately, with a comment naming the other copy** — this repo does not import test helpers into shipped modules, and the two are ~8 lines each. If they ever disagree, `test_read_pinned_ref_*` and `test_the_pinned_ref_file_is_a_single_forty_hex_sha` both fail, which is the intended coupling.
- Every write: `encoding="utf-8", newline="\n"`.
- Print `old -> new` for both files, naming the sha on each side, and say explicitly that nothing was staged.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_update_bot_contract.py -v`
Expected: PASS.

- [ ] **Step 5: Run it for real, against an unchanged pin**

Run: `uv run python -m scripts.update_bot_contract`
Expected: it resolves the same sha Task 1 pinned, the parity tests pass, both files are rewritten with identical bytes, and `git status` reports a clean tree afterwards.

If `git status` is **not** clean, the extraction is not byte-stable — most likely a newline or encoding difference between the `git show > file` redirect Task 1 used and the script's own write. That is a defect in this step, not something to commit around: **stop and report.**

- [ ] **Step 6: Keep the dev-only files out of the deploy image**

`Dockerfile`'s `COPY . .` would otherwise carry `contracts/` and `scripts/` into the runtime image. Neither is read by the running service — `router.py` never opens the contract; it is a test fixture and a developer tool. `CLAUDE.md`'s Docker-image section is explicit that layers cost real size, and `.dockerignore` already excludes `**/tests/` and `docs/superpowers/` on exactly this reasoning.

Add to `.dockerignore`, after the existing `**/tests/` block:

```
# Dev-only cross-repo tooling: the vendored pr-review-bot contract is a test
# fixture (tests/test_bot_contract_parity.py) and update_bot_contract.py is a
# developer command. The running service never reads either -- same reasoning
# as **/tests/ above.
contracts/
scripts/
```

Do not touch `Dockerfile` itself — `tests/test_dockerfile.py` pins its properties and none of them change here.

- [ ] **Step 7: Document the command**

Add one line to `README.md`, next to the existing test/lint instructions:

> Re-vendor pr-review-bot's provisioning contract and its pin (rewrites `contracts/provisioning.json` and `.ci/pr-review-bot-ref` together, or neither; never stages or commits): `uv run python -m scripts.update_bot_contract`

- [ ] **Step 8: Run the full suite and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add scripts/update_bot_contract.py tests/test_update_bot_contract.py .dockerignore README.md
git commit -m "Add update_bot_contract.py: rewrite the vendored contract and its pin atomically"
```

---

### Task 3: The remaining §6.1 parity assertions

Spec §6.1's four remaining wizard-side checks. Every one reads only this repo's own tree — the vendored contract plus `router.py`'s own constants — so none of them can skip, which is the point: they are the replacements that must be green *before* Task 4 shrinks the constants and Task 5 removes the old tests.

Before writing this task's tests, read `router.py`'s current `_LLM_ENV_VAR_NAMES`, `_KEY_INDEX_COLUMNS`, `_GENERIC_OPERATIONAL_ENV_DEFAULTS`, `_SLOT_CONFIG_SCHEMA`, `_RUNTIME_CONFIG_SCHEMA`, and `bulk_push_render_env_vars` in full — confirm the line ranges and the three env-var-assembly shapes described below against the actual current source before writing the AST extractor, since the design doc's own line numbers may have drifted since it was written.

The Render push-set is assembled inside `bulk_push_render_env_vars` from three shapes: `env_vars["LITERAL"] = ...` assignments, one `env_vars[credential_var] = ...` whose key is a variable looked up through `_LLM_ENV_VAR_NAMES`, and `env_vars.update(_GENERIC_OPERATIONAL_ENV_DEFAULTS)`. An AST walk over the function recovers the full name set with no test harness, no session fixture, and no Postgres. Find the existing behavioural counterpart that pins the actual runtime dict produced by a fully-populated session (search `tests/test_onboarding_router.py` for a test asserting on `bulk_push_render_env_vars`'s output) and confirm it still exists — so the static extractor cannot silently diverge from what the endpoint really pushes.

**Files:**
- Modify: `tests/test_bot_contract_parity.py` (append)
- Read (do not modify): `router.py`'s `_LLM_ENV_VAR_NAMES`, `_KEY_INDEX_COLUMNS`, `_GENERIC_OPERATIONAL_ENV_DEFAULTS`, `_SLOT_CONFIG_SCHEMA`, `_RUNTIME_CONFIG_SCHEMA`, `bulk_push_render_env_vars`; `contracts/provisioning.json`

**Interfaces:**
- Consumes: Task 1's `_contract()`, `_REPO_ROOT`.
- Produces two helpers Tasks 4 and 5 both read:
  - `_render_push_set() -> set[str]` — every env-var name `bulk_push_render_env_vars` can push, recovered by AST
  - `_ddl_column_names(ddl_text: str, table: str) -> list[str]` — column *names* only, from this repo's own DDL constants. This is §7.2's surviving "much smaller column-name extractor": it reads only the wizard's own source, never the bot's, so there is no cross-repo type-string normalization to get wrong.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bot_contract_parity.py` (add `import ast` and `import inspect` to the stdlib imports, and `import router` below `import pytest` — adjust the import if this repo's package layout names the module differently; verify with `python -c "import router"` from the repo root first):

```python
def _render_push_set() -> set[str]:
    """Every env-var name bulk_push_render_env_vars can ever push.

    Recovered by AST from that function's own source rather than by driving
    the endpoint: the names are what the contract constrains, and the values
    all come from visitor session state. Three shapes, all deliberate:

      env_vars["LITERAL"] = ...   -> the name, directly
      env_vars[credential_var]    -> the active provider's credential; the
                                     possible names are _LLM_ENV_VAR_NAMES'
                                     own, and the assertion below pins that
                                     there is exactly ONE such dynamic key,
                                     so a second one cannot slip in unnamed
      env_vars.update(NAME)       -> that module constant's keys

    A behavioural counterpart in tests/test_onboarding_router.py pins the
    real dict a fully-populated session produces -- so this static view
    cannot drift from the endpoint's actual behaviour without one of the
    two going red.
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
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "env_vars"
            ):
                if isinstance(target.slice, ast.Constant):
                    names.add(target.slice.value)
                else:
                    dynamic += 1
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "update"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "env_vars"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
        ):
            names |= set(getattr(router, node.args[0].id))
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
```

- [ ] **Step 2: Run the tests and read the failures carefully**

Run: `uv run pytest tests/test_bot_contract_parity.py -v`

Expected: **one failure, and exactly one** —
`test_the_wizard_declares_no_column_the_bot_backfills`, reporting all 15 `bot_backfilled` columns as declared in `router._RUNTIME_CONFIG_SCHEMA`. That is correct and expected: it is the red half of Task 4's red-green cycle, written here so the assertion exists and is *demonstrated to bite* before the constants it guards shrink. Task 4 turns it green.

Every other test in this task must pass on its first run. If any other one is red, **stop and report** which — each is a conformance check against the current, unchanged `router.py`, so a failure is a real drift between this wizard and the pinned bot, not a missing implementation:
- `test_the_push_set_covers_every_always_synced_env_var` red → a credential the wizard never pushes; a provisioned deployment is broken today.
- either `trespasses` test red → a live two-sources-of-truth bug.
- either `providers`-block test red → a rename landed over there; re-vendor before doing anything else.

**Never resolve any of these by loosening an assertion or editing `contracts/provisioning.json`.**

- [ ] **Step 3: Mark the one expected failure, so the suite can stay green until Task 4**

Add `@pytest.mark.xfail(strict=True, reason=...)` to `test_the_wizard_declares_no_column_the_bot_backfills` only, with a reason naming Task 4 of this plan and the fact that the marker is removed there. `strict=True` is load-bearing: it makes an *unexpected pass* a failure too, so the marker cannot silently outlive the shrink it is waiting on.

This is the one place in this plan where a test is landed red-on-purpose. The alternative — folding this assertion into Task 4 — would violate §10's ordering requirement that the replacement tests exist and pass before the constants shrink, and would leave the shrink unguarded at the moment it happens.

- [ ] **Step 4: Run the full suite and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: all green, with one `xfailed`. Nothing in `router.py` or any existing test changes in this task.

- [ ] **Step 5: Commit**

```bash
git add tests/test_bot_contract_parity.py
git commit -m "Assert the wizard's push-set and provisioning writes against the vendored contract"
```

---

### Task 4: Collapse §7.1's duplication

Only now, with Task 3's replacements green, do the constants shrink. Read `router.py`'s current `_RUNTIME_CONFIG_SCHEMA`, `_RUNTIME_CONFIG_DEFAULTS`, `_GENERIC_OPERATIONAL_ENV_DEFAULTS`'s comment, and `_seed_provider_config` in full before editing, and confirm every line-range reference below against the actual current file rather than trusting it verbatim.

Three changes in `router.py`, each with a reason the contract now carries:

- **`_RUNTIME_CONFIG_SCHEMA` shrinks from 22 hand-typed columns to 6** — the contract's `provisioner_required` (`id`, `provider`, `updated_at`) plus all three `provisioner_required_one_of` columns. Spec §3.1's boot-time `ADD COLUMN IF NOT EXISTS` widening (landed in Stage 1: `review_queue/store.py::_widen_statements`) removes the "must be the FULL column set" requirement that this file's own comment documents, *along with its stated reason*. The comment must be rewritten, not trimmed: it currently explains a constraint that no longer exists, and a reader who finds the constraint gone but the explanation intact will restore the columns.
- **`_RUNTIME_CONFIG_DEFAULTS` is deleted outright** — 15 hand-copied values, including the `"04:00:00"` string literal. The bot's `_backfill_runtime_config` fills every one of them at boot with `COALESCE(runtime_config.col, EXCLUDED.col)`, which cannot clobber a value anyone deliberately wrote. Deleting the copy is how the reset-time logical/wire type mismatch gets *removed* rather than fixed (spec §7.1).
- **The stale provenance comments are corrected** — any comment citing the bot's `_GENERIC_OPERATIONAL_ENV_ATTRS` as `_GENERIC_OPERATIONAL_ENV_DEFAULTS`' source is wrong: that tuple is now empty over there, and `GITHUB_TARGET_REPO` actually lives in `_ALWAYS_SYNCED`. The behaviour is right, only the provenance claim is wrong. Any reference to the bot's removed `_seed_runtime_config_defaults` becomes `_backfill_runtime_config`.

`_SLOT_CONFIG_SCHEMA` is **not** touched (spec §7.1, and Task 3 pins that it stays the contract's full shape).

**Files:**
- Modify: `router.py` (`_GENERIC_OPERATIONAL_ENV_DEFAULTS`'s comment, `_RUNTIME_CONFIG_SCHEMA`, delete `_RUNTIME_CONFIG_DEFAULTS`, `_seed_provider_config`'s `runtime_config` INSERT and its comment/docstring)
- Modify: `tests/test_bot_contract_parity.py` (remove the `xfail` marker)
- Modify: `tests/test_onboarding_router.py` (the `_RUNTIME_CONFIG_DEFAULTS`-dependent tests)

**Interfaces:**
- Consumes: Task 3's parity assertions.
- Removes: `router._RUNTIME_CONFIG_DEFAULTS`. Nothing outside `router.py` and `tests/test_onboarding_router.py` reads it — confirm with `grep -rn "_RUNTIME_CONFIG_DEFAULTS" --include='*.py' --include='*.md' .` before deleting, and if `CLAUDE.md` or `ISSUES.md` mention it, note the reference for Stage 5 rather than editing those files here.

- [ ] **Step 1: Write the failing tests**

Find every existing test in `tests/test_onboarding_router.py` that depends on `_RUNTIME_CONFIG_DEFAULTS` or asserts the tuning knobs get written by `_seed_provider_config` (search for `_RUNTIME_CONFIG_DEFAULTS`, `dispatcher_idle_sleep_seconds`, `cooldown_base_seconds` in that file). Rewrite the one that asserts the seed writes tuning defaults into something like:

```python
def test_seed_provider_config_writes_only_what_this_wizard_uniquely_knows(
    db_url, db_exec, db_query
):
    """The 2026-09-10 contract-direction change, from this side. This wizard
    no longer copies pr-review-bot's 15 operational defaults: it writes
    provider, the chosen provider's key-slot index, and updated_at, and the
    bot fills the rest at boot from its OWN declared defaults (its
    review_queue/store.py::_widen_statements + _backfill_runtime_config,
    landed 2026-09-10). Those columns coming back NULL here is now CORRECT --
    the bot's backfill is what makes them non-NULL, and tests/
    test_cross_repo_config_ordering.py::test_wizard_seed_leaves_bot_boot_ready
    is what proves the whole chronology end to end against a live Postgres.

    Selecting from the columns the narrow table actually declares, not from
    the bot's full 22: after tier-2 has run, this shared Postgres may hold a
    table the bot already widened, so a SELECT of a tuning column would
    succeed or raise UndefinedColumn depending on test order.
    """
    db_exec("DROP TABLE IF EXISTS runtime_config CASCADE")
    ok = router._seed_provider_config(db_url, "groq", "llama-3.3-70b-versatile", None, None)
    assert ok is True
    row = db_query(
        "SELECT provider, groq_key_index, gemini_key_index, vertex_key_index "
        "FROM runtime_config WHERE id = 1"
    )
    assert row == [("groq", 0, None, None)]
    assert "cooldown_base_seconds" not in router._RUNTIME_CONFIG_SCHEMA
    assert not hasattr(router, "_RUNTIME_CONFIG_DEFAULTS")
```

Delete any test asserting `_seed_provider_config` never overwrites an operator-set tuning value. Its premise disappears with the constant: after the shrink this wizard writes no tuning column at all, so there is nothing for its COALESCE to protect. That is strictly safer than the behaviour the test was guarding — not a regression — and keeping a test whose setup targets a column the wizard's own DDL no longer declares would be actively misleading about who owns that value. The remaining never-clobber property that *does* still matter (the bot's backfill must not overwrite an operator's dashboard edit) is the bot's own to test, and Stage 1 does.

Also remove the `xfail` marker from `test_the_wizard_declares_no_column_the_bot_backfills` in `tests/test_bot_contract_parity.py`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_onboarding_router.py -k seed_provider_config tests/test_bot_contract_parity.py -v`
Expected: red — `assert not hasattr(router, "_RUNTIME_CONFIG_DEFAULTS")` fails, `"cooldown_base_seconds" not in router._RUNTIME_CONFIG_SCHEMA` fails, and `test_the_wizard_declares_no_column_the_bot_backfills` now fails for real rather than xfailing.

- [ ] **Step 3: Shrink the schema constant**

Replace `_RUNTIME_CONFIG_SCHEMA` with the narrow DDL and a comment that argues from the contract. Types are the bot's `RUNTIME_CONFIG_COLUMNS` declarations for those six columns, verbatim:

```python
# Duplicated (not imported) from the sibling review-engine project's
# (~/pr-review-bot) review_queue/store.py -- same duplication-not-import
# convention as _SLOT_CONFIG_SCHEMA above, and for the same reason: a
# freshly-provisioned Supabase database has no schema at all yet (that
# project's own store.init_pool() is what normally creates it, on the
# deployed service's first boot), and this wizard runs BEFORE that first
# boot.
#
# DELIBERATELY NARROWER than that project's full 22-column
# RUNTIME_CONFIG_COLUMNS: exactly contracts/provisioning.json's
# runtime_config.provisioner_required (id, provider, updated_at) plus all
# three provisioner_required_one_of columns. All three key-index columns are
# declared even though only the chosen provider's is ever written -- the
# column has to exist before the INSERT below can name it.
#
# This used to have to be the FULL column set, because CREATE TABLE IF NOT
# EXISTS is a no-op against an existing table and that project's own
# init_pool() would then never widen it. **That is no longer true**: as of
# its 2026-09-10 bot-owned-defaults work, init_pool() widens both tables
# itself with ALTER TABLE ... ADD COLUMN IF NOT EXISTS
# (review_queue/store.py::_widen_statements) and then backfills every NULL
# column from its own declared Settings defaults
# (_backfill_runtime_config, which uses COALESCE per column and so cannot
# clobber a value this wizard or an operator wrote). A narrower table here
# is now self-healing, and this wizard carrying a copy of that project's 15
# operational defaults was exactly the hand-duplication the contract exists
# to end. Do NOT re-add the tuning columns.
# tests/test_bot_contract_parity.py asserts this covers
# provisioner_required and declares nothing the bot backfills.
_RUNTIME_CONFIG_SCHEMA = """
CREATE TABLE IF NOT EXISTS runtime_config (
    id                  INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    provider            TEXT,
    updated_at          TEXT NOT NULL,
    gemini_key_index    INTEGER,
    groq_key_index      INTEGER,
    vertex_key_index    INTEGER
);
ALTER TABLE runtime_config ENABLE ROW LEVEL SECURITY;
"""
```

Delete `_RUNTIME_CONFIG_DEFAULTS` and its whole comment block entirely.

- [ ] **Step 4: Simplify the INSERT**

In `_seed_provider_config`, replace the `runtime_config` INSERT with:

```python
            # key_index_column is looked up through _KEY_INDEX_COLUMNS above,
            # never built from `provider`, so that dict IS the injection
            # guard for the f-strings here. All three columns are
            # unconditionally overwritten on every call -- a redo of the
            # LLM-provider frame really is a reconfiguration of exactly
            # these three, and they are the only runtime_config values this
            # wizard has any claim to. Every other column is the deployed
            # service's own to fill at boot (see _RUNTIME_CONFIG_SCHEMA's
            # comment): this wizard no longer writes, and no longer needs a
            # COALESCE to avoid clobbering, any operational default.
            conn.execute(
                "INSERT INTO runtime_config "
                f"(id, provider, {key_index_column}, updated_at) "
                "VALUES (1, %s, 0, %s) "
                "ON CONFLICT (id) DO UPDATE SET "
                "provider = EXCLUDED.provider, "
                f"{key_index_column} = EXCLUDED.{key_index_column}, "
                "updated_at = EXCLUDED.updated_at",
                (provider, now),
            )
```

Then re-read `_seed_provider_config`'s docstring in full for internal consistency, per `CLAUDE.md`'s "re-read the whole passage afterward" rule — it currently describes the write in terms that predate the shrink.

- [ ] **Step 5: Correct the stale provenance comments**

In `_GENERIC_OPERATIONAL_ENV_DEFAULTS`'s comment: the source is the bot's `_ALWAYS_SYNCED`, not `_GENERIC_OPERATIONAL_ENV_ATTRS` (which is now empty over there), and any "keep in sync by hand, nothing automated ties the two together" clause is no longer true — `tests/test_bot_contract_parity.py::test_generic_operational_env_defaults_are_all_render_pushable` now ties them. Any mention of the bot's removed `_seed_runtime_config_defaults` becomes `_backfill_runtime_config`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_bot_contract_parity.py tests/test_onboarding_router.py -v`
Expected: PASS, including `test_the_wizard_declares_no_column_the_bot_backfills` (now unmarked) and every other `_seed_provider_config` test.

- [ ] **Step 7: Run the full suite and lint**

Run: `uv run pytest -v && uv run ruff check .`

Expected: **one known failure** — the test in `tests/test_cross_repo_config_ordering.py` asserting ordered equality between this wizard's DDL and the bot's full 22-column tuple. That assertion is now false **by design** (spec §7.2), and Task 5 retires the test. Do not fix it by widening the DDL back.

`test_wizard_seed_leaves_bot_boot_ready` must still pass — it is the direct proof that a minimally-provisioned database is boot-ready — and the slot_config column-parity test must still pass, since `_SLOT_CONFIG_SCHEMA` is unchanged. If either is red, **stop and report**: a red chronology test here means the bot's widen-and-backfill does not actually cover what this task just stopped writing, which is a correctness problem, not a test-retirement problem.

- [ ] **Step 8: Commit**

```bash
git add router.py tests/test_bot_contract_parity.py tests/test_onboarding_router.py
git commit -m "Write only what the wizard uniquely knows: shrink the runtime_config DDL, drop the copied defaults"
```

Note in the commit body that the runtime_config column-parity test is expected red until the next commit, and why.

---

### Task 5: Retire §7.2's superseded pieces, and make the chronology test claim the new thing

The old cross-repo integration comes out, in the same commit that leaves the suite green again. Before touching either test file, grep both `tests/test_cross_repo_config_ordering.py` and `tests/test_onboarding_router.py` for every symbol named below (`_parse_ddl_columns`, `_CONSTRAINT_KEYWORDS`, `_bot_runtime_config_columns`, any test with "parity" or "pr_review_bot" in its name, `_pr_review_bot_path`, `_skip_if_bot_checkout_missing`) and confirm the current file contents and line numbers before editing — the design doc's own citations may have drifted, and this plan's own citations are a starting point for that grep, not a substitute for it.

Spec §7.2's dispositions, plus any superseded pieces the design's table does not name that the grep above turns up (the planning pass for this task found: a hand-listed test asserting the wizard no longer pushes 11 specific tuning-knob keys as db-only env vars, a test asserting `_LLM_ENV_VAR_NAMES` against the bot's `providers/registry.py` loaded directly off a sibling checkout, and a duplicate of the slot_config parity check with its own separate bot-path convention — verify all three are still present and named as such before relying on this list):

| Piece | Disposition |
|---|---|
| `test_runtime_config_column_parity` (in `test_cross_repo_config_ordering.py`) | **Retired** — ordered equality, false by design after Task 4. Replaced by Task 3's coverage check. |
| `test_slot_config_column_parity` (in `test_cross_repo_config_ordering.py`) | **Retired** — replaced by Task 3's required-plus-optional check. |
| `_parse_ddl_columns`, `_CONSTRAINT_KEYWORDS`, `_bot_runtime_config_columns` | **Retired** — the DDL regex and the AST literal-eval exist only to compare source text across repos. A vendored JSON contract makes that `json.load` plus set operations. The narrow name-only extractor survives in `test_bot_contract_parity.py`. |
| Any test asserting `_LLM_ENV_VAR_NAMES`/`_KEY_INDEX_COLUMNS` against the bot's `providers/registry.py` loaded from a sibling checkout | **Retired** — replaced by Task 3's providers-block check, which never skips. |
| Any duplicate of the slot_config parity check with its own bot-path convention | **Retired** — a duplicate of `test_slot_config_column_parity`. |
| Any test hand-listing db-only/tuning-knob env-var keys | **Retired** — hand-lists a subset of the keys the contract now derives in full. Replaced by Task 3's `db_only` trespass check. |
| Any now-orphaned imports (e.g. `importlib.util`, an unused `re`, an unused `Path` import, a module-level sibling-path constant) left behind by the retirements above | **Removed** — verify with `grep -n` that nothing else in the file uses them before removing; leaving them is a ruff `F401` failure. |
| `test_wizard_seed_leaves_bot_boot_ready` | **Kept, and strengthened** — see Step 3. |
| `_pr_review_bot_path`, `_skip_if_bot_checkout_missing` | **Kept, narrowed to tier-2 only**, plus §6.3's fail-don't-skip. |
| `.ci/pr-review-bot-ref` | **Kept** in §5.5's format (Task 1), now serving tier-2's checkout *and* the vendored-copy freshness comparison. |
| Wizard CI block (pinned checkout + `PR_REVIEW_BOT_PATH`) | **Kept, essentially unchanged**; its explanatory comment is rewritten. |
| `uv sync --all-extras --dev` in the bot's directory | **Kept, and load-bearing** — tier-2 runs `uv run --directory <bot>`, so the bot's dependencies must be installed. Do not remove it as "no longer needed"; it is more load-bearing now, not less. |
| File name `test_cross_repo_config_ordering.py` | **Kept.** With the parity tests moved out it holds only the seed-then-boot chronology test, which is what "config ordering" referred to all along. Its module docstring, which describes multiple tiers/tests, is rewritten. |

**Files:**
- Modify: `tests/test_cross_repo_config_ordering.py` (delete the retired helpers/tests, rewrite the module docstring, rewrite the chronology test's docstring and add the non-NULL assertion)
- Modify: `tests/test_onboarding_router.py` (delete the retired tests and orphaned imports)
- Modify: `.github/workflows/ci.yml` (the comment above the ref-read step)

**Interfaces:**
- Consumes: `contracts/provisioning.json`'s `runtime_config.bot_backfilled` (Task 1), the narrowed `router._RUNTIME_CONFIG_SCHEMA` (Task 4).
- Removes: `_parse_ddl_columns`, `_CONSTRAINT_KEYWORDS`, `_bot_runtime_config_columns`, and the retired tests named above.

- [ ] **Step 1: Delete the retired pieces**

From `tests/test_cross_repo_config_ordering.py`: delete `_CONSTRAINT_KEYWORDS`, `_parse_ddl_columns`, `_bot_runtime_config_columns`, `test_runtime_config_column_parity`, `test_slot_config_column_parity`, and any now-unused imports those leave behind.

From `tests/test_onboarding_router.py`: delete the tests named in the table above (hand-listed db-only keys, `_LLM_ENV_VAR_NAMES`-against-sibling-registry, the slot_config duplicate) and then remove any imports or module-level constants (e.g. a sibling-path constant, `importlib.util`) that only those tests used — confirm with `grep -n` that nothing else in the file references them first.

- [ ] **Step 2: Give the bot-checkout skip helper §6.3's fail-don't-skip discipline**

Rename `_skip_if_bot_checkout_missing` to `_require_bot_checkout` and make it `pytest.fail(...)` when `os.environ.get("CI")` is set and the checkout is absent, mirroring `tests/test_bot_contract_parity.py`'s helper. The workflow checks the bot out at the pinned ref *specifically so this test runs*; if it is missing there, the workflow broke, and a skip would report that as a pass. Locally, skipping stays correct.

Keep `_pr_review_bot_path`'s existing resolution unchanged — `PR_REVIEW_BOT_PATH` override, else the sibling layout, gated on the bot's own source being present (tier-2 needs the bot's *source and dependencies*, not just its `.git`, which is why this check differs from the parity file's `.git`-only check; note that in a comment so the two are not "unified" later by someone who reads them as duplicates).

- [ ] **Step 3: Rewrite the chronology test to claim the new thing**

Spec §7.2's two required changes, plus the mechanical part that makes the second one real.

The docstring must stop claiming "the wizard seeded 15 values correctly" and start claiming "the bot's ALTER + backfill makes a minimally-provisioned database boot-ready" — the direct regression test for spec §3. And it must additionally assert the tuning columns came back **non-NULL**, or it cannot distinguish a working backfill from a wizard that seeded them anyway.

The column list comes from the vendored contract's `runtime_config.bot_backfilled`, not a hand-typed list — so a column added over there is picked up on the next `update_bot_contract.py` run instead of silently going unchecked. `key_usage_token_cap` is correctly absent from that list: it is in `no_default_by_design`, and a NULL cap paired with a real reset time is "cap intentionally disabled", a valid configured state (spec §3.3).

Read the test's current setup (how it invokes the bot's `store.init_pool()` and `dispatcher_tuning_config.problems()` against the shared Postgres, and what `db_url`/`db_exec`/`db_query` fixtures it already uses) before rewriting it, and preserve that mechanism — only the docstring's claim and the final assertion change in kind:

```python
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

    # ... keep this test's existing mechanism for invoking the bot's
    # store.init_pool() + dispatcher_tuning_config.problems() against db_url
    # via `uv run --directory <bot>`, and its existing assertion that
    # problems() comes back empty ...

    row = db_query(f"SELECT {', '.join(backfilled)} FROM runtime_config WHERE id = 1")[0]
    still_null = [name for name, value in zip(backfilled, row) if value is None]
    assert not still_null, (
        f"the bot's backfill left these NULL: {still_null} -- a wizard-provisioned "
        "deployment would boot into exactly ISSUES.md's 2026-09-09 state"
    )
```

Keep whatever `import json`, `import os`, `import subprocess`, `from pathlib import Path` the file already needs for its existing mechanism; do not remove one still in use by the untouched part of the test.

- [ ] **Step 4: Rewrite the module docstring**

`tests/test_cross_repo_config_ordering.py`'s module docstring describes multiple tiers and multiple tests, at least two of which no longer exist in either form. Replace it with a docstring for the one test the file now holds: what the chronology is, why it needs a live Postgres and the sibling checkout (the only test in this repo that does), that the static parity checks moved to `tests/test_bot_contract_parity.py` and read a vendored contract instead of the bot's source, and that this file's name — "config ordering" — is what it was always about.

- [ ] **Step 5: Rewrite CI's explanatory comment**

Find the comment block above `.github/workflows/ci.yml`'s ref-read step (added/modified in Task 1 Step 6) describing what the pinned checkout is for. If it says anything like "cross-validates the runtime_config/slot_config schemas these two repos hand-duplicate", that is no longer what it does. Rewrite it to say: the pin powers two things — `tests/test_cross_repo_config_ordering.py`'s live-Postgres seed-then-boot chronology, and `tests/test_bot_contract_parity.py`'s check that the vendored `contracts/provisioning.json` still matches the bot at that exact commit. Note that both fail rather than skip here, and that bumping the pin means running `uv run python -m scripts.update_bot_contract` rather than editing the file by hand.

Leave every other `steps:` entry alone — in particular the step installing the bot's own dependencies, which tier-2's `uv run --directory` still needs.

- [ ] **Step 6: Run the full suite and lint**

Run: `uv run pytest -v && uv run ruff check .`
Expected: **fully green, no xfails, no unexpected skips.** Locally, `test_wizard_seed_leaves_bot_boot_ready` and `test_vendored_contract_matches_the_bot_at_the_pinned_ref` are the only two tests that may skip, and only when no sibling checkout is present.

Then confirm the fail-don't-skip guard actually fires, rather than trusting it:

```bash
CI=1 PR_REVIEW_BOT_PATH=/nonexistent uv run pytest \
  tests/test_cross_repo_config_ordering.py tests/test_bot_contract_parity.py -v
```

Expected: two **failures** (not skips), each naming the missing checkout and saying it is required in CI. If either skips, §6.3's discipline is not implemented — **stop and report.**

And confirm the normal local path still skips cleanly:

```bash
PR_REVIEW_BOT_PATH=/nonexistent uv run pytest \
  tests/test_cross_repo_config_ordering.py tests/test_bot_contract_parity.py -v
```

Expected: 2 skipped, everything else passed.

- [ ] **Step 7: Commit**

```bash
git add tests/test_cross_repo_config_ordering.py tests/test_onboarding_router.py .github/workflows/ci.yml
git commit -m "Retire the source-text cross-repo parity tests; the chronology test now proves the bot's backfill"
```

---

## Done criteria

- [ ] `uv run pytest -v` fully green; `uv run ruff check .` clean. No `xfail`, and no skip other than the two sibling-dependent tests when no checkout is present.
- [ ] **§6.1's wizard-side list, all five, exist in `tests/test_bot_contract_parity.py`:** vendored copy byte-identical to the bot at the pinned ref; the Render push-set covers the contract's provisioning responsibilities (superset, not equality); the wizard pushes nothing `db_only`; the write-set covers `provisioner_required` for both tables; `_KEY_INDEX_COLUMNS` and the per-provider credential var names match the `providers` block.
- [ ] **§7.1's duplication is gone:** `_RUNTIME_CONFIG_SCHEMA` declares 6 columns, not 22; `router._RUNTIME_CONFIG_DEFAULTS` does not exist (`grep -rn "_RUNTIME_CONFIG_DEFAULTS" --include='*.py' .` returns nothing); the `"04:00:00"` literal is gone from `router.py`; `_SLOT_CONFIG_SCHEMA` is unchanged and asserted to stay the contract's full shape; `_GENERIC_OPERATIONAL_ENV_DEFAULTS`'s provenance comment names `_ALWAYS_SYNCED` and the test that now guards it.
- [ ] **§7.2's retirements are done:** the source-text parity tests and their supporting helpers (`_parse_ddl_columns`, `_CONSTRAINT_KEYWORDS`, `_bot_runtime_config_columns`) are gone from `tests/test_cross_repo_config_ordering.py`; the superseded sibling-dependent tests and their orphaned imports are gone from `tests/test_onboarding_router.py`.
- [ ] **§7.2's keeps are intact:** `.ci/pr-review-bot-ref` in §5.5's format; `_pr_review_bot_path` narrowed to tier-2; the CI pinned-checkout block and its bot-dependency-install step both still present.
- [ ] **The tier-2 chronology test still exercises live-Postgres chronology** — real `db_url`, real `_seed_provider_config`, real `uv run --directory <bot> ...` subprocess against the bot's own `store.init_pool()` and `dispatcher_tuning_config.problems()` — with a rewritten docstring that claims the backfill rather than the seed, and an added assertion that every `bot_backfilled` column came back non-NULL. It was not converted to a static or mocked test.
- [ ] **§6.3 is implemented and observed:** `CI=1 PR_REVIEW_BOT_PATH=/nonexistent uv run pytest tests/test_cross_repo_config_ordering.py tests/test_bot_contract_parity.py` produces two failures, not two skips.
- [ ] `uv run python -m scripts.update_bot_contract` runs green against an unchanged pin and leaves a clean `git status`; a forced parity failure leaves **both** files untouched; the module contains no `git add` and no `git commit`.
- [ ] `contracts/provisioning.json` was never hand-edited (`git log -p -- contracts/provisioning.json` shows only Task 1's extraction), and contains no value that is not a name, a placement word, a SQL type, or a non-secret operational default.
- [ ] `.dockerignore` excludes `contracts/` and `scripts/`; `Dockerfile` is unmodified.
- [ ] **Not done here, deliberately:**
  - **No `CLAUDE.md` change.** Spec §9's new top-level section is Stage 5. **Carry this forward:** if this wizard's `CLAUDE.md` states anywhere that the `runtime_config` duplicate "must be the FULL column set" or cites the bot's now-removed `_seed_runtime_config_defaults`, Task 4 makes that claim false. It is not corrected here because §9 revises that same passage in Stage 5 — but a false claim sitting in `CLAUDE.md` between stages is a real hazard, so **raise it with the user when reporting Task 5 done** and let them decide whether to pull the correction forward rather than deciding either way unilaterally.
  - No change in `~/pr-review-bot` of any kind.
  - No advisory cross-repo job (§6.2 — Stage 4, and bot-side).
  - No `_SLOT_CONFIG_SCHEMA` shrink (§7.1, deliberate).
  - No client-side input validation (§4.4).
  - No `git push`. `CLAUDE.md` requires the `deploy-verify` skill before any push to `main`, and this plan ends with commits on a branch.

## Task breakdown summary

| # | Task | Key files |
|---|---|---|
| 1 | Vendor the contract, bump the pin to the Stage-2 sha, add the pin-format + freshness tests, fix CI's ref read | `contracts/provisioning.json`, `.ci/pr-review-bot-ref`, `tests/test_bot_contract_parity.py`, `.github/workflows/ci.yml` |
| 2 | `update_bot_contract.py` — §5.5's 5 steps, both-files-or-neither, never commits | `scripts/update_bot_contract.py`, `tests/test_update_bot_contract.py`, `.dockerignore`, `README.md` |
| 3 | The remaining §6.1 assertions (AST push-set extractor, db_only/never_synced trespass, providers block, DDL coverage); one `xfail(strict=True)` awaiting Task 4 | `tests/test_bot_contract_parity.py` |
| 4 | §7.1's collapse: 22→6 column DDL, delete `_RUNTIME_CONFIG_DEFAULTS`, simplify the INSERT, fix stale provenance comments | `router.py`, `tests/test_onboarding_router.py`, `tests/test_bot_contract_parity.py` |
| 5 | §7.2's retirements + tier-2 rewritten to prove the bot's backfill + fail-don't-skip verified | `tests/test_cross_repo_config_ordering.py`, `tests/test_onboarding_router.py`, `.github/workflows/ci.yml` |

Dependency order is strict: 3 must be green before 4 shrinks the constants, and 4's shrink is what makes 5's retirements true rather than premature. Task 4 deliberately leaves the runtime_config column-parity test red for exactly one commit, which Task 5 closes.
