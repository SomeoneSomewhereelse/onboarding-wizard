# Issues log

Running log of anything that went wrong (mine or a subagent's) while executing
this project's plans, so `CLAUDE.md` can be updated afterward to avoid
repeating the same mistake. One entry per issue: what happened, what it cost,
what should change.

Format:

```
## <short title>
- **When:** Task N, step/context
- **What happened:** ...
- **Cost:** (time lost / rework / none — just a near-miss)
- **Suggested CLAUDE.md change:** ...
```

**2026-09-05 pruning note:** a large number of fully-resolved, narrative
incident entries that predate this date were removed in a cleanup pass, per
the same convention the 2026-08-21 pre-flight-audit note at the bottom of
this file already established: once an incident is fully closed and its
lesson has either been folded into a `CLAUDE.md` file or is preserved by a
regression test/code comment/design doc, the blow-by-blow narrative is safe
to drop — `git log -p -- ISSUES.md` has the original text if the discovery
process is ever useful context again. What remains below is: (a) incidents
whose lesson was *not* fully folded elsewhere, or whose "Suggested CLAUDE.md
change" explicitly says it wasn't made yet; and (b) anything still genuinely
open/unresolved.

**This file's own history starts here.** This repo was split off from a monorepo shared with a sibling review-engine project (now at `~/pr-review-bot`, which kept the combined project's full `ISSUES.md` and git history). Every entry below was carried over because it's specific to this service (the onboarding wizard) — entries about the sibling project's own incidents, parked issues, or design gaps were left in that project's own file instead. `~/pr-review-bot/ISSUES.md` has the full combined history if older context is ever needed again.

---

## A requested security + code review of the whole onboarding wizard found a real SSRF vulnerability in the Vertex credential frame, plus 9 correctness bugs — all fixed in one pass

- **When:** 2026-08-28, user-requested "a set of reviews of the entire onboarding app" — a `security-review`-skill pass and a `code-review`-skill pass (high effort), run in parallel, independently of the task-scoped reviews that already passed each sub-project.
- **What happened:** The security review found a HIGH-severity SSRF in `llm_client.py::list_vertex_models` (sub-project 4): a visitor-supplied GCP service-account JSON's `token_uri`/`universe_domain` fields were passed unvalidated into `google.oauth2.service_account.Credentials.from_service_account_info()`, letting an unauthenticated visitor redirect this server's own outbound token-refresh request to an arbitrary host. Fixed by pinning both fields to Google's real values before credentials are ever constructed — see `CLAUDE.md`'s sub-project 4 section and the accompanying tests/regression coverage for the guard itself. The code review separately found and fixed 9 more correctness bugs across the GitHub App, Supabase, and UptimeRobot frames (stale-completion flags, missing generation tokens on poll loops, unpaginated dedupe scans, missing error states) — each fix has its own regression test; full blow-by-blow dropped here per this file's pruning convention (`git log -p -- ISSUES.md` has it).
- **Cost:** None net-negative — caught by a review the user asked for proactively, not by an exploit. But the near-miss is real: a real, shippable bug survived every task-scoped review for one sub-project and was only caught by a later, broader pass — the first such instance to be an actual security vulnerability rather than a correctness bug.
- **Suggested CLAUDE.md change:** Worth generalizing explicitly: **a credential-accepting endpoint that constructs an auth/HTTP client object from a visitor-supplied structured value (JSON, a config blob) needs a specific SSRF-focused check during its own design/review — does any field in that structure influence which host a server-side request is made to? — not just the "returns a verdict, never the credential" review this project already does well.** That specific class of gap (a "paste your service-account JSON" feature routing internal fields into a client library that reads them for connection-destination purposes) is exactly the shape a task-scoped review focused on credential *handling* (never logged, never echoed) can miss, because the vulnerable field isn't the credential itself — it's inert-looking routing metadata sitting right next to it in the same JSON blob. This generalized principle was never folded into `CLAUDE.md` as a standing rule — worth doing if a similar frame is ever added.

## GitHub's push protection flagged a Stripe-shaped string in git history before the first push — a known, intentional fake fixture value, not a real credential, but still worth a content-level scan going forward

