#!/usr/bin/env python3
"""
🤖 NEUGI WIZARD v2.3 - With Ollama Helper
============================================

Flow:
1. Check Ollama - if NOT running, HELP USER START IT first!
2. Then continue with other steps

Version: 2.3
Date: March 13, 2026
"""

import os
import json
import requests
import subprocess
import sys

# ============================================================
# CHECK & HELP OLLAMA
# ============================================================

def check_ollama() -> bool:
    """Check if Ollama is running"""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.ok
    except:
        return False

def help_start_ollama():
    """Help user start Ollama"""
    print("\n" + "="*60)
    print("🔧 HELP ME START OLLAMA")
    print("="*60)
    
    print("\n📝 Ollama is not running. Let me help you start it!")
    print()
    
    # Try different methods
    print("Trying to start Ollama...")
    
    # Method 1: Try ollama serve
    print("\n[1] Trying: ollama serve")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("   ✅ Started! Waiting for Ollama to initialize...")
        import time
        time.sleep(3)
        
        if check_ollama():
            print("✅ Ollama is now running!")
            return True
    except:
        pass
    
    # Method 2: Check if installed but not running
    print("\n[2] Checking if Ollama is installed...")
    try:
        result = subprocess.run(
            ["which", "ollama"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"   ✅ Ollama installed at: {result.stdout.strip()}")
            print("\n📝 Please run in a NEW terminal:")
            print("   ollama serve")
            print("\n   Then come back here and press Enter!")
            input("\n   Press Enter when Ollama is running...")
            
            if check_ollama():
                print("✅ Ollama is now running!")
                return True
    except:
        pass
    
    # Method 3: Install Ollama
    print("\n[3] Ollama not found!")
    print("\n📝 To install Ollama, run this in your terminal:")
    print()
    print("   # For Linux/Mac:")
    print("   curl -fsSL https://ollama.ai/install | sh")
    print()
    print("   # For Windows:")
    print("   Download from: https://ollama.com/download")
    print()
    
    input("\n   Press Enter after installing Ollama...")
    
    if check_ollama():
        print("✅ Ollama is now running!")
        return True
    
    return False

# ============================================================
# MODEL LISTS
# ============================================================

OLLAMA_CLOUD = [
    {"model": "qwen3.5:cloud", "ctx": 32768, "best_for": "all-round"},
    {"model": "qwen3.5:7b", "ctx": 8192, "best_for": "chat"},
]

PROVIDERS = {
    "openai": {"name": "OpenAI", "env": "OPENAI_API_KEY", 
               "url": "https://platform.openai.com",
               "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]},
    "anthropic": {"name": "Anthropic Claude", "env": "ANTHROPIC_API_KEY",
                  "url": "https://console.anthropic.com",
                  "models": ["claude-sonnet-4", "claude-3.5-sonnet", "claude-3-haiku"]},
    "groq": {"name": "Groq", "env": "GROQ_API_KEY",
             "url": "https://console.groq.com",
             "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "llama-3.1-8b-instant"]},
    "openrouter": {"name": "OpenRouter", "env": "OPENROUTER_API_KEY",
                   "url": "https://openrouter.ai",
                   "models": ["google/gemini-2.0-flash-exp", "meta-llama/llama-3.1-8b-instant"]},
    "minimax": {"name": "MiniMax", "env": "MINIMAX_API_KEY",
                "url": "https://platform.minimax.io",
                "models": ["MiniMax-M2.5"]},
}

# ============================================================
# WIZARD
# ============================================================

class NeugiWizard:
    def __init__(self):
        self.answers = {}
        self.config = {}
        self.ollama_running = False
    
    def run(self):
        print("\n" + "="*60)
        print("🤖 NEUGI WIZARD v2.3")
        print("="*60)
        
        # STEP 1: CHECK OLLAMA - HELP IF NEEDED!
        self._step_check_ollama()
        
        # Continue only if Ollama is running
        if not self.ollama_running:
            print("\n❌ Cannot continue without Ollama.")
            print("Please start Ollama and run the wizard again.")
            return
        
        # STEP 2: Name
        self._step_name()
        
        # STEP 3: Use case
        self._step_use_case()
        
        # STEP 4: API Key
        self._step_api_key()
        
        # STEP 5: Save
        self._save()
    
    def _step_check_ollama(self):
        """Step 1: Check Ollama - help if not running!"""
        print("\n🔍 Step 1: Checking Ollama server...")
        
        self.ollama_running = check_ollama()
        
        if self.ollama_running:
            print("✅ Ollama is running!")
        else:
            print("⚠️ Ollama is NOT running!")
            print("\n🤖 Let me help you start it...")
            
            # Help user start Ollama
            success = help_start_ollama()
            
            if success:
                self.ollama_running = True
                print("\n✅ Great! Ollama is now running!")
            else:
                print("\n❌ Could not start Ollama automatically.")
                print("Please start Ollama manually, then run the wizard again.")
    
    def _step_name(self):
        """Step 2: Name"""
        print("\n" + "-"*60)
        print("👋 Step 2: Your Name")
        print("-"*60)
        name = input("What should I call you? ").strip()
        self.answers["name"] = name or "User"
        print(f"✓ Nice to meet you, {self.answers['name']}!")
    
    def _step_use_case(self):
        """Step 3: Use case"""
        print("\n" + "-"*60)
        print("🎯 Step 3: How will you use Neugi?")
        print("-"*60)
        print("   1. Just chat")
        print("   2. Help with coding")
        print("   3. Research and analysis")
        print("   4. Automation and tasks")
        
        choice = input("\nChoose (1-4): ").strip()
        cases = {"1": "chat", "2": "coding", "3": "research", "4": "automation"}
        self.answers["use_case"] = cases.get(choice, "chat")
        print(f"✓ {self.answers['use_case'].title()}!")
    
    def _step_api_key(self):
        """Step 4: API Key"""
        print("\n" + "-"*60)
        print("🔑 Step 4: API Key")
        print("-"*60)
        
        print("\nDo you have your own AI API key?")
        print("   y - YES, I have an API key")
        print("   n - NO, use free Ollama Cloud")
        
        choice = input("\nAnswer (y/n): ").strip().lower()
        
        if choice == "y":
            self._setup_with_key()
        else:
            self._setup_ollama_cloud()
    
    def _setup_with_key(self):
        """Setup with user's API key"""
        print("\n📋 Available providers:")
        for i, (key, p) in enumerate(PROVIDERS.items(), 1):
            free = " 🆓 FREE" if key in ["groq", "openrouter"] else ""
            print(f"   {i}. {p['name']}{free}")
        
        choice = input("\nChoose provider (1-5): ").strip()
        provider_keys = list(PROVIDERS.keys())
        provider = provider_keys[int(choice)-1] if choice.isdigit() and 1 <= int(choice) <= 5 else "groq"
        
        p = PROVIDERS[provider]
        
        print(f"\n✓ {p['name']}")
        
        print(f"\n📋 Available models:")
        for i, m in enumerate(p["models"], 1):
            print(f"   {i}. {m}")
        
        choice2 = input("\nChoose model (default: 1): ").strip()
        model = p["models"][0] if not choice2 else p["models"][int(choice2)-1]
        
        print(f"\n📝 Enter your {p['name']} API key:")
        print(f"   Get it from: {p['url']}")
        
        api_key = input("\nAPI Key: ").strip()
        
        if not api_key:
            api_key = os.environ.get(p["env"], "")
        
        # Test
        print("\n🧪 Testing connection...")
        if self._test_key(provider, api_key):
            print("✅ Connected!")
        else:
            print("⚠️ Could not verify, but trying anyway...")
        
        self.config = {
            "user": {"name": self.answers["name"]},
            "use_case": self.answers["use_case"],
            "model": {"provider": provider, "model": model},
            "assistant": {"provider": "ollama_cloud", "model": "qwen3.5:cloud"},
            "technician": {"enabled": True},
            "privacy": "cloud",
            "api_key_set": bool(api_key)
        }
    
    def _setup_ollama_cloud(self):
        """Setup with Ollama Cloud"""
        print("\n✓ Using Ollama Cloud (FREE!)")
        
        model = OLLAMA_CLOUD[0]
        
        print(f"\n📋 Model: {model['model']}")
        print(f"   Context: {model['ctx']:,} tokens")
        print(f"   Best for: {model['best_for']}")
        
        self.config = {
            "user": {"name": self.answers["name"]},
            "use_case": self.answers["use_case"],
            "model": {"provider": "ollama_cloud", "model": model["model"], "ctx": model["ctx"]},
            "assistant": {"provider": "ollama_cloud", "model": "qwen3.5:cloud"},
            "technician": {"enabled": True},
            "privacy": "cloud"
        }
    
    def _test_key(self, provider: str, key: str) -> bool:
        """Test API key"""
        if not key:
            return False
        
        try:
            if provider == "groq":
                r = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"}, timeout=10
                )
                return r.ok
            elif provider == "openai":
                r = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"}, timeout=10
                )
                return r.ok
            elif provider == "openrouter":
                r = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {key}"}, timeout=10
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
        print(f"\n🧠 Main: {self.config['model']['provider']} / {self.config['model']['model']}")
        print(f"🤖 Assistant: {self.config['assistant']['model']}")
        
        print("\n🚀 Start: python3 neugi.py")
        print("📖 Dashboard: http://localhost:19888")
        print("="*60 + "\n")

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    wizard = NeugiWizard()
    wizard.run()
