# ROADMAP v1.1

Documento de planejamento pós-v1.0. Nenhuma funcionalidade nova foi implementada nesta missão.

## Deploy de produção

- Definir estratégia oficial de deploy backend/frontend.
- Configurar ambientes separados para homologação, staging e produção.
- Validar variáveis obrigatórias por ambiente antes de qualquer ativação real.
- Formalizar rollback operacional e checklist pré-release.

## Dashboard operacional

- Criar painel executivo para status de segurança, filas, auditoria e saúde dos conectores.
- Exibir estado de dry-run/real-mode, bloqueios ativos e pendências de aprovação humana.
- Consolidar indicadores de campanhas, alertas e tarefas pendentes em uma visão única.

## Observabilidade

- Evoluir logs estruturados, métricas e rastreamento por correlation/execution/mission ID.
- Adicionar dashboards de latência, erro, auditoria imutável e filas.
- Definir alertas para falhas críticas, tentativa de modo real e regressões de segurança.

## CI/CD

- Criar pipeline de lint, testes e auditoria de segredos.
- Adicionar empacotamento automatizado de release após aprovação manual.
- Publicar artefatos somente via fluxo controlado, sem push direto e sem segredos embutidos.

## Segurança e governança

- Manter Meta em dry-run por padrão até aprovação humana e ambiente real validado.
- Revisar CORS antes de exposição web cross-origin.
- Fortalecer política JWT/secrets para produção.
- Automatizar verificação de cadeia de audit log antes de releases futuras.
