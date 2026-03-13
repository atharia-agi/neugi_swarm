#!/usr/bin/env python3
"""
🤖 NEUGI WIZARD v2.4 - Auto Start Ollama
==========================================

Auto-start Ollama if not running!
Corporate Brand: NEUGI (capital GI!)

Version: 2.4
Date: March 13, 2026
"""

import os
import json
import requests
import subprocess
import sys
import threading
import time

BRAND = "NEUGI"  # Corporate branding!

# ============================================================
# OLLAMA MANAGER
# ============================================================

class OllamaManager:
    """Auto-manage Ollama server"""
    
    @staticmethod
    def is_running() -> bool:
        """Check if Ollama is running"""
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            return r.ok
        except:
            return False
    
    @staticmethod
    def start_background() -> bool:
        """Start Ollama in background automatically"""
        print("   ⚡ Starting Ollama automatically...")
        
        # Try different methods to start in background
        try:
            # Method 1: ollama serve (background)
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            # Wait and check
            for i in range(10):
                time.sleep(1)
                if OllamaManager.is_running():
                    print("   ✅ Ollama started automatically!")
                    return True
            
        except:
            pass
        
        # Method 2: Try just "ollama"
        try:
            subprocess.Popen(
                ["ollama"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            for i in range(10):
                time.sleep(1)
                if OllamaManager.is_running():
                    print("   ✅ Ollama started!")
                    return True
        except:
            pass
        
        return False
    
    @staticmethod
    def ensure_running() -> bool:
        """Ensure Ollama is running, start if needed"""
        
        if OllamaManager.is_running():
            return True
        
        # Try to start automatically
        if OllamaManager.start_background():
            return True
        
        # If still not running, tell user
        print("\n📌 Ollama couldn't start automatically.")
        print("Please start Ollama manually, then run wizard again.")
        return False

# ============================================================
# MODELS
# ============================================================

OLLAMA_MODELS = [
    {"model": "qwen3.5:cloud", "ctx": 32768},
    {"model": "qwen3.5:7b", "ctx": 8192},
]

PROVIDERS = {
    "openai": {"name": "OpenAI", "env": "OPENAI_API_KEY",
               "url": "https://platform.openai.com",
               "models": ["gpt-4o", "gpt-4o-mini"]},
    "anthropic": {"name": "Anthropic Claude", "env": "ANTHROPIC_API_KEY",
                  "url": "https://console.anthropic.com",
                  "models": ["claude-sonnet-4", "claude-3.5-sonnet"]},
    "groq": {"name": "Groq", "env": "GROQ_API_KEY",
             "url": "https://console.groq.com",
             "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]},
    "openrouter": {"name": "OpenRouter", "env": "OPENROUTER_API_KEY",
                   "url": "https://openrouter.ai",
                   "models": ["google/gemini-2.0-flash-exp"]},
}

# ============================================================
# WIZARD
# ============================================================

class NEUGIWizard:
    def __init__(self):
        self.answers = {}
        self.config = {}
    
    def run(self):
        print(f"\n{'='*60}")
        print(f"🤖 {BRAND} WIZARD v2.4")
        print(f"{'='*60}")
        
        # STEP 1: Ensure Ollama Running (Auto!)
        if not self._step_ollama():
            print(f"\n❌ Cannot continue without Ollama.")
            return
        
        # STEP 2-5: Other Steps
        self._step_name()
        self._step_use_case()
        self._step_api_key()
        self._save()
    
    def _step_ollama(self) -> bool:
        """Step 1: Ensure Ollama is running (auto-start!)"""
        print(f"\n🔍 Step 1: Checking Ollama...")
        
        if OllamaManager.is_running():
            print(f"   ✅ Ollama is running!")
            return True
        
        print(f"   ⚠️ Ollama not running...")
        print(f"   🤖 {BRAND} will start it automatically...")
        
        return OllamaManager.ensure_running()
    
    def _step_name(self):
        print(f"\n{'-'*60}")
        print("👋 Step 2: Your Name")
        print(f"{'-'*60}")
        name = input("What should I call you? ").strip()
        self.answers["name"] = name or "User"
        print(f"✓ Nice to meet you, {self.answers['name']}!")
    
    def _step_use_case(self):
        print(f"\n{'-'*60}")
        print("🎯 Step 3: How will you use NEUGI?")
        print(f"{'-'*60}")
        print("   1. Just chat")
        print("   2. Help with coding")
        print("   3. Research / analysis")
        print("   4. Automation")
        
        choice = input("\nChoose (1-4): ").strip()
        cases = {"1": "chat", "2": "coding", "3": "research", "4": "automation"}
        self.answers["use_case"] = cases.get(choice, "chat")
        print(f"✓ {self.answers['use_case'].title()}!")
    
    def _step_api_key(self):
        print(f"\n{'-'*60}")
        print("🔑 Step 4: API Key")
        print(f"{'-'*60}")
        
        print("\nDo you have your own AI API key?")
        print("   y - YES, I have an API key")
        print("   n - NO, use free Ollama Cloud")
        
        choice = input("\nAnswer (y/n): ").strip().lower()
        
        if choice == "y":
            self._setup_with_key()
        else:
            self._setup_ollama()
    
    def _setup_with_key(self):
        print("\n📋 Available providers:")
        for i, (k, p) in enumerate(PROVIDERS.items(), 1):
            free = " 🆓" if k in ["groq", "openrouter"] else ""
            print(f"   {i}. {p['name']}{free}")
        
        choice = input("\nChoose (1-4): ").strip()
        provider_keys = list(PROVIDERS.keys())
        provider = provider_keys[int(choice)-1] if choice.isdigit() and 1 <= int(choice) <= 4 else "groq"
        
        p = PROVIDERS[provider]
        
        print(f"\n📋 {p['name']} models:")
        for i, m in enumerate(p["models"], 1):
            print(f"   {i}. {m}")
        
        model = p["models"][0]
        
        print(f"\n📝 Get key from: {p['url']}")
        api_key = input("API Key: ").strip() or os.environ.get(p["env"], "")
        
        print("\n🧪 Testing...")
        if self._test_key(provider, api_key):
            print("✅ Connected!")
        
        self.config = {
            "user": {"name": self.answers["name"]},
            "use_case": self.answers["use_case"],
            "model": {"provider": provider, "model": model},
            "assistant": {"model": "qwen3.5:cloud"},
            "technician": {"enabled": True},
            "api_key_set": bool(api_key)
        }
    
    def _setup_ollama(self):
        print("\n✓ Using Ollama Cloud (FREE!)")
        
        model = OLLAMA_MODELS[0]
        
        self.config = {
            "user": {"name": self.answers["name"]},
            "use_case": self.answers["use_case"],
            "model": {"provider": "ollama_cloud", "model": model["model"]},
            "assistant": {"model": "qwen3.5:cloud"},
            "technician": {"enabled": True}
        }
    
    def _test_key(self, provider: str, key: str) -> bool:
        if not key:
            return False
        try:
            if provider == "groq":
                r = requests.get("https://api.groq.com/openai/v1/models",
                               headers={"Authorization": f"Bearer {key}"}, timeout=10)
                return r.ok
            elif provider == "openai":
                r = requests.get("https://api.openai.com/v1/models",
                               headers={"Authorization": f"Bearer {key}"}, timeout=10)
                return r.ok
        except:
            pass
        return False
    
    def _save(self):
        os.makedirs("./data", exist_ok=True)
        
        with open("./data/config.json", "w") as f:
            json.dump(self.config, f, indent=2)
        
        print(f"\n{'='*60}")
        print("✅ SETUP COMPLETE!")
        print(f"{'='*60}")
        
        print(f"\n👤 Name: {self.config['user']['name']}")
        print(f"🎯 Use: {self.config['user']['use_case']}")
        print(f"\n🧠 Main: {self.config['model']['provider']} / {self.config['model']['model']}")
        print(f"🤖 Assistant: {self.config['assistant']['model']}")
        
        print(f"\n🚀 Start: python3 neugi.py")
        print(f"📖 Dashboard: http://localhost:19888")
        print(f"{'='*60}\n")

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    wizard = NEUGIWizard()
    wizard.run()
