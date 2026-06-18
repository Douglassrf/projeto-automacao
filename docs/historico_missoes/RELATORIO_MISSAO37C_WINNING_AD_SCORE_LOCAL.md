# Relatorio - Missao 37C - Winning Ad Score Local

Data: 2026-06-05

## Objetivo

Criar uma pontuacao inicial 0-100 para anuncios, transformando sinais normalizados em uma decisao quantificada antes de qualquer execucao.

## Entregas

- Criado `src/app/core/winning_ad_score.py`.
- Criado endpoint `/api/v1/global-intelligence/winning-ad-score`.
- Criado teste `src/app/tests/test_winning_ad_score.py`.
- Integracao com Global Intelligence Data Contract.
- Aprendizado registrado no Brian/CampaignMemory.

## Score

O score combina:

- `creative_score`;
- `landing_score`;
- `offer_score`;
- `performance_score`;
- `trend_score`;
- `global_score`.

## Vereditos

- `likely_winner`;
- `needs_iteration`;
- `high_risk`.

## Guardrails

- Nenhuma chamada externa.
- Nenhuma acao real.
- Nenhum gasto ativo.
- Sinais invalidos sao bloqueados.

## Validacao

```txt
9 passed
```

Suite completa:

```txt
189 passed
```
