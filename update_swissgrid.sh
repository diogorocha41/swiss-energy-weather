#!/bin/bash
# Atualiza os dados da Swissgrid e publica no GitHub.
# Uso: põe o Excel novo em data/raw/swissgrid/ (substitui o antigo) e corre:
#   ./update_swissgrid.sh
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

echo "▶ A correr o pipeline..."
python -m src.pipeline all

if git diff --quiet -- data/processed data/marts; then
  echo "✔ Nada mudou nos dados — não há nada para enviar."
  exit 0
fi

echo "▶ A enviar para o GitHub..."
git add data/processed data/marts
git commit -m "data: update Swissgrid $(date +%F)"
git pull --rebase
git push
echo "✔ Feito. O dashboard atualiza-se em poucos minutos."
