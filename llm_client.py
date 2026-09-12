"""Thin async wrapper around Gemini, Vertex AI, and Groq's model-listing
calls — used to validate a visitor-supplied credential and discover which
models it can actually reach, without persisting anything server-side.
Gemini and Vertex share one internal helper since both go through the same
google-genai SDK, differing only in how genai.Client is constructed; Groq
uses the official groq SDK directly. See
docs/superpowers/specs/2026-08-27-onboarding-llm-provider-frame-design.md
sections 3-4."""
from __future__ import annotations

import asyncio
import base64
import binascii
import dataclasses
import json

import groq
import httpx
from google import genai
from google.auth import exceptions as google_auth_exceptions
from google.auth.transport import requests as google_auth_requests
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from google.oauth2 import service_account

_VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_VERTEX_LOCATION = "us-central1"
_REQUEST_TIMEOUT_MS = 10_000

# The only values from a visitor-supplied service-account JSON that
# google.oauth2.service_account.Credentials uses to pick the destination of
# its own outbound token-refresh request -- token_uri is required by
# from_service_account_info, universe_domain is optional. Left unpinned, a
# visitor who supplies a matching self-generated private key (they always
# can, since they built the JSON themselves) can fully control where this
# server issues that request: an SSRF via a "paste your service-account key"
# feature. Anything other than Google's real values is rejected outright.
_VERTEX_TOKEN_URI = "https://oauth2.googleapis.com/token"
_VERTEX_UNIVERSE_DOMAIN = "googleapis.com"


@dataclasses.dataclass(frozen=True)
class LlmModelsListed:
    models: list[str]


@dataclasses.dataclass(frozen=True)
class VertexModelsListed:
    project_id: str
    models: list[str]


@dataclasses.dataclass(frozen=True)
class LlmApiFailed:
    reason: str
    # "unauthorized" | "forbidden" | "rate_limited" | "provider_unreachable"
    # | "invalid_service_account_json" (vertex only)


def _strip_model_prefix(name: str) -> str:
    """"models/gemini-flash-latest" -> "gemini-flash-latest";
    "publishers/google/models/gemini-2.5-flash" -> "gemini-2.5-flash" — both
    are resource-name formats google-genai returns; the sibling
    review-engine project's config.py's llm_model/vertex_model fields expect
    the bare id."""
    return name.rsplit("/", 1)[-1]


async def _list_generative_models(client: genai.Client) -> list[str]:
    """Filtered to generateContent-capable models where that capability is
    actually known. Gemini Developer API responses populate
    Model.supported_actions (google/genai/models.py's _Model_from_mldev);
    Vertex responses never do -- _Model_from_vertex has no
    supported_actions mapping at all, verified directly against the
    installed SDK's source, not assumed. A Vertex model therefore always
    has supported_actions=None and is let through rather than dropped --
    dropping it silently empties the entire Vertex catalog regardless of
    credential, which is exactly the bug this check exists to avoid.

    WHAT THIS LIST IS NOT: for Vertex it is essentially the global Model
    Garden, not a per-project entitlement list -- a live listing returns
    veo-*, lyria-* and medgemma entries no ordinary project can call.
    Membership means the credential authenticates, nothing more. Whether
    the project may actually generate with a model is probe_vertex_model's
    question. Treating the two as one fact put a 404-ing model into a
    provisioned deployment in the sibling pr-review-bot project -- see its
    docs/superpowers/specs/2026-09-11-vertex-model-entitlement-validation-
    design.md section 1."""
    names = []
    async for model in await client.aio.models.list():
        if not model.name:
            continue
        if model.supported_actions is not None and "generateContent" not in model.supported_actions:
            continue
        names.append(_strip_model_prefix(model.name))
    return names


def _reason_for_client_error_code(code: int) -> str:
    if code == 401:
        return "unauthorized"
    if code == 403:
        return "forbidden"
    if code == 429:
        return "rate_limited"
    return "provider_unreachable"


