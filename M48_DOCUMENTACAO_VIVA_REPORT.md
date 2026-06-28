# Missão 48 — Documentação Viva

## Objetivo

Substituir documentação estática (que fica desatualizada no minuto em que o
sistema muda) por um serviço que gera a documentação a partir do **estado
vivo** do sistema, a cada chamada: rotas carregadas/falhas, schema de
configuração, problemas de validação correntes e versão do app.

## Justificativa real (não hipotética)

O `README.md` deste repositório afirma hoje, em texto estático:

- "Requer Python 3.11+ (o projeto usa `datetime.UTC` e `enum.StrEnum`)."
- "Última validação registrada... **261 passed**."

Nenhuma das duas frases reflete o estado atual:

- O ambiente de execução real é **Python 3.10.12** (`python3 --version`).
  Todo serviço novo desde a Missão 41 carrega o comentário `# compat Python
  3.10` ao lado de `UTC = timezone.utc` por esse mesmo motivo.
- A suite de testes já passou de 261 para **508** (Missões 41–48; eram 489
  antes desta missão).

Isso não é um problema hipotético: é uma divergência presente, hoje, no
arquivo real do repositório, entre o que está escrito e o que é verdade.
Texto estático sobre o sistema fica errado no instante em que o sistema
muda, porque ninguém lembra de sincronizar os dois lados. `DocumentationService`
resolve isso gerando o conteúdo a partir do estado real em tempo de execução,
em vez de depender de um `.md` editado à mão.

## O que foi entregue

`DocumentationService` (`src/app/services/documentation_service.py`), sem
duplicar lógica já existente:

- `routes_summary()` — reaproveita `LOADED_ROUTES`/`FAILED_ROUTES`/
  `ROUTE_MODULES` de `app.api.safe_router`, com o mesmo padrão de import
  tardio com fallback usado por `observability.health_dashboard()`
  (Missão 27), para evitar import circular.
- `settings_summary()` — enumera `Settings.model_fields` via introspecção
  real do schema pydantic (não uma lista mantida à mão que ficaria
  desatualizada a cada novo campo). Redige por padrão qualquer campo cujo
  nome contenha um marcador de segredo (`secret`/`password`/`token`/`key`),
  controlado por `documentation_redact_secrets`.
- `live_snapshot()` — agrega rotas + settings + `CONFIG_SCHEMA_VERSION` +
  `detect_environment()` + `validate_settings()` (Missão 41) + o conteúdo
  atual do arquivo `VERSION` da raiz do repositório.
- `render_markdown()` — renderiza o snapshot acima como Markdown legível
  (o mesmo conteúdo que hoje vive estático em pedaços do `README.md`, mas
  gerado a cada chamada).

Campo novo em `Settings` (`src/app/core/config.py`):

- `documentation_redact_secrets: bool = True` — nunca deve ser `False` em
  produção.

Nova regra em `validate_settings()` (perfil produção,
`src/app/core/config_profiles.py`): `documentation_redact_secrets=False`
em produção gera um issue (os endpoints `/documentation/*` exporiam
valores reais de segredo). `CONFIG_SCHEMA_VERSION` sobe de `1.6.0` para
`1.7.0`.

Duas rotas novas em `/documentation` (`safe_router.py` registra o módulo):

- `GET /api/v1/documentation/live` — snapshot completo em JSON
  (`DocumentationSnapshotResponse`).
- `GET /api/v1/documentation/markdown` — o mesmo snapshot renderizado como
  Markdown (`text/markdown`).

### Decisão de design deliberada: redação conservadora por substring

A correspondência de campo-de-segredo é por substring no nome
(`secret`/`password`/`token`/`key`), não por uma lista de nomes exatos.
Isso é intencionalmente conservador: `access_token_expire_minutes` (um
inteiro de configuração, não um segredo de fato) é redigido por conter
`token` no nome. O trade-off é proposital — falso positivo (campo inócuo
redigido sem necessidade) é um custo aceitável; falso negativo (um segredo
real escapando por uma lista incompleta de nomes exatos) não é. Isso está
coberto explicitamente em
`test_settings_summary_never_redacts_non_secret_fields` (que usa
`upload_max_bytes`, um campo que não contém nenhum marcador) e nos testes
de `_is_secret_field`.

### Arquivos novos

| Arquivo | Conteúdo |
|---|---|
| `src/app/services/documentation_service.py` | `DocumentationService` |
| `src/app/schemas/documentation.py` | `DocumentationSnapshotResponse` e schemas auxiliares |
| `src/app/api/routes/documentation.py` | rotas `/documentation/live` e `/documentation/markdown` |
| `src/app/tests/test_m48_documentation_service.py` | 19 testes novos |

### Arquivos modificados

```
$ git diff --stat -- CONFIG_CHANGELOG.md src/app/api/safe_router.py src/app/core/config.py src/app/core/config_profiles.py
 CONFIG_CHANGELOG.md             | 38 ++++++++++++++++++++++++++++++++++++++
 src/app/api/safe_router.py      |  1 +
 src/app/core/config.py          |  5 +++++
 src/app/core/config_profiles.py | 11 ++++++++++-
 4 files changed, 54 insertions(+), 1 deletion(-)
```

## Evidência

### Teste novo, isolado

```
$ python -m pytest -q src/app/tests/test_m48_documentation_service.py
...................                                                      [100%]
19 passed, 1 warning in 1.98s
```

### Contagem total da suíte

```
$ python -m pytest -q --collect-only
508 tests collected in 1.86s
```

