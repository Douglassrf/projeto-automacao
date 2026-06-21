# M06-A Observabilidade — Relatório de Entrega

## Escopo implementado

- Logging estruturado em JSON com `APP_LOG_LEVEL`/`observability_log_level` e propagação de `request_id`/`correlation_id`, `execution_id` e `mission_id` nos logs de observabilidade.
- Métricas em memória para requisições HTTP, com contadores, erros e latência média/máxima por rota.
- Endpoint autenticado `GET /api/v1/observability/metrics` via `Depends(get_current_user)`.
- Snapshot consolidado de readiness em `GET /api/v1/observability/readiness`, autenticado via `Depends(get_current_user)`, cobrindo banco de dados, fila e auditoria imutável.
- Healthcheck público mínimo `GET /health` mantido sem dados sensíveis e reaproveitando o snapshot consolidado para refletir indisponibilidade do banco.
- Testes automatizados cobrindo logging estruturado, autenticação obrigatória nos endpoints novos, métricas e readiness.

## Restrições observadas

- Não foram alterados flags, credenciais, chamadas ou integrações de Meta/Facebook Ads.
- Não foram alterados arquivos ou integrações de TikTok.
- Não houve alteração da camada de autenticação existente; endpoints novos sensíveis usam `Depends(get_current_user)`.
- A lógica existente de observabilidade, auditoria imutável e dashboard foi reaproveitada e expandida no mesmo serviço, sem substituir o fluxo existente.
- Não foram adicionados dados fake/hardcoded como dados reais de negócio.

## Evidências literais de testes

### Testes focados M06-A + regressão de healthcheck

Comando:

```bash
pytest -q src/app/tests/test_m02a_health.py src/app/tests/test_m06a_observability.py
```

Saída:

```text
.....                                                                    [100%]
=============================== warnings summary ===============================
../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
5 passed, 1 warning in 1.35s
```

### Suite completa de regressão

Comando:

```bash
DEFAULT_ADMIN_PASSWORD='SenhaTeste123!' pytest -q
```

Saída:

```text
........................................................................ [ 24%]
........................................................................ [ 49%]
........................................................................ [ 74%]
........................................................................ [ 99%]
.                                                                        [100%]
=============================== warnings summary ===============================
../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:368: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
289 passed, 3 warnings in 9.53s
```

### Checagem de sintaxe dos arquivos alterados

Comando:

```bash
python -m py_compile src/app/main.py src/app/services/observability.py
```

Saída:

```text
```

## Limitações conhecidas

- As métricas são mantidas em memória do processo atual. Em múltiplos workers/processos, cada processo terá seu próprio snapshot até existir um backend compartilhado.
- A suite completa exige `DEFAULT_ADMIN_PASSWORD` configurado para cenários legados de login/admin; por isso a regressão completa foi executada explicitamente com essa variável de ambiente.
- Os avisos de teste são de dependências/ambiente (`StarletteDeprecationWarning` e `InsecureKeyLengthWarning` em teste que força segredo curto) e não bloqueiam a missão.
