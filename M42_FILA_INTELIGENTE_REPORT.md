# Missão 42 — Gerenciador Inteligente de Filas

Data UTC: 2026-06-27.
Branch: `missao-42-fila-inteligente` (sobre `missao-41-config-centralizada`).
Autorização de escopo: mesma da Missão 41 — Douglas autorizou suspender a
regra "Fase Ômega apenas / sem funcionalidade nova" do `CLAUDE.md` para o
conjunto de Missões 41–50.

## Objetivo (conforme especificação do Douglas)

Backoff exponencial para retries; detecção de filas travadas/inanição;
dead-letter queue com reprocessamento manual; métricas de saúde da fila.
Construído sobre o `QueueService` (SQLite) zero-custo já existente — sem
introduzir Redis/KeyDB real, mantendo o contrato compatível para troca futura.

## O que foi entregue

### 1. Backoff exponencial determinístico

Nova função pura `compute_backoff_seconds(*, attempts, job_id, base_seconds,
max_seconds)` em `queue_service.py`:

```python
def compute_backoff_seconds(*, attempts, job_id, base_seconds, max_seconds):
    attempts = max(1, attempts)
    base_seconds = max(0, base_seconds)
    exponential = base_seconds * (2 ** (attempts - 1))
    jitter = (job_id % base_seconds) if base_seconds > 0 else 0
    return float(min(exponential + jitter, max_seconds))
```

Sem `random`: o jitter é `job_id % base_seconds`, determinístico e
reprodutível em teste, mas ainda espalha jobs que falham juntos. `fail()`
agora grava `next_attempt_at = now + delay` quando `retry=True`, e `claim()`
só reclama jobs em `retry` cujo `next_attempt_at` já passou (ou é `NULL`,
para compatibilidade com linhas migradas de antes da Missão 42).

### 2. Dead-letter queue com reprocessamento manual

Novo método `requeue_dead_letter(job_id, reset_attempts=True)`: só aceita
jobs com `status="dead"` (levanta `ValueError` nos demais), devolve o job
para `status="queued"`, limpa `locked_by`/`locked_at`/`next_attempt_at`, e
prefixa `error_message` com `"[reenviado manualmente] "` para preservar o
histórico do erro original. Novo endpoint `POST
/queue/jobs/{job_id}/requeue` (400 se o job não estiver morto).

### 3. Métricas de saúde da fila

Novo método `health_report()`: detecta jobs presos (`status="running"` com
`locked_at` mais antigo que `queue_lock_timeout_seconds`), jobs famintos
(`status` em `queued`/`retry` esperando há mais de
`queue_starvation_threshold_seconds` desde `created_at`), e filas com taxa de
falha alta (`dead / (done + dead) > queue_failure_rate_threshold`, só
calculado com amostra mínima de 5 jobs finalizados, para não disparar alarme
falso em filas novas/pequenas). Retorna contagens por fila
(`per_queue`) e mensagens de aviso legíveis. Novo endpoint `GET
/queue/health`. `GET /queue/stats` (já existente) passou a incluir `healthy`
e `warnings` no mesmo payload, sem remover nenhum campo anterior.

### 4. Configuração e validação (reaproveitando a Missão 41)

Quatro campos novos em `Settings`: `queue_retry_backoff_base_seconds` (5),
`queue_retry_backoff_max_seconds` (300), `queue_starvation_threshold_seconds`
(600), `queue_failure_rate_threshold` (0.5). Quatro regras novas em
`validate_settings()`: base/máximo de backoff positivos e coerentes entre si,
limiar de inanição positivo, e taxa de falha em `(0.0, 1.0]`.
`CONFIG_SCHEMA_VERSION` subiu de `1.0.0` para `1.1.0` (entrada nova em
`CONFIG_CHANGELOG.md`) — nenhum valor antigo muda de significado.

### Arquivos novos

| Arquivo | Conteúdo |
|---|---|
| `src/app/tests/test_m42_intelligent_queue.py` | 33 testes |

### Arquivos modificados

| Arquivo | Mudança |
|---|---|
| `src/app/domain/models.py` | +5: campos `locked_at`/`next_attempt_at` em `QueueJob` |
| `src/app/core/config.py` | +5: 4 campos novos de configuração de fila |
| `src/app/core/config_profiles.py` | +22/-1: 4 regras novas + `CONFIG_SCHEMA_VERSION` 1.1.0 |
| `src/app/db/init_db.py` | +11: migração leve de coluna (`next_attempt_at`) |
| `src/app/services/queue_service.py` | +142/-2: backoff, requeue, health_report |
| `src/app/schemas/queue.py` | +16: novos schemas de resposta/request |
| `src/app/api/routes/queue.py` | +18: endpoints `/queue/health` e `/queue/jobs/{id}/requeue` |
| `src/app/tests/conftest.py` | +9: migração de coluna também na fixture de teste (ver Incidentes) |
| `CONFIG_CHANGELOG.md` | +26: entrada da versão 1.1.0 do esquema |

```
$ git diff --stat -- src/app/domain/models.py src/app/core/config.py src/app/core/config_profiles.py src/app/db/init_db.py src/app/services/queue_service.py src/app/schemas/queue.py src/app/api/routes/queue.py src/app/tests/conftest.py CONFIG_CHANGELOG.md
 CONFIG_CHANGELOG.md               |  26 +++++++
 src/app/api/routes/queue.py       |  18 +++++
 src/app/core/config.py            |   5 ++
 src/app/core/config_profiles.py   |  22 +++++-
 src/app/db/init_db.py             |  11 +++
 src/app/domain/models.py          |   5 ++
 src/app/schemas/queue.py          |  16 +++++
 src/app/services/queue_service.py | 142 +++++++++++++++++++++++++++++++++++++-
 src/app/tests/conftest.py         |   9 +++
 9 files changed, 252 insertions(+), 2 deletions(-)
```

