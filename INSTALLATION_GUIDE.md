# 🤖 NEUGI SWARM
## Complete Installation Guide

**Version:** 14.1  
**Date:** March 13, 2026

---

![Neugi Swarm](https://img.shields.io/badge/Neugi-Swarm-blue) ![Python 3.8+](https://img.shields.io/badge/Python-3.8+-green) ![Free](https://img.shields.io/badge/Price-Free-brightgreen)

---

# 📋 Table of Contents

1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Quick Installation](#quick-installation)
4. [Step-by-Step Setup](#step-by-step-setup)
5. [First Run](#first-run)
6. [Dashboard Guide](#dashboard-guide)
7. [Configuration](#configuration)
8. [Troubleshooting](#troubleshooting)
9. [FAQ](#faq)

---

# 1. Introduction

## What is Neugi Swarm?

Neugi Swarm is a **production-ready autonomous AI system** that works with:

- ✅ **Free providers** (Groq, OpenRouter, Ollama)
- ✅ **Local models** (llama.cpp, Ollama)
- ✅ **Premium providers** (OpenAI, Anthropic, MiniMax)
- ✅ **Flexible context** (2K to 1M+ tokens!)
- ✅ **Low hardware requirements** (2GB RAM minimum!)

## Why Neugi Swarm?

| Feature | Neugi Swarm | OpenClaw |
|---------|-------------|----------|
| Minimum Context | **2K tokens** | 16K+ |
| Free Providers | ✅ Multiple | Limited |
| Setup Complexity | **Simple** | Complex |
| Hardware Needs | **2GB RAM** | Higher |
| Dashboard | ✅ Built-in | Separate |

---

# 2. Prerequisites

## Minimum Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.8+ | 3.10+ |
| RAM | 2 GB | 4 GB |
| Storage | 500 MB | 1 GB |
| Internet | Required | Required |

## Operating Systems

- ✅ Linux (Ubuntu, Debian, CentOS, etc.)
- ✅ macOS
- ✅ Windows (via WSL2)

---

# 3. Quick Installation

## One-Line Install (Recommended)

Open your terminal and run:

```bash
curl -sSL https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/install.sh | bash
```

This will:
1. Check Python installation
2. Create `~/neugi` directory
3. Download Neugi Swarm
4. Create configuration file
5. Show next steps

## Manual Installation

```bash
# Clone repository
git clone https://github.com/atharia-agi/neugi_swarm.git
cd neugi_swarm

# Run setup
python3 neugi_swarm.py --setup

# Start
python3 neugi_swarm.py
```

---

# 4. Step-by-Step Setup

## Step 1: Get API Key (Choose One)

### Option A: Groq (RECOMMENDED - FREE & FAST!)

1. Visit: https://console.groq.com
2. Sign up (free)
3. Go to API Keys
4. Copy your API key

### Option B: OpenRouter (FREE Tier)

1. Visit: https://openrouter.ai
2. Sign up (free credits)
3. Get API key from settings

### Option C: Ollama (LOCAL - FREE Forever!)

1. Visit: https://ollama.ai
2. Download and install
3. Run: `ollama pull llama2`

### Option D: llama.cpp (Lightest - 2GB RAM!)

1. Download from: https://github.com/ggerganov/llama.cpp
2. Get model from: https://huggingface.co/TheBloke

## Step 2: Run Setup Wizard

```bash
cd ~/neugi
python3 neugi_swarm.py --setup
```

You'll see:

```
============================================================
🤖 NEUGI SWARM SETUP WIZARD
============================================================

Welcome to Neugi Swarm!

This wizard will help you set up Neugi in minutes.
Minimum requirements: Python 3.8, 2GB RAM

Works with: 2K context models and above!

Press ENTER to continue...
```

### Setup Wizard Steps:

1. **Choose Provider** - Select Groq/OpenRouter/Ollama/etc
2. **Enter API Key** - Paste your key
3. **Select Model** - Choose recommended model
4. **Configure Context** - Default: 8K (works with 2K!)
5. **Setup Channels** - Telegram/Discord/WhatsApp (optional)
6. **Set Security** - Master password

## Step 3: Start Neugi

```bash
python3 neugi_swarm.py
```

---

# 5. First Run

## Starting Neugi

```bash
$ python3 neugi_swarm.py

🤖 Starting Neugi Swarm...

============================================================
🤖 Neugi Swarm v14.1
   Production-Ready Autonomous AI
============================================================

🧠 LLM: groq
📝 Context: 8192 (minimum: 8192)

🌐 Dashboard: http://localhost:19888
📡 API: http://localhost:19888/api/chat

Press Ctrl+C to stop
```

## Access Dashboard

Open your browser:

```
http://localhost:19888
```

You'll see the dashboard with:
- LLM Status (provider, model, context)
- System info (version, uptime)
- Quick Actions
- Chat interface

---

# 6. Dashboard Guide

## Main Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  🤖 Neugi Swarm                                            │
│  Production-Ready Autonomous AI | v14.1                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 🧠 LLM Status │  │ 📊 System   │  │ 🛠️ Actions  │      │
│  │              │  │              │  │              │      │
│  │ Provider:    │  │ Version:     │  │ Test LLM    │      │
│  │ Groq         │  │ 14.1         │  │ Status      │      │
│  │              │  │              │  │ Health      │      │
│  │ Model:       │  │ Status:      │  │             │      │
│  │ llama-3.1-8b │  │ ● Active    │  │             │      │
│  │              │  │              │  │             │      │
│  │ Context:     │  │ Uptime:      │  │ API:       │      │
│  │ 8,000       │  │ 0h 5m 32s   │  │ /api/chat  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
├─────────────────────────────────────────────────────────────┤
│  💬 Quick Chat                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Type your message here...                          │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Response will appear here...                        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## API Usage

### Chat API

```bash
curl -X POST http://localhost:19888/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

Response:
```json
{
  "response": "Hello! I'm Neugi Swarm, a production-ready autonomous AI..."
}
```

### Other Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard |
| `/api/status` | GET | System status |
| `/api/health` | GET | Health check |
| `/api/test` | GET | Test LLM |
| `/api/chat` | POST | Chat with AI |

---

# 7. Configuration

## Configuration File

After setup, edit `config.py`:

```python
# Provider
PROVIDER = "groq"
MODEL = "llama-3.1-8b-instant"
API_KEY = "gsk_..."

# Context (minimum 2K works!)
CONTEXT_WINDOW = 8192

# Channels (optional)
CHANNELS = {
    "telegram": {"bot_token": "...", "chat_id": "..."},
    "discord": {"webhook": "..."},
}

# Security
SECURITY = {
    "master_key": "change_this",
    "rate_limit": True,
}
```

## Environment Variables

```bash
# Instead of editing config.py
export GROQ_API_KEY="gsk_..."
export OPENROUTER_API_KEY="sk-or-..."
export OLLAMA_URL="http://localhost:11434"
```

---

# 8. Troubleshooting

## Common Issues

### "Python not found"

```bash
# Ubuntu/Debian
sudo apt install python3

# macOS
brew install python3
```

### "Port already in use"

```bash
# Use different port
python3 neugi_swarm.py --port 19889
```

### "API key invalid"

1. Check your API key at provider dashboard
2. Ensure no extra spaces when pasting
3. For Groq: https://console.groq.com/keys
4. For OpenRouter: https://openrouter.ai/settings

### "Model not found"

Some models may not be available. Try:
- Groq: `llama-3.1-8b-instant`
- OpenRouter: `google/gemini-2.0-flash-exp`

### "Connection timeout"

Check internet connection. For Ollama/llama.cpp, ensure local server is running.

---

# 9. FAQ

## Q: Is Neugi really free?

**A:** Yes! Groq and OpenRouter have free tiers. Ollama and llama.cpp are completely free and run locally.

## Q: Does it work with small RAM?

**A:** Yes! 2GB RAM minimum. llama.cpp with quantized models works great on 2GB!

## Q: What's the minimum context?

**A:** 2,000 tokens! Much lower than OpenClaw's 16K requirement.

## Q: Can I use my own model?

**A:** Yes! Supports Ollama, llama.cpp, and any API provider.

## Q: How do I update?

```bash
cd ~/neugi
git pull origin main
```

---

# 🎉 You're Ready!

```bash
# Quick start
python3 neugi_swarm.py

# Dashboard
# http://localhost:19888
```

**Need help?** https://github.com/atharia-agi/neugi_swarm

---

**Neugi Swarm** - Production-Ready Autonomous AI  
*Built by Auroria for the future of AI*

---
