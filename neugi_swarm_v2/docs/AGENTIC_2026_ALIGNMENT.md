# NEUGI Agentic 2026 Alignment

> Updated: 2026-05-16
> Scope: Jan-May 2026 agentic runtime patterns, MCP, A2A, skills, tracing, sandboxing, and durable execution.

## External Baseline

NEUGI should track these 2026 ecosystem expectations:

- OpenAI Agents SDK: model-native agent harness, MCP tools, skills, AGENTS.md, shell/apply-patch style execution, built-in tracing, snapshotting, and rehydration for long-running work.
  Source: https://openai.com/index/the-next-evolution-of-the-agents-sdk/
- OpenAI Agents SDK tracing: explicit spans for agents, handoffs, tools, generations, guardrails, custom spans, and MCP tool listing.
  Source: https://openai.github.io/openai-agents-python/ref/tracing/
- MCP current transport direction: Streamable HTTP is the modern request/response transport and includes session identity via `Mcp-Session-Id`; legacy HTTP+SSE is retained only where clients need event streams.
  Source: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- MCP governance: MCP has moved into the Linux Foundation Agentic AI Foundation alongside AGENTS.md, with registry and newer spec work around async operations, statelessness, server identity, and extensions.
  Source: https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation
- Google ADK: production agents need modular code, deployable runtimes, MCP toolsets, and distributed/container-aware MCP connections.
  Source: https://google.github.io/adk-docs/tools-custom/mcp-tools/
- CrewAI: MCP servers are now a first-class tool source for crew-style multi-agent systems.
  Source: https://docs.crewai.com/en/mcp/overview
- Provider UX baseline: model catalogs must be curated from official provider docs where possible, but runtime must preserve custom provider/base URL/model entry because model availability changes faster than releases.
  Sources: https://platform.openai.com/docs/models, https://docs.anthropic.com/en/docs/about-claude/models/all-models, https://ai.google.dev/models/gemini, https://console.groq.com/docs/models, https://docs.mistral.ai/models, https://docs.x.ai/developers/models, https://api-docs.deepseek.com/quick_start/pricing/, https://openrouter.ai/docs/guides/overview/models

## NEUGI Contracts

These are non-negotiable runtime contracts for v2.1.3+:

1. `NeugiSwarmV2.chat()` must return a `StructuredResponse` by default and must not depend on stale v2.0 constructor names.
2. `NeugiConfig` must be a real dataclass instance, not a class with unresolved `Field` defaults.
3. Version metadata must be consistent across `__init__.py`, `tools/__init__.py`, `pyproject.toml`, docs, and installer banners.
4. Prompt assembly must inject real skills and memory rather than empty placeholders.
5. OpenAI-compatible providers must normalize base URLs so `/v1` is not appended twice.
6. MCP HTTP responses must expose `Mcp-Session-Id` for modern clients while preserving SSE event subscriptions.
7. Any tool execution exposed through MCP, chat, or autonomous loops must pass through validation, approval, sandboxing, audit, and observability where available.
8. Autonomous activity must remain idle-gated, rate-limited, circuit-broken, and inspectable through dashboard/status APIs.
9. Provider setup must be simple by default: pick provider, enter API key, search/select model. Custom provider, base URL, API key, and model must remain available for power users.
10. Curated provider catalogs must not invent model IDs. Preview aliases are allowed only when the source documents them, and users can override them.
11. Install paths must converge: website one-liners, GitHub raw scripts, and local development must install the same package and launch the same `neugi wizard` flow.

## Current Implementation Status

| Area | Status | Notes |
|------|--------|-------|
| Structured chat facade | Wired | `assistant.py` updated to v2.1.3 APIs |
| Config dataclass integrity | Wired | `NeugiConfig` restored as dataclass |
| Version sync | Wired | Core version now matches 2.1.3 |
| Prompt memory/skills injection | Wired | `NeugiSwarmV2` now injects loaded skills and high-value memory |
| Provider/model setup UX | Wired | `GeniusWizard` uses a curated provider catalog, API-key prompt, searchable model list, and custom endpoint path |
| Provider endpoint normalization | Wired | OpenAI-compatible URL builder handles standard `/v1/chat/completions` plus Gemini OpenAI-compatible shape |
| Install path parity | Wired | Unix one-liner installs `neugi_swarm_v2` from `~/neugi_swarm`; Windows one-liner uses PowerShell `install.ps1` |
| MCP session header | Wired | HTTP/SSE responses include `Mcp-Session-Id` |
| Streamable HTTP full parity | Partial | JSON-RPC over HTTP exists; resumable streams and full spec negotiation remain next-step work |
| Trace spans across all agent/tool/handoff events | Partial | Event bus exists; OpenAI-style span taxonomy should be layered on top |
| Snapshot/rehydration for arbitrary long-running agents | Partial | Session/workflow checkpoints exist; full container rehydration contract remains roadmap |

## Next Implementation Targets

1. Add live provider model listing using each provider's `/models` endpoint when an API key is present, falling back to the curated catalog offline.
2. Add an OpenTelemetry-compatible trace adapter over `observability.EventBus`.
3. Add resumable Streamable HTTP streams with event IDs and replay windows.
4. Add signed agent identity for A2A/MCP calls before cross-process delegation.
5. Route all assistant default tools through `ToolExecutor` instead of local direct calls.
6. Add integration tests for `NeugiSwarmV2.chat()` with fake LLM, fake tool call, memory save, and session persistence.
7. Add docs MCP resource endpoints that expose this file, architecture docs, and live capability status as read-only agent authoring context.
