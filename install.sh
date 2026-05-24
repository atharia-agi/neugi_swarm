#!/bin/bash
set -e

cat <<'EOF'
 _   _ _____ _   _  ____ ___
| \ | | ____| | | |/ ___|_ _|
|  \| |  _| | | | | |  _ | |
| |\  | |___| |_| | |_| || |
|_| \_|_____|\___/ \____|___|
EOF
echo "NEUGI Installer Safety Notice"
echo "- This framework can execute autonomous and tool-driven actions."
echo "- Outputs can be incorrect; keep human oversight and staged rollout."
echo "- Use implies acceptance of Terms/Privacy at https://neugi.com."
echo
read -r -p "Continue installer bootstrap? [y/N]: " NEUGI_BOOTSTRAP_CONSENT
if [[ ! "$NEUGI_BOOTSTRAP_CONSENT" =~ ^[Yy]$ ]]; then
  echo "[NEUGI] Installation cancelled by user."
  exit 0
fi

SCRIPT_URL="https://raw.githubusercontent.com/atharia-agi/neugi_swarm/master/neugi_swarm_v2/install.sh"
curl -fsSL "$SCRIPT_URL" | bash
