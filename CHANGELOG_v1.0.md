# CHANGELOG v1.0

Data de empacotamento: 2026-06-20
Versão: 1.0.0

## Visão geral

Este pacote marca a versão **1.0.0** do Projeto Automação / AdIntelligence Pro como uma entrega local segura para operação, validação e continuidade de desenvolvimento.

O projeto é um backend FastAPI local para automação e inteligência de campanhas de anúncios, com foco em Meta/Facebook Ads, mineração/análise controlada, geração de conteúdo, orquestração de campanhas, camada de decisão/aprendizado e guardrails de segurança para evitar ações reais sem confirmação humana explícita.

## Adicionado

- Arquivos de empacotamento da versão 1.0:
  - `CHANGELOG_v1.0.md`
  - `RELEASE_NOTES_v1.0.md`
- Registro formal da versão `1.0.0` no arquivo `VERSION`.
- Documentação consolidada de escopo, limitações, segurança, validação e próximos passos para o release v1.0.

## Incluído no pacote v1.0

- Backend FastAPI local com banco SQLite.
- Autenticação local com JWT e senha com hash `pbkdf2_sha256`.
- Mineração/análise de anúncios em modo controlado e local.
- Learning Loop auditável, sem envio real para Meta/CAPI.
- `MetaCampaignOperator` com múltiplas camadas de guardrail:
  - dry-run por padrão;
  - perfis `sandbox`, `test_account` e `production`;
  - confirmação manual por frase literal;
  - hash de payload aprovado;
  - revisão de credenciais sem exposição de valores;
  - rollback formal;
  - monitoramento pós-execução.
- Observabilidade e auditoria com identificadores operacionais e logs JSONL locais.
- Scripts e documentação operacional para instalação, execução, validação e continuidade.

## Segurança

- O `.env` real permanece fora do Git.
- `DEFAULT_ADMIN_PASSWORD` não possui valor padrão hardcoded no código-fonte e deve ser definido localmente.
- O pacote mantém a postura de operação segura por padrão: nenhuma escrita real em Meta Ads deve ocorrer sem configuração deliberada e confirmação humana explícita.
- Artefatos locais sensíveis, bancos, logs, backups e caches continuam excluídos do empacotamento versionado.

## Limitações conhecidas

- O projeto roda localmente; não há deploy de produção ou pipeline CI/CD configurado neste repositório.
- Não há frontend web implementado; a interface operacional é a API/Swagger.
- Billing, multi-tenant, API pública comercial, conectores externos reais, Vector DB e compliance SaaS permanecem como especificações/readiness local, não como funcionalidades reais em produção.
- A validação completa registrada pelo projeto indica `261 passed`, mas deve ser reexecutada em ambiente Python 3.11+ antes de uma homologação operacional final independente.

## Alterado

- `VERSION` atualizado de `0.1.0` para `1.0.0`.

## Removido

- Nenhum arquivo de código ou documentação existente foi removido neste empacotamento.
