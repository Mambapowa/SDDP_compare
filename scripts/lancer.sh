#!/usr/bin/env bash
# Lance l'interface web du comparateur SDDP (port 8501 par défaut).
# Usage : ./scripts/lancer.sh [port]
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-8501}"
echo "Interface disponible sur http://$(hostname -I 2>/dev/null | awk '{print $1}'):$PORT  (Ctrl+C pour arrêter)"
exec .venv/bin/streamlit run app.py \
    --server.address 0.0.0.0 --server.port "$PORT" \
    --server.headless true --browser.gatherUsageStats false
