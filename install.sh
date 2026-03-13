#!/bin/bash
# 🤖 NEUGI SWARM - ONE-LINE INSTALLER
# =====================================
# Corporate: NEUGI
# 100% AUTOMATED - User just runs ONE command!

set -e

# ============================================================
# COLORS
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# ============================================================
# FUNCTIONS
# ============================================================

log_info() { echo -e "${BLUE}➜${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; }
log_step() { echo -e "${PURPLE}━━━${NC} $* ${PURPLE}━━━"; }

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
    # STEP 1: Install Ollama
    # ============================================================
    
    log_step "INSTALLING OLLAMA"
    
    if command -v ollama &> /dev/null; then
        log_success "Ollama already installed"
        log_info "Updating to latest version..."
        curl -fsSL https://ollama.ai/install.sh | sh >> /tmp/neugi_install.log 2>&1 || true
    else
        log_info "Installing Ollama (this may take a minute)..."
        curl -fsSL https://ollama.ai/install.sh | sh >> /tmp/neugi_install.log 2>&1
    fi
    
    if command -v ollama &> /dev/null; then
        log_success "Ollama ready"
    fi
    
    # ============================================================
    # STEP 2: Start Ollama Server
    # ============================================================
    
    log_step "STARTING OLLAMA SERVER"
    
    export PATH="$HOME/.local/bin:$PATH"
    
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_success "Ollama is already running"
    else
        log_info "Starting Ollama server..."
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        
        for i in {1..15}; do
            sleep 1
            if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
                log_success "Ollama server started"
                break
            fi
            if [ $i -eq 15 ]; then
                log_warn "Ollama starting in background..."
            fi
        done
    fi
    
    # ============================================================
    # STEP 3: Pull Models
    # ============================================================
    
    log_step "DOWNLOADING AI MODELS"
    
    export PATH="$HOME/.local/bin:$PATH"
    
    log_info "Pulling qwen3.5:cloud model..."
    ollama pull qwen3.5:cloud >> /tmp/neugi_install.log 2>&1 || true
    log_success "Model ready"
    
    # ============================================================
    # STEP 4: Install NEUGI
    # ============================================================
    
    log_step "INSTALLING NEUGI"
    
    NEUGI_DIR="$HOME/neugi"
    mkdir -p "$NEUGI_DIR"
    cd "$NEUGI_DIR"
    
    log_info "Downloading NEUGI files..."
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_swarm.py" -o neugi_swarm.py
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_wizard.py" -o neugi_wizard.py 2>/dev/null || true
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_technician.py" -o neugi_technician.py 2>/dev/null || true
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_assistant.py" -o neugi_assistant.py 2>/dev/null || true
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/dashboard.html" -o dashboard.html 2>/dev/null || true
    
    chmod +x neugi_swarm.py
    
    # Create config
    cat > config.py << 'EOF'
# 🤖 NEUGI SWARM CONFIG
USE_OLLAMA=true
OLLAMA_URL="http://localhost:11434"
OLLAMA_MODEL="qwen3.5:cloud"
MODEL="auto"
CONTEXT_WINDOW=2048
MASTER_KEY="neugi123"
EOF
    
    mkdir -p data models logs
    log_success "NEUGI installed to: $NEUGI_DIR"
    
    # ============================================================
    # STEP 5: Install NEUGI CLI (like openclaw!)
    # ============================================================
    
    log_step "INSTALLING NEUGI CLI"
    
    # Download CLI
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi" -o "$NEUGI_DIR/neugi"
    chmod +x "$NEUGI_DIR/neugi"
    
    # Download Assistant
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi_assistant.py" -o "$NEUGI_DIR/neugi_assistant.py" 2>/dev/null || true
    
    # Download Dashboard
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/dashboard.html" -o "$NEUGI_DIR/dashboard.html" 2>/dev/null || true
    
    # Download Systemd Service (for auto-start)
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/main/neugi.service" -o "$NEUGI_DIR/neugi.service" 2>/dev/null || true
    
    # Add to PATH in .bashrc
    if ! grep -q "neugi" ~/.bashrc 2>/dev/null; then
        echo "" >> ~/.bashrc
        echo "# NEUGI CLI" >> ~/.bashrc
        echo "export PATH=\"\$HOME/neugi:\$PATH\"" >> ~/.bashrc
    fi
    
    # Create symlink for global access
    sudo ln -sf "$NEUGI_DIR/neugi" /usr/local/bin/neugi 2>/dev/null || \
        ln -sf "$NEUGI_DIR/neugi" "$HOME/.local/bin/neugi" 2>/dev/null || true
    
    log_success "NEUGI CLI ready!"
    log_info "   Usage: neugi [command]"
    
    # ============================================================
    # STEP 6: RUN WIZARD AUTOMATICALLY
    # ============================================================
    
    log_step "RUNNING SETUP WIZARD"
    
    echo ""
    log_info "Starting setup wizard..."
    echo ""
    
    # Run wizard
    python3 neugi_wizard.py
    
    # ============================================================
    # STEP 7: START NEUGI + ACTIVITY LOG MODE
    # ============================================================
    
    log_step "STARTING NEUGI"
    
    echo ""
    log_success "Wizard complete!"
    echo ""
    
    # Start NEUGI in background
    log_info "Starting NEUGI Swarm..."
    nohup python3 neugi_swarm.py > "$NEUGI_DIR/logs/neugi.log" 2>&1 &
    NEUGI_PID=$!
    
    # Wait for startup
    sleep 3
    
    # ============================================================
    # ACTIVITY LOG MODE
    # ============================================================
    
    echo ""
    echo "╔═══════════════════════════════════════════════════╗"
    echo "║         🚀 NEUGI IS RUNNING!                      ║"
    echo "╚═══════════════════════════════════════════════════╝"
    echo ""
    echo "📖 Dashboard: http://localhost:19888"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "         📊 ACTIVITY LOG MODE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "💡 QUICK COMMANDS (after restart):"
    echo "   neugi start       - Start NEUGI"
    echo "   neugi stop        - Stop NEUGI"  
    echo "   neugi status      - Check status"
    echo "   neugi logs        - View logs"
    echo "   neugi dashboard   - Open dashboard"
    echo "   neugi help        - Ask NEUGI Assistant"
    echo ""
    echo "💡 AUTO-START AFTER REBOOT (optional):"
    echo "   cp ~/neugi/neugi.service ~/.config/systemd/user/"
    echo "   systemctl --user enable neugi"
    echo "   systemctl --user start neugi"
    echo ""
    
    # Show live logs
    log_info "Press Ctrl+C to stop"
    echo ""
    
    # Tail logs
    tail -f "$NEUGI_DIR/logs/neugi.log" 2>/dev/null || (
        echo "📋 Initial Activity Log:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "• NEUGI Swarm started successfully"
        echo "• Ollama connected: http://localhost:11434"
        echo "• Model loaded: qwen3.5:cloud"
        echo "• Dashboard ready: http://localhost:19888"
        echo "• Waiting for commands..."
        echo ""
        echo "💡 Use dashboard or send messages to interact!"
    )
}

# ============================================================
# RUN
# ============================================================

main "$@"
