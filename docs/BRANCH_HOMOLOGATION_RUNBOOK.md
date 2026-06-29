# Runbook — Revisão de branches de missão e homologação

Este runbook padroniza a revisão de branches `missao-*`/`mission-*`, abertura de PRs e validação de CI antes da homologação.

## Pré-requisitos

1. O repositório precisa ter um remote GitHub configurado, normalmente `origin`.
2. A GitHub CLI (`gh`) precisa estar autenticada para consultar PRs, criar PRs e ler runs de CI.
3. Os workflows de CI precisam estar habilitados no GitHub Actions.

## Revisar branches sem abrir PRs

```bash
python scripts/review_mission_branches.py --remote origin --base main
```

O comando lista branches de missão, PR aberto, último estado de CI e recomendação de homologação.

## Abrir PRs ausentes para homologação

```bash
python scripts/review_mission_branches.py --remote origin --base main --open-prs
```

O modo `--open-prs` cria PRs ausentes com título `Homologação: <branch>` e mantém a validação de CI no relatório.

## Critério de homologação

Uma branch só deve ser homologada quando:

- existir PR aberto;
- o último CI do branch estiver `completed:success`;
- não houver conflitos ou bloqueadores no review;
- o escopo da missão estiver documentado no PR.

## Limitação operacional deste ambiente

Se o clone local não tiver remote configurado, o script encerra com código `2` e informa que não é possível revisar branches no GitHub. Nesse caso, configure `origin` antes de executar a homologação.
