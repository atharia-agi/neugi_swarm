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
            config.llm.api_key = "existing-key"
            server = SimpleNamespace(swarm=SimpleNamespace(config=config))
            api = DashboardAPI(server)

            body = json.dumps({
                "llm": {
                    "provider": "openai",
                    "model": "gpt-5.2",
                    "base_url": "https://api.openai.com",
                    "api_key": "",
                    "temperature": 0.2,
                },
                "neugi_dir": "C:/should-not-change",
            }).encode("utf-8")

            response = api.update_config(None, body, {})

            assert response["status"] == "ok"
            assert config.llm.provider == "openai"
            assert config.llm.model == "gpt-5.2"
            assert config.llm.api_key == "existing-key"
            assert config.llm.max_tokens == 4096
            assert config.neugi_dir == Path(tmpdir)
            config_path = Path(tmpdir) / "config.json"
            saved = json.loads(config_path.read_text(encoding="utf-8"))
            assert saved["llm"]["provider"] == "openai"
            assert saved["llm"]["api_key"] == "existing-key"

    def test_update_config_accepts_new_non_empty_api_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NeugiConfig()
            config.neugi_dir = Path(tmpdir)
            server = SimpleNamespace(swarm=SimpleNamespace(config=config))
            api = DashboardAPI(server)

            body = json.dumps({"llm": {"api_key": "new-key"}}).encode("utf-8")

            response = api.update_config(None, body, {})

            assert response["status"] == "ok"
            assert config.llm.api_key == "new-key"
