#!/usr/bin/env python3
"""
🤖 NEUGI ASSISTANT
===================
Smart assistant using qwen2.5:1.5b (Ollama Cloud)
Helps users with installation, setup, and general questions

Version: 1.0
Date: March 13, 2026
"""

import os
import json
import requests
import urllib.request
import urllib.error

# Config
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
ASSISTANT_MODEL = "qwen2.5:1.5b"


class NeugiAssistant:
    """Smart assistant - always ready to help!"""

    def __init__(self):
        self.model = ASSISTANT_MODEL
        self.url = OLLAMA_URL
        self.system_prompt = """You are NEUGI Assistant - a helpful AI assistant for NEUGI Swarm.

You help users with:
- Installation problems
- Setup questions
- How to use NEUGI
- Troubleshooting
- General questions

Be friendly, concise, and helpful. Always try to solve the user's problem.
If you don't know something, say so and suggest where to find help.

NEUGI is Neural General Intelligence - made easy!
"""

    def is_ollama_running(self) -> bool:
        """Check if Ollama is running"""
        try:
            r = requests.get(f"{self.url}/api/tags", timeout=3)
            return r.ok
        except:
            return False

    def chat(self, message: str) -> str:
        """Send message and get response"""

        # Check if Ollama is running
        if not self.is_ollama_running():
            return self._offline_response(message)

        try:
            # Try Ollama Cloud model
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": message},
                ],
                "stream": False,
            }

            req = urllib.request.Request(
                f"{self.url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                return data.get("message", {}).get("content", "No response")

        except Exception as e:
            # Try fallback model
            return self._fallback_chat(message)

    def _fallback_chat(self, message: str) -> str:
        """Try fallback models if qwen2.5:1.5b fails"""

        fallback_models = ["qwen2.5:7b", "llama3.2:3b", "mistral:7b"]

        for model in fallback_models:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": message}],
                    "stream": False,
                }

                req = urllib.request.Request(
                    f"{self.url}/api/chat",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )

                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode())
                    return data.get("message", {}).get("content", "No response")

            except:
                continue

        return self._offline_response(message)

    def _offline_response(self, message: str) -> str:
        """Respond when Ollama is not available"""

        message_lower = message.lower()

        # Common questions
        if "install" in message_lower or "setup" in message_lower:
            return """📥 **Installation Help**

To install NEUGI, run:

```bash
curl -fsSL https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/install.sh | bash
```

This will:
1. Install Ollama
2. Start Ollama server
3. Download AI models
4. Install NEUGI
5. Run setup wizard
6. Start NEUGI

After install, use:
- `neugi start` - Start NEUGI
- `neugi status` - Check status
- `neugi stop` - Stop NEUGI"""

        elif "start" in message_lower:
            return """🚀 **Starting NEUGI**

```bash
# Using CLI (recommended)
neugi start

# Or manually
cd ~/neugi
python3 neugi_swarm.py
```

Dashboard: http://localhost:19888"""

        elif "status" in message_lower:
            return """📊 **Check Status**

```bash
neugi status
```

This shows:
- If NEUGI is running
- Active model
- Number of sessions
- Uptime"""

        elif "stop" in message_lower:
            return """🛑 **Stop NEUGI**

```bash
neugi stop
```

Or manually:
```bash
pkill -f neugi_swarm.py
```"""

        elif "ollama" in message_lower:
            return """🔧 **Ollama Help**

Ollama is required for NEUGI to work.

Start Ollama:
```bash
ollama serve
```

Check if running:
```bash
curl http://localhost:11434/api/tags
```

Download models:
```bash
ollama pull qwen2.5:1.5b
```"""

        elif "api" in message_lower or "key" in message_lower:
            return """🔑 **API Keys**

NEUGI supports:
- **Free**: Ollama Cloud (qwen2.5:1.5b)
- **Groq**: https://console.groq.com (FREE!)
- **OpenRouter**: https://openrouter.ai (Free tier)
- **OpenAI**: https://platform.openai.com
- **Anthropic**: https://console.anthropic.com

Add your API key in config.py or use the wizard!"""

        else:
            return f"""👋 Hi! I'm NEUGI Assistant.

I'm here to help! Try asking about:

- **Installation**: How to install NEUGI
- **Starting**: How to start NEUGI
- **Status**: Check if NEUGI is running
- **Ollama**: Problems with Ollama
- **API Keys**: Adding your own API key

Your question: "{message}"

Make sure Ollama is running: `ollama serve`"""

    def help_user(self, question: str) -> str:
        """Main help function"""
        return self.chat(question)


# ============================================================
# CLI
# ============================================================


def main():
    import sys

    assistant = NeugiAssistant()

    if len(sys.argv) > 1:
        # Command line mode
        question = " ".join(sys.argv[1:])
        response = assistant.help_user(question)
        print(response)
    else:
        # Interactive mode
        print("🤖 NEUGI Assistant")
        print("Type 'quit' to exit\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() in ["quit", "exit", "q"]:
                    print("👋 Goodbye!")
                    break

                if not user_input:
                    continue

                response = assistant.help_user(user_input)
                print(f"\nNEUGI: {response}\n")

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break


if __name__ == "__main__":
    main()
