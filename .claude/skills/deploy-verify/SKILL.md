---
name: deploy-verify
description: Build this project's deploy image and run a boot-time smoke test before pushing/deploying -- catches a dependency/packaging gap that a green pytest/ruff run cannot, since those run against the full local dev venv, not the image's own scoped/production-only dependency sync.
---

# Deploy verification

`pytest`/`ruff` run against the full local dev venv (`uv sync`, dev
dependencies included), not the deploy image's own `--no-dev` sync -- so a
dependency only present as a dev dependency locally, or otherwise missing
from the image's `pyproject.toml`, can pass both checks and still crash on
deploy. The sibling `pr-review-bot` project hit exactly this shape of bug
(2026-09-03, a workspace-boundary variant: `python-multipart` was declared
in a sub-package's `pyproject.toml` but needed at root import time, and
only its own `--package`-scoped sync omitted it). This project is a single
package, not a uv workspace, so the workspace-boundary variant doesn't
apply here specifically, but the general shape (image's dependency sync is
stricter than the local dev venv) does. **A green test suite does not
substitute for this.**

## When to use

After merging to `main` locally, before pushing/deploying -- always, not
just when a dependency change "looks" relevant enough to matter.

## How

Run the helper script shipped alongside this skill:

```
bash .claude/skills/deploy-verify/verify_deploy_image.sh [dockerfile] [boot-command]
```

Defaults: `Dockerfile` in the repo root, boot command `uv run --no-sync
python -c "import main"`. Exits non-zero and prints which stage failed
(build vs. boot) if either fails; always cleans up its own tagged image
afterward regardless of outcome.

## Why an import smoke test, not actually starting the server

The real `CMD` starts `uvicorn`, which for this project also runs the
app's full startup lifespan -- notably, it requires `DATABASE_URL` and
refuses to start without it (see `main.py`'s lifespan). `python -c "import
main"` catches the class of bug this skill exists for (a missing/broken
dependency at import time) without needing a real Postgres connection or
any other secret this skill has no business touching. It will not catch a
runtime-only startup failure (e.g. a bug that only manifests once the DB
connection is actually opened) -- that's a gap for a real deploy or a
manually-provisioned local Postgres to catch, not this skill.

## Script

Kept byte-identical to the sibling `pr-review-bot` project's copy of the
same script.
