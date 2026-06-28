# Missão 49 — Auditoria de Dependências

## Objetivo

Expor, a partir do estado real do ambiente (não de suposição), quais
dependências declaradas em `requirements.txt` estão sem versão fixa, quais
estão ausentes do ambiente de execução e quais têm versão instalada
diferente da fixada — sem usar nenhum serviço externo, API paga ou consulta
de rede (PyPI Advisory DB, OSV, safety-db etc.), em conformidade com a
regra do `CLAUDE.md` de não usar serviços externos sem Douglas pedir.

## Justificativa real (não hipotética)

`requirements.txt` deste repositório, hoje, declara 19 dependências e
**nenhuma das 19 (0%) tem versão fixa com `==`**:

```
fastapi
uvicorn
sqlalchemy
pydantic
pydantic-settings
PyJWT
passlib
bcrypt
python-dotenv
python-multipart
email-validator
httpx
sentry-sdk
pillow
python-magic
werkzeug
celery
requests
pytest
```

Isso significa que um `pip install -r requirements.txt` futuro pode trazer
qualquer versão de qualquer uma dessas 19 bibliotecas, silenciosamente, sem
nenhum aviso. Não é um risco hipotético: é o estado literal do arquivo
real do repositório nesta data. `DependencyAuditService` resolve isso
reportando essa divergência (e divergências de versão instalada vs. fixada,
quando houver fixação) a partir de introspecção real do ambiente, em vez de
depender de alguém revisar manualmente o `requirements.txt` a cada PR.

## O que foi entregue

`DependencyAuditService` (`src/app/services/dependency_audit_service.py`),
sem duplicar lógica já existente:

- `_parse_requirements_text()` — usa `packaging.requirements.Requirement`
  (biblioteca local, sem rede; já é dependência transitiva declarada do
  `pytest`, confirmado via `pip show pytest` → `Requires: ..., packaging,
  ...` — nenhuma dependência nova foi adicionada ao projeto) para
  classificar cada linha declarada como fixada (`==` presente) ou não
  fixada, ignorando linhas em branco/comentário/`-r`, e registrando
  `parse_error` para linhas inválidas.
- `_installed_version()` — usa `importlib.metadata.version()` (biblioteca
  padrão do Python, sem rede) para obter a versão de fato instalada,
  tratando `PackageNotFoundError` como pacote ausente.
- `audit()` — agrega: total declarado, contagem fixada/não fixada, pacotes
  ausentes, divergências de versão fixada vs. instalada, e a lista de
  "issues" (sempre inclui ausência/divergência; inclui não-fixação apenas
  quando `dependency_audit_warn_on_unpinned=True`, o padrão).
- `render_markdown()` — renderiza o snapshot acima como Markdown legível,
  mesmo padrão das Missões 44/48.

Campo novo em `Settings` (`src/app/core/config.py`):

- `dependency_audit_warn_on_unpinned: bool = True` — nunca deve ser
  `False` em produção (com 100% das dependências hoje não fixadas, desligar
  isso em produção elimina o único sinal de alerta existente sobre o
  problema).

Nova regra em `validate_settings()` (perfil produção,
`src/app/core/config_profiles.py`): `dependency_audit_warn_on_unpinned=False`
em produção gera um issue. `CONFIG_SCHEMA_VERSION` sobe de `1.7.0` para
`1.8.0`.

Duas rotas novas em `/dependency-audit` (`safe_router.py` registra o
módulo, imediatamente após `"documentation"`):

- `GET /api/v1/dependency-audit/live` — snapshot completo em JSON
  (`DependencyAuditResponse`).
- `GET /api/v1/dependency-audit/markdown` — o mesmo snapshot renderizado
  como Markdown (`text/markdown`).

### Arquivos novos

| Arquivo | Conteúdo | Linhas |
|---|---|---|
| `src/app/services/dependency_audit_service.py` | `DependencyAuditService` | 209 |
| `src/app/schemas/dependency_audit.py` | `DependencyEntry`, `DependencyAuditResponse` | 26 |
| `src/app/api/routes/dependency_audit.py` | rotas `/dependency-audit/live` e `/dependency-audit/markdown` | 18 |
| `src/app/tests/test_m49_dependency_audit_service.py` | 18 testes novos | 197 |

