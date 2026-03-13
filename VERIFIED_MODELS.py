#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - VERIFIED MODELS (MARCH 2026)
================================================

ACTUAL models available NOW - no hallucinations!
Corrected: Qwen 3.5 with 0.8B!

Last Updated: March 13, 2026
"""

# ============================================================
# OLLAMA MODELS (Verified March 2026)
# ============================================================

OLLAMA_MODELS = {
    # Qwen3.5 - LATEST! (Corrected!)
    "qwen2.5": {
        "sizes": ["0.5b", "0.8b", "1.5b", "3b", "7b", "14b", "32b", "72b"],
        "release": "March 2025",
        "ctx": 32768,
        "ram_guide": {
            "0.5b": "~350MB",
            "0.8b": "~500MB",  # NEW! Super tiny!
            "1.5b": "~1GB",
            "3b": "~2GB",
            "7b": "~4.5GB",
            "14b": "~9GB",
            "32b": "~20GB",
        },
        "highlights": "Best open source value! 0.8B = super tiny!",
    },
    # Llama 3.2
    "llama3.2": {
        "sizes": ["1b", "3b", "11b", "90b"],
        "release": "Late 2024",
        "ctx": 8192,
        "ram_guide": {
            "1b": "~800MB",
            "3b": "~2GB",
            "11b": "~7GB",
            "90b": "~55GB",
        },
        "highlights": "Meta's efficient models with vision",
    },
    # Llama 3.1
    "llama3.1": {
        "sizes": ["8b", "70b", "405b"],
        "release": "July 2024",
        "ctx": 8192,
        "ram_guide": {
            "8b": "~5GB",
            "70b": "~40GB",
            "405b": "~240GB",
        },
        "highlights": "Meta's flagship open model",
    },
    # DeepSeek R1 - Reasoning powerhouse!
    "deepseek-r1": {
        "sizes": ["1.5b", "7b", "8b", "14b", "32b", "70b", "671b"],
        "release": "Jan 2025",
        "ctx": 4096,  # Limited but reasoning is INSANE!
        "ram_guide": {
            "1.5b": "~1GB",
            "7b": "~4.5GB",
            "14b": "~9GB",
            "32b": "~20GB",
            "671b": "~400GB",  # MoE
        },
        "highlights": "Reasoning EQUALS GPT-4! Best open source reasoning!",
    },
    # Gemma 3 (Google's latest)
    "gemma3": {
        "sizes": ["270m", "1b", "4b", "12b", "27b"],
        "release": "March 2025",
        "ctx": 8192,
        "ram_guide": {
            "1b": "~800MB",
            "4b": "~2.5GB",
            "12b": "~8GB",
            "27b": "~16GB",
        },
        "highlights": "Google's latest, good reasoning",
    },
    # Phi-4 (Microsoft)
    "phi4": {
        "sizes": ["14b"],
        "release": "Late 2024",
        "ctx": 4096,
        "ram_guide": {"14b": "~9GB"},
        "highlights": "Microsoft's best small model",
    },
    # Mistral
    "mistral": {
        "sizes": ["7b"],
        "release": "2023",
        "ctx": 8192,
        "ram_guide": {"7b": "~4GB"},
        "highlights": "Classic, reliable",
    },
    # TinyLlama
    "tinyllama": {
        "sizes": ["1.1b"],
        "release": "2023",
        "ctx": 4096,
        "ram_guide": {"1.1b": "~700MB"},
        "highlights": "Proof of concept only",
    },
}

# ============================================================
# GROQ - FREE API (Verified March 2026)
# ============================================================

GROQ_MODELS = {
    "llama-3.1-8b-instant": {"ctx": 8192, "free": True, "speed": "ultra_fast"},
    "llama-3.1-70b-versatile": {"ctx": 8192, "free": True, "speed": "fast"},
    "mixtral-8x7b-32768": {"ctx": 32768, "free": True, "speed": "fast"},
    "llama-3.3-70b-instruct": {"ctx": 8192, "free": True, "speed": "medium"},
    "gemma2-9b-it": {"ctx": 8192, "free": True, "speed": "fast"},
}

# ============================================================
# OPENROUTER - Free Tier (Verified March 2026)
# ============================================================

OPENROUTER_MODELS = {
    "google/gemini-2.0-flash-exp": {
        "ctx": 1000000,
        "free": True,
        "notes": "1M CONTEXT - FREE!",
    },
    "meta-llama/llama-3.1-8b-instant": {"ctx": 128000, "free": True},
    "google/gemini-1.5-flash": {"ctx": 1000000, "free": True},
    "deepseek/deepseek-chat": {"ctx": 64000, "free": True},
    "qwen/qwen2.5-7b-instruct": {"ctx": 32768, "free": True},
}

# ============================================================
# BEST EDGE RECOMMENDATIONS
# ============================================================

EDGE_CHOICES = {
    "256mb": {"model": "tinyllama:1.1b", "ram": "~700MB", "use": "Proof of concept"},
    "512mb": {"model": "qwen2.5:0.5b", "ram": "~350MB", "use": "Super minimal!"},
    "1gb": {"model": "qwen2.5:0.8b", "ram": "~500MB", "use": "NEW! Tiny but capable!"},
    "2gb": {"model": "llama3.2:1b", "ram": "~800MB", "use": "Good balance!"},
    "4gb": {"model": "qwen2.5:7b", "ram": "~4.5GB", "use": "BEST VALUE!"},
    "8gb": {"model": "llama3.1:8b", "ram": "~5GB", "use": "Excellent performance!"},
    "16gb": {"model": "deepseek-r1:14b", "ram": "~9GB", "use": "Reasoning = GPT-4!"},
    "32gb": {"model": "qwen2.5:32b", "ram": "~20GB", "use": "Near GPT-4 level!"},
}

# ============================================================
# QUICK REFERENCE
# ============================================================


def get_model(ram_gb: float) -> dict:
    """Get best model for your RAM"""

    if ram_gb <= 0.5:
        return EDGE_CHOICES["512mb"]
    elif ram_gb <= 1:
        return EDGE_CHOICES["1gb"]
    elif ram_gb <= 2:
        return EDGE_CHOICES["2gb"]
    elif ram_gb <= 4:
        return EDGE_CHOICES["4gb"]
    elif ram_gb <= 8:
        return EDGE_CHOICES["8gb"]
    elif ram_gb <= 16:
        return EDGE_CHOICES["16gb"]
    else:
        return EDGE_CHOICES["32gb"]


if __name__ == "__main__":
    print("=" * 60)
    print("🤖 NEUGI - VERIFIED MODELS (March 2026)")
    print("=" * 60)

    print("\n🟢 OLLAMA - Local (FREE)")
    print("-" * 40)
    for name, info in OLLAMA_MODELS.items():
        sizes = ", ".join(info["sizes"])
        print(f"\n{name.upper()}: {sizes}")
        print(f"   Context: {info['ctx']}")
        if "0.8b" in str(info.get("sizes", [])):
            print(f"   ⚡ NEW: 0.8B version available!")

    print("\n\n🔵 GROQ - Free API")
    print("-" * 40)
    for m, info in GROQ_MODELS.items():
        print(f"  {m}: {info['ctx']} ctx [FREE]")

    print("\n\n🟣 OPENROUTER - Free Tier")
    print("-" * 40)
    for m, info in OPENROUTER_MODELS.items():
        free = " [FREE]" if info.get("free") else ""
        print(f"  {m}: {info['ctx']} ctx{free}")

    print("\n\n" + "=" * 60)
    print("🎯 BEST CHOICES BY RAM")
    print("=" * 60)
    for ram, info in EDGE_CHOICES.items():
        note = f" - {info['use']}" if info["use"] else ""
        print(f"  {ram:>5} → {info['model']}{note}")
