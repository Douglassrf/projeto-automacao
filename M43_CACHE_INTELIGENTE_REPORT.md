# Missão 43 — Cache Inteligente

Data UTC: 2026-06-27.
Branch: `missao-43-cache-inteligente` (stack: `missao-41-...` → `missao-42-fila-inteligente` → `missao-43-cache-inteligente`).
Autorização de escopo: Douglas autorizou explicitamente suspender a regra
"Fase Ômega apenas / sem funcionalidade nova" do `CLAUDE.md` para o conjunto
de Missões 41–50, atribuídas ao Claude ("essas são as suas"). Push/PR desta
missão fica para Douglas executar pessoalmente ao final das 10 missões
("vou fazer o push quando terminar todas as missão, prosseguir...").

## Objetivo (conforme especificação do Douglas)

Cache zero-custo (sem Redis/KeyDB pago) com TTL configurável, invalidação
por namespace, e métricas de hit/miss — preparado para troca futura por um
backend real sem mudar quem chama.

## O que foi entregue

### 1. Camada de cache (`CacheService`, SQLite)

Novo módulo `src/app/services/cache_service.py`. Duas tabelas novas em
`src/app/domain/models.py`:

- **`CacheEntry`** (`cache_entries`): linha por `(namespace, cache_key)` —
  `value_json` (serializado via `json.dumps`), `hits`, `expires_at`
  (nullable = sem expiração), `created_at`, `last_accessed_at`.
- **`CacheStat`** (`cache_stats`): contadores cumulativos **por namespace**
  (`total_hits`, `total_misses`, `total_sets`, `total_evictions`,
  `total_expired_purged`) — tabela separada de `cache_entries` de propósito,
  para que a estatística sobreviva à remoção das linhas que a geraram (uma
  entrada evitada ou expirada não deve "apagar" o que ela já contabilizou).

Contrato público de `CacheService(db: Session)`:

```python
get(key, *, namespace="default") -> Any | None
get_entry(key, *, namespace="default") -> CacheEntry | None  # desambigua valor=None de miss
set(key, value, *, namespace="default", ttl_seconds=None) -> CacheEntry
delete(key, *, namespace="default") -> bool
invalidate_namespace(namespace) -> int
clear() -> int
purge_expired(*, namespace=None) -> int
stats(*, namespace=None) -> dict
```

**Semântica de TTL:** `ttl_seconds=None` usa o default da configuração
(`cache_default_ttl_seconds`, padrão 300s). `ttl_seconds<=0` é um pedido
explícito de "sem expiração" — diferente do default da configuração, que
precisa ser `>= 1` (`validate_settings`).

**Evicção LRU por namespace:** ao exceder `cache_max_entries_per_namespace`
(padrão 1000) numa namespace, as entradas menos recentemente *acessadas*
(`last_accessed_at`, não frequência de hits) são removidas até caber no
limite — escolha deliberada por simplicidade e determinismo, mesma filosofia
do backoff determinístico da Missão 42.

**Cuidado técnico aplicado (evita um bug real de fuso horário):** todas as
comparações de tempo (expiração, LRU) são feitas via filtro SQL
(`Coluna <= now` dentro de `.filter(...)`), nunca comparando em Python puro
um `datetime` já lido de volta do SQLite contra um `datetime.now(UTC)` novo
— colunas `DateTime` do SQLite voltam *naive* (sem tzinfo) após uma query, e
compará-las contra um valor aware lançaria `TypeError`. Esse é o mesmo padrão
já usado em `QueueService.claim()` (Missão 42), replicado aqui de propósito.

### 2. Schemas e API (`/api/v1/cache/*`)

`src/app/schemas/cache.py`: `CacheSetRequest`, `CacheEntryResponse`,
`CacheDeleteResponse`, `CacheInvalidateRequest`, `CacheInvalidateResponse`,
`CacheStatsResponse`.

