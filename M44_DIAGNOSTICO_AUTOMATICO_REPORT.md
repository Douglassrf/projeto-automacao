# Missão 44 — Diagnóstico Automático

Data UTC: 2026-06-27.
Branch: `missao-44-diagnostico-automatico` (empilhada sobre
`missao-43-cache-inteligente`).
Autorização de escopo: Douglas autorizou explicitamente suspender a regra
"Fase Ômega apenas / sem funcionalidade nova" do `CLAUDE.md` para o conjunto
de Missões 41–50, atribuídas ao Claude ("essas são as suas"). Push/PR ficam
para Douglas executar pessoalmente ao final das 10 missões — esta entrega
é commit local apenas.

## Objetivo

Como a especificação detalhada original desta missão não sobreviveu a uma
compactação de contexto (restou apenas o nome "Diagnóstico Automático"), o
escopo foi derivado por investigação estruturada do código já existente:
agregar, em uma única chamada, sinais de saúde que já existem espalhados em
serviços de missões anteriores (`QueueService.health_report()` da Missão 42,
`CacheService` da Missão 43, `validate_settings()` da Missão 41), somando
dois checks novos que não existiam antes (banco de dados e disco) — sem
inventar funcionalidade fora desse escopo de diagnóstico/leitura.

## O que foi entregue

### 1. `DiagnosticsService` (`src/app/services/diagnostics_service.py`)

Serviço **sem estado novo**: cada chamada recalcula um snapshot fresco a
partir do estado atual do banco, da fila, do cache e da configuração — não
há tabela de histórico nem agendador (decisão deliberada, para manter o
escopo estritamente *diagnóstico/leitura*, sem se sobrepor à futura Missão
45 — Gerenciamento de Recursos — que cuidará de enforcement/ação ativa).

Cinco checks, cada um retornando um `DiagnosticCheck(name, status, message,
details)` com `status` em `"ok" | "warning" | "critical"`:

- **`check_database()`**: `SELECT 1` na sessão ativa; `critical` em
  `SQLAlchemyError`, senão `ok`.
- **`check_queue()`**: delega a `QueueService.health_report()` (Missão 42).
  `critical` se `unhealthy_queues` não vazio (falha ativa e contínua de
  taxa de erro); `warning` se houver `stuck_jobs`/`starving_jobs` sem fila
  marcada como `unhealthy` (sintoma transitório/autocurável); senão `ok`.
- **`check_cache()`**: **sondagem funcional real**, não heurística de
  estatística. Grava uma chave de prova em um namespace dedicado
  (`__diagnostics__`), lê de volta, confere igualdade, e apaga a chave —
  tudo via `CacheService` (Missão 43). `critical` se o valor não
  corresponder ou se qualquer etapa lançar exceção; senão `ok`, com
  `stats()` anexado como informação adicional (não como condição de falha
  — decisão deliberada de não inventar limiares arbitrários de taxa de
  acerto, que Douglas nunca especificou e que arriscariam falsos positivos
  em cargas legitimamente pouco repetitivas).
- **`check_config()`**: delega a `validate_settings()` (Missão 41). Sem
  problemas → `ok`. Com problemas → `critical` se o perfil ativo for
  `production`/`testing` (espelha o comportamento real e bloqueante de
  `validate_or_raise()` nesses perfis), senão `warning` (development/staging,
  onde a validação avisa mas não bloqueia).
- **`check_disk()`**: `shutil.disk_usage(diagnostics_disk_path)`. `critical`
  se MB livres < `diagnostics_disk_critical_free_mb`; `warning` se < 
  `diagnostics_disk_warning_free_mb`; senão `ok`.

`run_full_diagnostics()` agrega os cinco em
`{"status": <pior de todos>, "generated_at": <datetime>, "summary": {ok, warning, critical}, "checks": [...]}`,
com ordem de severidade `ok < warning < critical`. `run_check(name)`
despacha por nome (usado pelo endpoint individual), levantando
`UnknownDiagnosticCheckError` (→ 404 na API) para nome desconhecido.

### 2. Schemas e API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/diagnostics/run` | Relatório completo (5 checks agregados) |
| GET | `/api/v1/diagnostics/checks/{name}` | Um check específico por nome; 404 se desconhecido |

Schemas Pydantic em `src/app/schemas/diagnostics.py`:
`DiagnosticCheckResponse {name, status, message, details}` e
`DiagnosticsReportResponse {status, generated_at, summary, checks}`. Rota
registrada em `ROUTE_MODULES` (`src/app/api/safe_router.py`), mesmo
mecanismo de auto-descoberta já usado por `queue`/`cache`. Ambas as rotas
são **GET-only**, consistente com a natureza puramente leitora desta missão
(nenhuma mutação de estado).

### 3. Configuração

Três campos novos em `Settings` (`src/app/core/config.py`):
`diagnostics_disk_path` (default `"."`), `diagnostics_disk_warning_free_mb`
(default `500`), `diagnostics_disk_critical_free_mb` (default `100`).

Três regras novas em `validate_settings()` (todos os perfis):
`diagnostics_disk_warning_free_mb >= 1`; `diagnostics_disk_critical_free_mb
>= 1`; `diagnostics_disk_critical_free_mb` deve ser estritamente menor que
`diagnostics_disk_warning_free_mb` (mesmo raciocínio do par
`queue_retry_backoff_base_seconds`/`_max_seconds` da Missão 42 — evita as
duas faixas colapsarem em uma só). `CONFIG_SCHEMA_VERSION`: `"1.2.0"` →
`"1.3.0"`.

