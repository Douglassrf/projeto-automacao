# M04-A — Mission Orchestrator Report

## Escopo entregue

Implementado o Mission Orchestrator v1.1 Fase 1 com 6 módulos somente leitura/seguros:

1. **Mission Planner** — endpoint `GET /api/v1/mission-orchestrator/planner`, monta a sequência pesquisa/mineração → estratégia/inteligência → criativos → site → publicação → monitoramento usando evidências do banco existente.
2. **Mission Timeline** — endpoint `GET /api/v1/mission-orchestrator/timeline/{mission_id}`, expõe eventos de campanha, métricas e tickets já persistidos.
3. **Mission Memory** — endpoint `GET /api/v1/mission-orchestrator/memory`, lista histórico de missões a partir de campanhas existentes.
4. **Mission Recovery** — endpoint `GET /api/v1/mission-orchestrator/recovery/{mission_id}`, retorna último estado salvo, estados concluídos e próxima etapa sem reprocessar etapas e sem execução real.
5. **Mission Score** — endpoint `GET /api/v1/mission-orchestrator/score`, calcula saúde da missão a partir de métricas, filas e tickets existentes.
6. **Mission Dashboard** — endpoint `GET /api/v1/mission-orchestrator/dashboard/ui`, entrega visão consolidada com tema escuro e grid `sidebar/content/rightbar`.

## Restrições atendidas

- Todas as rotas novas usam `Depends(get_current_user)` e ficam sob `/api/v1`.
- Nenhuma rota pública foi criada.
- Nenhuma integração externa nova foi adicionada.
- Nenhuma chamada de publicação real foi adicionada.
- Nenhum armazenamento novo de credenciais ou dado sensível foi criado.
- O Mission Recovery declara explicitamente `will_execute_real_action: false` e usa política de retomada segura.
- Dados de negócio vêm de tabelas/modelos existentes (`Campaign`, `CampaignMetric`, `PerformanceTicket`, `QueueJob`, `ContentWorkflow`, `DecisionLog`).
- A UI consolidada reaproveita o padrão visual aprovado em M03-A: tema escuro com grid `sidebar`, `content`, `rightbar`.

## Arquivos alterados

- `src/app/core/mission_orchestrator.py`
- `src/app/api/routes/mission_orchestrator.py`
- `src/app/api/safe_router.py`
- `src/app/tests/test_mission_orchestrator.py`
- `M04A_MISSION_ORCHESTRATOR_REPORT.md`

## Evidência literal de testes

### Teste focado do Mission Orchestrator

Comando:

```bash
DEFAULT_ADMIN_PASSWORD=admin123 pytest -q src/app/tests/test_mission_orchestrator.py
```

Saída:

```text
.......                                                                  [100%]
=============================== warnings summary ===============================
../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
7 passed, 1 warning in 1.88s
```

### Suíte completa de regressão sem variável de ambiente obrigatória

Comando:

```bash
pytest -q
```

Saída resumida relevante:

```text
16 failed, 277 passed, 3 warnings in 12.43s
```

Limitação observada: a suíte completa exige `DEFAULT_ADMIN_PASSWORD` configurado para testes de autenticação legados. Sem essa variável, `init_db()` bloqueia corretamente por segurança com a mensagem `DEFAULT_ADMIN_PASSWORD nao configurado`.

### Suíte completa de regressão com variável de ambiente obrigatória

Comando:

```bash
DEFAULT_ADMIN_PASSWORD=admin123 pytest -q
```

Saída:

```text
........................................................................ [ 24%]
........................................................................ [ 49%]
........................................................................ [ 73%]
........................................................................ [ 98%]
.....                                                                    [100%]
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
293 passed, 3 warnings in 13.43s
```

## Limitações conhecidas

- A Fase 1 é intencionalmente somente leitura e orquestra estados/evidências existentes; não cria executor assíncrono nem armazenamento novo de missões.
- A etapa de publicação permanece apenas como gate manual, sem disparo automático.
- Timeline e Recovery dependem de dados já persistidos; missões sem campanha correspondente retornam timeline vazia e recovery sem último estado salvo.
- A suíte completa precisa de `DEFAULT_ADMIN_PASSWORD` no ambiente para passar os testes de autenticação existentes.