### Arquivos modificados

```
$ git diff --stat -- CONFIG_CHANGELOG.md src/app/api/safe_router.py src/app/core/config.py src/app/core/config_profiles.py src/app/tests/test_m48_documentation_service.py
 CONFIG_CHANGELOG.md                             | 41 +++++++++++++++++++++++++
 src/app/api/safe_router.py                      |  1 +
 src/app/core/config.py                          |  6 ++++
 src/app/core/config_profiles.py                 | 13 +++++++-
 src/app/tests/test_m48_documentation_service.py |  7 ++++-
 5 files changed, 66 insertions(+), 2 deletions(-)
```

(A alteração em `test_m48_documentation_service.py` é a correção de um bug
real encontrado durante esta missão — ver seção Incidentes abaixo.)

## Evidência

### Teste novo, isolado

```
$ python -m pytest -q app/tests/test_m49_dependency_audit_service.py
..................                                                        [100%]
18 passed, 1 warning in 3.78s
```

### Contagem total da suíte

```
$ python -m pytest -q --collect-only
526 tests collected in 4.37s
```

(508 testes existentes após a Missão 48 + 18 testes novos da Missão 49 = 526.)

### 3 execuções completas da suíte (exigência do CLAUDE.md)

A suíte foi dividida em 16 sub-lotes de até 7 arquivos cada
(`split -l 7 -d`), uma chamada de shell por sub-lote (sem encadear múltiplos
lotes na mesma chamada — disciplina adotada nesta missão depois de
instabilidades de sandbox ao tentar lotes maiores ou múltiplos lotes por
chamada; ver Incidentes). Os 16 sub-lotes somam exatamente os 526 testes
coletados, em todas as 3 execuções.

**Execução 1:**

```
lote 00: 16 passed
lote 01: 23 passed
lote 02: 24 passed
lote 03: 18 passed
lote 04: 23 passed
lote 05: 17 passed
lote 06: 129 passed
lote 07: 109 passed   ← 1 falha real encontrada e corrigida antes deste resultado (ver Incidentes)
lote 08: 19 passed
lote 09: 22 passed
lote 10: 18 passed
lote 11: 32 passed
lote 12: 24 passed
lote 13: 25 passed
lote 14: 16 passed
lote 15: 11 passed
TOTAL: 526 passed, 0 failed
```

**Execução 2:**

```
lote 00: 16 passed
lote 01: 23 passed
lote 02: 24 passed
lote 03: 18 passed
lote 04: 23 passed
lote 05: 17 passed
lote 06: 129 passed
lote 07: 109 passed
lote 08: 19 passed
lote 09: 22 passed
lote 10: 18 passed
lote 11: 32 passed
lote 12: 24 passed
lote 13: 25 passed
lote 14: 16 passed
lote 15: 11 passed
TOTAL: 526 passed, 0 failed
```

**Execução 3:**

```
lote 00: 16 passed
lote 01: 23 passed
lote 02: 24 passed
lote 03: 18 passed
lote 04: 23 passed
lote 05: 17 passed
lote 06: 129 passed
lote 07: 109 passed
lote 08: 19 passed
lote 09: 22 passed
lote 10: 18 passed
lote 11: 32 passed
lote 12: 24 passed
lote 13: 25 passed
lote 14: 16 passed
lote 15: 11 passed
TOTAL: 526 passed, 0 failed
```

## Incidentes durante o desenvolvimento

