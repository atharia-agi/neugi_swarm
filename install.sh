#!/bin/bash
# Neugi Army One-Line Installer

echo "🤖 Installing Neugi Army..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 required"
    exit 1
fi

# Download latest version
curl -sSL https://raw.githubusercontent.com/atharia-agi/neugi_army/main/neugi_army_v11.py -o neugi.py

if [ $? -eq 0 ]; then
    echo "✅ Neugi Army downloaded!"
    echo ""
    echo "To run:"
    echo "  python3 neugi.py"
    echo ""
    echo "First-time setup:"
    echo "  cp config_template.py config.py"
    echo "  # Add your API_KEY"
else
    echo "❌ Download failed"
    exit 1
fi
