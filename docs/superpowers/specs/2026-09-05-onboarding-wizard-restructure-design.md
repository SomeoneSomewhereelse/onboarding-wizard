# Design: restructure this repo into a standalone onboarding-wizard project

## Context

This repo was just split off from a monorepo it shared with a sibling
project, the "bot" review engine (now living independently at
`~/pr-review-bot`, which kept the monorepo's full git history). This copy
has no git history of its own content yet (`git init` already ran; no
commits exist). `brief.md` (gitignored, local-only, to be deleted once this
work is reviewed) captured the starting context and a set of already-decided
points plus four open decisions, worked through via brainstorming — this
document is the resulting design.

## Already decided (from `brief.md`, unchanged)

- `bot/` and `dashboard/` are removed entirely — they live at
  `~/pr-review-bot` now, a fully separate project this service has never
  imported from anyway.
- Fresh git history — no attempt to preserve or import the monorepo's
  history for this service's own files.
- `ISSUES.md` starts non-empty, scoped to onboarding-only entries carried
  over from the monorepo's combined `ISSUES.md` (a copy sits at
  `~/pr-review-bot/ISSUES.md`): the GitHub-account-suspension saga (five
  entries, 2026-08-30 through 09-01), the SSRF-in-the-Vertex-frame security
  review, the session-storage/popup/COOP saga and its server-side-session
  resolution, the Supabase pooler-connection deploy blockers, and every
  onboarding-tagged Parked Issue/Design Gap. Leave out anything purely about
  `bot`/`dashboard`.
- Move the ~10 onboarding-relevant specs/plans out of
  `docs/superpowers/{specs,plans}/`, keeping only: the
  onboarding-wizard-frame series (2026-08-26 wizard-render-frame,
  github-app-frame, supabase-provisioning-frame; 2026-08-27
  llm-provider-frame, render-service-frame, uptimerobot-frame), the
  manual-GitHub-App-validation redesign (2026-09-01), the
  server-side-session redesign (2026-09-01), and the Supabase PAT redesign
  (2026-09-04) + its superseded OAuth-abuse-mitigation predecessor
  (2026-09-03). Drop every other spec/plan and every loose `docs/*.md`
  handoff note.
- No `guide/`-style docs site — just a fresh `README.md`.
- `render.yaml`'s `envVars` fixed to match this service's actual `Settings`
  (`DATABASE_URL`, `ONBOARDING_SESSION_ENCRYPTION_KEY` only); the
  monorepo-era `buildFilter` path-scoping trick is no longer needed.
- Verification bar: full test suite, `ruff check .`, a Docker build + boot
  smoke-test all stay green throughout.

## Decisions made in this brainstorm

### 1. Flatten `onboarding/` to repo root

There is no longer a sibling package needing the `onboarding/` prefix for
disambiguation (matches the equivalent decision already made for `bot/` in
`~/pr-review-bot`). Every file under `onboarding/` moves up one level:
`main.py`, `router.py`, `config.py`, `github_client.py`, `llm_client.py`,
`render_client.py`, `session_store.py`, `supabase_client.py`,
`uptimerobot_client.py`, `__init__.py`, `Dockerfile`, `.env`, `.env.example`,
`static/`, `tests/`. Internal imports (`from onboarding.X import Y` →
`from X import Y`) update accordingly throughout the moved code and its
tests.

### 2. Root `CLAUDE.md`: merge structure

New root `CLAUDE.md` sections, in order:

1. **Secret-handling section** — adapted from the monorepo root, trimmed to
   this service's own scope: operator secrets are now just `DATABASE_URL`
   and `ONBOARDING_SESSION_ENCRYPTION_KEY`; the rest of the section (never
   display/log a secret, never broad-dump env state, never pass one as a CLI
   arg, never let a validation error echo one, never write one somewhere
   shared, the `.env`-is-absolutely-off-limits rule, the harness-diff
   exposure vector, the "ask the user to check" rule, the incident-disclosure
   rule) carries over near-verbatim — it's generic, not bot-specific. The
   dashboard-environment-tab scoped exception is dropped (dashboard is gone).
2. **Project overview** — replaces the old "onboarding/ — self-service
   setup wizard" framing (no longer a sub-service description; this *is*
   the whole repo now).
3. **The session-store architecture section** — carried over near-verbatim
   from `onboarding/CLAUDE.md`'s "invariant this service now protects"
   section.
