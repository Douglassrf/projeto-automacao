#!/usr/bin/env bash
# Verificação O07 — build + smoke test Docker — Projeto Automação v1.1.0
# Rode este script no seu terminal, dentro da pasta clonada do repositório
# (onde está o Dockerfile / docker-compose.yml), com Docker Desktop aberto.
#
# Uso:
#   cd /caminho/para/projeto-automacao
#   bash verificar_docker_O07.sh
#
# Cole a saída completa no relatório O07 como evidência literal.

set -e

echo "=== 1) Versão do Docker ==="
docker --version
docker compose version

echo ""
echo "=== 2) Build da imagem v1.1.0 ==="
docker build -t projeto-automacao:v1.1.0 .

echo ""
echo "=== 3) Subindo os containers ==="
docker compose up -d

echo ""
echo "=== 4) Aguardando inicialização (10s) ==="
sleep 10

echo ""
echo "=== 5) Smoke test do endpoint de saúde ==="
curl -fsS http://localhost:8000/api/v1/health && echo "" && echo "HEALTH OK"

echo ""
echo "=== 6) Testes automatizados dentro do container ==="
docker compose exec -T api pytest -q || true

echo ""
echo "=== 7) Status final dos containers ==="
docker compose ps

echo ""
echo "=== Concluído. Copie toda a saída acima para o relatório O07. ==="
