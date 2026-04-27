#!/bin/bash
set -e

echo "========================================="
echo "  NEUGI Swarm V2 - Installer"
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

echo -e "${GREEN}✓ Python $PYTHON_VERSION detected${NC}"

# Create installation directory
INSTALL_DIR="${NEUGI_INSTALL_DIR:-$HOME/.neugi}"
echo -e "${YELLOW}Installing to: $INSTALL_DIR${NC}"

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Clone or copy the repository
if [ -d ".git" ]; then
    echo -e "${YELLOW}Updating existing installation...${NC}"
    git pull || true
else
    echo -e "${YELLOW}Downloading NEUGI Swarm V2...${NC}"
    if command -v curl &> /dev/null; then
        curl -fsSL https://github.com/neugi-ai/neugi-swarm-v2/archive/refs/heads/main.tar.gz | tar xz --strip-components=1
    elif command -v wget &> /dev/null; then
        wget -qO- https://github.com/neugi-ai/neugi-swarm-v2/archive/refs/heads/main.tar.gz | tar xz --strip-components=1
    else
        echo -e "${RED}Error: curl or wget is required${NC}"
        exit 1
    fi
fi

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip
pip install -e .

# Create symlink for CLI
echo -e "${YELLOW}Creating CLI symlink...${NC}"
if [ -w "/usr/local/bin" ]; then
    ln -sf "$INSTALL_DIR/venv/bin/neugi" /usr/local/bin/neugi
else
    ln -sf "$INSTALL_DIR/venv/bin/neugi" "$INSTALL_DIR/neugi"
    echo -e "${YELLOW}Add to PATH: export PATH=\"$INSTALL_DIR:\$PATH\"${NC}"
fi

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  NEUGI Swarm V2 installed successfully!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Quick start:"
echo "  neugi init        # Initialize configuration"
echo "  neugi start       # Start the gateway"
echo "  neugi status      # Check status"
echo ""
echo "Documentation: https://docs.neugi.ai"
