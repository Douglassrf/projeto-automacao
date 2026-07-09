# Missões 112-121 — Engineering Control Tower v2.0

## Entrega

Foi adicionada uma Torre de Controle de Engenharia em uma única tela, com endpoints JSON e Markdown para consolidar:

- status global dos módulos, PRs, testes, pipelines, certificações e equipes;
- relatório automático de refatoração com duplicidade, métodos longos, classes complexas, acoplamento e sugestões priorizadas;
- saúde das dependências;
- validação de consistência arquitetural;
- estado da documentação;
- recomendações operacionais;
- centro de simulação;
- programa de estabilidade de longo prazo;
- centro unificado de operações;
- certificação Legacy & Evolution.

## Endpoints

- `GET /api/v1/engineering-control-tower/live`
- `GET /api/v1/engineering-control-tower/markdown`

## Critério de aprovação

A saúde completa da engenharia passa a estar disponível em um snapshot único, calculado a partir de evidências locais do repositório e dos serviços internos existentes, sem dependência de rede externa.

## Revisão solicitada para homologação

- Branches: o snapshot agora inclui inventário Git local (`current_branch`, branches locais, branches remotas e remotes configurados).
- PRs: o painel expõe `homologation_gate`, sinalizando quando a branch está pronta para abertura de PR de homologação.
- CI: o painel lista os comandos locais de validação e marca o status remoto como `requires_github_push` quando o ambiente não possui integração GitHub/CI disponível.
