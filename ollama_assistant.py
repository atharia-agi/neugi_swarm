#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - OLLAMA CLOUD ASSISTANT
===========================================

Built-in smart assistant:
- Uses Ollama Cloud API
- Helps with installation/setup
- Available in CLI and Dashboard
- Separate from main Swarm agent

Version: 1.0
Date: March 13, 2026
"""

import os
import json
import requests
from typing import Dict, List, Optional

# ============================================================
# OLLAMA CLOUD CONFIG
# ============================================================

OLLAMA_CLOUD = {
    "api_base": "https://cloud.ollama.ai/api",
    # Note: Ollama Cloud uses existing Ollama API
    # Users need to sign up at ollama.com/cloud
    
    "cloud_model": "qwen3.5:cloud",  # The cloud model!
    
    "free_models": [
        "qwen3.5:cloud",     # ⭐ RECOMMENDED - Cloud version!
        "qwen3.5:7b",
        "qwen3.5:3b", 
        "llama3.2:3b",
        "mistral:7b",
        "llama3.1:8b",
    ],
    
    # Best for assistant (balance of speed + quality)
    "recommended": "qwen3.5:cloud",
}

# Fallback free providers
FALLBACK_PROVIDERS = {
    "groq": {
        "api_base": "https://api.groq.com/openai/v1",
        "models": ["llama-3.1-8b-instant"],
        "free": True,
    },
    "openrouter": {
        "api_base": "https://openrouter.ai/api/v1", 
        "models": ["meta-llama/llama-3.1-8b-instant"],
        "free_tier": True,
    }
}

# ============================================================
# OLLAMA CLOUD ASSISTANT
# ============================================================

class OllamaAssistant:
    """
    Built-in smart assistant using Ollama Cloud
    Separate from main Swarm agent
    """
    
    # System prompt for installation assistant
    SYSTEM_PROMPT = """You are Neugi's Installation Assistant. Your job is to help users:

1. INSTALL NEUGI
   - Guide through one-command installation
   - Explain each step simply
   
2. SETUP
   - Help configure API keys
   - Choose the right model
   - Set up channels (Telegram, Discord, etc)
   
3. TROUBLESHOOT
   - Explain errors simply
   - Suggest solutions
   - Point to documentation

Rules:
- Be friendly and patient
- Use simple language (no jargon)
- Ask one question at a time
- Keep responses short (2-3 sentences max)
- If stuck, suggest getting help

You have access to installation docs and can guide users step by step."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("OLLAMA_API_KEY", "")
        self.provider = self._detect_provider()
        self.model = OLLAMA_CLOUD["recommended"]
        
        # Conversation history
        self.history = []
    
    def _detect_provider(self) -> str:
        """Detect best available provider"""
        
        # Check for Ollama Cloud / Pro
        if self.api_key:
            return "ollama_cloud"
        
        # Check for Groq (free, fast)
        if os.environ.get("GROQ_API_KEY"):
            return "groq"
        
        # Check for OpenRouter (free tier)
        if os.environ.get("OPENROUTER_API_KEY"):
            return "openrouter"
        
        # Check local Ollama
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            if r.ok:
                return "ollama_local"
        except:
            pass
        
        return "simulation"
    
    def chat(self, message: str) -> str:
        """Chat with assistant"""
        
        # Add to history
        self.history.append({"role": "user", "content": message})
        
        # Build messages
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        messages.extend(self.history[-5:])  # Last 5 messages
        
        # Get response
        response = self._call_llm(messages)
        
        # Add response to history
        self.history.append({"role": "assistant", "content": response})
        
        return response
    
    def _call_llm(self, messages: list) -> str:
        """Call LLM based on provider"""
        
        if self.provider == "ollama_cloud":
            return self._call_ollama_cloud(messages)
        elif self.provider == "groq":
            return self._call_groq(messages)
        elif self.provider == "openrouter":
            return self._call_openrouter(messages)
        elif self.provider == "ollama_local":
            return self._call_ollama_local(messages)
        else:
            return self._fallback_response(messages)
    
    def _call_ollama_cloud(self, messages: list) -> str:
        """Call Ollama Cloud API"""
        
        url = f"{OLLAMA_CLOUD['api_base']}/chat"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        
        try:
            r = requests.post(url, json=data, headers=headers, timeout=30)
            
            if r.ok:
                return r.json()["message"]["content"]
            else:
                # Fallback
                return self._fallback_response(messages)
        
        except Exception as e:
            return self._fallback_response(messages)
    
    def _call_groq(self, messages: list) -> str:
        """Call Groq (free, fast)"""
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        
        # Convert messages format
        sys_msg = messages[0]["content"] if messages[0]["role"] == "system" else ""
        user_msgs = [{"role": m["role"], "content": m["content"]} for m in messages[1:]]
        
        headers = {
            "Authorization": f"Bearer {os.environ.get('GROQ_API_KEY', '')}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "system", "content": sys_msg}] + user_msgs,
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        try:
            r = requests.post(url, json=data, headers=headers, timeout=20)
            
            if r.ok:
                return r.json()["choices"][0]["message"]["content"]
        except:
            pass
        
        return self._fallback_response(messages)
    
    def _call_openrouter(self, messages: list) -> str:
        """Call OpenRouter (free tier)"""
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://neugi.ai"
        }
        
        data = {
            "model": "meta-llama/llama-3.1-8b-instant",
            "messages": messages,
            "max_tokens": 500
        }
        
        try:
            r = requests.post(url, json=data, headers=headers, timeout=20)
            
            if r.ok:
                return r.json()["choices"][0]["message"]["content"]
        except:
            pass
        
        return self._fallback_response(messages)
    
    def _call_ollama_local(self, messages: list) -> str:
        """Call local Ollama"""
        
        url = "http://localhost:11434/api/chat"
        
        # Convert messages
        msgs = []
        for m in messages:
            if m["role"] == "system":
                msgs.append({"role": "system", "content": m["content"]})
            else:
                msgs.append({"role": m["role"], "content": m["content"]})
        
        data = {
            "model": "llama2",
            "messages": msgs,
            "stream": False
        }
        
        try:
            r = requests.post(url, json=data, timeout=60)
            
            if r.ok:
                return r.json()["message"]["content"]
        except:
            pass
        
        return self._fallback_response(messages)
    
    def _fallback_response(self, messages: list) -> str:
        """Fallback when no LLM available"""
        
        user_msg = messages[-1]["content"].lower() if messages else ""
        
        # Simple rule-based responses
        if "install" in user_msg:
            return """To install Neugi, run:

curl -sSL https://neugi.ai/install | bash

This will download and set everything up automatically!"""
        
        elif "setup" in user_msg or "configure" in user_msg:
            return """After installation, run:

python3 neugi_wizard.py --wizard

This will guide you through setup step by step!"""
        
        elif "api key" in user_msg:
            return """You can get free API keys from:

- Groq: https://console.groq.com (fast!)
- OpenRouter: https://openrouter.ai (has free tier)

Or use local models with Ollama!"""
        
        elif "help" in user_msg:
            return """I'm here to help! Ask me about:

- Installing Neugi
- Setting up API keys  
- Configuring channels
- Troubleshooting errors
- Using different models

What would you like to know?"""
        
        else:
            return """Hi! I'm your installation assistant.

Try asking me:
- "How to install Neugi?"
- "How to set up API key?"
- "What's the best model for my computer?"

Or just say "help" for more options!"""
    
    def clear_history(self):
        """Clear conversation history"""
        self.history = []
    
    def get_status(self) -> Dict:
        """Get assistant status"""
        return {
            "provider": self.provider,
            "model": self.model,
            "history_length": len(self.history),
            "available": self.provider != "simulation"
        }

