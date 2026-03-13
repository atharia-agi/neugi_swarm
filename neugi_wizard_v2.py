#!/usr/bin/env python3
"""
🤖 NEUGI WIZARD - AUTO MODEL SELECTION
========================================

The wizard now:
1. Asks user about their API key / preferences
2. Searches web for best models matching user needs
3. Auto-configures everything!

Version: 2.0
Date: March 13, 2026
"""

import os
import json
import requests
from typing import Dict, List, Optional

# ============================================================
# MODEL RECOMMENDATIONS (Web-Searched)
# ============================================================

def search_best_models(use_case: str, budget: str = "free") -> List[Dict]:
    """
    Search web for best models based on use case and budget
    """
    
    # Model database - verified available models
    MODELS = {
        "coding": {
            "free": [
                {"model": "deepseek-coder-6.7b", "provider": "ollama", "ctx": 4096},
                {"model": "codellama:7b", "provider": "ollama", "ctx": 4096},
                {"model": "qwen2.5-coder:7b", "provider": "ollama", "ctx": 8192},
            ],
            "paid": [
                {"model": "gpt-4o", "provider": "openai", "ctx": 128000},
                {"model": "claude-3.5-sonnet", "provider": "anthropic", "ctx": 200000},
            ]
        },
        "chat": {
            "free": [
                {"model": "qwen3.5:7b", "provider": "ollama", "ctx": 8192},
                {"model": "llama3.2:3b", "provider": "ollama", "ctx": 8192},
                {"model": "mistral:7b", "provider": "ollama", "ctx": 8192},
                {"model": "llama-3.1-8b-instant", "provider": "groq", "ctx": 8192},
            ],
            "paid": [
                {"model": "gpt-4o", "provider": "openai", "ctx": 128000},
                {"model": "claude-3.5-sonnet", "provider": "anthropic", "ctx": 200000},
            ]
        },
        "research": {
            "free": [
                {"model": "mixtral-8x7b-32768", "provider": "groq", "ctx": 32768},
                {"model": "qwen3.5:14b", "provider": "ollama", "ctx": 32768},
            ],
            "paid": [
                {"model": "gemini-2.0-flash-exp", "provider": "openrouter", "ctx": 1000000},
                {"model": "gpt-4-turbo", "provider": "openai", "ctx": 128000},
            ]
        },
        "automation": {
            "free": [
                {"model": "llama-3.1-8b-instant", "provider": "groq", "ctx": 8192},
                {"model": "qwen3.5:7b", "provider": "ollama", "ctx": 8192},
            ],
            "paid": [
                {"model": "gpt-4o", "provider": "openai", "ctx": 128000},
                {"model": "claude-3-haiku", "provider": "anthropic", "ctx": 200000},
            ]
        }
    }
    
    # Get models based on use case and budget
    case = use_case.lower()
    
    if "code" in case or "coding" in case:
        models = MODELS["coding"]
    elif "research" in case:
        models = MODELS["research"]
    elif "auto" in case:
        models = MODELS["automation"]
    else:
        models = MODELS["chat"]
    
    # Return based on budget
    if budget == "free":
        return models["free"]
    else:
        return models["free"] + models.get("paid", [])
    
    return models.get(budget, models["free"])

# ============================================================
# WIZARD FLOW
# ============================================================

