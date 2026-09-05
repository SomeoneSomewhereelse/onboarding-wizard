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

- **When:** 2026-08-28, user-requested "a set of reviews of the entire onboarding app" — a `security-review`-skill pass (diffed against `origin/main`, i.e. the wizard's whole build) and a `code-review`-skill pass (`onboarding/`, high effort), run in parallel, independently of the task-scoped reviews that already passed each sub-project.
- **What happened:** The security review found a HIGH-severity SSRF in `onboarding/llm_client.py::list_vertex_models` (sub-project 4, shipped and merged 2026-08-27): the endpoint accepts a visitor-supplied GCP service-account JSON with no validation beyond shape, and passes it straight into `google.oauth2.service_account.Credentials.from_service_account_info()`, which reads `token_uri` (required) and `universe_domain` (optional) verbatim out of that dict and uses them as the destination of the OAuth2 token-refresh request it issues later. Since the visitor also supplies the matching private key (self-generated, so they can sign a valid assertion), an unpinned `token_uri` let an unauthenticated visitor make **this server** issue an outbound POST to an arbitrary host — internal network probing, or using the wizard as a request-oracle via the differing `unauthorized`/`provider_unreachable` responses. Independently re-verified against the installed `google-auth` source (traced the exact refresh code path) before being treated as real, per this project's finding-verification discipline. Fixed by rejecting any `token_uri`/`universe_domain` that doesn't match Google's real values, before credentials are ever constructed — tests assert the guard trips before `from_service_account_info` is even reached. The same review pass separately caught (and fixed) that Vertex's credential refresh was blocking the process's single event loop for every other concurrent visitor, since it's synchronous under the hood — fixed by proactively refreshing off-thread via `asyncio.to_thread`, mirroring `github_client.py`'s existing pattern for its own blocking PyGithub calls.
  The code review separately found 9 more correctness bugs, all fixed: a GitHub-App-frame reload could falsely mark the frame "done" after a failed webhook-set (now gated on an explicit `completed` flag, matching the Supabase frame's own pattern, with an auto-resume path instead of a silent false-complete); the Render-deploy and Supabase provisioning poll loops had no guard against a stale `setTimeout` callback overwriting a freshly-reset frame's state after a mid-poll "Change" (both loops, plus their one-shot "check again" counterparts, now carry a generation token bumped on every reset); a Supabase OAuth callback could throw on a corrupted `sessionStorage` value with no visible error (wrapped in try/catch, matching every sibling reader in the file); the UptimeRobot dedupe-before-create scan only checked the first page of monitors (now paginates via the v3 API's `nextLink`, verified against the published OpenAPI spec rather than guessed); a webhook-retry button had no double-submit guard (added, matching the project's established convention); a malformed `installation_id` GitHub callback param produced the wrong error message via a silent `NaN` (now validated); a visitor with zero Supabase organizations hit a blank picker instead of a clear error (now a dedicated terminal state + new `err_supabase_no_organizations` string, both languages); and changing the render-key or render-service frame after UptimeRobot already created a monitor orphaned it silently (now cleaned up best-effort via a new `DELETE /monitors/{id}`-backed relay endpoint, verified against UptimeRobot's own published OpenAPI spec for the id field's shape and location before being implemented). One flagged item (a claim that a real Supabase project ref could contain a digit, defeating the router's `^[a-z]{20}$` validator) was checked against Supabase CLI's own upstream source (`ProjectRefPattern = regexp.MustCompile(`^[a-z]{20}$`)`) and confirmed a **false positive** — the existing code was already correct; left untouched rather than "fixed."
- **Cost:** None net-negative — caught by a review the user asked for proactively, not by an exploit. But the near-miss is real: this is not the first instance in this project of a real, shippable bug surviving every task-scoped review for one sub-project and only being caught by a later, broader pass (see "The final whole-branch review caught a real bug that all six task-scoped reviews missed" above) — and the first such instance to be an actual security vulnerability rather than a correctness bug. Every external-API-shape assumption made while fixing the correctness bugs (UptimeRobot's create/list/delete response shapes, its pagination field) was verified against UptimeRobot's own published OpenAPI spec before being written into code, not guessed — consistent with `[[feedback-verify-live-api-struct-before-plan]]`, extended here to "verify via published docs," not just "verify via a live call," when a live call isn't available/appropriate.
- **Suggested CLAUDE.md change:** Worth generalizing explicitly: **a credential-accepting endpoint that constructs an auth/HTTP client object from a visitor-supplied structured value (JSON, a config blob) needs a specific SSRF-focused check during its own design/review — does any field in that structure influence which host a server-side request is made to? — not just the "returns a verdict, never the credential" review this project already does well.** That specific class of gap (a "paste your service-account JSON" feature routing internal fields into a client library that reads them for connection-destination purposes) is exactly the shape a task-scoped review focused on credential *handling* (never logged, never echoed) can miss, because the vulnerable field isn't the credential itself — it's inert-looking routing metadata sitting right next to it in the same JSON blob.

## GitHub's push protection flagged a Stripe-shaped string in git history before the first push — a known, intentional fake fixture value, not a real credential, but still worth a content-level scan going forward

- **When:** 2026-09-05, first `git push` of this newly-split repo to its own GitHub remote (`SomeoneSomewhereelse/onboarding-wizard`), immediately after the monorepo-to-standalone-repo restructure was merged to `main`.
- **What happened:** The restructure's baseline commit (created to bring this repo's ~305 untracked files under version control for the first time — see the restructure's own design/plan docs) included several old `bot`-project audit/findings documents (`docs/2026-08-05-first-hosted-run-findings.md`, `docs/2026-08-11-full-project-review-security-performance-quality.md`, `docs/superpowers/plans/2026-08-11-audit-fix-round.md`, `docs/superpowers/specs/2026-08-11-audit-fix-round-design.md`) whose prose quoted a Stripe-shaped placeholder string. **This was never a real, live Stripe credential.** The string originated from `bot/fixtures/bad_code/billing_report.py` — a deliberately planted, intentionally-bad fixture used to give `bot`'s own AI code-review "Security specialist" something obvious to catch during demos/tests (seeded via `scripts/seed_demo_pr.py`). A 2026-08-11 security review in `bot`'s own history had already flagged that the fixture's placeholder was shaped too realistically (risking exactly this GitHub scanner trip) and replaced it with an unambiguous value (`"FAKE-DEMO-KEY-fA6bC0dE4gH-DO-NOT-ROTATE"`) in the fixture code itself — but the *old prose documents describing that finding* still quoted the original Stripe-shaped placeholder, and those documents (not the fixture code, which was already fixed) are what got swept into this repo's baseline commit and tripped GitHub's push protection again.
- **Initial response, corrected:** Treated the flagged string as a real, live credential on first discovery (reasonable given GitHub's scanner had no way to know it was synthetic) and advised the user to rotate it. The user pointed out they'd never used the flagged service, which prompted checking the actual surrounding context in the (already-redacted) git history — at which point the fixture/demo-fixture origin became clear. **Correction:** nothing needs rotating; no real account or credential was ever involved. Lesson: before advising "treat this as compromised, rotate now," check what the flagged content actually *is* (read the surrounding context, which is safe once the exact value itself is structurally redacted) rather than reacting to the scanner's pattern match alone — a synthetic security-testing fixture that intentionally mimics a real credential's shape is a real, if narrow, class of false positive this project's own history had already produced once before.
- **Cost:** None — no real secret was ever involved, and the value never left this machine regardless. Some unnecessary work (a git-history rewrite, in hindsight not required) and a wrong initial rotate-the-key recommendation to the user, corrected once actual context was checked.
- **Fix:** Rewrote local git history with `git filter-repo --replace-text` (via `uv tool run git-filter-repo`, since the repo had never been pushed anywhere yet, making history rewrite safe/low-cost) using structural regex patterns for Stripe's known key-prefix shapes (`sk_live_`/`sk_test_`/`rk_live_`/`rk_test_`/`pk_live_`/`pk_test_`/`whsec_`) — the actual string was never read, viewed, or printed at any point during the fix itself. Force-pushed the rewritten history, then deleted the local backup tag and ran `git gc --prune=now --aggressive`. This was ultimately more thorough than strictly necessary once the fixture origin was confirmed, but harmless — the repo's history is clean either way.
- **Suggested CLAUDE.md change:** A bulk first-commit of a large pre-existing tree (bringing previously-untracked files under version control, or importing a directory from elsewhere) benefits from a content-level secret scan — not just a filename-based one — before that commit is created, not just before every push thereafter. A filename check (`.env`, `*.pem`, known service-account JSON names) only catches secrets that live in files whose *names* signal them; a credential-shaped string pasted inline into a prose document (an incident writeup, an audit finding, a demo fixture's own description) has no such signal. Separately: when a scanner (GitHub's push protection or otherwise) flags a credential-shaped string, check what it actually is — read the surrounding context once the value itself is safely handled — before asserting "treat as compromised, rotate now" to the user; a real deliberately-fake security-testing fixture is a known false-positive shape in this project's own history, not a hypothetical.
- **Follow-up (same day):** The user separately noted that `bot`/`dashboard`/`guide` content (including this fixture and the docs that quoted it) had no reason to exist in this repo's git history at all, even though the restructure had already removed it from the current tree in later commits. Re-ran `git filter-repo --invert-paths` (again via `uv tool run git-filter-repo`) with an explicit path list covering every `bot/`, `dashboard/`, `guide/` file, `mkdocs.yml`, the two dead `.claude/commands/*.md` slash commands, `tests/test_setup_command.py`, and all 81 bot-project-only spec/plan/handoff docs the restructure's own Task 5 had pruned from the tree — removing them from every commit, not just the tree at `HEAD`. This incidentally also fully removed the four docs this entry is about (rather than leaving a redacted placeholder in them), since their paths were on the same removal list. Verified zero remaining reachable paths under any of the removed prefixes via `git log --all --diff-filter=A --name-only`, full test suite (452 passed) and `ruff check .` unaffected (removed paths were already absent from the working tree), then force-pushed again and repeated the local backup-tag-delete + `git gc --prune=now --aggressive` cleanup. This repo's history now only ever shows onboarding-wizard content, matching the restructure's original intent that this be a genuinely standalone repo.

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
- **What:** No dedicated test for the empty-input validation path (the code handles it correctly). No Enter-key submit binding on the password input — only the button's click listener triggers validation, so an on-screen mobile keyboard's "Go" button does nothing.
- **Why parked:** Cosmetic/UX polish, no functional or security impact.
- **Follow-up:** Bind `keydown` → Enter on the password input to call `validateRenderKey()`; add the empty-input test.
- **Update (2026-08-27, parked-minors fix wave):** the third original sub-item here (the self-contradictory "Not started — checking…" label) is closed — `setFrameStatus(id, "ready", "checking")` was generalized to a dedicated `"checking"` status with its own `badge_checking` STRINGS key, applied to every frame that had the same composed-label shape (render-key, render-service, uptime-pinger), not just this one. The two items above are still open.
- **Update (2026-09-05):** closed — `render-key-input` now has a `keydown` listener that submits on Enter (mirroring every other frame's click-to-submit UX for a mobile keyboard's "Go" key), and `test_validate_render_key_rejects_an_empty_key_client_side`/`test_render_key_input_submits_on_enter` cover both remaining gaps in `tests/test_onboarding_page.py`.

### tests/test_onboarding_i18n.py: one RTL test asserts an exact whole-line literal string
- **Found during:** Final whole-branch review, `docs/superpowers/plans/2026-08-26-onboarding-wizard-render-frame.md`
- **What:** `test_language_switch_sets_dir_for_rtl` asserts a full literal source line rather than a more targeted substring, making it more brittle than necessary to a harmless refactor of that one line.
- **Why parked:** The reviewer's own assessment: the brittleness is doing real work here — it pins that the RTL direction is genuinely derived from the selected language, not just that `dir` is set to *something*. Not worth loosening.
- **Follow-up:** None planned; revisit only if that line needs a legitimate refactor and the test starts failing on unrelated changes.

### static/index.html: `code`, base-URL, and error-message minor gaps from sub-project 2 (GitHub App automation)
- **Found during:** Final whole-branch review and its fix-wave re-review, `docs/superpowers/plans/2026-08-26-onboarding-github-app-frame.md`
- **What:** Six small items, all confirmed low-risk and left as-is:
  1. `github_client.py::exchange_manifest_code`'s `code` parameter is interpolated unescaped into the GitHub API request path — bounded by `Field(max_length=128)` on the router's request model, no credential attached to the request, and a host-escape was verified impossible (stays rooted at `/app-manifests/`). `scripts/create_github_app.py` has the identical shape.
  2. `verify_installation`'s `except (ValueError, jwt.exceptions.InvalidKeyError)` wraps the entire `asyncio.to_thread(_fetch_installation, ...)` call rather than just the JWT-signing step, so a hypothetical malformed-JSON `ValueError` from PyGithub's own response parsing would be miscategorized as `invalid_credentials` instead of `github_unreachable` — but PyGithub's `__structuredFromJson` already catches that internally rather than propagating it, so the path is largely unreachable in practice.
  3. No test exercises `verify_installation`'s `requests.exceptions.RequestException` branch (a real coverage gap, just low value relative to what the fix wave prioritized).
  4. `handleGithubManifestCallback`'s two distinct failure branches (bad HTTP status vs. a JSON-parse failure) both surface as the same `err_github_unreachable` message — imprecise, not incorrect.
  5. The phase-2 install redirect's CSRF token reuses phase 1's `GITHUB_MANIFEST_STATE_KEY` sessionStorage constant name — functionally correct (the two round trips are strictly sequential and `sessionStorage` is per-tab), just a misleading name now that it's shared.
  6. Neither `/api/github/exchange-manifest-code` nor `/api/github/verify-installation` sets `Cache-Control: no-store`, despite carrying/returning a private key in the response body — low practical risk (POST responses aren't cached by browsers/proxies absent unusual config) but standard hardening for this class of endpoint.
  7. `parseInt(installationId, 10)` on the install-callback query param can yield `NaN` on a malformed value, which then reports as the (wrong) `err_github_unreachable` message instead of something more specific — not reachable under normal GitHub-redirect operation.
- **Why parked:** All seven confirmed low-severity by both the final reviewer and its fix-wave re-review; the fix wave was scoped to the 6 Important findings plus 2 cheap/high-value deferred items (config validation, undeclared dependencies) rather than every Minor on the list.
- **Follow-up:** Each is independently fixable in isolation whenever one of these endpoints gets touched again; none block anything else in the wizard's remaining sub-projects.
- **Note (2026-09-05):** most of this frame's original interactive install/create flow was subsequently removed entirely for an unrelated reason (repeated GitHub account suspensions during live testing — see `CLAUDE.md`'s sub-project 2 section for the current, fully-manual design). Items 1, 4, 5, 6, 7 above concern the manifest/install redirect code paths that design replaced; left here rather than re-verified against the current file, since none were ever fixed and the replacement may have mooted some of them.
- **Update (2026-09-05):** closed as moot, re-verified against the current code. `exchange_manifest_code`, `verify_installation`, `handleGithubManifestCallback`, `GITHUB_MANIFEST_STATE_KEY`, `/api/github/exchange-manifest-code`, and `/api/github/verify-installation` no longer exist anywhere in `github_client.py`/`router.py`/`static/index.html` — the fully-manual redesign (`validate_app()`, no manifest, no install redirect) replaced the entire code surface every one of these 7 items was about. Nothing to fix.

### render_client.py and router.py: no server-side structural logging
- **Found during:** Final whole-branch review, `docs/superpowers/plans/2026-08-26-onboarding-wizard-render-frame.md`
- **What:** The design spec (section 5) anticipated a structural log line on validation failure (e.g. `"render key validation: invalid (401)"`, name/outcome only, never the value). The implementation logs nothing at all — safe, but means a production report of "validation keeps failing" is currently undebuggable (can't distinguish a wave of `invalid_key` submissions from a genuine Render outage).
- **Why parked:** Zero logging is the stricter, safer default, and this project has a documented history of secret-handling incidents (see the entries above this one) — adding logging under the time pressure of a single fix wave felt like the wrong moment to touch this area.
- **Follow-up:** Add the structural log line the spec already specifies (status code / outcome enum only, never the key) once this service is closer to being actually deployed.

### static/index.html: minor UX/robustness gaps from sub-project 3 (Supabase provisioning)
- **Found during:** Task 6 review, Task 7 review, and the final whole-branch review + its fix-wave re-review, `docs/superpowers/plans/2026-08-26-onboarding-supabase-provisioning-frame.md`
- **What:** Three small items remain, all confirmed low-risk:
  1. `generateDbPassword()`'s `charset[byte % charset.length]` has a small modulo bias (8 of 62 characters ~1.6x more likely than the other 54) — doesn't threaten the alphanumeric-only requirement, and 32 bytes is far more entropy than a database password needs regardless. Not worth fixing.
  2. `generateDbPassword()` itself isn't wrapped in try/catch — much lower risk than the `crypto.subtle` call fixed elsewhere in this file, since `crypto.getRandomValues` essentially never throws for a 32-byte array.
  3. The "Check again" button (`supabase-check-status-submit`) isn't disabled while its own check is in flight — a double-click can issue two concurrent status checks. Lower stakes than the credential-submit buttons already fixed (parked-minors fix wave, 2026-08-27), since this only re-checks status, it doesn't submit a credential or create a resource.
- **Why parked:** All three low-severity; a separate cleanup fixed everything else in this bundle (the wrong crypto/storage error message in `connectSupabase()`, the two previously-unguarded `sessionStorage.setItem` call sites in `kickOffProjectCreation`/`fetchSupabaseConnectionInfo`, plus a fourth in `callSupabaseRelay`'s token-refresh path) — see the 2026-08-27 parked-minors fix wave commits.
- **Follow-up:** Wrap `generateDbPassword()`'s body in try/catch for consistency, even though it essentially never throws; disable `supabase-check-status-submit` for the duration of its own in-flight check, matching the pattern every credential-submit button now has.
- **Note (2026-09-05):** the Supabase frame's own connection method (OAuth vs. visitor-pasted PAT) and its session-storage/relay architecture were both replaced since this was written — see the Design Gaps section below and `docs/superpowers/specs/2026-09-04-supabase-pat-frame-design.md`, `docs/superpowers/specs/2026-09-01-onboarding-server-side-session-design.md`. Re-verify these three items still apply to the current `static/index.html` before spending time on any of them.
- **Update (2026-09-05):** re-verified. Items 1 and 2 are moot — `generateDbPassword()` no longer exists client-side at all; `db_pass` generation moved server-side to `router.py` (`secrets.token_urlsafe(24)`, part of the 2026-09-01 server-side-session redesign), which has neither the modulo bias nor any realistic exception path. Item 3 is fixed: `checkSupabaseStatusOnce()` now disables `supabase-check-status-submit` for the duration of its own in-flight check and re-enables it only on a timeout, mirroring `checkRenderDeployStatusOnce()`'s identical pattern exactly; covered by `test_supabase_check_again_button_disables_itself_while_in_flight`.

### router.py: four Supabase request models repeat access_token's Field constraint verbatim
- **Found during:** Task 5 review, `docs/superpowers/plans/2026-08-26-onboarding-supabase-provisioning-frame.md`
- **What:** `SupabaseListOrgsRequest`, `SupabaseCreateProjectRequest`, `SupabaseProjectStatusRequest`, and `SupabaseConnectionInfoRequest` each declare `access_token: str = Field(max_length=4096)` independently rather than sharing a base model.
- **Why parked:** Matches this file's existing style — `RenderKeyRequest`/`GithubManifestCodeRequest` don't share a base model either, and four repetitions of one field isn't yet enough duplication to justify introducing one.
- **Follow-up:** Revisit only if a future sub-project adds enough additional `access_token`-bearing request models that the duplication becomes harder to keep in sync by hand.
- **Update (2026-09-05):** closed as moot. The 2026-09-01 server-side-session redesign means `create-project`/`project-status`/`connection-info` now read the credential from the session (`session_store.read_frame`), never from the request body — `SupabaseListOrgsRequest`, `SupabaseProjectStatusRequest`, and `SupabaseConnectionInfoRequest` don't exist anymore. Only one Supabase credential model remains (`SupabaseKeyRequest.key`), so there's no duplication left to consolidate.

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
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md`
- **What:** `CLAUDE.md` retains several `onboarding/`-prefixed path references left over from the pre-flatten layout; several source test-file docstrings still say `onboarding/config.py`/`bot/main.py`/`dashboard/static/dashboard.html`/etc.; `main.py`'s own module docstring still frames this as "a separate service from the review engine in bot/"; and a few files still say "same standard as root `CLAUDE.md`" even though this file's content now lives in the merged root `CLAUDE.md` and no longer needs the word "root" to disambiguate from anything. Explicitly excluded from this sweep: `render_client.py`'s `"envSpecificDetails": {"dockerfilePath": "./bot/Dockerfile"}` line — that string is the path on the *separately provisioned bot repo* this wizard deploys, not a stale reference to this repo's own now-deleted `bot/` directory; it is correct as written and must not be touched.
- **Why parked:** Out of scope for any single restructure task; needs a dedicated repo-wide sweep rather than a scattered set of one-off edits.
- **Follow-up:** A dedicated pass grepping for `onboarding/`, `bot/`, `dashboard/` path references and "root CLAUDE.md" phrasing across the repo, fixing each to the current flat layout, explicitly skipping the `render_client.py` line noted above.

### `.gitignore` has several now-dead entries from the pre-flatten layout
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md`
- **What:** `site/` (MkDocs build output — no docs site in this repo), `bot/fixtures/demo_bulk_bad_code/` and `bot/scripts/seed_bulk_demo_pr.py` (paths under the deleted `bot/`), and `queue.db*` (the bot's SQLite queue, not used by this service) are all dead ignore patterns nobody owns any more.
- **Why parked:** Low-risk — dead ignore patterns are harmless — and no restructure task owned `.gitignore`'s full content.
- **Follow-up:** Remove the four dead entries whenever `.gitignore` is next touched for an unrelated reason.

### `pyproject.toml` dev-dependency group lost its `cryptography` rationale comment
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md`
- **What:** The dev-dependency group previously explained, via a comment, that `cryptography>=44.0` is imported directly by `tests/test_onboarding_github_client.py` to build a real RSA key. That comment was lost during the restructure; the dependency itself is still correctly declared.
- **Why parked:** Cosmetic — the dependency is present and correct, just missing its explanatory comment.
- **Follow-up:** Re-add the one-line rationale comment whenever someone's next in that file.

### Root `__init__.py` (0 bytes) makes the flat repo layout look like a package
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md`
- **What:** An empty `__init__.py` sits at the repo root, but in a flat top-level-modules layout nothing actually imports the repo root as a package.
- **Why parked:** Harmless as-is — the restructure design doc's own file list included moving it here — not worth churn without a concrete reason to remove it.
- **Follow-up:** Remove only if/when something concrete depends on the repo root *not* being package-like, or as part of an unrelated cleanup pass.

### `CLAUDE.md`'s "LLM API testing hygiene" section interrupts the numbered sub-project sections, and its lead-in lost its antecedent
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md`
- **What:** The "LLM API testing hygiene" section sits between two numbered sub-project sections, breaking their numbering, and its "**Rules to avoid repeating this:**" lead-in lost its antecedent when the narrative paragraph above it was trimmed to one sentence during the merge into the flat `CLAUDE.md`.
- **Why parked:** Cosmetic placement/flow issue, not a correctness problem.
- **Follow-up:** Move the section out of the numbered sub-project sequence (or renumber around it), and restore or rewrite the lead-in sentence so "this" has a clear antecedent.

### `config.py`'s encryption-key field comment references a removed `supabase_oauth_client_id` field
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md`
- **What:** The encryption-key field's comment in `config.py` still references `supabase_oauth_client_id`, a field removed in the 2026-09-04 Supabase PAT redesign — this predates the restructure and is unrelated to it.
- **Why parked:** Pre-existing staleness unrelated to this restructure; noted while the file was under fresh eyes, not something this fix wave owns.
- **Follow-up:** Update the comment to reflect the current PAT-based field set whenever `config.py` is next touched.

### Deleted spec/plan filenames are still cross-referenced from the specs/plans kept in this repo
- **Found during:** Final whole-branch review of `docs/superpowers/plans/2026-09-05-onboarding-wizard-restructure.md`
- **What:** 79 deleted spec/plan filenames are still cross-referenced from the 21 specs/plans kept in this repo, pointing at documents that now only exist in the sibling `~/pr-review-bot` repo's history. `ISSUES.md`'s own intro already tells readers where to find the full combined history, but nothing in `docs/` or `README.md` does.
- **Why parked:** Low-value polish — one sentence in the README's "Related project" section would close it, but it's not a correctness gap since `ISSUES.md`'s intro already covers the pointer.
- **Follow-up:** Add a one-sentence pointer to `~/pr-review-bot`'s combined history in README's "Related project" section.

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
