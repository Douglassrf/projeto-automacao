# Missão 45 — Gerenciamento de Recursos

Data UTC: 2026-06-27.
Autorização de escopo: Douglas autorizou explicitamente suspender a regra
"Fase Ômega apenas / sem funcionalidade nova" do `CLAUDE.md` para o conjunto
de Missões 41–50, atribuídas ao Claude ("essas são as suas").

## Objetivo

Não há texto de especificação de Douglas além do nome da missão (mesma
situação da Missão 44). Por análise do código e do padrão das Missões
41-44, "Gerenciamento de Recursos" foi entendido como: a contraparte de
**ação** da Missão 44 (que é somente leitura/diagnóstico) — um serviço que
de fato libera recursos acumulados pela aplicação: jobs de fila terminais
antigos, entradas de cache expiradas, e relatório de uso de disco dos
diretórios de saída que o próprio projeto escreve.

## Justificativa real (não hipotética)

Consulta direta ao banco de dev/teste durante o desenvolvimento desta
missão encontrou:

```
queue_jobs total: 503
  dead 143
  done 72
  queued 185
  retry 42
  running 61
cache_entries total: 1
```

Os `215` jobs `done`+`dead` são exatamente o tipo de registro que
`purge_old_queue_jobs()` foi desenhado para remover — acúmulo real, não
projetado. `data/campaign_kits` e `data/orchestration_runs` somam ~56 MB em
milhares de arquivos de execuções de teste anteriores, o que
`disk_usage_report()` agora tem como medir.

## O que foi entregue

### 1. `ResourceManagerService` (`src/app/services/resource_manager_service.py`, novo)

- `disk_usage_report()` — percorre 4 diretórios gerenciados
  (`campaign_kits`, `orchestration_runs`, `ugc`, `premium_renders`),
  resolvidos via `safe_project_path()` (mesma função usada pelos 8 serviços
  que efetivamente escrevem nesses caminhos: `video_pipeline.py`,
  `learning_loop.py`, `serverless_render.py`, `hybrid_stack.py`,
  `zero_cost_stack.py`, `war_kit_generator.py`, `premium_render.py`,
  `ugc_processing.py`). Retorna tamanho total em MB e contagem de arquivos
  por diretório.
- `purge_old_queue_jobs(max_age_days=None)` — apaga jobs com status em
  `TERMINAL_STATUSES` (`{"done", "dead"}`, já definido em
  `queue_service.py` — reaproveitado, não redeclarado) cujo `updated_at`
  seja mais antigo que `max_age_days` (default:
  `settings.resource_job_retention_days`, 30 dias). Jobs `queued`/
  `running`/`retry` nunca são tocados, independente da idade.
- `purge_expired_cache()` — delega para `CacheService.purge_expired()`
  (Missão 43), sem duplicar lógica.
- `run_cleanup(max_age_days=None)` — varredura combinada (fila + cache) em
  um único ponto de entrada.

### 2. Configuração (`src/app/core/config.py`, `config_profiles.py`)

Campo novo: `resource_job_retention_days: int = 30`. Regra nova em
`validate_settings()` (todos os perfis): `>= 1`. `CONFIG_SCHEMA_VERSION`
`1.3.0` → `1.4.0`.

### 3. API (`src/app/schemas/resources.py`, `src/app/api/routes/resources.py`, novos)

Três rotas em `/resources`, registradas em `safe_router.py`
(`ROUTE_MODULES`), seguindo o padrão `POST` + `Query()` já estabelecido em
`cache.py` para ações mutáveis simples (não há schema de request body):

| Rota | Método | Função |
|---|---|---|
| `/resources/disk-usage` | GET | `disk_usage_report()` |
| `/resources/queue-jobs/purge` | POST (`?max_age_days=`) | `purge_old_queue_jobs()` |
| `/resources/cleanup` | POST (`?max_age_days=`) | `run_cleanup()` |

### Arquivos novos

| Arquivo | Conteúdo |
|---|---|
| `src/app/services/resource_manager_service.py` | Serviço de limpeza/relatório |
| `src/app/schemas/resources.py` | 4 schemas de resposta |
| `src/app/api/routes/resources.py` | 3 rotas |
| `src/app/tests/test_m45_resource_management.py` | 25 testes |

### Arquivos modificados

```
$ git diff --stat -- src/app/core/config.py src/app/core/config_profiles.py src/app/api/safe_router.py
 src/app/api/safe_router.py      | 1 +
 src/app/core/config.py          | 3 +++
 src/app/core/config_profiles.py | 8 +++++++-
 3 files changed, 11 insertions(+), 1 deletion(-)
```

## Evidência — suíte completa, 3 execuções consecutivas

**Nota sobre o método de captura**: o ambiente de execução desta sessão tem
um teto de ~45s por chamada de terminal. A suíte completa (448 testes,
crescida desde a Missão 41 com as Missões 42-45) passou a ultrapassar esse
teto em execução única. Para obter evidência literal sem truncamento, cada
execução completa abaixo foi dividida em sub-lotes de arquivos de teste
(união exaustiva, sem sobreposição, confirmada via
`pytest -q --collect-only` = `448 tests collected`), cada sub-lote rodado
em uma chamada separada até completar. Nenhum teste foi pulado; a soma de
cada execução fecha em `448`.

