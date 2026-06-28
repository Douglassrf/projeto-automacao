# Missão 71 — Operational Intelligence Hub

## Objetivo

Entregar um painel unificado de inteligência operacional que consolida, em uma
única chamada, métricas de estabilidade, desempenho e risco já calculadas pelos
módulos existentes (diagnósticos, alertas, cache, fila, recursos, recuperação,
auditoria de dependências e certificação) — sem duplicar a lógica de nenhum
deles e sem chamadas de rede/API paga.

## Justificativa real

Após a Missão 50, o repositório tinha um veredito Platinum (`/certification/
platinum/*`) e dezenas de endpoints operacionais isolados, mas nenhum painel
único que respondesse "como está o projeto agora?" com quatro eixos claros:
estabilidade, desempenho, risco e estado global. `OperationalIntelligenceService`
resolve isso compondo os serviços já existentes (reuso, não reimplementação).

## O que foi entregue

`OperationalIntelligenceService` (`src/app/services/operational_intelligence_service.py`),
reutilizando diretamente:

- `DiagnosticsService.run_full_diagnostics()` (M44)
- `AlertService.active_alerts()` (M46 — somente leitura)
- `CacheService.stats()` (M43)
- `QueueService.health_report()` (M42)
- `ResourceManagerService.disk_usage_report()` (M45)
- `RecoveryService.recovery_report()` (M47)
- `DependencyAuditService.audit()` (M49)
- `CertificationService.certify()` (M50)

Quatro eixos do painel:

1. **`global_project_state`** — `overall_status` (`healthy`/`degraded`/`critical`),
   `platinum_certified`, saúde por módulo (8 módulos rastreados).
2. **`stability`** — diagnósticos, alertas ativos, fila e recuperação.
3. **`performance`** — cache hit-rate, fila por queue, disco gerenciado.
4. **`risk_indicators`** — dependências, config, bloqueios da certificação.

Campo novo em `Settings` (`src/app/core/config.py`):
`operational_intelligence_include_unpinned_in_risk: bool = True`.

Nova regra em `validate_settings()` (perfil produção): rejeita
`operational_intelligence_include_unpinned_in_risk=False` em produção.
`CONFIG_SCHEMA_VERSION` sobe de `1.9.0` para `2.0.0`.

Duas rotas novas em `/operational-intelligence` (`safe_router.py` registra o
módulo imediatamente após `"certification"`):

- `GET /api/v1/operational-intelligence/health-panel/live` — painel completo em JSON.
- `GET /api/v1/operational-intelligence/health-panel/markdown` — o mesmo painel em Markdown.

### Arquivos novos

| Arquivo | Conteúdo |
|---|---|
| `src/app/services/operational_intelligence_service.py` | `OperationalIntelligenceService` |
| `src/app/schemas/operational_intelligence.py` | schemas Pydantic do painel |
| `src/app/api/routes/operational_intelligence.py` | rotas `/health-panel/live` e `/markdown` |
| `src/app/tests/test_m71_operational_intelligence_hub.py` | 23 testes novos |

### Arquivos modificados

| Arquivo | Alteração |
|---|---|
| `src/app/core/config.py` | campo `operational_intelligence_include_unpinned_in_risk` |
| `src/app/core/config_profiles.py` | `CONFIG_SCHEMA_VERSION` → `2.0.0`, regra produção |
| `src/app/api/safe_router.py` | módulo `operational_intelligence` |
| `CONFIG_CHANGELOG.md` | entrada `2.0.0` |

## Evidência de testes

```text
$ DATABASE_URL=sqlite:///./.pytest_m71_temp.db python -m pytest src/app/tests/test_m71_operational_intelligence_hub.py -q
.......................
23 passed in 8.76s
```

Nota: o `adintelligence.db` local estava corrompido (`database disk image is malformed`);
os testes M71 foram executados com banco temporário isolado conforme acima.

## Branch

`missao-71-operational-intelligence-hub`

## Escopo respeitado

- Uma visão unificada do estado global do sistema.
- Nenhuma funcionalidade nova fora do painel operacional.
- Nenhuma alteração em módulos M41–M50 além de config/router.
