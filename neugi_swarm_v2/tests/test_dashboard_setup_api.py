"""Tests for dashboard setup/config API helpers."""

import json
import tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from config import NeugiConfig
from dashboard.api import DashboardAPI
from dashboard.server import DashboardConfig
from llm_provider import LLMResponse


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

    def test_test_llm_config_uses_proposed_provider_without_persisting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NeugiConfig()
            config.neugi_dir = Path(tmpdir)
            config.llm.api_key = "stored-key"
            server = SimpleNamespace(swarm=SimpleNamespace(config=config))
            api = DashboardAPI(server)
            captured = {}

            class FakeProvider:
                def generate(self, **kwargs):
                    captured.update(kwargs)
                    return LLMResponse(content="NEUGI_OK", model=kwargs["model"], usage={"total_tokens": 3})

            def make_provider(llm_data, api_key):
                captured["api_key"] = api_key
                return FakeProvider()

            api._make_test_provider = make_provider

            body = json.dumps({
                "llm": {
                    "provider": "openai",
                    "model": "gpt-5.2",
                    "base_url": "https://api.openai.com",
                }
            }).encode("utf-8")

            response = api.test_llm_config(None, body, {})

            assert response["status"] == "ok"
            assert response["data"]["connected"] is True
            assert response["data"]["sample"] == "NEUGI_OK"
            assert captured["api_key"] == "stored-key"
            assert captured["model"] == "gpt-5.2"
            assert not (Path(tmpdir) / "config.json").exists()

    def test_test_llm_config_requires_cloud_api_key(self):
        server = SimpleNamespace(swarm=SimpleNamespace(config=NeugiConfig()))
        api = DashboardAPI(server)
        body = json.dumps({
            "llm": {
                "provider": "openai",
                "model": "gpt-5.2",
                "base_url": "https://api.openai.com",
            }
        }).encode("utf-8")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "", "NEUGI_LLM_API_KEY": ""}, clear=False):
            response = api.test_llm_config(None, body, {})

        assert response["status"] == "error"
        assert "API key" in response["message"]

    def test_test_llm_config_sanitizes_failed_provider_error(self):
        api = DashboardAPI(SimpleNamespace(swarm=None))

        class FakeProvider:
            def generate(self, **kwargs):
                raise RuntimeError("Authorization: Bearer secret-token rejected")

        api._make_test_provider = lambda llm_data, api_key: FakeProvider()
        body = json.dumps({
            "llm": {
                "provider": "openai",
                "model": "gpt-5.2",
                "base_url": "https://api.openai.com",
                "api_key": "secret-token",
            }
        }).encode("utf-8")

        response = api.test_llm_config(None, body, {})

        assert response["status"] == "ok"
        assert response["data"]["connected"] is False
        assert "secret-token" not in response["data"]["error"]
        assert "Bearer" not in response["data"]["error"]

    def test_dashboard_config_defaults_to_local_no_friction(self):
        config = DashboardConfig()

        assert config.host == "127.0.0.1"
        assert config.enable_auth is False
        assert "*" not in config.cors_origins

    def test_dashboard_config_auto_secures_network_bind(self):
        config = DashboardConfig(host="0.0.0.0", cors_origins=["*"])

        assert config.enable_auth is True
        assert config.api_key
        assert "*" not in config.cors_origins

    def test_approval_queue_lists_pending_requests(self):
        request = SimpleNamespace(
            request_id="req-1",
            agent_id="aurora",
            agent_role="coder",
            action="system_execute_command",
            description="Run a migration",
            cost_estimate=0.25,
            risk_level="high",
            status="pending",
            required_approvals=1,
            approval_count=0,
            metadata={},
            decisions=[],
        )
        gate = SimpleNamespace(
            get_pending_requests=lambda agent_id=None: [request],
            get_stats=lambda: {"pending": 1},
        )
        server = SimpleNamespace(swarm=SimpleNamespace(approval_gate=gate))
        api = DashboardAPI(server)

        response = api.approval_queue(None, None, {})

        assert response["status"] == "ok"
        assert response["data"]["total"] == 1
        item = response["data"]["requests"][0]
        assert item["request_id"] == request.request_id
        assert item["risk_level"] == "high"
        assert item["status"] == "pending"

    def test_approval_decision_approves_request(self):
        request = SimpleNamespace(
            request_id="req-1",
            agent_id="aurora",
            agent_role="coder",
            action="system_execute_command",
            description="",
            cost_estimate=0.0,
            risk_level="high",
            status="approved",
            required_approvals=1,
            approval_count=1,
            metadata={},
            decisions=[],
        )
        gate = SimpleNamespace(
            approve=lambda request_id, approver, reason: request,
            get_pending_requests=lambda agent_id=None: [],
        )
        events = []
        server = SimpleNamespace(
            swarm=SimpleNamespace(approval_gate=gate),
            broadcast_event=lambda event_type, data: events.append((event_type, data)),
        )
        api = DashboardAPI(server)
        body = json.dumps({
            "request_id": request.request_id,
            "decision": "approve",
            "approver": "owner",
        }).encode("utf-8")

        response = api.decide_approval(None, body, {})

        assert response["status"] == "ok"
        assert response["data"]["request"]["status"] == "approved"
        assert events[0][0] == "approval_approved"
