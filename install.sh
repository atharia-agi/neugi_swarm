#!/usr/bin/env bash
# NEUGI Swarm v2 — Root Install Wrapper
# Delegates to neugi_swarm_v2/install.sh

set -e

REPO_URL="https://github.com/atharia-agi/neugi_swarm.git"
INSTALL_DIR="${HOME}/neugi_swarm"

echo "🦞 NEUGI Swarm v2 Installer"
echo "============================"
echo ""

# Clone or update
if [ -d "$INSTALL_DIR" ]; then
    echo "📁 Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull origin master
else
    echo "📥 Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Delegate to v2 installer
echo "🚀 Running v2 installer..."
bash neugi_swarm_v2/install.sh
