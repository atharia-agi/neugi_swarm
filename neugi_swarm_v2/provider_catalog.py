"""
NEUGI v2 provider and model catalog.

This module is a curated setup aid, not a hard restriction. Users can pick any
custom provider, base URL, API key, or model name from the wizard.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelInfo:
    """Info about a model that is suitable for the setup wizard."""

    id: str
    name: str
    description: str = ""
    context_window: int = 4096
    max_output: int = 4096
    supports_tools: bool = True
    supports_vision: bool = False
    tier: str = "medium"  # local / medium / cloud
    status: str = "stable"  # stable / preview / local / custom


@dataclass
class ProviderInfo:
    """Info about a provider NEUGI can configure."""

    name: str
    display_name: str
    category: str = ""
    api_endpoint: str = ""
    base_url: str = ""
    auth_type: str = "bearer_header"
    auth_header: str = "Authorization"
    auth_format: str = "Bearer <API_KEY>"
    env_vars: list[str] = field(default_factory=list)
    api_key_url: str = ""
    model_list_url: str = ""
    compatibility: str = "openai"  # openai / anthropic / ollama / custom
    notes: str = ""
    models: list[ModelInfo] = field(default_factory=list)

    def get_base_url(self) -> str:
        """Return the base URL expected by NEUGI providers.

        OpenAI-compatible providers append ``/v1/chat/completions`` at runtime,
        so catalog base URLs intentionally omit a trailing ``/v1``.
        """
        return normalize_base_url(self.base_url or endpoint_to_base_url(self.api_endpoint))


def normalize_base_url(url: str) -> str:
    """Normalize a URL for NEUGI's provider adapters."""
    cleaned = (url or "").strip().rstrip("/")
    for suffix in ("/v1/chat/completions", "/chat/completions", "/v1/messages", "/messages"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
    if cleaned.endswith("/v1"):
        cleaned = cleaned[:-3]
    return cleaned.rstrip("/")


def endpoint_to_base_url(endpoint: str) -> str:
    """Best-effort endpoint to base URL conversion."""
    cleaned = (endpoint or "").strip().rstrip("/")
    for marker in ("/v1/chat/completions", "/chat/completions", "/v1/messages", "/messages"):
        if marker in cleaned:
            return cleaned.split(marker)[0]
    return cleaned.rsplit("/", 1)[0] if "/" in cleaned else cleaned


DEFAULT_PROVIDERS: list[ProviderInfo] = [
    ProviderInfo(
        name="ollama",
        display_name="Ollama (Local)",
        category="local",
        base_url="http://localhost:11434",
        auth_type="none",
        compatibility="ollama",
        notes="Local, private, offline once models are downloaded.",
        models=[
            ModelInfo("qwen2.5-coder:7b", "Qwen 2.5 Coder 7B", "Best default local coding agent.", 32768, 8192, True, False, "medium", "local"),
            ModelInfo("qwen3:8b", "Qwen 3 8B", "Strong local reasoning and chat.", 32768, 8192, True, False, "medium", "local"),
            ModelInfo("llama3.1:8b", "Llama 3.1 8B", "Balanced general local model.", 131072, 8192, True, False, "medium", "local"),
            ModelInfo("llama3.2:3b", "Llama 3.2 3B", "Small fallback for low-memory machines.", 131072, 8192, True, False, "local", "local"),
            ModelInfo("llama3.3:70b", "Llama 3.3 70B", "Powerful local/server model when hardware allows.", 131072, 32768, True, False, "cloud", "local"),
            ModelInfo("deepseek-r1:14b", "DeepSeek R1 14B", "Local reasoning-oriented model.", 64000, 16000, True, False, "medium", "local"),
            ModelInfo("mistral:7b", "Mistral 7B", "Fast general local model.", 32768, 8192, True, False, "medium", "local"),
        ],
    ),
    ProviderInfo(
        name="openai",
        display_name="OpenAI",
        category="US",
        api_endpoint="https://api.openai.com/v1/chat/completions",
        base_url="https://api.openai.com",
        env_vars=["OPENAI_API_KEY"],
        api_key_url="https://platform.openai.com/api-keys",
        model_list_url="https://api.openai.com/v1/models",
        notes="Frontier agentic, coding, multimodal, realtime, and deep-research models.",
        models=[
            ModelInfo("gpt-5.2", "GPT-5.2", "Best default for coding and agentic tasks.", 400000, 128000, True, True, "cloud"),
            ModelInfo("gpt-5.2-pro", "GPT-5.2 Pro", "More precise high-compute GPT-5.2 variant.", 400000, 128000, True, True, "cloud"),
            ModelInfo("gpt-5-mini", "GPT-5 Mini", "Fast and cost-efficient GPT-5 family model.", 400000, 128000, True, True, "medium"),
            ModelInfo("gpt-5-nano", "GPT-5 Nano", "Lowest-cost GPT-5 family option.", 400000, 128000, True, False, "local"),
            ModelInfo("gpt-4.1", "GPT-4.1", "Strong non-reasoning model with tools.", 1000000, 32768, True, True, "cloud"),
            ModelInfo("gpt-4.1-mini", "GPT-4.1 Mini", "Affordable tool-capable model.", 1000000, 32768, True, True, "medium"),
            ModelInfo("o3-deep-research", "o3 Deep Research", "Specialized deep research model.", 200000, 32768, True, False, "cloud"),
        ],
    ),
    ProviderInfo(
        name="anthropic",
        display_name="Anthropic Claude",
        category="US",
        api_endpoint="https://api.anthropic.com/v1/messages",
        base_url="https://api.anthropic.com",
        auth_type="header_api_key",
        auth_header="x-api-key",
        auth_format="x-api-key: <API_KEY>",
        env_vars=["ANTHROPIC_API_KEY"],
        api_key_url="https://console.anthropic.com/settings/keys",
        compatibility="anthropic",
        notes="Claude API with strong coding, tool use, and long-context reasoning.",
        models=[
            ModelInfo("claude-opus-4-1-20250805", "Claude Opus 4.1", "Highest Claude intelligence and coding capability.", 200000, 32000, True, True, "cloud"),
            ModelInfo("claude-sonnet-4-20250514", "Claude Sonnet 4", "Excellent balance for agents and complex chat.", 200000, 64000, True, True, "cloud"),
            ModelInfo("claude-3-7-sonnet-20250219", "Claude 3.7 Sonnet", "Extended-thinking Sonnet generation.", 200000, 64000, True, True, "cloud"),
            ModelInfo("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", "Fast, lower-cost Claude.", 200000, 8192, True, True, "medium"),
        ],
    ),
    ProviderInfo(
        name="gemini",
        display_name="Google Gemini",
        category="US",
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        env_vars=["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        api_key_url="https://aistudio.google.com/app/apikey",
        model_list_url="https://generativelanguage.googleapis.com/v1beta/models",
        notes="Configured through Google's OpenAI-compatible endpoint for NEUGI.",
        models=[
            ModelInfo("gemini-3-pro-preview", "Gemini 3 Pro Preview", "Google's top multimodal agentic model.", 1048576, 65536, True, True, "cloud", "preview"),
            ModelInfo("gemini-2.5-pro", "Gemini 2.5 Pro", "Strong thinking model for hard coding/reasoning.", 1048576, 65536, True, True, "cloud"),
            ModelInfo("gemini-2.5-flash", "Gemini 2.5 Flash", "Best price-performance Gemini model.", 1048576, 65536, True, True, "medium"),
            ModelInfo("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite", "Low-latency high-throughput option.", 1048576, 65536, True, True, "medium"),
        ],
    ),
    ProviderInfo(
        name="grok",
        display_name="xAI Grok",
        category="US",
        api_endpoint="https://api.x.ai/v1/chat/completions",
        base_url="https://api.x.ai",
        env_vars=["XAI_API_KEY", "GROK_API_KEY"],
        api_key_url="https://console.x.ai/",
        model_list_url="https://api.x.ai/v1/models",
        notes="OpenAI-compatible xAI API. Search tools are needed for realtime events.",
        models=[
            ModelInfo("grok-4.3", "Grok 4.3", "Recommended current xAI chat/agentic model.", 1000000, 32768, True, True, "cloud"),
            ModelInfo("grok-4.3-latest", "Grok 4.3 Latest", "Alias that follows the latest 4.3 release.", 1000000, 32768, True, True, "cloud"),
        ],
    ),
    ProviderInfo(
        name="deepseek",
        display_name="DeepSeek",
        category="CN",
        api_endpoint="https://api.deepseek.com/v1/chat/completions",
        base_url="https://api.deepseek.com",
        env_vars=["DEEPSEEK_API_KEY"],
        api_key_url="https://platform.deepseek.com/api_keys",
        notes="OpenAI-compatible. V4 model names supersede chat/reasoner aliases.",
        models=[
            ModelInfo("deepseek-v4-pro", "DeepSeek V4 Pro", "Frontier reasoning/coding model.", 1000000, 384000, True, False, "cloud"),
            ModelInfo("deepseek-v4-flash", "DeepSeek V4 Flash", "Fast V4 model with thinking mode.", 1000000, 384000, True, False, "medium"),
            ModelInfo("deepseek-chat", "DeepSeek Chat", "Compatibility alias for non-thinking mode.", 64000, 8192, True, False, "medium"),
            ModelInfo("deepseek-reasoner", "DeepSeek Reasoner", "Compatibility alias for thinking mode.", 64000, 8192, True, False, "cloud"),
        ],
    ),
    ProviderInfo(
        name="groq",
        display_name="Groq",
        category="US",
        api_endpoint="https://api.groq.com/openai/v1/chat/completions",
        base_url="https://api.groq.com/openai",
        env_vars=["GROQ_API_KEY"],
        api_key_url="https://console.groq.com/keys",
        model_list_url="https://api.groq.com/openai/v1/models",
        notes="Very fast OpenAI-compatible inference.",
        models=[
            ModelInfo("groq/compound", "Groq Compound", "Tool-using Groq system for agentic answers.", 131072, 8192, True, False, "cloud"),
            ModelInfo("groq/compound-mini", "Groq Compound Mini", "Fast tool-using Groq system.", 131072, 8192, True, False, "medium"),
            ModelInfo("openai/gpt-oss-120b", "GPT OSS 120B", "Open-weight reasoning-capable model.", 131072, 65536, True, False, "cloud"),
            ModelInfo("openai/gpt-oss-20b", "GPT OSS 20B", "Very fast open-weight model.", 131072, 65536, True, False, "medium"),
            ModelInfo("llama-3.3-70b-versatile", "Llama 3.3 70B Versatile", "Production Groq Llama model.", 131072, 32768, True, False, "cloud"),
        ],
    ),
    ProviderInfo(
        name="mistral",
        display_name="Mistral AI",
        category="EU",
        api_endpoint="https://api.mistral.ai/v1/chat/completions",
        base_url="https://api.mistral.ai",
        env_vars=["MISTRAL_API_KEY"],
        api_key_url="https://console.mistral.ai/api-keys/",
        model_list_url="https://api.mistral.ai/v1/models",
        notes="European provider with strong code, document, and multimodal models.",
        models=[
            ModelInfo("mistral-medium-latest", "Mistral Medium", "Frontier multimodal agentic/coding model.", 128000, 32000, True, True, "cloud"),
            ModelInfo("mistral-large-latest", "Mistral Large", "Strong multilingual reasoning model.", 128000, 32000, True, False, "cloud"),
            ModelInfo("devstral-medium-latest", "Devstral Medium", "Software-engineering agent model.", 128000, 32000, True, False, "cloud"),
            ModelInfo("devstral-small-latest", "Devstral Small", "Efficient coding-agent model.", 128000, 32000, True, False, "medium"),
        ],
    ),
    ProviderInfo(
        name="cohere",
        display_name="Cohere",
        category="CA",
        api_endpoint="https://api.cohere.ai/compatibility/v1/chat/completions",
        base_url="https://api.cohere.ai/compatibility",
        env_vars=["COHERE_API_KEY"],
        api_key_url="https://dashboard.cohere.com/api-keys",
        notes="Enterprise RAG, tools, citations, and structured outputs via Chat Completions compatibility.",
        models=[
            ModelInfo("command-a-03-2025", "Command A", "Enterprise agent/RAG model with tool use.", 256000, 8000, True, True, "cloud"),
            ModelInfo("command-r-plus", "Command R+", "RAG-focused command model.", 128000, 4096, True, False, "cloud"),
            ModelInfo("command-r", "Command R", "Efficient RAG and agent workflows.", 128000, 4096, True, False, "medium"),
        ],
    ),
    ProviderInfo(
        name="openrouter",
        display_name="OpenRouter",
        category="aggregator",
        api_endpoint="https://openrouter.ai/api/v1/chat/completions",
        base_url="https://openrouter.ai/api",
        env_vars=["OPENROUTER_API_KEY"],
        api_key_url="https://openrouter.ai/settings/keys",
        model_list_url="https://openrouter.ai/api/v1/models",
        notes="OpenAI-compatible router for hundreds of models. Use custom model search from their dashboard/API.",
        models=[
            ModelInfo("openai/gpt-5.2", "OpenAI GPT-5.2", "Frontier OpenAI model through OpenRouter.", 400000, 128000, True, True, "cloud"),
            ModelInfo("anthropic/claude-sonnet-4", "Claude Sonnet 4", "Claude through OpenRouter.", 200000, 64000, True, True, "cloud"),
            ModelInfo("google/gemini-3-pro-preview", "Gemini 3 Pro Preview", "Gemini through OpenRouter.", 1048576, 65536, True, True, "cloud", "preview"),
            ModelInfo("openrouter/auto", "Auto Router", "Let OpenRouter route to a suitable model.", 128000, 8192, True, True, "medium"),
        ],
    ),
    ProviderInfo(
        name="perplexity",
        display_name="Perplexity",
        category="US",
        api_endpoint="https://api.perplexity.ai/v1/chat/completions",
        base_url="https://api.perplexity.ai",
        env_vars=["PERPLEXITY_API_KEY"],
        api_key_url="https://www.perplexity.ai/settings/api",
        notes="OpenAI-compatible search-grounded models.",
        models=[
            ModelInfo("sonar-pro", "Sonar Pro", "Research answers with search/citations.", 200000, 8000, True, False, "cloud"),
            ModelInfo("sonar-reasoning", "Sonar Reasoning", "Reasoning model with search grounding.", 128000, 8000, True, False, "medium"),
            ModelInfo("sonar", "Sonar", "Fast search-grounded model.", 128000, 8000, True, False, "medium"),
        ],
    ),
    ProviderInfo(
        name="nvidia_nim",
        display_name="NVIDIA NIM",
        category="US",
        api_endpoint="https://integrate.api.nvidia.com/v1/chat/completions",
        base_url="https://integrate.api.nvidia.com",
        env_vars=["NVIDIA_API_KEY", "NIM_API_KEY"],
        api_key_url="https://build.nvidia.com/",
        model_list_url="https://integrate.api.nvidia.com/v1/models",
        notes="OpenAI-compatible endpoint for NVIDIA-hosted models and NIM integrations.",
        models=[
            ModelInfo("meta/llama-3.1-70b-instruct", "Llama 3.1 70B Instruct", "Strong general instruction model via NVIDIA.", 131072, 8192, True, False, "cloud"),
            ModelInfo("meta/llama-3.1-405b-instruct", "Llama 3.1 405B Instruct", "Frontier-scale model for heavy reasoning.", 131072, 8192, True, False, "cloud"),
            ModelInfo("qwen/qwen2.5-coder-32b-instruct", "Qwen 2.5 Coder 32B", "Code-focused model with solid tool use.", 131072, 16384, True, False, "cloud"),
            ModelInfo("nvidia/llama-3.1-nemotron-70b-instruct", "Nemotron 70B Instruct", "NVIDIA-tuned reasoning and alignment.", 131072, 8192, True, False, "cloud"),
        ],
    ),
    ProviderInfo(
        name="together",
        display_name="Together AI",
        category="US",
        api_endpoint="https://api.together.xyz/v1/chat/completions",
        base_url="https://api.together.xyz",
        env_vars=["TOGETHER_API_KEY"],
        api_key_url="https://api.together.xyz/settings/api-keys",
        model_list_url="https://api.together.xyz/v1/models",
        notes="OpenAI-compatible API with broad open-model catalog.",
        models=[
            ModelInfo("meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "Llama 3.1 70B Turbo", "Fast 70B class model for production chats.", 131072, 8192, True, False, "cloud"),
            ModelInfo("Qwen/Qwen2.5-Coder-32B-Instruct", "Qwen 2.5 Coder 32B", "Strong coding model with long context.", 131072, 16384, True, False, "cloud"),
            ModelInfo("deepseek-ai/DeepSeek-V3", "DeepSeek V3", "Reasoning + coding model through Together.", 128000, 16384, True, False, "cloud"),
            ModelInfo("mistralai/Mixtral-8x22B-Instruct-v0.1", "Mixtral 8x22B Instruct", "High-quality open MoE model.", 65536, 8192, True, False, "cloud"),
        ],
    ),
    ProviderInfo(
        name="fireworks",
        display_name="Fireworks AI",
        category="US",
        api_endpoint="https://api.fireworks.ai/inference/v1/chat/completions",
        base_url="https://api.fireworks.ai/inference",
        env_vars=["FIREWORKS_API_KEY"],
        api_key_url="https://fireworks.ai/account/api-keys",
        model_list_url="https://api.fireworks.ai/inference/v1/models",
        notes="OpenAI-compatible inference platform for fast open-model serving.",
        models=[
            ModelInfo("accounts/fireworks/models/llama-v3p1-70b-instruct", "Llama 3.1 70B Instruct", "Reliable flagship open model on Fireworks.", 131072, 8192, True, False, "cloud"),
            ModelInfo("accounts/fireworks/models/qwen2p5-coder-32b-instruct", "Qwen 2.5 Coder 32B", "Code-oriented model with robust outputs.", 131072, 16384, True, False, "cloud"),
            ModelInfo("accounts/fireworks/models/mixtral-8x22b-instruct", "Mixtral 8x22B Instruct", "MoE model for high-quality generation.", 65536, 8192, True, False, "cloud"),
        ],
    ),
    ProviderInfo(
        name="cerebras",
        display_name="Cerebras",
        category="US",
        api_endpoint="https://api.cerebras.ai/v1/chat/completions",
        base_url="https://api.cerebras.ai",
        env_vars=["CEREBRAS_API_KEY"],
        api_key_url="https://cloud.cerebras.ai/",
        model_list_url="https://api.cerebras.ai/v1/models",
        notes="OpenAI-compatible ultra-fast inference from Cerebras.",
        models=[
            ModelInfo("llama3.1-70b", "Llama 3.1 70B", "Low-latency 70B model for interactive workflows.", 131072, 8192, True, False, "cloud"),
            ModelInfo("llama3.1-8b", "Llama 3.1 8B", "Fast economical model for high throughput tasks.", 131072, 8192, True, False, "medium"),
            ModelInfo("qwen2.5-coder-32b", "Qwen 2.5 Coder 32B", "Code-heavy tasks with fast response times.", 131072, 16384, True, False, "cloud"),
        ],
    ),
    ProviderInfo(
        name="openai_compatible",
        display_name="OpenAI-Compatible (Custom)",
        category="custom",
        compatibility="custom",
        notes="Any provider exposing /v1/chat/completions.",
        models=[ModelInfo("custom", "Custom Model", "Enter any model name.", 4096, 4096, True, False, "medium", "custom")],
    ),
    ProviderInfo(
        name="anthropic_compatible",
        display_name="Anthropic-Compatible (Custom)",
        category="custom",
        auth_type="header_api_key",
        auth_header="x-api-key",
        compatibility="custom",
        notes="Any provider exposing /v1/messages.",
        models=[ModelInfo("custom", "Custom Model", "Enter any model name.", 4096, 4096, True, False, "medium", "custom")],
    ),
]


def get_provider(name: str) -> ProviderInfo | None:
    """Get a provider by internal name."""
    for provider in DEFAULT_PROVIDERS:
        if provider.name == name:
            return provider
    return None


def get_all_providers() -> list[ProviderInfo]:
    """Get all providers in display order."""
    return list(DEFAULT_PROVIDERS)


def get_models_for_provider(provider_name: str) -> list[ModelInfo]:
    """Get the curated models for a provider."""
    provider = get_provider(provider_name)
    return list(provider.models) if provider else []


def get_model(provider_name: str, model_id: str) -> ModelInfo | None:
    """Get a specific model by provider and ID."""
    for model in get_models_for_provider(provider_name):
        if model.id == model_id:
            return model
    return None


def search_models(provider_name: str, query: str, limit: int = 20) -> list[ModelInfo]:
    """Search the curated model list by ID, name, description, status, or tier."""
    models = get_models_for_provider(provider_name)
    q = (query or "").strip().lower()
    if not q:
        return models[:limit]
    matches: list[ModelInfo] = []
    for model in models:
        haystack = " ".join(
            [model.id, model.name, model.description, model.tier, model.status]
        ).lower()
        if all(part in haystack for part in q.split()):
            matches.append(model)
    return matches[:limit]


def list_provider_names() -> list[str]:
    """List provider internal names."""
    return [provider.name for provider in DEFAULT_PROVIDERS]


def list_provider_display_names() -> list[tuple[str, str]]:
    """List ``(name, display_name)`` pairs."""
    return [(provider.name, provider.display_name) for provider in DEFAULT_PROVIDERS]


def get_capable_models(min_tier: str = "local") -> list[tuple[str, str, str]]:
    """Return models capable enough for NEUGI."""
    tier_order = {"local": 0, "medium": 1, "cloud": 2}
    min_level = tier_order.get(min_tier, 0)
    result: list[tuple[str, str, str]] = []
    for provider in DEFAULT_PROVIDERS:
        for model in provider.models:
            if tier_order.get(model.tier, 0) >= min_level:
                result.append((provider.name, model.id, model.name))
    return result


def provider_to_runtime(provider_name: str) -> str:
    """Map a catalog provider to NEUGI's runtime provider family."""
    if provider_name == "openai_compatible":
        return "openai"
    if provider_name == "anthropic_compatible":
        return "anthropic"
    return provider_name


def default_fallback_model(provider_name: str) -> str:
    """Return a sensible fallback for a runtime provider."""
    fallback_map = {
        "ollama": "llama3.2:3b",
        "openai": "gpt-5-mini",
        "anthropic": "claude-3-5-haiku-20241022",
        "gemini": "gemini-2.5-flash",
        "grok": "grok-4.3-latest",
        "deepseek": "deepseek-v4-flash",
        "groq": "openai/gpt-oss-20b",
        "mistral": "devstral-small-latest",
        "cohere": "command-r",
        "openrouter": "openrouter/auto",
        "perplexity": "sonar",
        "nvidia_nim": "meta/llama-3.1-70b-instruct",
        "together": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "fireworks": "accounts/fireworks/models/llama-v3p1-70b-instruct",
        "cerebras": "llama3.1-70b",
    }
    return fallback_map.get(provider_name, "")


def add_provider(provider: ProviderInfo) -> None:
    """Add a provider at runtime."""
    DEFAULT_PROVIDERS.append(provider)


def remove_provider(name: str) -> bool:
    """Remove a provider from the runtime catalog."""
    for index, provider in enumerate(DEFAULT_PROVIDERS):
        if provider.name == name:
            DEFAULT_PROVIDERS.pop(index)
            return True
    return False