`src/app/api/routes/cache.py` — só GET/POST, seguindo a convenção já
confirmada do projeto (`grep` por `@router.delete|@router.put|@router.patch`
em todas as rotas existentes retorna vazio):

| Rota | Verbo | Ação |
|---|---|---|
| `/cache/entries` | POST | grava (set) |
| `/cache/entries/{key}` | GET | lê (get), 404 em miss |
| `/cache/entries/{key}/delete` | POST | remove uma chave |
| `/cache/invalidate` | POST | remove uma namespace inteira |
| `/cache/clear` | POST | remove tudo |
| `/cache/purge-expired` | POST | remove expirados sem precisar de get() |
| `/cache/stats` | GET | estatísticas (globais ou por namespace) |

Registrado em `src/app/api/safe_router.py` (`ROUTE_MODULES`), pelo mecanismo
de auto-discovery já existente — nenhuma mudança em `main.py` foi necessária.

### 3. Configuração (campos novos + validação)

`src/app/core/config.py`: `cache_default_ttl_seconds=300`,
`cache_max_entries_per_namespace=1000`, `cache_backend="sqlite"`.

`src/app/core/config_profiles.py`: `CONFIG_SCHEMA_VERSION` `1.1.0` → `1.2.0`;
novas regras em `validate_settings()` (todos os perfis):
`cache_default_ttl_seconds >= 1`, `cache_max_entries_per_namespace >= 1`.
Entrada correspondente em `CONFIG_CHANGELOG.md`.

### 4. Migração

`src/app/db/init_db.py`: import de `CacheEntry, CacheStat` adicionado;
nenhum `ALTER TABLE` foi necessário — são tabelas novas, criadas do zero por
`Base.metadata.create_all()`. Comentário-marcador deixado no lugar certo
para futuras colunas, seguindo o padrão já estabelecido para `queue_jobs`.

### Arquivos novos

| Arquivo | Conteúdo |
|---|---|
| `src/app/services/cache_service.py` | `CacheService` (get/set/delete/invalidate_namespace/clear/purge_expired/stats) |
| `src/app/schemas/cache.py` | Schemas Pydantic da API de cache |
| `src/app/api/routes/cache.py` | Rotas `/api/v1/cache/*` |
| `src/app/tests/test_m43_intelligent_cache.py` | 28 testes |

### Arquivos modificados

```
$ git diff --stat -- src/app/domain/models.py src/app/core/config.py \
    src/app/core/config_profiles.py src/app/db/init_db.py \
    src/app/api/safe_router.py src/app/tests/test_m42_intelligent_queue.py
 src/app/api/safe_router.py                  |  1 +
 src/app/core/config.py                      |  5 ++++
 src/app/core/config_profiles.py             | 12 ++++++++-
 src/app/db/init_db.py                       |  6 ++++-
 src/app/domain/models.py                    | 41 +++++++++++++++++++++++++++++
 src/app/tests/test_m42_intelligent_queue.py |  6 ++++-
 6 files changed, 68 insertions(+), 3 deletions(-)
```

(`CONFIG_CHANGELOG.md` ganhou a seção `1.2.0` — não capturado pelo
`diff --stat` acima porque o arquivo é tratado separadamente abaixo.)

## Compatibilidade

Nenhuma variável de ambiente nova é exigida — os três campos novos têm
defaults equivalentes a "cache habilitado com TTL de 5 minutos e até 1000
entradas por namespace", e nenhum código existente antes desta missão usava
cache (confirmado por varredura prévia: zero ocorrências de infraestrutura
de cache no repositório).

## Evidência — suíte completa, 4 execuções consecutivas

Comando (replica `pytest.ini` + shim ffmpeg do `conftest.py`):

```
cd /tmp/work/repo && PATH="$PWD/tools:$PATH" python -m pytest -q
```

**Execução 1:** `393 passed, 1 warning in 24.89s`
**Execução 2:** `393 passed, 1 warning in 24.01s`
**Execução 3:** `393 passed, 1 warning in 31.11s`

