#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - LLM POWERED WIZARD
======================================

Zero-setup installation wizard:
1. One command install
2. Chat with wizard (LLM-powered)
3. Auto-configure everything
4. Start chatting immediately!

Version: 1.0
Date: March 13, 2026
"""

import os
import sys
import json
import requests

# ============================================================
# BUNDLED FREE CONFIG
# ============================================================

# Ollama Cloud Free API (bundled for instant use!)
# Users can replace this later
BUNDLED_API_KEY = os.environ.get("OLLAMA_API_KEY", "")
BUNDLED_PROVIDER = "ollama"
BUNDLED_MODEL = "qwen2.5:7b"  # Stable, won't deprecate soon!

# Fallback to Groq if no key
FALLBACK_PROVIDER = "groq"
FALLBACK_MODEL = "llama-3.1-8b-instant"

# ============================================================
# WIZARD QUESTIONS
# ============================================================

WIZARD_STEPS = [
    {
        "id": "greeting",
        "prompt": "Hi! I'm Neugi 🤖 I'll help you set up in 30 seconds.\n\nWhat should I call you?",
        "key": "name",
        "type": "text"
    },
    {
        "id": "use_case",
        "prompt": None,  # Dynamic based on name
        "key": "use_case",
        "type": "choice",
        "options": [
            ("1", "Just chat with AI"),
            ("2", "Help with coding"),
            ("3", "Automate tasks"),
            ("4", "Research assistant"),
        ]
    },
    {
        "id": "api_key",
        "prompt": None,  # Dynamic
        "key": "has_api_key",
        "type": "yesno"
    },
    {
        "id": "privacy",
        "prompt": "Privacy preference:\n1. Local only (slower, private)\n2. Cloud (faster, uses internet)",
        "key": "privacy",
        "type": "choice",
        "options": [
            ("1", "Local (private)"),
            ("2", "Cloud (fast)"),
        ]
    },
]

# ============================================================
# LLM FOR WIZARD
# ============================================================

class WizardLLM:
    """Lightweight LLM for wizard conversations"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or BUNDLED_API_KEY
    
    def chat(self, messages: list) -> str:
        """Simple chat for wizard"""
        
        # Build prompt
        system = """You are Neugi Setup Wizard. Your job is to:
- Be friendly and simple
- Keep responses under 2 sentences
- Guide user through setup step by step
- Be encouraging and supportive

No technical jargon. Speak like a helpful friend."""
        
        # Try Ollama first (local)
        try:
            return self._ollama_chat(system, messages)
        except:
            pass
        
        # Fallback to simple responses
        return "Great! Let's continue setup..."
    
    def _ollama_chat(self, system: str, messages: list) -> str:
        """Chat via Ollama"""
        url = "http://localhost:11434/api/chat"
        
        data = {
            "model": "llama2",
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False
        }
        
        r = requests.post(url, json=data, timeout=10)
        
        if r.ok:
            return r.json()["message"]["content"]
        
        raise Exception("Ollama not available")

# ============================================================
# HARDWARE DETECTION
# ============================================================

def detect_hardware() -> dict:
    """Auto-detect user hardware"""
    
    import psutil
    
    try:
        ram_gb = psutil.virtual_memory().total / (1024**3)
    except:
        ram_gb = 2  # Default assumption
    
    # Detect OS
    import platform
    os_name = platform.system().lower()
    
    # Detect Python
    python_ver = sys.version_info
    
    return {
        "ram_gb": round(ram_gb, 1),
        "os": os_name,
        "python": f"{python_ver.major}.{python_ver.minor}",
        "recommended_model": _recommend_model(ram_gb),
    }

def _recommend_model(ram_gb: float) -> str:
    """Recommend model based on RAM"""
    
    if ram_gb < 1:
        return "qwen2.5:0.5b"  # Tiny
    elif ram_gb < 2:
        return "qwen2.5:1.5b"  # Small
    elif ram_gb < 4:
        return "qwen2.5:3b"  # Medium
    elif ram_gb < 8:
        return "qwen2.5:7b"  # Default
    elif ram_gb < 16:
        return "qwen2.5:14b"  # Large
    else:
        return "qwen2.5:32b"  # XL

# ============================================================
# AUTO CONFIGURATION
# ============================================================

def auto_configure(answers: dict, hardware: dict) -> dict:
    """Auto-generate configuration based on answers"""
    
    config = {
        "user": {
            "name": answers.get("name", "User"),
            "use_case": answers.get("use_case", "chat"),
        },
        "model": {
            "provider": BUNDLED_PROVIDER,
            "model": BUNDLED_MODEL,
            "fallback": FALLBACK_PROVIDER,
        },
        "privacy": answers.get("privacy", "cloud"),
        "channels": [],
        "features": _detect_features(answers),
    }
    
    # Use hardware recommendation if local
    if answers.get("privacy") == "local":
        config["model"]["provider"] = "ollama"
        config["model"]["model"] = hardware["recommended_model"]
    
    return config

def _detect_features(answers: dict) -> dict:
    """Detect which features to enable"""
    
    use_case = answers.get("use_case", "chat")
    
    features = {
        "chat": True,
        "code": False,
        "automation": False,
        "research": False,
    }
    
    if use_case in ["2", "coding"]:
        features["code"] = True
    elif use_case in ["3", "automation"]:
        features["automation"] = True
    elif use_case in ["4", "research"]:
        features["research"] = True
    
    return features

