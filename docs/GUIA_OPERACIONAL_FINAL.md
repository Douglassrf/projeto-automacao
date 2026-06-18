# Guia Operacional Final

Data: 2026-06-05

## Estado

Projeto homologado em modo seguro de ponta a ponta.

Resultado atual:

`261 passed`

## Regra Principal

Manter operacao em modo economico e seguro:

- chat apenas para decisoes curtas, status e bloqueios;
- memoria longa em `docs/` e `logs/`;
- patches pequenos;
- teste especifico antes da suite completa;
- nunca expor `.env`, token ou segredo;
- nunca ativar gasto sem autorizacao especifica.
- trocar `DEFAULT_ADMIN_PASSWORD` no `.env` antes de qualquer uso fora do laptop local.

## Meta

Campanha Codex:

`52616252576068`

Estado:

`PAUSED`

Campanhas antigas:

`PAUSED`

A exclusao das antigas saiu do fluxo principal porque a Meta retornou bloqueio externo `OAuthException 31 / 3858385`.

## Como Validar

Na raiz do projeto:

```bash
python -m pytest -p no:cacheprovider --basetemp .pytest_tmp
```

Resultado esperado:

```txt
261 passed
```

Validar o ZIP final:

```bat
VERIFICAR_PACOTE_FINAL.bat
```

## Proximo Nivel Real

Somente prosseguir para escrita real na Meta quando:

- a Meta liberar criacao/modificacao pela API;
- o usuario autorizar valor e objetivo;
- a campanha continuar `PAUSED`;
- `META_REQUIRE_MANUAL_CONFIRMATION=true`;
- `META_ALLOW_ACTIVE_LAUNCH=false`.

Frase minima para continuar campanha pausada:

```txt
Autorizo continuar a campanha PAUSADA com orçamento de R$ 6 por dia, sem ativar gasto.
```

## Arquivos Chave

