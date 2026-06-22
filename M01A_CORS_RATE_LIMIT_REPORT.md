# M01-A — CORS e Rate Limiting Report

## Escopo executado
- CORS centralizado no app FastAPI com `CORSMiddleware`, allowlist explícita via `CORS_ORIGINS` e sem wildcard por padrão.
- Rate limiting HTTP configurável por variáveis de ambiente, reaproveitando o guard central existente da API.
- Respostas bloqueadas por rate limit mantêm status `429` e agora incluem o header `Retry-After`.
- Conflitos de `src/app/main.py` e `src/app/services/observability.py` resolvidos preservando métricas HTTP (`record_http_metric`) e health snapshot operacional (`component_health_snapshot`) já presentes na base local.
- Variáveis novas documentadas em `.env.example`, sem segredos reais.

## Restrições confirmadas
- Nenhuma credencial real adicionada.
- Nenhuma alteração relacionada a TikTok.
- Nenhuma alteração de integração, chamada, credencial ou flag operacional de Meta/Facebook Ads.
- Nenhuma remoção, afrouxamento ou bypass da autenticação de produção.

## Evidência de testes
- `pytest src/app/tests/test_m01a_cors_rate_limit.py -q`
- `pytest src/app/tests/test_r14_security_final.py -q`

## Limitações conhecidas
- O rate limiter permanece em memória, portanto os contadores não são compartilhados entre múltiplos processos/instâncias.
