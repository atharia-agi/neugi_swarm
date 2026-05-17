#!/usr/bin/env bash
# NEUGI Swarm v2 - Root Install Wrapper
# Delegates to neugi_swarm_v2/install.sh

set -e

REPO_URL="https://github.com/atharia-agi/neugi_swarm.git"
INSTALL_DIR="${NEUGI_INSTALL_DIR:-$HOME/neugi_swarm}"

echo "NEUGI Swarm v2 Installer"
echo "========================"
echo ""

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull origin master
else
    echo "Cloning repository..."
    if [ -e "$INSTALL_DIR" ] && [ "$(find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 2>/dev/null | head -n 1)" ]; then
        echo "[ERROR] Install directory exists but is not a NEUGI git repo: $INSTALL_DIR"
        echo "Set NEUGI_INSTALL_DIR to an empty directory or remove the directory first."
        exit 1
    fi
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo "Running v2 installer..."
bash neugi_swarm_v2/install.sh
