# INSTRUÇÕES M152 — GO final (Douglas)

**Data UTC:** 2026-06-29  
**Critério GO (Douglas):** Linux 🟢 + Windows 🟢 **3 vezes consecutivas** no CI (`repeat=3`), após `gh auth login`. Douglas assina GO manualmente se critério atingido.

**Clone:** `C:\Users\USUÁRIO\Documents\projeto-automacao-m81`  
**Branch:** `missao-152-homologacao-final-multiplataforma`  
**SHA esperado (ref):** `54c00c52c100d66bf1177e44eb38ec3a19441ad6` (`54c00c5`)

---

## Status auth nesta execução (agente Cursor)

```
gh auth status
You are not logged into any GitHub hosts. To log in, run: gh auth login

GH_TOKEN=not set
GITHUB_TOKEN=not set
```

**Veredito técnico preliminar:** 🔴 **NO GO** — evidência única pendente é autenticação `gh`; workflow M152 com `repeat=3` não foi disparado neste ambiente.

---

## Comandos exatos (PowerShell)

Abra PowerShell e execute **na ordem**:

```powershell
cd C:\Users\USUÁRIO\Documents\projeto-automacao-m81
git fetch origin missao-152-homologacao-final-multiplataforma
git checkout missao-152-homologacao-final-multiplataforma
git rev-parse HEAD
```

Confirme que `git rev-parse HEAD` começa com `54c00c5` (ou documente o SHA real se diferente).

### 1) Autenticar GitHub CLI (obrigatório)

```powershell
gh auth login
```

- Escolha **GitHub.com**
- Preferir **HTTPS** (alinhado ao GCM já listando `Douglassrf`)
- Autentique no browser ou com token conforme o assistente `gh`

Validação:

```powershell
gh auth status
```

Deve mostrar logged in to github.com.

### 2) Disparar homologação M152 (3× pytest em cada OS)

```powershell
gh workflow run ci.yml --ref missao-152-homologacao-final-multiplataforma -f repeat=3
```

### 3) Aguardar término (timeout generoso — Windows pode ser lento)

```powershell
gh run watch
```

Se `gh run watch` não pegar o run certo, use:

```powershell
gh run list --workflow=ci.yml --branch=missao-152-homologacao-final-multiplataforma --limit 3
gh run watch <RUN_ID>
```

---

## O que observar no GitHub Actions

Workflow: **CI** — `.github/workflows/ci.yml`

| Job | Runner | Critério |
|-----|--------|----------|
| `lint-and-test-linux` | `ubuntu-latest` | Conclusão **success** — dentro do job, 3 loops `pytest -q` sem falha |
| `lint-and-test-windows` | `windows-latest` | Conclusão **success** — 3 loops `pytest -q -m "not ffmpeg"` sem falha |

**GO técnico:** **um único run** disparado com `repeat=3` em que **ambos** jobs terminam **success** (equivale a 3× verde Linux + 3× verde Windows na mesma execução).

**NO GO** se qualquer job falha, cancela, ou fica `in_progress` por horas (runner travado — ver runs antigos em master).

Links úteis:

- Actions: https://github.com/Douglassrf/projeto-automacao/actions
- Workflow CI: https://github.com/Douglassrf/projeto-automacao/actions/workflows/ci.yml

---

## Template de evidência (colar após concluir)

Copie a saída literal e preencha:

```
=== M152 GO — evidência Douglas ===
Data/hora local:
SHA do run (checkout no Actions ou git rev-parse antes do dispatch):
gh auth status:
  (colar saída)

Dispatch:
  gh workflow run ci.yml --ref missao-152-homologacao-final-multiplataforma -f repeat=3
  (colar saída ou "sem erro")

Run:
  URL: https://github.com/Douglassrf/projeto-automacao/actions/runs/________
  Run ID:
  Duração total:
  lint-and-test-linux: success | failure | cancelled | in_progress
  lint-and-test-windows: success | failure | cancelled | in_progress

Critério 3× Linux + 3× Windows no mesmo run: ATINGIDO | NÃO ATINGIDO

Veredito técnico: GO | NO GO
Assinatura Douglas (GO manual): pendente | GO assinado em ____
```

---

## Após GO técnico (opcional — agente ou Douglas)

Atualizar no branch M152:

- `FINAL_PLATFORM_AUDIT.md` — veredito 🟢 GO + "Aguardando assinatura Douglas"
- `M152_FINAL_MULTIplatform_HOMOLOGATION_REPORT.md` — mesma linha + links dos runs

Se **NO GO:** manter NO GO, incluir URLs dos runs e falha mínima (job + step).

---

## Referência — jobs no workflow

- Linux: `lint-and-test-linux`
- Windows: `lint-and-test-windows`
- Input: `repeat=3` → variável `PYTEST_REPEAT` no step de pytest
---

## Anexo — evidencia final M152 GO (fail-closed)

**Registro:** 2026-06-29 (execucao evidencia final GO — Cursor subagent, autorizacao Douglas explicita)  
**Branch:** `missao-152-homologacao-final-multiplataforma`  
**SHA local (`git rev-parse HEAD`):** `54c00c52c100d66bf1177e44eb38ec3a19441ad6` (`54c00c5`)

### Terminal literal — preparacao

```
git checkout missao-152-homologacao-final-multiplataforma
Already on 'missao-152-homologacao-final-multiplataforma'
Your branch is up to date with 'origin/missao-152-homologacao-final-multiplataforma'.
54c00c52c100d66bf1177e44eb38ec3a19441ad6
54c00c5 M152: ORDEM FINAL homologacao — NO GO com evidencias exec 2
```

### Terminal literal — autenticacao

```
gh auth status
You are not logged into any GitHub hosts. To log in, run: gh auth login

GH_TOKEN not set
GITHUB_TOKEN not set
```

### Terminal literal — dispatch CI (repeat=3)

```
gh workflow run ci.yml --ref missao-152-homologacao-final-multiplataforma -f repeat=3
To get started with GitHub CLI, please run:  gh auth login
Alternatively, populate the GH_TOKEN environment variable with a GitHub API authentication token.
(exit code 4)
```

**Run URL / jobs:** nao aplicavel — workflow nao disparado nesta execucao.

### GitHub API publica (sem token)

```
GET .../actions/runs?branch=missao-152-homologacao-final-multiplataforma
total_count 0
```

Referencia CI recente em master (nao substitui criterio M152): run 28375712227 — failure — https://github.com/Douglassrf/projeto-automacao/actions/runs/28375712227

### Criterio repeat=3 (Linux + Windows success no mesmo run)

| Item | Resultado |
|------|-----------|
| lint-and-test-linux x3 no run M152 | NAO ATINGIDO (0 runs na branch) |
| lint-and-test-windows x3 no run M152 | NAO ATINGIDO (0 runs na branch) |

### Veredito tecnico M152

NO GO — fail-closed: exige ambos jobs success no run disparado com repeat=3. Autenticacao gh ainda necessaria no terminal do Douglas (gh auth login ou GH_TOKEN).

**Assinatura Douglas (GO manual):** pendente
