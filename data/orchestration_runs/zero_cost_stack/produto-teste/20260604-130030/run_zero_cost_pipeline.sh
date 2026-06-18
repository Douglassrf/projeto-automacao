#!/usr/bin/env bash
set -euo pipefail

PIPELINE_JSON="${1:-pipeline_master.json}"
API_BASE="${API_BASE:-http://localhost:8000/api/v1}"
N8N_WEBHOOK_URL="${N8N_WEBHOOK_URL:-}"

echo "[AdIntelligence] Validando pipeline: ${PIPELINE_JSON}"
test -f "$PIPELINE_JSON"

if [ -n "$N8N_WEBHOOK_URL" ]; then
  echo "[AdIntelligence] Enviando para n8n..."
  curl -sS -X POST "$N8N_WEBHOOK_URL" -H "Content-Type: application/json" --data-binary "@${PIPELINE_JSON}"
else
  echo "[AdIntelligence] N8N_WEBHOOK_URL vazio. Rodando em modo local/dry-run."
fi

echo "[AdIntelligence] Pipeline finalizado em modo seguro."
