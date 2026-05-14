# Error Handling Guide

## Common Errors & Solutions

### Import Errors
```
ModuleNotFoundError: No module named 'autonomous'
```
**Solution:** Ensure you're running from the correct directory:
```bash
cd K:\neugi_swarm\repo
python -m neugi_swarm_v2.tests.test_autonomous
```

### Docker Errors
```
docker.errors.DockerException: Error while fetching server API version
```
**Solution:** Ensure Docker Desktop is running.

### Plugin Load Errors
```
PluginValidationError: Invalid plugin.json
```
**Solution:** Verify plugin manifest schema at `docs/PLUGINS.md`.

### Event Bus Errors
```
EventBusError: Middleware chain broken
```
**Solution:** Check middleware configuration in `neugi_swarm_v2/observability/event_bus.py`.

---

## Error Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| E001 | Plugin manifest invalid | Check plugin.json |
| E002 | Docker not available | Start Docker Desktop |
| E003 | Scope violation | Check ScopeValidator config |
| E004 | Auth failed | Verify API keys |
| E005 | Event bus full | Increase buffer size |
| E006 | Memory limit exceeded | Close unused plugins |
| E007 | Checkpoint failed | Enable PostgreSQL |
| E008 | Network timeout | Check proxy/firewall |