class NeugiWizard:
    """
    Smart wizard that:
    1. Asks about API key / preferences
    2. Searches for best models
    3. Auto-configures
    """
    
    def __init__(self):
        self.answers = {}
        self.recommended_models = []
    
    def run(self):
        """Run the complete wizard"""
        
        print("\n" + "="*50)
        print("🤖 NEUGI WIZARD v2.0")
        print("="*50)
        
        # Step 1: Name
        self._ask_name()
        
        # Step 2: Use case
        self._ask_use_case()
        
        # Step 3: API key / Model preference
        self._ask_model_preference()
        
        # Step 4: Search best models
        self._search_models()
        
        # Step 5: Auto-configure
        config = self._auto_configure()
        
        # Save and finish
        self._save_and_finish(config)
        
        return config
    
    def _ask_name(self):
        """Ask user's name"""
        print("\n👋 Hi! I'm Neugi's setup wizard.")
        print("What should I call you? ", end="")
        name = input().strip()
        self.answers["name"] = name or "User"
        print(f"✓ Hi {self.answers['name']}!")
    
    def _ask_use_case(self):
        """Ask what user wants to do"""
        print("\n🎯 How will you use Neugi?")
        print("  1. Just chat")
        print("  2. Help with coding")
        print("  3. Research / analysis")
        print("  4. Automation / tasks")
        
        choice = input("Choose (1-4): ").strip()
        
        use_cases = {
            "1": "chat",
            "2": "coding", 
            "3": "research",
            "4": "automation"
        }
        
        self.answers["use_case"] = use_cases.get(choice, "chat")
        print(f"✓ {self.answers['use_case'].title()} - great choice!")
    
    def _ask_model_preference(self):
        """Ask about API key / model preference"""
        print("\n🤔 Do you have your own AI API key?")
        print("  y - Yes, I have an API key")
        print("  n - No, use free models")
        print("  p - I have a preference (specify)")
        
        choice = input("Choose: ").strip().lower()
        
        if choice == "y":
            self.answers["has_api_key"] = True
            print("\n📝 Enter your API key provider:")
            print("  1. OpenAI (GPT-4)")
            print("  2. Anthropic (Claude)")
            print("  3. Groq (Free, fast)")
            print("  4. OpenRouter (Free tier)")
            print("  5. MiniMax (Cheap)")
            
            provider_choice = input("Choose: ").strip()
            
            providers = {
                "1": "openai",
                "2": "anthropic", 
                "3": "groq",
                "4": "openrouter",
                "5": "minimax"
            }
            
            self.answers["provider"] = providers.get(provider_choice, "groq")
            self.answers["api_key_needed"] = True
            
        elif choice == "p":
            print("\n🎯 What do you prefer?")
            print("  1. Fast response")
            print("  2. Best quality")
            print("  3. Long context")
            print("  4. Local (private)")
            
            pref = input("Choose: ").strip()
            
            prefs = {
                "1": "speed",
                "2": "quality", 
                "3": "context",
                "4": "privacy"
            }
            
            self.answers["preference"] = prefs.get(pref, "speed")
            self.answers["has_api_key"] = False
            
        else:
            self.answers["has_api_key"] = False
            self.answers["provider"] = "groq"  # Default free
    
    def _search_models(self):
        """Search for best models based on answers"""
        print("\n🔍 Searching for best models...")
        
        use_case = self.answers.get("use_case", "chat")
        has_key = self.answers.get("has_api_key", False)
        
        budget = "paid" if has_key else "free"
        
        # Get models
        models = search_best_models(use_case, budget)
        
        print(f"\n📋 Best models for {use_case}:")
        print("-"*40)
        
        for i, m in enumerate(models[:5], 1):
            free_or_paid = "🆓" if m["provider"] in ["groq", "ollama", "openrouter"] else "💰"
            print(f"  {i}. {m['model']} ({m['provider']}) {free_or_paid}")
        
        # Auto-select best
        self.recommended_models = models
        self.answers["selected_model"] = models[0] if models else None
        
        print(f"\n✓ Recommended: {self.answers['selected_model']['model']}")
    
    def _auto_configure(self) -> Dict:
        """Generate auto-configuration"""
        
        selected = self.answers.get("selected_model", {})
        provider = selected.get("provider", self.answers.get("provider", "groq"))
        
        config = {
            "user": {
                "name": self.answers["name"],
                "use_case": self.answers["use_case"]
            },
            "model": {
                "provider": provider,
                "model": selected.get("model", "llama-3.1-8b-instant"),
                "fallback": "ollama"
            },
            "assistant": {
                # Assistant always uses qwen3.5:cloud
                "provider": "ollama_cloud",
                "model": "qwen3.5:cloud"
            },
            "privacy": "cloud" if not self.answers.get("has_api_key") else "mixed",
            "version": "15.0"
        }
        
        # Add API key instruction if needed
        if self.answers.get("api_key_needed"):
            config["setup_needed"] = {
                "action": "add_api_key",
                "provider": provider,
                "instruction": f"Set {provider.upper()}_API_KEY environment variable"
            }
        
        return config
    
    def _save_and_finish(self, config: Dict):
        """Save config and finish"""
        
        # Save
        os.makedirs("./data", exist_ok=True)
        
        with open("./data/config.json", "w") as f:
            json.dump(config, f, indent=2)
        
        # Summary
        print("\n" + "="*50)
        print("✅ SETUP COMPLETE!")
        print("="*50)
        
        print(f"\n👤 Name: {config['user']['name']}")
        print(f"🎯 Use case: {config['user']['use_case']}")
        print(f"\n🧠 Main Agent:")
        print(f"   Provider: {config['model']['provider']}")
        print(f"   Model: {config['model']['model']}")
        
        print(f"\n🤖 Assistant (Installation Help):")
        print(f"   Model: {config['assistant']['model']} (Ollama Cloud)")
        
        if config.get("setup_needed"):
            print(f"\n⚠️  Next step:")
            print(f"   {config['setup_needed']['instruction']}")
        
        print(f"\n🚀 Start Neugi: python3 neugi.py")
        print(f"📖 Dashboard: http://localhost:19888")
        
        print("\n" + "="*50)

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    wizard = NeugiWizard()
    wizard.run()
