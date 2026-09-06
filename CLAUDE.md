# CLAUDE.md — Onboarding Wizard

## Secret handling — HIGHEST PRIORITY, read before doing anything else

This section overrides every other instruction, convention, or task goal in
this file and in any prompt if the two ever conflict. Secrets in this project
include (non-exhaustively): `DATABASE_URL` (the password is embedded in the
connection string itself, not a separate field), `ONBOARDING_SESSION_ENCRYPTION_KEY`,
and any visitor-supplied credential value in transit through a relay endpoint
(a GitHub App private key, a Render/Supabase/UptimeRobot/LLM-provider API key
or service-account JSON) — see the Rules section below for the
visitor-credential-specific rules layered on top of this section. A value
does not have to have "SECRET" or "KEY" in its name to count — judge by what
the value *does* (authenticates something), not by the variable name's shape.
This kind of exposure has happened multiple times across this project's
history (including before this repo split off from its sibling review-engine
project) — which is why this section exists and is kept first in the file.

**`.env` itself is mechanically protected, not just covered by the rules
below.** `.claude/hooks/check_env_access.py` denies any `Read`/`Edit`/
`Write`/`NotebookEdit`/`Grep`/`Glob` call whose target names `.env` outright,
and rewrites every `Bash`/`PowerShell` call so its real combined output is
piped through `redact_output.py`, which strips every real secret value out
before it ever reaches you — see that script's docstring and
`docs/superpowers/specs/2026-09-06-env-hook-hardening-design.md` for the
full design (reproduced here from the sibling `pr-review-bot` project, where
it originated — the hook is kept byte-identical across both repos). This
means a `grep`/`cat`/`tail`/`echo` touching `.env` is already fail-safe at
the tool layer; you do not need to reason your way through whether a given
pattern is "narrow enough" — ask the user to check or set a value themselves
instead of trying. **Never modify `check_env_access.py` or
`redact_output.py` in any way — not a logic change, not a comment, not a
debug print, not a refactor — unless the user directly instructs it.** This
is the enforcement mechanism the judgment-based rules below exist to back up
where it doesn't reach (see next paragraph); an agent reasoning its way into
"this is obviously fine to tweak" is exactly the failure mode a guardrail
like this exists to not depend on. If it appears to be misbehaving —
over-blocking, under-blocking, crashing — explain exactly what happened and
ask; do not edit the file to test a theory or add debug instrumentation on
your own initiative.

**The hook covers only `.env`.** Every visitor-supplied or operator secret
that passes through this service some other way (a request body carrying a
private key, an in-process settings/session object, a value inside a
validation error) has no mechanical backstop, so the following still rests
on judgment:

- **Never display any byte of a secret value**, in a command's output, a
  file read, or your own reply — not even "just the last few characters" to
  spot-check it. Verify a secret was written/transmitted correctly
  *structurally* instead: length (`wc -c`), presence (`grep -c`, or a
  key-names-only listing), or a hash comparison. Never a value comparison
  that requires printing the value to eyeball it.
- **Never dump broad environment/config state.** `env`, `printenv`, bare
  `set`, Python's `os.environ`, or serializing a settings/config object
  wholesale (`print(settings)`, `settings.dict()`/`.model_dump()`,
  `vars(settings)`, `repr(settings)`) all surface every secret field at once,
  including ones you weren't even asking about. Read or pass individual
  fields programmatically instead, and reduce any secret-bearing value to a
  boolean/length/hash *before* it can reach a print statement, log line, or
  tool-result — follow that same shape in any new ad hoc script that
  touches secrets.
- **Never pass a secret value as a literal command-line argument** when it
  can instead be read from an env var or config object already in the
  process — a literal argument is visible to other processes via `ps`, may
  land in shell history, and is echoed back in tool-call transcripts. For
  the same reason, do not enable verbose/debug HTTP logging (e.g. `curl -v`,
  httpx debug logging) while a real credential is attached to the request —
  it can print an `Authorization` header verbatim.