- **When:** 2026-09-05, first `git push` of this newly-split repo to its own GitHub remote (`SomeoneSomewhereelse/onboarding-wizard`), immediately after the monorepo-to-standalone-repo restructure was merged to `main`.
- **What happened:** The restructure's baseline commit (created to bring this repo's ~305 untracked files under version control for the first time — see the restructure's own design/plan docs) included several old `bot`-project audit/findings documents (`docs/2026-08-05-first-hosted-run-findings.md`, `docs/2026-08-11-full-project-review-security-performance-quality.md`, `docs/superpowers/plans/2026-08-11-audit-fix-round.md`, `docs/superpowers/specs/2026-08-11-audit-fix-round-design.md`) whose prose quoted a Stripe-shaped placeholder string. **This was never a real, live Stripe credential.** The string originated from `bot/fixtures/bad_code/billing_report.py` — a deliberately planted, intentionally-bad fixture used to give `bot`'s own AI code-review "Security specialist" something obvious to catch during demos/tests (seeded via `scripts/seed_demo_pr.py`). A 2026-08-11 security review in `bot`'s own history had already flagged that the fixture's placeholder was shaped too realistically (risking exactly this GitHub scanner trip) and replaced it with an unambiguous value (`"FAKE-DEMO-KEY-fA6bC0dE4gH-DO-NOT-ROTATE"`) in the fixture code itself — but the *old prose documents describing that finding* still quoted the original Stripe-shaped placeholder, and those documents (not the fixture code, which was already fixed) are what got swept into this repo's baseline commit and tripped GitHub's push protection again.
- **Initial response, corrected:** Treated the flagged string as a real, live credential on first discovery (reasonable given GitHub's scanner had no way to know it was synthetic) and advised the user to rotate it. The user pointed out they'd never used the flagged service, which prompted checking the actual surrounding context in the (already-redacted) git history — at which point the fixture/demo-fixture origin became clear. **Correction:** nothing needs rotating; no real account or credential was ever involved. Lesson: before advising "treat this as compromised, rotate now," check what the flagged content actually *is* (read the surrounding context, which is safe once the exact value itself is structurally redacted) rather than reacting to the scanner's pattern match alone — a synthetic security-testing fixture that intentionally mimics a real credential's shape is a real, if narrow, class of false positive this project's own history had already produced once before.
- **Cost:** None — no real secret was ever involved, and the value never left this machine regardless. Some unnecessary work (a git-history rewrite, in hindsight not required) and a wrong initial rotate-the-key recommendation to the user, corrected once actual context was checked.
- **Fix:** Rewrote local git history with `git filter-repo --replace-text` (via `uv tool run git-filter-repo`, since the repo had never been pushed anywhere yet, making history rewrite safe/low-cost) using structural regex patterns for Stripe's known key-prefix shapes (`sk_live_`/`sk_test_`/`rk_live_`/`rk_test_`/`pk_live_`/`pk_test_`/`whsec_`) — the actual string was never read, viewed, or printed at any point during the fix itself. Force-pushed the rewritten history, then deleted the local backup tag and ran `git gc --prune=now --aggressive`. This was ultimately more thorough than strictly necessary once the fixture origin was confirmed, but harmless — the repo's history is clean either way.
- **Suggested CLAUDE.md change:** A bulk first-commit of a large pre-existing tree (bringing previously-untracked files under version control, or importing a directory from elsewhere) benefits from a content-level secret scan — not just a filename-based one — before that commit is created, not just before every push thereafter. A filename check (`.env`, `*.pem`, known service-account JSON names) only catches secrets that live in files whose *names* signal them; a credential-shaped string pasted inline into a prose document (an incident writeup, an audit finding, a demo fixture's own description) has no such signal. Separately: when a scanner (GitHub's push protection or otherwise) flags a credential-shaped string, check what it actually is — read the surrounding context once the value itself is safely handled — before asserting "treat as compromised, rotate now" to the user; a real deliberately-fake security-testing fixture is a known false-positive shape in this project's own history, not a hypothetical.
- **Follow-up (same day):** The user separately noted that `bot`/`dashboard`/`guide` content (including this fixture and the docs that quoted it) had no reason to exist in this repo's git history at all, even though the restructure had already removed it from the current tree in later commits. Re-ran `git filter-repo --invert-paths` (again via `uv tool run git-filter-repo`) with an explicit path list covering every `bot/`, `dashboard/`, `guide/` file, `mkdocs.yml`, the two dead `.claude/commands/*.md` slash commands, `tests/test_setup_command.py`, and all 81 bot-project-only spec/plan/handoff docs the restructure's own Task 5 had pruned from the tree — removing them from every commit, not just the tree at `HEAD`. This incidentally also fully removed the four docs this entry is about (rather than leaving a redacted placeholder in them), since their paths were on the same removal list. Verified zero remaining reachable paths under any of the removed prefixes via `git log --all --diff-filter=A --name-only`, full test suite (452 passed) and `ruff check .` unaffected (removed paths were already absent from the working tree), then force-pushed again and repeated the local backup-tag-delete + `git gc --prune=now --aggressive` cleanup. This repo's history now only ever shows onboarding-wizard content, matching the restructure's original intent that this be a genuinely standalone repo.

## A session-scoped Playwright sync-API fixture broke unrelated async tests in the same worker process

- **When:** 2026-09-06, implementing `docs/superpowers/plans/2026-09-06-onboarding-browser-tests.md` Task 1 (real browser-behavior test fixtures).
- **What happened:** Running the new browser test file together with `tests/test_onboarding_page.py` deterministically (not flaky) failed an unrelated async test with `RuntimeError: Runner.run() cannot be called from a running event loop`. Root cause, confirmed by direct repro before being treated as real: Playwright's sync API (`playwright.sync_api.sync_playwright()`) marks an event loop as "running" on the calling thread for as long as its context stays open — even with no browser launched yet. A session-scoped `browser` fixture held that context open for the whole test session, which broke every *other* `pytest-asyncio` async test that ran afterward in the same xdist worker process. The full suite happened to pass regardless (xdist's scheduling never put the affected test in the same worker as the browser test), which would have let this ship unnoticed if the plan's own verification step hadn't specifically run the two files together.
- **Cost:** None shipped — caught during the same implementation pass, before the commit. Some rework: the fixture, the spec (`docs/superpowers/specs/2026-09-06-onboarding-browser-tests-design.md` section 3), and the plan all needed a correction pass.
- **Fix:** Made `browser` function-scoped instead of session-scoped — Chromium is launched and the `sync_playwright()` context fully closed within each single test, so the "running loop" leak is transient and invisible to every other test. Verified by running the two affected files together three times in a row (not just the full suite once) to rule out scheduling-dependent flakiness.
- **Suggested CLAUDE.md change:** Worth a general note for any future Playwright-sync-API fixture in this project: **never make it session/module-scoped in a suite that also runs `pytest-asyncio` async tests** — the "running loop" side effect is scoped to however long the `sync_playwright()` context stays open, not to whether a browser is actually doing anything, and running the full suite is not sufficient to catch this (xdist's worker scheduling can hide it by accident). When verifying a fix like this, deliberately run the specific combination of files/tests suspected of interacting, not just the full suite.

## Parked Issues

Deliberately deferred quality nits from task and final-review passes — not
incidents ("something went wrong"), but known, low-severity gaps a
controller ruled were not worth a fix loop or fix-wave slot at the time.
Recorded here so they aren't silently lost. Format:

```
### <short title>
- **Found during:** stage/task, which review caught it
- **What:** the gap, in one or two sentences
- **Why parked:** why it didn't get fixed in-session
- **Follow-up:** what closing it would take
```

_Everything closed as of 2026-09-05 or earlier (Stage 3b's five items,
2026-08-21's four items, and "Repo-wide `ruff check .` is already red on
main" — confirmed clean again as of 2026-09-05) has been pruned from this
section; `git log -p -- ISSUES.md` has the original write-ups if useful
again. One implementation note worth keeping from the pruned batch, since
it's not obvious from the code alone: `sync_config_db()`'s
`_looks_like_local_test_db` guard also fires against `tests/conftest.py`'s
own `db` fixture (a real Postgres for tests, always `localhost`-shaped) — the
fix wasn't to weaken the guard, but to give the handful of tests that
deliberately need real Postgres
(`test_sync_config_db_writes_settings_values_into_runtime_config` and its
siblings) an explicit bypass fixture
(`tests/test_deploy_script.py::_real_db_target`) rather than have them
accidentally exercise the refusal path instead of the real one._

### render_client.py constructs a fresh httpx.AsyncClient per validate_key() call
- **Found during:** Task 2 review and final whole-branch review, `docs/superpowers/plans/2026-08-26-onboarding-wizard-render-frame.md`
- **What:** `validate_key()` opens a new `httpx.AsyncClient` context on every call instead of reusing/injecting one.
- **Why parked:** Correct and cheap at current call volume (one validation per visitor per wizard session); a shared client would need lifespan management that `main.py` deliberately doesn't have (this service has no app-level state).
- **Follow-up:** Revisit only if a future frame in this wizard starts making many calls to the same external API in a hot path.

### static/index.html: minor Render-key-frame UX gaps
- **Found during:** Task 4 review and final whole-branch review, `docs/superpowers/plans/2026-08-26-onboarding-wizard-render-frame.md`
- **Update (2026-09-05):** closed — all items fixed (Enter-key submit on `render-key-input`, empty-input test, and the "checking" status badge generalized across frames in the earlier 2026-08-27 fix wave). Covered by `test_validate_render_key_rejects_an_empty_key_client_side`/`test_render_key_input_submits_on_enter` in `tests/test_onboarding_page.py`.

### tests/test_onboarding_i18n.py: one RTL test asserts an exact whole-line literal string
- **Found during:** Final whole-branch review, `docs/superpowers/plans/2026-08-26-onboarding-wizard-render-frame.md`
- **What:** `test_language_switch_sets_dir_for_rtl` asserts a full literal source line rather than a more targeted substring, making it more brittle than necessary to a harmless refactor of that one line.
- **Why parked:** The reviewer's own assessment: the brittleness is doing real work here — it pins that the RTL direction is genuinely derived from the selected language, not just that `dir` is set to *something*. Not worth loosening.
- **Follow-up:** None planned; revisit only if that line needs a legitimate refactor and the test starts failing on unrelated changes.

### static/index.html: `code`, base-URL, and error-message minor gaps from sub-project 2 (GitHub App automation)
- **Found during:** Final whole-branch review, `docs/superpowers/plans/2026-08-26-onboarding-github-app-frame.md` (original manifest/install-redirect flow).
- **Update (2026-09-05):** closed as moot. The entire manifest/install-redirect code surface these 7 items concerned (`exchange_manifest_code`, `verify_installation`, `handleGithubManifestCallback`, `GITHUB_MANIFEST_STATE_KEY`, both endpoints) no longer exists — the 2026-09-01 fully-manual App-creation redesign (see `CLAUDE.md`'s sub-project 2 section) replaced it entirely. Nothing to fix; full original write-up in `git log -p -- ISSUES.md` if useful again.

### render_client.py and router.py: no server-side structural logging
- **Found during:** Final whole-branch review, `docs/superpowers/plans/2026-08-26-onboarding-wizard-render-frame.md` — validation failures logged nothing, undebuggable in production.
- **Update (2026-09-05, parked-issues fix wave):** closed, now that this service is actually deployed. `render_client.py::validate_key` logs outcome-only structural lines (`"render key validation: valid"` / `"invalid (<status>)"` / `"render_unreachable (<status or reason>)"`) via `logging.getLogger(__name__)` — never the key value.

### static/index.html: minor UX/robustness gaps from sub-project 3 (Supabase provisioning)
- **Found during:** Task 6/7 review and final whole-branch review, `docs/superpowers/plans/2026-08-26-onboarding-supabase-provisioning-frame.md` — `generateDbPassword()`'s modulo bias and missing try/catch, plus no disable-while-in-flight guard on the "Check again" button.
- **Update (2026-09-05):** closed, re-verified against the current code. `generateDbPassword()` no longer exists client-side (db_pass generation moved server-side in the 2026-09-01 session redesign, mooting the first two items). The in-flight-guard item is fixed: `checkSupabaseStatusOnce()` disables `supabase-check-status-submit` for the duration of its check, covered by `test_supabase_check_again_button_disables_itself_while_in_flight`.

### router.py: four Supabase request models repeat access_token's Field constraint verbatim
- **Found during:** Task 5 review, `docs/superpowers/plans/2026-08-26-onboarding-supabase-provisioning-frame.md`.
- **Update (2026-09-05):** closed as moot — the 2026-09-01 server-side-session redesign removed three of the four models entirely (credentials now come from the session, not the request body); only one Supabase credential model remains, so there's no duplication left to consolidate.

### tests/test_onboarding_page.py: one Supabase restore-from-session test only checks substrings, not structural nesting
- **Found during:** Task 7 review, `docs/superpowers/plans/2026-08-26-onboarding-supabase-provisioning-frame.md`
- **What:** `test_restore_from_session_resumes_polling_for_a_ref_without_a_connection_string` only asserts that `showSupabaseProvisioning()`, `pollUntilReady(Date.now())`, and `function restoreFromSession` each appear somewhere in the served page — it doesn't confirm they're inside the same `else if` branch. The implementation itself was independently verified correct by direct code reading during task review; the test is just a weaker regression guard than its name implies.
- **Why parked:** This test file is a content-substring harness by design (matching this repo's `tests/test_dashboard_page.py` convention), not a JS execution environment — a more structural assertion isn't cheaply available without changing that convention project-wide.
- **Follow-up:** None planned; revisit only if a real regression here ever slips through undetected, which would be the concrete signal that a substring check is no longer enough for this file.

### Spec section 6 (onboarding-uptimerobot-frame-design.md) described a browser-behavior test this project's suite cannot execute
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-08-27-onboarding-uptimerobot-frame.md` (sub-project 5).
- **What:** The spec asked for a test where "mocked `sessionStorage` without [the Render-URL] key renders the blocked message, no form" — this project's onboarding page tests are all static-HTML-source-substring assertions (`tests/test_onboarding_page.py`'s established convention, since there is no JS test runner anywhere in this project — no `package.json`, no jsdom/playwright/selenium). The implementer correctly substituted a static-source check for the blocked-state markup/logic's *presence*, matching every prior frame's convention, but this means the blocked-state *behavior* has zero executable coverage — only its source text does.
- **Why parked:** Not a defect in any implementation — the gap is in how the spec was written, describing a test shape the project's suite structurally cannot run.
- **Follow-up:** Either add a lightweight JS test runner to this project (a real architecture decision, its own brainstorm), or have future specs stop describing browser-behavior tests in this style.

### static/index.html: minor UX/robustness gaps from sub-project 4 (LLM provider credential UI)
- **Found during:** Final whole-branch review and its fix-wave re-review, `docs/superpowers/plans/2026-08-27-onboarding-llm-provider-frame.md`
- **What:** Two small items remain, both confirmed genuinely low-value to fix:
  1. `base64ToJsonSanityCheck` is a synchronous function but is called with `await` — harmless (an extra microtask tick), matches the brief's own snippet verbatim. Not worth touching.
  2. `atob()` on a service-account JSON containing non-ASCII bytes would mis-decode and reject client-side a file the server's `json.loads` would accept fine (UTF-8) — vanishingly rare for GCP-issued keys.
- **Why parked:** Both deliberately not worth fixing (see each item's own reasoning above) — the other three items in this entry's original bundle (the badge not resetting after a later successful retry; the raw internal provider id shown instead of its localized label; the missing throwaway-key comment in `tests/test_onboarding_llm_client.py`) were fixed in the 2026-08-27 parked-minors fix wave.
- **Follow-up:** None planned for either remaining item; revisit only if either ever causes a real, reported problem.

### Repo-wide stale-path sweep: leftover `onboarding/`-prefixed paths and old-layout framing
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md` — several files still referenced the pre-flatten layout (`onboarding/`-prefixed paths, `bot/`/`dashboard/` bare-path citations of the sibling repo, "root `CLAUDE.md`" phrasing).
- **Update (2026-09-05, parked-issues fix wave):** closed. Every stale reference across root `*.py`, `tests/*.py`, `static/index.html`, `CLAUDE.md`, and `README.md` fixed to the current flat layout (deliberately excluding `docs/superpowers/**` and `ISSUES.md`'s own historical entries). `render_client.py`'s `"./bot/Dockerfile"` line — the *separately provisioned bot repo's* own path, not a stale self-reference — confirmed correct and left untouched. Full suite (452 passed), `ruff check .` clean, Docker build + boot re-verified.

### `.gitignore` has several now-dead entries from the pre-flatten layout
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md`
- **What:** `site/` (MkDocs build output — no docs site in this repo), `bot/fixtures/demo_bulk_bad_code/` and `bot/scripts/seed_bulk_demo_pr.py` (paths under the deleted `bot/`), and `queue.db*` (the bot's SQLite queue, not used by this service) are all dead ignore patterns nobody owns any more.
- **Why parked:** Low-risk — dead ignore patterns are harmless — and no restructure task owned `.gitignore`'s full content.
- **Follow-up:** Remove the four dead entries whenever `.gitignore` is next touched for an unrelated reason.
- **Update (2026-09-05, parked-issues fix wave):** closed. Removed all four dead entries plus their section comments; also removed a dangling comment stub (the old `brief.md` section header, whose pattern line was already removed in the restructure's Task 7 but whose two-line comment was accidentally left behind) found in the same file while fixing this.

### `pyproject.toml` dev-dependency group lost its `cryptography` rationale comment
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md` — restructure dropped the comment explaining `cryptography>=44.0`'s dev-dependency rationale.
- **Update (2026-09-05):** closed — comment re-added.

### Root `__init__.py` (0 bytes) makes the flat repo layout look like a package
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md`.
- **Update (2026-09-05):** closed — confirmed nothing referenced it, removed.

### `CLAUDE.md`'s "LLM API testing hygiene" section interrupts the numbered sub-project sections, and its lead-in lost its antecedent
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md`.
- **Update (2026-09-05):** closed — moved out of the numbered sub-project sequence, lead-in rewritten with a clear antecedent.

### `config.py`'s encryption-key field comment references a removed `supabase_oauth_client_id` field
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md` — pre-existing staleness from the 2026-09-04 Supabase PAT redesign, unrelated to the restructure itself.
- **Update (2026-09-05):** closed — comment now describes the reasoning generically instead of naming a removed field.

### Deleted spec/plan filenames are still cross-referenced from the specs/plans kept in this repo
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md` — 79 deleted spec/plan filenames still cross-referenced, with no pointer to the sibling `~/pr-review-bot` repo's history outside `ISSUES.md`'s own intro.
- **Update (2026-09-05):** closed — pointer sentence added to README's "Related project" section.

### README.md's local-dev section doesn't mention Postgres/Docker is required to run the full test suite
- **Found during:** Writing the implementation plan for `docs/superpowers/specs/2026-09-06-onboarding-browser-tests-design.md` — caught before any plan code was written, not a review of shipped code.
- **What:** The new `live_app_url` browser-test fixture depends on the existing `db_url` fixture purely so `main.py`'s `lifespan` can boot (it eagerly opens a real Postgres connection and raises `RuntimeError` otherwise — see the spec's section 2 correction). This was already true for every `db`-marked test (via `DATABASE_URL` or a local testcontainers/Docker fallback), but was easy to miss since only a subset of the suite needed it; the new `browser`-marked tests make a locally-available Postgres (real or Docker-backed) load-bearing for a second, independent slice of the suite. `README.md`'s "Local development" section currently only documents `uv sync` + `.env` + `uv run pytest -v`, with no mention of Docker/Postgres being required at all for a `DATABASE_URL`-less local run.
- **Why parked:** Noted while writing the plan, not fixed in the same pass — the plan itself doesn't touch README's dev-setup prose beyond the one-line Playwright-install addition the spec already calls for.
- **Follow-up:** Add a sentence to README's "Local development" section noting that running the full suite locally without a `DATABASE_URL` set requires Docker (for testcontainers' throwaway Postgres) — both for `db`-marked tests (pre-existing) and now `browser`-marked tests (new).

---

## Design Gaps

Proactive findings, not incidents — nothing here actually happened. Format:

```
### <short title>
- **Found during:** audit context
- **What:** the gap, with file:line evidence
- **Why it matters:** production impact if left as-is
- **Status:** open | decided-non-issue | needs-verification
- **Follow-up:** what closing it (or verifying it) would take
```
