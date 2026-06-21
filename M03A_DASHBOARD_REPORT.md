# Relatório M03-A — Dashboard operacional — v1.1 Fase 1

## O que foi feito

- Criado dashboard operacional somente leitura em `GET /api/v1/dashboard/operational`.
- Consolidada a interface visual somente leitura em `GET /api/v1/dashboard/operational/ui` com a imagem oficial confirmada por Douglas: tema escuro, grid sidebar/conteúdo/rightbar, sidebar fixa, topo com saudação, ações rápidas, fluxo "Como funciona?", painéis laterais, visão geral e ferramentas rápidas.
- Adicionado agregador executivo com visão única de:
  - status de segurança e políticas de execução real;
  - estado de dry-run/real-mode, autenticação obrigatória e confirmação manual;
  - filas e contagem por status;
  - auditoria/observabilidade e integridade do audit log imutável;
  - saúde/readiness dos conectores sem rede, sem credenciais e sem escrita;
  - campanhas, tickets, alertas, bloqueios ativos e aprovações humanas pendentes.
- A rota nova usa `Depends(get_current_user)` e foi validada com `AUTH_REQUIRED=true` exigindo token.
- Não foram criados endpoints novos de escrita/ação.
- Não foram alteradas/removidas rotas, guards ou fluxos existentes.

## Arquivos alterados

- `src/app/core/operational_dashboard.py`
- `src/app/api/routes/dashboard.py`
- `src/app/api/safe_router.py`
- `src/app/tests/test_operational_dashboard.py`
- `M03A_DASHBOARD_REPORT.md`

## Comandos executados e evidência real

### Testes automatizados específicos do dashboard

Comando:

```bash
cd src && pytest -q app/tests/test_operational_dashboard.py
```

Saída literal:

```text
...                                                                      [100%]
=============================== warnings summary ===============================
../../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
3 passed, 1 warning in 2.09s
```

### Suíte completa de regressão

Comando:

```bash
cd src && DEFAULT_ADMIN_PASSWORD='dashboard-test-password' pytest -q
```

Saída literal:

```text
........................................................................ [ 24%]
........................................................................ [ 49%]
........................................................................ [ 74%]
........................................................................ [ 99%]
.                                                                        [100%]
=============================== warnings summary ===============================
../../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(

app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:368: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
289 passed, 3 warnings in 13.28s
```

### Checagem de screenshot

Comando:

```bash
which chromium || which chromium-browser || which google-chrome || true
```

Saída literal:

```text

```

Resultado: não havia navegador/headless browser instalado no container para capturar screenshot local. A conferência visual final foi feita contra a especificação da imagem oficial confirmada por Douglas.

## Limitações conhecidas

- A suíte completa precisa de `DEFAULT_ADMIN_PASSWORD` configurado para os testes legados que fazem login real. Foi usado um valor local de teste no comando, sem segredo real.
- Há warnings existentes de ambiente/dependência (`StarletteDeprecationWarning`) e de chave HMAC curta em teste de hardening. Nenhum warning bloqueou a regressão.
- O dashboard é intencionalmente somente leitura/readiness-only: não ativa conectores, não carrega credenciais, não usa rede e não executa ações reais.
- Ajuste visual considerado fechado nesta entrega com base na imagem oficial confirmada por Douglas e na especificação visual consolidada.
