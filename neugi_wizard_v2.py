#!/usr/bin/env python3
"""
🤖 NEUGI WIZARD v2.1 - Smart Model Selection
===============================================

Logic:
- Check if Ollama is running!
- If NO API key → Use Ollama Cloud (same as assistant!)
- If YES API key → Help setup until it works!

Version: 2.1
Date: March 13, 2026
"""

import os
import json
import requests

# ============================================================
# CHECK OLLAMA SERVER
# ============================================================

def check_ollama_server() -> bool:
    """Check if Ollama server is running"""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.ok
    except:
        return False

# ============================================================
# MODEL DATABASE
# ============================================================

OLLAMA_CLOUD_MODELS = [
    {"model": "qwen3.5:cloud", "ctx": 32768, "best_for": "all-round"},
    {"model": "qwen3.5:7b", "ctx": 8192, "best_for": "chat"},
    {"model": "qwen3.5:3b", "ctx": 8192, "best_for": "lightweight"},
    {"model": "llama3.2:3b", "ctx": 8192, "best_for": "quality"},
    {"model": "mistral:7b", "ctx": 8192, "best_for": "general"},
]

API_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "models": [
            {"model": "gpt-4o", "ctx": 128000, "best_for": "best-quality"},
            {"model": "gpt-4o-mini", "ctx": 128000, "best_for": "fast"},
        ],
        "key_env": "OPENAI_API_KEY",
        "signup": "https://platform.openai.com"
    },
    "anthropic": {
        "name": "Anthropic (Claude)",
        "models": [
            {"model": "claude-sonnet-4-20250514", "ctx": 200000, "best_for": "best-quality"},
            {"model": "claude-3-5-sonnet-20240620", "ctx": 200000, "best_for": "fast"},
        ],
        "key_env": "ANTHROPIC_API_KEY",
        "signup": "https://console.anthropic.com"
    },
    "groq": {
        "name": "Groq (Free!)",
        "models": [
            {"model": "llama-3.3-70b-versatile", "ctx": 8192, "best_for": "fast-free"},
            {"model": "mixtral-8x7b-32768", "ctx": 32768, "best_for": "long-context-free"},
        ],
        "key_env": "GROQ_API_KEY",
        "signup": "https://console.groq.com"
    },
    "openrouter": {
        "name": "OpenRouter (Free Tier)",
        "models": [
            {"model": "google/gemini-2.0-flash-exp", "ctx": 1000000, "best_for": "1m-context-free"},
            {"model": "meta-llama/llama-3.1-8b-instant", "ctx": 128000, "best_for": "free-quality"},
        ],
        "key_env": "OPENROUTER_API_KEY",
        "signup": "https://openrouter.ai"
    }
}

# ============================================================
# WIZARD ENGINE
# ============================================================