async def list_gemini_models(api_key: str) -> LlmModelsListed | LlmApiFailed:
    """Live models-listing call against the Gemini Developer API (AI
    Studio) — doubles as credential validation. Never logs api_key."""
    client = genai.Client(
        api_key=api_key,
        http_options=genai_types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS),
    )
    try:
        models = await _list_generative_models(client)
    except genai_errors.APIError as exc:
        return LlmApiFailed(reason=_reason_for_client_error_code(exc.code))
    except httpx.HTTPError:
        return LlmApiFailed(reason="provider_unreachable")
    finally:
        await client.aio.aclose()
    return LlmModelsListed(models=models)


def _vertex_credentials_and_project(
    service_account_key_b64: str,
) -> tuple[service_account.Credentials, str] | LlmApiFailed:
    """Decode, SSRF-guard, and build credentials from a submitted Vertex
    service-account b64 key. Shared by list_vertex_models and
    probe_vertex_model so the two can never disagree about which
    credential/project a verdict was obtained against, and so the SSRF
    guard on token_uri/universe_domain (see the module-level comment on
    _VERTEX_TOKEN_URI) is written once, not duplicated per caller -- a
    second, slightly-different copy of a load-bearing security check is
    exactly the kind of drift this project's own history warns about.
    Never logs the decoded key or its contents.
    """
    try:
        decoded = base64.b64decode(service_account_key_b64, validate=True)
        info = json.loads(decoded)
        project_id = str(info["project_id"])
    except (binascii.Error, ValueError, KeyError, TypeError):
        return LlmApiFailed(reason="invalid_service_account_json")

    # SSRF guard -- see the module-level comment on _VERTEX_TOKEN_URI. Must
    # run before from_service_account_info() below, which is what actually
    # reads these fields off info and wires them into the credential object.
    submitted_token_uri = info.get("token_uri")
    if submitted_token_uri is not None and submitted_token_uri != _VERTEX_TOKEN_URI:
        return LlmApiFailed(reason="invalid_service_account_json")
    submitted_universe_domain = info.get("universe_domain")
    if submitted_universe_domain not in (None, _VERTEX_UNIVERSE_DOMAIN):
        return LlmApiFailed(reason="invalid_service_account_json")

    try:
        creds = service_account.Credentials.from_service_account_info(info, scopes=_VERTEX_SCOPES)
    except ValueError:
        # google.auth.exceptions.MalformedError subclasses ValueError, so
        # this one clause already covers it.
        return LlmApiFailed(reason="invalid_service_account_json")
    return creds, project_id


