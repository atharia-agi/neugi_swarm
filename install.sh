#!/bin/bash
# 🤖 NEUGI SWARM ONE-LINE INSTALLER
# ==================================
# Supports: Linux, macOS, Windows (WSL)
# Includes: Ollama latest version!

set -e

echo "🤖 Installing NEUGI Swarm..."
echo "================================"
echo ""

# ============================================================
# STEP 1: Install Ollama (Latest Version!)
# ============================================================

echo "📦 Installing Ollama (latest)..."

# Check if Ollama is already installed
if command -v ollama &> /dev/null; then
    echo "   ✅ Ollama already installed: $(ollama --version)"
else
    # Detect OS and install Ollama
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        echo "   📱 Installing Ollama for macOS..."
        curl -fsSL https://ollama.ai/install.sh | sh
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        echo "   🐧 Installing Ollama for Linux..."
        curl -fsSL https://ollama.ai/install.sh | sh
        
        # Add to PATH for this session
        export PATH="$HOME/.local/bin:$PATH"
    else
        # Other - try generic install
        echo "   💻 Installing Ollama..."
        curl -fsSL https://ollama.ai/install.sh | sh
    fi
    
    # Verify installation
    if command -v ollama &> /dev/null; then
        echo "   ✅ Ollama installed: $(ollama --version)"
    else
        echo "   ⚠️ Could not install Ollama automatically."
        echo "   Please install manually from: https://ollama.ai"
    fi
fi

echo ""

# Start Ollama in background (for the wizard!)
echo "🚀 Starting Ollama server..."
export PATH="$HOME/.local/bin:$PATH"

# Try to start ollama serve in background
ollama serve &
OLLAMA_PID=$!

# Wait a moment for Ollama to start
sleep 3

# Check if Ollama is running
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "   ✅ Ollama is running!"
else
    # Try once more
    sleep 2
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "   ✅ Ollama is running!"
    else
        echo "   ⚠️ Ollama started in background"
    fi
fi

echo ""

# ============================================================
# STEP 2: Check Python
# ============================================================

if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Install from python.org or: sudo apt install python3"
    exit 1
fi

echo "✅ Python3 found: $(python3 --version)"

# ============================================================
# STEP 3: Create NEUGI Directory
# ============================================================

NEUGI_DIR="$HOME/neugi"
mkdir -p "$NEUGI_DIR"
cd "$NEUGI_DIR"

echo "📁 Created directory: $NEUGI_DIR"

# ============================================================
# STEP 4: Download NEUGI Files
# ============================================================

echo "📥 Downloading NEUGI Swarm..."

# Download main file
curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm.py" -o neugi_swarm.py

if [ $? -ne 0 ]; then
    echo "❌ Download failed. Trying alternate..."
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi_swarm.py" -o neugi_swarm.py
fi

# Download wizard
curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_wizard.py" -o neugi_wizard.py 2>/dev/null || true

# Make executable
chmod +x neugi_swarm.py

# ============================================================
# STEP 5: Create Config
# ============================================================

cat > config.py << 'EOF'
# 🤖 NEUGI SWARM CONFIGURATION
# ============================
# Corporate: NEUGI (Neural General Intelligence)

# ============================================================
# LLM Provider Selection
# ============================================================

# OPTION A: Free Providers (RECOMMENDED!)
# ----------------------------------------

# Groq (Fast, free!) - https://console.groq.com
# GROQ_API_KEY="gsk_..."

# OpenRouter (Many free models!) - https://openrouter.ai
# OPENROUTER_API_KEY="sk..."

# ============================================================

# OPTION B: Cheap Providers
# --------------------------

# MiniMax - https://platform.minimax.io
# MINIMAX_API_KEY="..."

# ============================================================

# OPTION C: Premium Providers
# --------------------------

# OpenAI - https://platform.openai.com
# OPENAI_API_KEY="sk-..."

# Anthropic - https://console.anthropic.com
# ANTHROPIC_API_KEY="sk-ant-..."

# ============================================================

# OPTION D: Ollama (Local - FREE forever!)
# ----------------------------------------

# NEUGI will auto-start Ollama if needed
USE_OLLAMA=true
OLLAMA_URL="http://localhost:11434"
OLLAMA_MODEL="qwen3.5:cloud"  # Best for NEUGI!

# ============================================================
# Model Selection (2K+ Context Works!)
# ============================================================

MODEL="auto"  # Auto-select best
CONTEXT_WINDOW=2048  # Minimum that works!

# ============================================================
# Channels (Optional)
# ============================================================

# Telegram
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""

# Discord
DISCORD_WEBHOOK_URL=""

# ============================================================
# Security
# ============================================================

MASTER_KEY="change_me"

# ============================================================
# END
# ============================================================
EOF

echo "✅ Config created: config.py"

# Download additional modules
echo "📦 Getting additional modules..."
curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm_skills.py" -o neugi_swarm_skills.py 2>/dev/null || true
curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm_channels.py" -o neugi_swarm_channels.py 2>/dev/null || true

# Create directories
mkdir -p data models logs

echo ""
echo "================================"
echo "✅ INSTALLATION COMPLETE!"
echo "================================"
echo ""
echo "📍 Location: $NEUGI_DIR"
echo "🔧 Ollama: Installed & Running"
echo ""
echo "NEXT STEPS:"
echo "----------"
echo "1. Run setup wizard:"
echo "   python3 neugi_wizard.py"
echo ""
echo "2. Or start NEUGI directly:"
echo "   python3 neugi_swarm.py"
echo ""
echo "📖 Dashboard: http://localhost:19888"
echo ""