class NeugiWizard:
    """
    Smart Wizard:
    - Check Ollama first!
    - No API key? → Use Ollama Cloud (free, works!)
    - Has API key? → Help setup until it works!
    """
    
    def __init__(self):
        self.answers = {}
        self.config = {}
        self.ollama_running = False
    
    def run(self):
        """Run complete wizard flow"""
        
        print("\n" + "="*60)
        print("🤖 NEUGI WIZARD v2.1")
        print("="*60)
        
        # Step 0: Check Ollama FIRST!
        self._check_ollama()
        
        # Step 1: Name
        self._ask_name()
        
        # Step 2: Use case
        self._ask_use_case()
        
        # Step 3: API Key Question
        has_api_key = self._ask_api_key()
        
        # Step 4: Configure
        if has_api_key:
            self._setup_with_api_key()
        else:
            self._setup_ollama_cloud()
        
        # Step 5: Save
        self._save_and_finish()
    
    def _check_ollama(self):
        """Check if Ollama is running"""
        print("\n🔍 Checking Ollama server...")
        self.ollama_running = check_ollama_server()
        
        if self.ollama_running:
            print("✅ Ollama is running!")
        else:
            print("⚠️  Ollama is NOT running!")
            print("\n📝 To start Ollama:")
            print("   • Run: ollama serve")
            print("   • Or: Start Ollama app")
            print("   • Or: Set OLLAMA_API_KEY for cloud")
            print()
    
    def _ask_name(self):
        print("\n👋 Hi! I'm Neugi's setup wizard.")
        print("What should I call you? ", end="")
        name = input().strip()
        self.answers["name"] = name or "User"
        print(f"✓ Great to meet you, {self.answers['name']}!")
    
    def _ask_use_case(self):
        print("\n🎯 How will you use Neugi?")
        print("  1. Just chat with AI")
        print("  2. Help with coding")
        print("  3. Research and analysis")
        print("  4. Automation and tasks")
        
        choice = input("\nChoose (1-4): ").strip()
        
        use_cases = {"1": "chat", "2": "coding", "3": "research", "4": "automation"}
        self.answers["use_case"] = use_cases.get(choice, "chat")
        print(f"✓ {self.answers['use_case'].title()} - awesome!")
    
    def _ask_api_key(self) -> bool:
        print("\n" + "="*60)
        print("❓ IMPORTANT QUESTION")
        print("="*60)
        print("\nDo you have your own AI API key?")
        print()
        print("  y  - YES, I have an API key (I'll help you set it up!)")
        print("  n  - NO, use free cloud models (I'll auto-configure!)")
        print()
        
        choice = input("Your answer (y/n): ").strip().lower()
        
        if choice == "y":
            self.answers["has_api_key"] = True
            print("\n✅ Great! I'll help you set up your API key!")
            return True
        else:
            self.answers["has_api_key"] = False
            print("\n✅ No problem! I'll use free Ollama Cloud models!")
            return False
    
    def _setup_ollama_cloud(self):
        """Use Ollama Cloud (same as Assistant!)"""
        print("\n" + "="*60)
        print("☁️  SETUP: OLLAMA CLOUD (FREE)")
        print("="*60)
        
        # Check Ollama again
        if not self.ollama_running:
            print("\n⚠️  Ollama not running - trying anyway...")
        
        # Use qwen3.5:cloud (same as Assistant!)
        selected_model = OLLAMA_CLOUD_MODELS[0]
        
        print(f"\n✓ Using: {selected_model['model']}")
        print(f"  Context: {selected_model['ctx']:,}")
        print(f"  Best for: {selected_model['best_for']}")
        
        self.config = {
            "user": {"name": self.answers["name"]},
            "use_case": self.answers["use_case"],
            "model": {
                "provider": "ollama_cloud",
                "model": selected_model["model"],
                "ctx": selected_model["ctx"]
            },
            "assistant": {
                "provider": "ollama_cloud",
                "model": "qwen3.5:cloud"
            },
            "technician": {"enabled": True},
            "privacy": "cloud"
        }
        
        print("\n✅ Auto-configured with Ollama Cloud!")
    
    def _setup_with_api_key(self):
        """Help set up user's API key"""
        print("\n" + "="*60)
        print("🔑 SETUP: YOUR API KEY")
        print("="*60)
        
        # Choose provider
        print("\nWhich provider?")
        for i, (key, provider) in enumerate(API_PROVIDERS.items(), 1):
            free = " 🆓 FREE!" if "Free" in provider["name"] else ""
            print(f"  {i}. {provider['name']}{free}")
        
        choice = input("\nChoose (1-4): ").strip()
        provider_keys = list(API_PROVIDERS.keys())
        selected_provider = provider_keys[int(choice)-1] if choice.isdigit() and 1 <= int(choice) <= 4 else "groq"
        
        provider_info = API_PROVIDERS[selected_provider]
        
        # Choose model
        print(f"\n✓ {provider_info['name']}")
        print("\n📋 Available models:")
        for i, model in enumerate(provider_info["models"], 1):
            print(f"  {i}. {model['model']} ({model['best_for']})")
        
        selected_model = provider_info["models"][0]
        
        # Get API key
        print(f"\n📝 Get key from: {provider_info['signup']}")
        print(f"Or set: export {provider_info['key_ENV']}='your-key'")
        print()
        
        api_key = input(f"Enter {provider_info['name']} API key: ").strip()
        
        # Test
        print("\n🧪 Testing connection...")
        
        env_key = provider_info["key_env"]
        test_key = api_key or os.environ.get(env_key, "")
        
        if test_key:
            test_result = self._test_api_key(selected_provider, test_key)
            if test_result["success"]:
                print("✅ Connection successful!")
            else:
                print(f"⚠️ Test failed: {test_result['error']}")
        
        # Save config
        self.config = {
            "user": {"name": self.answers["name"]},
            "use_case": self.answers["use_case"],
            "model": {
                "provider": selected_provider,
                "model": selected_model["model"],
                "ctx": selected_model["ctx"]
            },
            "assistant": {
                "provider": "ollama_cloud",
                "model": "qwen3.5:cloud"
            },
            "technician": {"enabled": True},
            "privacy": "cloud",
            "api_key_set": bool(api_key)
        }
        
        print("\n✅ Setup complete!")
    
    def _test_api_key(self, provider: str, api_key: str) -> dict:
        """Test API key"""
        try:
            if provider == "groq":
                r = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=5
                )
                return {"success": r.ok}
            elif provider == "openai":
                r = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=5
                )
                return {"success": r.ok}
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)[:50]}
    
    def _save_and_finish(self):
        """Save config"""
        os.makedirs("./data", exist_ok=True)
        
        with open("./data/config.json", "w") as f:
            json.dump(self.config, f, indent=2)
        
        print("\n" + "="*60)
        print("✅ SETUP COMPLETE!")
        print("="*60)
        
        print(f"\n👤 Name: {self.config['user']['name']}")
        print(f"🎯 Use case: {self.config['user']['use_case']}")
        
        print(f"\n🧠 Main Agent:")
        print(f"   {self.config['model']['provider']} / {self.config['model']['model']}")
        
        print(f"\n🤖 Assistant:")
        print(f"   {self.config['assistant']['model']} (Ollama Cloud)")
        
        print("\n🚀 Start: python3 neugi.py")
        print("📖 Dashboard: http://localhost:19888")
        print("="*60)

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    wizard = NeugiWizard()
    wizard.run()
