# Runbook Operacional v1.1

1. Verificar `/health`.
2. Verificar `/api/v1/observability/readiness`.
3. Verificar `/api/v1/platform-readiness/self-diagnostic`.
4. Priorizar `/api/v1/platform-readiness/alerts`.
5. Registrar decisão em audit trail antes de ações manuais.
