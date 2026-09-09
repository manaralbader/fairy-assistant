"""fairy.llm.config.get_client is the one place a route name turns into a
concrete client. These tests prove the whole "switchable by config, not by
code" claim: the only thing that changes between a sim result and a real
result is what's in the environment."""

from __future__ import annotations

import pytest

from fairy.llm.config import get_client
from fairy.llm.openai_compat import OpenAICompatClient
from fairy.llm.sim import SimClient


def test_no_env_keys_resolves_to_the_simulator():
    client = get_client("commercial", env={})
    assert isinstance(client, SimClient)
    assert client.tier == "commercial"


def test_open_weight_route_resolves_to_the_matching_sim_tier():
    client = get_client("open_weight", env={})
    assert isinstance(client, SimClient)
    assert client.tier == "open_weight"


def test_a_real_key_resolves_to_the_real_adapter_with_no_code_change():
    env = {
        "FAIRY_COMMERCIAL_API_KEY": "fake-key-for-this-test-only",
        "FAIRY_COMMERCIAL_BASE_URL": "https://example.invalid/v1",
        "FAIRY_COMMERCIAL_MODEL": "some-model",
    }
    client = get_client("commercial", env=env)
    assert isinstance(client, OpenAICompatClient)
    assert client.model == "some-model"
    assert client.route == "commercial"


def test_a_key_without_base_url_or_model_fails_loudly_rather_than_guessing():
    with pytest.raises(RuntimeError):
        get_client("commercial", env={"FAIRY_COMMERCIAL_API_KEY": "x"})


def test_unknown_route_is_rejected():
    with pytest.raises(ValueError):
        get_client("nonsense", env={})
