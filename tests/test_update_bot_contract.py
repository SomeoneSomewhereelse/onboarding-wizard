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
from __future__ import annotations

import ast
import inspect
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import update_bot_contract


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def _commit_all(path: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=path, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True, capture_output=True, text=True
    ).stdout.strip()


# ---------------------------------------------------------------------------
# read_pinned_ref
# ---------------------------------------------------------------------------


def test_read_pinned_ref_accepts_a_bare_sha(tmp_path):
    sha = "a" * 40
    (tmp_path / ".ci").mkdir()
    (tmp_path / update_bot_contract.REF_PATH).write_text(sha + "\n", encoding="utf-8")
    assert update_bot_contract.read_pinned_ref(tmp_path) == sha


def test_read_pinned_ref_accepts_comment_lines_above_the_sha(tmp_path):
    sha = "b" * 40
    (tmp_path / ".ci").mkdir()
    (tmp_path / update_bot_contract.REF_PATH).write_text(
        f"# held: waiting on the bot's next release\n{sha}\n", encoding="utf-8"
    )
    assert update_bot_contract.read_pinned_ref(tmp_path) == sha


def test_read_pinned_ref_rejects_two_shas(tmp_path):
    (tmp_path / ".ci").mkdir()
    (tmp_path / update_bot_contract.REF_PATH).write_text(
        f"{'a' * 40}\n{'b' * 40}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError):
        update_bot_contract.read_pinned_ref(tmp_path)


def test_read_pinned_ref_rejects_a_ref_name(tmp_path):
    (tmp_path / ".ci").mkdir()
    (tmp_path / update_bot_contract.REF_PATH).write_text("main\n", encoding="utf-8")
    with pytest.raises(ValueError):
        update_bot_contract.read_pinned_ref(tmp_path)


def test_read_pinned_ref_rejects_uppercase_hex(tmp_path):
    (tmp_path / ".ci").mkdir()
    (tmp_path / update_bot_contract.REF_PATH).write_text("A" * 40 + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        update_bot_contract.read_pinned_ref(tmp_path)


# ---------------------------------------------------------------------------
# resolve_origin_main
# ---------------------------------------------------------------------------


def test_resolve_origin_main_never_returns_local_head(tmp_path):
    remote = tmp_path / "remote"
    remote.mkdir()
    _init_git_repo(remote)
    (remote / "contracts").mkdir()
    (remote / "contracts" / "provisioning.json").write_text("{}", encoding="utf-8")
    origin_sha = _commit_all(remote, "initial")
    subprocess.run(["git", "branch", "-q", "-m", "main"], cwd=remote, check=True)

    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(remote), str(clone)], check=True)
    _init_git_repo(clone)
    (clone / "extra.txt").write_text("local work\n", encoding="utf-8")
    local_sha = _commit_all(clone, "local-only commit, ahead of origin/main")
    assert local_sha != origin_sha

    resolved = update_bot_contract.resolve_origin_main(clone)
    assert resolved == origin_sha
    assert resolved != local_sha


# ---------------------------------------------------------------------------
# extract_contract
# ---------------------------------------------------------------------------


def test_extract_contract_reads_by_git_object_not_worktree(tmp_path):
    bot = tmp_path / "bot"
    bot.mkdir()
    _init_git_repo(bot)
    (bot / "contracts").mkdir()
    (bot / "contracts" / "provisioning.json").write_text('{"committed": true}', encoding="utf-8")
    sha = _commit_all(bot, "commit the contract")

    (bot / "contracts" / "provisioning.json").write_text("junk, not committed", encoding="utf-8")

    extracted = update_bot_contract.extract_contract(bot, sha)
    assert extracted == '{"committed": true}'


def test_extract_contract_raises_when_the_path_is_absent_at_that_sha(tmp_path):
    bot = tmp_path / "bot"
    bot.mkdir()
    _init_git_repo(bot)
    (bot / "README.md").write_text("no contract here\n", encoding="utf-8")
    sha = _commit_all(bot, "no contract yet")

    with pytest.raises(ValueError, match="contracts/provisioning.json"):
        update_bot_contract.extract_contract(bot, sha)


# ---------------------------------------------------------------------------
# main() -- the atomic, both-or-neither run
# ---------------------------------------------------------------------------


