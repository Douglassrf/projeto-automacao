# Relatório — Missão 07 / Memória Evolutiva Inicial

## Objetivo

Fazer o `CampaignBrainAgent` começar a lembrar e consultar experiências anteriores antes de recomendar uma campanha.

## Status

MISSÃO 07 APROVADA EM CÓPIA ISOLADA.

## Arquivos criados/alterados

- Criado: `src/app/services/campaign_memory.py`
- Alterado: `src/app/services/campaign_brain.py`
- Alterado: `src/app/api/routes/campaign_brain.py`
- Preservado: `FacebookAdMiner`
- Preservado: `MinerEngine`
- Preservado: `AdProcessor`
- Preservado: `MetaCampaignOperator`
- Preservado: `MetaMarketingClient`
- Preservado: `VideoPipeline`
- Preservado: `PremiumRender`

## O que foi criado

Foi criado o `CampaignMemoryStore`, uma memória local segura baseada em JSONL:

```txt
logs/campaign_brain_memory.log
```

Esta memória não depende de banco, SQLAlchemy, API Meta ou serviços externos.

## Novo comportamento do Brain

Antes, o Brain analisava regras, métricas e risco.

Agora ele também consulta:

```txt
experience_summary
historical_recommendation
last_similar
winners
losers
blocked
recent_lessons
```

## Rotas adicionadas

```txt
POST /api/v1/brain/learn
GET  /api/v1/brain/learn/mock
```

Rotas já existentes preservadas:

```txt
GET  /api/v1/brain/health
POST /api/v1/brain/review
GET  /api/v1/brain/review/mock
GET  /api/v1/miner/test
```

## Segurança

A memória evolutiva inicial:

- não chama API externa;
- não publica campanha;
- não altera orçamento;
- não aciona MetaCampaignOperator;
- não aciona VideoPipeline;
- não aciona PremiumRender;
- não altera banco;
- grava apenas em log local JSONL quando chamada explicitamente por `/brain/learn`.

## Validação técnica

```txt
py_compile app/services/campaign_memory.py        OK
py_compile app/services/campaign_brain.py         OK
py_compile app/api/routes/campaign_brain.py       OK
py_compile app/services/miner_engine.py           OK
py_compile app/services/facebook_ad_miner.py      OK
py_compile app/api/routes/meta_operator.py        OK
py_compile app/api/safe_router.py                 OK
py_compile app/main.py                            OK
```

Import de `app.main`: OK.

## Teste executado

Sequência validada:

```txt
1. /brain/review/mock
   → similar_records: 0

2. /brain/learn/mock
   → aprendizado registrado em logs/campaign_brain_memory.log

3. /brain/review/mock
   → similar_records: 1
   → winners: 1
   → historical_recommendation: Há histórico positivo parecido. Prosseguir com cautela e validar em dry_run.

4. /miner/test
   → o Brain consultou a memória e retornou experiência parecida.
```

## Resultado

O Brain começou a lembrar.

Agora o fluxo é:

```txt
FacebookAdMiner
    ↓
MinerEngine
    ↓
AdProcessor
    ↓
CampaignBrainAgent
    ↓
CampaignMemoryStore
    ↓
Recomendação com histórico
```

## Próxima missão recomendada

Missão 08 — MetaUpdateWatcher.

Objetivo:

Criar um agente seguro para registrar e consultar atualizações da Meta antes de campanhas.

Primeira versão recomendada:

- sem scraping automático pesado;
- sem login;
- sem API Meta;
- guardar atualizações manualmente ou por fonte controlada;
- responder ao Brain se existe risco de política/atualização.