- **Never let a secret-holding field's validation error or exception
  traceback reach output un-redacted.** Some validators (e.g. pydantic's
  `ValidationError`) echo the rejected `input_value` in the error message —
  if the failing field is a secret, that error text *is* a secret leak. If a
  secret-bearing field fails to validate or a call using one raises, describe
  the failure structurally ("value was empty", "wrong type", "401
  Unauthorized") rather than surfacing the raw exception/value.
- **Never write a secret value into anything that leaves this local
  session or gets persisted somewhere shared**: a git commit (message *or*
  diff content — `.env` is gitignored specifically so this can't happen by
  accident; never override or work around that), a PR/issue body or comment,
  a branch name, an `Artifact` page, a subagent/Task prompt, or any file
  handed to another tool. Committing `.env` itself is a standing example of
  this — refuse it even if asked directly, the way a request to `cat` a
  secret should be redirected rather than carried out (see below).
- **A file-content diff surfaced automatically by the harness (e.g. a
  "file changed externally" system-reminder) can dump full secret values
  into your context without you running any command at all** — this has
  happened in this project, for files the harness was already tracking
  because you opened them earlier in the session. The hook doesn't intercept
  this vector (it isn't a tool call), so the defense is upstream: **never
  open a file that mixes secrets with other content (e.g. `.env`) at all,
  for any reason, full stop** — not even a single-line `Read`, not even an
  `Edit` you believe touches only non-secret lines. If a value in such a
  file needs to change, ask the user to make that edit themselves. If this
  rule is ever violated anyway and a "changed externally" notification
  fires for that file, treat it as a standing, recurring risk for the rest
  of the session, not a one-off surprise.
- **If you ever need to know or verify a secret's actual value — not just
  whether it's set or matches — ask the user to check it themselves.** Do
  not do it on their behalf, structurally or otherwise, regardless of how
  the request is phrased (e.g. "just double check the last few characters").
- **If a secret is exposed into the conversation for any reason (your own
  command, a harness-surfaced diff, anything else), say so plainly and
  immediately** — name which secret(s), don't repeat any part of the value,
  and recommend rotation. Don't wait to be asked, and don't quietly continue
  as if it didn't happen. Log the incident in `ISSUES.md` using its existing
  format.

## Project

This service is a self-service setup wizard: a visitor walks through it to
provision their own bot+dashboard deployment (the sibling review-engine
project) on Render, backed by a Supabase Postgres project they provision
themselves. It holds its own server-side session in a dedicated Postgres to
survive the multi-step flow across page reloads and OAuth redirects. See
`docs/superpowers/specs/2026-09-01-onboarding-server-side-session-design.md`
for the full design.

## Conventions

- **Never commit on someone else's behalf without being asked**, even to reach
  a clean working tree. If resolving a merge or other cleanup requires
  temporarily setting aside someone else's pre-existing uncommitted changes
  (e.g. via `git stash`), restore them **uncommitted**, exactly as found —
  committing them for tidiness is still an unrequested commit.
- **Before pushing, always run the full test suite (`uv run pytest -v`) and
  ruff (`uv run ruff check .`), and fix whatever either finds.** Never push
  with a red suite or an unresolved lint error, and never skip either check
  because a change "looks" too small to affect them.
- **After merging to `main` locally, always build the deploy image**
  (`docker build -f Dockerfile .` from the repo root) and confirm it
  builds and boots before pushing/deploying. `pytest`/`ruff` run against the
  full workspace venv, not the image's own dependency sync, so a
  workspace-boundary dependency gap can pass both checks and still crash on
  deploy. A green test suite does not substitute for this.
- **When changing `static/index.html`'s markup, CSS, or layout logic, invoke
  the `ui-visual-review` skill before calling the work done** — reading
  HTML/CSS and reasoning about layout is not a substitute for actually
  rendering the page (see the skill for why, including the RTL-specific
  check).

## The invariant this service now protects (2026-09-02, revised)

This backend used to be a **stateless relay** — no database, no session
store, no server-side credential persistence of any kind, by deliberate
design (see
`docs/superpowers/specs/2026-08-26-onboarding-wizard-render-frame-design.md`
section 3). That invariant was found fragile in practice: mobile browsers
were observed destroying `sessionStorage` (and the browsing context holding
it) mid-flow, most sharply during Supabase's OAuth redirect, resetting the
whole wizard including earlier frames' already-validated credentials — see
`ISSUES.md`. It was deliberately replaced, not patched around.

**The service now holds a server-side session** (`session_store.py`)
in a **new, dedicated Postgres** — never the sibling review-engine project's
own queue DB, never a visitor's own provisioned project — identified by an
`HttpOnly`/`Secure`/`SameSite=Lax` cookie rather than anything tab-scoped.
Every credential value is application-encrypted (Fernet, one opaque blob per
frame) before it's written. See
`docs/superpowers/specs/2026-09-01-onboarding-server-side-session-design.md`
for the full design, including the fork-risk hardening on
`session_store.update_frame()` (it requires an existing session and never
upserts — `create_session()` is the only place a session id is ever minted).
A session's TTL is `session_store.SESSION_TTL` (4 hours as of this writing —
check the constant itself, not this number, if it matters), swept lazily
(no cron): a lookup past its `expires_at` is deleted and treated identically
to a missing session, and `create_session()` sweeps expired rows before
inserting.

What this changes in practice:
- A relay endpoint's *first* submission of a credential still comes from the
  browser (the visitor pastes/uploads it), but the server now persists it
  server-side on success and — for any later step that needs the same
  credential again (e.g. the final deploy frame needing the GitHub key,
  Supabase connection string, and Render key together) — reads it back from
  the session instead of the browser resending it.
- `GET /api/session` (called by the page's `restoreFromSession()` on every
  load) is the source of truth for which frames are already done, not
  `sessionStorage`. It maps session-store frame keys onto the wizard's UI
  frame ids explicitly (not 1:1 — `render` backs three UI frames; `supabase`
  has a genuine "OAuth done, project not yet created" in-between state) and
  never echoes a raw credential back to the browser — only the same class of
  non-secret display fields (an account/org/project name, a URL, an id) this
  file already allowed relay responses to carry.
- A visitor-facing "Start over" control (`POST /api/session/reset`) deletes
  the session and clears the cookie — the explicit, deliberate way to clear
  progress, replacing the implicit "just don't complete a frame" model a
  stateless relay didn't need.

**Two implementation details found missing during a 2026-09-02 correctness
review, fixed the same day (see `ISSUES.md`) — both load-bearing, not
optional:**
- **Every `router.py` endpoint calls `session_store.py` through the
  `_get_session`/`_read_frame`/`_update_frame`/`_create_session`/
  `_delete_session` wrapper functions at the top of `router.py`, never the
  `session_store.*` functions directly.** They exist solely to run the sync,
  real-Postgres-calling `session_store.py` functions via `asyncio.to_thread`
  — calling `session_store.py` directly from an `async def` endpoint blocks
  the single event loop for every other concurrent request for the duration
  of that DB round-trip. A new endpoint that needs the session store uses
  these wrappers, not a fresh direct call.
- **`update_frame(..., replace=True)` fully discards a frame's existing
  content instead of merging — used only by the two endpoints that
  represent "start this frame over" (`validate-key`, `connect`).** A plain
  merge on a resubmitted Render key or a Supabase reconnect would leave the
  *previous* account/project's `service_id`/`ref`/`database_url` sitting in
  the session, which `GET /api/session`'s completeness check (keyed off a
  field's mere presence) could then report as still-done for the wrong
  account. Every endpoint's own docstring/comment says which one it is; a
  new "start over" endpoint for a different frame should use `replace=True`
  too, not assume a plain merge is always safe. Also check every
  `update_frame()`/`_update_frame()` call's return value for
  `SessionNotFound` and report `{"valid": false, "reason": "no_session"}`
  rather than silently reporting success when the write didn't happen — the
  one deliberate exception is `trigger-deploy`'s own write (see its inline
  comment): a real, non-idempotent external side effect already happened by
  that point, so failing the response would only invite a duplicate deploy.

## Rules

- **Never log a visitor-supplied credential**, in full or truncated — same
  standard as this file's secret-handling section applies to the operator's own secrets, applied
  here to strangers' secrets, which if anything deserves *more* caution
  since these are people who did not choose to trust this codebase with
  their operational hygiene the way the project's own operator has.
