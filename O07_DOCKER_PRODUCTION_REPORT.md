# O07 — DOCKER PRODUCTION REPORT

Data UTC: 2026-06-27.

## Veredito O07

**O07 EXECUTADO_OK VIA GITHUB ACTIONS (CUSTO ZERO).**  
Build Docker, `docker compose up`, smoke test `/api/v1/health` e pytest no container concluídos com **success** na nuvem GitHub.  
Notebook local **sem Docker Desktop** (8 GB RAM) — execução substituída por workflow equivalente ao `verificar_docker_O07.sh`.

## Evidência — run GitHub Actions

| Campo | Valor |
|-------|--------|
| Workflow | O07 Docker Production |
| Run | https://github.com/Douglassrf/projeto-automacao/actions/runs/28293417725 |
| Job | o07-docker (#83829153327) |
| Commit | `3f46a002e83af15a4c1739ee7fe079683f27e490` |
| Branch | master |
| Duração total | 1m 37s |
| Conclusão | **success** |

## Passos (API GitHub — todos success)

| # | Step | Início (UTC) | Fim (UTC) |
|---|------|--------------|-----------|
| 1 | === 1) Versao do Docker === | 15:25:33 | 15:25:33 |
| 2 | === 2) Build da imagem v1.1.0 === | 15:25:33 | 15:26:39 |
| 3 | === 3) Subindo os containers === | 15:26:39 | 15:26:41 |
| 4 | === 4) Aguardando inicializacao (10s) === | 15:26:41 | 15:26:51 |
| 5 | === 5) Smoke test do endpoint de saude === | 15:26:51 | 15:26:51 |
| 6 | === 6) Testes automatizados dentro do container === | 15:26:51 | 15:27:01 |
| 7 | === 7) Status final dos containers === | 15:27:01 | 15:27:01 |

## Saída esperada do script (workflow `.github/workflows/o07-docker.yml`)

```
=== 1) Versão do Docker ===
Docker version …
Docker Compose version …

=== 2) Build da imagem v1.1.0 ===
[docker build -t projeto-automacao:v1.1.0 .]

=== 3) Subindo os containers ===
[docker compose up -d]

=== 4) Aguardando inicialização (10s) ===

=== 5) Smoke test do endpoint de saúde ===
{"ok":true,...}
HEALTH OK

=== 6) Testes automatizados dentro do container ===
[docker compose exec -T api pytest -q]

=== 7) Status final dos containers ===
[docker compose ps]

=== Concluído. Copie os logs deste job para o relatório O07. ===
```

Logs literais completos: abrir o run acima (login GitHub) → job **o07-docker** → expandir cada step.

## Ambiente local (referência)

```text
docker --version
# docker: command not found (Docker Desktop desinstalado — notebook 8 GB RAM)
```

## Artefatos adicionados no repositório

- `.github/workflows/o07-docker.yml` — O07 na nuvem, gratuito
- `verificar_docker_O07.sh` / `.ps1` — para uso futuro se Docker local voltar
- `O07_DOCKER_SEM_NOTEBOOK.md` — guia

## Evidência adicional — Shutdown gracioso + Restart (recertificação O10)

Adicionado em 2026-06-27 por exigência de `ORDEM_RECERTIFICACAO_O10_FINAL.md`: provar que o container aceita `docker compose stop` (SIGTERM, shutdown gracioso, sem erro/crash no log) e que um dado gravado antes do shutdown continua consistente depois do restart.

| Campo | Valor |
|-------|--------|
| Workflow | O07 Docker Production #3 |
| Run | https://github.com/Douglassrf/projeto-automacao/actions/runs/28297813277 |
| Job | o07-docker (#83840692125) |
| Commit | `108f001` |
| Branch | o07-restart-test |
| Duração total | 1m 24s |
| Conclusão | **success** |

Ferramenta de prova: `tools/o07_restart_probe.py` — escreve/lê um marcador direto no SQLite usado pelo container (`/app/data/adintelligence.db`), sem depender de rotas da API. Ferramenta de CI, mesmo escopo do shim `tools/ffmpeg` já existente no repositório — não é funcionalidade nova do produto.

### Passo 7 — Gravando registro antes do shutdown (saída literal)

```
=== 7) Gravando registro antes do shutdown (prova de consistencia O07) ===
WRITE_OK marker=o07-probe-28297813277-1
```

### Passo 8 — Shutdown gracioso (`docker compose stop -t 10 api`) (saída literal)

```
=== 8) Shutdown gracioso (docker compose stop) ===
 Container projeto-automacao-api-1  Stopping
 Container projeto-automacao-api-1  Stopped
--- logs apos stop ---
api-1  | INFO:     Shutting down
api-1  | INFO:     Waiting for application shutdown.
api-1  | INFO:     Application shutdown complete.
api-1  | INFO:     Finished server process [1]
--- status apos stop ---
NAME                      IMAGE                            COMMAND                SERVICE   CREATED          STATUS
projeto-automacao-api-1   projeto-automacao-api:1.1-local "uvicorn app.main:ap…"  api       20 seconds ago   Exited (0) Less than a second ago
SHUTDOWN GRACIOSO OK (sem traceback nos logs)
```

### Passo 9 — Restart dos containers (saída literal)

```
=== 9) Restart dos containers ===
 Container projeto-automacao-api-1  Recreate
 Container projeto-automacao-api-1  Recreated
 Container projeto-automacao-api-1  Starting
 Container projeto-automacao-api-1  Started
{"status":"ok","scope":"api","loaded_routes":43,"failed_routes":0}
HEALTH OK APOS RESTART
```

### Passo 10 — Verificando consistência do dado após restart (saída literal)

```
=== 10) Verificando consistencia do dado apos restart ===
READ_OK id=1 marker=o07-probe-28297813277-1 created_at=2026-06-27 18:23:13
```

**Conclusão:** o marcador gravado no passo 7 (`o07-probe-28297813277-1`) foi lido de volta com sucesso no passo 10, após shutdown gracioso (sem traceback nos logs, `Exited (0)`) e restart completo do container (`HEALTH OK APOS RESTART`). O dado sobrevive ao ciclo stop/restart porque persiste no volume nomeado `projeto_automacao_data`, montado fora do ciclo de vida do container.

## Pendência

Nenhuma para O07 técnico — incluindo o teste de shutdown gracioso + restart, agora coberto com evidência literal acima. Homologação final v1.1 depende apenas de O10 (branch protection, ação exclusiva do Douglas) conforme `ORDEM_RECERTIFICACAO_O10_FINAL.md`.
