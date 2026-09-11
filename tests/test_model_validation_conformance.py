"""The contract declares which providers need a live entitlement probe before
a model is written; this asserts THIS repo implements exactly that.

Without this test the contract documents the rule and nothing checks we obey
it -- which is the whole difference between a vendored declaration and a
docstring. See pr-review-bot's docs/superpowers/specs/2026-09-11-vertex-model-
entitlement-validation-design.md section 7c.
"""
from __future__ import annotations

import json
from pathlib import Path

import llm_client

_REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((_REPO_ROOT / "contracts/provisioning.json").read_text(encoding="utf-8"))


def test_contract_version_is_understood():
    assert CONTRACT["contract_version"] == 2


def test_a_probe_exists_for_every_provider_that_requires_one():
    for provider, policy in CONTRACT["model_validation"]["providers"].items():
        probe = getattr(llm_client, f"probe_{provider}_model", None)
        if policy["required_before_write"]:
            assert callable(probe), f"{provider} requires a probe and none is implemented"
        else:
            assert probe is None, f"{provider} requires no probe but one exists"


def test_reported_codes_are_exactly_the_declared_ones():
    assert set(llm_client.MODEL_PROBE_ERROR_CODES) == set(
        CONTRACT["model_validation"]["error_codes"]
    )
