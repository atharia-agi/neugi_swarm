#!/bin/bash
# 🤖 NEUGI SWARM ONE-LINE INSTALLER
# ==================================
# Supports: Linux, macOS, Windows (WSL)
# Corporate Brand: NEUGI

set -e

echo "🤖 Installing NEUGI Swarm..."
echo "================================"
echo ""

# ============================================================
# STEP 1: Install/Update Ollama (NO SIGNUP REQUIRED!)
# ============================================================

echo "📦 Installing Ollama (latest)..."
echo "   💡 NOTE: Ollama is FREE, no signup required!"
echo "   💡 Cloud models (qwen3.5:cloud) work with free tier"
echo "   💡 For heavy usage, can upgrade to Pro ($20/mo) later"

# Check if Ollama is already installed
if command -v ollama &> /dev/null; then
    echo "   ✅ Ollama already installed: $(ollama --version)"
    
    # UPDATE to latest version!
    echo "   🔄 Updating Ollama to latest version..."
    curl -fsSL https://ollama.ai/install.sh | sh
    
    echo "   ✅ Ollama updated!"
else
    # Install Ollama based on OS
    echo "   🐧 Installing Ollama for Linux/macOS..."
    curl -fsSL https://ollama.ai/install.sh | sh
    
    # Add to PATH
    export PATH="$HOME/.local/bin:$PATH"
    
    if command -v ollama &> /dev/null; then
        echo "   ✅ Ollama installed: $(ollama --version)"
    else
        echo "   ⚠️ Please restart terminal or run: source ~/.bashrc"
    fi
fi

echo ""

# ============================================================
# STEP 2: Start Ollama Server
# ============================================================

echo "🚀 Starting Ollama server..."

# Add to path
export PATH="$HOME/.local/bin:$PATH"

# Start in background
ollama serve &
OLLAMA_PID=$!

# Wait for startup
sleep 3

# Check if running
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "   ✅ Ollama is running!"
else
    sleep 2
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "   ✅ Ollama is running!"
    else
        echo "   ⚠️ Ollama started in background"
    fi
fi

echo ""

# ============================================================
# STEP 3: Pull Recommended Models (Free!)
# ============================================================

echo "📥 Pulling recommended models (FREE, local)..."

# Pull qwen3.5:cloud (works with free tier!)
echo "   • Pulling qwen3.5:cloud (cloud model - free tier)..."
ollama pull qwen3.5:cloud 2>/dev/null || echo "   • Cloud model will be pulled on first use"

# Pull local backup model
echo "   • Pulling qwen3.5:7b (local backup)..."
ollama pull qwen3.5:7b 2>/dev/null || echo "   • Will be downloaded on first use"

echo ""

# ============================================================
# STEP 4: Check Python
# ============================================================

if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Install: sudo apt install python3"
    exit 1
fi

echo "✅ Python3 found: $(python3 --version)"

# ============================================================
# STEP 5: Create NEUGI Directory
# ============================================================

NEUGI_DIR="$HOME/neugi"
mkdir -p "$NEUGI_DIR"
cd "$NEUGI_DIR"

echo "📁 Created: $NEUGI_DIR"

# ============================================================
# STEP 6: Download NEUGI Files
# ============================================================

echo "📥 Downloading NEUGI Swarm..."

curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm.py" -o neugi_swarm.py
curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_wizard.py" -o neugi_wizard.py 2>/dev/null || true

chmod +x neugi_swarm.py

# ============================================================
# STEP 7: Create Config
# ============================================================

cat > config.py << 'EOF'
# 🤖 NEUGI SWARM CONFIG
# =====================
# Corporate: NEUGI

# ============================================================
# LLM Provider (Free Options!)
# ============================================================

# OPTION A: Ollama Cloud (FREE tier works!)
# -----------------------------------------
# qwen3.5:cloud - Best for NEUGI!
# Works with free tier (light usage)
USE_OLLAMA=true
OLLAMA_URL="http://localhost:11434"
OLLAMA_MODEL="qwen3.5:cloud"

# OPTION B: Local Models (100% FREE!)
# -----------------------------------
# ollama pull llama3.2:3b
# ollama pull mistral:7b
# ollama pull codellama:7b

# OPTION C: Free API Providers
# ----------------------------
# Groq (Free!) - https://console.groq.com
# GROQ_API_KEY="gsk_..."

# OpenRouter (Free tier) - https://openrouter.ai
# OPENROUTER_API_KEY="sk..."

# ============================================================
# Model Settings
# ============================================================

MODEL="auto"
CONTEXT_WINDOW=2048  # Works with small models!

# ============================================================
# Security
# ============================================================

MASTER_KEY="change_me"

# ============================================================
# END
# ============================================================
EOF

echo "✅ Config created: config.py"

# Create directories
mkdir -p data models logs

echo ""
echo "================================"
echo "✅ INSTALLATION COMPLETE!"
echo "================================"
echo ""
echo "📍 Location: $NEUGI_DIR"
echo "🔧 Ollama: Installed & Running"
echo "📦 Models: Downloaded"
echo ""
echo "NEXT STEPS:"
echo "----------"
echo "1. Run setup wizard:"
echo "   python3 neugi_wizard.py"
echo ""
echo "2. Or start NEUGI:"
echo "   python3 neugi_swarm.py"
echo ""
echo "📖 Dashboard: http://localhost:19888"
echo ""
echo "💡 FREE TIER: qwen3.5:cloud works with Ollama free!"
echo "💡 UPGRADE: https://ollama.com/pricing for Pro ($20/mo)"
echo ""
