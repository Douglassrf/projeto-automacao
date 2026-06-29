# Release Notes v1.7.0

**Data:** 2026-06-29  
**Operador:** Douglas (`Douglassrf`)  
**Base merge:** PR #29 @ master `aaae7d8`  
**CONFIG_SCHEMA_VERSION:** `4.0.0`

## Resumo

Homologacao FASE v1.7 (Missoes M82-M91): estabilizacao CI/CD, camada FFmpeg, confiabilidade de testes, release candidate, auditorias de seguranca/performance/recuperacao, revisao documental, aprovacao pre-producao e autorizacao de lancamento.

## Destaques

- CI Linux: suite completa com ffmpeg; CI Windows: `pytest -m "not ffmpeg"`.
- Novos endpoints `/live` e `/markdown` para M82-M91 sob `/api/v1/`.
- CONFIG schema 3.1.0 -> 4.0.0 (capstone M91 Production Launch Authorization).

## Versao do produto

- Arquivo `VERSION`: **1.7.0** (alinhado a tag `v1.7.0`).

## Validacao

- Merge PR #29 em master (2026-06-29).
- CI pos-merge master: ver Actions run associado ao push de merge.

## Limitacoes conhecidas

- Gates fail-closed (M91 pode reportar `not_ready` se dependencias upstream tiverem `blocking_issues`).
- Windows CI pode falhar independentemente da suite Linux; revisar job `lint-and-test-windows`.
