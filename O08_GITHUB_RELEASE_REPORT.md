# O08 — GITHUB RELEASE REPORT

Data UTC: 2026-06-25.

## Veredito O08

**O08 REPROVADO NESTE WORKSPACE.** Não há remote `origin`, não foi possível confirmar tag `v1.1.0` publicada com `git ls-remote --tags origin`, e os artefatos `CHANGELOG.md` e `RELEASE_NOTES_v1.1.md` estavam ausentes antes desta correção documental.

## Evidência

```bash
git remote -v
# sem saída
```

```bash
git ls-remote --tags origin
# fatal: 'origin' does not appear to be a git repository
```

```bash
cat VERSION
# 1.0.0
```

## Ação nesta correção

- `VERSION` foi atualizado para `1.1.0`.
- `CHANGELOG.md` foi criado.
- `RELEASE_NOTES_v1.1.md` foi criado.

## Pendência externa

Publicar e verificar a tag `v1.1.0` no GitHub em workspace com remote configurado.
