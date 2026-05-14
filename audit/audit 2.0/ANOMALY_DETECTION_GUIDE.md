# Anomaly Detection Guide for External Auditors

## Purpose

This guide helps external auditors systematically identify anomalies, security weaknesses, and operational irregularities in NEUGI Swarm v2.1.3.

---

## 1. Code Quality Anomalies

### What to Check
- **Import issues:** Run `python neugi_swarm_v2/test_import.py` to verify all imports resolve
- **Plugin loading:** Check `neugi_swarm_v2/plugins/` for valid plugin.json manifests
- **Circular dependencies:** Scan for import loops in core modules

### Expected vs Anomalous
| Normal | Anomalous |
|--------|-----------|
| All imports succeed | Missing dependency errors |
| Plugin JSON is valid | Malformed plugin.json |
| Event bus initializes cleanly | Events lost or double-processed |

---

## 2. Security Anomalies

### 2.1 Sandbox Escapes
- Check Docker sandbox config in `neugi_swarm_v2/tools/tool_executor.py`
- Verify resource limits (CPU, memory, network)
- Confirm read-only filesystem mode
- Review `neugi_swarm_v2/security/sandbox.py` for escape mitigations

### 2.2 Authorization Bypass
- Test AuthGate with invalid tokens
- Verify ScopeValidator rejects out-of-scope targets
- Check audit logs for unauthorized access attempts

### 2.3 Secret Exposure
- Search for hardcoded API keys in all .py and .json files
- Verify `.gitignore` excludes `.env`, `neugi_swarm_v2/config.py`, `*.key`
- Check `SecretManager` for plaintext storage

---

## 3. Data Integrity Anomalies

### 3.1 Audit Log Integrity
- Verify hash chain continuity in `AuditLogger`
- Check for timestamp manipulation
- Confirm log rotation does not drop entries

### 3.2 Knowledge Base
- Verify index consistency between Whoosh and vector store
- Check for stale or poisoned embeddings
- Confirm knowledge base directory permissions

---

## 4. Operational Anomalies

### 4.1 Event Bus Health
- **Missing events:** Check if middleware drops events
- **Duplicate events:** Verify idempotency
- **High latency:** Profile middleware pipeline

### 4.2 Memory Leaks
- Check `MemoryMonitor` output for growth patterns
- Profile plugin lifecycle for unreleased resources
- Verify Docker container cleanup after tool execution

---

## 5. Configuration Anomalies

### 5.1 Config Validation
- Check `neugi_swarm_v2/config.py` for undefined defaults
- Verify environment variable fallbacks
- Test with minimal/invalid config files
- Review `neugi_swarm_v2/security/secret_manager.py` for secret handling

### 5.2 Feature Flags
- Verify all new features (observability, plugins) are opt-in
- Check for default-enable of risky features
- Confirm feature gate logic is correct

### 5.3 Governance & Compliance
- Review `neugi_swarm_v2/governance/audit.py` for audit trail integrity
- Check policy enforcement in `neugi_swarm_v2/governance/policy.py`
- Verify budget tracking in `neugi_swarm_v2/governance/budget.py`

---

## 6. Reproducibility Checks

### 6.1 Build Verification
```bash
cd K:\neugi_swarm\repo
python -m pytest tests/ -v
```

### 6.2 Import Verification
```bash
python neugi_swarm_v2/test_import.py
```

### 6.3 Plugin Load Test
```bash
python -c "from neugi_swarm_v2.plugins import PluginRegistry; pr = PluginRegistry(); print(pr.list_plugins())"
```

---

## 7. Red Flag Checklist

| Flag | Severity | Check |
|------|----------|-------|
| Missing .gitignore for secrets | Critical | Scan for committed credentials |
| Docker in privileged mode | Critical | Check executor.py config |
| No TLS on internal WS | High | Check ws_bridge.py |
| Plaintext logging of sensitive data | High | Search for print/logger on secrets |
| Unvalidated plugin paths | Medium | Check `neugi_swarm_v2/tools/plugin_validator.py` |
| No rate limiting | Medium | Review event bus config |
| Stale dependencies | Low | Check pyproject.toml |
| Missing `__init__.py` in packages | Low | Verify all packages have init files |
| No type hints on public APIs | Low | Review core modules |
| Missing docstrings on exported functions | Low | Run pydocstyle |