- **Every relay endpoint takes a credential in the request body and returns
  a verdict — never the credential itself, never a derived artifact that
  reconstructs it.** A response schema that echoes back anything from the
  request beyond a boolean/enum/short display name (e.g. an account or
  owner name) needs a specific reason, not just convenience.
- **New external-service integrations follow the same relay shape** as the
  Render frame (`render_client.py` / `router.py`'s `/api/render/validate-key`
  pattern): browser holds the token, backend is a stateless pass-through per
  request. Do not special-case a "simple" integration into calling an
  external API directly from browser JS just because it doesn't strictly
  need server-side confidentiality (see design doc section 3 for why).

## What the implementation adds to these rules

- **The app-wide `RequestValidationError` handler lives in `main.py`,
  not `router.py`.** It's what turns a malformed request into the generic
  `{"detail": "invalid request"}` 422 instead of FastAPI's default response
  (which echoes the rejected input, including a submitted credential). Every
  relay endpoint lives in `router.py` and inherits this protection only
  because `main.py` mounts `router` on the same `app` the handler is
  registered on — a non-obvious cross-file dependency. A new relay endpoint
  added to `router.py` gets this for free; the same router mounted on a
  *different* app (a test harness building its own `FastAPI()`, a future
  split-out service) would lose it silently.
- **A visitor's credential never touches `localStorage`, on the browser
  side too — not just "no database" on the backend.** This page's own
  non-secret theme/language preferences legitimately use `localStorage`
  (they should persist across tabs/sessions); a credential must not, since
  `localStorage` persists past the tab closing. As of the 2026-09-02
  server-side-session redesign, most credentials no longer touch
  `sessionStorage` either — once a frame's endpoint validates a credential,
  it's persisted server-side (`session_store.py`) and never needs to be
  resent, so it never needs local storage at all (the Render API key and
  GitHub App credentials are the clearest examples: `STORAGE_KEYS` has no
  entry for either). Where a frame still keeps a local `sessionStorage`
  mirror (`render-service`, `supabase`, `llm-provider`, `dashboard-auth`,
  `uptime-pinger`), it holds only non-secret continuity/display state for
  the current page view (a url, an id, a provider/model choice, a
  `completed` flag) — never the credential value itself. A new frame that
  needs to remember something locally follows that non-secret-only pattern,
  not the pre-redesign one of mirroring the whole credential.
- **Every credential-carrying `fetch()` on the page has its own
  `..._leaves_the_page_exactly_once` test in
  `tests/test_onboarding_page.py`,** each asserting
  `body.count('fetch("<that endpoint>"') == 1`. This is deliberate: a visitor
  credential should have exactly one, auditable exit path per page load. The
  check was originally a single blanket `body.count("fetch(") == 1`; it was
  narrowed to per-endpoint counts once frame 2 legitimately added a second
  and third relay call, which is the *only* acceptable way to satisfy it —
  loosening a count to `>= 1`, or dropping one, is not. A new frame that
  adds a relay call adds its own such test alongside; a second `fetch()` to
  an endpoint that already has one is the signal to stop and ask why that
  credential now has two exits, not to bump a number.
  For an endpoint called through the shared `callSupabaseRelay(...)` helper
  (sub-project 3's `list-organizations`, `create-project`, `project-status`,
  `connection-info` — see below) rather than a direct `fetch()`, the audit
  target is `body.count('callSupabaseRelay("<that endpoint>"') == 1`
  instead. This is a faithful adaptation of the same one-exit-path
  invariant to the helper's indirection, not a loosening of it: the
  endpoint string must still appear exactly once as the call's own
  argument, wherever in the call chain that argument is spelled.
  `callSupabaseRelay` itself no longer carries `access_token` at all (the
  server reads it from the session cookie) — its callers now pass at most a
  small non-secret payload (e.g. `organization_slug`), never a credential.

## What sub-project 2 (GitHub App automation) adds to these rules

- **App creation is fully manual (2026-09-01), not just installation.**
  The wizard used to automate creation via GitHub's App Manifest flow (a
  JS-constructed form POST to `github.com/settings/apps/new`). A GitHub
  account was suspended during this frame a second time, with the
  install-page fix (below) already shipped — pointing at the manifest
  flow's own automated navigation as the next most likely remaining
  source, though this is **not confirmed**: the account's age, this
  project's own App-creation rate during testing, or some other factor
  could equally explain it. Automation was removed as a precaution given
  that uncertainty, not as a diagnosed fix — see
  `docs/superpowers/specs/2026-09-01-onboarding-github-app-manual-validation-design.md`
  and `ISSUES.md`. There is no manifest, no `redirect_url`/`state` CSRF
  dance, and no cross-origin form POST left in this frame at all.
