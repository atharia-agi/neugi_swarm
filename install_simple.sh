#!/bin/bash
# 🤖 NEUGI SWARM - ONE-COMMAND INSTALL
# ======================================
# Usage: curl -sSL neugi.ai/install | bash

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   🤖 NEUGI SWARM - INSTALL IN 30 SECONDS         ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}❌ Python3 not found${NC}"
    echo "Install from: https://python.org"
    exit 1
fi

echo -e "${GREEN}✅ Python3 found${NC}: $(python3 --version)"

# Create directory
NEUGI_DIR="$HOME/neugi"
mkdir -p "$NEUGI_DIR"
cd "$NEUGI_DIR"

echo -e "${GREEN}✅ Created directory${NC}: $NEUGI_DIR"

# Download main files
echo "📥 Downloading Neugi..."

# Download wizard (new!)
curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi_wizard.py" -o neugi_wizard.py

# Download main
curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi_swarm.py" -o neugi_swarm.py

# Download install scripts
curl -sSL "https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/install.sh" -o install.sh

chmod +x *.py *.sh 2>/dev/null || true

echo -e "${GREEN}✅ Download complete${NC}"

# Create data directory
mkdir -p data memory logs

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   🎉 INSTALL COMPLETE!                             ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "NEXT STEPS:"
echo "----------"
echo ""
echo "Option 1: RUN WIZARD (Recommended!)"
echo "  cd $NEUGI_DIR"
echo "  python3 neugi_wizard.py --wizard"
echo ""
echo "Option 2: QUICK CHAT"
echo "  python3 neugi_swarm.py"
echo ""
echo "Dashboard: http://localhost:19888"
echo ""
echo "🎯 That's it! You're ready to use Neugi!"
echo ""