def _build_bot_and_root(tmp_path: Path, contract_body: str) -> tuple[Path, Path, str]:
    """A bare 'origin' plus a clone (so origin/main resolves to a real ref),
    and a wizard root pointing at the clone via --bot-path, pre-seeded with
    a pin and a stale contract -- committed, so the dirty-check at the top
    of main() sees a clean tree by default (as a real checkout normally is)
    and individual tests can make it dirty on purpose."""
    bare = tmp_path / "bot-origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)

    seed = tmp_path / "bot-seed"
    seed.mkdir()
    _init_git_repo(seed)
    (seed / "contracts").mkdir()
    (seed / "contracts" / "provisioning.json").write_text(contract_body, encoding="utf-8")
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=seed, check=True)
    _commit_all(seed, "seed contract")
    subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=seed, check=True)

    bot = tmp_path / "bot-clone"
    subprocess.run(["git", "clone", "-q", str(bare), str(bot)], check=True)
    subprocess.run(["git", "branch", "-q", "-m", "main"], cwd=bot, check=True)
    sha = subprocess.run(
        ["git", "-C", str(bot), "rev-parse", "origin/main"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    root = tmp_path / "wizard-root"
    (root / "contracts").mkdir(parents=True)
    (root / ".ci").mkdir()
    (root / "contracts" / "provisioning.json").write_text("stale contract\n", encoding="utf-8")
    (root / ".ci" / "pr-review-bot-ref").write_text("0" * 40 + "\n", encoding="utf-8")
    _init_git_repo(root)
    _commit_all(root, "initial wizard state")
    return bot, root, sha


def test_a_green_run_writes_both_files_and_prints_old_to_new(tmp_path, monkeypatch, capsys):
    bot, root, sha = _build_bot_and_root(tmp_path, '{"contract_version": 1}')
    monkeypatch.setattr(
        update_bot_contract, "_run_parity_tests", lambda root, bot_path: (True, "")
    )

    exit_code = update_bot_contract.main(["--bot-path", str(bot), "--root", str(root)])

    assert exit_code == 0
    assert (root / "contracts" / "provisioning.json").read_text(
        encoding="utf-8"
    ) == '{"contract_version": 1}'
    assert (root / ".ci" / "pr-review-bot-ref").read_text(encoding="utf-8") == sha + "\n"
    out = capsys.readouterr().out
    assert "->" in out
    assert sha in out


def test_a_red_parity_run_writes_neither_file(tmp_path, monkeypatch, capsys):
    bot, root, _sha = _build_bot_and_root(tmp_path, '{"contract_version": 1}')
    monkeypatch.setattr(
        update_bot_contract,
        "_run_parity_tests",
        lambda root, bot_path: (False, "1 failed, 0 passed"),
    )

    before_contract = (root / "contracts" / "provisioning.json").read_text(encoding="utf-8")
    before_ref = (root / ".ci" / "pr-review-bot-ref").read_text(encoding="utf-8")

    exit_code = update_bot_contract.main(["--bot-path", str(bot), "--root", str(root)])

    assert exit_code != 0
    assert (root / "contracts" / "provisioning.json").read_text(encoding="utf-8") == before_contract
    assert (root / ".ci" / "pr-review-bot-ref").read_text(encoding="utf-8") == before_ref
    assert "1 failed" in capsys.readouterr().out


def test_a_red_parity_run_deletes_a_file_that_did_not_exist_before_this_run(
    tmp_path, monkeypatch
):
    """The restore-on-failure path must put each file back to its EXACT
    prior state, including "didn't exist at all" -- writing placeholder
    content for a file this run itself created is a different kind of
    inconsistent pair than the one the dirty-check guards against, but
    just as real: the ref would be advanced while the contract (or vice
    versa) silently reappears at its old content instead of vanishing."""
    bot, root, _sha = _build_bot_and_root(tmp_path, '{"contract_version": 1}')
    ref_file = root / ".ci" / "pr-review-bot-ref"
    ref_file.unlink()
    _commit_all(root, "simulate a first-ever vendor: no pin committed yet")
    monkeypatch.setattr(
        update_bot_contract, "_run_parity_tests", lambda root, bot_path: (False, "boom")
    )

    exit_code = update_bot_contract.main(["--bot-path", str(bot), "--root", str(root)])

    assert exit_code != 0
    assert not ref_file.exists(), "the ref didn't exist before this run and must not be left behind"


def test_it_refuses_to_run_with_either_file_already_dirty(tmp_path, monkeypatch, capsys):
    bot, root, _sha = _build_bot_and_root(tmp_path, '{"contract_version": 1}')
    monkeypatch.setattr(
        update_bot_contract, "_run_parity_tests", lambda root, bot_path: (True, "")
    )
    (root / "contracts" / "provisioning.json").write_text("uncommitted edit\n", encoding="utf-8")

    exit_code = update_bot_contract.main(["--bot-path", str(bot), "--root", str(root)])

    assert exit_code != 0
    assert (root / "contracts" / "provisioning.json").read_text(
        encoding="utf-8"
    ) == "uncommitted edit\n"
    assert "dirty" in capsys.readouterr().out.lower()


def test_it_refuses_to_run_when_git_status_cannot_run(tmp_path, monkeypatch, capsys):
    """`git status` exits non-zero WITH EMPTY STDOUT whenever it can't
    operate at all -- not a git repo, git missing, or a "dubious ownership"
    refusal -- and empty stdout must never be read as "the tree is clean" in
    that case, or the dirty-check silently stops protecting anything."""
    bot, root, _sha = _build_bot_and_root(tmp_path, '{"contract_version": 1}')
    shutil.rmtree(root / ".git")
    monkeypatch.setattr(
        update_bot_contract, "_run_parity_tests", lambda root, bot_path: (True, "")
    )

    before_contract = (root / "contracts" / "provisioning.json").read_text(encoding="utf-8")
    before_ref = (root / ".ci" / "pr-review-bot-ref").read_text(encoding="utf-8")

    exit_code = update_bot_contract.main(["--bot-path", str(bot), "--root", str(root)])

    assert exit_code != 0
    assert (root / "contracts" / "provisioning.json").read_text(encoding="utf-8") == before_contract
    assert (root / ".ci" / "pr-review-bot-ref").read_text(encoding="utf-8") == before_ref


def test_run_parity_tests_forces_pr_review_bot_path_to_the_extracted_checkout(monkeypatch):
    """Without this, the parity file's OWN bot-checkout resolution
    (PR_REVIEW_BOT_PATH, else a sibling directory) runs independently of
    whatever --bot-path this script was given -- so a non-default
    --bot-path could gate against a different checkout, or, if no sibling
    directory happens to exist either, silently SKIP the one test that
    verifies the extraction, which main() would then misreport as a real
    pass. Checked at the subprocess-argument level rather than by faking a
    whole pytest run."""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr(update_bot_contract.subprocess, "run", fake_run)
    bot_path = Path("/some/pr-review-bot/checkout")
    update_bot_contract._run_parity_tests(Path("/some/root"), bot_path)

    assert captured["env"]["PR_REVIEW_BOT_PATH"] == str(bot_path)
    assert update_bot_contract.PARITY_TESTS in captured["cmd"]


def test_every_subprocess_run_in_text_mode_declares_encoding():
    """subprocess.run(text=True) with no `encoding=` decodes with the
    LOCALE encoding, not necessarily utf-8 -- the one gap the encoding/
    newline discipline below doesn't cover, since it only inspects
    open/read_text/write_text. Git's output here is committed repo content
    (.gitattributes pins `text=auto eol=lf`), so an unset encoding is a
    latent divergence waiting for a non-ASCII contract or a non-UTF-8
    locale, not a live bug today."""
    tree = ast.parse(inspect.getsource(update_bot_contract))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "run"):
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        text_mode = (
            "text" in kwargs
            and isinstance(kwargs["text"], ast.Constant)
            and kwargs["text"].value is True
        )
        if text_mode:
            assert "encoding" in kwargs, (
                f"subprocess.run(text=True) at update_bot_contract.py:{node.lineno} "
                "has no encoding="
            )


def test_it_never_invokes_git_add_or_git_commit():
    tree = ast.parse(inspect.getsource(update_bot_contract))
    for node in ast.walk(tree):
        if isinstance(node, ast.List) or isinstance(node, ast.Tuple):
            values = [elt.value for elt in node.elts if isinstance(elt, ast.Constant)]
            assert "add" not in values, "must never invoke `git add`"
            assert "commit" not in values, "must never invoke `git commit`"


def test_every_file_call_declares_encoding_and_newline():
    """.gitattributes pins this working tree to eol=lf; a locale-default
    write would produce a CRLF contract that fails the byte-compare on a
    Windows operator's machine and nowhere else."""
    tree = ast.parse(inspect.getsource(update_bot_contract))
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name in {"open", "read_text", "write_text"}:
            calls.append((name, node))
    assert calls, "expected at least one open/read_text/write_text call to check"
    for name, node in calls:
        kwargs = {kw.arg for kw in node.keywords if kw.arg}
        assert "encoding" in kwargs, (
            f"{name}() at update_bot_contract.py:{node.lineno} has no encoding="
        )
        if name == "write_text":
            assert "newline" in kwargs, (
                f"{name}() at update_bot_contract.py:{node.lineno} has no newline="
            )