- **No URL referencing `github.com` appears anywhere on the page, for
  either creation or installation.** The 2026-08-31 install-page fix
  (below) already banned URLs for that one step; this extends the same
  policy to App creation, on the theory that any correlation between this
  page and a GitHub navigation — however it's initiated — is the thing
  worth avoiding, not just a JS-driven redirect specifically. Instructions
  are breadcrumb text only ("Settings → Developer settings → GitHub Apps →
  New GitHub App"). `test_page_offers_no_route_to_the_install_page_at_all`
  and its sibling `test_page_offers_no_route_to_github_app_creation_either`
  both enforce this.
- **A doctor.py-style validation checklist compensates for losing the
  manifest flow's built-in correctness.** A Manifest always creates an App
  with exactly the requested permissions/events/webhook URL; a hand-created
  App can have any of those wrong by a missed checkbox. The visitor pastes
  back App ID + private key (the private key via a file picker, converted
  to base64 client-side — never typed/pasted as text), and
  `github_client.validate_app()` reads the App's actual configuration back
  from GitHub (`GET /app`, `GET /app/installations`, `GET /app/hook/config`,
  all under the visitor's own App JWT) and reports one pass/fail line per
  requirement. The frame unlocks — and only then pushes credentials to
  Render — once every line passes. This is a fresh, independent
  implementation of the same idea the sibling review-engine project's own
  doctor checks already use for its operator-side CLI/deploy path, not a
  shared import.
- **Installation is auto-discovered, not typed.** `validate_app()` calls
  `GET /app/installations` itself rather than asking the visitor for an
  installation ID — mirrors the sibling review-engine project's own
  exactly-one-installation expectation for its GitHub App discovery. Zero
  installations and multiple installations are both distinct, reported
  failure states, not folded together into one generic "not found."
- **The webhook secret is generated by the wizard, not invented by the
  visitor.** `ensureGithubAppWebhookSecret()` (client-side,
  `crypto.getRandomValues`, same shape as the dashboard frame's session
  secret) generates and persists one the first time this frame's
  instructions render, and displays it for the visitor to copy into
  GitHub's form. GitHub's API never returns a webhook secret to check it
  against, so this field is the one requirement `validate_app()` cannot
  verify — its presence in the pushed env vars is all that's checked.
- **`validate-app`'s request body carries a GitHub App's full private
  key** — the same sensitivity tier as this project's own
  `GITHUB_APP_PRIVATE_KEY`. Treat it accordingly: never logged, never in an
  unhandled exception's message, narrow `except` clauses only.
- **The wizard offers no route to GitHub's App-install page — no redirect,
  no link, and no URL text to copy either (2026-08-31).** Five separate
  throwaway GitHub accounts were suspended for a ToS violation at exactly
  this step: three via `location.href`, one via an `<a>` carrying both
  `rel="noreferrer"` and `referrerpolicy="no-referrer"`, and one via the
  visitor pasting the URL into their own address bar. The fourth run rules
  out the `Referer` header (a click still sends `Sec-Fetch-Site:
  cross-site`, which no page can suppress); the fifth rules out the
  navigation's initiator too. What the surviving runs have in common is
  that the visitor reached the install page by navigating *inside GitHub*.
  See `ISSUES.md`.

- **There is no `public_base_url` setting, and the page's base URL is never
  templated in from the server (2026-08-31).** `index.html` derives it from
  `location.origin`, which the browser already knows exactly and which is by
  definition the origin GitHub and Supabase redirect back to. The old
  hand-set `PUBLIC_BASE_URL` was a second source of truth for the same fact,
  and the two drifted: the env var read `https://host` while the page was
  served at `https://host/`, which broke Supabase's OAuth leg outright with
  `redirect_uri not allowed`. Do not reintroduce the setting, its validator,
  or the lifespan check without a use the browser genuinely cannot serve
  itself — removing it also removed a raw-substitution injection surface, so
  `supabase_oauth_client_id` is now the only value templated into the page's
  `<script>` and keeps its own validator for exactly that reason.
- **Supabase's OAuth callback is a bare path (`/oauth/supabase/callback`),
  never a query flag.** Supabase matches registered redirect URIs exactly,
  and a query string is the part most likely to be normalised away or
  mis-registered. `router.py` serves the same document on that path as on
  `/`, and the page routes on `location.pathname`. The GitHub frame has no
  redirect leg to compare this against anymore (App creation and
  installation are both fully manual — see the sub-project 2 section
  above), so this pattern is Supabase-specific, not a choice between two
  live alternatives.
- **The browser sends the exact `redirect_uri` it used to
  `exchange-oauth-code`, rather than the server rebuilding it.** OAuth
  requires the authorize and token legs to agree byte-for-byte, and deriving
  them independently on two sides is how they drift apart. Supabase
  validates the value against the app's registered list, so accepting it
  from the caller cannot redirect anything anywhere; the field still carries
  a shape check so no arbitrary string is relayed outbound.

## What sub-project 3 (Supabase provisioning) adds to these rules

- **The credential is a visitor-pasted Personal Access Token, not an
  OAuth app (2026-09-04 redesign)** — see
  `docs/superpowers/specs/2026-09-04-supabase-pat-frame-design.md`. The
  original design used an operator-registered OAuth app, which made this
  service's one shared credential across every visitor; a follow-up
  brainstorm found the stated reason for that choice ("PAT can't do full
  automation") didn't hold up against Supabase's own docs, so this
  frame now matches every other frame's model (Render, GitHub App, LLM
  provider, UptimeRobot): the visitor supplies their own credential, no
  operator-level Supabase secret exists.
- **`POST /api/supabase/validate-key` does both credential validation and
  org listing in one call** (`supabase_client.validate_key`, one
  `GET /v1/organizations` request) — Supabase has no separate
  token-identity endpoint, so this doubles as both. On success the PAT is
  persisted server-side (`session_store.py`, under the `supabase` frame's
  `api_key` field) via `_update_frame(..., replace=True)` — a resubmitted
  key (via "Change") must discard any previous project's `ref`/`db_pass`/
  `database_url`, same reasoning the Render/GitHub validate-key endpoints
  already document.
- **The project name is captured alongside the org picker, after key
  validation** — not before, since there's no pre-redirect step anymore
  to have captured it earlier (the original OAuth design had the visitor
  type it before authorizing). `create-project`'s request body carries
  both `organization_slug` and `name` now; the session never pre-stores
  `name` on its own.
- **`db_pass` is still generated server-side** (`create-project`,
  `router.py`) — this was already true before this redesign (2026-09-02)
  and is unaffected by the credential swap. It never needs to leave the
  server: `create-project` mints it, passes it directly to
  `supabase_client.create_project()`, and stores it in the session for
  `connection-info` to assemble the final `DATABASE_URL` with later.
- **`connection-info` never returns Supabase's own `connection_string`/
  `connectionString` fields, nor `db_user`/`db_host`/`db_port`/`db_name`
  individually** — unchanged from before this redesign. Since `db_pass`
  already lives server-side, the endpoint assembles the full
  `postgresql://` URL itself and stores it in the session
  (`supabase.database_url`); its response to the browser is just
  `{"valid": true}`.
- **`create-project`, `project-status`, and `connection-info` all read
  `api_key` from the session** (via `session_store.read_frame`), never
  from the request body — set by `validate-key` above. There is no
  client-facing refresh path (there never was one exposed to the
  browser even under OAuth) and nothing to refresh: a PAT doesn't expire
  the way an OAuth access token does.

## What sub-project 4 (LLM provider credential UI) adds to these rules

- **The model this deployment runs is always fetched live from the
  provider's own catalog, never hardcoded.** `llm_client.py`
  makes exactly one models-listing call per credential submission, which
  doubles as validation. No provider's default/fallback model string may
  be hardcoded anywhere in this service — that is exactly the drift this
  sub-project exists to avoid (the real-world incident this generalizes
  from: a hardcoded `gemini-flash-latest` default string 404-ing against
  Vertex's publisher-model catalog).
- **Gemini and Vertex share one internal helper**
  (`_list_generative_models`) since both go through the same `google-genai`
  SDK and differ only in how `genai.Client` is constructed. A change to the
  filtering/prefix-stripping logic belongs in that shared helper, not
  duplicated per provider. **The `generateContent` filter only applies
  when `supported_actions` is populated** — Vertex's response converter
  (`google/genai/models.py`'s `_Model_from_vertex`) never sets that field
  at all, unlike the Gemini Developer API's converter, so a Vertex model
  is let through rather than dropped when the field is `None`. Filtering
  Vertex strictly on that field (the original implementation) silently
  emptied its entire model catalog for every credential — verify against
  the installed SDK's actual converter functions before changing this
  again, not just against the `Model` type's field list.
- **Groq's model list is deliberately unfiltered** — its `Model` type
  carries no capability field to distinguish chat-completion models from
  Whisper/TTS/moderation ones, and a name-pattern heuristic was
  deliberately rejected as guessing at API behavior this project's
  testing-hygiene discipline warns against. Do not add one without a new
  brainstorm.
- **The frame's unlock gate requires both a live-validated credential AND
  an explicit model pick** — there is no fallback to any baked-in default
  if the visitor skips picking a model. A credential that validates but
  returns zero eligible models is a genuine dead end under this gate; it
  gets its own distinct error message (`err_llm_no_models_available`)
  rather than folding into a generic validation failure.
- **No operator-level settings were added for this sub-project** — unlike
  Supabase's OAuth app, every credential here is visitor-supplied per
  request. `config.py` and `main.py`'s `lifespan` are
  untouched by it.
- **Gemini/Vertex tests mock at the SDK client boundary
  (`google.genai.Client` itself is monkeypatched), not `respx`** — the
  async listing call itself is `httpx`-based for both providers (verified:
  this environment has no `aiohttp` installed, so `google-genai`'s async
  path falls back to `httpx` regardless of auth type). What `respx` alone
  can't cover is Vertex's separate credential step: a service-account
  refreshes its access token via `google.auth`'s synchronous,
  `requests`-based transport before the `httpx` listing call ever happens,
  and `respx` only intercepts `httpx`. SDK-boundary mocking sidesteps
  needing two different mocking libraries for one code path, and covers
  Gemini and Vertex with the same test shape despite their different
  `Client`-construction inputs (`api_key` vs a service-account credential
  object). Groq's tests use `respx` as normal, since its SDK transport is
  pure `httpx` end-to-end with no separate credential-refresh step.
- **All three credentials share one `fetch(endpoint, ...)` call site**
  in `validateLlmProviderCredential()`, with `endpoint` set to a literal
  per-provider URL string in each branch — a second adaptation of the
  one-exit-path convention (alongside `callSupabaseRelay`'s): audited by
  checking each `endpoint = "/api/llm/<provider>/list-models"` assignment
  appears exactly once, plus the shared call site itself appears exactly
  once. A new provider added to this frame follows the same shape, not a
  new dedicated `fetch()` call.
- **The Vertex credential's storage field name
  (`gcp_service_account_key_b64`) deliberately differs from its wire field
  name (`service_account_key_b64`)** — the frame maps between them in
  `showLlmProviderModels`'s caller. Keep this distinction if either name
  changes: the wire name matches the relay endpoint's pydantic field, the
  storage name matches this service's `GCP_SERVICE_ACCOUNT_KEY`-adjacent
  naming convention for sub-project 6 to read later.
- **`list_vertex_models` validates the submitted service-account JSON's
  `token_uri`/`universe_domain` against Google's real values before ever
  constructing credentials from it — this is a load-bearing SSRF guard, not
  a style nit.** `google.oauth2.service_account.Credentials` reads both
  fields verbatim out of the caller-supplied dict and uses them as the
  destination of the token-refresh request it issues later; since the
  visitor also supplies the matching private key, an unpinned value lets
  them redirect this server's own outbound request to an arbitrary host
  (found by a dedicated security review, 2026-08-28 — see `ISSUES.md`).
  Never relax this to "just check the JSON parses" again. The same fix
  proactively refreshes the credential off the event loop via
  `asyncio.to_thread` before the async listing call, since google-auth's
  refresh is synchronous under the hood — remove this and every other
  visitor's concurrent request stalls for the refresh round-trip.

## What sub-project 5 (UptimeRobot keep-warm frame) adds to these rules

- **UptimeRobot's v3 REST API (`Bearer` auth, JSON,
  `https://api.uptimerobot.com/v3/monitors`) is used for every call this
  frame makes — never the legacy v2 form-API.** The sibling review-engine
  project's own deploy script still uses v2 for its read-only `getMonitors`
  check, and that is intentionally untouched — no reason to migrate a
  working read-only check. But v2's `POST /newMonitor` was verified live to
  reject monitor creation on a free-plan account (`403 "You are not allowed
  to use some settings with your current plan"`), while v3 was verified
  live to accept the identical creation on the same account. Do not
  "simplify" this frame's client onto v2 without re-verifying that live
  behavior first.
- **This frame reads a `sessionStorage` key it does not write:
  `onboarding.renderServiceUrl`.** The "Render service" frame (sub-project 6,
  now built) writes the deployed service's base URL there on its own
  completion — see
  `docs/superpowers/specs/2026-08-27-onboarding-uptimerobot-frame-design.md`
  section 3's forward contract, and (as of 2026-09-02)
  `restoreFromSession()`'s own write of this same key from
  `GET /api/session`'s `render-service` display field on page load, so a
  reload after that frame is done still has it available.
- **Dedupe-before-create is load-bearing, not an optimization.** Every
  credential submission to this frame (including a "Change" resubmit)
  calls `GET /v3/monitors` before ever calling `POST /v3/monitors` — a
  monitor is only created if none already watches the derived
  `<render_service_url>/healthz` target. Removing this check reintroduces
  orphaned duplicate monitors on every resubmit.
- **There is no way to detect a read-only (Monitor-Specific) API key
  server-side — verified live.** `POST /v3/monitors` and `GET
  /v3/monitors` both return the identical `401 {"message": "Invalid
  token.", "code": "003-005"}` for a valid-but-read-only key as for a
  wholly invalid one. Do not add a `reason` value implying this frame can
  tell the two apart; the only mitigation is UI copy (the input's help
  text and the `unauthorized` error both name the Main-API-Key requirement
  explicitly).
- **The monitor's `friendlyName`/`type`/`interval`/`timeout` are fixed, not
  visitor-configurable** — `friendlyName` is always the derived target URL
  itself (matching this project's own production monitor's existing
  naming), `type: "HTTP"`, `interval: 300`, `timeout: 30`. A future change
  that lets the visitor choose these needs its own brainstorm, not a quiet
  addition here.
- **`uptimerobot_client.py` follows the same raw-`httpx`, no-SDK
  shape as `render_client.py`/`github_client.py`/`supabase_client.py`** —
  UptimeRobot has no official SDK. Tests mock via `respx`, same as those
  three modules, not the SDK-boundary mocking `llm_client.py`'s tests
  needed for `google-genai`.
- **Dedupe-before-create pages through every result via v3's cursor-based
  `nextLink`, not just the first `GET /monitors` response (2026-08-28 fix,
  see `ISSUES.md`)** — a single-page scan silently misses a match on any
  account with more monitors than fit in one page, defeating the
  dedupe-is-load-bearing guarantee above. The page cap
  (`_MAX_LIST_PAGES`) is a defensive bound against a malformed/looping
  `nextLink`, not an expected real-account limit.
- **`delete_monitor` (backed by `DELETE /v3/monitors/{id}`) exists so a
  changed render-key or render-service frame can clean up the monitor it
  orphans** — `static/index.html`'s `cleanupOrphanedUptimeMonitor()`
  calls it best-effort from `beginChange`, before `relockDownstreamOf`
  clears the uptime-pinger frame's own `sessionStorage` record (which is
  where the monitor id it needs comes from). Only `render-key` and
  `render-service` changes trigger it — every other frame's "Change"
  leaves the deployed service's URL, and therefore the existing monitor,
  valid.

## What sub-project 6 (Render service creation + deploy, final) adds to these rules

- **What was originally decomposed as one "sub-project 6" frame is
  actually two frames**: "Render service" (position 2, right after the
  Render-key frame) creates the service; the pre-existing placeholder
  `frame-render-deploy` (reserved since sub-project 1's shell, always
  last in `FRAME_ORDER`) is "Finish & Deploy" — triggers the real deploy
  once frames 2-5 have run. Do not conflate them or try to merge them
  back into one frame; the accordion's sequential-lock model is why
  they're split (see
  `docs/superpowers/specs/2026-08-27-onboarding-render-service-frame-design.md`
  section 3).
- **Reversed 2026-09-02: no frame pushes its own credential to Render
  incrementally anymore.** The original design here had frames 2/3/4 each
  push-and-clear the moment they validated, as a deliberate
  browser-residency-shrinking property. That property is moot now that
  those credentials never sit in `sessionStorage` to begin with — they're
  persisted server-side (`session_store.py`) on validation instead. The
  four per-frame push endpoints (`github/push-render-vars`,
  `supabase/push-render-var`, `llm/push-render-vars`,
  `dashboard-auth/push-render-vars`) and their four frontend push
  functions are **deleted, not deprecated** — do not resurrect this
  pattern for a new frame.
- **One bulk push instead: `POST /api/render/bulk-push-env-vars`**, called
  by the final "Finish & Deploy" frame (`triggerRenderDeploy()`) right
  before `trigger-deploy`. It reads every completed frame's data straight
  from the session (`session_store.read_frame`, no request body at all)
  and assembles the full env-var dict in one place — `router.py`'s
  `bulk_push_render_env_vars()`. A frame whose session data is missing
  (never completed) is simply omitted from the push, not an error; the
  wizard's own sequential frame-lock already guarantees every frame is
  done by the time this endpoint is reachable in normal use.
  `render_client.push_env_vars`'s push-failure-handling behavior
  (partial-failure reporting via `_push_result`) is unchanged — only
  *when* it's called moved from per-frame to this one call site.
- **The bulk push also always includes `_GENERIC_OPERATIONAL_ENV_DEFAULTS`**
  (2026-09-02) — the sibling review-engine project's own tuning-knob
  operational keys that its deploy script pushes but no wizard frame has a
  field for (dispatcher backoff/retry/sweep settings, `GCP_LOCATION`,
  `LLM_REQUEST_TIMEOUT_SECONDS`). Unconditional, not gated on any frame:
  these are hardcoded operational defaults, kept in sync by hand with the
  sibling review-engine project's own config (`~/pr-review-bot`) — nothing
  automated ties the two together. `GITHUB_TARGET_REPO` and `GCP_PROJECT`
  are deliberately excluded rather than pushed as `""` — Render's API
  rejects an empty env-var value outright, and both default genuinely
  blank — same reasoning the sibling project's own deploy script already
  encodes for its optional-empty env keys. Keep this dict in sync with the
  sibling project's config by hand.
- **The final `render-deploy` frame stays open (doesn't collapse) once
  done** (2026-09-02) — `completeFrame()` grew a 5th, optional `keepOpen`
  parameter (every other call site omits it, keeping the default
  collapse-on-complete behavior). The dashboard link (the service's live
  URL, which routes to the dashboard's login-gated `GET /` once the
  deploy is live) is the actual payoff of finishing the wizard; collapsing
  the frame the instant it appears would hide it. Applies to both the live
  completion path (`finishRenderDeploy()`) and the reload-resume path
  (`restoreFromSession()`), which previously didn't even re-show the
  done-section/link at all on a reload after a completed deploy — fixed
  alongside this.
- **`relockDownstreamOf(id)` relocks by real dependency, not by page
  position** (2026-09-02) — `FRAME_DEPENDENTS` is a precomputed-transitive-
  closure map naming which frames' already-submitted data actually goes
  stale when a given frame's data changes (e.g. `render-service`'s
  `service_url` feeds `github-app`'s webhook-URL check and
  `uptime-pinger`'s monitor, so changing it relocks both; `llm-provider`
  feeds nothing but the final bulk push, so changing it relocks only
  `render-deploy`). Replaces the old "relock everything positioned after
  `id` in `FRAME_ORDER`" rule, which forced redoing frames — e.g.
  `uptime-pinger` after an `llm-provider` change — that read none of the
  changed frame's data. Because `render-deploy` is frequently *not* the
  next positional frame after the one just resubmitted anymore,
  `completeFrame()` also gained `maybeUnlockRenderDeployAfterRedo()`: once
  `render-deploy` has completed at least once (`renderDeployCompletedOnce`
  — never true during the wizard's first pass, so first-time visitors still
  must reach `render-deploy` via `uptime-pinger` as before), any frame
  whose dependents include `render-deploy` re-checks whether every real
  prerequisite (`RENDER_DEPLOY_PREREQS` — everything `bulk_push_render_env_
  vars` actually reads; deliberately excludes `uptime-pinger`) is done, and
  unlocks it directly if so. `completeFrame()`'s own `unlockFrame(next)`
  call is now also guarded on `next` actually being `"locked"` — otherwise
  a redo's positional "next frame" (which may be an untouched, already-
  `"done"` frame) would get wrongly reopened and reset to "Not started".
  `lockFrame("render-deploy")` additionally clears the `deployed`/
  `pending_deploy_id` flags from `render-service`'s own storage blob (the
  only place they live — "render-deploy" has no `STORAGE_KEYS` entry of its
  own), so a reload mid-redo shows the frame's initial pre-deploy state
  instead of resurrecting the previous deploy's live URL.
