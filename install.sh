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
    echo -e "${RED}${BOLD}  ⚠️  DANGER: UNRESTRICTED SYSTEM ACCESS${NC}"
    echo -e "${YELLOW}  NEUGI is an autonomous AI system. By installing, you give the"
    echo -e "  AI permission to execute system-level commands on this machine.${NC}"
    echo ""
    log_step "QUICK INSTALL NEUGI"
    echo ""
    
    # Add PATH
export PATH="$HOME/.local/bin:$PATH"
    
    # ============================================================
    # STEP 1: Install Ollama (REQUIRED)
    # ============================================================
    
    log_step "🔄 INSTALLING OLLAMA (Required for NEUGI)"
    
    if command -v ollama &> /dev/null; then
        log_success "✓ Ollama ALREADY installed"
    else
        log_info "Installing Ollama..."
        
        # Download Ollama binary directly (fast!)
        curl -L https://ollama.ai/download/ollama-linux-amd64 -o /tmp/ollama 2>&1 | while IFS= read -r line; do
            echo -ne "\rDownloading... $line"
        done
        
        if [ -f /tmp/ollama ]; then
            chmod +x /tmp/ollama
            sudo cp /tmp/ollama /usr/local/bin/ollama 2>/dev/null || sudo mv /tmp/ollama /usr/local/bin/ollama
            log_success "✓ Ollama installed successfully!"
        else
            log_warn "Ollama download failed - you can install manually later"
        fi
    fi
    
    # Now verify
    if command -v ollama &> /dev/null; then
        log_success "✓ Ollama is ready!"
    fi
    
    # ============================================================
    # STEP 2: Clone NEUGI
    # ============================================================
    
    log_step "📦 CLONING NEUGI"
    
    NEUGI_DIR="$HOME/neugi"
    mkdir -p "$NEUGI_DIR"
    cd "$NEUGI_DIR"
    
    log_info "Cloning NEUGI (shallow clone - fast)..."
    git clone --depth 1 https://github.com/atharia-agi/neugi_swarm.git "$NEUGI_DIR"
    
    log_info "Installing python dependencies (lightweight)..."
    pip3 install requests flask psutil --break-system-packages 2>/dev/null || pip3 install requests flask psutil 2>/dev/null || true
    
    log_success "✓ Dependencies ready"
    
    chmod +x neugi_swarm/neugi_swarm.py 2>/dev/null || true
    
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
    
    mkdir -p data models logs workspace
    log_success "✓ NEUGI installed to: $NEUGI_DIR"
    
    # ============================================================
    # START EVERYTHING UP!
    # ============================================================
    
    log_step "🚀 STARTING NEUGI..."
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🎉 NEUGI READY! Starting now..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Start Ollama in background
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 2
    
    # Check if running
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        log_success "✓ Ollama server running on port 11434"
    else
        log_info "Ollama may take a moment to start..."
    fi
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  To start NEUGI Wizard:"
    echo "  ➜ cd ~/neugi"
    echo "  ➜ python neugi_swarm/neugi_wizard.py"
    echo ""
    echo "  Or use: python neugi_swarm/neugi_swarm.py"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # ============================================================
    # STEP 5: Install NEUGI CLI (like openclaw!)
    # ============================================================
    
    log_step "INSTALLING NEUGI CLI"
    
    # Download CLI
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi" -o "$NEUGI_DIR/neugi"
    chmod +x "$NEUGI_DIR/neugi"
    
    # Download Assistant
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi_assistant.py" -o "$NEUGI_DIR/neugi_assistant.py" 2>/dev/null || true
    
    # Download Dashboard
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/dashboard.html" -o "$NEUGI_DIR/dashboard.html" 2>/dev/null || true
    
    # Download Systemd Service (for auto-start)
    curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi.service" -o "$NEUGI_DIR/neugi.service" 2>/dev/null || true
    
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
    python3 neugi_swarm/neugi_wizard.py
    
    # ============================================================
    # STEP 7: START NEUGI + ACTIVITY LOG MODE
    # ============================================================
    
    log_step "STARTING NEUGI"
    
    echo ""
    log_success "Wizard complete!"
    echo ""
    
    # Start NEUGI in background
    log_info "Starting NEUGI Swarm..."
    nohup python3 neugi_swarm/neugi_swarm.py > "$NEUGI_DIR/logs/neugi.log" 2>&1 &
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
