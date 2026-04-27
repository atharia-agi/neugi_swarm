# NEUGI v2 Plugin Development

## Overview

NEUGI v2 exposes a plugin SDK with 8 lifecycle hooks, manifest-based discovery, and topological dependency resolution.

## Plugin Structure

```
my_plugin/
├── plugin.json       # Manifest
├── __init__.py       # Entry point
├── hooks.py          # Hook implementations
└── README.md         # Documentation
```

## Manifest (plugin.json)

```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "description": "Does something useful",
  "author": "Your Name",
  "requires": {
    "neugi": ">=2.0.0",
    "plugins": ["base_plugin >= 1.0"]
  },
  "hooks": [
    "post_init",
    "pre_command",
    "post_command"
  ],
  "entry_point": "my_plugin:activate"
}
```

## Lifecycle Hooks

| Hook | When Fired | Args |
|------|-----------|------|
| `pre_init` | Before NEUGI initializes | `config` |
| `post_init` | After NEUGI initializes | `assistant` |
| `pre_command` | Before command executes | `command`, `args` |
| `post_command` | After command executes | `command`, `result` |
| `pre_llm` | Before LLM call | `messages`, `model` |
| `post_llm` | After LLM response | `messages`, `response` |
| `pre_tool` | Before tool execution | `tool_name`, `params` |
| `post_tool` | After tool execution | `tool_name`, `result` |

## Example Plugin

```python
# my_plugin/__init__.py
from neugi_swarm_v2.plugins import Plugin, HookContext

class MyPlugin(Plugin):
    def activate(self, context):
        self.logger.info("MyPlugin activated!")

    def post_command(self, ctx: HookContext):
        if ctx.command == "deploy":
            self.send_notification("Deploy completed!")

def activate():
    return MyPlugin()
```

## Installation

```bash
# From directory
neugi plugin install ./my_plugin

# From GitHub
neugi plugin install https://github.com/user/neugi-plugin

# From registry
neugi plugin install my_plugin
```

## Discovery

Plugins are discovered from:
1. Built-in plugins (`neugi_swarm_v2/plugins/builtins/`)
2. User plugins (`~/.neugi/plugins/`)
3. Project plugins (`./.neugi/plugins/`)

## Dependency Resolution

Plugins are loaded in topological order. Circular dependencies raise an error at startup.

```bash
neugi plugin deps --tree
```

## Security

Plugins run in the same process as NEUGI but are subject to:
- Tool allowlist restrictions
- Sandbox path constraints
- Policy engine rules

Critical plugins can be signed and verified:
```bash
neugi plugin verify my_plugin --pubkey key.pem
```

## Best Practices

1. **Minimize hook usage** — Only subscribe to hooks you need
2. **Handle errors gracefully** — Don't crash NEUGI on plugin errors
3. **Log everything** — Use `self.logger` for debug output
4. **Test independently** — Use `neugi plugin test my_plugin`
5. **Version compatibility** — Specify `requires.neugi` accurately
