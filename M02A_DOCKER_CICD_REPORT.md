# M02-A — Dockerização + CI/CD cloud-agnostic

## Status

**PARCIALMENTE HOMOLOGADO COM LIMITAÇÃO DE AMBIENTE**.

A implementação de código, Dockerfile, docker-compose, CI e health check real foi concluída e validada localmente onde havia runtime Python. A validação Docker (`docker build` / `docker compose up`) não pôde ser executada neste sandbox porque o binário `docker` não está instalado (`command not found`).

## Escopo entregue

- `Dockerfile` multi-stage para a API, com stage `builder` para wheels e stage `runtime` não-root, incluindo `ffmpeg` e `libmagic1` para a suíte de mídia/upload.
- `docker-compose.yml` para stage local, sem cloud específica.
- `.dockerignore` excluindo `.env`, bancos locais, ZIPs, logs, caches e `__pycache__`.
- GitHub Actions em `.github/workflows/ci.yml` com dependências de sistema (`ffmpeg`, `libmagic1`), lint de sintaxe (`python -m compileall -q src`) e suíte pytest completa a cada PR/push em `master`/`main`.
- `/health` real verificando acesso ao banco com `SELECT 1`; retorna `200` quando DB está acessível e `503` quando DB está indisponível.
- Testes automatizados para `/health` saudável e indisponível.

## Regras de segurança mantidas

- Nenhum `.env` real foi lido, editado ou versionado.
- Nenhuma flag real `AUTH_REQUIRED`, `META_DRY_RUN`, `META_AUTOPUBLISH`, `META_ALLOW_ACTIVE_LAUNCH` ou `META_ALLOW_PRODUCTION_REAL` foi alterada em ambiente real.
- Não houve chamada real à Meta.
- Nenhum segredo real foi persistido em texto puro.
- O `docker-compose.yml` usa apenas valores seguros/de teste explícitos para ambiente local, incluindo `DEFAULT_ADMIN_PASSWORD=test-only-admin-password`.

## Evidência real — lint local

Comando executado:

```bash
python -m compileall -q src
```

Resultado observado: comando finalizou com exit code `0` antes da execução dos testes.

## Evidência real — testes do health check

Comando executado:

```bash
DEFAULT_ADMIN_PASSWORD='test-only-admin-password' pytest src/app/tests/test_m02a_health.py -q
```

Saída final observada:

```text
..                                                                       [100%]
=============================== warnings summary ===============================
../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2 passed, 1 warning in 2.24s
```

## Evidência real — suíte pytest completa

Comando executado:

```bash
DEFAULT_ADMIN_PASSWORD='test-only-admin-password' pytest
```

Saída final observada:

```text
collected 271 items
...
src/app/tests/test_m02a_health.py ..                                     [ 45%]
...
src/app/tests/test_ugc_processing.py ...                                 [ 92%]
src/app/tests/test_video_pipeline.py ..                                  [ 94%]
...
======================= 271 passed, 3 warnings in 13.19s =======================
```

Warnings observados:

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256.
InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256.
```

## Evidência real — falha proposital de CI/teste

Para provar que um erro proposital derruba o job de teste, foi criado um teste temporário fora do repositório em `/tmp/test_m02a_intentional_failure.py`, executado e removido em seguida.

Comando executado:

```bash
pytest /tmp/test_m02a_intentional_failure.py -q
```

Saída observada:

```text
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_m02a_ci_intentional_failure_probe ____________________

    def test_m02a_ci_intentional_failure_probe():
>       assert False, "intentional CI failure probe"
E       AssertionError: intentional CI failure probe
E       assert False

/tmp/test_m02a_intentional_failure.py:2: AssertionError
=========================== short test summary info ============================
FAILED ../../tmp/test_m02a_intentional_failure.py::test_m02a_ci_intentional_failure_probe
1 failed in 0.03s
intentional_failure_exit_code=1
```

Conclusão: a etapa `pytest` usada no CI falha com exit code `1` quando há teste quebrado.

## Evidência real — Docker indisponível no sandbox

Comandos executados:

```bash
docker --version
docker compose version
```

Saída observada:

```text
/bin/bash: line 7: docker: command not found
docker_exit=127
/bin/bash: line 8: docker: command not found
docker_compose_exit=127
```

Conclusão: `docker build` e `docker compose up` não foram executados por limitação do ambiente, não por falha detectada nos arquivos Docker.

## Arquivos criados/alterados

- `Dockerfile`: multi-stage builder/runtime, usuário não-root, dependências `ffmpeg`/`libmagic1`, healthcheck HTTP local e comando `uvicorn`.
- `docker-compose.yml`: stage local cloud-agnostic com volumes nomeados para dados/logs e flags seguras de teste.
- `.dockerignore`: exclusões para segredos, bancos, logs, caches, ZIPs e bytecode.
- `.github/workflows/ci.yml`: pipeline com checkout, Python 3.12, instalação de `ffmpeg`/`libmagic1`, dependências Python, lint de sintaxe e pytest.
- `src/app/main.py`: `/health` passou a validar DB com `SELECT 1` e responder `503` em erro de banco.
- `src/app/tests/test_m02a_health.py`: testes do health check `200` e `503`.

## Conclusão

M02-A está implementada no código e validada por lint, testes unitários do health check, suíte completa e prova de falha proposital do pytest. A única pendência é operacional: o sandbox atual não possui Docker instalado, então `docker build` e `docker compose up` precisam ser executados por Douglas/Claude em ambiente com Docker antes da homologação final desta missão.