# ============================================================
# INTEGRATION WITH MAIN NEUGI
# ============================================================

class NeugiWithAssistant:
    """
    Neugi Swarm + Built-in Assistant
    Two separate agents:
    - Main Swarm Agent (for tasks)
    - Installation Assistant (for help)
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Main Swarm (for tasks)
        # self.swarm = NeugiSwarm(config)
        
        # Installation Assistant (separate!)
        self.assistant = OllamaAssistant(
            api_key=config.get("assistant_api_key") if config else None
        )
        
        print("\n🤖 Neugi Swarm + Installation Assistant")
        print("="*50)
        print()
        print("Agents:")
        print("  1. Swarm Agent - For your tasks")
        print("  2. Installation Assistant - For help")
        print()
    
    def chat_with_assistant(self, message: str) -> str:
        """Chat with installation assistant"""
        return self.assistant.chat(message)
    
    def chat_with_swarm(self, message: str) -> str:
        """Chat with main Swarm agent"""
        # Would call main swarm
        return "[Swarm Agent] Processing your request..."
    
    def route(self, message: str) -> str:
        """Route to appropriate agent"""
        
        # Keywords that trigger assistant
        assistant_keywords = [
            "install", "setup", "configure", "how to",
            "help me", "error", "problem", "trouble",
            "api key", "can't", "won't", "stuck",
            "?", "guide", "tutorial"
        ]
        
        message_lower = message.lower()
        
        # Check if should use assistant
        for keyword in assistant_keywords:
            if keyword in message_lower:
                return self.chat_with_assistant(message)
        
        # Default to main swarm
        return self.chat_with_swarm(message)
    
    def assistant_status(self) -> Dict:
        """Get assistant status"""
        return self.assistant.get_status()

# ============================================================
# CLI MODE
# ============================================================

def run_cli():
    """Run assistant in CLI mode"""
    
    print("\n" + "="*50)
    print("🤖 NEUGI INSTALLATION ASSISTANT")
    print("="*50)
    print()
    print("I'm here to help you install and setup Neugi!")
    print("Type 'quit' to exit.")
    print()
    
    # Create assistant
    assistant = OllamaAssistant()
    
    print(f"Status: {assistant.provider}")
    print()
    
    # Welcome message
    welcome = assistant.chat("Hello!")
    print(f"Assistant: {welcome}")
    print()
    
    # Main loop
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["quit", "exit", "bye"]:
                print("\n👋 Goodbye! Good luck with Neugi!")
                break
            
            # Get response
            response = assistant.chat(user_input)
            print(f"\nAssistant: {response}\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Neugi Installation Assistant")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    parser.add_argument("--status", action="store_true", help="Show assistant status")
    
    args = parser.parse_args()
    
    if args.cli:
        run_cli()
    elif args.status:
        assistant = OllamaAssistant()
        print(json.dumps(assistant.get_status(), indent=2))
    else:
        print("Neugi Installation Assistant")
        print()
        print("Usage:")
        print("  python3 ollama_assistant.py --cli     # Chat in CLI")
        print("  python3 ollama_assistant.py --status   # Check status")
