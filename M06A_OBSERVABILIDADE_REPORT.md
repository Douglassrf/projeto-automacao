# M06-A Observabilidade — Relatório de Entrega

## Escopo implementado

- Logging estruturado em JSON com `APP_LOG_LEVEL`/`observability_log_level` e propagação de `request_id`/`correlation_id`, `execution_id` e `mission_id` nos logs de observabilidade.
- Métricas em memória para requisições HTTP, com contadores, erros e latência média/máxima por rota.
- Endpoint autenticado `GET /api/v1/observability/metrics` via `Depends(get_current_user)`.
- Snapshot consolidado de readiness em `GET /api/v1/observability/readiness`, autenticado via `Depends(get_current_user)`, cobrindo banco de dados, fila e auditoria imutável.
- Healthcheck público mínimo `GET /health` mantido sem dados sensíveis e reaproveitando o snapshot consolidado para refletir indisponibilidade do banco.
- Testes automatizados cobrindo logging estruturado, autenticação obrigatória nos endpoints novos, métricas e readiness.
