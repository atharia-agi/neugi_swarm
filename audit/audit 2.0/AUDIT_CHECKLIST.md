# External Auditor Checklist

## Pre-Audit Setup

- [ ] Clone repository: `git clone git@github.com:atharia-agi/neugi_swarm.git`
- [ ] Install Python 3.10+
- [ ] Install Docker Desktop
- [ ] Run `pip install -r requirements.txt` (if available)
- [ ] Verify all imports: `python neugi_swarm_v2/test_import.py`

---

## 1. Code Review

### 1.1 General
- [ ] Check for hardcoded credentials/secrets
- [ ] Verify input validation on all user-facing endpoints
- [ ] Review error handling for information leakage
- [ ] Check logging for sensitive data exposure

### 1.2 Security
- [ ] Review `ScopeValidator` (`plugins/autonomous_security_harness/core/security/scope_validator.py`)
- [ ] Verify `AuthGate` role logic (`plugins/autonomous_security_harness/core/security/auth_gate.py`)
- [ ] Check Docker sandbox configuration (`neugi_swarm_v2/security/sandbox.py`)
- [ ] Review exploit prevention patterns (`neugi_swarm_v2/security/exploit_prevention.py`)
- [ ] Verify audit log immutability (`plugins/autonomous_security_harness/core/security/audit_logger.py`)
- [ ] Review command validator (`neugi_swarm_v2/security/command_validator.py`)
- [ ] Verify secret handling (`neugi_swarm_v2/security/secret_manager.py`)

### 1.3 Architecture
- [ ] Check for circular dependencies
- [ ] Verify event bus middleware chain integrity
- [ ] Review plugin loading isolation
- [ ] Check memory management patterns
- [ ] Verify subsystem wiring (`autonomous/subsystem_wiring.py`)

### 1.4 Governance
- [ ] Review policy enforcement (`governance/policy.py`)
- [ ] Verify budget tracking (`governance/budget.py`)
- [ ] Check approval gate logic (`governance/approval.py`)
- [ ] Audit governance trail (`governance/audit.py`)

---

## 2. Automated Testing

### 2.1 Run Test Suite
```bash
cd repo && python -m pytest tests/ -v
```

### 2.2 Import Verification
```bash
cd repo && python neugi_swarm_v2/test_import.py
```

### 2.3 Plugin Verification
```bash
cd repo && python -c "
from neugi_swarm_v2.plugins import PluginRegistry
pr = PluginRegistry()
for p in pr.list_plugins():
    print(f'Plugin: {p.name} - {p.version} - Status: {p.status}')
"
```

### 2.4 Governance Verification
```bash
cd repo && python -c "
from neugi_swarm_v2.governance import policy, budget, approval, audit
print('Policy:', policy.__version__ if hasattr(policy, '__version__') else 'OK')
print('Budget:', budget.__version__ if hasattr(budget, '__version__') else 'OK')
print('Approval:', approval.__version__ if hasattr(approval, '__version__') else 'OK')
print('Audit:', audit.__version__ if hasattr(audit, '__version__') else 'OK')
"
```

---

## 3. Dynamic Analysis

### 3.1 Security Scanning
- [ ] Run `nuclei` on web endpoints (if deployed)
- [ ] Check Docker images for known vulnerabilities
- [ ] Run dependency vulnerability scanner
- [ ] Static analysis with bandit or semgrep

### 3.2 Penetration Testing
- [ ] Attempt Docker sandbox escape
- [ ] Test scope validation bypass
- [ ] Attempt unauthorized plugin loading
- [ ] Test approval gate bypass
- [ ] Test governance policy enforcement

---

## 4. Observability Check

- [ ] Verify event bus captures all security events
- [ ] Check WebSocket streaming works end-to-end
- [ ] Review dashboard for real-time metrics
- [ ] Verify audit log chain continuity
- [ ] Test event bus persistence and recovery

---

## 5. Compliance Verification

- [ ] Check NIST framework coverage
- [ ] Verify ISO 27001 controls
- [ ] Review OWASP Top 10 mitigations
- [ ] Check PCI-DSS relevant controls
- [ ] Verify GDPR compliance for data handling
- [ ] Verify autonomous agent safety controls

---

## 6. Final Verification

- [ ] All Critical findings addressed
- [ ] All High findings documented
- [ ] Remediation plan exists for open findings
- [ ] Re-validation confirms fixes
- [ ] Final report signed off

---

## Auditor Sign-off

**Auditor Name:** _____________
**Date:** _____________
**Signature:** _____________