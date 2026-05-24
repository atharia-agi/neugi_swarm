"""Tests for provider catalog names mapping to runtime adapters."""

import pytest

from neugi_swarm_v2 import NeugiSwarmV2
from neugi_swarm_v2.config import NeugiConfig
from neugi_swarm_v2.llm_provider import AnthropicCompatibleProvider, OpenAICompatibleProvider


def _swarm_with_provider(provider: str) -> NeugiSwarmV2:
    swarm = object.__new__(NeugiSwarmV2)
    swarm.config = NeugiConfig()
    swarm.config.llm.provider = provider
    swarm.config.llm.model = "test-model"
    swarm.config.llm.base_url = "https://example.com"
    return swarm


def test_anthropic_compatible_uses_anthropic_adapter():
    swarm = _swarm_with_provider("anthropic_compatible")

    provider = swarm._create_llm_provider()

    assert isinstance(provider, AnthropicCompatibleProvider)


def test_openrouter_uses_openai_compatible_adapter():
    swarm = _swarm_with_provider("openrouter")

    provider = swarm._create_llm_provider()

    assert isinstance(provider, OpenAICompatibleProvider)


@pytest.mark.parametrize(
    "provider_name",
    [
        "nvidia_nim",
        "together",
        "fireworks",
        "cerebras",
    ],
)
def test_new_cloud_providers_use_openai_compatible_adapter(provider_name: str):
    swarm = _swarm_with_provider(provider_name)

    provider = swarm._create_llm_provider()

    assert isinstance(provider, OpenAICompatibleProvider)