async def list_vertex_models(
    service_account_key_b64: str,
    project: str | None = None,
    location: str | None = None,
) -> VertexModelsListed | LlmApiFailed:
    """Live models-listing call against Vertex AI, authenticated as the
    submitted GCP service account. `project`/`location` default to the
    key's own project_id and this module's _VERTEX_LOCATION; a caller that
    already knows the exact provisioning target can override either --
    mirrors probe_vertex_model's own override shape. Never logs the decoded
    key or its contents.

    VertexModelsListed.project_id reports the project actually queried
    (the override when given, else the key's home project), never the
    key's home project unconditionally -- conflating the two is how a
    listing gets attributed to the wrong pair.

    WHAT THIS LIST IS NOT: Vertex's models.list() returns essentially the
    global Model Garden catalog, not a per-project entitlement list --
    membership here means the credential authenticates, nothing more.
    Whether this project may actually generate with a given model is
    probe_vertex_model's question, and only a real call can answer it.
    Treating the two as the same fact is what let a 404-ing model reach a
    provisioned deployment in the sibling pr-review-bot project -- see its
    docs/superpowers/specs/2026-09-11-vertex-model-entitlement-validation-
    design.md section 1.
    """
    result = _vertex_credentials_and_project(service_account_key_b64)
    if isinstance(result, LlmApiFailed):
        return result
    creds, project_id = result
    used_project = project or project_id

    client = genai.Client(
        vertexai=True,
        project=used_project,
        location=location or _VERTEX_LOCATION,
        credentials=creds,
        http_options=genai_types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS),
    )
    try:
        # google-auth's Credentials.refresh() is synchronous (requests-based
        # transport, per this module's own docs/superpowers spec section 6)
        # -- refreshing it here, off the event loop via asyncio.to_thread,
        # means client.aio.models.list() below finds an already-valid token
        # and skips its own internal, un-thread-wrapped synchronous refresh,
        # which would otherwise block this single-process server's event
        # loop for every other concurrent visitor's request for the
        # round-trip's duration. Same reasoning as github_client.py already
        # wrapping its own blocking PyGithub calls in asyncio.to_thread.
        await asyncio.to_thread(creds.refresh, google_auth_requests.Request())
        models = await _list_generative_models(client)
    except genai_errors.APIError as exc:
        return LlmApiFailed(reason=_reason_for_client_error_code(exc.code))
    except google_auth_exceptions.RefreshError:
        # A bad/unauthorized credential fails to refresh its token.
        return LlmApiFailed(reason="unauthorized")
    except google_auth_exceptions.GoogleAuthError:
        # Any other google-auth failure (e.g. a transport error during
        # token refresh) is a connectivity problem, not a bad credential.
        return LlmApiFailed(reason="provider_unreachable")
    except httpx.HTTPError:
        return LlmApiFailed(reason="provider_unreachable")
    finally:
        await client.aio.aclose()
    return VertexModelsListed(project_id=used_project, models=models)


async def list_groq_models(api_key: str) -> LlmModelsListed | LlmApiFailed:
    """Live models-listing call against Groq's OpenAI-compatible API —
    doubles as credential validation. Deliberately unfiltered (spec
    section 2): Groq's Model type carries no capability field to
    distinguish chat-completion models from Whisper/TTS/moderation ones.
    max_retries=0 matches the sibling review-engine project's
    providers/groq.py's documented "no hidden retry layer" convention —
    CLAUDE.md counsels stopping on a 403/429 rather than silently retrying,
    which the SDK's default
    max_retries=2 would otherwise do behind this function's back. Never
    logs api_key."""
    try:
        async with groq.AsyncGroq(api_key=api_key, max_retries=0, timeout=10.0) as client:
            response = await client.models.list()
    except groq.AuthenticationError:
        return LlmApiFailed(reason="unauthorized")
    except groq.PermissionDeniedError:
        return LlmApiFailed(reason="forbidden")
    except groq.RateLimitError:
        return LlmApiFailed(reason="rate_limited")
    except (groq.InternalServerError, groq.APIConnectionError, groq.APITimeoutError):
        return LlmApiFailed(reason="provider_unreachable")
    return LlmModelsListed(models=[m.id for m in response.data])


@dataclasses.dataclass(frozen=True)
class LlmModelProbed:
    model: str


# The only two verdicts a probe may report, published in the sibling
# pr-review-bot project's contracts/provisioning.json (model_validation.
# error_codes) and asserted against it by
# tests/test_model_validation_conformance.py -- kept apart on purpose:
# model_not_callable means the model answered 404 and is unusable here;
# model_probe_unavailable means no verdict was reached (429, 5xx, timeout).
# Collapsing the second into the first would condemn a working model
# because the provider hiccuped, which is the exact class of wrong answer
# this whole mechanism exists to stop giving. Every OTHER LlmApiFailed
# reason a probe can also return (unauthorized, forbidden,
# invalid_service_account_json, provider_unreachable) is a credential/
# transport problem distinct from a model verdict, not a third probe
# outcome -- this tuple names only the two new ones this design introduces.
MODEL_PROBE_ERROR_CODES = ("model_not_callable", "model_probe_unavailable")

# One token of throwaway text: countTokens neither generates nor bills, so
# the content is irrelevant -- only whether the publisher model resolves
# for this project.
_PROBE_CONTENTS = "ping"


