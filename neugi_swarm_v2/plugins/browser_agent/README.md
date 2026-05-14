# Browser Agent Plugin

This plugin demonstrates how to create a browser automation agent using NEUGI's plugin system and the existing BrowserTool.

## Features

- Uses the existing `BrowserTool` for web automation
- Implements a `BrowserAgent` class that extends `TypedAgent` for LLM-driven browser control
- Provides an alternative reasoning-loop implementation
- Includes usage examples

## Installation

The plugin is built-in and available at `neugi_swarm_v2/plugins/browser_agent/`.

To use it, simply import and activate it in your NEUGI setup:

```python
from neugi_swarm_v2.plugins.browser_agent import BrowserAgentPlugin

# Or activate via the plugin system
# neugi plugin install ./plugins/browser_agent
```

## Usage

### Basic BrowserAgent

```python
from neugi_swarm_v2 import NeugiSwarmV2
from neugi_swarm_v2.plugins.browser_agent import BrowserAgent

# Initialize NEUGI
swarm = NeugiSwarmV2()

# Create a browser agent
browser_agent = BrowserAgent(
    llm_callback=swarm._llm_call,  # Use NEUGI's LLM caller
    browser_tool=swarm.browser_tool  # Use NEUGI's browser tool
)

# Use the agent to perform a task
result = browser_agent.run("Go to google.com and search for 'NEUGI Swarm'")
print(result)
```

### Alternative Reasoning Loop

```python
from neugi_swarm_v2.plugins.browser_agent import BrowserAgentImpl

# Initialize with your LLM and browser tool
agent = BrowserAgentImpl(
    llm_callback=your_llm_function,
    browser_tool=your_browser_tool_instance
)

# Run a task
result = agent.run("Extract all product prices from amazon.com/laptops")
```

## How It Works

The plugin leverages NEUGI's existing infrastructure:
- `BrowserTool` for low-level browser automation (Playwright-based)
- `TypedAgent` for LLM-driven tool usage with schema validation
- NEUGI's plugin system for easy integration without core modifications

## Extending

To create your own browser-based plugin:
1. Follow the plugin structure in `PLUGINS.md`
2. Use `BrowserTool` from `neugi_swarm_v2.tools.browser`
3. Implement your agent logic using `TypedAgent` or custom reasoning loops
4. Register any needed hooks in your plugin manifest

## Requirements

- NEUGI Swarm v2.1.1 or higher
- A working LLM provider (configured in NEUGI)
- Playwright dependencies (installed with NEUGI)

## Notes

- The browser agent requires an active browser context (managed by NEUGI's BrowserTool)
- For headless operation, ensure your environment supports it
- The plugin is designed as an example - production agents may need additional error handling and configuration