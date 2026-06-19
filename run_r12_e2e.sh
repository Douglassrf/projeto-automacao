#!/usr/bin/env bash
# Missao R12 - Teste do fluxo completo (raiz a raiz), backend real.
#
# Seguranca:
# - Banco SQLite ISOLADO (/tmp/test_adintelligence_r12.db) - nunca toca o banco de producao.
# - UPLOAD_DIR isolado (/tmp/r12_uploads) - nunca toca diretorio real de upload.
# - Usa o .env REAL do projeto para tudo o mais (JWT secret real, credencial real do
#   admin, flags Meta reais) - NUNCA sobrescreve META_DRY_RUN/META_AUTOPUBLISH/
#   META_ALLOW_ACTIVE_LAUNCH/META_ALLOW_PRODUCTION_REAL/AUTH_REQUIRED.
# - O unico endpoint Meta chamado e /api/v1/campaign/dry-run, que FORCA mode="dry_run"
#   por construcao de codigo - nao publica nada, nao gasta dinheiro, nao faz nenhuma
#   chamada de rede real ao Meta.
# - Nenhum valor de segredo e impresso; apenas presenca/ausencia e resultados HTTP.
set -uo pipefail

PROJECT_ROOT="/sessions/modest-zealous-noether/mnt/projeto_automacao"
cd "$PROJECT_ROOT" || exit 1

PORT=8021
BASE="http://127.0.0.1:${PORT}"
DB_FILE="/tmp/test_adintelligence_r12.db"
UPLOAD_DIR_PATH="/tmp/r12_uploads"
LOG_FILE="/tmp/r12_uvicorn.log"
OUT_DIR="/tmp/r12_steps"

rm -f "$DB_FILE"
rm -rf "$UPLOAD_DIR_PATH" "$OUT_DIR"
mkdir -p "$UPLOAD_DIR_PATH" "$OUT_DIR"

export DATABASE_URL="sqlite:///${DB_FILE}"
export UPLOAD_DIR="$UPLOAD_DIR_PATH"

echo "=== R12: inicializando schema + admin no banco isolado (init_db real) ==="
PYTHONPATH=src python3 -c "from app.db.init_db import init_db; init_db(); print('init_db() OK - tabelas criadas e admin seedado no banco isolado')"
INIT_EXIT=$?
if [ "$INIT_EXIT" != "0" ]; then
  echo "FALHA: init_db() falhou (exit=${INIT_EXIT}). Abortando."
  exit 1
fi
echo ""

echo "=== R12: subindo backend real (uvicorn) com banco isolado ==="
PYTHONPATH=src python3 -m uvicorn app.main:app --host 127.0.0.1 --port ${PORT} --app-dir src > "$LOG_FILE" 2>&1 &
UVICORN_PID=$!
echo "uvicorn PID=${UVICORN_PID}"

READY=0
for i in $(seq 1 60); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/health" 2>/dev/null)
  if [ "$CODE" = "200" ]; then
    READY=1
    break
  fi
  sleep 0.3
done

if [ "$READY" != "1" ]; then
  echo "FALHA: backend nao respondeu /health a tempo. Log:"
  cat "$LOG_FILE"
  kill "$UVICORN_PID" 2>/dev/null
  exit 1
fi
echo "Backend pronto. /health = 200"
echo ""

print_body() {
  local outfile="$1"
  python3 - "$outfile" <<'PYEOF'
import json, sys
path = sys.argv[1]
try:
    d = json.load(open(path))
    print(json.dumps(d, ensure_ascii=False, indent=2)[:1500])
except Exception as e:
    print("(corpo nao-JSON ou vazio)", e)
PYEOF
}

