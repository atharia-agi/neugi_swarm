#!/bin/bash
set -e

echo "========================================="
echo "  NEUGI Swarm V2.1.3 - Installer"
echo "========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${YELLOW}Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3.10 or higher:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  macOS: brew install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)${NC}"
    exit 1
fi

echo -e "${GREEN}[OK] Python $PYTHON_VERSION detected${NC}"

# Check Ollama
if ! command -v ollama &> /dev/null; then
    echo -e "${YELLOW}[WARN] Ollama not found. NEUGI can use local AI through Ollama.${NC}"
    echo "Options:"
    echo "  1. Install Ollama now (curl -fsSL https://ollama.com/install.sh | sh)"
    echo "  2. Skip and use cloud API later"
    read -p "Install Ollama? [Y/n]: " choice
    if [[ ! "$choice" =~ ^[Nn]$ ]]; then
        echo -e "${YELLOW}Installing Ollama...${NC}"
        curl -fsSL https://ollama.com/install.sh | sh
        echo -e "${GREEN}[OK] Ollama installed${NC}"
    else
        echo -e "${YELLOW}Skipping Ollama. Run 'neugi wizard' later to set up cloud API.${NC}"
    fi
else
    echo -e "${GREEN}[OK] Ollama found${NC}"
fi

# Create installation directory. Runtime config still lives in ~/.neugi.
INSTALL_DIR="${NEUGI_INSTALL_DIR:-$HOME/neugi_swarm}"
echo -e "${YELLOW}Installing to: $INSTALL_DIR${NC}"

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Clone or update the repository.
if [ -d ".git" ]; then
    echo -e "${YELLOW}Updating existing installation...${NC}"
    git pull origin master || git pull
else
    echo -e "${YELLOW}Downloading NEUGI Swarm V2...${NC}"
    if command -v curl &> /dev/null; then
        curl -fsSL https://github.com/atharia-agi/neugi_swarm/archive/refs/heads/master.tar.gz | tar xz --strip-components=1
    elif command -v wget &> /dev/null; then
        wget -qO- https://github.com/atharia-agi/neugi_swarm/archive/refs/heads/master.tar.gz | tar xz --strip-components=1
    else
        echo -e "${RED}Error: curl or wget is required${NC}"
        exit 1
    fi
fi

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
PACKAGE_DIR="$INSTALL_DIR/neugi_swarm_v2"
if [ ! -d "$PACKAGE_DIR/venv" ]; then
    python3 -m venv "$PACKAGE_DIR/venv"
fi
source "$PACKAGE_DIR/venv/bin/activate"

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip
pip install -e "$PACKAGE_DIR"

# Create symlink for CLI
echo -e "${YELLOW}Creating CLI symlink...${NC}"
if [ -w "/usr/local/bin" ]; then
    ln -sf "$PACKAGE_DIR/venv/bin/neugi" /usr/local/bin/neugi
else
    ln -sf "$PACKAGE_DIR/venv/bin/neugi" "$INSTALL_DIR/neugi"
    echo -e "${YELLOW}Add to PATH: export PATH=\"$INSTALL_DIR:\$PATH\"${NC}"
fi

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  NEUGI Swarm V2 installed successfully!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Quick start:"
echo "  neugi wizard      # Pick provider, enter API key, choose model"
echo "  neugi chat        # Start chatting"
echo "  neugi status      # Check system health"
echo ""
echo "Documentation: https://neugi.com/docs.html"
