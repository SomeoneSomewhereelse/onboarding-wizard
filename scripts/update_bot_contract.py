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
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

CONTRACT_PATH = "contracts/provisioning.json"
REF_PATH = ".ci/pr-review-bot-ref"
PARITY_TESTS = "tests/test_bot_contract_parity.py"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def resolve_bot_path(override: str | None) -> Path:
    """The sibling pr-review-bot checkout: --bot-path, else PR_REVIEW_BOT_PATH,
    else the sibling-directory layout every local dev environment has."""
    if override:
        return Path(override)
    env = os.environ.get("PR_REVIEW_BOT_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1].parent / "pr-review-bot"


def read_pinned_ref(root: Path) -> str:
    """The single 40-hex sha in <root>/.ci/pr-review-bot-ref.

    Deliberately duplicated (not imported) from
    tests/test_bot_contract_parity.py::_pinned_ref -- this repo does not
    import test helpers into shipped scripts, and the two are ~8 lines
    each. If they ever disagree, that test file's own format tests and this
    function's tests both fail, which is the intended coupling: the format
    rule has exactly one definition in each of the two places that need it,
    checked against each other by the test suite rather than shared code.

    Format is fixed by that design's section 5.5: exactly one 40-hex line,
    optional trailing newline, '#'-prefixed comment lines permitted so a
    deliberately-held pin can record why. Anything else is a hard error --
    a malformed pin silently read as a ref name is how a "pinned" checkout
    quietly becomes a floating one.
    """
    text = (root / REF_PATH).read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(lines) != 1:
        raise ValueError(f"{REF_PATH} must hold exactly one sha line, found {len(lines)}")
    if not _SHA_RE.match(lines[0]):
        raise ValueError(f"{REF_PATH} is not 40 lowercase hex characters: {lines[0]!r}")
    return lines[0]


def resolve_origin_main(bot_path: Path) -> str:
    """origin/main's current sha -- never local HEAD, never a feature-branch
    tip. A squash-merged branch tip becomes a pin that can never be resolved
    again once the branch is deleted (spec section 5.5 step 2)."""
    result = subprocess.run(
        ["git", "-C", str(bot_path), "rev-parse", "origin/main"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    sha = result.stdout.strip()
    if not _SHA_RE.match(sha):
        raise ValueError(f"origin/main did not resolve to a 40-hex sha: {sha!r}")
    return sha


def extract_contract(bot_path: Path, sha: str) -> str:
    """The contract's exact committed text at `sha`, read by git OBJECT --
    no worktree is created inside the sibling's .git, and a dirty sibling
    tree is irrelevant (spec section 5.5 step 3)."""
    result = subprocess.run(
        ["git", "-C", str(bot_path), "show", f"{sha}:{CONTRACT_PATH}"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise ValueError(
            f"cannot read {CONTRACT_PATH} from pr-review-bot at {sha}: {result.stderr.strip()}"
        )
    return result.stdout


def _run_parity_tests(root: Path, bot_path: Path) -> tuple[bool, str]:
    """Run this repo's own wizard-side parity tests against whatever
    contract/pin currently sit on disk under `root`.

    Forces PR_REVIEW_BOT_PATH to the exact `bot_path` this run extracted
    from, overriding any value already in the environment -- the parity
    file's own bot-checkout resolution (PR_REVIEW_BOT_PATH, else a sibling
    directory) is independent of --bot-path, so without this a run against
    a non-default --bot-path could gate against a *different* checkout, or
    -- if no sibling directory happens to exist either -- silently skip the
    one test that verifies the extraction at all, which a green exit code
    would then misreport as a real pass.

    Never passed -n: the pinned -n 4 in pyproject.toml's addopts is
    inherited unchanged, so a bespoke worker count here cannot mask an
    xdist-only failure the real suite would hit.
    """
    env = {**os.environ, "PR_REVIEW_BOT_PATH": str(bot_path)}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", PARITY_TESTS, "-q", "-p", "no:cacheprovider"],
        cwd=root, env=env, capture_output=True, text=True, encoding="utf-8",
    )
    return result.returncode == 0, result.stdout + result.stderr


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-vendor pr-review-bot's provisioning contract and its pin, together"
    )
    parser.add_argument("--bot-path", default=None, help="path to the pr-review-bot checkout")
    parser.add_argument("--root", default=".", help="this repo's root")
    args = parser.parse_args(argv)

    root = Path(args.root)
    bot_path = resolve_bot_path(args.bot_path)

    contract_file = root / CONTRACT_PATH
    ref_file = root / REF_PATH

    # Refuse up front if either file already carries an uncommitted edit --
    # that is what makes the remember/write/restore sequence below safe: a
    # plain `git checkout` is always a sufficient recovery afterwards, never
    # a recovery that has to distinguish this script's own edit from a
    # pre-existing one. The returncode is checked, not just stdout: `git
    # status` prints nothing to stdout AND exits non-zero (128) when it
    # can't run at all -- not a git repo, git missing, or an unsafe/dubious
    # ownership refusal -- and empty stdout must never be read as "clean"
    # in that case, or this guard silently stops protecting anything.
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", str(CONTRACT_PATH), str(REF_PATH)],
        cwd=root, capture_output=True, text=True, encoding="utf-8",
    )
    if dirty.returncode != 0:
        print(
            f"refusing to run: `git status` failed in {root} (exit {dirty.returncode}): "
            f"{dirty.stderr.strip()} -- cannot verify {CONTRACT_PATH}/{REF_PATH} are clean"
        )
        return 1
    if dirty.stdout.strip():
        print(
            f"refusing to run: {CONTRACT_PATH} and/or {REF_PATH} already has uncommitted "
            "(dirty) changes -- commit or discard them first, then re-run"
        )
        return 1

    # existed_before/old_* let restore-on-failure put each file back to
    # EXACTLY its prior state, including "didn't exist at all" -- writing
    # placeholder content for a file that was previously absent would
    # itself leave the pair inconsistent, the same failure mode the dirty
    # check above exists to keep unreachable.
    contract_existed_before = contract_file.exists()
    ref_existed_before = ref_file.exists()
    old_contract = contract_file.read_text(encoding="utf-8") if contract_existed_before else None
    old_ref_text = ref_file.read_text(encoding="utf-8") if ref_existed_before else None
    try:
        old_sha = read_pinned_ref(root) if ref_existed_before else None
    except ValueError:
        old_sha = None

    subprocess.run(["git", "-C", str(bot_path), "fetch", "origin"], check=True)
    new_sha = resolve_origin_main(bot_path)
    new_contract = extract_contract(bot_path, new_sha)

    contract_file.parent.mkdir(parents=True, exist_ok=True)
    ref_file.parent.mkdir(parents=True, exist_ok=True)
    contract_file.write_text(new_contract, encoding="utf-8", newline="\n")
    ref_file.write_text(new_sha + "\n", encoding="utf-8", newline="\n")

    ok, output = _run_parity_tests(root, bot_path)
    if not ok:
        # Restore -- both files, together, to their EXACT prior state
        # (including absence) -- rather than leaving a partially advanced
        # pair on disk. Nothing is staged either way (this script never
        # runs `git add`/`git commit`), so restoring here is purely a
        # working-tree write, safe because the dirty-check above already
        # guaranteed there was nothing uncommitted to clobber.
        if contract_existed_before:
            contract_file.write_text(old_contract, encoding="utf-8", newline="\n")
        else:
            contract_file.unlink(missing_ok=True)
        if ref_existed_before:
            ref_file.write_text(old_ref_text, encoding="utf-8", newline="\n")
        else:
            ref_file.unlink(missing_ok=True)
        print("parity tests failed against the newly extracted contract -- wrote neither file:")
        print(output)
        return 1

    print(f"{CONTRACT_PATH}: {old_sha or '(none)'} -> {new_sha}")
    print(f"{REF_PATH}: {old_sha or '(none)'} -> {new_sha}")
    print("Nothing was staged. Review the diff and commit deliberately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