def _probe_reason(code: int) -> str:
    """404 means this project may not call the model -- the same answer a
    real generateContent call gives (verified live against production,
    pr-review-bot's design spec section 1a). Anything else means no verdict
    was reached, which is NOT the same answer and must never be reported as
    one. 401/403 keep their normal credential-shaped classification so a
    visitor is told to fix their key, not to pick a different model."""
    if code == 404:
        return "model_not_callable"
    if code in (401, 403):
        return _reason_for_client_error_code(code)
    return "model_probe_unavailable"


async def probe_vertex_model(
    service_account_key_b64: str,
    model: str,
    project: str | None = None,
    location: str | None = None,
) -> LlmModelProbed | LlmApiFailed:
    """Whether `model` is actually callable for this project/location --
    THE question list_vertex_models cannot answer. Vertex's own listing is
    the global Model Garden -- entitlement is enforced only when a request
    names the publisher model -- so membership in it proves the credential
    authenticates and nothing more. countTokens resolves the publisher
    model exactly as generateContent does, for free and without generating
    anything, which makes it the cheapest honest answer available.

    `project`/`location` default to the credential's own embedded
    project_id and this module's fixed _VERTEX_LOCATION -- the same pair
    list_vertex_models would use -- but a caller that already knows the
    exact provisioning target (this wizard always does: it seeds
    slot_config with `location` fixed and `project` left for the deployed
    service to derive from the key itself) can override either so the
    probe verifies the SAME pair that will actually run in production.
    """
    result = _vertex_credentials_and_project(service_account_key_b64)
    if isinstance(result, LlmApiFailed):
        return result
    creds, own_project_id = result

    client = genai.Client(
        vertexai=True,
        project=project or own_project_id,
        location=location or _VERTEX_LOCATION,
        credentials=creds,
        http_options=genai_types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS),
    )
    try:
        # Same proactive off-thread refresh as list_vertex_models, and for
        # the same reason -- google-auth's refresh is synchronous, and
        # skipping this would block the event loop for every other
        # concurrent visitor for the round-trip's duration.
        await asyncio.to_thread(creds.refresh, google_auth_requests.Request())
        await client.aio.models.count_tokens(model=model, contents=_PROBE_CONTENTS)
    except genai_errors.APIError as exc:
        return LlmApiFailed(reason=_probe_reason(exc.code))
    except google_auth_exceptions.RefreshError:
        # A bad/unauthorized credential fails to refresh its token.
        return LlmApiFailed(reason="unauthorized")
    except google_auth_exceptions.GoogleAuthError:
        # Any other google-auth failure during the probe (e.g. a transport
        # error mid-refresh) reached no verdict about the MODEL -- it must
        # not be conflated with "this model doesn't exist here".
        return LlmApiFailed(reason="model_probe_unavailable")
    except httpx.HTTPError:
        return LlmApiFailed(reason="model_probe_unavailable")
    finally:
        await client.aio.aclose()
    return LlmModelProbed(model=model)


async def probe_gemini_model(api_key: str, model: str) -> LlmModelProbed | LlmApiFailed:
    """Whether `model` is callable with this AI-Studio key. Gemini's listing
    IS key-scoped, unlike Vertex's, so this is a narrower guarantee than
    probe_vertex_model's -- but countTokens is free here too, and a verdict
    obtained the same way production actually calls the model beats one
    inferred from a listing."""
    client = genai.Client(
        api_key=api_key,
        http_options=genai_types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS),
    )
    try:
        await client.aio.models.count_tokens(model=model, contents=_PROBE_CONTENTS)
    except genai_errors.APIError as exc:
        return LlmApiFailed(reason=_probe_reason(exc.code))
    except httpx.HTTPError:
        return LlmApiFailed(reason="model_probe_unavailable")
    finally:
        await client.aio.aclose()
    return LlmModelProbed(model=model)
