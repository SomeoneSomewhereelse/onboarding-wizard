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


def _build_bot_and_root(tmp_path: Path, contract_body: str) -> tuple[Path, Path]:
    """A bare 'origin' plus a clone (so origin/main resolves to a real ref),
    and a wizard root pointing at the clone via --bot-path, pre-seeded with
    a pin and a stale contract."""
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
    return bot, root, sha


def test_a_green_run_writes_both_files_and_prints_old_to_new(tmp_path, monkeypatch, capsys):
    bot, root, sha = _build_bot_and_root(tmp_path, '{"contract_version": 1}')
    monkeypatch.setattr(update_bot_contract, "_run_parity_tests", lambda root: (True, ""))

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
        update_bot_contract, "_run_parity_tests", lambda root: (False, "1 failed, 0 passed")
    )

    before_contract = (root / "contracts" / "provisioning.json").read_text(encoding="utf-8")
    before_ref = (root / ".ci" / "pr-review-bot-ref").read_text(encoding="utf-8")

    exit_code = update_bot_contract.main(["--bot-path", str(bot), "--root", str(root)])

    assert exit_code != 0
    assert (root / "contracts" / "provisioning.json").read_text(encoding="utf-8") == before_contract
    assert (root / ".ci" / "pr-review-bot-ref").read_text(encoding="utf-8") == before_ref
    assert "1 failed" in capsys.readouterr().out


def test_it_refuses_to_run_with_either_file_already_dirty(tmp_path, monkeypatch, capsys):
    bot, root, _sha = _build_bot_and_root(tmp_path, '{"contract_version": 1}')
    monkeypatch.setattr(update_bot_contract, "_run_parity_tests", lambda root: (True, ""))
    _init_git_repo(root)
    _commit_all(root, "initial wizard state")
    (root / "contracts" / "provisioning.json").write_text("uncommitted edit\n", encoding="utf-8")

    exit_code = update_bot_contract.main(["--bot-path", str(bot), "--root", str(root)])

    assert exit_code != 0
    assert (root / "contracts" / "provisioning.json").read_text(
        encoding="utf-8"
    ) == "uncommitted edit\n"
    assert "dirty" in capsys.readouterr().out.lower()


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
