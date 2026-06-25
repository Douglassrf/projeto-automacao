# Release Notes — Projeto Automação v1.1

Data UTC: 2026-06-25.

## Status

A versão local foi atualizada para `1.1.0`, mas a publicação GitHub/tag `v1.1.0` ainda precisa ser confirmada em ambiente com remote configurado.

## Evidência principal

- Regressão completa: `python -m pytest -q` passou 3 vezes consecutivas com `302 passed, 3 warnings`.
- Compilação Python: `python -m compileall -q src` passou.
- O shim de `ffmpeg` em `tools/` é carregado por `conftest.py` apenas no contexto de testes.

## Ressalvas de certificação

- Build Docker de produção não foi executado porque Docker não está instalado no workspace.
- Tag remota `v1.1.0` não foi verificada porque não há remote `origin` configurado.
- PR #11 e PR #13 não puderam ser fechados/anotados diretamente neste workspace porque `gh` não está instalado e não há remote GitHub configurado.