## Compatibilidade

Nenhuma coluna/campo é removido ou muda de significado. Jobs `retry` com
`next_attempt_at IS NULL` (linhas que já existiam antes desta migração)
continuam sendo reclamados por `claim()` exatamente como antes — o novo
filtro de backoff só passa a valer a partir do próximo `fail(..., retry=True)`
de cada job. `GET /queue/stats` ganhou campos, não removeu nenhum.

## Evidência — suíte completa, 4 execuções consecutivas

Comando:

```
cd /tmp/work/repo && PATH="$PWD/tools:$PATH" python -m pytest -q
```

**Execução 1:**
```
365 passed, 1 warning in 29.35s
```

**Execução 2:**
```
365 passed, 1 warning in 19.04s
```

**Execução 3:**
```
365 passed, 1 warning in 18.08s
```

**Execução 4 (saída completa capturada):**
```
........................................................................ [ 19%]
........................................................................ [ 39%]
........................................................................ [ 59%]
........................................................................ [ 78%]
........................................................................ [ 98%]
.....                                                                    [100%]
=============================== warnings summary ===============================
../../../sessions/modest-zealous-noether/.local/lib/python3.10/site-packages/fastapi/testclient.py:1
  .../fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
365 passed, 1 warning in 25.48s
```

Baseline antes da Missão 42 (suíte completa após a Missão 41): `332 passed`.
Delta: `+33` (os 33 testes novos de `test_m42_intelligent_queue.py`). O único
aviso (`StarletteDeprecationWarning`) já existia antes desta missão e não
está relacionado a esta mudança.

### Isolado (arquivo novo apenas)

```
$ cd /tmp/work/repo && PATH="$PWD/tools:$PATH" python -m pytest -q src/app/tests/test_m42_intelligent_queue.py
.................................                                        [100%]
33 passed, 1 warning in 2.34s
```

## Incidentes durante o desenvolvimento (e correções)

1. **Migração ausente na fixture de teste (regressão real, autocausada)**: ao
   adicionar a coluna `queue_jobs.next_attempt_at`, 18 dos 33 testes novos
   falharam com `sqlalchemy.exc.OperationalError: table queue_jobs has no
   column named next_attempt_at`. Causa: o banco de teste
   (`adintelligence.db`, arquivo SQLite real e persistente, fora do git via
   `.gitignore`) já tinha a tabela `queue_jobs` de sessões de teste
   anteriores, e `tests/conftest.py` só chamava
   `Base.metadata.create_all(bind=engine)` — que cria tabelas ausentes, mas
   não adiciona colunas a tabelas já existentes. Corrigido chamando também
   `_ensure_sqlite_columns()` (o mesmo helper de migração leve já usado em
   produção, em `app/db/init_db.py`) na fixture de sessão
   `ensure_database_schema`. Esta é uma correção de infraestrutura de teste
   legítima e de alcance geral: sem ela, qualquer desenvolvedor (incluindo o
   próprio Douglas, na sua máquina) com um `adintelligence.db` local
   pré-existente veria a mesma falha em qualquer missão futura (43-50) que
   adicionasse uma coluna nova. Confirmado: corrigiu 17 das 18 falhas.
2. **Divergência de acentuação entre teste e código (autocausada, menor)**: a
   18ª falha restante era
   `test_health_report_detects_starving_queued_job` —
   `assert any("inanição" in warning for warning in report["warnings"])`
   retornando `False`. A mensagem de aviso real em `health_report()` usa
   "inanicao" sem acentuação (consistente com o estilo ASCII-only já usado em
   comentários/strings de runtime deste módulo, ex.: "execucao", "ha mais
   de"). Corrigido ajustando a asserção do teste para a string real
   ("inanicao"), em vez de alterar a string de runtime — evita reabrir uma
   decisão de estilo de string que não faz parte do escopo desta missão.
   Confirmado: suíte do arquivo voltou a `33 passed`.
3. **Base de branch incorreta (herdado do início da missão, já resolvido
   antes desta sessão)**: a primeira tentativa de criar
   `missao-42-fila-inteligente` não incluía os arquivos da Missão 41
   (`config_profiles.py` inexistente), causando `FileNotFoundError` ao editar
   esse arquivo. Corrigido recriando o branch a partir de
   `missao-41-config-centralizada`. Confirmado nesta sessão: a edição de
   `config_profiles.py` foi aplicada com sucesso na primeira tentativa.

## Critério de aceite

Backoff exponencial determinístico cobrindo crescimento, teto (`max_seconds`),
jitter e proteção contra `base_seconds=0`: testado. `claim()` respeita o
backoff (não reclama antes do prazo, reclama depois, reclama linhas
`next_attempt_at=NULL` pré-migração): testado. Dead-letter queue com
reprocessamento manual, incluindo rejeição de jobs não mortos: testado.
`health_report()` detecta jobs presos, famintos e filas com taxa de falha
alta (com proteção de amostra mínima): testado. Suíte completa estável em
`365 passed` por 4 execuções consecutivas, sem regressão sobre o baseline de
`332 passed` da Missão 41.

## Próximos passos

Commit local no branch `missao-42-fila-inteligente` — push e PR ficam para
Douglas executar manualmente ao final das 10 missões, por instrução
explícita dele. Em seguida, Missão 43 (Cache Inteligente).
