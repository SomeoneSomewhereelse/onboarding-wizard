# Onboarding-Wizard Repo Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn this repo from a `bot`+`dashboard`+`onboarding` monorepo checkout into a standalone, flat, single-package `onboarding-wizard` repo — no behavior change to the wizard itself, purely structural.

**Architecture:** `onboarding/`'s package contents flatten to repo root (no more sibling packages to disambiguate against). `bot/`, `dashboard/`, `guide/`, and the mkdocs site are deleted outright (they live at `~/pr-review-bot` now). `pyproject.toml`, `tests/`, `CLAUDE.md`, `ISSUES.md`, `docs/superpowers/{specs,plans}/`, `render.yaml`, and `.github/workflows/ci.yml` all collapse from "one of several packages/services" shape to "the whole repo" shape.

**Tech Stack:** Python 3.12, FastAPI, `uv` workspaces (collapsing to a single non-workspace project), pytest/ruff, Docker, Render.

**Spec:** `docs/superpowers/specs/2026-09-05-onboarding-wizard-restructure-design.md`

## Global Constraints

- Full test suite (`uv run pytest -v`) and `uv run ruff check .` must stay green after every task.
- No behavior change to the wizard's own logic (frames, validation, session-store schema) anywhere in this plan — every task is structural/packaging/documentation only.
- Never run a broad, unscoped `grep -rn`/`grep -rl` across the whole repo tree while doing this work — always exclude `.env` and `.env.config` (e.g. `grep -rn --exclude='.env' --exclude='.env.config' ...`), or scope to explicit file lists/extensions instead of a bare directory. Never open `.env` with any tool for any reason.
- After the final task, a Docker build (`docker build -f Dockerfile .`) must build and boot (`docker run --rm <image> uv run --no-sync --no-dev python -c "import main"`).
- Every commit in this plan is a normal commit on `main` (no branch/worktree gymnastics required — the repo has no history to protect yet beyond the design-doc commits already made).

---

### Task 1: Flatten `onboarding/` to repo root — package, tests, conftest, pyproject

This is the foundational move: after this task, the repo has exactly one Python package (rooted at `.`), one `tests/` directory, and one `pyproject.toml`. `bot/` and `dashboard/` still exist on disk after this task (deleted in Task 2) — that's fine, because `pyproject.toml`'s `testpaths` will only point at `tests/`, so pytest never collects `bot/tests`/`dashboard/tests` regardless of whether those directories are still present.

