# Vertex project/location + early model-probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a visitor choose the GCP project and region their Vertex deployment will use, and verify their chosen model is actually callable against *that exact pair* at the LLM-provider frame instead of four frames later.

**Architecture:** The Vertex branch of the LLM-provider frame gains a project dropdown (live `projects:search`) and a region dropdown (static list vendored from the bot's contract). Both flow into `probe_vertex_model` at the frame's Continue submit and into `_seed_provider_config` at Finish & Deploy, so the pair that is verified is the pair that is provisioned. The existing Finish & Deploy probe stays as the correctness gate.

**Tech Stack:** Python 3.12, FastAPI, pydantic v2, `google-genai`, `google-auth`, pytest + pytest-asyncio, vanilla JS in a single static page, `uv`.

**Spec:** `docs/superpowers/specs/2026-09-12-wizard-vertex-project-location-and-early-model-probe-design.md`

## Global Constraints

- **A Vertex location is part of the outbound hostname** (`{location}-aiplatform.googleapis.com`). Every `location` value reaching `genai.Client` MUST be a member of the vendored contract's `vertex_locations.options`. A regex/shape check is NOT sufficient. Reject before constructing any client. (Spec section 3.)
- **Never log, echo, or include in an exception message any visitor credential** — the service-account JSON, its decoded contents, or any API key. Narrow `except` clauses only.
- **Never hand-edit `contracts/provisioning.json` or `.ci/pr-review-bot-ref`.** Only `uv run python -m scripts.update_bot_contract` writes them, and it writes both or neither.
- **SSRF guard is written once:** any new code needing Vertex credentials calls the existing `llm_client._vertex_credentials_and_project`, never its own `from_service_account_info`.
- **google-auth is synchronous.** Any call using it runs under `asyncio.to_thread`.
- **`router.py` touches the session only through** `_get_session`/`_read_frame`/`_update_frame`/`_create_session`/`_delete_session`, never `session_store.*` directly.
- **Every new user-facing string is added to BOTH the `en` and `he` dictionaries** in `static/index.html`. `tests/test_onboarding_i18n.py:62` fails otherwise.
- **`llm_client.MODEL_PROBE_ERROR_CODES` must stay exactly** `("model_not_callable", "model_probe_unavailable")` — `tests/test_model_validation_conformance.py` asserts it equals the contract's set. New listing reasons do not belong there.
- **Before any push:** `uv run pytest -v` and `uv run ruff check .` both green. Before any push to `main`: the `deploy-verify` skill. Before calling the UI work done: the `ui-visual-review` skill.
- Project-id pattern, used verbatim wherever a project is validated: `^[a-z][a-z0-9-]{4,28}[a-z0-9]$`

---

### Task 1: Bot-side contract v3 (repo `~/pr-review-bot`)

**This task is in a different repository and MUST land on the bot's `main` before Task 2 can run** — `scripts/update_bot_contract.py` here resolves `origin/main`, never a local or feature-branch tip.

**Files:**
- Modify: `~/pr-review-bot/scripts/gen_contract.py`
- Modify: `~/pr-review-bot/contracts/provisioning.json` (regenerated, never hand-edited)
- Test: `~/pr-review-bot/tests/test_provisioning_contract.py`

**Interfaces:**
- Consumes: `providers.catalog.VERTEX_CATALOG_LOCATIONS`, `providers.catalog.DEFAULT_VERTEX_LOCATION`
- Produces: contract key `vertex_locations` = `{"default": str, "options": list[str]}`; `contract_version` == 3

- [ ] **Step 1: Write the failing test**

In `~/pr-review-bot/tests/test_provisioning_contract.py`:

```python
def test_contract_publishes_the_vertex_location_reference_list():
    """The onboarding wizard renders a region dropdown from this. It must
    come from the contract, not a hand-copied list over there -- a
    duplicate with no parity assertion is the 2026-09-09 shape again."""
    contract = gen_contract.build_contract()
    block = contract["vertex_locations"]
    assert block["options"] == catalog.VERTEX_CATALOG_LOCATIONS
    assert block["default"] == catalog.DEFAULT_VERTEX_LOCATION
    assert block["default"] in block["options"]
    assert contract["contract_version"] == 3
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd ~/pr-review-bot && uv run pytest tests/test_provisioning_contract.py::test_contract_publishes_the_vertex_location_reference_list -v`
Expected: FAIL — `KeyError: 'vertex_locations'`

- [ ] **Step 3: Implement**

In `scripts/gen_contract.py`, bump `CONTRACT_VERSION = 3`, add:

```python
def vertex_locations() -> dict[str, object]:
    """Vertex's generative-model regions, published for the onboarding
    wizard's region dropdown. Emitted from catalog.py's own constants so
    the wizard consumes a generated fact rather than maintaining a second
    copy of this list. Order is the curated geographic grouping catalog.py
    authors, NOT alphabetical -- consumers render it as received."""
    return {
        "default": catalog.DEFAULT_VERTEX_LOCATION,
        "options": list(catalog.VERTEX_CATALOG_LOCATIONS),
    }
```

and wire it into `build_contract()` alongside the existing blocks:

```python
        "vertex_locations": vertex_locations(),
```

- [ ] **Step 4: Regenerate the committed contract and run the full suite**

Run: `cd ~/pr-review-bot && uv run python -m scripts.gen_contract && uv run pytest -v && uv run ruff check .`
Expected: all green, `contracts/provisioning.json` shows the new block and `"contract_version": 3`

- [ ] **Step 5: Commit and get it onto `main`**

```bash
cd ~/pr-review-bot
git add scripts/gen_contract.py contracts/provisioning.json tests/test_provisioning_contract.py
git commit -m "Publish Vertex's region reference list in the provisioning contract"
```

STOP and report if the bot repo is not on a branch you were asked to push, if its working tree had pre-existing uncommitted changes, or if its suite was not already green before you started. Do not merge to `main` on your own initiative — confirm with the controller first.

---

### Task 2: Vendor contract v3 into the wizard

**Files:**
- Modify: `contracts/provisioning.json` (via the script only)
- Modify: `.ci/pr-review-bot-ref` (via the script only)
- Test: `tests/test_model_validation_conformance.py:20`

**Interfaces:**
- Consumes: Task 1's contract on the bot's `main`
- Produces: `CONTRACT["vertex_locations"]["options"]` / `["default"]` available to every later task

- [ ] **Step 1: Update the conformance test's version assertion**

In `tests/test_model_validation_conformance.py`, change `assert CONTRACT["contract_version"] == 2` to `== 3`.

- [ ] **Step 2: Run it to confirm it fails**

Run: `uv run pytest tests/test_model_validation_conformance.py::test_contract_version_is_understood -v`
Expected: FAIL — still vendoring version 2

- [ ] **Step 3: Vendor the new contract**

Run: `uv run python -m scripts.update_bot_contract`
Expected: rewrites both `contracts/provisioning.json` and `.ci/pr-review-bot-ref`. If it refuses, `tests/test_bot_contract_parity.py` is red against the extracted copy — STOP and report; do not hand-edit either file.

- [ ] **Step 4: Add the parity assertion for the new block**

In `tests/test_bot_contract_parity.py`:

```python
def test_vertex_location_allowlist_is_non_empty_and_contains_its_default():
    """router pins every submitted location to this list (a location is part
    of the Vertex hostname -- see the spec's section 3). An empty or
    default-less list would silently turn that allowlist into a deny-all."""
    block = CONTRACT["vertex_locations"]
    assert block["options"], "an empty allowlist would reject every region"
    assert block["default"] in block["options"]
```

- [ ] **Step 5: Run the full suite and commit**

Run: `uv run pytest -v && uv run ruff check .`

```bash
git add contracts/provisioning.json .ci/pr-review-bot-ref tests/test_model_validation_conformance.py tests/test_bot_contract_parity.py
git commit -m "Vendor bot contract v3 (Vertex region reference list)"
```

---

### Task 3: `list_vertex_models` accepts a project/location pair

**Files:**
- Modify: `llm_client.py:166-218` (`list_vertex_models`)
- Test: `tests/test_onboarding_llm_client.py`

**Interfaces:**
- Produces: `async def list_vertex_models(service_account_key_b64: str, project: str | None = None, location: str | None = None) -> VertexModelsListed | LlmApiFailed`. `VertexModelsListed.project_id` is the project actually used (the override when given, else the key's own).

- [ ] **Step 1: Write the failing tests**

In `tests/test_onboarding_llm_client.py` (follow the file's existing `genai.Client` monkeypatch pattern — do NOT use `respx` for Vertex):

```python
async def test_list_vertex_models_defaults_to_the_keys_own_project_and_region(monkeypatch):
    captured = {}
    _install_fake_genai_client(monkeypatch, captured, models=["publishers/google/models/m1"])
    result = await llm_client.list_vertex_models(_VALID_KEY_B64)
    assert captured["project"] == "test-project"
    assert captured["location"] == "us-central1"
    assert result.project_id == "test-project"


async def test_list_vertex_models_honours_an_explicit_pair(monkeypatch):
    captured = {}
    _install_fake_genai_client(monkeypatch, captured, models=["publishers/google/models/m1"])
    result = await llm_client.list_vertex_models(
        _VALID_KEY_B64, project="other-project", location="europe-west4"
    )
    assert captured["project"] == "other-project"
    assert captured["location"] == "europe-west4"
    # The reported project is the one actually queried, never the key's home
    # project -- conflating them is how a verdict gets attributed to the
    # wrong pair.
    assert result.project_id == "other-project"
```

If `_install_fake_genai_client` does not already exist in that file, write it to monkeypatch `llm_client.genai.Client` with a stub recording the `project`/`location` kwargs and exposing `aio.models.list()` / `aio.aclose()`.

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_onboarding_llm_client.py -k list_vertex_models -v`
Expected: FAIL — `list_vertex_models() got an unexpected keyword argument 'project'`

- [ ] **Step 3: Implement**

```python
async def list_vertex_models(
    service_account_key_b64: str,
    project: str | None = None,
    location: str | None = None,
) -> VertexModelsListed | LlmApiFailed:
```

In the body, replace the client construction's `project=project_id` with
`project=project or project_id` and `location=_VERTEX_LOCATION` with
`location=location or _VERTEX_LOCATION`, bind `used_project = project or project_id`
before constructing the client, and return `VertexModelsListed(project_id=used_project, models=models)`.

Update the docstring: location is no longer "fixed to us-central1" — it defaults to `_VERTEX_LOCATION` and callers that know the provisioning target override it, mirroring `probe_vertex_model`'s existing docstring. State that `project_id` reports the project actually queried.

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_onboarding_llm_client.py -k list_vertex_models -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add llm_client.py tests/test_onboarding_llm_client.py
git commit -m "Let list_vertex_models query an explicit project/region pair"
```

---

### Task 4: `list_accessible_projects`

**Files:**
- Modify: `llm_client.py` (new dataclass + new function, beside `list_vertex_models`)
- Test: `tests/test_onboarding_llm_client.py`

**Interfaces:**
- Consumes: existing `llm_client._vertex_credentials_and_project(b64) -> tuple[Credentials, str] | LlmApiFailed`
- Produces: `@dataclasses.dataclass(frozen=True) class VertexProjectsListed: projects: list[str]`; `async def list_accessible_projects(service_account_key_b64: str) -> VertexProjectsListed | LlmApiFailed`, failure reason `"vertex_projects_unavailable"`

- [ ] **Step 1: Write the failing tests**

```python
async def test_list_accessible_projects_returns_sorted_ids(monkeypatch):
    def fake_session(creds):
        return _FakeAuthorizedSession(
            {"projects": [{"projectId": "zeta-proj"}, {"projectId": "alpha-proj"}]}
        )

    monkeypatch.setattr(llm_client, "AuthorizedSession", fake_session)
    result = await llm_client.list_accessible_projects(_VALID_KEY_B64)
    assert result.projects == ["alpha-proj", "test-project", "zeta-proj"]


async def test_list_accessible_projects_always_includes_the_keys_own_project(monkeypatch):
    """A service account whose IAM binding hasn't propagated is missing from
    its own projects:search results. Without the union the wizard would
    refuse to offer the one project the credential certainly works against."""
    monkeypatch.setattr(
        llm_client, "AuthorizedSession", lambda creds: _FakeAuthorizedSession({"projects": []})
    )
    result = await llm_client.list_accessible_projects(_VALID_KEY_B64)
    assert result.projects == ["test-project"]


async def test_list_accessible_projects_reports_a_denied_listing_distinctly(monkeypatch):
    """403 here means Cloud Resource Manager isn't enabled or the account
    lacks resourcemanager.projects.get -- actionable, and not the same fact
    as a bad credential."""
    monkeypatch.setattr(
        llm_client, "AuthorizedSession", lambda creds: _FakeAuthorizedSession(None, status=403)
    )
    result = await llm_client.list_accessible_projects(_VALID_KEY_B64)
    assert result == llm_client.LlmApiFailed(reason="vertex_projects_unavailable")


async def test_list_accessible_projects_rejects_a_malformed_key():
    result = await llm_client.list_accessible_projects("not-base64!!")
    assert result == llm_client.LlmApiFailed(reason="invalid_service_account_json")
```

Add the transport stub to the same file:

```python
class _FakeAuthorizedSession:
    def __init__(self, payload, status=200):
        self._payload, self._status = payload, status

    def get(self, url, timeout=None):
        assert url == "https://cloudresourcemanager.googleapis.com/v3/projects:search"
        return self

    def raise_for_status(self):
        if self._status != 200:
            raise requests_exceptions.HTTPError(response=_FakeResponse(self._status))

    def json(self):
        return self._payload
```

with `_FakeResponse` a trivial object exposing `.status_code`, and
`from requests import exceptions as requests_exceptions` at the top.

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_onboarding_llm_client.py -k accessible_projects -v`
Expected: FAIL — `AttributeError: module 'llm_client' has no attribute 'list_accessible_projects'`

- [ ] **Step 3: Implement**

Add near the other imports:

```python
from google.auth.transport.requests import AuthorizedSession
```

Add beside `VertexModelsListed`:

```python
@dataclasses.dataclass(frozen=True)
class VertexProjectsListed:
    projects: list[str]
```

Add the module constant beside `_VERTEX_TOKEN_URI`:

```python
_RESOURCE_MANAGER_SEARCH_URL = "https://cloudresourcemanager.googleapis.com/v3/projects:search"
```

And the function:

```python
async def list_accessible_projects(
    service_account_key_b64: str,
) -> VertexProjectsListed | LlmApiFailed:
    """Every GCP project this credential's IAM bindings let it act against,
    via Cloud Resource Manager's projects:search -- mirroring the sibling
    review-engine project's providers/catalog.py::list_accessible_projects.

    NOT derivable from the key: a service account's own project_id names
    only its "home" project, but the same account can hold roles on others,
    and pr-review-bot's factory.py passes vertex_gcp_project straight
    through without ever checking it against the key's project_id. Offering
    only the home project would therefore hide valid choices.

    Credentials come from _vertex_credentials_and_project so this shares the
    one token_uri/universe_domain SSRF guard rather than growing a second,
    slightly-different copy of it. Never logs the key or its contents.
    """
    result = _vertex_credentials_and_project(service_account_key_b64)
    if isinstance(result, LlmApiFailed):
        return result
    creds, own_project_id = result

    def _search() -> list[str]:
        # AuthorizedSession is requests-based and fully synchronous --
        # including the token refresh it performs internally -- so the whole
        # call runs off the event loop, same rule as creds.refresh above.
        session = AuthorizedSession(creds)
        response = session.get(
            _RESOURCE_MANAGER_SEARCH_URL, timeout=_REQUEST_TIMEOUT_MS / 1000
        )
        response.raise_for_status()
        return [p["projectId"] for p in response.json().get("projects", []) if p.get("projectId")]

    try:
        found = await asyncio.to_thread(_search)
    except Exception:  # noqa: BLE001 -- see below
        # Deliberately broad, and deliberately silent about the cause: this
        # call's failure modes span requests, google-auth and JSON decoding,
        # and every one of them can carry credential-derived detail in its
        # message. A structural verdict is all the caller needs.
        return LlmApiFailed(reason="vertex_projects_unavailable")
    return VertexProjectsListed(projects=sorted(set(found) | {own_project_id}))
```

Note the `noqa: BLE001` and its comment are required — ruff will flag the bare
`except Exception` otherwise, and the reason it is correct here (never surfacing
a credential-bearing exception message) must stay written down.

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_onboarding_llm_client.py -k accessible_projects -v && uv run ruff check llm_client.py`
Expected: PASS, no lint errors

- [ ] **Step 5: Commit**

```bash
git add llm_client.py tests/test_onboarding_llm_client.py
git commit -m "List the GCP projects a Vertex service account can act against"
```

---

### Task 5: Location allowlist + the locations endpoint

**Files:**
- Modify: `router.py` (module-level contract read, new GET endpoint, two validators)
- Test: `tests/test_onboarding_router.py`

**Interfaces:**
- Produces: `router._VERTEX_LOCATIONS: tuple[str, ...]`, `router._VERTEX_DEFAULT_LOCATION: str`, `router._valid_vertex_location(v) -> bool`, `router._valid_vertex_project(v) -> bool`, and `GET /api/llm/vertex/locations -> {"locations": [...], "default": "..."}`

- [ ] **Step 1: Write the failing tests**

```python
async def test_vertex_locations_endpoint_serves_the_contract_list_in_order():
    """Rendered as received -- the contract's order is a curated geographic
    grouping, not alphabetical, and the dropdown preserves it."""
    client = await _client()
    resp = await client.get("/api/llm/vertex/locations")
    assert resp.status_code == 200
    assert resp.json() == {
        "locations": CONTRACT["vertex_locations"]["options"],
        "default": CONTRACT["vertex_locations"]["default"],
    }


def test_only_contract_declared_locations_are_accepted():
    """A location is part of the Vertex hostname -- an allowlist, never a
    pattern. See the spec's section 3."""
    assert router._valid_vertex_location("us-central1")
    assert not router._valid_vertex_location("evil-attacker-host")
    assert not router._valid_vertex_location("")
    assert not router._valid_vertex_location("us-central1.evil.com")


def test_project_ids_are_pattern_checked():
    assert router._valid_vertex_project("my-project-123")
    assert not router._valid_vertex_project("Bad_Project")
    assert not router._valid_vertex_project("x")
    assert not router._valid_vertex_project("")
```

Load `CONTRACT` in the test module the same way `tests/test_model_validation_conformance.py` does.

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_onboarding_router.py -k "vertex_locations or _valid_vertex" -v`
Expected: FAIL — 404 on the GET, `AttributeError` on the helpers

- [ ] **Step 3: Implement**

Near `router.py`'s other module-level contract reads:

```python
# A Vertex location is part of the outbound hostname
# ({location}-aiplatform.googleapis.com), so every submitted value is pinned
# to the set the bot's contract declares -- an allowlist, never a pattern.
# "evil-attacker-host" satisfies any reasonable regex; membership is what
# makes the reachable-host set closed by construction. Same vulnerability
# class as the token_uri/universe_domain finding in ISSUES.md.
_VERTEX_LOCATIONS: tuple[str, ...] = tuple(_CONTRACT["vertex_locations"]["options"])
_VERTEX_DEFAULT_LOCATION: str = _CONTRACT["vertex_locations"]["default"]

# GCP's own project-id rule. A project is a path segment, not a host, so this
# is a clarity check rather than a security boundary -- it turns a malformed
# value into a clear verdict instead of an opaque Google API error.
_VERTEX_PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")


def _valid_vertex_location(value: str) -> bool:
    return value in _VERTEX_LOCATIONS


def _valid_vertex_project(value: str) -> bool:
    return bool(_VERTEX_PROJECT_RE.fullmatch(value))


@router.get("/api/llm/vertex/locations")
async def get_vertex_locations() -> dict:
    """A static reference list, not a live call -- there is no API that
    enumerates generative-model-enabled regions per project (see the bot's
    catalog.VERTEX_CATALOG_LOCATIONS docstring). Served rather than
    templated into the page: index.html templates exactly one value
    (supabase_oauth_client_id) and that stays true."""
    return {"locations": list(_VERTEX_LOCATIONS), "default": _VERTEX_DEFAULT_LOCATION}
```

If `router.py` does not already read the contract at module level, add the read
mirroring `tests/test_model_validation_conformance.py`'s (`json.loads((Path(__file__).parent / "contracts/provisioning.json").read_text(encoding="utf-8"))`), and `import re` if absent.

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_onboarding_router.py -k "vertex_locations or _valid_vertex" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add router.py tests/test_onboarding_router.py
git commit -m "Pin Vertex locations to the contract allowlist, and serve them"
```

---

### Task 6: `list-models` accepts the pair and returns the project options

**Files:**
- Modify: `router.py:161` area (`LlmVertexListModelsRequest`), `router.py:733-738` (`list_vertex_models` endpoint)
- Test: `tests/test_onboarding_router.py`

**Interfaces:**
- Consumes: Task 3's `llm_client.list_vertex_models(b64, project, location)`, Task 4's `llm_client.list_accessible_projects(b64)`, Task 5's validators
- Produces: request fields `project: str | None`, `location: str | None`; response gains `projects`, `default_project`, `default_location` on the both-absent path only

- [ ] **Step 1: Write the failing tests**

```python
async def test_first_validate_returns_the_project_options(monkeypatch):
    async def fake_list_models(b64, project=None, location=None):
        return llm_client.VertexModelsListed(project_id="test-project", models=["m1"])

    async def fake_list_projects(b64):
        return llm_client.VertexProjectsListed(projects=["a-proj", "test-project"])

    monkeypatch.setattr(llm_client, "list_vertex_models", fake_list_models)
    monkeypatch.setattr(llm_client, "list_accessible_projects", fake_list_projects)
    client = await _client()
    resp = await client.post("/api/llm/vertex/list-models", json={"service_account_key_b64": "k"})
    assert resp.json() == {
        "valid": True,
        "project_id": "test-project",
        "models": ["m1"],
        "projects": ["a-proj", "test-project"],
        "default_project": "test-project",
        "default_location": router._VERTEX_DEFAULT_LOCATION,
    }


async def test_a_dropdown_change_does_not_repeat_the_projects_listing(monkeypatch):
    """One live Cloud Resource Manager call per credential, not one per
    dropdown change -- the burst pattern CLAUDE.md's LLM hygiene forbids."""
    async def fake_list_models(b64, project=None, location=None):
        return llm_client.VertexModelsListed(project_id=project, models=["m1"])

    async def boom(b64):
        raise AssertionError("re-validate must not repeat the projects listing")

    monkeypatch.setattr(llm_client, "list_vertex_models", fake_list_models)
    monkeypatch.setattr(llm_client, "list_accessible_projects", boom)
    client = await _client()
    resp = await client.post(
        "/api/llm/vertex/list-models",
        json={"service_account_key_b64": "k", "project": "other-proj", "location": "europe-west4"},
    )
    assert resp.json() == {"valid": True, "project_id": "other-proj", "models": ["m1"]}


async def test_an_unlisted_location_is_refused_without_constructing_a_client(monkeypatch):
    """The SSRF regression test: a well-shaped but undeclared location must
    never reach genai.Client -- a location is part of the hostname."""
    async def boom(*a, **k):
        raise AssertionError("no Vertex client may be constructed for a rejected location")

    monkeypatch.setattr(llm_client, "list_vertex_models", boom)
    monkeypatch.setattr(llm_client, "list_accessible_projects", boom)
    client = await _client()
    resp = await client.post(
        "/api/llm/vertex/list-models",
        json={"service_account_key_b64": "k", "location": "evil-attacker-host"},
    )
    assert resp.json() == {"valid": False, "reason": "invalid_vertex_location"}


async def test_a_malformed_project_is_refused(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("no listing may run for a rejected project")

    monkeypatch.setattr(llm_client, "list_vertex_models", boom)
    monkeypatch.setattr(llm_client, "list_accessible_projects", boom)
    client = await _client()
    resp = await client.post(
        "/api/llm/vertex/list-models",
        json={"service_account_key_b64": "k", "project": "Bad_Project"},
    )
    assert resp.json() == {"valid": False, "reason": "invalid_vertex_project"}


async def test_a_failed_projects_listing_fails_the_whole_call(monkeypatch):
    """The frame cannot offer a project dropdown it could not populate."""
    async def fake_list_models(b64, project=None, location=None):
        return llm_client.VertexModelsListed(project_id="test-project", models=["m1"])

    async def fake_list_projects(b64):
        return llm_client.LlmApiFailed(reason="vertex_projects_unavailable")

    monkeypatch.setattr(llm_client, "list_vertex_models", fake_list_models)
    monkeypatch.setattr(llm_client, "list_accessible_projects", fake_list_projects)
    client = await _client()
    resp = await client.post("/api/llm/vertex/list-models", json={"service_account_key_b64": "k"})
    assert resp.json() == {"valid": False, "reason": "vertex_projects_unavailable"}
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_onboarding_router.py -k "projects_listing or unlisted_location or malformed_project or first_validate" -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Extend the request model:

```python
class LlmVertexListModelsRequest(BaseModel):
    service_account_key_b64: str = Field(min_length=1, max_length=16384)
    project: str | None = None
    location: str | None = None
```

Replace the endpoint:

```python
@router.post("/api/llm/vertex/list-models")
async def list_vertex_models(payload: LlmVertexListModelsRequest) -> dict:
    """Both fields absent means "first validate of a freshly uploaded key":
    list models at the key's own project/default region AND run the one
    projects:search that populates the dropdown. Either present means "the
    visitor changed a dropdown": re-list models for that exact pair only --
    repeating the projects listing per change would be a live call per
    keystroke."""
    if payload.location is not None and not _valid_vertex_location(payload.location):
        return {"valid": False, "reason": "invalid_vertex_location"}
    if payload.project is not None and not _valid_vertex_project(payload.project):
        return {"valid": False, "reason": "invalid_vertex_project"}

    result = await llm_client.list_vertex_models(
        payload.service_account_key_b64, payload.project, payload.location
    )
    if not isinstance(result, llm_client.VertexModelsListed):
        return {"valid": False, "reason": result.reason}
    response = {"valid": True, "project_id": result.project_id, "models": result.models}
    if payload.project is None and payload.location is None:
        projects = await llm_client.list_accessible_projects(payload.service_account_key_b64)
        if not isinstance(projects, llm_client.VertexProjectsListed):
            return {"valid": False, "reason": projects.reason}
        response["projects"] = projects.projects
        response["default_project"] = result.project_id
        response["default_location"] = _VERTEX_DEFAULT_LOCATION
    return response
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_onboarding_router.py -v`
Expected: PASS (whole router file — the existing vertex list-models tests must still pass unchanged)

- [ ] **Step 5: Commit**

```bash
git add router.py tests/test_onboarding_router.py
git commit -m "Return the project options, and list models for a chosen pair"
```

---

### Task 7: `confirm` probes the chosen pair before writing

**Files:**
- Modify: `router.py:162-165` (`LlmConfirmRequest`), `router.py:741-757` (`confirm_llm_provider`)
- Test: `tests/test_onboarding_router.py:1274-1302`

**Interfaces:**
- Consumes: `llm_client.probe_vertex_model(b64, model, project=, location=)`, `llm_client.probe_gemini_model(key, model)`, Task 5's validators
- Produces: session frame `llm_provider` now carrying `vertex_gcp_project` and `vertex_gcp_location` for vertex

- [ ] **Step 1: Write the failing tests**

```python
async def test_confirm_probes_the_pair_the_visitor_chose(monkeypatch):
    """The pair that is verified must be the pair that gets provisioned --
    probing the key's home project while seeding a different one is the
    defect this whole frame exists to close."""
    fake = _use_fake_session_store(monkeypatch)
    session_id = fake.create_session()
    seen = {}

    async def fake_probe(b64, model, project=None, location=None):
        seen.update(project=project, location=location, model=model)
        return llm_client.LlmModelProbed(model=model)

    monkeypatch.setattr(llm_client, "probe_vertex_model", fake_probe)
    client = await _client()
    resp = await client.post(
        "/api/llm/confirm",
        json={
            "provider": "vertex",
            "credential_value": "b64",
            "model": "gemini-2.5-flash",
            "vertex_gcp_project": "chosen-proj",
            "vertex_gcp_location": "europe-west4",
        },
        cookies={"onboarding_session": session_id},
    )
    assert resp.json() == {"valid": True}
    assert seen == {"project": "chosen-proj", "location": "europe-west4", "model": "gemini-2.5-flash"}
    assert fake.read_frame(session_id, "llm_provider") == {
        "provider": "vertex",
        "credential_value": "b64",
        "model": "gemini-2.5-flash",
        "vertex_gcp_project": "chosen-proj",
        "vertex_gcp_location": "europe-west4",
    }


async def test_confirm_refuses_an_uncallable_model_and_writes_nothing(monkeypatch):
    """A refused model must never become session state -- otherwise
    GET /api/session reports the frame done behind an uncallable model."""
    fake = _use_fake_session_store(monkeypatch)
    session_id = fake.create_session()

    async def fake_probe(api_key, model):
        return llm_client.LlmApiFailed(reason="model_not_callable")

    monkeypatch.setattr(llm_client, "probe_gemini_model", fake_probe)
    client = await _client()
    resp = await client.post(
        "/api/llm/confirm",
        json={"provider": "gemini", "credential_value": "k", "model": "nope"},
        cookies={"onboarding_session": session_id},
    )
    assert resp.json() == {"valid": False, "reason": "model_not_callable"}
    assert fake.read_frame(session_id, "llm_provider") in (None, {})


async def test_confirm_never_probes_groq(monkeypatch):
    fake = _use_fake_session_store(monkeypatch)
    session_id = fake.create_session()

    async def boom(*a, **k):
        raise AssertionError("groq needs no probe -- see the contract")

    monkeypatch.setattr(llm_client, "probe_gemini_model", boom)
    monkeypatch.setattr(llm_client, "probe_vertex_model", boom)
    client = await _client()
    resp = await client.post(
        "/api/llm/confirm",
        json={"provider": "groq", "credential_value": "k", "model": "llama-3.3-70b"},
        cookies={"onboarding_session": session_id},
    )
    assert resp.json() == {"valid": True}


async def test_confirm_refuses_a_vertex_submission_missing_its_pair(monkeypatch):
    _use_fake_session_store(monkeypatch)
    client = await _client()
    resp = await client.post(
        "/api/llm/confirm",
        json={"provider": "vertex", "credential_value": "b64", "model": "m"},
    )
    # main.py's app-wide handler -- the rejected body is never echoed back.
    assert resp.status_code == 422
    assert resp.json() == {"detail": "invalid request"}
```

Also update the existing `test_confirm_llm_provider_persists_to_session` to
monkeypatch a passing `probe_gemini_model`, mirroring the bulk-push tests'
existing `fake_probe_gemini_model` pattern — it now exercises the probe path.

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_onboarding_router.py -k confirm -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
class LlmConfirmRequest(BaseModel):
    provider: str = Field(pattern=r"^(gemini|groq|vertex)$")
    credential_value: str = Field(min_length=1, max_length=16384)
    model: str = Field(min_length=1, max_length=256)
    vertex_gcp_project: str | None = None
    vertex_gcp_location: str | None = None

    @model_validator(mode="after")
    def _pair_belongs_to_vertex_only(self) -> "LlmConfirmRequest":
        """Field() alone cannot say "required only when a sibling field has
        one particular value". A gemini/groq submission carrying a region is
        a malformed request, not a field to quietly ignore."""
        has_pair = self.vertex_gcp_project is not None and self.vertex_gcp_location is not None
        if self.provider == "vertex" and not has_pair:
            raise ValueError("vertex requires a project and a location")
        if self.provider != "vertex" and (
            self.vertex_gcp_project is not None or self.vertex_gcp_location is not None
        ):
            raise ValueError("only vertex carries a project/location")
        return self
```

Import `model_validator` from pydantic alongside the existing imports.

Then, in `confirm_llm_provider`, after the session check and **before**
`_update_frame`:

```python
    if payload.provider == "vertex":
        if not _valid_vertex_location(payload.vertex_gcp_location):
            return {"valid": False, "reason": "invalid_vertex_location"}
        if not _valid_vertex_project(payload.vertex_gcp_project):
            return {"valid": False, "reason": "invalid_vertex_project"}

    # Prove the model is callable BEFORE it becomes session state -- same
    # ordering rule bulk_push_render_env_vars already follows, one frame
    # earlier, so a refused model never reaches GET /api/session as "done".
    # For vertex this probes the exact project/region pair the visitor
    # chose, which is the same pair _seed_provider_config will write.
    # Groq needs no probe (contracts/provisioning.json's model_validation).
    probe: llm_client.LlmModelProbed | llm_client.LlmApiFailed | None = None
    if payload.provider == "vertex":
        probe = await llm_client.probe_vertex_model(
            payload.credential_value,
            payload.model,
            project=payload.vertex_gcp_project,
            location=payload.vertex_gcp_location,
        )
    elif payload.provider == "gemini":
        probe = await llm_client.probe_gemini_model(payload.credential_value, payload.model)
    if isinstance(probe, llm_client.LlmApiFailed):
        return {"valid": False, "reason": probe.reason}
```

and extend the `_update_frame` payload with the two fields **only** for vertex
(build the dict conditionally so gemini/groq frames keep exactly their current
three keys).

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_onboarding_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add router.py tests/test_onboarding_router.py
git commit -m "Probe the chosen model/project/region before the frame completes"
```

---

### Task 8: Seed and back-probe the stored pair at Finish & Deploy

**Files:**
- Modify: `router.py:948-978` (the probe + seed block in `bulk_push_render_env_vars`)
- Test: `tests/test_onboarding_router.py`

**Interfaces:**
- Consumes: session frame fields written by Task 7
- Produces: `_seed_provider_config(db_url, provider, model, project, location)` called with the visitor's pair

- [ ] **Step 1: Write the failing test**

```python
async def test_bulk_push_seeds_and_probes_the_visitors_chosen_pair(monkeypatch):
    """The backstop must re-verify, and seed, the same pair the frame
    confirmed -- not the key's home project at a hardcoded region."""
    fake = _use_fake_session_store(monkeypatch)
    session_id = _session_ready_for_bulk_push(fake)  # existing helper pattern
    fake.update_frame(session_id, "llm_provider", {
        "provider": "vertex",
        "credential_value": "b64",
        "model": "gemini-2.5-flash",
        "vertex_gcp_project": "chosen-proj",
        "vertex_gcp_location": "europe-west4",
    })
    seeded, probed = {}, {}

    def fake_seed(database_url, provider, model, project, location):
        seeded.update(project=project, location=location)
        return True

    async def fake_probe(b64, model, project=None, location=None):
        probed.update(project=project, location=location)
        return llm_client.LlmModelProbed(model=model)

    monkeypatch.setattr(router, "_seed_provider_config", fake_seed)
    monkeypatch.setattr(llm_client, "probe_vertex_model", fake_probe)
    monkeypatch.setattr(render_client, "push_env_vars",
                        lambda *a, **k: render_client.RenderEnvVarsPushed(pushed=[]))
    client = await _client()
    resp = await client.post("/api/render/bulk-push-env-vars",
                             cookies={"onboarding_session": session_id})
    assert resp.json()["valid"] is True
    assert probed == {"project": "chosen-proj", "location": "europe-west4"}
    assert seeded == {"project": "chosen-proj", "location": "europe-west4"}
```

Reuse whatever session-setup helper the neighbouring bulk-push tests already
use rather than inventing a new one; if `push_env_vars` must be async in that
file, follow the existing stubs' shape.

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_onboarding_router.py -k chosen_pair -v`
Expected: FAIL — probed/seeded carry `None`/`"us-central1"`

- [ ] **Step 3: Implement**

In the vertex probe branch, pass the stored pair:

```python
            probe = await llm_client.probe_vertex_model(
                llm_provider["credential_value"],
                llm_provider["model"],
                project=llm_provider.get("vertex_gcp_project"),
                location=llm_provider.get("vertex_gcp_location"),
            )
```

and in the `_seed_provider_config` call replace the literal `None` and the
`llm_client._VERTEX_LOCATION` conditional with
`llm_provider.get("vertex_gcp_project")` and
`llm_provider.get("vertex_gcp_location")`.

Rewrite the block's comment: `vertex_gcp_project` is no longer always NULL — the
visitor chose it, it was verified at the LLM-provider frame against this same
pair, and `factory.py` now reads the seeded value rather than deriving it from
the key's embedded `project_id` (identical strings when the visitor kept the
default). Note that this probe is retained as the correctness gate because a
reload never re-runs `/api/llm/confirm` and `SESSION_TTL` is 4 hours.

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_onboarding_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add router.py tests/test_onboarding_router.py
git commit -m "Seed and re-probe the visitor's own project/region at deploy"
```

---

### Task 9: The two dropdowns, the shared relay helper, and the strings

**Files:**
- Modify: `static/index.html` — the vertex branch of the LLM-provider frame (markup ~1085-1111), `showLlmProviderModels` (~2214), `validateLlmProviderCredential` (~2271), `confirmLlmProviderModel` (~2357), `llmProviderErrorForReason` (~2179), both `STRINGS` dictionaries (~1313 en, ~1468 he), the listener block (~4002)
- Test: `tests/test_onboarding_page.py`

**Interfaces:**
- Consumes: `GET /api/llm/vertex/locations`, `POST /api/llm/vertex/list-models` (with and without the pair), `POST /api/llm/confirm` (with the pair)

- [ ] **Step 1: Write the failing tests**

```python
async def test_vertex_frame_offers_project_and_region_dropdowns():
    client = await _client()
    body = (await client.get("/")).text
    assert '<select id="llm-provider-project-select">' in body
    assert '<select id="llm-provider-location-select">' in body


async def test_project_options_are_sorted_alphabetically():
    """Same rule as the model dropdown -- a project list carries no authored
    order, so it sorts by name."""
    client = await _client()
    body = (await client.get("/")).text
    assert "const sortedProjects = [...projects].sort((a, b) => a.localeCompare(b));" in body


async def test_location_options_are_rendered_in_contract_order_not_sorted():
    """The contract's order is a curated geographic grouping with `global`
    last. Sorting it would scatter `global` into the g's and bury
    us-central1 -- so this asserts the absence of a sort, deliberately."""
    client = await _client()
    body = (await client.get("/")).text
    fn_start = body.index("function showVertexLocations")
    fn_body = body[fn_start : body.index("}", body.index("locations.forEach"))]
    assert "sort(" not in fn_body


async def test_vertex_list_models_endpoint_still_leaves_the_page_exactly_once():
    """Both the first validate and every dropdown-change re-list go through
    one shared helper -- one credential, one exit path."""
    client = await _client()
    body = (await client.get("/")).text
    assert body.count('endpoint = "/api/llm/vertex/list-models"') == 1


async def test_changing_a_dropdown_clears_the_selected_model():
    """A model verified against one project/region says nothing about
    another pair."""
    client = await _client()
    body = (await client.get("/")).text
    fn_start = body.index("function onVertexPairChanged")
    fn_body = body[fn_start : fn_start + 800]
    assert 'document.getElementById("llm-provider-model-select").innerHTML = "";' in fn_body
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/test_onboarding_page.py -k "vertex or project_options or location_options or dropdown" -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Markup — inside the vertex branch of the LLM-provider frame, above the existing
model section, add a `llm-provider-vertex-pair-section` (hidden by default)
containing two labelled `<select>`s, `llm-provider-project-select` and
`llm-provider-location-select`, following the existing model section's markup
and class conventions exactly.

JS:
- `showVertexLocations(locations, defaultLocation)` — populates the region
  select **in received order**, with a comment stating the order is the
  contract's curated grouping and must not be sorted, and preselects
  `defaultLocation`. Fetched once per page load from
  `GET /api/llm/vertex/locations`.
- `showVertexProjects(projects, defaultProject)` — sorts via
  `const sortedProjects = [...projects].sort((a, b) => a.localeCompare(b));`
  and preselects `defaultProject`.
- Both sections revealed inside `growFrameToFit("llm-provider", ...)`.
- Factor the existing `fetch(endpoint, ...)` in `validateLlmProviderCredential`
  so the initial validate and `onVertexPairChanged` share **one** call site —
  the `endpoint = "/api/llm/vertex/list-models"` assignment must still appear
  exactly once in the file. Follow `callSupabaseRelay`'s precedent.
- `onVertexPairChanged()` — clears the model select and the current error,
  re-lists models for `{project, location}` via that shared helper, and
  re-renders the model dropdown. Wired to both selects' `change` events in the
  listener block.
- `confirmLlmProviderModel()` — for vertex, include `vertex_gcp_project` and
  `vertex_gcp_location` in the POST body, read from the two selects; for
  gemini/groq send exactly the current three fields (the server rejects a
  stray pair).
- `llmProviderErrorForReason`'s map gains: `model_not_callable` →
  `err_llm_model_not_callable`, `model_probe_unavailable` →
  `err_llm_model_probe_unavailable`, `vertex_projects_unavailable` →
  `err_llm_vertex_projects_unavailable`, `invalid_vertex_location` →
  `err_llm_invalid_vertex_location`, `invalid_vertex_project` →
  `err_llm_invalid_vertex_project`.

Strings — add to **both** dictionaries:

```
frame4_project_label / frame4_region_label
frame4_project_placeholder / frame4_region_placeholder
err_llm_model_not_callable:
  en: "Your provider lists this model, but this project isn't entitled to call it. Pick a different model below."
err_llm_model_probe_unavailable:
  en: "Couldn't verify this model right now (the provider is unreachable). Try again in a moment."
err_llm_vertex_projects_unavailable:
  en: "Couldn't list your GCP projects. Enable the Cloud Resource Manager API on this project, or grant the service account the resourcemanager.projects.get permission, then try again."
err_llm_invalid_vertex_location / err_llm_invalid_vertex_project:
  en: generic "That selection isn't valid. Reload the page and try again."
```

Write natural Hebrew for each — and per `CLAUDE.md`, **no arrow-chained LTR
term sequences in Hebrew prose**; the Cloud Resource Manager string names its
steps with ordinary prepositions, or a real nested `<ol>` if it needs steps.
The first two are frame-local and must NOT reuse the `err_render_deploy_*`
strings, whose text tells the visitor to go back to this frame.

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_onboarding_page.py tests/test_onboarding_i18n.py -v`
Expected: PASS (i18n parity proves the Hebrew half is complete)

- [ ] **Step 5: Visual review**

Invoke the `ui-visual-review` skill. Required — this is a real markup/layout
change, and the RTL check matters for two newly labelled dropdowns. Fix
whatever it surfaces before proceeding.

- [ ] **Step 6: Commit**

```bash
git add static/index.html tests/test_onboarding_page.py
git commit -m "Collect the Vertex project and region, and verify the model there"
```

---

### Task 10: Documentation, parked issue, and release checks

**Files:**
- Modify: `CLAUDE.md` (sub-project 4 and sub-project 6 sections)
- Modify: `ISSUES.md` (Parked Issues)

- [ ] **Step 1: Update `CLAUDE.md`'s sub-project 4 section**

The unlock gate is now **credential + model pick + a passing entitlement
probe**, and for vertex also a project/region pick. Record that the probe runs
at `/api/llm/confirm` before the session write, that the pair probed is the pair
seeded, and that `location` is pinned to the contract allowlist because it is
part of the Vertex hostname.

- [ ] **Step 2: Update `CLAUDE.md`'s sub-project 6 section**

Two claims there are now false and must be corrected, not merely appended to:
- "No project/location collection UI exists in this wizard (never did)" — it
  does now.
- `vertex_gcp_project` is "always written NULL" and `vertex_gcp_location` is
  always `"us-central1"` — both now carry the visitor's verified choice.

Keep the surviving half intact: both remain **DB-only**, never Render env vars.
Per `CLAUDE.md`'s own rule, re-read each whole passage after editing it for
internal consistency, not just the sentence you changed.

- [ ] **Step 3: Log the parked issue**

Add to `ISSUES.md`'s Parked Issues: `/api/llm/confirm` uses a merge write, not
`replace=True`, so a failed re-submit via "Change" leaves the previously
confirmed provider/model/pair in the session while the UI shows the frame
errored. **Why parked:** pre-existing, shared with every other frame's failed
resubmit, and whether `confirm` counts as a "start this frame over" endpoint
under the `replace=True` rule is a separate design question.

- [ ] **Step 4: Full verification**

Run: `uv run pytest -v && uv run ruff check .`
Expected: all green. Then invoke the `deploy-verify` skill — required before any
push to `main`, and a green pytest/ruff run does not substitute for it.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md ISSUES.md
git commit -m "Document the Vertex pair collection and the earlier probe gate"
```

---

## Self-review notes

- **Spec coverage:** §3 → Tasks 5, 6, 7 (allowlist at all three entry points, with a no-client-constructed regression test). §4 → Task 1. §5a → Task 3. §5b → Task 4. §6a → Task 5. §6b → Task 6. §6c → Task 7. §6d → Task 8. §7 → Task 9. §8's parked item → Task 10. §9's skills → Tasks 9 and 10.
- **Type consistency:** `VertexProjectsListed.projects` (Task 4) is what Task 6 unwraps; `list_vertex_models(b64, project, location)` positional order (Task 3) matches Task 6's call; `_seed_provider_config`'s existing five-positional signature (Task 8) is unchanged; `_valid_vertex_location`/`_valid_vertex_project` (Task 5) are used verbatim in Tasks 6 and 7.
- **Known sequencing risk:** Task 2 is blocked until Task 1 is on the bot's `main`. Everything from Task 3 onward depends on Task 2 only through `_VERTEX_LOCATIONS`; Tasks 3 and 4 (`llm_client.py` only) can proceed in parallel with that wait if needed.