Comando base (mesmo de M41-M44, fragmentado em arquivos):
```
cd /tmp/work/repo && PATH="$PWD/tools:$PATH" python -m pytest -q <subconjunto de arquivos>
```

**Execução 1** (6 sub-lotes):
```
105 passed, 1 warning in 14.98s
54 passed, 1 warning in 3.41s
129 passed, 1 warning in 8.93s
15 passed, 1 warning in 5.17s
27 passed, 1 warning in 3.67s
118 passed, 1 warning in 15.71s
```
Total: `105+54+129+15+27+118 = 448 passed`, 0 falhas.

**Execução 2** (3 sub-lotes):
```
105 passed, 1 warning in 13.86s
183 passed, 1 warning in 10.50s
160 passed, 1 warning in 18.05s
```
Total: `105+183+160 = 448 passed`, 0 falhas.

**Execução 3** (3 sub-lotes):
```
159 passed, 1 warning in 14.67s
144 passed, 1 warning in 11.94s
145 passed, 1 warning in 11.80s
```
Total: `159+144+145 = 448 passed`, 0 falhas.

**Contagem total confirmada**:
```
$ python -m pytest -q --collect-only
448 tests collected in 2.02s
```

**Arquivo da Missão 45 isolado**:
```
$ python -m pytest -q src/app/tests/test_m45_resource_management.py
.........................                                                [100%]
25 passed, 1 warning in 2.93s
```

Baseline antes da Missão 45 (Missão 44): `423 passed`. Delta: `+25` (os 25
testes novos de `test_m45_resource_management.py`), `423 + 25 = 448` —
confere exatamente com `--collect-only`.

## Incidentes durante o desenvolvimento (e correções)

1. **`ObjectDeletedError` em 2 testes** — `test_purge_old_queue_jobs_deletes_old_terminal_job`
   e `..._deletes_old_dead_job_too` acessavam `job.id` *depois* de chamar
   `purge_old_queue_jobs()`, que apaga e comita a remoção daquela mesma
   linha. Com `expire_on_commit=True` (padrão do SQLAlchemy), o acesso
   posterior ao atributo força um refresh do banco — mas a linha já não
   existe, levantando `ObjectDeletedError` em vez de simplesmente retornar
   o valor já conhecido. Corrigido capturando `job_id = job.id` *antes* da
   purga, referenciando o primitivo depois.
2. **Arredondamento de float zera tamanhos pequenos** —
   `test_dir_stats_counts_real_files` usava arquivos de 1 KB; `round(bytes
   / 1024 / 1024, 2)` colapsa esse total para `0.0` em 2 casas decimais,
   fazendo `assert size_mb > 0.0` falhar mesmo com bytes reais escritos.
   Corrigido usando arquivos de 2 MB no fixture do teste.
3. **Convenção de teste de violação de config** — primeira versão do teste
   de `resource_job_retention_days < 1` usava
   `settings.model_copy(update=...)`. Revisão do padrão já estabelecido em
   `test_m44_automatic_diagnostics.py` mostrou que o repositório muta o
   singleton cacheado de `get_settings()` diretamente dentro de
   `try/finally`, restaurando o valor original no `finally`. Reescrito
   para seguir esse padrão exatamente.
4. **Teto de 45s por chamada de terminal vs. crescimento da suíte** — a
   suíte completa, que rodava em 17-24s na Missão 41, hoje (448 testes,
   +146 desde então) se aproxima ou excede o teto de uma única chamada.
   Investigado com uma consulta direta ao banco (ver seção "Justificativa
   real" acima), que confirmou acúmulo real de dados de teste — exatamente
   o problema que esta missão resolve. Resolvido para fins de evidência
   dividindo a suíte em sub-lotes de arquivos (sem sobreposição, soma
   exata = 448), sem alterar nenhum teste. Não foi executado
   `run_cleanup()` contra o banco de dev real nesta sessão — ficaria fora
   do escopo de "implementar e testar a Missão 45", já que o objetivo aqui
   é entregar a capacidade, não operá-la em produção sem pedido do Douglas.

## Critério de aceite

`ResourceManagerService` implementado e testado (25 testes, 100%
passando); reaproveita `TERMINAL_STATUSES`, `safe_project_path()` e
`CacheService.purge_expired()` em vez de duplicar lógica; 3 rotas novas
registradas em `safe_router.py`; configuração nova validada
(`resource_job_retention_days >= 1`); `CONFIG_SCHEMA_VERSION` em `1.4.0`,
documentado em `CONFIG_CHANGELOG.md`; suíte completa (448 testes) em
`0` falhas, confirmada em 3 execuções consecutivas.

## Próximos passos

Commit local na branch `missao-45-gerenciamento-de-recursos` (sem
push/PR — Douglas fará o push de todas as Missões 41-50 de uma vez,
quando estiverem completas). Em seguida, Missão 46 (Sistema de Alertas).
