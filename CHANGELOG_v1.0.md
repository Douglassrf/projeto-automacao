# CHANGELOG v1.0.0

Este changelog foi preparado para o empacotamento final v1.0 (F07) com moratória de funcionalidade nova. Ele registra apenas o que aparece no histórico Git local e nos relatórios já versionados; não inventa PRs, features ou resultados externos.

## Evidência base usada

Comandos locais usados como fonte factual:

```bash
git log --oneline --reverse --max-count=10
```

Saída observada:

```text
700bf36 ajuste de seguranca no gitignore
c44bea6 R01-R11 + C01 + C02: testes raiz completos + correcoes criticas pos-parecer da arquiteta
45181dd C01/C02 follow-up: inclui 2 arquivos que ficaram fora do commit c44bea6 por cache desatualizado do git
cd32e56 C04: corrige 3 caminhos sem guardrail meta_env/META_ALLOW_PRODUCTION_REAL antes de escrita real na Meta
585537a docs: plano mestre de finalizacao + briefing formal para o Codex (C03/C06/R13/R14), com protocolo de revisao do chefe
5938df5 R12: teste do fluxo completo raiz-a-raiz com evidencia HTTP real (FULL_ROOT_E2E_REPORT.md)
7cb499e follow-up pos-R12: restaura arquivos truncados + guardrails C04 + docs atualizados
1ba2053 C03 aplica guard de IA pesada no video
808ba57 Merge pull request #1 from Douglassrf/codex/corrigir-guard-de-ia-pesada-na-rota-de-video
b48361e Add R13/R14 security & failure tests and add C06/R13/R14 test run reports
```

Também foi conferido o intervalo local após o merge C03:

```bash
git log --oneline --reverse 808ba57..HEAD
```

Saída observada:

```text
b48361e Add R13/R14 security & failure tests and add C06/R13/R14 test run reports
```

## v1.0.0 — Empacotamento final

### Documentação de release

- Adicionado este `CHANGELOG_v1.0.md` para registrar a v1.0.0 a partir do histórico Git real.
- Adicionado `RELEASE_NOTES_v1.0.md` com escopo, limitações conhecidas e regras operacionais de segurança da v1.0.0.
- Atualizado `VERSION` de `0.1.0` para `1.0.0`.

### Homologação e relatórios C06/R13/R14

- `b48361e` adicionou os relatórios `C06_PYTEST_REPORT.md`, `FAILURE_TEST_REPORT.md` e `SECURITY_FINAL_TEST_REPORT.md`.
- `b48361e` adicionou `src/app/tests/test_r13_failure_scenarios.py` para cenários de falha controlada.
- `b48361e` adicionou `src/app/tests/test_r14_security_final.py` para validações finais de segurança.

### C03 — Guard de IA pesada no vídeo

- `1ba2053` aplicou o guard de IA pesada no fluxo de vídeo.
- `808ba57` mesclou o PR #1 relacionado ao guard de vídeo.

### R12 — Fluxo completo raiz-a-raiz

- `5938df5` adicionou o teste/relatório do fluxo completo raiz-a-raiz com evidência HTTP real (`FULL_ROOT_E2E_REPORT.md`).
- `7cb499e` restaurou arquivos truncados e atualizou guardrails/documentação no follow-up pós-R12.

### C04 — Guardrails Meta antes de escrita real

- `cd32e56` corrigiu 3 caminhos sem guardrail `meta_env`/`META_ALLOW_PRODUCTION_REAL` antes de escrita real na Meta.

### C01/C02 e R01-R11

- `c44bea6` registrou testes raiz completos e correções críticas pós-parecer da arquiteta para R01-R11 + C01 + C02.
- `45181dd` adicionou arquivos de follow-up de C01/C02 que haviam ficado fora do commit anterior por cache desatualizado do Git.

### Higiene do repositório

- `700bf36` ajustou segurança no `.gitignore`.

## Observações de corte

- Este changelog não declara funcionalidades novas além do que o Git local registra.
- A geração de pacote `.zip` não faz parte da F07; ficará para Douglas via GitHub Release após merge.
- A v1.0.0 mantém as limitações e regras operacionais descritas em `RELEASE_NOTES_v1.0.md`.