### 4. Migração

Nenhuma — sem nova tabela, sem `ALTER TABLE`. `DiagnosticsService` é
inteiramente derivado de dados e serviços já persistidos por missões
anteriores.

## Arquivos novos

| Arquivo | Conteúdo |
|---|---|
| `src/app/services/diagnostics_service.py` | `DiagnosticsService`, `DiagnosticCheck`, `UnknownDiagnosticCheckError` |
| `src/app/schemas/diagnostics.py` | `DiagnosticCheckResponse`, `DiagnosticsReportResponse` |
| `src/app/api/routes/diagnostics.py` | `GET /diagnostics/run`, `GET /diagnostics/checks/{name}` |
| `src/app/tests/test_m44_automatic_diagnostics.py` | 30 testes |

## Arquivos modificados

```
$ git diff --stat src/app/core/config.py src/app/core/config_profiles.py src/app/api/safe_router.py CONFIG_CHANGELOG.md
 CONFIG_CHANGELOG.md             | 30 ++++++++++++++++++++++++++++++
 src/app/api/safe_router.py      |  1 +
 src/app/core/config.py          |  5 +++++
 src/app/core/config_profiles.py | 19 ++++++++++++++++++-
 4 files changed, 54 insertions(+), 1 deletion(-)
```

## Compatibilidade

Nenhuma variável de ambiente nova é exigida — os três campos novos têm
defaults seguros (`"."`, `500`, `100`) que satisfazem as próprias regras de
validação adicionadas. Nenhum endpoint existente foi alterado.

## Evidência — suíte completa, 4 execuções consecutivas

Comando (replica `pytest.ini` + shim ffmpeg do `conftest.py`):

```
cd /tmp/work/repo && PATH="$PWD/tools:$PATH" python -m pytest -q
```

**Execução 1:**
```
423 passed, 1 warning in 39.57s
```

**Execução 2:**
```
423 passed, 1 warning in 27.84s
```

**Execução 3:**
```
423 passed, 1 warning in 28.51s
```

**Execução 4 (saída completa capturada):**
```
........................................................................ [ 17%]
........................................................................ [ 34%]
........................................................................ [ 51%]
........................................................................ [ 68%]
........................................................................ [ 85%]
...............................................................          [100%]
=============================== warnings summary ===============================
.../fastapi/testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
423 passed, 1 warning in 27.34s
```

**Arquivo novo isolado:**
```
$ PATH="$PWD/tools:$PATH" python -m pytest -q src/app/tests/test_m44_automatic_diagnostics.py
..............................                                           [100%]
30 passed, 1 warning in 8.21s
```

Baseline antes da Missão 44 (mesma execução, mesmo ambiente): `393 passed`.
Delta: `+30` (os 30 testes novos de `test_m44_automatic_diagnostics.py`). O
único aviso (`StarletteDeprecationWarning`) já existia antes da Missão 44 e
é de dependência pré-existente, não relacionado a esta mudança.

## Incidentes durante o desenvolvimento (e correções)

1. **Estado residual no SQLite de desenvolvimento**: uma verificação manual
   end-to-end de `GET /diagnostics/run` (antes de escrever os testes
   automatizados) revelou que o banco `./adintelligence.db` acumula linhas
   de `QueueJob` de execuções de teste de sessões anteriores (o mesmo
   arquivo SQLite é reusado entre sessões de pytest, sem isolamento por
   execução) — o que fazia `check_queue()` reportar `critical` real com
   treze filas residuais das Missões 42/43. Isso não é um bug desta missão
   (confirma que `check_queue()` está corretamente detectando sinais reais
   de `QueueService.health_report()`), mas tornaria os testes automatizados
   não-determinísticos se dependessem do estado acumulado do banco. Corrigido
   adotando o padrão de `monkeypatch` já estabelecido em
   `test_m02a_health.py` (que usa uma `BrokenEngine` falsa) para isolar a
   lógica de mapeamento de severidade desta missão (`check_database`,
   `check_queue`, `check_disk`, `check_config`) do estado real do banco —
   só `check_cache()` usa uma sondagem real (com namespace dedicado e chave
   única por execução), porque seu próprio roundtrip é determinístico por
   construção.
2. Nenhum outro incidente: todas as quatro execuções completas da suíte e a
   execução isolada do arquivo novo passaram de primeira, sem regressão em
   nenhum teste pré-existente.

## Critério de aceite

`DiagnosticsService.run_full_diagnostics()` agrega corretamente os cinco
checks com a lógica de "pior status vence" (`ok < warning < critical`),
confirmado por teste dedicado (`test_run_full_diagnostics_critical_outranks_warning`).
Os dois endpoints novos (`/diagnostics/run`, `/diagnostics/checks/{name}`)
respondem com o formato esperado e 404 corretamente para nome de check
desconhecido. Nenhuma tabela nova foi criada; nenhuma configuração nova
ficou sem validação correspondente em `validate_settings()`.

## Próximos passos

Commit local apenas, na branch `missao-44-diagnostico-automatico` — sem
push/PR, por instrução de Douglas ("vou fazer o push quando terminar todas
as missão"). Em seguida, Missão 45 (Gerenciamento de Resources).
