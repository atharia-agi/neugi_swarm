# Audit Findings Template

## Finding #[NUMBER]

**Severity:** [Critical/High/Medium/Low/Info]
**Status:** [Open/In Progress/Resolved/False Positive]
**Discoverer:** [Name]
**Date Found:** [YYYY-MM-DD]

---

### Description
[Clear, concise description of the finding]

### Location
- **File:** [path/to/file.py:line_number]
- **Module:** [module name]
- **Component:** [component name]

### Evidence
```
[Relevant code snippet, log output, or command output]
```

### Impact
- **Confidentiality:** [None/Low/Medium/High/Critical]
- **Integrity:** [None/Low/Medium/High/Critical]  
- **Availability:** [None/Low/Medium/High/Critical]
- **CVSS Score:** [0.0-10.0]

### Reproduction Steps
1. [Step 1]
2. [Step 2]
3. [Step 3]

### Root Cause
[Analysis of what causes this issue]

### Recommendation
[Suggested fix or mitigation]

---

## Anomaly Categories

| Category | Description | Examples |
|----------|-------------|----------|
| A-CODE | Code quality issue | Dead code, missing error handling |
| A-SEC | Security vulnerability | Injection, auth bypass |
| A-CONF | Configuration issue | Hardcoded secrets, misconfig |
| A-PERF | Performance issue | Memory leak, slow query |
| A-ARCH | Architecture issue | Circular deps, tight coupling |
| A-DATA | Data integrity issue | Missing validation, corruption |

---

## Severity Definitions

| Severity | Definition | Response Time |
|----------|------------|---------------|
| Critical | Immediate risk of compromise | 24 hours |
| High | Significant security gap | 72 hours |
| Medium | Notable weakness | 1 week |
| Low | Minor issue | 1 month |
| Info | Suggestion | Next release |