**Files:**
- Move: `onboarding/__init__.py` → `__init__.py`
- Move: `onboarding/config.py` → `config.py`
- Move: `onboarding/github_client.py` → `github_client.py`
- Move: `onboarding/llm_client.py` → `llm_client.py`
- Move: `onboarding/main.py` → `main.py`
- Move: `onboarding/render_client.py` → `render_client.py`
- Move: `onboarding/router.py` → `router.py`
- Move: `onboarding/session_store.py` → `session_store.py`
- Move: `onboarding/supabase_client.py` → `supabase_client.py`
- Move: `onboarding/uptimerobot_client.py` → `uptimerobot_client.py`
- Move: `onboarding/Dockerfile` → `Dockerfile`
- Move: `onboarding/.env` → `.env`
- Move: `onboarding/.env.example` → `.env.example`
- Move: `onboarding/static/` → `static/`
- Move: `onboarding/tests/*.py` → `tests/*.py`
- Move: `conftest.py` (repo root) → `tests/conftest.py`, trimmed
- Modify: `pyproject.toml` (replace wholesale with `onboarding/pyproject.toml`'s content, adjusted)
- Delete: `onboarding/pyproject.toml` (superseded by the moved-and-adjusted root one)
- Delete: the empty `onboarding/` directory once everything above has moved out of it

**Interfaces:**
- Consumes: nothing from other tasks (this is Task 1).
- Produces: a flat, single-package repo layout that every later task builds on. `main:app` (was `onboarding.main:app`) is the ASGI app entrypoint later tasks' Dockerfile/render.yaml edits (Task 2) point at.

- [ ] **Step 1: Move the package files and static assets**

```bash
git mv onboarding/__init__.py __init__.py
git mv onboarding/config.py config.py
git mv onboarding/github_client.py github_client.py
git mv onboarding/llm_client.py llm_client.py
git mv onboarding/main.py main.py
git mv onboarding/render_client.py render_client.py
git mv onboarding/router.py router.py
git mv onboarding/session_store.py session_store.py
git mv onboarding/supabase_client.py supabase_client.py
git mv onboarding/uptimerobot_client.py uptimerobot_client.py
git mv onboarding/Dockerfile Dockerfile
git mv onboarding/.env .env
git mv onboarding/.env.example .env.example
git mv onboarding/static static
```

(`onboarding/.env` is gitignored and untracked — `git mv` will fail on it specifically; use plain `mv onboarding/.env .env` for that one file only. Do not open, read, or print `.env`'s contents at any point in this step — a plain `mv` never needs to.)

- [ ] **Step 2: Move the tests and conftest.py**

```bash
git mv onboarding/tests/test_onboarding_config.py tests/test_onboarding_config.py
git mv onboarding/tests/test_onboarding_github_client.py tests/test_onboarding_github_client.py
git mv onboarding/tests/test_onboarding_i18n.py tests/test_onboarding_i18n.py
git mv onboarding/tests/test_onboarding_llm_client.py tests/test_onboarding_llm_client.py
git mv onboarding/tests/test_onboarding_main.py tests/test_onboarding_main.py
git mv onboarding/tests/test_onboarding_page.py tests/test_onboarding_page.py
git mv onboarding/tests/test_onboarding_render_client.py tests/test_onboarding_render_client.py
git mv onboarding/tests/test_onboarding_router.py tests/test_onboarding_router.py
git mv onboarding/tests/test_onboarding_session_store.py tests/test_onboarding_session_store.py
git mv onboarding/tests/test_onboarding_supabase_client.py tests/test_onboarding_supabase_client.py
git mv onboarding/tests/test_onboarding_uptimerobot_client.py tests/test_onboarding_uptimerobot_client.py
git mv conftest.py tests/conftest.py
```

- [ ] **Step 3: Update import paths in every moved source file**

In `main.py`, replace:
```python
from onboarding import session_store
from onboarding.config import settings
from onboarding.router import router
```
with:
```python
import session_store
from config import settings
from router import router
```

In `session_store.py`, replace `from onboarding.config import settings` with `from config import settings`.

In `router.py`, replace:
```python
from onboarding import (
    github_client,
    llm_client,
    render_client,
    session_store,
    supabase_client,
    uptimerobot_client,
)
```
with:
```python
import github_client
import llm_client
import render_client
import session_store
import supabase_client
import uptimerobot_client
```

In `main.py`'s module docstring and RuntimeError messages, replace `onboarding/.env.example` with `.env.example` (two occurrences).

In `config.py`'s module docstring, replace:
```python
"""onboarding/'s own Settings — a separate deployed service from bot/, so
this does NOT import bot/config.py's Settings (per onboarding/CLAUDE.md's
no-shared-credential-path rule)."""
```
with:
```python
"""This service's own Settings."""
```
(The no-shared-credential-path rule this used to reference was dropped in the restructure design — see the design doc's decision 2 — since there's no sibling package left in this repo to guard against.)

- [ ] **Step 4: Update import paths in every moved test file**

For each of these files, replace `from onboarding import X` with `import X`, and `from onboarding.X import Y` with `from X import Y`:
- `tests/test_onboarding_github_client.py`: `from onboarding import github_client` → `import github_client`
- `tests/test_onboarding_config.py`: `from onboarding.config import Settings` → `from config import Settings`
- `tests/test_onboarding_main.py`: `from onboarding import session_store` → `import session_store`; `from onboarding.config import settings` → `from config import settings`; `from onboarding.main import app, lifespan` → `from main import app, lifespan`
- `tests/test_onboarding_render_client.py`: `from onboarding import render_client` → `import render_client`
- `tests/test_onboarding_llm_client.py`: `from onboarding import llm_client` → `import llm_client`
- `tests/test_onboarding_uptimerobot_client.py`: `from onboarding import uptimerobot_client` → `import uptimerobot_client`
- `tests/test_onboarding_page.py`: `from onboarding.main import app` → `from main import app`
- `tests/test_onboarding_supabase_client.py`: `from onboarding import supabase_client` → `import supabase_client`
- `tests/test_onboarding_i18n.py`: `from onboarding.main import app` → `from main import app`
- `tests/test_onboarding_router.py`: the same multi-import block as `router.py` above (`from onboarding import (...)` → six separate `import X` lines), plus `from onboarding.main import app` → `from main import app`
- `tests/test_onboarding_session_store.py`: `from onboarding import session_store` → `import session_store`; `from onboarding.config import settings` → `from config import settings`

Run, scoped to the files just edited (never a bare directory-wide search — see Global Constraints):
```bash
grep -n "onboarding\." main.py config.py github_client.py llm_client.py render_client.py router.py session_store.py supabase_client.py uptimerobot_client.py tests/*.py
```
Expected: no matches (confirms every `onboarding.`-prefixed import was caught). If anything remains, fix it before moving on.

- [ ] **Step 5: Rewrite `tests/conftest.py` to be onboarding-only**

Read the file's current content first (it moved in Step 2, so it's now at `tests/conftest.py`). Make these changes:

1. Delete the `db` fixture entirely (the one that truncates `tickets, runtime_config, reviews` and imports `bot.config`/`bot.queue.store`).
2. Delete `_close_onboarding_pool`'s bot-specific docstring framing if any, but keep the function itself (it's still needed — it closes `session_store`'s pool). Update its `import onboarding.session_store as onboarding_store` to `import session_store as onboarding_store`.
3. Rename the `onboarding_db` fixture to `db` (it's the only DB fixture left in the file). Update its body:
   ```python
   import session_store as onboarding_store
   from config import settings as onboarding_settings
   ```
   (dropping the `onboarding.` prefix from both). Update its docstring: remove the "Lives here, not in a separate `onboarding/tests/conftest.py`, because..." paragraph entirely (that collision reasoning no longer applies — there's only one `tests/` directory now, and this file already lives at `tests/conftest.py`). Replace it with a one-line docstring: `"""Points session_store at the test Postgres and truncates its one table (wizard_sessions) before each test that requests this fixture."""`
4. Delete `_quarantine_local_slot_discovery` and `local_slot_discovery_allowed` entirely (both wrap `bot.scripts._override`, which no longer exists in this repo).
5. Search (scoped to this one file only) for any other `bot`/`onboarding.` reference:
   ```bash
   grep -n "\bbot\.\|onboarding\." tests/conftest.py
   ```
   Fix anything else found the same way (drop the `onboarding.` prefix; delete anything that's bot-only).
6. Every fixture/hook that referenced the now-deleted `db` fixture by name (e.g. any `db_exec`/`db_query`/`_touches_shared_postgres` logic that lists `db` as a root dependency) needs checking: since the trimmed file's only remaining DB fixture is now itself named `db` (per point 3), these should still work unchanged — but read them after the edits above to confirm no leftover reference to the old `onboarding_db` name survives.

- [ ] **Step 6: Replace `pyproject.toml` wholesale**

Read `onboarding/pyproject.toml` (not yet deleted) for its exact current dependency list, then write the new root `pyproject.toml`:

```toml
[project]
name = "onboarding-wizard"
version = "0.1.0"
description = "Self-service setup wizard: provisions a visitor's own bot+dashboard deployment"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "pygithub>=2.4",
    "google-genai>=0.3",
    "httpx>=0.27",
    "groq>=1.5.0",
    "google-auth>=2.35",
    # Imported directly by github_client.py (JWT-signing) and requests-based
    # transport for the sync google-auth credential refresh path.
    "pyjwt>=2.13",
    "requests>=2.32",
    "psycopg[binary]>=3.2",
    "psycopg-pool>=3.2",
    "cryptography>=43",
]

[tool.uv]
package = false

[dependency-groups]
dev = [
    "cryptography>=44.0",
    "playwright>=1.62.0",
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-xdist>=3.6",
    "respx>=0.21",
    "ruff>=0.7",
    "testcontainers[postgres]>=4.0",
]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "E501"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
# -n is a PINNED 4, deliberately not `auto` -- see the 2026-08-19
# test-suite-performance design doc (carried over from the monorepo) for the
# measured reasoning: a fixed worker-startup cost per xdist worker dominates
# this suite's runtime, and `auto` (spinning one worker per core) was
# measured slower than a small fixed count on a many-core machine.
addopts = "-n 4 --dist=loadgroup --import-mode=importlib"
markers = [
    "db: transitively touches the shared Postgres via the db fixture (auto-applied by tests/conftest.py's pytest_collection_modifyitems hook, not meant to be added by hand)",
]
```

(The `xdist_meta` marker from the old root `pyproject.toml` documents a test that exercises real xdist worker subprocess scheduling — check whether any moved test file actually uses it: `grep -n "xdist_meta" tests/*.py`. If nothing matches, leave it out as done above. If something matches, add the marker back with its original description.)

Delete `onboarding/pyproject.toml` and the now-empty `onboarding/` directory:
```bash
rm onboarding/pyproject.toml
rmdir onboarding
```

- [ ] **Step 7: Regenerate the lockfile and run the full suite**

```bash
uv lock
uv run pytest -v
```

Expected: full suite passes (same test count as before this task, since no tests were added/removed — only moved and import-fixed). If the first run in this environment takes several minutes with no output, that's `uv` building `.venv` from scratch (see the "test suite looks hung" note in `onboarding/CLAUDE.md` at the time this plan was written) — not a real hang.

- [ ] **Step 8: Run ruff**

```bash
uv run ruff check .
```

Expected: clean. Fix anything it flags (most likely: unused `onboarding` import remnants, or line-length issues from the import rewrites).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
Flatten onboarding/ package to repo root

No sibling package remains in this repo to disambiguate against, so
the onboarding/ prefix is dropped throughout: package modules, static
assets, tests, conftest.py, and pyproject.toml all move to repo root
and collapse to a single package/single test dir/single manifest.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Utcu7cT1qPXUY1CHifBDSA
EOF
)"
```

---

### Task 2: Remove `bot/`/`dashboard/`/`guide/`, simplify CI, fix `render.yaml`

**Files:**
- Delete: `bot/` (entire directory)
- Delete: `dashboard/` (entire directory)
- Delete: `guide/` (entire directory)
- Delete: `mkdocs.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `render.yaml`
- Modify: `Dockerfile` (path references, from Task 1's move)
- Modify: `.dockerignore`

**Interfaces:**
- Consumes: the flattened layout from Task 1 (root `main.py`/`Dockerfile`/`pyproject.toml`).
- Produces: a repo with no `bot`/`dashboard`/`guide` content left anywhere, a single-job CI workflow, and a `render.yaml` that matches this service's actual `Settings` fields (`database_url`, `onboarding_session_encryption_key`).

- [ ] **Step 1: Delete the removed directories and docs-site config**

```bash
git rm -r bot dashboard guide
git rm mkdocs.yml
```

- [ ] **Step 2: Fix `Dockerfile`'s now-stale paths**

`Dockerfile` (moved to root in Task 1) still says:
```dockerfile
COPY pyproject.toml uv.lock ./
COPY onboarding/pyproject.toml ./onboarding/pyproject.toml
RUN uv sync --frozen --no-dev --package onboarding

COPY onboarding ./onboarding
...
CMD ["uv", "run", "--no-sync", "--no-dev", "uvicorn", "onboarding.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Replace with:
```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .
...
CMD ["uv", "run", "--no-sync", "--no-dev", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

(`--package onboarding` is dropped along with it — there's no workspace/package name to select anymore, just the one project. `COPY . .` replaces `COPY onboarding ./onboarding` since the whole repo *is* the service now — `.dockerignore`, fixed in Step 5 below, keeps `tests/`/`.git/`/docs out of the build context.)

- [ ] **Step 3: Rewrite `.github/workflows/ci.yml`**

Replace the whole file with just the `lint-and-test` job (drop `docs` and `pages` entirely):

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres" --health-interval 5s
          --health-timeout 5s --health-retries 10
    env:
      DATABASE_URL: "postgresql://postgres:postgres@localhost:5432/test"
    steps:
      - uses: actions/checkout@v7

      - name: Install uv
        uses: astral-sh/setup-uv@v10.0.1

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --all-extras --dev

      - name: Lint (ruff)
        run: uv run ruff check .

      - name: Test (pytest)
        run: uv run pytest -v
```

- [ ] **Step 4: Fix `render.yaml`**

Replace the whole file:

```yaml
services:
  - type: web
    name: onboarding-wizard
    runtime: docker
    dockerfilePath: ./Dockerfile
    plan: free
    healthCheckPath: /healthz
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: ONBOARDING_SESSION_ENCRYPTION_KEY
        sync: false
```

(`buildFilter` is dropped entirely — it existed only to stop a `bot`-only push, inside the old shared monorepo, from triggering this service's redeploy; moot now that this is a real separate repo where every push is relevant to this one service. The service `name` changes from `pr-review-engine`, which described the bot, to `onboarding-wizard`.)

- [ ] **Step 5: Fix `.dockerignore`**

Remove the now-dead `bot/`-specific block and the stale comment mentioning both Dockerfiles:

```
# Test suite and fixtures aren't needed by the running service -- the
# Dockerfile only ever `uv sync`/runs the package itself.
**/tests/
**/__pycache__/
*.pyc

# Never let a build context pick up local secrets or machine-specific config
# even though .dockerignore is a second, redundant safety net alongside
# .gitignore and the git-tracked-files-only build context most CI setups use.
.env
**/.env
.env.config
**/.env.config
*.pem
gcp-service-account-key*.json

.git/
.venv/
docs/superpowers/
```

(Drop the `bot/scripts/`, `bot/fixtures/`, `bot/SPEC.md`, `bot/cost.md` lines — none of those paths exist anymore.)

- [ ] **Step 6: Run the full verification bar**

```bash
uv run pytest -v
uv run ruff check .
docker build -f Dockerfile -t onboarding-wizard-test .
docker run --rm onboarding-wizard-test uv run --no-sync --no-dev python -c "import main"
```

Expected: all four succeed. The last line should print nothing and exit 0 (a clean import, matching the pattern `bot/CLAUDE.md`'s own smoke-test convention used: `python -c "import bot.main"` — here it's just `import main`).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
Remove bot/, dashboard/, guide/; single-job CI; fix render.yaml

bot/ and dashboard/ now live at ~/pr-review-bot as a fully separate
project; this repo never imported from them. Drops the docs-site CI
jobs (no guide/ here) and trims render.yaml's envVars/buildFilter to
match this service's actual Settings (DATABASE_URL,
ONBOARDING_SESSION_ENCRYPTION_KEY only).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Utcu7cT1qPXUY1CHifBDSA
EOF
)"
```

---

### Task 3: Merge and rewrite root `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md` (currently the monorepo-root version; rewrite wholesale using its own secret-handling/process-hygiene sections plus `onboarding/CLAUDE.md`'s content — `onboarding/CLAUDE.md` no longer exists as a separate file after Task 1's directory removal, so read its content from git history if needed: `git show HEAD~2:onboarding/CLAUDE.md` after Tasks 1-2 are committed, or simply keep a local copy of its text on hand before this task starts.)

**Interfaces:**
- Consumes: nothing structural from Tasks 1-2 beyond "the repo is now flat" (this task only touches one markdown file).
- Produces: the final root `CLAUDE.md` every later task's own doc edits (README, ISSUES.md) are consistent with.

- [ ] **Step 1: Recover `onboarding/CLAUDE.md`'s content**

Since Task 1 moved `onboarding/` contents to root but never moved `onboarding/CLAUDE.md` itself (it wasn't in Task 1's file list — it gets absorbed into root `CLAUDE.md` here, not moved as its own file), it should still exist on disk at `onboarding/CLAUDE.md`... but Task 2 deleted the `onboarding/` directory's remaining contents via `rmdir` only after it was empty, so it must still be present unless something else removed it. Check first:

```bash
ls onboarding/CLAUDE.md 2>&1 || git log --all --oneline -- onboarding/CLAUDE.md
```

If the file is gone, retrieve its last committed content: `git show <commit-before-task-2>:onboarding/CLAUDE.md > /tmp/onboarding-claude-md-content.md` and read that.

- [ ] **Step 2: Write the new root `CLAUDE.md`**

Structure, in this order (see the design doc's decision 2 for the full reasoning behind each section):

1. **Secret-handling section** — start from the current root `CLAUDE.md`'s "Secret handling — HIGHEST PRIORITY" section (everything from that heading down through the "Scoped exception: the dashboard Environment tab" subsection). Keep the section's opening framing and every generic bullet (never display a secret, never run a broad/unbounded command against a file known to hold secrets, never dump broad environment/config state, never pass a secret as a CLI arg, never let a validation error leak one, never write one somewhere shared, the `.env`-absolute-rule, the harness-diff exposure vector, "ask the user to check," the incident-disclosure rule, the `.claude/hooks/check_env_access.py` never-modify-without-being-asked rule). Make these changes while copying it over:
   - Update the opening paragraph's secret list to this service's actual scope: `DATABASE_URL`, `ONBOARDING_SESSION_ENCRYPTION_KEY`, plus (new sentence) "and any visitor-supplied credential value in transit through a relay endpoint (a GitHub App private key, a Render/Supabase/UptimeRobot/LLM-provider API key or service-account JSON) — see the Rules section below for the visitor-credential-specific rules layered on top of this section."
   - The opening paragraph's "Three separate real incidents during this project's life produced actual secret exposure into a conversation transcript this way — see `ISSUES.md`" sentence: reword to drop the specific incident count and the implicit promise that those exact incidents are findable in *this* repo's `ISSUES.md` (they're bot/dashboard-specific and were left out of this repo's pruned history — see Task 4). Replace with: "This kind of exposure has happened multiple times across this project's history (including before this repo split off from its sibling review-engine project) — which is why this section exists and is kept first in the file."
   - The "never run a broad or unbounded command" bullet's parenthetical examples (`tail -c 20` on a `.env` line, a `grep` sharing a line with `GCP_SERVICE_ACCOUNT_KEY`): these are bot-specific incidents (that env var belongs to the bot's Vertex provider, not this service). Reword to a generic statement of the same risk without naming those specific past incidents: "even a pattern aimed at confirming a variable's name or searching for an unrelated keyword can print a full secret value if it happens to occur on the same line — this is a real, demonstrated failure mode, not a hypothetical one."
   - The "`.env`-is-absolutely-off-limits" bullet's "This bullet has already been misread twice as licensing exactly that — see `ISSUES.md`" sentence: reword to "This has been misread before as licensing exactly that, so if a command's target is `.env`, the answer is always 'ask the user,' full stop, regardless of how safe the pattern looks" — dropping the specific `ISSUES.md` pointer since those two incidents aren't in this repo's own file.
   - Drop the "Scoped exception: the dashboard Environment tab" subsection entirely — that endpoint lived in `dashboard/`, which this repo no longer has.
   - Keep the `.claude/hooks/check_env_access.py` paragraph as-is (that hook file itself is presumably still present under `.claude/` in this repo — verify with `ls .claude/hooks/check_env_access.py`; if present, keep the rule verbatim; if the hook isn't actually in this repo, drop the paragraph and note it in your task report instead of guessing).

2. **Project overview** — replace the monorepo root's "## Project" section (which describes the whole three-package system) with a short paragraph describing this service alone: a self-service setup wizard that provisions a visitor's own bot+dashboard deployment (on Render, backed by Supabase), holding its own server-side session in a dedicated Postgres. Point at `docs/superpowers/specs/2026-09-01-onboarding-server-side-session-design.md` for the full design.

3. **The session-store architecture section** — copy `onboarding/CLAUDE.md`'s "## The invariant this service now protects" section verbatim (it's already generic to this service, no bot references to reword).

4. **Rules** — copy `onboarding/CLAUDE.md`'s "## Rules" section, dropping the third bullet ("This service and the review engine (`bot/`) do not import from each other's credential-handling code paths...") entirely per the design doc's decision to drop the no-shared-credential-path rule outright. Keep the other three bullets verbatim.

5. **Sub-project sections** — copy `onboarding/CLAUDE.md`'s six "## What sub-project N adds to these rules" sections (GitHub App, Supabase, LLM provider, UptimeRobot, Render/deploy, Dashboard login) verbatim, then apply these specific rewordings (search for each quoted phrase and replace it — do not reword anything else in these sections):
   - "hardcoded copies of `bot/config.py`'s own field defaults, not visitor-submitted data" → "hardcoded operational defaults, kept in sync by hand with the sibling review-engine project's own config (`~/pr-review-bot`) — nothing automated ties the two together"
   - "reuses `bot/scripts/deploy.py`'s own `_DEPLOY_IN_FLIGHT_STATUSES`/`_DEPLOY_FAILED_STATUSES` status-bucket sets as a verbatim, paired-comment copy in `render_client.py`" → "keeps its own copy of Render's deploy-status buckets in `render_client.py`, matching the sibling review-engine project's equivalent sets by hand — no import between the two repos"
   - "`bot/queue/store.py::init_pool()` now seeds the `runtime_config` singleton row with `bot/config.py`'s own defaults itself, the first time it runs against a table with no row yet" → "the review engine's own first-boot seeding handles this on its side — no second service needs to open a connection to write into that database's schema from the outside"
   - "onboarding/ never imports bot/" (wherever this exact clause appears standalone as a parenthetical justification) → delete the parenthetical entirely (the rule it was justifying — never sharing credential code — is already dropped; a bare "there's no bot/ to import from" is now simply true by construction, not a rule to state).
   - Any remaining bare `bot/`-prefixed file path found while copying (e.g. `bot/github_app.py`'s doctor-check pattern, `bot/scripts/_render.py`, `bot/scripts/deploy.py`'s `_wanted_env`) — reword the same way: name what the sibling project does in prose, drop the exact path. Use this search after pasting the sections in, scoped to just this one file:
     ```bash
     grep -n "bot/" CLAUDE.md
     ```
     Fix every match the same way (reword to drop the dead path, keep the constraint), except references inside a sentence like "~/pr-review-bot" (the sibling repo's own location, which is fine to keep) — only bare `bot/<file>` in-repo path references need rewording.

6. **Plan-execution/process-hygiene section** — copy the monorepo root's "## Plan-execution / multi-agent process hygiene" section verbatim (fully generic, no bot-specific content).

7. **The "test suite looks hung on a fresh worktree" note** — copy `onboarding/CLAUDE.md`'s final section verbatim.

Drop from the monorepo root `CLAUDE.md` entirely (do not carry over): the "## Project" section's bot-specific framing (replaced in point 2), "## Conventions" (all bot-specific: module boundaries, async/one-purpose-modules convention that doesn't describe this service, the partial-failure-visible-in-PR-comment rule, the pre-push test/ruff/Docker rule — actually **keep** the pre-push test/ruff/Docker-build rule and the never-commit-on-someone-else's-behalf rule, both are fully generic; drop only the module-boundaries/async/PR-comment bullets which are bot-specific), "## Substitutions from the brief" (bot's LLM-provider swap reasoning), "## Cost" (bot's cost model), and the "## LLM API testing hygiene" section **unless** a check shows it's still load-bearing for this service's own `llm_client.py` — check:
```bash
grep -n "one deliberate live call\|testing hygiene\|Trust.*Safety" onboarding/CLAUDE.md
```
`onboarding/CLAUDE.md`'s own sub-project 4 section already says its LLM-provider tests use SDK-boundary/`respx` mocking, i.e. no live calls in the test suite — but the *discipline* (don't loop live model-shopping calls when manually verifying a credential) is still a real risk for this service's own `llm_client.py` during manual work. Carry over a trimmed version of the "LLM API testing hygiene" section: keep the "Rules to avoid repeating this" bullet list (one deliberate live call, prefer mocked tests, stop on 403/429, metadata/listing calls are fine, applies to any provider), drop the Gemini-account-block narrative paragraph above it (that's a bot-project incident narrative, not a generic rule) and replace it with one sentence: "This project's `llm_client.py` makes real live calls to Gemini/Groq/Vertex during credential validation — the same abuse-flag risk applies here as anywhere else this discipline is documented."

- [ ] **Step 3: Verify no remaining dead references**

```bash
grep -n "\bbot/\|\bdashboard/\|\bguide/" CLAUDE.md
```

Expected: no matches (every reference to those removed paths was either dropped or reworded in Step 2). Fix any stragglers.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git rm --cached onboarding/CLAUDE.md 2>/dev/null || true
git commit -m "$(cat <<'EOF'
Merge root and onboarding/ CLAUDE.md into one onboarding-scoped file

Folds the generic secret-handling and plan-execution sections (kept
from the monorepo root) together with onboarding/CLAUDE.md's own
session-store architecture, rules, and sub-project sections. Drops
bot-/dashboard-specific content and the now-moot no-shared-
credential-path rule; rewords dead bot/-file-path references to
describe the sibling review-engine project generically instead.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Utcu7cT1qPXUY1CHifBDSA
EOF
)"
```

---

### Task 4: Prune `ISSUES.md` to onboarding-only scope

**Files:**
- Modify: `ISSUES.md`

**Interfaces:**
- Consumes: nothing structural (a standalone doc-pruning task).
- Produces: this repo's starting `ISSUES.md` history.

- [ ] **Step 1: Rewrite the file's intro (lines 1-31 of the current file)**

Replace the current intro paragraph (which explains a 2026-09-05 pruning pass removing resolved narrative entries) with one that also explains *this* repo-split pruning. Keep the format block (`## <short title>` / `- **When:**` / etc.) unchanged. New paragraph, appended after the existing pruning-note paragraph:

> **This file's own history starts here.** This repo was split off from a monorepo shared with a sibling review-engine project (now at `~/pr-review-bot`, which kept the combined project's full `ISSUES.md` and git history). Every entry below was carried over because it's specific to this service (the onboarding wizard) — entries about the sibling project's own incidents, parked issues, or design gaps were left in that project's own file instead. `~/pr-review-bot/ISSUES.md` has the full combined history if older context is ever needed again.

- [ ] **Step 2: Keep exactly one entry from the top-level incident log**

The current file (before this task) has nine top-level incident entries between the intro and "## Parked Issues". Keep only "A requested security + code review of the whole onboarding wizard found a real SSRF vulnerability in the Vertex credential frame, plus 9 correctness bugs — all fixed in one pass" verbatim. Delete these eight entirely (all are about the sibling project's own `.env`/secrets, bot's webhook/dispatcher, or the dashboard's Environment tab — none mention onboarding):
- "Controller mistake: a broad grep for an unrelated keyword printed a full secret value"
- "Harness surfaced a full `.env` diff (every secret in the file) into the conversation with no command run"
- "The final whole-branch review caught a real bug that all six task-scoped reviews missed"
- "Controller mistake: printed a fragment of the base64-encoded credential to the transcript"
- "Controller ran the 'safe' `.env` presence-check pattern against `.env` itself — twice, in two different sessions"
- "Bot silently enqueued nothing after a real PR open, cause still unconfirmed; added logging along the whole webhook->dispatch chain to diagnose it live"
- "Live deployment's Environment tab listed zero Render vars: `RENDER_SERVICE_NAME` is a Render-reserved env var, not a settable one"
- "Real, unrotated `RENDER_API_KEY` exposed by the user directly into the conversation"
- "Controller ran a directory-recursive `grep` that swept in `bot/.env` without naming it"

- [ ] **Step 3: Keep every `onboarding/`-prefixed Parked Issue, with paths flattened**

Under "## Parked Issues", keep these ten entries verbatim (including their "Update"/"Note" follow-ups), except: everywhere one of these entries' body text says `onboarding/<path>` (e.g. `onboarding/render_client.py`, `onboarding/static/index.html`, `onboarding/tests/test_onboarding_page.py`), drop the `onboarding/` prefix to match this repo's now-flat layout (e.g. `render_client.py`, `static/index.html`, `tests/test_onboarding_page.py`). Do not reword anything else in these entries — they're a historical record, and their prose (e.g. "the design spec (section 5)") stays as originally written.

1. "onboarding/render_client.py constructs a fresh httpx.AsyncClient per validate_key() call"
2. "onboarding/static/index.html: minor Render-key-frame UX gaps"
3. "onboarding/tests/test_onboarding_i18n.py: one RTL test asserts an exact whole-line literal string"
4. "onboarding/static/index.html: `code`, base-URL, and error-message minor gaps from sub-project 2 (GitHub App automation)"
5. "onboarding/render_client.py and router.py: no server-side structural logging"
6. "onboarding/static/index.html: minor UX/robustness gaps from sub-project 3 (Supabase provisioning)"
7. "onboarding/router.py: four Supabase request models repeat access_token's Field constraint verbatim"
8. "onboarding/tests/test_onboarding_page.py: one Supabase restore-from-session test only checks substrings, not structural nesting"
9. "Spec section 6 (onboarding-uptimerobot-frame-design.md) described a browser-behavior test this project's suite cannot execute" (no path prefix to flatten in the title itself, but check its body text too)
10. "onboarding/static/index.html: minor UX/robustness gaps from sub-project 4 (LLM provider credential UI)"

Delete the four entries between/after these that are dashboard/bot-specific or now-moot:
- "dashboard/tests/test_auth.py's `_no_login_delay` autouse fixture applies file-wide, not just to the route tests"
- "dashboard/tests/test_login_page.py asserts on raw JS source text rather than behavior"
- "Unused `openai` dependency bumped to a major version by the workspace re-lock"
- "`bot/pyproject.toml`/`onboarding/pyproject.toml` lost the `pyjwt`/`requests` rationale comment"
- "Leftover `app/`-path prose scattered across `bot/*.py` and `tests/*.py`"
- "Leftover bare `scripts/`-path prose scattered across active non-doc files"
- "`bot/SPEC.md`'s Module-layout tree (§2) and Deploy+cost model (§9) describe the pre-restructure architecture"
- "`guide/setup/06-render.md` and `render.yaml`'s `envVars` list need full reconciliation with the onboarding-is-primary deploy model"
- "Docker images ship the test suite, scripts, and fixtures with no `.dockerignore`"
- "`dashboard/pyproject.toml` doesn't document that standalone `uv sync --package dashboard` is unsupported"
- "No `__init__.py` in the four test directories — latent duplicate-basename collision risk"

(All of these are either bot/dashboard-specific, already fully closed with no onboarding relevance, or made moot by this very restructure — e.g. the render.yaml/guide reconciliation issue and the four-test-directories issue are both resolved by this plan's own Tasks 1-2.)

- [ ] **Step 4: Keep the "## Design Gaps" section header, empty**

The only entry currently under "## Design Gaps" ("`bot/scripts/deploy.py --sync-env` and `bot/scripts/set_override.py` are now redundant with the dashboard Environment tab") is bot/dashboard-specific — delete it. Keep the "## Design Gaps" section header itself in the file, empty, ready for future onboarding-specific entries (matching this file's own existing convention of leaving a cleared section's header in place, as seen at the bottom of the file with the pre-flight-audit section).

- [ ] **Step 5: Keep the closing "pre-flight audit" note**

The file's final paragraph (about the 2026-08-21 pre-flight audit being cleared into `SPEC.md`) refers to `SPEC.md`, which is a `bot/`-only file that doesn't exist in this repo. Delete this closing note entirely — it describes bot's own history, not onboarding's.

- [ ] **Step 6: Review the result**

Read the whole rewritten file back and confirm: the format template block is intact, exactly one incident entry survives, exactly ten Parked Issues survive (all path-flattened), the Design Gaps section is present but empty, and no `bot/`, `dashboard/`, or `guide/` path reference remains anywhere.

```bash
grep -n "bot/\|dashboard/\|guide/" ISSUES.md
```

Expected: no matches.

- [ ] **Step 7: Commit**

```bash
git add ISSUES.md
git commit -m "$(cat <<'EOF'
Prune ISSUES.md to onboarding-only history

Keeps the SSRF-in-the-Vertex-frame incident and all ten
onboarding-tagged Parked Issues (paths flattened to match the
restructured repo layout); drops every bot-/dashboard-specific
incident and parked issue. ~/pr-review-bot/ISSUES.md keeps the full
combined history.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Utcu7cT1qPXUY1CHifBDSA
EOF
)"
```

---

### Task 5: Prune `docs/superpowers/{specs,plans}/` and delete loose `docs/*.md` notes

**Files:**
- Delete: every file in `docs/superpowers/specs/` except the ten named below
- Delete: every file in `docs/superpowers/plans/` except the matching plans named below
- Delete: every loose `docs/*.md` file (the handoff notes)

**Interfaces:**
- Consumes: nothing structural.
- Produces: a `docs/superpowers/` tree scoped to onboarding's own design history.

- [ ] **Step 1: Keep exactly these specs, delete every other file in `docs/superpowers/specs/`**

Keep:
- `2026-08-26-onboarding-github-app-frame-design.md`
- `2026-08-26-onboarding-supabase-provisioning-frame-design.md`
- `2026-08-26-onboarding-wizard-render-frame-design.md`
- `2026-08-27-onboarding-llm-provider-frame-design.md`
- `2026-08-27-onboarding-render-service-frame-design.md`
- `2026-08-27-onboarding-uptimerobot-frame-design.md`
- `2026-09-01-onboarding-github-app-manual-validation-design.md`
- `2026-09-01-onboarding-server-side-session-design.md`
- `2026-09-03-supabase-oauth-abuse-mitigation-design.md`
- `2026-09-04-supabase-pat-frame-design.md`

(Plus the restructure design doc itself, `2026-09-05-onboarding-wizard-restructure-design.md`, already committed — don't touch it.)

```bash
cd docs/superpowers/specs
git rm \
  2026-07-27-queue-features-design.md \
  2026-07-28-dispatcher-followups-design.md \
  2026-07-29-comment-visibility-followups-design.md \
  2026-07-31-comment-identity-design.md \
  2026-07-31-escalating-cooldown-design.md \
  2026-08-01-re-review-notice-design.md \
  2026-08-02-notice-cleanup-design.md \
  2026-08-03-demo-plan-design.md \
  2026-08-03-supabase-hosting-migration-design.md \
  2026-08-05-deploy-command-design.md \
  2026-08-05-supabase-first-deploy-hardening-and-first-hosted-run-design.md \
  2026-08-08-provider-agnostic-config-and-deploy-hardening-design.md \
  2026-08-10-provider-live-credential-verification-design.md \
  2026-08-10-render-access-consolidation-design.md \
  2026-08-11-audit-fix-round-design.md \
  2026-08-11-how-it-works-section-design.md \
  2026-08-11-ops-dashboard-design.md \
  2026-08-12-api-key-index-override-design.md \
  2026-08-12-override-cli-unification-design.md \
  2026-08-12-runtime-cooldown-tuning-design.md \
  2026-08-13-vertex-ai-provider-design.md \
  2026-08-15-key-usage-cap-design.md \
  2026-08-15-operational-config-split-design.md \
  2026-08-16-credential-convention-design.md \
  2026-08-16-model-pricing-validation-design.md \
  2026-08-17-multi-repo-support-design.md \
  2026-08-18-setup-experience-design.md \
  2026-08-19-test-suite-performance-design.md \
  2026-08-28-dashboard-authentication-design.md \
  2026-08-29-project-restructure-design.md \
  2026-09-02-dashboard-environment-tab-design.md \
  2026-09-03-dashboard-env-credential-guardrails-design.md \
  2026-09-05-hosted-only-guide-and-mandatory-keys-design.md
cd ../../..
```

- [ ] **Step 2: Keep exactly these plans, delete every other file in `docs/superpowers/plans/`**

Keep:
- `2026-08-26-onboarding-github-app-frame.md`
- `2026-08-26-onboarding-supabase-provisioning-frame.md`
- `2026-08-26-onboarding-wizard-render-frame.md`
- `2026-08-27-onboarding-llm-provider-frame.md`
- `2026-08-27-onboarding-render-service-frame.md`
- `2026-08-27-onboarding-uptimerobot-frame.md`
- `2026-09-01-onboarding-github-app-manual-validation.md`
- `2026-09-02-onboarding-server-side-session.md`
- `2026-09-04-supabase-pat-frame.md`

(Plus this very plan, `2026-09-05-onboarding-wizard-restructure.md` — don't touch it. Note there's no separate "supabase-oauth-abuse-mitigation" plan file to keep alongside its spec — check `ls docs/superpowers/plans/ | grep -i oauth-abuse` first; if none exists, that's expected, the spec-only predecessor never got its own plan file.)

```bash
cd docs/superpowers/plans
git rm \
  2026-07-27-review-queue.md \
  2026-07-28-dispatcher-followups.md \
  2026-07-29-comment-visibility-followups.md \
  2026-07-31-comment-identity.md \
  2026-07-31-escalating-cooldown.md \
  2026-08-01-re-review-notice.md \
  2026-08-02-notice-cleanup.md \
  2026-08-03-supabase-hosting-migration.md \
  2026-08-05-supabase-first-deploy-hardening-and-first-hosted-run.md \
  2026-08-07-deploy-verification-cli.md \
  2026-08-08-provider-agnostic-config-and-deploy-hardening.md \
  2026-08-10-provider-live-credential-verification.md \
  2026-08-11-audit-fix-round.md \
  2026-08-11-how-it-works-section.md \
  2026-08-11-ops-dashboard.md \
  2026-08-11-render-access-consolidation.md \
  2026-08-12-api-key-index-override.md \
  2026-08-12-override-cli-unification.md \
  2026-08-12-runtime-cooldown-tuning.md \
  2026-08-14-vertex-ai-provider.md \
  2026-08-15-key-usage-cap.md \
  2026-08-15-operational-config-split.md \
  2026-08-16-credential-convention.md \
  2026-08-16-model-pricing-validation.md \
  2026-08-17-multi-repo-support.md \
  2026-08-18-setup-experience-stage-1-app-changes.md \
  2026-08-18-setup-experience-stage-2-setup-tooling.md \
  2026-08-18-setup-experience-stage-3a-doc-generation.md \
  2026-08-18-setup-experience-stage-3b-guide-site.md \
  2026-08-19-test-suite-performance.md \
  2026-08-28-dashboard-authentication.md \
  2026-08-29-project-restructure.md \
  2026-09-02-dashboard-environment-tab.md \
  2026-09-03-dashboard-env-credential-guardrails.md \
  2026-09-05-hosted-only-guide-and-mandatory-keys.md
cd ../../..
```

- [ ] **Step 3: Delete the loose `docs/*.md` handoff notes**

```bash
git rm docs/2026-07-28-dispatcher-followups.md \
       docs/2026-07-29-comment-visibility-final-review-fixes.md \
       docs/2026-07-29-comment-visibility-followups.md \
       docs/2026-07-29-cooldown-review-invocation-followup.md \
       docs/2026-07-31-comment-lifecycle-followups.md \
       docs/2026-07-31-escalating-cooldown-final-review-fixes.md \
       docs/2026-08-03-supabase-hosting-migration-handoff.md \
       docs/2026-08-05-first-hosted-run-findings.md \
       docs/2026-08-05-supabase-first-deploy-provisioning-handoff.md \
       docs/2026-08-07-deploy-cli-checkpoint.md \
       docs/2026-08-10-demo-rehearsal-checkpoint.md \
       docs/2026-08-10-deploy-provider-credential-verification-gap.md \
       docs/2026-08-11-full-project-review-security-performance-quality.md
```

(This list was accurate as of the design-doc's own survey — before deleting, run `ls docs/*.md` and confirm it matches exactly these 13 files plus nothing else; if the listing differs, treat any extra loose file the same way — bot/queue-history handoff notes, not onboarding's.)

- [ ] **Step 4: Verify and commit**

```bash
ls docs/superpowers/specs/
ls docs/superpowers/plans/
ls docs/*.md
```

Confirm the specs/plans listings match the "keep" lists above exactly (plus the restructure design doc and this plan file), and `docs/*.md` now has nothing loose left.

```bash
git commit -m "$(cat <<'EOF'
Prune docs/superpowers/{specs,plans} and loose docs/*.md to onboarding scope

Keeps the ten onboarding-wizard-frame/manual-GitHub-App-validation/
server-side-session/Supabase-PAT specs and their matching plans;
drops every bot/queue-history spec, plan, and handoff note.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Utcu7cT1qPXUY1CHifBDSA
EOF
)"
```

---

### Task 6: Write a fresh `README.md`

**Files:**
- Modify: `README.md` (rewrite wholesale — the current one is entirely bot-framed)

**Interfaces:**
- Consumes: the final flattened layout and merged `CLAUDE.md` from Tasks 1-3 (the README should describe the repo as it now stands, not the pre-restructure shape).
- Produces: nothing later tasks depend on structurally — this is a leaf task.

- [ ] **Step 1: Write the README**

Cover, briefly:
- What this service is: a self-service setup wizard that walks a visitor through provisioning their own instance of a separate PR-review bot (GitHub App creation/validation, a Supabase project, an LLM provider credential, an UptimeRobot keep-warm monitor, and the final Render deploy), without this wizard ever holding a long-lived operator credential of its own.
- Local development: `uv sync --all-extras --dev`, `.env.example` → `.env` (mention `DATABASE_URL` and `ONBOARDING_SESSION_ENCRYPTION_KEY` as the two required settings, and that a Fernet key for the latter is generated via `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`), `uv run pytest -v`, `uv run ruff check .`.
- Deployment: Render (`render.yaml`), backed by its own dedicated Supabase/Postgres session store — link to `docs/superpowers/specs/2026-09-01-onboarding-server-side-session-design.md`.
- A short "Related project" note: the bot/dashboard this wizard provisions lives in a separate repo (`~/pr-review-bot` for local reference — do not invent or guess a public URL for it; if the user wants a real link included, ask them for it rather than fabricating one).
- Point at `CLAUDE.md` for the full architecture/rules and `ISSUES.md` for this service's incident/parked-issue history.

Keep it well under the old README's length (~7KB) — this is a much smaller single-service repo now; a few hundred words across these sections is enough.

- [ ] **Step 2: Sanity-check no dead references**

```bash
grep -n "bot/\|dashboard/\|guide/\|mkdocs" README.md
```

Expected: no matches (other than the deliberate "Related project" mention above, which should describe the sibling project in prose, not reference a path in *this* repo).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
Write a fresh README describing this repo as a standalone service

The prior README was entirely framed around the bot review engine
and didn't describe this service at all.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Utcu7cT1qPXUY1CHifBDSA
EOF
)"
```

---

### Task 7: Final cleanup and full verification

**Files:**
- Delete: `brief.md`
- Modify: `.gitignore` (remove the `brief.md` line)

**Interfaces:**
- Consumes: everything from Tasks 1-6 — this is the closing task that re-verifies the whole restructure end to end.
- Produces: nothing further (terminal task).

- [ ] **Step 1: Delete `brief.md`**

```bash
rm brief.md
```

(It's gitignored, so this isn't a `git rm` — confirm it was never tracked: `git ls-files brief.md` should print nothing.)

- [ ] **Step 2: Remove `brief.md`'s now-dead `.gitignore` entry**

Open `.gitignore`, find the `brief.md` line (currently line 48), delete it.

- [ ] **Step 3: Full verification bar**

```bash
uv run pytest -v
uv run ruff check .
docker build -f Dockerfile -t onboarding-wizard-final .
docker run --rm onboarding-wizard-final uv run --no-sync --no-dev python -c "import main"
```

Expected: all four green/clean, matching Task 2's Step 6 exactly (nothing should have changed behaviorally since then — this is a final confirmation, not a new check).

- [ ] **Step 4: Confirm the repo tree matches the design doc's target layout**

```bash
ls -la
```

Expected top-level entries: `CLAUDE.md`, `README.md`, `ISSUES.md`, `pyproject.toml`, `uv.lock`, `render.yaml`, `Dockerfile`, `.env.example`, `__init__.py`, `config.py`, `github_client.py`, `llm_client.py`, `main.py`, `render_client.py`, `router.py`, `session_store.py`, `supabase_client.py`, `uptimerobot_client.py`, `static/`, `tests/`, `.github/`, `.gitignore`, `.gitattributes`, `.python-version`, `.dockerignore`, `.claude/`, `docs/`. No `bot/`, `dashboard/`, `guide/`, `mkdocs.yml`, `onboarding/`, `brief.md`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
Remove brief.md and its dead .gitignore entry; restructure complete

Final step of the monorepo-to-standalone-repo restructure: brief.md
documented its own deletion once this work was reviewed and merged.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Utcu7cT1qPXUY1CHifBDSA
EOF
)"
```
