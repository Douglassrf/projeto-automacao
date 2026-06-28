# Missão 72 — Predictive Health Monitor

## Objetivo

Monitorar tendências de CPU, memória e armazenamento com alertas preditivos
baseados em histórico e relatório de degradação gradual.

## O que foi entregue

`PredictiveHealthService` reutilizando `DiagnosticsService` (M44) e
`ResourceManagerService` (M45), com histórico curto em `CacheService` (M43).

Campo novo: `predictive_health_enable_predictive_alerts: bool = True`.
`CONFIG_SCHEMA_VERSION` → `2.1.0`.

Rotas:
- `GET /api/v1/predictive-health/monitor/live`
- `GET /api/v1/predictive-health/monitor/markdown`

## Branch

`missao-72-predictive-health-monitor`
