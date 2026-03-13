#!/bin/bash
# 🤖 NEUGI SWARM ONE-LINE INSTALLER
# ==================================
# Supports: Linux, macOS, Windows (WSL)
# Works with: Any Python 3.8+

set -e

echo "🤖 Installing Neugi Swarm..."
echo "================================"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Install from python.org or: sudo apt install python3"
    exit 1
fi

echo "✅ Python3 found: $(python3 --version)"

# Create neugi directory
NEUGI_DIR="$HOME/neugi"
mkdir -p "$NEUGI_DIR"
cd "$NEUGI_DIR"

echo "📁 Created directory: $NEUGI_DIR"

# Download main file
echo "📥 Downloading Neugi Swarm..."
curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm.py" -o neugi_swarm.py

if [ $? -ne 0 ]; then
    echo "❌ Download failed. Trying alternate..."
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi_swarm.py" -o neugi_swarm.py
fi

# Make executable
chmod +x neugi_swarm.py

# Create config
cat > config.py << 'EOF'
# 🤖 NEUGI SWARM CONFIGURATION
# ============================

# ============================================================
# STEP 1: Choose Your LLM Provider
# ============================================================

# OPTION A: Free Providers (RECOMMENDED FOR START!)
# -----------------------------------------------

# Groq (Free, fast!) - https://console.groq.com
# GROQ_API_KEY="gsk_..."

# OpenRouter (Many free models!) - https://openrouter.ai
# OPENROUTER_API_KEY="sk..."

# ============================================================

# OPTION B: Cheap Providers
# --------------------------

# MiniMax (Cheap, good quality) - https://platform.minimax.io
# MINIMAX_API_KEY="..."

# ============================================================

# OPTION C: Premium Providers
# ---------------------------

# OpenAI - https://platform.openai.com
# OPENAI_API_KEY="sk-..."

# Anthropic - https://console.anthropic.com
# ANTHROPIC_API_KEY="sk-ant-..."

# ============================================================

# OPTION D: Local (Free forever!)
# -------------------------------

# Ollama (Local models) - https://ollama.ai
# Set USE_OLLAMA=true and make sure Ollama is running
USE_OLLAMA=false
OLLAMA_URL="http://localhost:11434"
OLLAMA_MODEL="llama2"  # or mistral, codellama, etc

# llama.cpp (Very lightweight!)
# Set USE_LLAMACPP=true
USE_LLAMACPP=false
LLAMACPP_PATH="./models/"

# ============================================================
# STEP 2: Model Selection (Flexible Context!)
# ============================================================

# Minimum context: 2K tokens (works with small models!)
# Recommended: 8K+ for better performance

# For free tier / weak API:
MODEL="auto"  # Auto-select best available

# Specific models (check your provider's model list):
# - groq: llama-3.1-8b-instant, mixtral-8x7b-32768
# - openrouter: google/gemini-flash, meta-llama
# - ollama: llama2, mistral, codellama

# Context window (minimum that works):
CONTEXT_WINDOW=2048  # Works with small models!

# ============================================================
# STEP 3: Channels (Optional)
# ============================================================

# Telegram
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""

# Discord
DISCORD_WEBHOOK_URL=""

# WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=""
TWILIO_AUTH_TOKEN=""
TWILIO_PHONE_NUMBER=""

# ============================================================
# STEP 4: Security
# ============================================================

# Your master key (controls everything)
MASTER_KEY="change_me_in_setup"

# Rate limiting
RATE_LIMIT_MINUTE=60
RATE_LIMIT_HOUR=1000

# ============================================================
# END OF CONFIG
# ============================================================
EOF

echo "✅ Config created: config.py"

# Try to download additional files
echo "📦 Getting additional modules..."
curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm_skills.py" -o neugi_swarm_skills.py 2>/dev/null || true
curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm_channels.py" -o neugi_swarm_channels.py 2>/dev/null || true

# Create data directory
mkdir -p data models logs

echo ""
echo "================================"
echo "✅ INSTALLATION COMPLETE!"
echo "================================"
echo ""
echo "📍 Location: $NEUGI_DIR"
echo ""
echo "NEXT STEPS:"
echo "----------"
echo "1. Edit config.py and add your API key:"
echo "   nano config.py"
echo ""
echo "2. Run setup wizard:"
echo "   python3 neugi_swarm.py --setup"
echo ""
echo "3. Start Neugi:"
echo "   python3 neugi_swarm.py"
echo ""
echo "Or use --help for more options!"
echo ""
