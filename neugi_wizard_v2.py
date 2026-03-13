#!/usr/bin/env python3
"""
🤖 NEUGI WIZARD v2.1 - Smart Model Selection
===============================================

Logic:
- If NO API key → Use Ollama Cloud (same as assistant!)
- If YES API key → Help setup until it works!

Version: 2.1
Date: March 13, 2026
"""

import os
import json
import requests

# ============================================================
# MODEL DATABASE
# ============================================================

# Ollama Cloud Models (Free, same as Assistant!)
OLLAMA_CLOUD_MODELS = [
    {"model": "qwen3.5:cloud", "ctx": 32768, "best_for": "all-round"},
    {"model": "qwen3.5:7b", "ctx": 8192, "best_for": "chat"},
    {"model": "qwen3.5:3b", "ctx": 8192, "best_for": "lightweight"},
    {"model": "llama3.2:3b", "ctx": 8192, "best_for": "quality"},
    {"model": "mistral:7b", "ctx": 8192, "best_for": "general"},
]

# API Provider Models (If user has their own key)
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
    - No API key? → Use Ollama Cloud (free, works!)
    - Has API key? → Help setup until it works!
    """
    
    def __init__(self):
        self.answers = {}
        self.config = {}
    
    def run(self):
        """Run complete wizard flow"""
        
        print("\n" + "="*60)
        print("🤖 NEUGI WIZARD v2.1")
        print("="*60)
        
        # Step 1: Name
        self._ask_name()
        
        # Step 2: Use case
        self._ask_use_case()
        
        # Step 3: API Key Question (CRITICAL!)
        has_api_key = self._ask_api_key()
        
        # Step 4: Configure based on answer
        if has_api_key:
            # User HAS API key → Help setup
            self._setup_with_api_key()
        else:
            # No API key → Use Ollama Cloud (same as assistant!)
            self._setup_ollama_cloud()
        
        # Step 5: Save and finish
        self._save_and_finish()
    
    def _ask_name(self):
        """Ask user's name"""
        print("\n👋 Hi! I'm Neugi's setup wizard.")
        print("What should I call you? ", end="")
        name = input().strip()
        self.answers["name"] = name or "User"
        print(f"✓ Great to meet you, {self.answers['name']}!")
    
    def _ask_use_case(self):
        """Ask what user wants to do"""
        print("\n🎯 How will you use Neugi?")
        print("  1. Just chat with AI")
        print("  2. Help with coding")
        print("  3. Research and analysis")
        print("  4. Automation and tasks")
        
        choice = input("\nChoose (1-4): ").strip()
        
        use_cases = {
            "1": "chat", "2": "coding", 
            "3": "research", "4": "automation"
        }
        self.answers["use_case"] = use_cases.get(choice, "chat")
        print(f"✓ {self.answers['use_case'].title()} - awesome!")
    
    def _ask_api_key(self) -> bool:
        """
        CRITICAL QUESTION: Does user have API key?
        """
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
        """
        NO API KEY → Use Ollama Cloud (same as Assistant!)
        """
        print("\n" + "="*60)
        print("☁️  SETUP: OLLAMA CLOUD (FREE)")
        print("="*60)
        
        # Same model as Assistant uses!
        selected_model = OLLAMA_CLOUD_MODELS[0]  # qwen3.5:cloud
        
        print(f"\n✓ Using: {selected_model['model']}")
        print(f"  Context: {selected_model['ctx']:,}")
        print(f"  Best for: {selected_model['best_for']}")
        
        # Set config
        self.config = {
            "user": {"name": self.answers["name"]},
            "use_case": self.answers["use_case"],
            "model": {
                "provider": "ollama_cloud",
                "model": selected_model["model"],
                "ctx": selected_model["ctx"]
            },
            "assistant": {
                # Same as main agent!
                "provider": "ollama_cloud",
                "model": "qwen3.5:cloud"
            },
            "technician": {
                "enabled": True
            },
            "privacy": "cloud"
        }
        
        print("\n✅ Auto-configured with Ollama Cloud!")
    
    def _setup_with_api_key(self):
        """
        HAS API KEY → Help set up until it works!
        """
        print("\n" + "="*60)
        print("🔑 SETUP: YOUR API KEY")
        print("="*60)
        
        # Step 1: Choose provider
        print("\nWhich provider?")
        for i, (key, provider) in enumerate(API_PROVIDERS.items(), 1):
            free_tag = " 🆓 FREE!" if "Free" in provider["name"] else ""
            print(f"  {i}. {provider['name']}{free_tag}")
        
        choice = input("\nChoose (1-4): ").strip()
        provider_keys = list(API_PROVIDERS.keys())
        selected_provider = provider_keys[int(choice)-1] if choice.isdigit() and 1 <= int(choice) <= 4 else "groq"
        
        provider_info = API_PROVIDERS[selected_provider]
        
        print(f"\n✓ {provider_info['name']}")
        
        # Step 2: Show available models
        print("\n📋 Available models:")
        for i, model in enumerate(provider_info["models"], 1):
            print(f"  {i}. {model['model']}")
            print(f"     Context: {model['ctx']:,} | Best for: {model['best_for']}")
        
        choice2 = input("\nChoose model (default: 1): ").strip()
        selected_model = provider_info["models"][0] if not choice2 else provider_info["models"][int(choice2)-1]
        
        # Step 3: Get API key
        print("\n" + "-"*60)
        print("📝 ENTER YOUR API KEY")
        print("-"*60)
        print(f"Get your key from: {provider_info['signup']}")
        print(f"Or set environment: export {provider_info['key_env']}='your-key-here'")
        print()
        
        api_key = input(f"Enter {provider_info['name']} API key: ").strip()
        
        if not api_key:
            print("\n⚠️ No API key entered.")
            print("Will use environment variable instead.")
        
        # Step 4: Test connection
        print("\n🧪 Testing connection...")
        
        test_result = self._test_api_key(selected_provider, api_key or os.environ.get(provider_info["key_env"]))
        
        if test_result["success"]:
            print("✅ Connection successful!")
            
            self.config = {
                "user": {"name": self.answers["name"]},
                "use_case": self.answers["use_case"],
                "model": {
                    "provider": selected_provider,
                    "model": selected_model["model"],
                    "ctx": selected_model["ctx"]
                },
                "assistant": {
                    # Assistant still uses qwen3.5:cloud!
                    "provider": "ollama_cloud",
                    "model": "qwen3.5:cloud"
                },
                "technician": {
                    "enabled": True
                },
                "privacy": "cloud",
                "api_key_set": bool(api_key)
            }
            
            print("\n✅ Setup complete! Your API key is configured!")
        
        else:
            # If test fails, still configure but warn
            print(f"⚠️ Connection test failed: {test_result['error']}")
            print("But I've configured the settings. You can try again later!")
            
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
                "api_key_set": False,
                "setup_issue": test_result["error"]
            }
    
    def _test_api_key(self, provider: str, api_key: str = None) -> dict:
        """Test if API key works"""
        
        if not api_key:
            # Check environment
            env_keys = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "groq": "GROQ_API_KEY",
                "openrouter": "OPENROUTER_API_KEY"
            }
            api_key = os.environ.get(env_keys.get(provider, ""))
        
        if not api_key:
            return {"success": False, "error": "No API key provided"}
        
        # Simple test based on provider
        try:
            if provider == "groq":
                r = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=5
                )
                return {"success": r.ok, "error": None if r.ok else r.text[:100]}
            
            elif provider == "openai":
                r = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=5
                )
                return {"success": r.ok, "error": None if r.ok else r.text[:100]}
            
            elif provider == "openrouter":
                r = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=5
                )
                return {"success": r.ok, "error": None if r.ok else r.text[:100]}
            
            return {"success": False, "error": "Unknown provider"}
        
        except Exception as e:
            return {"success": False, "error": str(e)[:100]}
    
    def _save_and_finish(self):
        """Save config and show summary"""
        
        # Save
        os.makedirs("./data", exist_ok=True)
        
        with open("./data/config.json", "w") as f:
            json.dump(self.config, f, indent=2)
        
        # Summary
        print("\n" + "="*60)
        print("✅ SETUP COMPLETE!")
        print("="*60)
        
        print(f"\n👤 Name: {self.config['user']['name']}")
        print(f"🎯 Use case: {self.config['user']['use_case']}")
        
        print(f"\n🧠 Main Agent:")
        print(f"   Provider: {self.config['model']['provider']}")
        print(f"   Model: {self.config['model']['model']}")
        
        print(f"\n🤖 Assistant (Installation Help):")
        print(f"   Model: {self.config['assistant']['model']} (Ollama Cloud)")
        
        print(f"\n🔧 Technician: {self.config['technician']['enabled']}")
        
        print("\n" + "="*60)
        print("\n🚀 START NEUGI:")
        print("   python3 neugi.py")
        print("\n📖 Dashboard:")
        print("   http://localhost:19888")
        print("="*60)

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    wizard = NeugiWizard()
    wizard.run()
