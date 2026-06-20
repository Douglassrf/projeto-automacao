# PROJECT_STATUS

Atualizado em: 2026-06-18

Este arquivo registra o estado real e atual do Projeto Automação
(AdIntelligence Pro), sem alegações de prontidão que não tenham evidência por
trás. Para o histórico detalhado de cada missão, ver `docs/historico_missoes/`.

## 1. O que é este projeto

Backend FastAPI local para automação e inteligência de campanhas de anúncios
(Meta/Facebook): mineração de anúncios, geração de conteúdo, orquestração de
campanha, camada de decisão/aprendizado ("Brain"), e operação de
campanhas Meta com guardrails de segurança.

## 2. O que está implementado e validado

- API FastAPI com ~90 arquivos de teste automatizado (`src/app/tests/`).
- Banco local SQLite com migração leve própria (sem Alembic ainda).
- Autenticação local (JWT + senha com hash `pbkdf2_sha256`).
- Mineração de anúncios em modo controlado/local (sem scraping real, sem
  navegador headless, sem chamada externa) — `MinerEngine`,
  `FacebookAdMiner`.
- Learning Loop controlado (eventos auditáveis, sem envio real para Meta/CAPI).
- `MetaCampaignOperator` com múltiplas camadas de guardrail antes de qualquer
  escrita real: dry-run por padrão, perfis `sandbox`/`test_account`/
  `production`, confirmação manual por frase literal, hash de payload
  aprovado, revisão de credenciais sem expor valores, rollback formal,
  monitoramento pós-execução.
- Observabilidade e auditoria (correlation_id/execution_id/mission_id,
  logs JSONL em `logs/`).
- Última validação de suíte completa **registrada pelo próprio projeto**
  (não re-executada por mim neste ambiente — ver seção 6):
  `261 passed` (`docs/GUIA_OPERACIONAL_FINAL.md`,
  `docs/historico_missoes/RELATORIO_MISSAO38A_RELEASE_READINESS_LOCAL.md`).

## 3. O que existe só como especificação/"readiness local" (NÃO é real)

Os seguintes itens têm documentação e testes locais de "prontidão", mas **não
são funcionalidades reais em produção**:

- Billing (`docs/historico_missoes/RELATORIO_MISSAO37N_BILLING_READINESS_LOCAL.md`).
- Multi-tenant (`...MISSAO37O_MULTI_TENANT_READINESS_LOCAL.md`).
- API pública comercial (`...MISSAO37P_PUBLIC_API_READINESS_LOCAL.md`,
  `...MISSAO37M_API_COMERCIAL_SNAPSHOT.md`).
- Frontend enterprise (`...MISSAO37Q_FRONTEND_ENTERPRISE_SPEC_LOCAL.md`) —
  **não existe nenhum código de frontend no repositório**, apenas a
  especificação.
- Conectores reais externos (`...MISSAO37R_REAL_CONNECTORS_READINESS_LOCAL.md`).
- Vector DB (`...MISSAO37S_VECTOR_DB_READINESS_LOCAL.md`).
- Compliance SaaS (`...MISSAO37V_SAAS_COMPLIANCE_LOCAL.md`).

Tratar esses documentos como design/planejamento, não como status de entrega.

## 4. Meta / Facebook Ads — estado real

- Existe uma campanha real chamada "Codex" (`52616252576068`), mantida
  **pausada** (`PAUSED`).
- Nenhuma escrita real nova (criação/ativação de campanha, conjunto ou
  anúncio) foi feita pela plataforma além dessa campanha já pausada.
- Exclusão de campanhas antigas ficou bloqueada por uma resposta de
  autenticação/autorização da própria Meta (`OAuthException 31 / 3858385`),
  não por limitação do código.
- Qualquer ativação real de gasto exige autorização humana explícita por
  escrito, com valor e objetivo claros — não acontece automaticamente.

## 5. Deploy / Infraestrutura

- Hoje o projeto roda **somente local** (laptop de desenvolvimento).
- Não há deploy em nenhum provedor de nuvem, container em produção, nem
  pipeline de CI/CD configurado neste repositório.
- `Dockerfile` existe na raiz, mas não há evidência de uso em produção.

## 6. Limitação de ambiente conhecida (testes)

A suíte de testes do projeto requer Python 3.11+ (usa `datetime.UTC` e
`enum.StrEnum`). No ambiente usado para a migração para o Git (sandbox desta
sessão), só havia Python 3.10 disponível, então a suíte completa não pôde ser
re-executada para confirmar os `261 passed` de forma independente nesta
sessão. As mudanças de segurança feitas (remoção de senha padrão hardcoded)
foram validadas de forma isolada (sem a suíte completa) e o resultado foi
positivo. Recomenda-se rodar a suíte completa em um ambiente com Python
3.11+ antes de considerar o pacote 100% confirmado.

## 7. Segurança — estado atual (missões G01R-G04 desta migração para o Git)

- `secrets_audit_report.json`: `LIBERADO`, 0 achados de segredo hardcoded.
- `default_admin_password` não tem mais valor padrão no código; exige `.env`.
- `.gitignore` cobre `.env`, bancos locais, ambientes virtuais, caches,
  backups, logs e artefatos de auditoria.
- 3 pastas duplicadas e 32 arquivos de backup legados foram movidos (nunca
  apagados) para `archived_legacy/` — ver `legacy_manifest.json`.
- Backup imutável completo do projeto (com `.env` e banco) existe em
  `_backups/` (fora do Git).

## 8. Pendências conhecidas

- Confirmar `261 passed` em ambiente com Python 3.11+.
- Decidir e executar a migração para repositório remoto no GitHub (missões
  G06 em diante desta ordem executiva) — depende de decisão do usuário sobre
  método de autenticação/criação do repositório.
- `ffmpeg.exe` (binário grande) e `adintelligence.db` (banco com dados reais)
  permanecem locais, fora do pacote Git, por design.
