# System Architecture Overview for External Auditors

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    CLI Layer                                 │
│    neugi / agent / plugin / config commands                 │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│                  Core Engine                                 │
│  ┌────────────┐ ┌──────────┐ ┌───────────────────┐         │
│  │ Event Bus  │ │ Memory   │ │ Tool Executor      │         │
│  │ (pub/sub)  │ │ (SQLite) │ │ (Docker Sandbox)   │         │
│  └────────────┘ └──────────┘ └───────────────────┘         │
│  ┌────────────┐ ┌──────────┐ ┌───────────────────┐         │
│  │  Gateway   │ │ Learning │ │ Governance        │         │
│  │ (router/   │ │ (skill_  │ │ (policy/budget/   │         │
│  │  heartbeat)│ │  gener-  │ │  audit/approval)  │         │
│  └────────────┘ └──────────┘ └───────────────────┘         │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│                 Plugin System                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐          │
│  │ Cyber Expert │  │ Auto Sec     │  │ Browser  │          │
│  │ (v1.0.0)     │  │ Harness      │  │ Agent    │          │
│  │              │  │ (v1.0.0)     │  │ (v1.0.0) │          │
│  └──────────────┘  └──────────────┘  └──────────┘          │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│                Dashboard (Web)                               │
│  Real-time metrics / Event stream / System status            │
└──────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Plugin Registration Flow
```mermaid
CLI → PluginRegistry → Validate plugin.json → 
Load module → Register tools → Attach event handlers → Ready
```

### Security Tool Execution Flow
```mermaid
User → AuthGate → ScopeValidator → ApprovalGate → 
Docker Sandbox → Tool Executor → Audit Logger → Result
```

---

## Key File Locations

### Core Engine
| File | Purpose |
|------|---------|
| `neugi_swarm_v2/__init__.py` | Package init, version, exports |
| `neugi_swarm_v2/config.py` | Configuration management |
| `neugi_swarm_v2/cli/cli.py` | CLI entry point |
| `neugi_swarm_v2/observability/event_bus.py` | Event bus core |

### Security Infrastructure (Corrected Paths)
| File | Purpose |
|------|---------|
| `neugi_swarm_v2/tools/executor.py` | Tool execution framework |
| `neugi_swarm_v2/tools/plugin_validator.py` | Plugin manifest validation |
| `neugi_swarm_v2/security/command_validator.py` | Command whitelist/blacklist filtering |
| `neugi_swarm_v2/security/exploit_prevention.py` | Pattern-based exploit detection |
| `neugi_swarm_v2/security/sandbox.py` | Docker sandboxed execution |
| `neugi_swarm_v2/security/secret_manager.py` | Secure secret handling |
| `neugi_swarm_v2/plugins/autonomous_security_harness/core/security/scope_validator.py` | Scope validation |
| `neugi_swarm_v2/plugins/autonomous_security_harness/core/security/auth_gate.py` | Authorization gate |
| `neugi_swarm_v2/plugins/autonomous_security_harness/core/security/audit_logger.py` | Immutable audit logging |
| `neugi_swarm_v2/governance/audit.py` | Governance audit module |

### Governance
| File | Purpose |
|------|---------|
| `neugi_swarm_v2/governance/policy.py` | Policy enforcement |
| `neugi_swarm_v2/governance/budget.py` | Budget tracking |
| `neugi_swarm_v2/governance/approval.py` | Approval gate logic |

### Subsystems
| Subsystem | Purpose |
|-----------|---------|
| `gateway/` | Router, heartbeat, device management, cron scheduling |
| `learning/` | Skill generator, pattern tracker, feedback loop |
| `autonomous/` | Research engine, reporter, observer, loop engine |

### Plugins
| File | Purpose |
|------|---------|
| `plugins/cybersecurity_expert/__init__.py` | Cyber Expert plugin |
| `plugins/autonomous_security_harness/__init__.py` | Auto Security Harness |
| `plugins/browser_agent/__init__.py` | Browser automation |

---

## Security Architecture

### Defense in Depth Layers
1. **Network Layer:** Docker network isolation
2. **Application Layer:** Input validation, command filtering
3. **Plugin Layer:** Manifest validation, capability restrictions
4. **Data Layer:** Encrypted secrets, immutable audit logs
5. **Human Layer:** Approval gates for high-risk actions

### Docker Sandbox Configuration
- **Image:** Custom lockdown image (no network by default)
- **Resources:** CPU/Memory limits enforced
- **Filesystem:** Read-only root, tmpfs for /tmp
- **Capabilities:** Dropped all (--cap-drop=ALL)
- **Security:** Seccomp profile, no new privileges

---

## Dependencies

### Runtime
- Python 3.10+
- Docker (for sandboxed tool execution)
- sentence-transformers (for vector search)
- Whoosh (for knowledge base indexing)

### Optional
- PostgreSQL (for LangGraph checkpoints)
- Redis (for distributed event bus)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Initial | Core NEUGI framework |
| 2.0.0 | Major | Plugin system, tool executor |
| 2.1.0 | Update | Event bus, observability |
| 2.1.1 | Update | Security hardening |
| 2.1.2 | Update | Browser agent plugin |
| 2.1.3 | Current | Auto Security Harness + Vector KB |