# ============================================================
# WIZARD ENGINE
# ============================================================

class NeugiWizard:
    """LLM-powered setup wizard"""
    
    def __init__(self):
        self.step = 0
        self.answers = {}
        self.hardware = detect_hardware()
        self.llm = WizardLLM()
        
        # Welcome message
        print("\n" + "="*50)
        print("🤖 NEUGI SWARM - ZERO-SETUP WIZARD")
        print("="*50)
        print()
        print("Hi! I'm Neugi 🤖")
        print("I'll help you set up in just a few questions.")
        print()
    
    def run(self):
        """Run the wizard"""
        
        # Step 1: Name
        self._ask_name()
        
        # Step 2: Use case
        self._ask_use_case()
        
        # Step 3: API key
        self._ask_api_key()
        
        # Step 4: Privacy
        self._ask_privacy()
        
        # Finish!
        return self._finish()
    
    def _ask_name(self):
        """Ask user's name"""
        print("What should I call you? ", end="")
        name = input().strip()
        
        if not name:
            name = "User"
        
        self.answers["name"] = name
        print(f"Hi {name}! 🎉")
        print()
    
    def _ask_use_case(self):
        """Ask what user wants to do"""
        
        print("How will you use me?")
        print("  1. Just chat with AI")
        print("  2. Help with coding")
        print("  3. Automate tasks")
        print("  4. Research assistant")
        print()
        print("Choose (1-4): ", end="")
        
        choice = input().strip()
        
        use_cases = {
            "1": "chat",
            "2": "coding",
            "3": "automation",
            "4": "research"
        }
        
        self.answers["use_case"] = use_cases.get(choice, "chat")
        print()
    
    def _ask_api_key(self):
        """Ask if user has API key"""
        
        print("Do you have your own AI API key?")
        print("(This gives you better performance)")
        print()
        print("  y - Yes, I have an API key")
        print("  n - No, use free model")
        print()
        print("Choice (y/n): ", end="")
        
        choice = input().strip().lower()
        
        if choice == "y":
            print()
            print("Great! After setup, say 'add api key' and I'll help you add it.")
            print()
        
        self.answers["has_api_key"] = (choice == "y")
    
    def _ask_privacy(self):
        """Ask privacy preference"""
        
        print("Privacy preference:")
        print(f"  1. Cloud (faster, uses internet)")
        print(f"  2. Local (slower, more private)")
        print()
        
        # Show hardware detection
        print(f"📊 We detected: {self.hardware['ram_gb']}GB RAM")
        
        if self.hardware['ram_gb'] < 4:
            print("⚠️  Not enough RAM for local models. Using cloud.")
            self.answers["privacy"] = "cloud"
            return
        
        print()
        print("Choice (1-2): ", end="")
        
        choice = input().strip()
        
        if choice == "2":
            self.answers["privacy"] = "local"
        else:
            self.answers["privacy"] = "cloud"
        
        print()
    
    def _finish(self) -> dict:
        """Finish setup and generate config"""
        
        print("🎉 Setting up Neugi for you...")
        print()
        
        # Generate config
        config = auto_configure(self.answers, self.hardware)
        
        # Save config
        os.makedirs("./data", exist_ok=True)
        with open("./data/config.json", "w") as f:
            json.dump(config, f, indent=2)
        
        # Show summary
        print("✅ Setup Complete!")
        print("="*50)
        print()
        print(f"👤 Name: {config['user']['name']}")
        print(f"🎯 Use case: {config['user']['use_case']}")
        print(f"🧠 Model: {config['model']['provider']}/{config['model']['model']}")
        print(f"🔒 Privacy: {config['privacy']}")
        print()
        print("="*50)
        print()
        print("🚀 Start chatting: python3 neugi.py")
        print("📖 Dashboard: http://localhost:19888")
        print()
        print("Tips:")
        print('  - Say "help" for commands')
        print('  - Say "add api key" to upgrade later')
        print('  - Say "status" to check system')
        print()
        
        return config

# ============================================================
# QUICK START SCRIPT
# ============================================================

def quick_start():
    """One-command quick start"""
    
    print("""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║   🤖 NEUGI SWARM - INSTALL IN 30 SECONDS          ║
║                                                      ║
║   Just run: curl -sSL neugi.ai/install | bash      ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
""")
    
    # Check if already installed
    if os.path.exists("./data/config.json"):
        print("Neugi is already installed!")
        print("Run: python3 neugi.py")
        return
    
    # Run wizard
    wizard = NeugiWizard()
    wizard.run()

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Neugi Swarm Wizard")
    parser.add_argument("--wizard", action="store_true", help="Run setup wizard")
    parser.add_argument("--quick", action="store_true", help="Quick start")
    
    args = parser.parse_args()
    
    if args.wizard or args.quick:
        quick_start()
    else:
        # Just show help
        print("Neugi Swarm - Zero-setup AI Assistant")
        print()
        print("Quick start:")
        print("  python3 neugi_wizard.py --quick")
        print()
        print("Or run wizard:")
        print("  python3 neugi_wizard.py --wizard")
