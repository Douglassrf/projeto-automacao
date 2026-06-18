# AdIntelligence Pro — Projeto Automação

Plataforma local de automação e inteligência para campanhas de anúncios
(Meta/Facebook), operando em modo seguro (dry-run) por padrão.

## O que este projeto é

- Backend FastAPI (Python) com banco local SQLite.
- Mineração e análise de anúncios, geração de conteúdo/criativos, orquestração
  de campanhas.
- "Cérebro" (CampaignBrain) e "Brian" como camadas de decisão/aprendizado que
  registram decisões e memória de campanha.
- Guardrails de produção: nenhuma escrita real na Meta (criar/editar/ativar
  campanha) acontece sem múltiplas confirmações explícitas e configuração
  específica (`META_DRY_RUN`, `META_ALLOW_PRODUCTION_REAL`, confirmação manual
  por frase literal, hash de payload aprovado, etc.).

## O que este projeto NÃO é (ainda)

- Não tem frontend/interface web. É uma API backend (Swagger/OpenAPI em
  `/docs`).
- Não tem billing real, multi-tenant real, nem API pública real em produção —
  existem apenas especificações e testes de "readiness local" para esses
  recursos (ver `docs/historico_missoes/`), não implementações ativas.
- Não está implantado (deploy) em nenhum ambiente além do laptop local de
  desenvolvimento.

Estado completo e detalhado: ver [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

## Início rápido

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash). Linux/Mac: source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# edite o .env e defina DEFAULT_ADMIN_PASSWORD (obrigatorio) e demais valores
cd src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Swagger: `http://127.0.0.1:8000/docs`

## Variáveis de ambiente

Use `.env.example` como modelo. O `.env` real nunca deve ser commitado (já
está em `.gitignore`).

Desde a auditoria de segurança deste projeto, `DEFAULT_ADMIN_PASSWORD` não tem
mais valor padrão hardcoded no código-fonte: precisa estar definida no `.env`
local, senão a inicialização do banco falha de propósito (fail-loud) em vez de
usar uma senha fraca/previsível.

## Testes

```bash
python -m pytest -p no:cacheprovider --basetemp .pytest_tmp
```

Requer Python 3.11+ (o projeto usa `datetime.UTC` e `enum.StrEnum`). Última
validação registrada pelo próprio projeto: `261 passed` (ver
`docs/GUIA_OPERACIONAL_FINAL.md`).

## Segurança

- Segredos reais nunca devem ir para o Git. Ver `.gitignore` e
  `scripts/audit_secrets_before_git.py`.
- Escrita real na Meta Ads exige aprovação humana explícita, dry-run
  desligado, confirmação manual e outras camadas de guardrail — ver
  `src/app/services/meta_campaign_operator.py`.
- Arquivos legados/duplicados foram quarentenados (nunca apagados) em
  `archived_legacy/` — ver `legacy_manifest.json`.

## Estrutura

```text
src/app/          backend FastAPI (api, core, db, domain, services, schemas, tests)
scripts/          scripts de manutencao/seguranca (auditoria de segredos, backup, quarentena)
docs/             documentacao historica de missoes e arquitetura
data/             dados gerados localmente (campaign kits, etc.)
_backups/         backups imutaveis locais (ignorado pelo Git)
archived_legacy/  arquivos legados quarentenados (ignorado pelo Git)
```
