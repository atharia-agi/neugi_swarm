#!/bin/bash
# 🤖 NEUGI SWARM - ONE-LINE INSTALLER
# =====================================
# Corporate: NEUGI
# 100% AUTOMATED - No manual steps needed!
# User just runs ONE command!

set -e

# ============================================================
# COLORS
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================
# FUNCTIONS
# ============================================================

log_info() { echo -e "${BLUE}➜${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; }

# ============================================================
# MAIN INSTALLER
# ============================================================

main() {
    echo ""
    echo "╔═══════════════════════════════════════════════════╗"
    echo "║         🤖 NEUGI SWARM INSTALLER                ║"
    echo "║     Neural General Intelligence - Made Easy     ║"
    echo "╚═══════════════════════════════════════════════════╝"
    echo ""
    
    # Add PATH
    export PATH="$HOME/.local/bin:$PATH"
    
    # ============================================================
    # STEP 1: Install Ollama (Fully Automated!)
    # ============================================================
    
    log_info "Step 1/5: Installing Ollama..."
    
    if command -v ollama &> /dev/null; then
        log_success "Ollama already installed"
        
        # Update to latest
        log_info "Updating Ollama to latest version..."
        curl -fsSL https://ollama.ai/install.sh | sh >> /tmp/neugi_install.log 2>&1 || true
    else
        log_info "Installing Ollama (this may take a minute)..."
        curl -fsSL https://ollama.ai/install.sh | sh >> /tmp/neugi_install.log 2>&1
        
        # Source profile
        if [ -f ~/.bashrc ]; then
            source ~/.bashrc 2>/dev/null || true
        fi
    fi
    
    # Verify
    if command -v ollama &> /dev/null; then
        log_success "Ollama ready: $(ollama --version 2>/dev/null || echo 'installed')"
    else
        log_warn "Ollama install needs terminal restart"
    fi
    
    # ============================================================
    # STEP 2: Start Ollama Server
    # ============================================================
    
    log_info "Step 2/5: Starting Ollama server..."
    
    export PATH="$HOME/.local/bin:$PATH"
    
    # Check if already running
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_success "Ollama is already running"
    else
        # Start in background
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        OLLAMA_PID=$!
        
        # Wait for startup
        for i in {1..15}; do
            sleep 1
            if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
                log_success "Ollama server started"
                break
            fi
            if [ $i -eq 15 ]; then
                log_warn "Ollama server starting in background..."
            fi
        done
    fi
    
    # ============================================================
    # STEP 3: Pull Models (Automatic!)
    # ============================================================
    
    log_info "Step 3/5: Setting up AI models..."
    
    export PATH="$HOME/.local/bin:$PATH"
    
    # Pull qwen3.5:cloud (main model)
    log_info "Downloading qwen3.5:cloud model..."
    ollama pull qwen3.5:cloud >> /tmp/neugi_install.log 2>&1 || true
    log_success "Cloud model ready"
    
    # ============================================================
    # STEP 4: Install NEUGI
    # ============================================================
    
    log_info "Step 4/5: Installing NEUGI Swarm..."
    
    # Create directory
    NEUGI_DIR="$HOME/neugi"
    mkdir -p "$NEUGI_DIR"
    cd "$NEUGI_DIR"
    
    # Download main file
    log_info "Downloading NEUGI files..."
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm.py" -o neugi_swarm.py
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_wizard.py" -o neugi_wizard.py 2>/dev/null || true
    
    chmod +x neugi_swarm.py
    
    # Create config
    cat > config.py << 'EOF'
# 🤖 NEUGI SWARM CONFIG
# =====================
# Corporate: NEUGI

# Ollama (Default - FREE!)
USE_OLLAMA=true
OLLAMA_URL="http://localhost:11434"
OLLAMA_MODEL="qwen3.5:cloud"

MODEL="auto"
CONTEXT_WINDOW=2048
MASTER_KEY="neugi123"
EOF
    
    # Create directories
    mkdir -p data models logs
    
    log_success "NEUGI installed to: $NEUGI_DIR"
    
    # ============================================================
    # STEP 5: Ready!
    # ============================================================
    
    echo ""
    echo "╔═══════════════════════════════════════════════════╗"
    echo "║         ✅ INSTALLATION COMPLETE!                 ║"
    echo "╚═══════════════════════════════════════════════════╝"
    echo ""
    echo "📍 Location: $NEUGI_DIR"
    echo ""
    echo "🚀 TO START NEUGI:"
    echo "   cd $NEUGI_DIR"
    echo "   python3 neugi_wizard.py"
    echo ""
    echo "📖 Dashboard: http://localhost:19888"
    echo ""
    echo "💡 First time? Run the wizard - it will guide you!"
    echo ""
}

# ============================================================
# RUN
# ============================================================

main "$@"
