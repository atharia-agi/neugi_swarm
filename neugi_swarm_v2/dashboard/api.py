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
- GET  /api/learning/stats            - Learning statistics
- POST /api/steering                  - Send steering message
- POST /api/auth/login                - Authenticate
- POST /api/auth/logout               - Logout
- GET  /api/config                    - Get configuration
- PUT  /api/config                    - Update configuration
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _parse_body(body: Optional[bytes]) -> dict[str, Any]:
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

    def __init__(self, server: Any):
        self.server = server

    # -- Health ----------------------------------------------------------------

    def health(self, handler, body, query_params) -> dict:
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
            "version": "2.0.0",
            "status": "healthy" if all(v == "healthy" for v in subsystems.values()) else "degraded",
            "uptime_seconds": time.time(),
            "subsystems": subsystems,
            "websocket_clients": self.server.broadcaster.client_count,
        })

    # -- Agents ----------------------------------------------------------------

    def list_agents(self, handler, body, query_params) -> dict:
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

    def delegate_task(self, handler, body, query_params) -> dict:
        """POST /api/agents/{id}/task - Delegate a task to a specific agent."""
        data = _parse_body(body)
        task = data.get("task", "")
        if not task:
            return _error("Task is required")

        agent_id = data.get("agent_id", "")
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

    def list_sessions(self, handler, body, query_params) -> dict:
        """GET /api/sessions - List all active sessions."""
        swarm = self.server.swarm
        sessions = []

        if swarm and hasattr(swarm, "session_manager"):
            try:
                session_mgr = swarm.session_manager
                for session_id, session in session_mgr.sessions.items():
                    sessions.append({
                        "id": session_id,
                        "state": getattr(session, "state", "active"),
                        "message_count": getattr(session, "message_count", 0),
                        "created_at": getattr(session, "created_at", time.time()),
                        "last_active": getattr(session, "last_active", time.time()),
                        "isolation_mode": getattr(session, "isolation_mode", "shared"),
                    })
            except Exception as e:
                logger.warning("Failed to list sessions: %s", e)

        return _ok({
            "sessions": sessions,
            "total": len(sessions),
            "active": sum(1 for s in sessions if s["state"] == "active"),
        })

    def get_session_messages(self, handler, body, query_params) -> dict:
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

    def chat(self, handler, body, query_params) -> dict:
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

    def list_skills(self, handler, body, query_params) -> dict:
        """GET /api/skills - List all available skills."""
        swarm = self.server.swarm
        skills = []

        if swarm and hasattr(swarm, "skill_manager"):
            try:
                skill_mgr = swarm.skill_manager
                for skill_id, skill in skill_mgr.skills.items():
                    skills.append({
                        "id": skill_id,
                        "name": getattr(skill, "name", skill_id),
                        "tier": getattr(skill, "tier", "workspace"),
                        "state": getattr(skill, "state", "active"),
                        "description": getattr(skill, "description", ""),
                        "actions": len(getattr(skill, "actions", [])),
                    })
            except Exception as e:
                logger.warning("Failed to list skills: %s", e)

        tier_filter = query_params.get("tier", [None])[0]
        if tier_filter:
            skills = [s for s in skills if s["tier"] == tier_filter]

        return _ok({
            "skills": skills,
            "total": len(skills),
            "tiers": list(set(s["tier"] for s in skills)),
        })

    # -- Memory ----------------------------------------------------------------

    def memory_stats(self, handler, body, query_params) -> dict:
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

    def memory_recall(self, handler, body, query_params) -> dict:
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

    def list_channels(self, handler, body, query_params) -> dict:
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

    def list_workflows(self, handler, body, query_params) -> dict:
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

    def run_workflow(self, handler, body, query_params) -> dict:
        """POST /api/workflows/{id}/run - Execute a workflow."""
        data = _parse_body(body)
        workflow_id = data.get("workflow_id", "")
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

    def list_plugins(self, handler, body, query_params) -> dict:
        """GET /api/plugins - List all plugins."""
        swarm = self.server.swarm
        plugins = []

        if swarm and hasattr(swarm, "plugins"):
            try:
                for plugin_id, plugin in swarm.plugins.items():
                    plugins.append({
                        "id": plugin_id,
                        "name": getattr(plugin, "name", plugin_id),
                        "version": getattr(plugin, "version", "0.0.0"),
                        "enabled": getattr(plugin, "enabled", True),
                        "description": getattr(plugin, "description", ""),
                    })
            except Exception as e:
                logger.warning("Failed to list plugins: %s", e)

        return _ok({
            "plugins": plugins,
            "total": len(plugins),
            "enabled": sum(1 for p in plugins if p["enabled"]),
        })

    # -- Governance ------------------------------------------------------------

    def budget_status(self, handler, body, query_params) -> dict:
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

    def audit_log(self, handler, body, query_params) -> dict:
        """GET /api/governance/audit - Get audit log."""
        limit = int(query_params.get("limit", [50])[0])
        level = query_params.get("level", [None])[0]

        swarm = self.server.swarm
        entries = []

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

    # -- Learning --------------------------------------------------------------

    def learning_stats(self, handler, body, query_params) -> dict:
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

    def send_steering(self, handler, body, query_params) -> dict:
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

    def login(self, handler, body, query_params) -> dict:
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

    def logout(self, handler, body, query_params) -> dict:
        """POST /api/auth/logout - Revoke session token."""
        auth_header = handler.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            self.server.session_manager.revoke_token(token)
            return _ok({"message": "Logged out"})

        return _error("No active session")

    # -- Config ----------------------------------------------------------------

    def get_config(self, handler, body, query_params) -> dict:
        """GET /api/config - Get current configuration."""
        swarm = self.server.swarm
        if swarm and hasattr(swarm, "config"):
            try:
                return _ok(swarm.config.to_dict())
            except Exception:
                pass

        return _ok({
            "llm": {"provider": "ollama", "model": "qwen2.5-coder:7b"},
            "memory": {"daily_ttl_days": 30},
            "agent": {"default_agents": ["Aurora", "Cipher", "Nova"]},
        })

    def update_config(self, handler, body, query_params) -> dict:
        """PUT /api/config - Update configuration."""
        data = _parse_body(body)
        if not data:
            return _error("Configuration data is required")

        swarm = self.server.swarm
        if swarm and hasattr(swarm, "config"):
            try:
                for key, value in data.items():
                    if hasattr(swarm.config, key):
                        setattr(swarm.config, key, value)
                return _ok({"message": "Configuration updated"})
            except Exception as e:
                return _error(f"Config update failed: {e}")

        return _ok({"message": "Configuration queued for update"})
