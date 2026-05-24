from __future__ import annotations

from neugi_swarm_v2.cli.cli import NeugiCLI


def test_noninteractive_defaults_fallback_to_ollama(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)

    defaults = NeugiCLI._select_noninteractive_llm_defaults()

    assert defaults["provider"] == "ollama"
    assert defaults["model"] == "qwen2.5-coder:7b"
    assert defaults["ollama_url"] == "http://localhost:11434"
    assert defaults["base_url"] == ""
    assert defaults["api_key"] == ""


def test_noninteractive_defaults_prefer_cloud_provider_when_env_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai-key")

    defaults = NeugiCLI._select_noninteractive_llm_defaults()

    assert defaults["provider"] == "openai"
    assert defaults["model"] == "gpt-5.2"
    assert defaults["fallback_model"] == "gpt-5.2-pro"
    assert defaults["base_url"] == "https://api.openai.com"
    assert defaults["ollama_url"] == ""
    assert defaults["api_key"] == "sk-test-openai-key"
