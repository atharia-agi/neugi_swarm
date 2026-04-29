"""
NEUGI v2 — Provider & Model Catalog
====================================

Editable reference of AI providers, endpoints, and models.
This is NOT hardcoded restrictions — just convenient choices.
Users can always type custom model names and endpoints.

Auto-loaded by GeniusWizard to show pickable options.
Edit this file to add new providers or models anytime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ModelInfo:
    """Info about a specific model."""

    id: str
    name: str
    description: str = ""
    context_window: int = 4096
    max_output: int = 4096
    supports_tools: bool = True
    supports_vision: bool = False
    tier: str = "medium"  # local / medium / cloud


@dataclass
class ProviderInfo:
    """Info about an AI provider."""

    name: str
    display_name: str
    category: str = ""  # US, EU, CN, etc
    api_endpoint: str = ""
    base_url: str = ""
    auth_type: str = "bearer_header"
    auth_header: str = "Authorization"
    auth_format: str = "Bearer <API_KEY>"
    notes: str = ""
    models: List[ModelInfo] = field(default_factory=list)

    def get_base_url(self) -> str:
        """Return the base URL for API calls."""
        if self.base_url:
            return self.base_url
        # Derive from endpoint
        endpoint = self.api_endpoint
        if "/v1/" in endpoint:
            return endpoint.split("/v1/")[0] + "/v1"
        if "/v1beta/" in endpoint:
            return endpoint.split("/v1beta/")[0] + "/v1beta"
        if "/v4/" in endpoint:
            return endpoint.split("/v4/")[0] + "/v4"
        if "/paas/" in endpoint:
            return endpoint.split("/paas/")[0] + "/paas/v4"
        return endpoint.rsplit("/", 1)[0]


# =============================================================================
# EDITABLE CATALOG — Add or remove providers/models as needed
# =============================================================================

DEFAULT_PROVIDERS: List[ProviderInfo] = [
    # -- Local / Self-Hosted -------------------------------------------------
    ProviderInfo(
        name="ollama",
        display_name="Ollama (Local)",
        category="local",
        base_url="http://localhost:11434",
        auth_type="none",
        notes="Run models locally. Free, private, works offline.",
        models=[
            ModelInfo("qwen2.5-coder:7b", "Qwen 2.5 Coder 7B",
                     "Excellent coding & tool use. ~4GB.", 32768, 8192, True, False, "medium"),
            ModelInfo("qwen3:8b", "Qwen 3 8B",
                     "Strong reasoning, tool native. ~5GB.", 32768, 8192, True, False, "medium"),
            ModelInfo("llama3.1:8b", "Llama 3.1 8B",
                     "Balanced, fast. ~5GB.", 131072, 8192, True, False, "medium"),
            ModelInfo("llama3.2:3b", "Llama 3.2 3B",
                     "Lightweight but capable. ~2GB.", 131072, 8192, True, False, "local"),
            ModelInfo("llama3.3:70b", "Llama 3.3 70B",
                     "Powerful, needs GPU. ~40GB.", 131072, 8192, True, False, "cloud"),
            ModelInfo("deepseek-r1:14b", "DeepSeek-R1 14B",
                     "Deep reasoning. ~9GB.", 64000, 16000, True, False, "medium"),
            ModelInfo("phi4:14b", "Phi-4 14B",
                     "Microsoft, good tool use. ~9GB.", 16384, 4096, True, False, "medium"),
            ModelInfo("mistral:7b", "Mistral 7B",
                     "Solid all-rounder. ~4GB.", 32768, 8192, True, False, "medium"),
            ModelInfo("mixtral:8x7b", "Mixtral 8x7B",
                     "MoE, very capable. ~26GB.", 32768, 8192, True, False, "cloud"),
            ModelInfo("gemma2:9b", "Gemma 2 9B",
                     "Google, efficient. ~6GB.", 8192, 4096, True, False, "medium"),
            ModelInfo("gemma3:4b", "Gemma 3 4B",
                     "Google, vision + tools. ~3GB.", 128000, 8192, True, True, "local"),
        ],
    ),

    # -- OpenAI ---------------------------------------------------------------
    ProviderInfo(
        name="openai",
        display_name="OpenAI",
        category="US",
        api_endpoint="https://api.openai.com/v1/chat/completions",
        base_url="https://api.openai.com/v1",
        auth_type="bearer_header",
        auth_header="Authorization",
        auth_format="Bearer <API_KEY>",
        notes="Standard OpenAI API. Also supports Responses API.",
        models=[
            ModelInfo("gpt-5.5", "GPT-5.5", "Flagship. 1M context, tools, vision, audio.",
                     1048576, 131072, True, True, "cloud"),
            ModelInfo("gpt-5.4", "GPT-5.4", "Strong reasoning, lower cost than 5.5.",
                     1048576, 131072, True, True, "cloud"),
            ModelInfo("gpt-5.4-mini", "GPT-5.4 Mini", "Fast, cost-effective. 400K context.",
                     400000, 131072, True, False, "medium"),
            ModelInfo("gpt-4o", "GPT-4o", "Best all-rounder. Vision + tools.",
                     128000, 16384, True, True, "cloud"),
            ModelInfo("gpt-4o-mini", "GPT-4o Mini", "Fast, cheap. Great for most tasks.",
                     128000, 16384, True, False, "medium"),
            ModelInfo("o4", "o4", "Deep reasoning model.",
                     200000, 32768, True, False, "cloud"),
            ModelInfo("o4-mini", "o4 Mini", "Reasoning, cheap.",
                     200000, 65536, True, False, "medium"),
        ],
    ),

    # -- Anthropic ------------------------------------------------------------
    ProviderInfo(
        name="anthropic",
        display_name="Anthropic",
        category="US",
        api_endpoint="https://api.anthropic.com/v1/messages",
        base_url="https://api.anthropic.com",
        auth_type="header_api_key",
        auth_header="x-api-key",
        auth_format="x-api-key: <KEY>",
        notes="Claude models. Dedicated API (not OpenAI-compatible).",
        models=[
            ModelInfo("claude-opus-4-7", "Claude Opus 4.7",
                     "Flagship. Coding, agents, vision. 200K context.",
                     200000, 32000, True, True, "cloud"),
            ModelInfo("claude-3-7-sonnet-20250219", "Claude 3.7 Sonnet",
                     "Near-Opus intelligence, faster, cheaper.",
                     200000, 64000, True, True, "cloud"),
            ModelInfo("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet",
                     "Excellent balance of speed, quality, price.",
                     200000, 8192, True, True, "medium"),
            ModelInfo("claude-3-5-haiku-20241022", "Claude 3.5 Haiku",
                     "Fastest, most cost-effective Claude.",
                     200000, 8192, True, False, "local"),
        ],
    ),

    # -- Google Gemini --------------------------------------------------------
    ProviderInfo(
        name="gemini",
        display_name="Google Gemini",
        category="US",
        api_endpoint="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        auth_type="api_key_query_or_bearer",
        notes="Multimodal (text, image, audio). Pass key as ?key= or Bearer header.",
        models=[
            ModelInfo("gemini-3.1-pro", "Gemini 3.1 Pro",
                     "Premium multimodal. 1M context.",
                     1000000, 64000, True, True, "cloud"),
            ModelInfo("gemini-3-flash", "Gemini 3 Flash",
                     "Fast frontier, rivals larger models at lower cost.",
                     128000, 32000, True, True, "medium"),
            ModelInfo("gemini-2.5-pro", "Gemini 2.5 Pro",
                     "Advanced reasoning, deep coding.",
                     200000, 32000, True, True, "cloud"),
            ModelInfo("gemini-2.5-flash", "Gemini 2.5 Flash",
                     "Best price-performance in 2.5 family.",
                     128000, 32000, True, True, "medium"),
        ],
    ),

    # -- xAI Grok -------------------------------------------------------------
    ProviderInfo(
        name="grok",
        display_name="xAI Grok",
        category="US",
        api_endpoint="https://api.x.ai/v1/chat/completions",
        base_url="https://api.x.ai/v1",
        auth_type="bearer_header",
        notes="Real-time aware. OpenAI-compatible.",
        models=[
            ModelInfo("grok-3", "Grok 3", "xAI flagship. Real-time aware.",
                     131072, 8192, True, False, "cloud"),
            ModelInfo("grok-3-mini", "Grok 3 Mini", "Faster, cheaper variant.",
                     131072, 8192, True, False, "medium"),
        ],
    ),

    # -- DeepSeek -------------------------------------------------------------
    ProviderInfo(
        name="deepseek",
        display_name="DeepSeek",
        category="CN",
        api_endpoint="https://api.deepseek.com/chat/completions",
        base_url="https://api.deepseek.com",
        auth_type="bearer_header",
        notes="OpenAI-compatible. Reasoning models support thinking budget.",
        models=[
            ModelInfo("deepseek-v4-pro", "DeepSeek V4 Pro",
                     "Flagship reasoning. 64K context.",
                     64000, 16000, True, False, "cloud"),
            ModelInfo("deepseek-v4-flash", "DeepSeek V4 Flash",
                     "Fast reasoning, lower latency.",
                     64000, 16000, True, False, "medium"),
            ModelInfo("deepseek-v3.1", "DeepSeek V3.1",
                     "Powerful base model. 128K context.",
                     128000, 32000, True, False, "medium"),
        ],
    ),

    # -- Groq -----------------------------------------------------------------
    ProviderInfo(
        name="groq",
        display_name="Groq",
        category="US",
        api_endpoint="https://api.groq.com/openai/v1/chat/completions",
        base_url="https://api.groq.com/openai/v1",
        auth_type="bearer_header",
        notes="Ultra-fast inference on LPUs. OpenAI-compatible.",
        models=[
            ModelInfo("llama-3.3-70b-versatile", "Llama 3.3 70B",
                     "Highest quality on Groq. ~280 t/s.",
                     131072, 32768, True, False, "cloud"),
            ModelInfo("llama-3.1-8b-instant", "Llama 3.1 8B Instant",
                     "Extremely fast. ~560 t/s.",
                     131072, 131072, True, False, "medium"),
            ModelInfo("openai/gpt-oss-120b", "GPT OSS 120B",
                     "OpenAI open-weight. ~500 t/s.",
                     131072, 65536, True, False, "cloud"),
            ModelInfo("openai/gpt-oss-20b", "GPT OSS 20B",
                     "Faster 20B variant. ~1000 t/s.",
                     131072, 65536, True, False, "medium"),
        ],
    ),

    # -- Mistral AI -----------------------------------------------------------
    ProviderInfo(
        name="mistral",
        display_name="Mistral AI",
        category="EU",
        api_endpoint="https://api.mistral.ai/v1/chat/completions",
        base_url="https://api.mistral.ai/v1",
        auth_type="bearer_header",
        notes="European provider. OpenAI-compatible.",
        models=[
            ModelInfo("mistral-large-latest", "Mistral Large",
                     "Top-tier multilingual and reasoning.",
                     128000, 32000, True, False, "cloud"),
            ModelInfo("mistral-medium-latest", "Mistral Medium",
                     "Balanced performance.",
                     32000, 32000, True, False, "medium"),
            ModelInfo("mistral-small-latest", "Mistral Small",
                     "Fast, cost-efficient.",
                     32000, 32000, True, False, "medium"),
            ModelInfo("pixtral-large-latest", "Pixtral Large",
                     "Multimodal (vision + language).",
                     128000, 32000, True, True, "cloud"),
        ],
    ),

    # -- Cohere ---------------------------------------------------------------
    ProviderInfo(
        name="cohere",
        display_name="Cohere",
        category="CA",
        api_endpoint="https://api.cohere.ai/v1/chat",
        base_url="https://api.cohere.ai/v1",
        auth_type="bearer_header",
        notes="Enterprise RAG and command models. Not OpenAI-compatible.",
        models=[
            ModelInfo("command-r-plus", "Command R+",
                     "Advanced RAG, tool use. 128K context.",
                     128000, 4096, True, False, "cloud"),
            ModelInfo("command-r", "Command R",
                     "Powerful RAG and agentic tasks.",
                     128000, 4096, True, False, "medium"),
            ModelInfo("command", "Command",
                     "Classic text generation.",
                     4096, 4096, True, False, "medium"),
        ],
    ),

    # -- Perplexity -----------------------------------------------------------
    ProviderInfo(
        name="perplexity",
        display_name="Perplexity AI",
        category="US",
        api_endpoint="https://api.perplexity.ai/chat/completions",
        base_url="https://api.perplexity.ai/v1",
        auth_type="bearer_header",
        notes="Built-in web search and citations. OpenAI-compatible.",
        models=[
            ModelInfo("sonar-pro", "Sonar Pro",
                     "Premium with web search. 200K context.",
                     200000, 8000, True, False, "cloud"),
            ModelInfo("sonar-reasoning", "Sonar Reasoning",
                     "Enhanced reasoning with search.",
                     128000, 8000, True, False, "medium"),
            ModelInfo("sonar", "Sonar",
                     "Standard with web search. Good balance.",
                     128000, 8000, True, False, "medium"),
        ],
    ),

    # -- Together AI ----------------------------------------------------------
    ProviderInfo(
        name="together",
        display_name="Together AI",
        category="US",
        api_endpoint="https://api.together.xyz/v1/chat/completions",
        base_url="https://api.together.xyz/v1",
        auth_type="bearer_header",
        notes="Wide variety of models including Chinese ones. OpenAI-compatible.",
        models=[
            ModelInfo("deepseek-ai/DeepSeek-V3.1", "DeepSeek V3.1",
                     "Strong reasoning and coding.", 128000, 32000, True, False, "cloud"),
            ModelInfo("Qwen/Qwen3.5-397B-Instruct", "Qwen 3.5 397B",
                     "Massive model, top-tier performance.", 128000, 40000, True, False, "cloud"),
            ModelInfo("MoonshotAI/Kimi-K2.5", "Kimi K2.5",
                     "Strong multimodal and reasoning.", 128000, 32000, True, False, "cloud"),
        ],
    ),

    # -- Fireworks AI ---------------------------------------------------------
    ProviderInfo(
        name="fireworks",
        display_name="Fireworks AI",
        category="US",
        api_endpoint="https://api.fireworks.ai/v1/chat/completions",
        base_url="https://api.fireworks.ai/v1",
        auth_type="bearer_header",
        notes="Fastest inference. Broad model selection. OpenAI-compatible.",
        models=[
            ModelInfo("meta-llama/Llama-3.1-405B-Instruct", "Llama 3.1 405B",
                     "Meta's largest model.", 128000, 4096, True, False, "cloud"),
            ModelInfo("meta-llama/Llama-3.3-70B-Instruct", "Llama 3.3 70B",
                     "Latest Llama, improved coding.", 128000, 4096, True, False, "cloud"),
            ModelInfo("mistralai/Mixtral-8x22B-Instruct-v0.1", "Mixtral 8x22B",
                     "High quality MoE.", 64000, 4096, True, False, "cloud"),
        ],
    ),

    # -- Moonshot AI (Kimi) ---------------------------------------------------
    ProviderInfo(
        name="moonshot",
        display_name="Moonshot AI (Kimi)",
        category="CN",
        api_endpoint="https://api.moonshot.cn/v1/chat/completions",
        base_url="https://api.moonshot.cn/v1",
        auth_type="bearer_header",
        notes="OpenAI-compatible. Strong reasoning, 200K+ context.",
        models=[
            ModelInfo("kimi-k2-5", "Kimi K2.5",
                     "Strong reasoning, coding. 200K context.",
                     200000, 8000, True, False, "cloud"),
            ModelInfo("kimi-k2-5-turbo", "Kimi K2.5 Turbo",
                     "Speed and cost optimized.",
                     128000, 4000, True, False, "medium"),
            ModelInfo("kimi-k2-6", "Kimi K2.6",
                     "Improved agentic, web search.",
                     200000, 8000, True, False, "cloud"),
        ],
    ),

    # -- Alibaba Qwen ---------------------------------------------------------
    ProviderInfo(
        name="alibaba",
        display_name="Alibaba Cloud (Qwen)",
        category="CN",
        api_endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        auth_type="bearer_header",
        notes="OpenAI-compatible mode. Also available via Together AI.",
        models=[
            ModelInfo("qwen-max", "Qwen Max",
                     "Flagship Qwen. Strongest performance.", 128000, 2000, True, False, "cloud"),
            ModelInfo("qwen-plus", "Qwen Plus",
                     "High-performance chat and creative.", 128000, 2000, True, False, "medium"),
            ModelInfo("qwen-turbo", "Qwen Turbo",
                     "Fast, cost-effective.", 8000, 1500, True, False, "medium"),
        ],
    ),

    # -- ZhipuAI (GLM) --------------------------------------------------------
    ProviderInfo(
        name="zhipu",
        display_name="ZhipuAI (GLM)",
        category="CN",
        api_endpoint="https://open.bigmodel.cn/api/paas/v4/chat/completions",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        auth_type="bearer_header",
        notes="OpenAI-compatible. GLM series, strong coding and math.",
        models=[
            ModelInfo("glm-4", "GLM-4",
                     "Flagship. 128K context, supports tools.", 128000, 32000, True, False, "cloud"),
            ModelInfo("glm-4-plus", "GLM-4 Plus",
                     "Enhanced GLM-4, improved complex tasks.", 128000, 32000, True, False, "cloud"),
            ModelInfo("glm-4-turbo", "GLM-4 Turbo",
                     "Speed and latency optimized.", 128000, 32000, True, False, "medium"),
        ],
    ),

    # -- StepFun --------------------------------------------------------------
    ProviderInfo(
        name="stepfun",
        display_name="StepFun",
        category="CN",
        api_endpoint="https://api.stepfun.com/v1/chat/completions",
        base_url="https://api.stepfun.com/v1",
        auth_type="bearer_header",
        notes="OpenAI-compatible. Frontier reasoning and multimodal.",
        models=[
            ModelInfo("step-4", "Step 4",
                     "Flagship. Advanced reasoning, coding, multimodal.",
                     128000, 32000, True, True, "cloud"),
            ModelInfo("step-4-reasoning", "Step 4 Reasoning",
                     "Explicit reasoning mode. Highest quality.",
                     128000, 32000, True, False, "cloud"),
            ModelInfo("step-3.5-turbo", "Step 3.5 Turbo",
                     "Speed and cost optimized. 64K context.",
                     64000, 16000, True, False, "medium"),
        ],
    ),

    # -- OpenAI-Compatible (Custom) -------------------------------------------
    ProviderInfo(
        name="openai_compatible",
        display_name="OpenAI-Compatible (Custom)",
        category="custom",
        api_endpoint="",
        base_url="",
        auth_type="bearer_header",
        notes="Any provider with OpenAI-compatible API. You enter the base URL.",
        models=[
            ModelInfo("custom", "Custom Model", "Enter any model name.", 4096, 4096, True, False, "medium"),
        ],
    ),

    # -- Anthropic-Compatible (Custom) ----------------------------------------
    ProviderInfo(
        name="anthropic_compatible",
        display_name="Anthropic-Compatible (Custom)",
        category="custom",
        api_endpoint="",
        base_url="",
        auth_type="header_api_key",
        auth_header="x-api-key",
        notes="Any provider with Anthropic-compatible API. You enter the base URL.",
        models=[
            ModelInfo("custom", "Custom Model", "Enter any model name.", 4096, 4096, True, False, "medium"),
        ],
    ),
]


# =============================================================================
# Helper Functions
# =============================================================================

def get_provider(name: str) -> Optional[ProviderInfo]:
    """Get a provider by its internal name."""
    for p in DEFAULT_PROVIDERS:
        if p.name == name:
            return p
    return None


def get_all_providers() -> List[ProviderInfo]:
    """Get all providers in the catalog."""
    return list(DEFAULT_PROVIDERS)


def get_models_for_provider(provider_name: str) -> List[ModelInfo]:
    """Get all models for a specific provider."""
    p = get_provider(provider_name)
    return p.models if p else []


def get_model(provider_name: str, model_id: str) -> Optional[ModelInfo]:
    """Get a specific model by provider + ID."""
    for m in get_models_for_provider(provider_name):
        if m.id == model_id:
            return m
    return None


def list_provider_names() -> List[str]:
    """List all provider internal names."""
    return [p.name for p in DEFAULT_PROVIDERS]


def list_provider_display_names() -> List[tuple[str, str]]:
    """List (name, display_name) tuples."""
    return [(p.name, p.display_name) for p in DEFAULT_PROVIDERS]


def get_capable_models(min_tier: str = "local") -> List[tuple[str, str, str]]:
    """Get models capable enough for NEUGI.

    Returns list of (provider_name, model_id, display_name).
    """
    tier_order = {"local": 0, "medium": 1, "cloud": 2}
    min_level = tier_order.get(min_tier, 0)
    result = []
    for p in DEFAULT_PROVIDERS:
        for m in p.models:
            if tier_order.get(m.tier, 0) >= min_level:
                result.append((p.name, m.id, m.name))
    return result


# Allow runtime modification (user scripts can edit this)
def add_provider(provider: ProviderInfo) -> None:
    """Add a new provider to the catalog at runtime."""
    DEFAULT_PROVIDERS.append(provider)


def remove_provider(name: str) -> bool:
    """Remove a provider from the catalog."""
    for i, p in enumerate(DEFAULT_PROVIDERS):
        if p.name == name:
            DEFAULT_PROVIDERS.pop(i)
            return True
    return False