step() {
  local name="$1" method="$2" path="$3" data="$4"
  local outfile="${OUT_DIR}/${name}.json"
  local code
  if [ -n "$data" ]; then
    code=$(curl -s -o "$outfile" -w "%{http_code}" -X "$method" "${BASE}${path}" \
      -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" -d "$data")
  else
    code=$(curl -s -o "$outfile" -w "%{http_code}" -X "$method" "${BASE}${path}" \
      -H "Authorization: Bearer ${TOKEN}")
  fi
  echo "### ${name} -> ${method} ${path} => HTTP ${code}"
  print_body "$outfile"
  echo ""
}

echo "=== 1) AUTH - login real com credencial do .env (valor nunca impresso) ==="
ADMIN_EMAIL=$(PYTHONPATH=src python3 -c "from app.core.config import get_settings; print(get_settings().default_admin_email)")
LOGIN_PAYLOAD=$(PYTHONPATH=src python3 -c "import json; from app.core.config import get_settings; s=get_settings(); print(json.dumps({'email': s.default_admin_email, 'password': s.default_admin_password}))")
LOGIN_CODE=$(curl -s -o "${OUT_DIR}/login.json" -w "%{http_code}" -X POST "${BASE}/api/v1/auth/login" -H "Content-Type: application/json" -d "$LOGIN_PAYLOAD")
echo "POST /api/v1/auth/login => HTTP ${LOGIN_CODE} (email=${ADMIN_EMAIL}, senha NAO impressa)"
TOKEN=$(python3 - "${OUT_DIR}/login.json" <<'PYEOF'
import json, sys
try:
    print(json.load(open(sys.argv[1])).get("access_token", ""))
except Exception:
    print("")
PYEOF
)
if [ -z "$TOKEN" ]; then
  echo "FALHA CRITICA: nao obteve token real. Corpo da resposta de login:"
  cat "${OUT_DIR}/login.json"
  echo ""
  echo "Ultimas linhas do log do uvicorn:"
  tail -40 "$LOG_FILE"
  kill "$UVICORN_PID" 2>/dev/null
  exit 1
fi
echo "Token JWT real obtido (tamanho=${#TOKEN} chars, valor nao impresso)."
echo ""

step "02_auth_me" "GET" "/api/v1/auth/me" ""

echo "### 03_upload (multipart) -> POST /api/v1/upload"
python3 -c "
import base64
png_b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
with open('/tmp/r12_upload_sample.png', 'wb') as f:
    f.write(base64.b64decode(png_b64))
"
UPLOAD_CODE=$(curl -s -o "${OUT_DIR}/03_upload.json" -w "%{http_code}" -X POST "${BASE}/api/v1/upload" \
  -H "Authorization: Bearer ${TOKEN}" -F "file=@/tmp/r12_upload_sample.png;type=image/png")
echo "HTTP ${UPLOAD_CODE}"
print_body "${OUT_DIR}/03_upload.json"
echo ""

step "04_miner_controlled_real" "POST" "/api/v1/miner/controlled-real" \
'{"product_name":"Ebook E2E R12","niche":"emagrecimento","source_label":"r12_e2e_local_test","max_ads":5,"allow_external_call":false,"ads":[{"source_ad_id":"r12-ad-1","hook":"Pare de adiar sua rotina fitness","creative_pattern":"depoimento_curto","copy_pattern":"promessa_moderada","connect_rate":82,"roas":1.8}]}'

step "05_brain_review" "POST" "/api/v1/brain/review" \
'{"product_name":"Ebook E2E R12","niche":"emagrecimento","campaign_stage":"V3","budget_brl":25,"metrics":{"connect_rate":82,"checkout_rate":25.61,"purchase_rate":3.41},"copy":"Receitas e rotina fitness sem promessas milagrosas."}'

step "06_site_builder_safe_generate" "POST" "/api/v1/site-builder-safe/generate" \
'{"offer":{"product_name":"Ebook E2E R12","niche":"emagrecimento","headline":"Organize sua rotina fitness em 7 dias","subheadline":"Metodo pratico sem promessas milagrosas para iniciantes","benefits":["Receitas simples","Rotina flexivel","Sem equipamento caro"],"pain_points":["Falta de tempo","Dificuldade de manter consistencia"],"checkout_url":"https://example.com/checkout-r12"},"template":"direct_response","deploy":{"provider":"local","dry_run":true}}'

step "07_war_kit_generate" "POST" "/api/v1/war-kit/generate" \
'{"product":{"product_name":"Ebook E2E R12","niche":"emagrecimento","offer_promise":"Organize sua rotina fitness em 7 dias","target_avatar":"Mulheres 25-45 anos buscando rotina pratica e sustentavel","main_pain":"Falta de tempo e consistencia para manter habitos saudaveis","desired_transformation":"Sentir-se organizada e no controle da propria rotina","ticket_price":47,"pixel_id":"r12_pixel_test","landing_page_url":"https://example.com/lp-r12","checkout_url":"https://example.com/checkout-r12"},"mined_ads":[{"source_ad_id":"r12-ad-1","hook":"Pare de adiar sua rotina fitness","creative_pattern":"depoimento_curto","copy_pattern":"promessa_moderada","connect_rate":82,"roas":1.8}],"generate_pdf":true,"generate_images":true,"generate_videos":false,"generate_copies":true,"push_to_storage":false,"prepare_meta_upload":true,"dry_run_meta":true,"render_video_assets":false}'

step "08_video_pipeline_safe_render" "POST" "/api/v1/video-pipeline-safe/render" \
'{"product_name":"Ebook E2E R12","model":"V1","hook":"Pare de adiar sua rotina fitness","script":"Roteiro sintetico de teste R12 para validar a cadeia completa do pipeline de video sem chamadas externas reais.","cta":"Acesse agora","language":"pt-BR","aspect_ratio":"9:16","voice_provider":"fallback","scene_provider":"ffmpeg_local"}'

echo "=== 9) Agency Operator (TikTok) - create -> approve -> schedule -> publish ==="
CREATE_PAYLOAD='{"title":"Post TikTok E2E R12","brief":"Rotina fitness pratica sem promessas milagrosas. Teste E2E R12.","platform":"TikTok","content_type":"reels","requires_approval":true}'
CREATE_CODE=$(curl -s -o "${OUT_DIR}/09a_workflow_create.json" -w "%{http_code}" -X POST "${BASE}/api/v1/agency-operator/workflows" \
  -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" -d "$CREATE_PAYLOAD")
echo "POST /workflows => HTTP ${CREATE_CODE}"
print_body "${OUT_DIR}/09a_workflow_create.json"
WF_ID=$(python3 - "${OUT_DIR}/09a_workflow_create.json" <<'PYEOF'
import json, sys
try:
    print(json.load(open(sys.argv[1])).get("id", ""))
except Exception:
    print("")
PYEOF
)
echo "workflow_id=${WF_ID}"
echo ""

for ACTION in approve schedule publish; do
  CODE=$(curl -s -o "${OUT_DIR}/09_${ACTION}.json" -w "%{http_code}" -X POST "${BASE}/api/v1/agency-operator/workflows/${WF_ID}/${ACTION}" \
    -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" -d '{"notes":"R12 e2e"}')
  echo "POST /workflows/${WF_ID}/${ACTION} => HTTP ${CODE}"
  print_body "${OUT_DIR}/09_${ACTION}.json"
  echo ""
done

step "10_campaign_dry_run" "POST" "/api/v1/campaign/dry-run" \
'{"product_name":"Ebook E2E R12","niche":"emagrecimento","campaign_stage":"V3","budget_brl":25,"metrics":{"connect_rate":82,"checkout_rate":25.61,"purchase_rate":3.41},"copy":"Receitas e rotina fitness sem promessas milagrosas.","pixel_id":"r12_pixel_test","landing_page_url":"https://example.com/lp-r12"}'

echo "=== 11) Confirmacao direta no banco isolado (sem passar por HTTP) ==="
python3 - "$DB_FILE" <<'PYEOF'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
cur = con.cursor()
cur.execute("SELECT id, name, email FROM users")
print("users:", cur.fetchall())
cur.execute("SELECT id, workflow_key, platform, status FROM content_workflows ORDER BY id")
print("content_workflows:", cur.fetchall())
con.close()
PYEOF
echo ""

echo "=== 12) Encerrando backend ==="
kill "$UVICORN_PID" 2>/dev/null
wait "$UVICORN_PID" 2>/dev/null
echo "uvicorn finalizado."
echo ""
echo "=== R12 concluido. Banco isolado usado: ${DB_FILE} (nao e o banco de producao). ==="
