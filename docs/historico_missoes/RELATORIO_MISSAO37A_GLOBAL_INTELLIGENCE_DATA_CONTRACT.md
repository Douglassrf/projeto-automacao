# Relatorio - Missao 37A - Global Intelligence Data Contract

Data: 2026-06-05

## Objetivo

Iniciar a expansao global sem alterar o nucleo seguro da Meta, criando um contrato universal para sinais de anuncios de multiplas plataformas.

## Entregas

- Criado `src/app/core/global_intelligence_contract.py`.
- Criada rota `/api/v1/global-intelligence/normalize-ad`.
- Criado teste `src/app/tests/test_global_intelligence_contract.py`.
- Registrado aprendizado no Brian/CampaignMemory a cada normalizacao.

## Plataformas Mapeadas

- Meta.
- Google.
- TikTok.
- LinkedIn.
- Pinterest.

## Contrato Universal

O payload normalizado passa a conter:

- plataforma;
- pais;
- idioma;
- moeda;
- criativo;
- landing;
- oferta;
- metricas padronizadas.

## Guardrails

- Nenhuma chamada externa.
- Nenhuma acao real.
- Nenhum gasto ativo.
- Dados ruins ou plataforma desconhecida ficam bloqueados.

## Resultado

Status: concluida em modo seguro.

Validacao focal:

```txt
3 passed
```

Suite completa:

```txt
183 passed
```
