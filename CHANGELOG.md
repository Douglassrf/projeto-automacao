# Changelog

## 1.7.0 - 2026-06-29

### Added
- FASE v1.7 homologacao M82-M91 mergeada via PR #29 (CONFIG 4.0.0).
- RELEASE_NOTES_v1.7.0.md.

### Changed
- Versao declarada do projeto atualizada para `1.7.0` (Fase v1.7 homologacao).

### Validation
- Merge master @ `aaae7d8`; tag anotada `v1.7.0` apos bump de VERSION.
## 1.1.0 â€” 2026-06-25

### Added
- RelatÃ³rios finais da Fase Ã”mega para O03-O10.
- Release notes da versÃ£o 1.1.

### Changed
- VersÃ£o declarada do projeto atualizada para `1.1.0`.
- RelatÃ³rio O03 reescrito com a evidÃªncia real apÃ³s presenÃ§a do shim de ffmpeg do PR #15.

### Validation
- `python -m pytest -q` executado 3 vezes consecutivas com `302 passed, 3 warnings`.
- `python -m compileall -q src` executado com sucesso.

### Known limitations
- Docker local indisponÃ­vel neste workspace (`docker: command not found`).
- Remote Git `origin` ausente; tag `v1.1.0` nÃ£o pÃ´de ser verificada/publicada daqui.