1. **Bug real (não flaky) encontrado e corrigido durante a Execução 1,
   lote 07**: `test_m48_documentation_service.py::test_config_schema_version_bumped_for_mission_48`
   falhou deterministicamente (`1 failed, 108 passed`) porque fazia
   `assert CONFIG_SCHEMA_VERSION == "1.7.0"` por igualdade estrita de
   string — e esta própria missão (49) já tinha avançado a versão para
   `"1.8.0"` antes deste ponto da evidência. Não é flake: é um defeito de
   design que eu mesmo introduzi na Missão 48 (fixar para sempre um valor
   "atual" como se nunca mudasse). **Correção**: convertido para
   comparação por tupla "maior ou igual" —
   `tuple(int(p) for p in CONFIG_SCHEMA_VERSION.split(".")) >= (1, 7, 0)`
   — e o lote 07 foi re-executado, confirmando `109 passed, 1 warning`.
   O mesmo padrão preventivo foi aplicado proativamente ao teste análogo
   desta própria missão
   (`test_config_schema_version_bumped_for_mission_49`, comparação
   `>= (1, 8, 0)`), para que o próximo bump de versão (Missão 50) não
   reproduza o mesmo defeito. A Execução 1 reportada acima já é a versão
   corrigida (109 passed no lote 07, sem falha).

2. **Instabilidade recorrente de infraestrutura do sandbox**: a mesma
   classe de instabilidade já documentada nos relatórios das Missões
   47/48 (`bash failed on resume, create, and re-resume...` /
   `process ... already running`) ocorreu novamente nesta missão, inclusive
   ao tentar lotes maiores (15–17 arquivos) e ao tentar encadear múltiplos
   lotes pequenos em uma única chamada de shell. Foi confirmado
   experimentalmente que processos em segundo plano (`nohup ... &
   disown`) não sobrevivem entre chamadas separadas da ferramenta de
   shell — descartando isso como estratégia de contorno. **Disciplina
   adotada**: sub-lotes pequenos (≤7 arquivos) e exatamente uma chamada de
   shell por sub-lote, sem laços/encadeamento. Essa disciplina eliminou
   o problema de forma confiável pelo restante da missão — nenhum
   congelamento ocorreu depois de adotada de forma estrita. Nenhuma perda
   de trabalho ocorreu nos congelamentos que precederam a adoção da
   disciplina (apenas o lote em andamento, ainda não registrado em log,
   precisou ser refeito).

3. **Dois incidentes de ferramenta (sem perda de trabalho)**: as
   ferramentas `Edit`/`Read`/`Write` (que só alcançam a pasta Windows
   montada do Cowork) não alcançam `/tmp/work/repo` (onde todo o trabalho
   real das Missões 41–50 vive). Em um dos casos, um arquivo de schema foi
   criado por engano na pasta de scratchpad do Windows via `Write` em vez
   de via bash; corrigido recriando o arquivo correto via heredoc
   diretamente em `/tmp/work/repo/src/app/schemas/dependency_audit.py`.

## Critério de aceite

- [x] `DependencyAuditService` implementado, usando apenas bibliotecas
      locais/offline (`packaging`, já transitiva de `pytest`;
      `importlib.metadata`, biblioteca padrão) — sem nenhuma chamada de
      rede, API paga ou serviço externo.
- [x] Flag de aviso de não-fixação com regra de produção em
      `validate_settings()`.
- [x] Duas rotas novas (`/dependency-audit/live`, `/dependency-audit/markdown`).
- [x] `CONFIG_SCHEMA_VERSION` 1.7.0 → 1.8.0, `CONFIG_CHANGELOG.md`
      atualizado.
- [x] 18 testes novos, 100% passando isoladamente.
- [x] 3 execuções completas da suíte total (526 testes), 0 falhas em todas
      as 3 (a única falha observada na Execução 1 foi diagnosticada como
      bug real — não flake —, corrigida, e a evidência reportada já reflete
      a correção).
- [x] Bug pré-existente da Missão 48 (assertiva de versão por igualdade
      estrita) corrigido nesta missão, com o mesmo padrão aplicado
      proativamente ao teste equivalente da Missão 49.
- [x] Apenas arquivos relevantes da Missão 49 preparados para commit
      (nenhum `git add -A`).

## Próximos passos

Commit local na branch `missao-49-auditoria-dependencias` (sem push — por
instrução de Douglas, o push de todas as 10 missões será feito por ele
pessoalmente ao final). Prosseguir para a Missão 50 — Certificação
Platinum v1.3.
