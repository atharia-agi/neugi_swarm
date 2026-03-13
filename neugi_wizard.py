#!/usr/bin/env python3
"""
🤖 NEUGI WIZARD v2.2 - Streamlined Setup
==============================================

Flow:
1. Check Ollama
2. Ask name & use case  
3. Ask: "Do you have API key?"
   - NO → Use Ollama Cloud (auto)
   - YES → Ask for API key + desired model → Help setup until works!

Version: 2.2
Date: March 13, 2026
"""

import os
import json
import requests

# ============================================================
# CHECK OLLAMA
# ============================================================

def check_ollama() -> bool:
    """Check if Ollama is running"""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.ok
    except:
        return False

# ============================================================
# MODEL LISTS
# ============================================================

OLLAMA_CLOUD = [
    {"model": "qwen3.5:cloud", "ctx": 32768, "best_for": "all-round"},
    {"model": "qwen3.5:7b", "ctx": 8192, "best_for": "chat"},
]

PROVIDERS = {
    "openai": {"name": "OpenAI", "env": "OPENAI_API_KEY", "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]},
    "anthropic": {"name": "Anthropic Claude", "env": "ANTHROPIC_API_KEY", "models": ["claude-sonnet-4", "claude-3.5-sonnet", "claude-3-haiku"]},
    "groq": {"name": "Groq", "env": "GROQ_API_KEY", "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "llama-3.1-8b-instant"]},
    "openrouter": {"name": "OpenRouter", "env": "OPENROUTER_API_KEY", "models": ["google/gemini-2.0-flash-exp", "meta-llama/llama-3.1-8b-instant", "google/gemini-1.5-flash"]},
    "minimax": {"name": "MiniMax", "env": "MINIMAX_API_KEY", "models": ["MiniMax-M2.5", "MiniMax-Text-01"]},
}

# ============================================================
# WIZARD
# ============================================================

class NeugiWizard:
    def __init__(self):
        self.answers = {}
        self.config = {}
        self.ollama_ok = False
    
    def run(self):
        print("\n" + "="*60)
        print("🤖 NEUGI WIZARD v2.2")
        print("="*60)
        
        # 0. Check Ollama
        self._check_ollama()
        
        # 1. Name
        self._ask_name()
        
        # 2. Use case
        self._ask_use_case()
        
        # 3. API Key Question
        has_key = self._ask_api_key_question()
        
        # 4. Configure
        if has_key:
            self._setup_with_key()
        else:
            self._setup_ollama_cloud()
        
        # 5. Save
        self._save()
    
    def _check_ollama(self):
        print("\n🔍 Checking Ollama server...")
        self.ollama_ok = check_ollama()
        
        if self.ollama_ok:
            print("✅ Ollama is running!\n")
        else:
            print("⚠️ Ollama not running\n")
            print("   To start: ollama serve")
            print("   Or use: OLLAMA_API_KEY env\n")
    
    def _ask_name(self):
        print("👋 Hi! I'm Neugi's setup wizard.")
        name = input("What should I call you? ").strip()
        self.answers["name"] = name or "User"
        print(f"✓ Nice to meet you, {self.answers['name']}!\n")
    
    def _ask_use_case(self):
        print("🎯 How will you use Neugi?")
        print("   1. Just chat")
        print("   2. Help with coding")
        print("   3. Research / analysis")
        print("   4. Automation / tasks")
        
        choice = input("\nChoose (1-4): ").strip()
        cases = {"1": "chat", "2": "coding", "3": "research", "4": "automation"}
        self.answers["use_case"] = cases.get(choice, "chat")
        print(f"✓ {self.answers['use_case'].title()}!\n")
    
    def _ask_api_key_question(self) -> bool:
        print("="*60)
        print("❓ DO YOU HAVE AN API KEY?")
        print("="*60)
        print("\n   y - YES, I have an API key (I'll help set it up!)")
        print("   n - NO, use free Ollama Cloud models")
        print()
        
        choice = input("Your answer (y/n): ").strip().lower()
        
        if choice == "y":
            self.answers["has_api_key"] = True
            print("\n✅ Great! Let's set up your API key!\n")
            return True
        else:
            self.answers["has_api_key"] = False
            print("\n✅ No problem! I'll use free Ollama Cloud!\n")
            return False
    
    def _setup_with_key(self):
        """User HAS API key - help set up!"""
        print("="*60)
        print("🔑 SET UP YOUR API KEY")
        print("="*60)
        
        # List providers
        print("\n📋 Available providers:")
        for i, (key, p) in enumerate(PROVIDERS.items(), 1):
            free = " 🆓 FREE" if "Groq" in p["name"] or "OpenRouter" in p["name"] else ""
            print(f"   {i}. {p['name']}{free}")
        
        # Choose provider
        choice = input("\nChoose provider (1-5): ").strip()
        provider_keys = list(PROVIDERS.keys())
        provider = provider_keys[int(choice)-1] if choice.isdigit() and 1 <= int(choice) <= 5 else "groq"
        
        p = PROVIDERS[provider]
        print(f"\n✓ {p['name']}")
        
        # Show models
        print(f"\n📋 Available models for {p['name']}:")
        for i, model in enumerate(p["models"], 1):
            print(f"   {i}. {model}")
        
        # Choose model
        choice2 = input(f"\nChoose model (default: 1): ").strip()
        model = p["models"][0] if not choice2 else p["models"][int(choice2)-1]
        
        # Get API key
        print(f"\n📝 ENTER YOUR {p['name'].upper()} API KEY")
        print(f"   Get it from: ", end="")
        if provider == "openai": print("https://platform.openai.com")
        elif provider == "anthropic": print("https://console.anthropic.com")
        elif provider == "groq": print("https://console.groq.com")
        elif provider == "openrouter": print("https://openrouter.ai")
        else: print("https://platform.minimax.io")
        
        api_key = input(f"\n{p['name']} API Key: ").strip()
        
        if not api_key:
            # Try env variable
            api_key = os.environ.get(p["env"], "")
        
        # Test connection
        print("\n🧪 Testing connection...")
        
        success = self._test_key(provider, api_key)
        
        if success:
            print("✅ Connection successful!\n")
        else:
            print("⚠️ Could not verify, but will try anyway!\n")
        
        # Save config
        self.config = {
            "user": {"name": self.answers["name"]},
            "use_case": self.answers["use_case"],
            "model": {
                "provider": provider,
                "model": model,
            },
            "assistant": {
                "provider": "ollama_cloud",
                "model": "qwen3.5:cloud"
            },
            "technician": {"enabled": True},
            "privacy": "cloud",
            "api_key_set": bool(api_key)
        }
        
        print("✅ API key configuration saved!")
    
    def _setup_ollama_cloud(self):
        """No API key - use Ollama Cloud"""
        print("="*60)
        print("☁️  SETUP: OLLAMA CLOUD (FREE)")
        print("="*60)
        
        # Use qwen3.5:cloud (same as assistant!)
        model = OLLAMA_CLOUD[0]
        
        print(f"\n✓ Using: {model['model']}")
        print(f"   Context: {model['ctx']:,} tokens")
        print(f"   Best for: {model['best_for']}\n")
        
        self.config = {
            "user": {"name": self.answers["name"]},
            "use_case": self.answers["use_case"],
            "model": {
                "provider": "ollama_cloud",
                "model": model["model"],
                "ctx": model["ctx"]
            },
            "assistant": {
                "provider": "ollama_cloud",
                "model": "qwen3.5:cloud"
            },
            "technician": {"enabled": True},
            "privacy": "cloud"
        }
        
        print("✅ Auto-configured with Ollama Cloud!")
    
    def _test_key(self, provider: str, key: str) -> bool:
        """Test API key"""
        if not key:
            return False
        
        try:
            if provider == "groq":
                r = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=10
                )
                return r.ok
            elif provider == "openai":
                r = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=10
                )
                return r.ok
            elif provider == "openrouter":
                r = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=10
                )
                return r.ok
        except:
            pass
        
        return False
    
    def _save(self):
        """Save config"""
        os.makedirs("./data", exist_ok=True)
        
        with open("./data/config.json", "w") as f:
            json.dump(self.config, f, indent=2)
        
        print("\n" + "="*60)
        print("✅ SETUP COMPLETE!")
        print("="*60)
        
        print(f"\n👤 Name: {self.config['user']['name']}")
        print(f"🎯 Use: {self.config['user']['use_case']}")
        
        print(f"\n🧠 Main Agent: {self.config['model']['provider']} / {self.config['model']['model']}")
        print(f"🤖 Assistant: {self.config['assistant']['model']} (Ollama Cloud)")
        
        print("\n🚀 Start: python3 neugi.py")
        print("📖 Dashboard: http://localhost:19888")
        print("="*60 + "\n")

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    wizard = NeugiWizard()
    wizard.run()
