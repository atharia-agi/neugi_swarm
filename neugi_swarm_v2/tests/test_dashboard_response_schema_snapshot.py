"""Snapshot-style response schema checks for critical dashboard endpoints."""

from __future__ import annotations

from types import SimpleNamespace

from dashboard.api import DashboardAPI


def _assert_envelope(payload: dict) -> None:
    assert isinstance(payload, dict)
    assert "status" in payload
    assert "message" in payload
    assert "timestamp" in payload


def test_schema_snapshot_providers_endpoint():
    api = DashboardAPI(SimpleNamespace(swarm=None))
    resp = api.provider_catalog(None, None, {})
    _assert_envelope(resp)
    data = resp["data"]
    assert {"providers", "total"} <= set(data.keys())
    if data["providers"]:
        first = data["providers"][0]
        expected = {"name", "display_name", "models", "runtime_provider", "base_url", "auth_type"}
        assert expected <= set(first.keys())


def test_schema_snapshot_config_endpoint():
    api = DashboardAPI(SimpleNamespace(swarm=None))
    resp = api.get_config(None, None, {})
    _assert_envelope(resp)
    data = resp["data"]
    cfg = data
    assert "llm" in cfg
    assert {"provider", "model", "temperature", "max_tokens"} <= set(cfg["llm"].keys())


def test_schema_snapshot_governance_profile_endpoint():
    api = DashboardAPI(SimpleNamespace(swarm=None))
    resp = api.governance_profile_get(None, None, {})
    _assert_envelope(resp)
    data = resp["data"]
    assert {"profile", "available_profiles", "rules", "stats"} <= set(data.keys())
    assert isinstance(data["available_profiles"], list)
    assert isinstance(data["rules"], list)
    assert isinstance(data["stats"], dict)
