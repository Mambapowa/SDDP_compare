#!/usr/bin/env bash
# Installe le comparateur SDDP sans accès Internet.
# À lancer depuis le dossier de l'archive, qui contient le sous-dossier wheels/.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null; then
    echo "Python introuvable. Indiquez-le : PYTHON=/chemin/vers/python3.14 $0" >&2
    exit 1
fi
echo "Python utilisé : $("$PY" --version) ($(command -v "$PY"))"
if [ ! -d wheels ]; then
    echo "Dossier wheels/ absent : utilisez l'archive complète hors ligne." >&2
    exit 1
fi

"$PY" -m venv .venv
.venv/bin/python -m pip install --no-index --find-links wheels -r requirements.txt

echo
echo "Installation terminée. Pour lancer l'interface web :"
echo "  ./scripts/lancer.sh"