**Execução 4 (saída completa capturada):**
```
........................................................................ [ 18%]
........................................................................ [ 36%]
........................................................................ [ 54%]
........................................................................ [ 73%]
........................................................................ [ 91%]
.................................                                        [100%]
=============================== warnings summary ===============================
../../../sessions/modest-zealous-noether/.local/lib/python3.10/site-packages/fastapi/testclient.py:1
  /sessions/modest-zealous-noether/.local/lib/python3.10/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
393 passed, 1 warning in 34.15s
```

Baseline antes da Missão 43 (mesma execução, mesmo ambiente): `365 passed`
(Missão 42, já com o teste de acento corrigido). Delta: `+28` (os 28 testes
novos de `test_m43_intelligent_cache.py`). O único warning
(`StarletteDeprecationWarning`) já existia antes desta missão.

### Execução isolada do arquivo novo

```
$ PATH="$PWD/tools:$PATH" python -m pytest -q src/app/tests/test_m43_intelligent_cache.py
............................                                             [100%]
28 passed, 1 warning in 5.55s
```

## Incidentes durante o desenvolvimento (e correções)

1. **Erro de teste (autocausado), corrigido antes do commit**: o primeiro
   teste para a desambiguação "valor `None` armazenado vs. miss"
   (`test_get_value_none_is_a_hit_not_a_miss_get_entry_disambiguates`) chamava
   `service.get()` e depois `service.get_entry()` na mesma chave e esperava
   `hits == 1` — mas cada chamada é um *hit* real e independente (a linha foi
   encontrada viva nas duas vezes), então o total correto é `2`, não `1`.
   Corrigida a asserção (`== 2`), com um comentário explicando o motivo.
2. **Regressão de forward-compatibility detectada e corrigida (causa raiz na
   Missão 42, não nesta missão)**: `test_m42_intelligent_queue.py` tinha
   `test_config_schema_version_bumped_for_mission_42` fixando
   `CONFIG_SCHEMA_VERSION == "1.1.0"` (igualdade exata). Como a Missão 43
   bumpa o esquema para `"1.2.0"`, esse teste passou a falhar — não por uma
   regressão real, mas porque a asserção foi escrita de um jeito que não
   sobrevive a bumps futuros (e o `CONFIG_SCHEMA_VERSION` é estado global que
   só cresce, mission após mission, na mesma suíte). Corrigido trocando `==`
   por uma comparação de versão (`tuple(int(p) ...) >= (1, 1, 0)`), no mesmo
   espírito do padrão já mais robusto usado em `test_m41_centralized_config.py`
   (que nunca fixa o valor absoluto). Aplicado proativamente o mesmo padrão
   ao teste equivalente desta missão
   (`test_config_schema_version_bumped_for_mission_43`), para não repetir o
   mesmo bug quando a Missão 44 bumpar o esquema de novo.
3. Nenhum outro incidente: as quatro mudanças de fundação (models.py,
   config.py, config_profiles.py, init_db.py) foram verificadas por `grep`
   antes da primeira execução de teste, e passaram de primeira — a única
   correção de lógica necessária foi a do item 1 (teste, não código de
   produção).

## Critério de aceite

Cache zero-custo funcional com TTL configurável (default + override por
chamada + sentinel "sem expiração"), invalidação por namespace (`delete`,
`invalidate_namespace`, `clear`), evicção determinística (LRU por namespace)
e métricas de hit/miss/sets/evictions/expired_purged por namespace e
globais, expostas tanto via `CacheService` quanto via API REST
(`/api/v1/cache/*`, só GET/POST). Suíte completa estável em `393 passed` por
4 execuções consecutivas.

## Próximos passos

Comentado/commitado apenas localmente, na branch `missao-43-cache-inteligente`
— sem push/PR nesta etapa, por instrução do Douglas (push/PR de todas as
missões 41–50 será feito por ele, de uma vez, ao final). Em seguida, Missão
44 (Diagnóstico Automático).
