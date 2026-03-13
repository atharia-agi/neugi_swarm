# 📖 NEUGI Installation Guide

## One-Command Installation

```bash
curl -fsSL https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/install.sh | bash
```

---

## What Happens Automatically?

| Step | Action | Your Action |
|------|--------|--------------|
| 1 | Install Ollama (latest) | ❌ None |
| 2 | Start Ollama Server | ❌ None |
| 3 | Download qwen3.5:cloud model | ❌ None |
| 4 | Download NEUGI files | ❌ None |
| 5 | Install NEUGI CLI | ❌ None |
| 6 | **Run Setup Wizard** | ✅ **Your input!** |
| 7 | Start NEUGI + Activity Log | ❌ None |

---

## Step-by-Step Flow

### 1. User runs command

```bash
curl -fsSL https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/install.sh | bash
```

### 2. System installs automatically

```
━━━ INSTALLING OLLAMA ━━━
✓ Ollama ready

━━━ STARTING OLLAMA SERVER ━━━
✓ Ollama server started

━━━ DOWNLOADING AI MODELS ━━━
✓ Model ready

━━━ INSTALLING NEUGI ━━━
✓ NEUGI installed

━━━ INSTALLING NEUGI CLI ━━━
✓ NEUGI CLI ready!
```

### 3. Wizard runs (YOUR INPUT)

```
━━━ RUNNING SETUP WIZARD ━━━

🤖 NEUGI WIZARD v2.4

➜ Step 1: Checking Ollama...
   ✓ Ollama is running!

➜ Step 2: Your Name
What should I call you? ← KETIK NAMA

➜ Step 3: How will you use NEUGI?
   1. Just chat
   2. Help with coding
   3. Research
   4. Automation
Choose (1-4): ← PILIH

➜ Step 4: API Key
Do you have your own AI API key? (y/n): ← JAWAB

[If YES: enter your API key]
[If NO: auto-use qwen3.5:cloud]

✓ Setup complete!
```

### 4. NEUGI starts

```
━━━ STARTING NEUGI ━━━

╔═══════════════════════════════════════════╗
║         🚀 NEUGI IS RUNNING!              ║
╚═══════════════════════════════════════════╝

📖 Dashboard: http://localhost:19888

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         📊 ACTIVITY LOG MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• NEUGI Swarm started successfully
• Ollama connected
• Model loaded: qwen3.5:cloud
```

---

## After Installation

### Quick Commands

```bash
# Start NEUGI (after restart)
neugi start

# Check status
neugi status

# View logs
neugi logs

# Open dashboard
neugi dashboard

# Stop NEUGI
neugi stop
```

### Manual Start (Alternative)

```bash
cd ~/neugi
python3 neugi_swarm.py
```

---

## Access Dashboard

Buka browser:

```
http://localhost:19888
```

---

## Need Help?

### Check Status

```bash
neugi status
```

### View Logs

```bash
neugi logs
```

### Re-run Wizard

```bash
neugi wizard
```

---

## Requirements

| Requirement | Minimum |
|-------------|---------|
| Python | 3.8+ |
| RAM | 2GB |
| Internet | Required for install |

---

## Troubleshooting

### Ollama not running?

```bash
# Start Ollama manually
ollama serve

# Or use CLI
neugi start
```

### Port busy?

NEUGI uses port 19888 by default.

---

## Next Steps

After install, you can:

- 🎯 Use dashboard: http://localhost:19888
- 💬 Chat with NEUGI
- 🔧 Configure advanced settings
- 🔌 Add API keys for more features

---

**Questions?** Open an issue at https://github.com/atharia-agi/neugi_swarm/issues