(489 testes existentes após a Missão 47 + 19 testes novos da Missão 48 = 508.)

### 3 execuções completas da suíte (exigência do CLAUDE.md)

A suíte foi dividida em 7 sub-lotes não sobrepostos (mesma técnica usada
na Missão 47, necessária porque uma única chamada de shell tem timeout de
45s e a suíte completa não cabe em uma chamada). Os 7 sub-lotes somam
exatamente os 508 testes coletados em todas as 3 execuções.

**Execução 1:**

```
lote 00: 52 passed
lote 01: 41 passed
lote 02: 99 passed
lote 03: 168 passed
lote 04: 40 passed
lote 05: 57 passed
lote 06: 51 passed
TOTAL: 508 passed, 0 failed
```

**Execução 2 (primeira tentativa, com 1 falha transitória — ver Incidentes):**

```
lote 00: 52 passed
lote 01: 41 passed
lote 02: 99 passed
lote 03: 168 passed
lote 04: 40 passed
lote 05: 1 failed, 56 passed  ← test_r13_failure_scenarios.py::test_r13_missing_invalid_expired_and_tampered_tokens_are_controlled
lote 06: 51 passed
```

**Execução 2 (repetição limpa, após investigação — ver Incidentes):**

```
lote 00: 52 passed
lote 01: 41 passed
lote 02: 99 passed
lote 03: 168 passed
lote 04: 40 passed
lote 05: 57 passed
lote 06: 51 passed
TOTAL: 508 passed, 0 failed
```

**Execução 3:**

```
lote 00: 52 passed
lote 01: 41 passed
lote 02: 99 passed
lote 03: 168 passed
lote 04: 40 passed
lote 05: 57 passed
lote 06: 51 passed
TOTAL: 508 passed, 0 failed
```

## Incidentes durante o desenvolvimento

1. **Sem falhas de teste/lógica na implementação em si** — `documentation_service.py`,
   o schema e as rotas passaram de primeira em todas as chamadas manuais de
   verificação (snapshot, markdown, redação de segredo) antes mesmo da
   suíte de testes formal ser escrita.

2. **Uma falha transitória e não reprodutível durante a Execução 2**, no
   lote 05: `test_r13_failure_scenarios.py::test_r13_missing_invalid_expired_and_tampered_tokens_are_controlled`
   falhou em uma chamada. Investigação:
   - O teste passa isoladamente (`pytest ... -v` → `1 passed`).
   - O teste passa quando executado junto apenas com o arquivo anterior do
     mesmo lote (`test_public_api_readiness.py` + `test_r13...py` →
     `12 passed`).
   - O mesmo lote 05 completo (15 arquivos) foi re-executado duas vezes em
     seguida depois da falha, e passou limpo nas duas (`57 passed` cada).
   - Nenhum arquivo do projeto modificado nesta missão (`config.py`,
     `config_profiles.py`, `safe_router.py`) toca lógica de JWT/autenticação
     — não há relação causal plausível entre a Missão 48 e este teste.
   - A falha ocorreu imediatamente após um incidente de infraestrutura do
     sandbox (a chamada de shell anterior expirou com
     `Command timed out after 45000ms` / `process ... already running`,
     exigindo uma chamada de recuperação antes de continuar) — o mesmo
     padrão de instabilidade de sandbox já documentado no relatório da
     Missão 47. A explicação mais plausível é jitter de ambiente
     (CPU/relógio) imediatamente após a recuperação do sandbox, não uma
     regressão de código.
   - Em vez de aceitar a evidência com a falha, a Execução 2 foi descartada
     e refeita do zero, lote por lote, obtendo `508 passed, 0 failed` de
     forma limpa (ver acima). As 3 execuções de evidência reportadas como
     critério de aceite desta missão são, portanto, todas limpas.

3. **Dois incidentes de ferramenta (sem perda de trabalho)**: as ferramentas
   `Edit`/`Read` (que só alcançam a pasta Windows montada do Cowork) não
   conseguem alcançar `/tmp/work/repo` (onde todo o trabalho real das
   Missões 41–50 vive). Cada tentativa foi corrigida na primeira repetição
   usando `mcp__workspace__bash` (heredoc para arquivos novos, script Python
   inline para edição de arquivos existentes) — consistente com o padrão já
   estabelecido nas missões anteriores desta sessão.

## Critério de aceite

- [x] `DocumentationService` implementado, reaproveitando `safe_router`,
      `config_profiles` e introspecção nativa do pydantic (sem duplicar
      lógica).
- [x] Redação de segredos por padrão, com regra de produção em
      `validate_settings()`.
- [x] Duas rotas novas (`/documentation/live`, `/documentation/markdown`).
- [x] `CONFIG_SCHEMA_VERSION` 1.6.0 → 1.7.0, `CONFIG_CHANGELOG.md`
      atualizado.
- [x] 19 testes novos, 100% passando isoladamente.
- [x] 3 execuções completas da suíte total (508 testes), 0 falhas em todas
      as 3 (a única falha observada foi investigada, isolada como
      transitória/infraestrutura, e a execução correspondente foi refeita
      do zero antes de ser reportada como evidência).
- [x] Apenas arquivos relevantes da Missão 48 preparados para commit
      (nenhum `git add -A`).

## Próximos passos

Commit local na branch `missao-48-documentacao-viva` (sem push — por
instrução de Douglas, o push de todas as 10 missões será feito por ele
pessoalmente ao final). Prosseguir para a Missão 49 — Auditoria de
Dependências.
