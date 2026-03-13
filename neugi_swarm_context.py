#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - FLEXIBLE CONTEXT GUIDE
==========================================

This explains how context window affects responses
and provides recommended models for 2026.
"""

# ============================================================
# CONTEXT WINDOW - PROS & CONS
# ============================================================

CONTEXT_GUIDE = """
# 🎯 FLEXIBLE CONTEXT - COMPLETE GUIDE

## Apa itu Context Window?

Context window adalah "memory" model - seberapa banyak teks yang bisa 
diingat saat menghasilkan response.

## 🟢 LOW CONTEXT (2K-4K)

### Pros:
✅ Cepat response
✅ Murah (lebih sedikit token)
✅ OK buat hardware lemah (2GB RAM)
✅ Cocok untuk tugas sederhana
✅ Baterai hemat

### Cons:
❌ Tidak bisa ngobrol panjang
❌ Tidak bisa analisis dokumen panjang
❌ Tidak bisa context dari percakapan lama
❌ Kadang ответ bisa tidak lengkap

### Kapan Pakai:
- Tanya jawab sederhana
- Coding cepat
- Text generation pendek
- Chatbot basic

---

## 🟡 MEDIUM CONTEXT (8K-32K)

### Pros:
✅ Sudah cukup untuk mayoritas tugas
✅ Balance speed vs capability
✅ Bisa handling most use cases
✅ Tidak terlalu mahal

### Cons:
❌ Still limited untuk dokumen sangat panjang
❌ Tidak ideal untuk buku/article panjang

### Kapan Pakai:
- Regular conversations
- Document summarization
- Coding projects
- Multi-file analysis

---

## 🔴 HIGH CONTEXT (128K+)

### Pros:
✅ Bisa baca整个 buku sekaligus
✅ Excellent untuk research
✅ bisa handle complex projects
✅ Best untuk long conversations

### Cons:
❌ Lambat
❌ Mahal (banyak token)
❌ Butuh hardware kuat
❌ Response lebih lama

### Kapan Pakai:
- Research papers
- Codebase analysis
- Long document processing
- Complex problem solving

---

## 🎯 REKOMENDASI

| Tugas | Context Minimum | Rekomendasi |
|-------|-----------------|-------------|
| Basic chat | 2K | 4K-8K |
| Coding | 4K | 8K-32K |
| Research | 32K | 128K+ |
| Long documents | 64K | 256K+ |

---

## 💡 TIPS

1. Mulai dengan 4K context - cukup untuk大多数 tugas
2.Upgrade ke 8K/16K kalau perlu lebih
3. Tidak perlu 128K kalau tidak perlu

4. Neugi support 2K minimum - jadi bisa running di mana aja!
"""

# ============================================================
# 2026 MODELS - RECOMMENDED
# ============================================================

# These are hypothetical 2026 models (for reference/future planning)
2026_MODELS = {
    "groq": {
        "models": [
            "llama-4-scout-8b",  # 2026 - ultra fast
            "llama-4-force-32b",  # 2026 - large context
            "mixtral-3-large-8x22b",  # 2026 - mixture of experts
        ],
        "context": {
            "llama-4-scout-8b": 32768,
            "llama-4-force-32b": 131072,
            "mixtral-3-large-8x22b": 65536,
        }
    },
    "openrouter": {
        "models": [
            "google/gemini-ultra-3.0",  # 2026
            "openai/gpt-6",  # 2026
            "anthropic/claude-4-opus",  # 2026
            "meta/llama-4-400b",  # 2026
            "deepseek/r2",  # 2026
            "xai/grok-5",  # 2026
        ],
        "context": {
            "google/gemini-ultra-3.0": 2000000,  # 2M context!
            "openai/gpt-6": 1000000,
            "anthropic/claude-4-opus": 1500000,
            "meta/llama-4-400b": 200000,
            "deepseek/r2": 1000000,
            "xai/grok-5": 2000000,
        }
    },
    "ollama": {
        "models": [
            "llama4",  # 2026
            "mistral-large-3",  # 2026
            "qwen3-100b",  # 2026
            "phi-4-mini",  # 2026
        ],
        "context": {
            "llama4": 128000,
            "mistral-large-3": 128000,
            "qwen3-100b": 131072,
            "phi-4-mini": 65536,
        }
    },
    "local": {
        "llama_cpp": {
            "models": [
                "llama-3.1-8b-q4",  # ~5GB RAM
                "mistral-7b-q4",  # ~4GB RAM  
                "phi-3-mini-q4",  # ~2GB RAM - MINIMUM!
                "qwen-2.5-3b-q4",  # ~2GB RAM - MINIMUM!
            ],
            "min_context": 2048,  # Works with 2K!
            "recommended_context": 4096,
        }
    }
}

# ============================================================
# QUICK REFERENCE
# ============================================================

def get_model_for_context(context_needed: int) -> dict:
    """
    Get best model for required context
    """
    
    if context_needed <= 4096:
        return {
            "recommended": "phi-3-mini-q4",
            "provider": "llama.cpp / Ollama",
            "ram_needed": "~2GB",
            "type": "Local (FREE)"
        }
    elif context_needed <= 8192:
        return {
            "recommended": "llama-3.1-8b-instant",
            "provider": "Groq",
            "type": "API (FREE tier)",
            "speed": "Very Fast"
        }
    elif context_needed <= 32768:
        return {
            "recommended": "mixtral-8x7b-32768",
            "provider": "Groq",
            "type": "API (FREE tier)",
            "speed": "Fast"
        }
    elif context_needed <= 128000:
        return {
            "recommended": "google/gemini-2.0-flash-exp",
            "provider": "OpenRouter",
            "type": "API (FREE tier)",
            "context": "1M!"
        }
    else:
        return {
            "recommended": "google/gemini-ultra-3.0",
            "provider": "OpenRouter",
            "type": "API (Premium)",
            "context": "2M!"
        }

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    print("="*60)
    print("🤖 NEUGI SWARM - CONTEXT GUIDE")
    print("="*60)
    print()
    
    print(CONTEXT_GUIDE)
    
    print("\n" + "="*60)
    print("🎯 QUICK MODEL RECOMMENDATIONS")
    print("="*60)
    
    contexts = [2048, 4096, 8192, 32768, 128000, 1000000]
    
    for ctx in contexts:
        rec = get_model_for_context(ctx)
        print(f"\n📊 Context: {ctx:,} tokens")
        print(f"   Model: {rec['recommended']}")
        print(f"   Provider: {rec['provider']}")
        print(f"   Type: {rec.get('type', 'N/A')}")
    
    print("\n" + "="*60)
    print("✅ Neugi supports ALL context levels!")
    print("   Minimum: 2K tokens (works with small models!)")
    print("="*60)