4. **Rules** — carried over (never log a visitor credential, relay-shape
   rule, the `RequestValidationError`-handler cross-file dependency, the
   no-`localStorage`-for-credentials rule, the one-exit-path-per-credential
   test convention), **minus** the no-shared-credential-path rule (dropped
   entirely — no sibling package exists in this repo to import from anymore,
   and the rule is preserved in `bot/`'s own CLAUDE.md at `~/pr-review-bot`
   if still relevant there).
5. **Sub-project sections** (GitHub App, Supabase, LLM provider, UptimeRobot,
   Render/deploy, Dashboard login) — carried over, with every `bot/`-internal
   pointer reworded to drop the dead cross-repo reference while keeping the
   constraint itself. Concretely:
   - "hardcoded copies of `bot/config.py`'s own field defaults" → "hardcoded
     operational defaults, kept in sync by hand with the sibling review-engine
     project's own config (`~/pr-review-bot`) — nothing automated ties the
     two together"
   - "reuses `bot/scripts/deploy.py`'s own `_DEPLOY_IN_FLIGHT_STATUSES`/
     `_DEPLOY_FAILED_STATUSES` status-bucket sets as a verbatim, paired-comment
     copy" → "keeps its own copy of Render's deploy-status buckets, matching
     the sibling review-engine project's equivalent sets by hand — no import
     between the two repos"
   - "`bot/queue/store.py::init_pool()` now seeds the `runtime_config`
     singleton row... this is what a freshly wizard-provisioned Supabase
     project gets on the bot's first boot" → reworded to describe the
     behavior without naming the bot-repo file path (e.g. "the review
     engine's own first-boot seeding handles this — no second service needs
     to open a connection into that database's schema from the outside")
   - Same treatment for any other `bot/`-file-path pointer found during
     implementation (`bot/github_app.py`'s doctor-check pattern,
     `bot/scripts/_render.py`, etc.) — reword to drop the dead path, keep the
     constraint.
6. **Plan-execution/process-hygiene section** — carried over generically
   from the monorepo root (task-brief stop instructions, re-reading a whole
   passage after a targeted correction, task-scoped review vs. brief
   correctness, live-verification docs written after the step runs, plan
   files committed inside the worktree, checking the target branch before
   merging, not re-confirming a full-suite baseline per task, logging every
   parked finding in `ISSUES.md`).
7. **The "test suite looks hung on a fresh worktree" note** — carried over
   verbatim (still accurate, still project-specific).

Dropped from the monorepo root `CLAUDE.md` entirely: module boundaries and
per-module contracts (bot-specific), the LLM-provider substitutions section
(vertex/gemini-flash-latest reasoning — bot-specific), the cost model
section, the LLM-API-testing-hygiene section if and only if it's purely
about the bot's own provider testing (needs a check during implementation —
if `onboarding/llm_client.py`'s live-credential-verification testing already
follows this discipline, as its CLAUDE.md section suggests, keep a trimmed
version scoped to this service's own one-deliberate-live-call rule).

### 3. `pyproject.toml`: single flat manifest

`onboarding/pyproject.toml`'s content becomes the root `pyproject.toml`
directly:
- `[project]` section (name, version, description, dependencies) — carried
  over as-is, description updated to drop the "provisions a visitor's own
  bot+dashboard deployment" framing if it needs adjusting (still accurate:
  the wizard still provisions a `bot`+`dashboard` deployment elsewhere, just
  not from within this repo).
