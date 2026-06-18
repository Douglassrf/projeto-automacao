# Relatorio Missao 36C - Expansao Route Security Guard

Data: 2026-06-05

## Objetivo

Expandir o Route Security Guard para acoes sensiveis fora da Meta: publicacao de site, IA/render pesado, video e troca de link de afiliado.

## Entregas

- Guard para site publish com bloqueio de deploy real sem aprovacao.
- Guard para IA/render pesado com bloqueio de provedor pago sem aprovacao.
- Guard para video pipeline local.
- Guard para troca local de link de afiliado.
- Diagnostico `security_guard` na resposta do SiteBuilder.
- Testes dedicados ampliados.

## Arquivos

- `src/app/core/route_security.py`
- `src/app/api/routes/site_builder.py`
- `src/app/api/routes/premium_render.py`
- `src/app/api/routes/video_pipeline.py`
- `src/app/api/routes/affiliate.py`
- `src/app/tests/test_route_security_guard.py`

## Validacao

```txt
158 passed
```

## Status

```txt
MISSAO 36C CONCLUIDA
```
