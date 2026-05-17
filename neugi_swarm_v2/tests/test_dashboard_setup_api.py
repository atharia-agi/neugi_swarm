"""Tests for dashboard setup/config API helpers."""

import json
import tempfile
from types import SimpleNamespace
from pathlib import Path

from config import NeugiConfig
from dashboard.api import DashboardAPI


class TestDashboardSetupAPI:
    def test_provider_catalog_returns_models(self):
        api = DashboardAPI(SimpleNamespace(swarm=None))

        response = api.provider_catalog(None, None, {})

        assert response["status"] == "ok"
        assert response["data"]["total"] > 0
        providers = response["data"]["providers"]
        assert any(provider["name"] == "openai" for provider in providers)
        assert any(provider.get("models") for provider in providers)

    def test_update_config_merges_nested_llm_and_persists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NeugiConfig()
            config.neugi_dir = Path(tmpdir)
            server = SimpleNamespace(swarm=SimpleNamespace(config=config))
            api = DashboardAPI(server)

            body = json.dumps({
                "llm": {
                    "provider": "openai",
                    "model": "gpt-5.2",
                    "base_url": "https://api.openai.com",
                    "api_key": "test-key",
                    "temperature": 0.2,
                }
            }).encode("utf-8")

            response = api.update_config(None, body, {})

            assert response["status"] == "ok"
            assert config.llm.provider == "openai"
            assert config.llm.model == "gpt-5.2"
            assert config.llm.max_tokens == 4096
            config_path = Path(tmpdir) / "config.json"
            saved = json.loads(config_path.read_text(encoding="utf-8"))
            assert saved["llm"]["provider"] == "openai"
            assert saved["llm"]["api_key"] == "test-key"