- `docs/PROXIMOS_PASSOS.md`
- `docs/MODO_ECONOMICO_SEGURO.md`
- `docs/SECURITY_HARDENING_LAYER.md`
- `docs/SEGURANCA_TOKEN_META.md`
- `docs/ROTINA_OPERACIONAL_DIARIA.md`
- `docs/CHECKLIST_CONCLUSAO_PROJETO.md`
- `docs/RELATORIO_ENTREGA_FINAL.md`
- `docs/PROMPT_CONTINUACAO_OUTRO_AGENTE.md`
- `docs/AUDITORIA_OPERACIONAL_FINAL.md`
- `docs/MISSOES_CONCLUSAO_FINAL.md`
- `docs/TERMO_CONCLUSAO_PROJETO.md`
- `docs/historico_missoes/RELATORIO_HOMOLOGACAO_FINAL_SEGURA.md`
- `docs/historico_missoes/RELATORIO_ACAO_REAL_META_PAUSADA.md`
- `docs/historico_missoes/RELATORIO_POS_CONCLUSAO_HARDENING_SITEBUILDER.md`
- `docs/historico_missoes/RELATORIO_POS_CONCLUSAO_VERIFICADOR_PACOTE.md`
- `docs/historico_missoes/RELATORIO_POS_CONCLUSAO_GITIGNORE_SEGURO.md`
- `docs/historico_missoes/RELATORIO_MISSAO35A_SECURITY_SPEC_OFICIAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO35B_RBAC_SERVICE_ACCOUNTS.md`
- `docs/historico_missoes/RELATORIO_MISSAO35C_COMMAND_VALIDATOR.md`
- `docs/historico_missoes/RELATORIO_MISSAO35D_ZERO_TRUST_INTERNAL_CALLS.md`
- `docs/historico_missoes/RELATORIO_MISSAO35E_AUDIT_LOG_IMUTAVEL.md`
- `docs/historico_missoes/RELATORIO_MISSAO35F_HUMAN_APPROVAL_LAYER.md`
- `docs/historico_missoes/RELATORIO_MISSAO35G_SECRETS_VAULT_POLICY.md`
- `docs/historico_missoes/RELATORIO_MISSAO35H_INCIDENT_RESPONSE_MODE.md`
- `docs/historico_missoes/RELATORIO_MISSAO35I_RATE_LIMIT_INTELIGENTE.md`
- `docs/historico_missoes/RELATORIO_SECURITY_HARDENING_LAYER_CONCLUIDA.md`
- `docs/historico_missoes/RELATORIO_MISSAO36A_API_GATEWAY_GUARD.md`
- `docs/historico_missoes/RELATORIO_MISSAO36B_ROUTE_SECURITY_GUARD.md`
- `docs/historico_missoes/RELATORIO_MISSAO36C_EXPANSAO_ROUTE_SECURITY_GUARD.md`
- `docs/historico_missoes/RELATORIO_MISSAO36D_SECURITY_STATUS_DASHBOARD.md`
- `docs/historico_missoes/RELATORIO_MISSAO36E_REAL_MODE_HEALTH_GATE.md`
- `docs/historico_missoes/RELATORIO_MISSAO36F_SECURITY_BRAIN_BRIDGE.md`
- `docs/historico_missoes/RELATORIO_MISSAO36G_SANDBOX_READINESS.md`
- `docs/historico_missoes/RELATORIO_MISSAO36H_SANDBOX_EXECUTION_CONTRACT.md`
- `docs/historico_missoes/RELATORIO_MISSAO36I_TEMPLATE_TESTE_HIPOTESE_01.md`
- `docs/historico_missoes/RELATORIO_MISSAO36J_OPERATIONAL_HANDOFF.md`
- `docs/historico_missoes/RELATORIO_MISSAO36K_META_SANDBOX_SETUP.md`
- `docs/historico_missoes/RELATORIO_MISSAO36L_PRIMEIRO_PAYLOAD_SANDBOX_PAUSADO.md`
- `docs/historico_missoes/RELATORIO_MISSAO37A_GLOBAL_INTELLIGENCE_DATA_CONTRACT.md`
- `docs/historico_missoes/RELATORIO_MISSAO37B_MARKET_RADAR_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37C_WINNING_AD_SCORE_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37D_CREATIVE_INTELLIGENCE_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37E_COUNTRY_INTELLIGENCE_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37F_LANDING_INTELLIGENCE_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37G_OFFER_INTELLIGENCE_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37H_GLOBAL_OPPORTUNITY_BRIEF.md`
- `docs/historico_missoes/RELATORIO_MISSAO37I_GLOBAL_OPERATOR_HUB_DRY_RUN.md`
- `docs/historico_missoes/RELATORIO_MISSAO37J_DASHBOARD_ENTERPRISE_SNAPSHOT.md`
- `docs/historico_missoes/RELATORIO_MISSAO37K_GLOBAL_MINER_HUB_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37L_DATA_MOAT_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37M_API_COMERCIAL_SNAPSHOT.md`
- `docs/historico_missoes/RELATORIO_MISSAO37N_BILLING_READINESS_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37O_MULTI_TENANT_READINESS_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37P_PUBLIC_API_READINESS_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37Q_FRONTEND_ENTERPRISE_SPEC_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37R_REAL_CONNECTORS_READINESS_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37S_VECTOR_DB_READINESS_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37T_AD_LIBRARY_DATA_MODEL_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37U_AD_LIBRARY_SEARCH_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37V_SAAS_COMPLIANCE_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37W_EXECUTIVE_REPORTS_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37X_OPPORTUNITY_ALERTS_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37Y_SATURATION_MONITOR_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO37Z_SCALE_FORECAST_LOCAL.md`
- `docs/historico_missoes/RELATORIO_MISSAO38A_RELEASE_READINESS_LOCAL.md`
- `src/app/tests/test_final_safe_e2e.py`
- `src/app/tests/test_site_builder_legacy_compat.py`
- `src/app/tests/test_security_hardening_rbac.py`
- `src/app/tests/test_command_validator.py`
- `src/app/tests/test_zero_trust_internal_calls.py`
- `src/app/tests/test_immutable_audit_log.py`
- `src/app/tests/test_human_approval_layer.py`
- `src/app/tests/test_secrets_policy.py`
- `src/app/tests/test_incident_response_mode.py`
- `src/app/tests/test_rate_limit.py`
- `src/app/tests/test_api_gateway_guard.py`
- `src/app/tests/test_route_security_guard.py`
- `src/app/tests/test_security_status.py`
- `src/app/tests/test_real_mode_gate.py`
- `src/app/tests/test_security_brain_bridge.py`
- `src/app/tests/test_sandbox_readiness.py`
- `src/app/tests/test_sandbox_execution_contract.py`
- `src/app/tests/test_hypothesis_test_template.py`
- `src/app/tests/test_operational_handoff.py`
- `src/app/tests/test_meta_sandbox_setup.py`
- `src/app/tests/test_first_sandbox_payload.py`
- `src/app/tests/test_global_intelligence_contract.py`
- `src/app/tests/test_market_radar.py`
- `src/app/tests/test_winning_ad_score.py`
- `src/app/tests/test_creative_intelligence.py`
- `src/app/tests/test_country_intelligence.py`
- `src/app/tests/test_landing_intelligence.py`
- `src/app/tests/test_offer_intelligence.py`
- `src/app/tests/test_global_opportunity_brief.py`
- `src/app/tests/test_global_operator_hub.py`
- `src/app/tests/test_enterprise_dashboard_snapshot.py`
- `src/app/tests/test_global_miner_hub.py`
- `src/app/tests/test_data_moat.py`
- `src/app/tests/test_commercial_api_snapshot.py`
- `src/app/tests/test_billing_readiness.py`
- `src/app/tests/test_multi_tenant_readiness.py`
- `src/app/tests/test_public_api_readiness.py`
- `src/app/tests/test_frontend_enterprise_spec.py`
- `src/app/tests/test_real_connectors_readiness.py`
- `src/app/tests/test_vector_db_readiness.py`
- `src/app/tests/test_ad_library_model.py`
- `src/app/tests/test_ad_library_search.py`
- `src/app/tests/test_saas_compliance.py`
- `src/app/tests/test_executive_reports.py`
- `src/app/tests/test_opportunity_alerts.py`
- `src/app/tests/test_saturation_monitor.py`
- `src/app/tests/test_scale_forecast.py`
- `src/app/tests/test_release_readiness.py`

## Pacote

O pacote final deve excluir:

- `.env`
- `.env.*`
- bancos locais
- logs
- caches
- zips antigos
- binarios grandes como `ffmpeg.exe`