- `[tool.uv] package = false` — carried over.
- `[tool.uv.workspace]` — deleted (no workspace members left).
- `[dependency-groups] dev` — carried over from the current root, minus
  `mkdocs-material` (no docs site). `cryptography`, `playwright`, `pytest`,
  `pytest-asyncio`, `pytest-xdist`, `respx`, `ruff`, `testcontainers[postgres]`
  all stay (onboarding's tests use all of these).
- `[tool.ruff]` — carried over unchanged.
- `[tool.pytest.ini_options]` — `testpaths = ["tests"]` (collapsed from four
  dirs), `addopts` unchanged (`-n 4 --dist=loadgroup --import-mode=importlib`
  stays even though its collision-avoidance reason is now moot for a single
  test dir — it's still correct and there's no reason to churn it), markers
  unchanged.

### 4. `tests/` layout

- `onboarding/tests/*.py` → root `tests/*.py`, unchanged content except
  import-path updates (`onboarding.X` → `X`).
- `conftest.py` moves from repo root to `tests/conftest.py` — matches the
  common single-package OSS convention (root-level `conftest.py` is a
  multi-package-repo pattern this repo is leaving), and matches the
  original reason it lived at root in the first place (avoiding a
  same-named-file collision across `bot/tests`, `dashboard/tests`,
  `onboarding/tests` — a constraint that disappears once there's only one
  test dir).
- Trimmed to onboarding-only content: delete the `db` fixture (bot's queue-
  table truncation), `_quarantine_local_slot_discovery`, and
  `local_slot_discovery_allowed` (all wrap `bot.scripts._override` /
  `bot.queue.store`, none apply here). Rename `onboarding_db` → `db` (it's
  the only DB fixture left). Update its body's `onboarding.session_store`/
  `onboarding.config` imports to flat `session_store`/`config`. Re-check
  `_touches_shared_postgres`, the `db_exec`/`db_query` fixtures, and the
  `db`-marker auto-apply hook against the trimmed fixture set (they should
  need no logic change, just confirmation the single remaining `db`
  fixture still satisfies whatever they key off).
- No `tests/__init__.py` — current pytest guidance recommends against one
  unless disambiguating same-named modules across sibling test dirs, which
  no longer applies. `--import-mode=importlib` stays in `addopts` (harmless,
  already working).

### 5. `.github/workflows/ci.yml`: single job

Keep only `lint-and-test` (ruff + pytest against a Postgres service
container), unchanged in content. Drop `docs` (regenerates
`guide/reference/` via `bot.scripts.gen_docs` — no such machinery exists for
onboarding and no docs site exists here) and `pages` (builds/deploys the
mkdocs site — no docs site) entirely.

### 6. `render.yaml`

- `dockerfilePath`: `./onboarding/Dockerfile` → `./Dockerfile`.
- `buildFilter`: removed (the path-scoping trick existed only to stop a
  `bot`-only push from triggering this service's redeploy inside the shared
  monorepo; moot in a real separate repo).
- `envVars`: trimmed to `DATABASE_URL` and `ONBOARDING_SESSION_ENCRYPTION_KEY`
  only (matches `config.py`'s actual `Settings`), everything else
  (`GITHUB_APP_ID`, `GEMINI_API_KEY`, `DASHBOARD_*`, `RENDER_API_KEY`, etc. —
  all `bot`/`dashboard`-shaped) deleted.

### 7. What's removed entirely

`bot/`, `dashboard/`, `guide/`, `mkdocs.yml`, non-onboarding entries in
`ISSUES.md`, non-onboarding specs/plans in `docs/superpowers/{specs,plans}/`,
loose `docs/*.md` handoff notes, `brief.md` (once this restructuring is
reviewed and merged — it documents its own deletion).

### 8. Final step: drop `brief.md` from `.gitignore`

`brief.md` is deleted as part of this restructure (point 7 above). Once it's
gone, its `.gitignore` entry (currently line 48) is dead weight referencing
a file that will never exist again in this repo — remove that line as the
last step of the restructure, after `brief.md` itself has been deleted and
everything else has been verified green.

## Implementation caution: broad searches during the move

This restructure involves a lot of mechanical find-and-update work across
many files (import paths, `bot/`-file references in `CLAUDE.md`, etc.), which
tempts a broad recursive `grep -rn`/`grep -rl` across the whole repo tree.
`.env` (real secret values) and `.env.config` (operational config, not
secret but not the target of these searches either) must always be
excluded from any such broad search — a pattern aimed at an unrelated
keyword can still match and print a full line containing a secret value if
it happens to share a line with one (see root `CLAUDE.md`'s secret-handling
section for the standing incidents this generalizes from). Concretely: use
`grep -rn --exclude='.env' --exclude='.env.config' ...` (or equivalent
path-scoped alternatives — e.g. explicitly listing the file types actually
being edited, like `*.py`/`*.md`) for every repo-wide search this
restructure requires, never a bare `grep -rn` over the full tree.

## Testing

- Full suite (`uv run pytest -v`) green against the trimmed `tests/` +
  `tests/conftest.py`.
- `uv run ruff check .` green.
- `docker build -f Dockerfile .` (path updated from `-f bot/Dockerfile`)
  builds and boots (`docker run --rm <image> python -c "import main"` or
  equivalent, path updated from `import bot.main`).
- CI (`lint-and-test` job) green on the restructured repo.

## Out of scope

- Any behavior change to the wizard itself (frames, validation logic,
  session-store schema) — this is a pure structural/packaging move.
- Deciding whether `ISSUES.md`'s carried-over entries need rewording beyond
  the removal already specified in `brief.md` — copy them over as-is.
