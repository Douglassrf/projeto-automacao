# Verificacao O07 — Windows PowerShell — Projeto Automacao v1.1.0
# Uso: cd $env:USERPROFILE\Documents\projeto-automacao
#      powershell -ExecutionPolicy Bypass -File .\verificar_docker_O07.ps1

$ErrorActionPreference = "Continue"

Write-Host "=== 1) Versao do Docker ==="
try {
    docker --version
    docker compose version
} catch {
    Write-Host "ERRO: docker nao encontrado no PATH. Abra Docker Desktop (Engine running)."
    exit 1
}

Write-Host ""
Write-Host "=== 2) Build da imagem v1.1.0 ==="
docker build -t projeto-automacao:v1.1.0 .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "=== 3) Subindo os containers ==="
docker compose up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "=== 4) Aguardando inicializacao (10s) ==="
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "=== 5) Smoke test do endpoint de saude ==="
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -UseBasicParsing -TimeoutSec 30
    Write-Host $r.Content
    Write-Host "HEALTH OK"
} catch {
    Write-Host "ERRO health: $_"
}

Write-Host ""
Write-Host "=== 6) Testes automatizados dentro do container ==="
docker compose exec -T api pytest -q

Write-Host ""
Write-Host "=== 7) Status final dos containers ==="
docker compose ps

Write-Host ""
Write-Host "=== Concluido. Copie toda a saida acima para o relatorio O07. ==="
