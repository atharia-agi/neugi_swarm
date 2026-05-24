"""
NEUGI v2 Dashboard API
=======================

REST API endpoints for all NEUGI subsystems. Each method receives the
request handler, raw body bytes, and parsed query parameters.

Endpoints:
- GET  /api/health                    - System health
- GET  /api/agents                    - List agents with status
- POST /api/agents/{id}/task          - Delegate task to agent
- GET  /api/sessions                  - List sessions
- GET  /api/sessions/{id}/messages    - Get session messages
- POST /api/chat                      - Send chat message
- GET  /api/skills                    - List skills
- GET  /api/memory/stats              - Memory statistics
- GET  /api/memory/recall?query=      - Search memory
- GET  /api/channels                  - Channel status
- GET  /api/workflows                 - List workflows
- POST /api/workflows/{id}/run        - Run workflow
- GET  /api/plugins                   - List plugins
- GET  /api/governance/budget         - Budget status
- GET  /api/governance/audit          - Audit log
- GET  /api/governance/approvals      - Pending approval queue
- POST /api/governance/approvals/decide - Approve/reject a request
- GET  /api/learning/stats            - Learning statistics
- POST /api/steering                  - Send steering message
- POST /api/auth/login                - Authenticate
- POST /api/auth/logout               - Logout
- GET  /api/providers                 - Provider and model catalog
- GET  /api/config                    - Get configuration
- PUT  /api/config                    - Update configuration
- POST /api/config/test-llm           - Test a proposed LLM configuration
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import time
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from neugi_swarm_v2 import __version__

logger = logging.getLogger(__name__)


def _parse_body(body: bytes | None) -> dict[str, Any]:
    """Parse JSON request body."""
    if body is None:
        return {}
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _ok(data: Any, message: str = "ok") -> dict[str, Any]:
    """Build a success response."""
    return {
        "status": "ok",
        "message": message,
        "data": data,
        "timestamp": time.time(),
    }


def _error(message: str, code: int = 400) -> dict[str, Any]:
    """Build an error response."""
    return {
        "status": "error",
        "message": message,
        "code": code,
        "timestamp": time.time(),
    }


class DashboardAPI:
    """API handler for dashboard endpoints.

    Each method signature: (handler, body, query_params) -> dict
    """

    _CONFIG_UPDATE_ALLOWLIST: dict[str, Any] = {
        "llm": {
            "provider",
            "model",
            "fallback_model",
            "base_url",
            "ollama_url",
            "api_key",
            "temperature",
            "max_tokens",
            "timeout_seconds",
            "max_retries",
            "retry_delay_seconds",
        },
        "memory": {
            "daily_ttl_days",
            "scoring_recency_weight",
            "scoring_importance_weight",
            "scoring_frequency_weight",
            "scoring_relevance_weight",
            "dreaming_enabled",
            "dreaming_hour",
            "dreaming_consolidation_threshold",
            "enable_fts",
            "enable_vec",
        },
        "skill": {"skill_dirs", "max_skills_in_prompt", "max_tokens_in_prompt", "enable_hot_reload"},
        "agent": {"default_agents", "xp_threshold", "max_level", "heartbeat_interval_seconds"},
        "context": {"max_tokens", "max_chars", "safety_margin"},
        "capability_profile": {
            "name",
            "provider",
            "tier",
            "context_length",
            "supports_tools",
            "supports_vision",
            "supports_json_mode",
            "max_tools_per_call",
            "effective_context_ratio",
            "max_memory_entries",
            "recommended_prompt_tier",
        },
        "observability": {"enabled", "max_history"},
    }

    def __init__(self, server: Any):
        self.server = server

    def _plugin_state_path(self) -> Path:
        neugi_dir = Path.home() / ".neugi"
        neugi_dir.mkdir(parents=True, exist_ok=True)
        return neugi_dir / "plugin_state.json"

    def _load_plugin_state_overrides(self) -> dict[str, bool]:
        path = self._plugin_state_path()
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {}
            data = payload.get("plugins", payload)
            if not isinstance(data, dict):
                return {}
            out: dict[str, bool] = {}
            for key, value in data.items():
                if isinstance(value, bool):
                    out[str(key)] = value
            return out
        except Exception:
            return {}

    def _save_plugin_state_overrides(self, overrides: dict[str, bool]) -> None:
        path = self._plugin_state_path()
        payload = {"plugins": overrides, "updated_at": time.time()}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # -- Health ----------------------------------------------------------------

    def health(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/health - System health check."""
        swarm = self.server.swarm
        subsystems = {}

        if swarm:
            subsystems["memory"] = "healthy"
            subsystems["skills"] = "healthy"
            subsystems["sessions"] = "healthy"
            subsystems["llm"] = "healthy"
            subsystems["agents"] = "healthy"
        else:
            subsystems["memory"] = "not_initialized"
            subsystems["skills"] = "not_initialized"
            subsystems["sessions"] = "not_initialized"
            subsystems["llm"] = "not_initialized"
            subsystems["agents"] = "not_initialized"

        return _ok({
            "version": __version__,
            "status": "healthy" if all(v == "healthy" for v in subsystems.values()) else "degraded",
            "uptime_seconds": max(0.0, time.time() - getattr(self.server, "started_at", time.time())),
            "subsystems": subsystems,
            "websocket_clients": self.server.broadcaster.client_count,
        })

    # -- Agents ----------------------------------------------------------------

    def list_agents(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/agents - List all agents with status."""
        swarm = self.server.swarm
        if not swarm or not hasattr(swarm, "agent_manager"):
            return _ok({
                "agents": [
                    {
                        "id": "aurora",
                        "name": "Aurora",
                        "role": "orchestrator",
                        "status": "idle",
                        "level": 1,
                        "xp": 0,
                        "tasks_completed": 0,
                        "last_active": time.time(),
                    },
                    {
                        "id": "cipher",
                        "name": "Cipher",
                        "role": "analyst",
                        "status": "idle",
                        "level": 1,
                        "xp": 0,
                        "tasks_completed": 0,
                        "last_active": time.time(),
                    },
                    {
                        "id": "nova",
                        "name": "Nova",
                        "role": "creative",
                        "status": "idle",
                        "level": 1,
                        "xp": 0,
                        "tasks_completed": 0,
                        "last_active": time.time(),
                    },
                ],
                "total": 3,
                "active": 0,
                "idle": 3,
            })

        agents = []
        try:
            agent_mgr = swarm.agent_manager
            for agent_id, agent in agent_mgr.agents.items():
                agents.append({
                    "id": agent_id,
                    "name": getattr(agent, "name", agent_id),
                    "role": getattr(agent, "role", "worker"),
                    "status": getattr(agent, "status", "idle"),
                    "level": getattr(agent, "level", 1),
                    "xp": getattr(agent, "xp", 0),
                    "tasks_completed": getattr(agent, "tasks_completed", 0),
                    "last_active": getattr(agent, "last_active", time.time()),
                })
        except Exception as e:
            logger.warning("Failed to list agents: %s", e)

        active = sum(1 for a in agents if a["status"] == "active")
        return _ok({
            "agents": agents,
            "total": len(agents),
            "active": active,
            "idle": len(agents) - active,
        })

    def delegate_task(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/agents/{id}/task - Delegate a task to a specific agent."""
        data = _parse_body(body)
        task = data.get("task", "")
        if not task:
            return _error("Task is required")

        agent_id = data.get("agent_id", "") or query_params.get("id", [""])[0]
        if not agent_id:
            return _error("agent_id is required")

        swarm = self.server.swarm
        if swarm and hasattr(swarm, "agent_manager"):
            try:
                result = swarm.agent_manager.delegate_task(agent_id, task)
                self.server.broadcast_event("task_delegated", {
                    "agent_id": agent_id,
                    "task": task,
                })
                return _ok({"result": result, "agent_id": agent_id})
            except Exception as e:
                return _error(f"Task delegation failed: {e}")

        return _ok({
            "agent_id": agent_id,
            "task": task,
            "status": "queued",
            "task_id": str(uuid.uuid4()),
        })

    # -- Sessions --------------------------------------------------------------

    def list_sessions(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/sessions - List all active sessions."""
        swarm = self.server.swarm
        sessions = []

        if swarm and hasattr(swarm, "session_manager"):
            try:
                session_mgr = swarm.session_manager
                session_items = getattr(session_mgr, "sessions", None)
                if isinstance(session_items, dict):
                    iterable = session_items.items()
                else:
                    iterable = []
                for session_id, session in iterable:
                    sessions.append({
                        "id": session_id,
                        "state": getattr(session, "state", "active"),
                        "message_count": getattr(session, "message_count", 0),
                        "created_at": getattr(session, "created_at", time.time()),
                        "last_active": getattr(session, "last_active", time.time()),
                        "isolation_mode": getattr(session, "isolation_mode", "shared"),
                    })
            except Exception as e:
                logger.debug("Failed to list sessions: %s", e)

        return _ok({
            "sessions": sessions,
            "total": len(sessions),
            "active": sum(1 for s in sessions if s["state"] == "active"),
        })

    def get_session_messages(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/sessions/{id}/messages - Get messages from a session."""
        session_id = query_params.get("id", [""])[0]
        if not session_id:
            return _error("Session ID is required")

        limit = int(query_params.get("limit", [50])[0])
        offset = int(query_params.get("offset", [0])[0])

        swarm = self.server.swarm
        if swarm and hasattr(swarm, "session_manager"):
            try:
                session = swarm.session_manager.sessions.get(session_id)
                if session:
                    transcript = getattr(session, "transcript", [])
                    messages = transcript[offset:offset + limit]
                    return _ok({
                        "session_id": session_id,
                        "messages": messages,
                        "total": len(transcript),
                    })
            except Exception as e:
                logger.warning("Failed to get session messages: %s", e)

        return _ok({
            "session_id": session_id,
            "messages": [],
            "total": 0,
        })

    # -- Chat ------------------------------------------------------------------

    def chat(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/chat - Send a chat message."""
        data = _parse_body(body)
        message = data.get("message", "")
        if not message:
            return _error("Message is required")

        session_id = data.get("session_id")
        streaming = data.get("streaming", False)

        swarm = self.server.swarm
        if swarm and hasattr(swarm, "chat"):
            try:
                response = swarm.chat(message, session_id=session_id, streaming=streaming)
                self.server.broadcast_event("chat_message", {
                    "message": message,
                    "response": response.text if hasattr(response, "text") else str(response),
                    "session_id": session_id,
                })
                return _ok({
                    "response": response.text if hasattr(response, "text") else str(response),
                    "session_id": session_id,
                    "tool_calls": getattr(response, "tool_calls", []),
                })
            except Exception as e:
                logger.exception("Chat error")
                return _error(f"Chat failed: {e}")

        return _ok({
            "response": f"Echo: {message}",
            "session_id": session_id,
            "note": "Swarm not initialized",
        })

    # -- Skills ----------------------------------------------------------------

    def list_skills(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/skills - List all available skills."""
        swarm = self.server.swarm
        skills = []

        if swarm and hasattr(swarm, "skill_manager"):
            try:
                skill_mgr = swarm.skill_manager
                skill_items = getattr(skill_mgr, "skills", None)
                if isinstance(skill_items, dict):
                    iterable = skill_items.items()
                else:
                    iterable = []
                for skill_id, skill in iterable:
                    skills.append({
                        "id": skill_id,
                        "name": getattr(skill, "name", skill_id),
                        "tier": getattr(skill, "tier", "workspace"),
                        "state": getattr(skill, "state", "active"),
                        "description": getattr(skill, "description", ""),
                        "actions": len(getattr(skill, "actions", [])),
                    })
            except Exception as e:
                logger.debug("Failed to list skills: %s", e)

        tier_filter = query_params.get("tier", [None])[0]
        if tier_filter:
            skills = [s for s in skills if s["tier"] == tier_filter]

        return _ok({
            "skills": skills,
            "total": len(skills),
            "tiers": list(set(s["tier"] for s in skills)),
        })

    # -- Memory ----------------------------------------------------------------

    def memory_stats(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/memory/stats - Memory system statistics."""
        swarm = self.server.swarm

        if swarm and hasattr(swarm, "memory"):
            try:
                mem = swarm.memory
                stats = {
                    "total_entries": getattr(mem, "total_entries", 0),
                    "daily_entries": getattr(mem, "daily_entries", 0),
                    "consolidated_entries": getattr(mem, "consolidated_entries", 0),
                    "storage_size_bytes": getattr(mem, "storage_size_bytes", 0),
                    "fts_enabled": getattr(mem, "fts_enabled", False),
                    "vector_enabled": getattr(mem, "vector_enabled", False),
                }
                return _ok(stats)
            except Exception as e:
                logger.warning("Failed to get memory stats: %s", e)

        return _ok({
            "total_entries": 0,
            "daily_entries": 0,
            "consolidated_entries": 0,
            "storage_size_bytes": 0,
            "fts_enabled": False,
            "vector_enabled": False,
        })

    def memory_recall(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/memory/recall?query= - Search memory."""
        query = query_params.get("query", [""])[0]
        if not query:
            return _error("Query parameter is required")

        limit = int(query_params.get("limit", [10])[0])

        swarm = self.server.swarm
        if swarm and hasattr(swarm, "memory"):
            try:
                results = swarm.memory.search(query, limit=limit)
                return _ok({
                    "query": query,
                    "results": results,
                    "count": len(results),
                })
            except Exception as e:
                logger.warning("Memory recall failed: %s", e)

        return _ok({
            "query": query,
            "results": [],
            "count": 0,
        })

    # -- Channels --------------------------------------------------------------

    def list_channels(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/channels - List channel status."""
        swarm = self.server.swarm
        channels = []

        if swarm and hasattr(swarm, "channels"):
            try:
                for channel_id, channel in swarm.channels.items():
                    channels.append({
                        "id": channel_id,
                        "name": getattr(channel, "name", channel_id),
                        "type": getattr(channel, "type", "unknown"),
                        "status": getattr(channel, "status", "disconnected"),
                        "connected_at": getattr(channel, "connected_at", None),
                        "message_count": getattr(channel, "message_count", 0),
                    })
            except Exception as e:
                logger.warning("Failed to list channels: %s", e)

        return _ok({
            "channels": channels,
            "total": len(channels),
            "connected": sum(1 for c in channels if c["status"] == "connected"),
        })

    # -- Workflows -------------------------------------------------------------

    def list_workflows(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/workflows - List all workflows."""
        swarm = self.server.swarm
        workflows = []

        if swarm and hasattr(swarm, "workflows"):
            try:
                for wf_id, wf in swarm.workflows.items():
                    workflows.append({
                        "id": wf_id,
                        "name": getattr(wf, "name", wf_id),
                        "status": getattr(wf, "status", "idle"),
                        "steps": len(getattr(wf, "steps", [])),
                        "last_run": getattr(wf, "last_run", None),
                        "success_count": getattr(wf, "success_count", 0),
                        "failure_count": getattr(wf, "failure_count", 0),
                    })
            except Exception as e:
                logger.warning("Failed to list workflows: %s", e)

        return _ok({
            "workflows": workflows,
            "total": len(workflows),
            "running": sum(1 for w in workflows if w["status"] == "running"),
        })

    def run_workflow(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/workflows/{id}/run - Execute a workflow."""
        data = _parse_body(body)
        workflow_id = data.get("workflow_id", "") or query_params.get("id", [""])[0]
        if not workflow_id:
            return _error("workflow_id is required")

        swarm = self.server.swarm
        if swarm and hasattr(swarm, "workflows"):
            try:
                wf = swarm.workflows.get(workflow_id)
                if wf:
                    result = wf.run()
                    self.server.broadcast_event("workflow_run", {
                        "workflow_id": workflow_id,
                        "status": "completed",
                    })
                    return _ok({"workflow_id": workflow_id, "result": result})
            except Exception as e:
                return _error(f"Workflow execution failed: {e}")

        return _ok({
            "workflow_id": workflow_id,
            "status": "queued",
            "run_id": str(uuid.uuid4()),
        })

    # -- Plugins ---------------------------------------------------------------

    def list_plugins(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/plugins - List all plugins."""
        swarm = self.server.swarm
        plugins = []
        overrides = self._load_plugin_state_overrides()

        if swarm and hasattr(swarm, "plugins"):
            try:
                for plugin_id, plugin in swarm.plugins.items():
                    runtime_enabled = bool(getattr(plugin, "enabled", True))
                    if plugin_id in overrides:
                        runtime_enabled = bool(overrides[plugin_id])
                        try:
                            setattr(plugin, "enabled", runtime_enabled)
                        except Exception:
                            pass
                    plugins.append({
                        "id": plugin_id,
                        "name": getattr(plugin, "name", plugin_id),
                        "version": getattr(plugin, "version", "0.0.0"),
                        "enabled": runtime_enabled,
                        "description": getattr(plugin, "description", ""),
                    })
            except Exception as e:
                logger.warning("Failed to list plugins: %s", e)

        return _ok({
            "plugins": plugins,
            "total": len(plugins),
            "enabled": sum(1 for p in plugins if p["enabled"]),
        })

    def toggle_plugin(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/plugins/toggle - Enable or disable a plugin."""
        data = _parse_body(body)
        plugin_id = str(data.get("plugin_id") or "").strip()
        enabled = data.get("enabled")
        if not plugin_id:
            return _error("plugin_id is required")
        if not isinstance(enabled, bool):
            return _error("enabled must be boolean")

        swarm = self.server.swarm
        if not swarm or not hasattr(swarm, "plugins"):
            return _error("plugin system is unavailable")

        plugins = getattr(swarm, "plugins", {}) or {}
        plugin = plugins.get(plugin_id)
        if plugin is None:
            return _error(f"plugin '{plugin_id}' not found")

        changed = False
        # Prefer explicit lifecycle hooks if available.
        try:
            if enabled:
                if hasattr(plugin, "enable") and callable(plugin.enable):
                    plugin.enable()
                    changed = True
                elif hasattr(plugin, "set_enabled") and callable(plugin.set_enabled):
                    plugin.set_enabled(True)
                    changed = True
                else:
                    setattr(plugin, "enabled", True)
                    changed = True
            else:
                if hasattr(plugin, "disable") and callable(plugin.disable):
                    plugin.disable()
                    changed = True
                elif hasattr(plugin, "set_enabled") and callable(plugin.set_enabled):
                    plugin.set_enabled(False)
                    changed = True
                else:
                    setattr(plugin, "enabled", False)
                    changed = True
        except Exception as e:
            return _error(f"plugin toggle failed: {e}")

        # Best-effort with plugin registry when exposed by swarm.
        try:
            registry = getattr(swarm, "plugin_registry", None)
            if registry:
                if enabled and hasattr(registry, "enable_plugin"):
                    registry.enable_plugin(plugin_id)
                if (not enabled) and hasattr(registry, "disable_plugin"):
                    registry.disable_plugin(plugin_id)
        except Exception:
            # Non-fatal: runtime toggle above already applied.
            pass

        if hasattr(self.server, "broadcast_event"):
            self.server.broadcast_event("plugin_toggled", {
                "plugin_id": plugin_id,
                "enabled": enabled,
            })

        overrides = self._load_plugin_state_overrides()
        overrides[plugin_id] = enabled
        try:
            self._save_plugin_state_overrides(overrides)
        except Exception as e:
            logger.warning("Failed to persist plugin state override for %s: %s", plugin_id, e)

        return _ok({
            "plugin_id": plugin_id,
            "enabled": bool(getattr(plugin, "enabled", enabled)),
            "changed": changed,
        })

    # -- Governance ------------------------------------------------------------

    def budget_status(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/governance/budget - Get budget status."""
        swarm = self.server.swarm

        if swarm and hasattr(swarm, "governance"):
            try:
                gov = swarm.governance
                return _ok({
                    "daily_budget": getattr(gov, "daily_budget", 1000),
                    "daily_spent": getattr(gov, "daily_spent", 0),
                    "daily_remaining": getattr(gov, "daily_remaining", 1000),
                    "monthly_budget": getattr(gov, "monthly_budget", 30000),
                    "monthly_spent": getattr(gov, "monthly_spent", 0),
                    "monthly_remaining": getattr(gov, "monthly_remaining", 30000),
                    "cost_per_token": getattr(gov, "cost_per_token", 0.0),
                    "total_requests": getattr(gov, "total_requests", 0),
                })
            except Exception as e:
                logger.warning("Failed to get budget status: %s", e)

        return _ok({
            "daily_budget": 1000,
            "daily_spent": 0,
            "daily_remaining": 1000,
            "monthly_budget": 30000,
            "monthly_spent": 0,
            "monthly_remaining": 30000,
            "cost_per_token": 0.0,
            "total_requests": 0,
        })

    def audit_log(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/governance/audit - Get audit log."""
        limit = int(query_params.get("limit", [50])[0])
        level = query_params.get("level", [None])[0]

        swarm = self.server.swarm
        entries: list[dict[str, Any]] = []

        if swarm and hasattr(swarm, "governance"):
            try:
                gov = swarm.governance
                audit_entries = getattr(gov, "audit_log", [])
                if level:
                    audit_entries = [e for e in audit_entries if e.get("level") == level]
                entries = audit_entries[-limit:]
            except Exception as e:
                logger.warning("Failed to get audit log: %s", e)

        return _ok({
            "entries": entries,
            "total": len(entries),
        })

    def approval_queue(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/governance/approvals - List pending approval requests."""
        try:
            gate = self._get_approval_gate()
            agent_id = query_params.get("agent_id", [None])[0] if query_params else None
            pending = gate.get_pending_requests(agent_id=agent_id)
            stats: dict[str, Any] = {}
            if hasattr(gate, "get_stats"):
                try:
                    stats = gate.get_stats() or {}
                except Exception:
                    stats = {}
            return _ok({
                "requests": [self._serialize_approval_request(req) for req in pending],
                "total": len(pending),
                "stats": stats,
            })
        except Exception as e:
            logger.debug("Approval queue unavailable: %s", e)
            return _ok({
                "requests": [],
                "total": 0,
                "stats": {},
                "unavailable_reason": str(e),
            })

    def decide_approval(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/governance/approvals/decide - Approve or reject an action."""
        data = _parse_body(body)
        request_id = str(data.get("request_id") or "").strip()
        decision = str(data.get("decision") or "").strip().lower()
        approver = str(data.get("approver") or "dashboard").strip()
        reason = str(data.get("reason") or "").strip()
        if not request_id:
            return _error("request_id is required")
        if decision not in {"approve", "approved", "reject", "rejected"}:
            return _error("decision must be approve or reject")

        try:
            gate = self._get_approval_gate()
            if decision.startswith("approve"):
                request = gate.approve(request_id, approver=approver, reason=reason)
                event_type = "approval_approved"
            else:
                request = gate.reject(request_id, approver=approver, reason=reason)
                event_type = "approval_rejected"
            if hasattr(self.server, "broadcast_event"):
                self.server.broadcast_event(event_type, {
                    "request_id": request_id,
                    "approver": approver,
                    "reason": reason,
                })
            return _ok({"request": self._serialize_approval_request(request)})
        except Exception as e:
            return _error(f"Approval decision failed: {e}")

    def governance_profile_get(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/governance/profile - Get active governance risk profile and rules."""
        try:
            gate = self._get_approval_gate()
            profile = self._load_governance_profile_from_config()
            rules = []
            if hasattr(gate, "list_rules"):
                for r in gate.list_rules(enabled_only=False):
                    rules.append({
                        "rule_id": getattr(r, "rule_id", ""),
                        "name": getattr(r, "name", ""),
                        "action_type": getattr(r, "action_type", "*"),
                        "agent_role": getattr(r, "agent_role", "*"),
                        "min_risk": self._enum_value(getattr(r, "min_risk", "")),
                        "approval_count": getattr(r, "approval_count", 1),
                        "timeout_minutes": getattr(r, "timeout_minutes", 60),
                        "enabled": bool(getattr(r, "enabled", True)),
                    })
            stats = gate.get_stats() if hasattr(gate, "get_stats") else {}
            return _ok({
                "profile": profile,
                "available_profiles": ["startup", "team", "enterprise"],
                "rules": rules,
                "stats": stats or {},
            })
        except Exception as e:
            return _error(f"Failed to get governance profile: {e}", code=500)

    def governance_profile_set(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/governance/profile - Apply and persist governance risk profile."""
        data = _parse_body(body)
        profile = str(data.get("profile") or "team").strip().lower()
        force = bool(data.get("force", False))
        if profile not in {"startup", "team", "enterprise"}:
            return _error("profile must be one of: startup, team, enterprise")
        try:
            gate = self._get_approval_gate()
            if not hasattr(gate, "apply_risk_profile"):
                return _error("Approval gate does not support profile application", code=500)
            result = gate.apply_risk_profile(profile=profile, force=force)
            self._persist_governance_profile_to_config(profile)
            stats = gate.get_stats() if hasattr(gate, "get_stats") else {}
            if hasattr(self.server, "broadcast_event"):
                self.server.broadcast_event("governance_profile", {
                    "profile": profile,
                    "applied": bool(result.get("applied")),
                    "force": force,
                })
            return _ok({
                "profile": profile,
                "result": result,
                "stats": stats or {},
            }, message="Governance profile updated")
        except Exception as e:
            return _error(f"Failed to set governance profile: {e}", code=500)

    def governance_profile_preview(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/governance/profile/preview - Preview risk profile rule diff."""
        data = _parse_body(body)
        profile = str(data.get("profile") or "team").strip().lower()
        if profile not in {"startup", "team", "enterprise"}:
            return _error("profile must be one of: startup, team, enterprise")
        try:
            gate = self._get_approval_gate()
            current_rules = []
            if hasattr(gate, "list_rules"):
                for r in gate.list_rules(enabled_only=False):
                    current_rules.append({
                        "name": getattr(r, "name", ""),
                        "min_risk": self._enum_value(getattr(r, "min_risk", "")),
                        "approval_count": int(getattr(r, "approval_count", 1) or 1),
                        "enabled": bool(getattr(r, "enabled", True)),
                    })
            preview = gate.preview_risk_profile(profile) if hasattr(gate, "preview_risk_profile") else {
                "profile": profile,
                "rules": [],
                "rule_count": 0,
            }
            return _ok({
                "current": {"rule_count": len(current_rules), "rules": current_rules},
                "preview": preview,
                "delta_rule_count": int(preview.get("rule_count", 0)) - len(current_rules),
            })
        except Exception as e:
            return _error(f"Failed to preview governance profile: {e}", code=500)

    # -- Learning --------------------------------------------------------------

    def learning_stats(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/learning/stats - Learning system statistics."""
        swarm = self.server.swarm

        if swarm and hasattr(swarm, "learning"):
            try:
                learning = swarm.learning
                return _ok({
                    "total_patterns": getattr(learning, "total_patterns", 0),
                    "active_patterns": getattr(learning, "active_patterns", 0),
                    "confidence_avg": getattr(learning, "confidence_avg", 0.0),
                    "sessions_analyzed": getattr(learning, "sessions_analyzed", 0),
                    "skills_discovered": getattr(learning, "skills_discovered", 0),
                    "last_analysis": getattr(learning, "last_analysis", None),
                })
            except Exception as e:
                logger.warning("Failed to get learning stats: %s", e)

        return _ok({
            "total_patterns": 0,
            "active_patterns": 0,
            "confidence_avg": 0.0,
            "sessions_analyzed": 0,
            "skills_discovered": 0,
            "last_analysis": None,
        })

    # -- Steering --------------------------------------------------------------

    def send_steering(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/steering - Send a steering message."""
        data = _parse_body(body)
        message = data.get("message", "")
        if not message:
            return _error("Message is required")

        priority = data.get("priority", "normal")
        session_id = data.get("session_id")

        swarm = self.server.swarm
        if swarm and hasattr(swarm, "session_manager"):
            try:
                swarm.session_manager.steer(
                    message=message,
                    priority=priority,
                    session_id=session_id,
                )
                self.server.broadcast_event("steering", {
                    "message": message,
                    "priority": priority,
                })
                return _ok({"message": "Steering message sent"})
            except Exception as e:
                return _error(f"Steering failed: {e}")

        return _ok({
            "message": "Steering message queued",
            "priority": priority,
        })

    # -- Auth ------------------------------------------------------------------

    def login(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/auth/login - Authenticate and get a session token."""
        data = _parse_body(body)
        api_key = data.get("api_key", "")

        if self.server.config.api_key and api_key != self.server.config.api_key:
            return _error("Invalid API key", 401)

        token = self.server.session_manager.create_token()
        return _ok({
            "token": token,
            "expires_in": self.server.config.session_token_ttl,
        })

    def logout(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/auth/logout - Revoke session token."""
        auth_header = handler.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            self.server.session_manager.revoke_token(token)
            return _ok({"message": "Logged out"})

        return _error("No active session")

    # -- Config ----------------------------------------------------------------

    def provider_catalog(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/providers - Provider and model catalog for dashboard setup."""
        try:
            from neugi_swarm_v2.provider_catalog import (
                default_fallback_model,
                get_all_providers,
                provider_to_runtime,
            )

            providers = []
            for provider in get_all_providers():
                provider_data = asdict(provider) if is_dataclass(provider) else dict(provider)
                models = list(provider_data.get("models", []))
                if not any(str(m.get("id", "")).strip().lower() == "custom" for m in models if isinstance(m, dict)):
                    models.append({
                        "id": "custom",
                        "name": "Custom Model",
                        "description": "Use any model id supported by this provider.",
                        "context_window": 4096,
                        "max_output": 4096,
                        "supports_tools": True,
                        "supports_vision": False,
                        "tier": "medium",
                        "status": "custom",
                    })
                provider_data["models"] = models
                runtime_provider = provider_to_runtime(provider_data.get("name", ""))
                provider_data["runtime_provider"] = runtime_provider
                provider_data["default_fallback_model"] = default_fallback_model(runtime_provider)
                providers.append(provider_data)

            return _ok({
                "providers": providers,
                "total": len(providers),
            })
        except Exception as e:
            logger.warning("Provider catalog unavailable: %s", e)
            return _ok({"providers": [], "total": 0, "error": str(e)})

    def provider_health(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/providers/health - Lightweight provider readiness summary."""
        try:
            from neugi_swarm_v2.provider_catalog import get_all_providers

            items: list[dict[str, Any]] = []
            for provider in get_all_providers():
                env_vars = list(getattr(provider, "env_vars", []) or [])
                has_env_key = any(bool(os.environ.get(env_var, "").strip()) for env_var in env_vars)
                needs_api_key = str(getattr(provider, "auth_type", "bearer_header")).strip().lower() != "none"
                ready = (not needs_api_key) or has_env_key
                items.append({
                    "provider": provider.name,
                    "display_name": provider.display_name,
                    "category": provider.category,
                    "models_count": len(getattr(provider, "models", []) or []),
                    "needs_api_key": needs_api_key,
                    "has_env_key": has_env_key,
                    "ready": ready,
                })

            ready_count = sum(1 for item in items if item["ready"])
            return _ok({
                "providers": items,
                "ready_count": ready_count,
                "total": len(items),
            })
        except Exception as e:
            logger.warning("Provider health unavailable: %s", e)
            return _ok({"providers": [], "ready_count": 0, "total": 0, "error": str(e)})

    def get_config(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/config - Get current configuration."""
        swarm = self.server.swarm
        if swarm and hasattr(swarm, "config"):
            try:
                config_data = swarm.config.to_dict()
                llm_data = config_data.get("llm", {})
                raw_key = str(llm_data.get("api_key") or "")
                if raw_key:
                    llm_data["api_key"] = "********"
                    llm_data["api_key_masked"] = True
                else:
                    llm_data["api_key_masked"] = False
                config_data["llm"] = llm_data
                return _ok(config_data)
            except Exception:
                pass

        inferred_provider = "openai_compatible"
        inferred_model = ""
        inferred_base_url = ""
        inferred_fallback = ""
        if os.environ.get("OPENAI_API_KEY"):
            inferred_provider = "openai"
            inferred_model = "gpt-5-mini"
            inferred_fallback = "gpt-4.1-mini"
            inferred_base_url = "https://api.openai.com"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            inferred_provider = "anthropic"
            inferred_model = "claude-3-5-haiku-20241022"
            inferred_fallback = "claude-3-5-haiku-20241022"
            inferred_base_url = "https://api.anthropic.com"
        elif os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            inferred_provider = "gemini"
            inferred_model = "gemini-2.5-flash"
            inferred_fallback = "gemini-2.5-flash"
            inferred_base_url = "https://generativelanguage.googleapis.com/v1beta/openai"

        return _ok({
            "llm": {
                "provider": inferred_provider,
                "model": inferred_model,
                "fallback_model": inferred_fallback,
                "base_url": inferred_base_url,
                "ollama_url": "http://localhost:11434",
                "temperature": 0.7,
                "max_tokens": 4096,
                "api_key_masked": False,
            },
            "memory": {"daily_ttl_days": 30},
            "agent": {"default_agents": ["Aurora", "Cipher", "Nova"]},
        })

    def update_config(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """PUT /api/config - Update configuration."""
        data = _parse_body(body)
        if not data:
            return _error("Configuration data is required")

        swarm = self.server.swarm
        if swarm and hasattr(swarm, "config"):
            try:
                self._handle_api_key_update(swarm.config, data)
                self._apply_llm_defaults(data)
                self._merge_config(swarm.config, data, self._CONFIG_UPDATE_ALLOWLIST)
                saved_path = self._persist_config(swarm.config)
                config_data = swarm.config.to_dict() if hasattr(swarm.config, "to_dict") else {}
                llm_data = config_data.get("llm", {}) if isinstance(config_data, dict) else {}
                raw_key = str(llm_data.get("api_key") or "")
                if raw_key:
                    llm_data["api_key"] = "********"
                    llm_data["api_key_masked"] = True
                else:
                    llm_data["api_key_masked"] = False
                if isinstance(config_data, dict):
                    config_data["llm"] = llm_data
                return _ok({
                    "message": "Configuration updated",
                    "saved_path": str(saved_path) if saved_path else None,
                    "config": config_data,
                })
            except Exception as e:
                return _error(f"Config update failed: {e}")

        return _ok({"message": "Configuration queued for update"})

    def test_llm_config(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/config/test-llm - Test a proposed LLM provider setup."""
        data = _parse_body(body)
        llm_data = data.get("llm", data)
        if not isinstance(llm_data, dict):
            return _error("LLM configuration is required")
        self._apply_llm_defaults({"llm": llm_data})

        provider_name = str(llm_data.get("provider") or "").strip() or "ollama"
        model = str(llm_data.get("model") or "").strip()
        if not model:
            return _error("Model is required")

        api_key = str(llm_data.get("api_key") or "").strip()
        if not api_key:
            api_key = self._resolve_existing_api_key(provider_name)

        if provider_name != "ollama" and not api_key:
            return _error("API key is required to test this provider", code=400)
        if provider_name in {"openai_compatible", "anthropic_compatible"} and not str(llm_data.get("base_url") or "").strip():
            return _error("Base URL is required for custom providers", code=400)

        try:
            provider = self._make_test_provider(llm_data, api_key)
            started = time.monotonic()
            response = provider.generate(
                prompt="Reply with exactly: NEUGI_OK",
                system_prompt="You are testing a provider connection. Reply with exactly NEUGI_OK.",
                model=model,
                temperature=0,
                max_tokens=16,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            text = getattr(response, "content", "") or ""
            return _ok({
                "provider": provider_name,
                "model": getattr(response, "model", model) or model,
                "connected": True,
                "latency_ms": latency_ms,
                "sample": text[:120],
                "usage": getattr(response, "usage", {}) or {},
            }, message="Provider connection verified")
        except Exception as e:
            error_type = "unknown"
            try:
                error_type = provider.classify_error(e).value  # type: ignore[name-defined]
            except Exception:
                pass
            logger.info("LLM provider test failed for %s/%s: %s", provider_name, model, type(e).__name__)
            remediation = self._provider_error_remediation(provider_name, error_type, e)
            return _ok({
                "provider": provider_name,
                "model": model,
                "connected": False,
                "error_type": error_type,
                "error": self._sanitize_provider_error(e),
                "remediation": remediation,
            }, message="Provider connection failed")

    def _merge_config(self, target: Any, updates: dict[str, Any], allowlist: Any) -> None:
        """Recursively merge dashboard config updates into dataclass config."""
        for key, value in updates.items():
            if isinstance(allowlist, dict):
                if key not in allowlist:
                    continue
                allowed_child = allowlist[key]
            elif isinstance(allowlist, set):
                if key not in allowlist:
                    continue
                allowed_child = None
            else:
                continue

            if key == "api_key" and (value == "" or value == "********"):
                continue
            if not hasattr(target, key):
                continue
            current = getattr(target, key)
            if isinstance(value, dict) and hasattr(current, "__dataclass_fields__") and isinstance(allowed_child, set):
                self._merge_config(current, value, allowed_child)
            else:
                setattr(target, key, value)

    def _persist_config(self, config: Any) -> Path | None:
        """Persist updated config to ~/.neugi/config.json when possible."""
        if not hasattr(config, "to_dict"):
            return None

        neugi_dir = getattr(config, "neugi_dir", None) or (Path.home() / ".neugi")
        config_path = Path(neugi_dir) / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = config.to_dict()
        # Never persist API keys in plaintext config.
        if isinstance(data, dict):
            llm_data = data.setdefault("llm", {})
            if isinstance(llm_data, dict):
                llm_data["api_key"] = ""
        config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return config_path

    def _handle_api_key_update(self, config: Any, updates: dict[str, Any]) -> None:
        """Store dashboard-submitted API key in SecretManager and keep config plaintext empty."""
        llm_data = updates.get("llm")
        if not isinstance(llm_data, dict):
            return
        submitted = str(llm_data.get("api_key") or "").strip()
        if not submitted or submitted == "********":
            return

        from neugi_swarm_v2.security.secret_manager import SecretClass, SecretManager

        neugi_dir = getattr(config, "neugi_dir", None) or (Path.home() / ".neugi")
        secrets_db = Path(neugi_dir) / "secrets.db"
        if not os.environ.get("NEUGI_MASTER_KEY", "").strip():
            raise ValueError(
                "NEUGI_MASTER_KEY is required before storing API keys securely. "
                "Set NEUGI_MASTER_KEY and retry."
            )
        manager = SecretManager(db_path=str(secrets_db))
        try:
            manager.add_secret(
                name="llm_api_key",
                value=submitted,
                secret_class=SecretClass.API_KEY,
                description="Primary LLM provider API key",
            )
        except Exception:
            manager.update_secret(name="llm_api_key", value=submitted)

        # Avoid retaining plaintext key in runtime config and persisted JSON.
        if hasattr(config, "llm"):
            setattr(config.llm, "api_key", "")
        llm_data["api_key"] = "********"

    def _make_test_provider(self, llm_data: dict[str, Any], api_key: str):
        """Build a runtime provider from proposed dashboard settings."""
        from neugi_swarm_v2.llm_provider import (
            AnthropicCompatibleProvider,
            OllamaProvider,
            OpenAICompatibleProvider,
            ProviderConfig,
            ProviderType,
        )
        from neugi_swarm_v2.provider_catalog import get_provider, normalize_base_url

        provider_name = str(llm_data.get("provider") or "ollama").strip()
        catalog_provider = get_provider(provider_name)
        compatibility = getattr(catalog_provider, "compatibility", "") if catalog_provider else ""
        ptype = ProviderType.OLLAMA
        if provider_name in {"anthropic", "anthropic_compatible"} or compatibility == "anthropic":
            ptype = ProviderType.ANTHROPIC_COMPATIBLE
        elif provider_name != "ollama":
            ptype = ProviderType.OPENAI_COMPATIBLE

        base_url = str(llm_data.get("base_url") or "").strip()
        if ptype == ProviderType.OLLAMA:
            base_url = str(llm_data.get("ollama_url") or base_url or "http://localhost:11434")
        elif not base_url and catalog_provider:
            base_url = catalog_provider.get_base_url()

        cfg = ProviderConfig(
            provider_type=ptype,
            base_url=normalize_base_url(base_url),
            api_key=api_key,
            default_model=str(llm_data.get("model") or "").strip(),
            fallback_model=str(llm_data.get("fallback_model") or "").strip(),
            timeout=min(max(int(float(llm_data.get("timeout_seconds", 20))), 3), 30),
            max_retries=1,
            retry_delay=0.25,
        )
        if ptype == ProviderType.OLLAMA:
            return OllamaProvider(cfg)
        if ptype == ProviderType.ANTHROPIC_COMPATIBLE:
            return AnthropicCompatibleProvider(cfg)
        return OpenAICompatibleProvider(cfg)

    def _apply_llm_defaults(self, updates: dict[str, Any]) -> None:
        """Normalize/complete LLM payload before merge/test."""
        llm_data = updates.get("llm")
        if not isinstance(llm_data, dict):
            return
        provider_name = str(llm_data.get("provider") or "ollama").strip() or "ollama"
        fallback = str(llm_data.get("fallback_model") or "").strip()
        if fallback:
            return
        try:
            from neugi_swarm_v2.provider_catalog import default_fallback_model, provider_to_runtime

            runtime_provider = provider_to_runtime(provider_name)
            computed = default_fallback_model(runtime_provider)
            if computed:
                llm_data["fallback_model"] = computed
        except Exception:
            # Keep payload unchanged on catalog lookup failures.
            pass

    def _resolve_existing_api_key(self, provider_name: str) -> str:
        """Resolve an already configured API key without exposing it to the UI."""
        swarm = self.server.swarm
        if swarm and hasattr(swarm, "_resolve_api_key"):
            try:
                return swarm._resolve_api_key()
            except Exception:
                pass

        if swarm and hasattr(swarm, "config"):
            try:
                value = getattr(getattr(swarm.config, "llm", None), "api_key", "")
                if value:
                    return value
            except Exception:
                pass

        try:
            from neugi_swarm_v2.provider_catalog import get_provider

            provider_info = get_provider(provider_name)
            env_vars = getattr(provider_info, "env_vars", []) if provider_info else []
            for env_var in env_vars:
                value = os.environ.get(env_var, "")
                if value:
                    return value
        except Exception:
            pass
        return ""

    def _sanitize_provider_error(self, error: Exception) -> str:
        """Return a useful provider error without leaking credentials."""
        text = str(error) or type(error).__name__
        for marker in ("Authorization:", "Bearer ", "x-api-key:"):
            if marker in text:
                text = text.split(marker)[0].rstrip()
        text = re.sub(r"(?i)\b(sk-[A-Za-z0-9\-_]{10,}|xox[baprs]-[A-Za-z0-9\-]{10,}|ghp_[A-Za-z0-9]{10,})\b", "[REDACTED]", text)
        text = re.sub(r"(?i)\b(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[^'\"\s,;]{6,}['\"]?", r"\1=[REDACTED]", text)
        if len(text) > 300:
            text = text[:300].rstrip() + "..."
        return text or type(error).__name__

    def _provider_error_remediation(self, provider_name: str, error_type: str, error: Exception) -> list[str]:
        provider_label = provider_name or "provider"
        lowered = (str(error) or "").lower()
        steps: list[str] = []
        if "certificate_verify_failed" in lowered or "ssl" in lowered:
            steps.extend([
                "Your environment is blocking TLS trust. Disable SSL inspection/proxy MITM for API domains.",
                "Install/update system root certificates, then retry Test Provider.",
                f"If this is a corporate network, ask IT to trust the upstream CA for {provider_label} endpoints.",
            ])
            return steps
        if error_type in {"auth_error"} or "401" in lowered or "403" in lowered or "unauthorized" in lowered:
            steps.extend([
                f"Check API key for {provider_label}.",
                "Verify Base URL matches provider documentation.",
                "Retry with Setup -> Test Provider before saving.",
            ])
            return steps
        if error_type in {"network_error", "timeout_error"} or "timed out" in lowered or "refused" in lowered:
            steps.extend([
                "Check network connectivity and firewall egress.",
                "Validate Base URL and provider status page.",
                "Try another provider from Setup to confirm local environment health.",
            ])
            return steps
        steps.extend([
            "Re-check provider/model/base URL in Setup.",
            "Run Test Provider again and inspect error_type.",
            "If still failing, run `neugi doctor --json --strict` and share report.",
        ])
        return steps

    def _get_approval_gate(self):
        """Resolve or create the approval gate backing the dashboard queue."""
        swarm = self.server.swarm
        candidates = []
        if swarm is not None:
            candidates.extend([
                getattr(swarm, "approval_gate", None),
                getattr(getattr(swarm, "governance", None), "approval_gate", None),
                getattr(swarm, "governance", None),
            ])
        for candidate in candidates:
            if candidate and hasattr(candidate, "get_pending_requests"):
                return candidate

        cached = getattr(self.server, "_approval_gate", None)
        if cached is not None:
            return cached

        from neugi_swarm_v2.governance import ApprovalGate

        neugi_dir = Path.home() / ".neugi"
        if swarm is not None and hasattr(swarm, "config"):
            neugi_dir = Path(getattr(swarm.config, "neugi_dir", neugi_dir))
        db_path = neugi_dir / "data" / "governance.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.server._approval_gate = ApprovalGate(db_path=str(db_path))
        return self.server._approval_gate

    def _load_governance_profile_from_config(self) -> str:
        """Read governance profile from ~/.neugi/config.json with fallback."""
        neugi_dir = Path.home() / ".neugi"
        swarm = self.server.swarm
        if swarm is not None and hasattr(swarm, "config"):
            neugi_dir = Path(getattr(swarm.config, "neugi_dir", neugi_dir))
        config_path = neugi_dir / "config.json"
        if not config_path.exists():
            return "team"
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            profile = str((payload.get("governance") or {}).get("profile") or "team").strip().lower()
            if profile in {"startup", "team", "enterprise"}:
                return profile
        except Exception:
            pass
        return "team"

    def _persist_governance_profile_to_config(self, profile: str) -> Path:
        """Persist governance profile to ~/.neugi/config.json."""
        neugi_dir = Path.home() / ".neugi"
        swarm = self.server.swarm
        if swarm is not None and hasattr(swarm, "config"):
            neugi_dir = Path(getattr(swarm.config, "neugi_dir", neugi_dir))
        config_path = neugi_dir / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        gov = data.get("governance")
        if not isinstance(gov, dict):
            gov = {}
            data["governance"] = gov
        gov["profile"] = profile
        config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return config_path

    def _serialize_approval_request(self, request: Any) -> dict[str, Any]:
        """Serialize an approval request for dashboard rendering."""
        decisions = []
        for decision in getattr(request, "decisions", []) or []:
            decisions.append({
                "approver": getattr(decision, "approver", ""),
                "decision": getattr(decision, "decision", ""),
                "reason": getattr(decision, "reason", ""),
                "timestamp": self._iso(getattr(decision, "timestamp", None)),
            })
        return {
            "request_id": getattr(request, "request_id", ""),
            "agent_id": getattr(request, "agent_id", ""),
            "agent_role": getattr(request, "agent_role", ""),
            "action": getattr(request, "action", ""),
            "description": getattr(request, "description", ""),
            "cost_estimate": getattr(request, "cost_estimate", 0.0),
            "risk_level": self._enum_value(getattr(request, "risk_level", "")),
            "status": self._enum_value(getattr(request, "status", "")),
            "rule_id": getattr(request, "rule_id", ""),
            "required_approvals": getattr(request, "required_approvals", 1),
            "approval_count": getattr(request, "approval_count", 0),
            "timeout_at": self._iso(getattr(request, "timeout_at", None)),
            "created_at": self._iso(getattr(request, "created_at", None)),
            "metadata": getattr(request, "metadata", {}) or {},
            "decisions": decisions,
        }

    def _enum_value(self, value: Any) -> str:
        return getattr(value, "value", value) or ""

    def _iso(self, value: Any) -> str | None:
        return value.isoformat() if hasattr(value, "isoformat") else value

    # -- Autonomous Loop -------------------------------------------------------

    def benchmark_results(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/benchmarks - List benchmark results."""
        try:
            results_dir = Path(__file__).parent.parent / "evals" / "results"
            if results_dir.exists():
                benchmarks = []
                for f in sorted(results_dir.glob("*.json"), reverse=True)[:20]:
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        benchmarks.append({
                            "file": f.name,
                            "benchmark_name": data.get("benchmark_name", ""),
                            "version": data.get("version", ""),
                            "success_rate": data.get("success_rate", 0),
                            "total_duration": data.get("total_duration", 0),
                            "task_count": len(data.get("results", [])),
                            "timestamp": data.get("timestamp", ""),
                        })
                    except Exception:
                        pass
                return _ok({
                    "benchmarks": benchmarks,
                    "total": len(benchmarks),
                })
        except Exception:
            pass
        return _ok({"benchmarks": [], "total": 0, "note": "No benchmark results available"})

    def autonomous_status(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/autonomous/status - Live autonomous loop state."""
        swarm = self.server.swarm
        if not swarm or not hasattr(swarm, "autonomous_loop") or swarm.autonomous_loop is None:
            return _ok({
                "enabled": False,
                "state": "not_initialized",
                "message": "Autonomous loop is not active",
            })

        try:
            status = swarm.autonomous_loop.get_live_status()
            return _ok(status)
        except Exception as e:
            return _error(f"Failed to get autonomous status: {e}", code=500)

    # -- Observability -----------------------------------------------------------

    def observability_status(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/observability/status - Event bus status and metrics."""
        try:
            from neugi_swarm_v2.observability.event_bus import get_event_bus
            bus = get_event_bus()
            history = bus.get_history()
            event_counts: dict[str, int] = {}
            for e in history:
                event_counts[e.name] = event_counts.get(e.name, 0) + 1

            subscriber_counts = {}
            with bus._lock:
                for name, subs in bus._subscribers.items():
                    subscriber_counts[name] = len(subs)
                middleware_count = len(bus._middleware)

            return _ok({
                "enabled": True,
                "total_events": len(history),
                "subscribers": subscriber_counts,
                "middleware_count": middleware_count,
                "event_counts": event_counts,
                "max_history": bus._max_history,
            })
        except Exception as e:
            return _ok({
                "enabled": False,
                "error": str(e),
                "message": "Observability system not available",
            })

    # -- Local Runtime Controls -------------------------------------------------

    def autostart_status(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """GET /api/runtime/autostart - Get autostart status for current user."""
        mode, path = self._autostart_artifact()
        return _ok({
            "enabled": path.exists(),
            "mode": mode,
            "path": str(path),
            "platform": platform.system(),
        })

    def autostart_update(self, handler: Any, body: bytes | None, query_params: dict[str, list[str]]) -> dict[str, Any]:
        """POST /api/runtime/autostart - Enable/disable autostart for current user."""
        data = _parse_body(body)
        action = str(data.get("action", "")).strip().lower()
        if action not in {"enable", "disable"}:
            return _error("action must be 'enable' or 'disable'")

        mode, path = self._autostart_artifact()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            if action == "enable":
                if mode == "windows":
                    path.write_text("@echo off\r\nneugi start\r\n", encoding="utf-8")
                elif mode == "macos":
                    logs_dir = Path.home() / ".neugi" / "logs"
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.neugi.autostart</string>
  <key>ProgramArguments</key>
  <array><string>/bin/sh</string><string>-lc</string><string>neugi start</string></array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{str(logs_dir / "autostart.out.log")}</string>
  <key>StandardErrorPath</key><string>{str(logs_dir / "autostart.err.log")}</string>
</dict>
</plist>
"""
                    path.write_text(plist, encoding="utf-8")
                else:
                    desktop = """[Desktop Entry]
Type=Application
Version=1.0
Name=NEUGI Autostart
Comment=Start NEUGI at login
Exec=sh -lc 'neugi start'
Terminal=false
X-GNOME-Autostart-enabled=true
"""
                    path.write_text(desktop, encoding="utf-8")
            else:
                if path.exists():
                    path.unlink()

            return _ok({
                "enabled": action == "enable",
                "mode": mode,
                "path": str(path),
            }, message=f"Autostart {action}d")
        except Exception as e:
            return _error(f"Failed to update autostart: {e}", code=500)

    def _autostart_artifact(self) -> tuple[str, Path]:
        """Resolve current-user autostart file path."""
        system = platform.system()
        if system == "Windows":
            startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            return "windows", startup_dir / "neugi-start.cmd"
        if system == "Darwin":
            return "macos", Path.home() / "Library" / "LaunchAgents" / "com.neugi.autostart.plist"
        return "linux", Path.home() / ".config" / "autostart" / "neugi.desktop"
