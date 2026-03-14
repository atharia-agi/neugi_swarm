# 🤖 NEUGI SWARM
## Neural General Intelligence - Made Easy

---

<p align="center">
  <img src="https://img.shields.io/badge/NEUGI-NGI-blue" alt="NEUGI">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Python-3.8+-yellow" alt="Python">
  <a href="https://neugi.com"><img src="https://img.shields.io/badge/Website-Live-green" alt="Website"></a>
</p>

---

## 🚀 Quick Start

### One-Command Installation

```bash
curl -fsSL https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/install.sh | bash
```

**Done!** NEUGI will:
1. Install Ollama (latest)
2. Start Ollama Server
3. Download AI Model
4. Install NEUGI Files
5. Install NEUGI CLI
6. **Run Setup Wizard** ← Your input here!
7. Start NEUGI + Activity Log

---

## 🌐 Website & Dashboard

### Official Website
Visit our landing page: **[neugi.com](https://neugi.com)**

### Dashboard
After install, access:
```
http://localhost:19888
```

---

## 📖 Documentation

Full documentation available at: **[docs.html](https://neugi.com/docs.html)**

Includes:
- Installation Guide
- Configuration
- API Reference
- Security Settings
- Plugin System
- Troubleshooting

---

## 🔧 Features

| Feature | Description |
|---------|-------------|
| **True NGI** | Neural General Intelligence with Knowledge Graph, Reasoning, Planning |
| **Native Web Browser** | FREE web search - DuckDuckGo, SearXNG, Brave (no API keys!) |
| **Auto-Install** | One command installs everything including Ollama |
| **Smart Wizard v3.0** | All-in-one: setup, repair, diagnose, chat, plugins, update |
| **Technician** | Can fix system issues automatically |
| **Free Models** | qwen3.5:cloud works with Ollama Free tier |
| **Multi-Provider** | Support Groq, OpenRouter, OpenAI, Anthropic |
| **CLI** | Like `openclaw` - neugi start/stop/status |
| **Telegram Control** | Manage your swarm from your phone via Telegram Bot |
| **Streaming Responses** | Real-time AI responses |
| **Memory System** | Conversation history & user preferences |
| **Plugin System** | Extend with Native, MCP, or marketplace plugins |
| **Skills System** | Compatible with OpenClaw, Claude Code, MCP |
| **Workspace** | Isolated workspace for agents |
| **Auto-Updater** | Stay up to date |
| **Security Layer** | Sandbox & full access modes |

---

## 📁 Directory Structure

```
~/neugi/
├── neugi                 # Main CLI
├── neugi_swarm.py        # Server
├── workspace/            # Agent workspace
├── skills/               # Custom skills
├── plugins/              # Plugins
├── data/                 # Config, memory, DB
├── models/               # AI models cache
└── logs/                # Log files
```

---

## 🔌 Plugins & Skills

### Plugins (Native + MCP + Marketplace)
```bash
# List plugins
neugi plugins list

# Install from GitHub
neugi plugins install https://github.com/user/repo

# Install from marketplace
neugi plugins install telegram-pro

# Create MCP plugin
neugi plugins create my_plugin --mcp
```

### Skills (OpenClaw Compatible)
```python
from neugi_swarm_skills import SkillManager
skills = SkillManager()
skills.execute("github", "issue")
```

---

## 🤖 Agent Swarm

NEUGI comes with 9 specialized agents:

- **Aurora** - Vision & image analysis
- **Cipher** - Security & encryption
- **Nova** - Creative writing
- **Pulse** - Data analysis
- **Quark** - Code generation
- **Shield** - Defense & safety
- **Spark** - Innovation
- **Ink** - Documentation
- **Nexus** - Central coordinator

---

## 📖 Usage After Install

### CLI Commands (like OpenClaw!)

```bash
# Start NEUGI
neugi start

# Check status
neugi status

# View logs
neugi logs

# Open dashboard
neugi dashboard

# Stop NEUGI
neugi stop

# Restart
neugi restart

# Run wizard again
neugi wizard
```

---

## 💾 After Restart

```bash
# Start NEUGI
neugi start

# Or manually
cd ~/neugi
python3 neugi_swarm.py
```

---

## 🌟 Why NEUGI?

| Traditional AI | NEUGI |
|----------------|-------|
| Manual install | **Auto-install** |
| Complex setup | **Smart wizard** |
| Just chatbot | **True NGI** |
| No CLI | **neugi CLI** |
| Paid search APIs | **FREE web browser** |
| macOS only | **Windows, Linux, macOS** |

---

## 📞 Support

- 🌐 Website: [neugi.com](https://neugi.com)
- 📧 Email: atharia.agi@gmail.com
- 🐦 Twitter: @atharia_agi
- 🐙 GitHub: https://github.com/atharia-agi/neugi_swarm
- 📝 Issues: https://github.com/atharia-agi/neugi_swarm/issues

---

<p align="center">
  <strong>NEUGI - Neural General Intelligence</strong><br>
  Made for everyone 🚀
</p>