- **`unlockFrame()` now auto-opens the `<details>`, and `render-deploy`
  shows `"deploying…"` while a triggered deploy is in flight** (2026-09-02)
  — a newly-reachable frame previously became clickable but stayed
  visually collapsed, with no cue a new step was ready.
- **The DB-synced operational keys (cooldown/usage-cap/`REVIEW_DRAFT_PRS`)
  need no wizard-side push at all** (2026-09-02) — unlike the Render-env-var
  knobs above, the review engine's own first-boot seeding handles this on
  its side — no second service needs to open a connection to write into
  that database's schema from the outside (`ON CONFLICT (id) DO NOTHING`,
  so it never overwrites an operator's own value). This is what a freshly
  wizard-provisioned Supabase project gets on the sibling review-engine
  project's first boot. See `ISSUES.md`'s 2026-09-02 "push all optional env
  vars" entry for the reasoning and the ordering constraint that ruled out
  doing this from the wizard directly (the table doesn't exist until that
  first boot, which is after the wizard's bulk push already ran).
- **The created service's public URL is always derived from Render's
  returned `service.slug`, never the submitted `name`.** Render may
  normalize the name server-side; a create-service response was verified
  live to have no `service.url` field at all — trusting the requested
  name instead of the response's slug would silently point
  `onboarding.renderServiceUrl` (frame 5's forward contract) at a URL
  that doesn't exist.
- **`GITHUB_TARGET_REPO`, `GCP_PROJECT`, and `GCP_LOCATION` are
  deliberately never pushed** — track-all mode and this project's own
  matching defaults (the sibling review-engine project's own `gcp_location`
  default already equals `llm_client.py`'s fixed
  `_VERTEX_LOCATION` constant, verified) make an explicit push redundant.
  Do not add them without a concrete reason a default has drifted.
- **Deploy status polling keeps its own copy of Render's deploy-status
  buckets in `render_client.py`, matching the sibling review-engine
  project's equivalent sets by hand — no import between the two repos.**
  Keep the two in sync by hand if either changes; `router.py`'s
  `_LLM_ENV_VAR_NAMES` mapping is the same pattern, paired with the
  sibling project's own provider registry.
- **Frame 5 (UptimeRobot)'s "blocked, no Render URL" state is no longer
  reachable in normal sequential flow** — the "Render service" frame now
  writes `onboarding.renderServiceUrl` two frames before UptimeRobot
  unlocks. The blocked-state markup and its check function are
  unchanged and NOT dead code: they remain a correctness safeguard for a
  corrupted or manually-manipulated `sessionStorage` state, not something
  this sub-project needed or was asked to remove.
- **The GitHub App's webhook URL is a checked requirement, not something
  this wizard ever writes.** The instructions tell the visitor the real
  Render service URL (`<service_url>/webhook`) to type into GitHub's own
  form; `validate_app()` (see the sub-project 2 section above, updated
  2026-09-01) reads it back via `GET /app/hook/config` and reports a
  pass/fail line. There is no `PATCH /app/hook/config` call anywhere in
  this service — the earlier placeholder-then-PATCH flow, and later the
  manifest-flow's baked-in webhook URL, both predated the 2026-09-01 move
  to fully manual App creation; do not reintroduce a webhook-writing
  endpoint. A missing `service_url` still aborts validation up front
  (`err_github_no_render_service`) — unreachable in normal sequential flow
  (the Render-service frame completes two frames earlier), guarding the
  same corrupted/hand-edited `sessionStorage` case the UptimeRobot frame's
  blocked-state check exists for.
  **The stored record's `completed` flag (not `installation_id`'s mere
  presence) is what `restoreFromSession()` gates the frame's "done" state
  on** (2026-08-28 fix, see `ISSUES.md`) — `installation_id` is written
  before the push-and-clear step runs, so gating on it let a reload
  mid-push falsely mark the frame done. On a reload with `installation_id`
  set but `completed` still false, `restoreFromSession()` re-invokes
  `finishGithubAppSetup` itself rather than showing a dead end — same
  auto-resume shape as the Supabase branch beside it.

## What the "Dashboard login" frame (bounded addition, 2026-08-28) adds to these rules

- **This frame never writes a raw credential to `sessionStorage` at all** —
  a deliberate departure from every other frame's push-and-clear pattern
  (store the raw value, push it, then delete the field). The visitor must
  remember this username/password themselves (unlike a GitHub private key
  or Supabase's `db_pass`), so there is nothing useful left to persist once
  the push has been attempted; `onboarding.dashboardAuth` holds only
  `{completed: true}`.
- **`DASHBOARD_SESSION_SECRET` is generated entirely client-side**
  (`crypto.getRandomValues`, 32 random bytes, base64url) and never shown to
  the visitor — unlike the username/password, nothing downstream ever asks
  them to type it again.
- **A failed push here still follows the best-effort, non-gating
  convention** every other push-and-clear frame uses (see the "Render
  service" section above), even though the real consequence is worse: a
  missing `DASHBOARD_PASSWORD`/`DASHBOARD_SESSION_SECRET` fails the
  review engine's own boot guard, not just a feature. This was a deliberate
  choice for consistency over a one-off retry-until-verified gate on this
  single frame — "Finish & Deploy"'s own status poll surfaces a
  crash-looping deploy immediately, and "Change" lets the visitor redo this
  frame and re-push.

## LLM API testing hygiene (avoid Trust & Safety flags)

This project's `llm_client.py` makes real live calls to Gemini/Groq/Vertex
during credential validation, which carries the same Trust & Safety
abuse-flag risk documented elsewhere for LLM providers' free tiers.

**Rules to avoid triggering it:**

- **Never loop/burst live calls across many models or keys** to "see what
  sticks." One deliberate, single live call per real verification need.
- **Prefer mocked/cassette tests for exploration.** Reserve real network calls
  for the one live-verification step a build step actually requires — not
  for debugging or model-shopping.
- **If a provider starts returning 403/429, stop calling it immediately** and
  investigate via docs/support channels rather than retrying with different
  models/keys in quick succession — retrying does not help and each attempt
  is one more data point that can reinforce an abuse-pattern flag. This
  extends to OAuth/auth-layer failures too (e.g. `invalid_scope`,
  `RefreshError`) — same failure shape, same stop-and-diagnose principle,
  not a "try a different scope/key" situation.
- **The "one deliberate live call" limit is about generation/completion
  requests** — the ones that cost money and carry provider-abuse-flag risk.
  It does **not** apply to lightweight metadata/listing calls (e.g. checking
  whether a model ID exists in a provider's catalog). Checking several
  candidate values via a listing/existence endpoint in one pass is fine, and
  is the right way to narrow down configuration *before* making the one
  deliberate generation call — not a workaround for the rule above.
- This applies to **any** LLM provider's free tier, not just Gemini — Groq and
  future alternatives should get the same restraint.

## Plan-execution / multi-agent process hygiene

Lessons from running Superpowers-style plans through subagent-driven
development on this project (see `ISSUES.md` for the incidents these
generalize from):

- **A task brief's "stop and report" instruction is a hard stop, not a
  suggestion.** If an implementer hits an unpredicted failure a brief says to
  stop on, it must actually stop and return control — not self-resolve the
  problem and mention the deviation in its report afterward. A controller
  reviewing a report after the fact cannot approve or reject work that has
  already been done; by the time it reads "I deviated because...", the
  deviation has already happened.
- **When correcting or overriding part of a multi-sentence passage, re-read
  the whole passage afterward for internal consistency** — not just the
  clause that was changed. A targeted fix to one sentence is exactly the kind
  of edit that leaves a contradiction elsewhere in the same passage
  undetected by the person who made it.
- **Task-scoped review checks conformance to the brief, not correctness of
  the brief itself.** Code a plan hands an implementer verbatim — especially
  for external-API/auth integration (credential construction, OAuth scopes,
  client setup) — needs the same scrutiny as any other code. Matching the
  brief exactly does not mean the brief was right; a bug embedded in a plan's
  own provided snippet will sail through every task-scoped review that only
  checks "does this match what was asked." Flag this class of code for extra
  suspicion specifically at final/whole-branch review, and don't assume
  a whole-branch review that already had per-task reviews pass is redundant —
  it is often the first review that would even think to distrust the plan's
  own code.
- **Documentation describing the outcome of a live-verification step must be
  written after that step actually runs, not drafted in advance assuming
  success.** If a plan's task text describes what a doc should say about a
  pending live call's result, treat that text as a placeholder to revise
  based on the actual outcome, not as literal instructions to transcribe.
- **When a plan is authored in the same session that will execute it via a
  worktree-based flow, write or commit the plan file *inside* the worktree**
  (or commit it to the branch before creating the worktree). Writing a file
  to the main checkout and then branching off via `git worktree add` leaves
  that file invisible to the new worktree, since worktrees only materialize
  committed content.
- **Before merging a feature branch into any target branch, check the
  *target* branch for pre-existing uncommitted changes first** (`git status`
  there, not just on the branch being merged in) — a conflicting local edit
  or untracked file on the target can fail the merge in a way that's
  confusing to debug from the merge failure alone.
- **Don't ask an implementer subagent to reconfirm a full-suite baseline at
  the start of every task.** Trust the SDD ledger's last-recorded green
  state from the prior task's own final run instead. The shared
  `subagent-driven-development` skill's implementer template already asks
  for exactly one full-suite run, right before committing — a controller
  adding its own extra "first, confirm baseline" instruction on top of that
  is a habit this project fell into in earlier stages, not something the
  template requires. For a plan's first task, the worktree-setup step that
  precedes dispatch is normally what already confirms things are green, so
  there's usually no real gap to fill even there. Reason: measured directly
  during the 2026-08-19/20 test-suite-performance work — the doubling was
  never principled, and the case for it is weaker still now that the suite
  itself is faster (full suite 57s serial → 35s at `-n 4`; the `-m "not db"`
  fast-iteration subset 31s → 20s — see
  `docs/superpowers/specs/2026-08-19-test-suite-performance-design.md`
  section 8). Only add an explicit baseline-reconfirm instruction when
  there's a concrete reason to distrust the ledger for *this* task
  specifically — manual edits since the last confirmed-green run, a resumed
  session after a long gap, or a worktree/branch switch — not as a default
  precaution on every task.
- **Every parked/deferred Minor finding from a task-scoped or final
  whole-branch review must be logged in `ISSUES.md`'s Parked Issues section
  before the branch is considered done** — not left only in the SDD
  ledger (deleted once the branch merges) or in a session's own memory,
  either of which loses the finding the moment the workspace is cleaned up
  or the conversation ends. Log it there even when a review explicitly
  judges a finding "no action needed" / harmless-as-is — that judgment call
  belongs in the entry's **Why parked** line, not as a reason to skip
  logging it at all.
