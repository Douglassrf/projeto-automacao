# Changelog

## 1.1.0 — 2026-06-25

### Added
- Relatórios finais da Fase Ômega para O03-O10.
- Release notes da versão 1.1.

### Changed
- Versão declarada do projeto atualizada para `1.1.0`.
- Relatório O03 reescrito com a evidência real após presença do shim de ffmpeg do PR #15.

### Validation
- `python -m pytest -q` executado 3 vezes consecutivas com `302 passed, 3 warnings`.
- `python -m compileall -q src` executado com sucesso.

### Known limitations
- Docker local indisponível neste workspace (`docker: command not found`).
- Remote Git `origin` ausente; tag `v1.1.0` não pôde ser verificada/publicada daqui.
