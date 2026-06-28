# CONFIG_CHANGELOG.md

Histórico do **esquema de configuração** (`CONFIG_SCHEMA_VERSION`, em
`src/app/core/config_profiles.py`), introduzido na Missão 41 — Configuração
Centralizada. Isto é versionado separadamente da versão do produto
(`VERSION`): sobe quando um campo crítico é adicionado, removido, ou muda de
significado em `Settings` (`src/app/core/config.py`), ou quando uma regra de
`validate_settings()` muda.

## 1.9.0 — 2026-06-27 (Missão 50)

Adiciona a Certificação Platinum v1.3 — o capstone das Missões 41-49:
`CertificationService` não reimplementa nenhuma lógica de
diagnóstico/alerta/fila/recurso/dependência, apenas agrega em uma única
chamada o que cada serviço anterior já calcula
(`DiagnosticsService.run_full_diagnostics()` da Missão 44,
`AlertService.active_alerts()` da Missão 46 — somente leitura, nunca
`evaluate()`, para a certificação nunca ter efeito colateral —,
`RecoveryService.recovery_report()` da Missão 47,
`ResourceManagerService.disk_usage_report()` da Missão 45 e
`DependencyAuditService.audit()` da Missão 49) e aplica uma única regra
de veredito (`platinum_certified: bool` + `blocking_issues: list[str]`).

Regra de veredito ("fail-closed" por design, ver docstring de
`CertificationService`): bloqueiam a certificação (1) status de
diagnósticos diferente de `"ok"`, (2) qualquer alerta ativo não resolvido,
(3) dependência declarada ausente do ambiente ou com versão divergente da
fixada (Missão 49) — deliberadamente **não** bloqueia em dependência sem
pin (`unpinned_count`), tratado como informativo/risco aceito desde a
Missão 49 (19/19 dependências deste repositório sem pin hoje) —, e (4)
fila de jobs não saudável (Missão 47).

Campo novo em `Settings`:

- `certification_platinum_require_clean_diagnostics` (default `True`):
  o "gate" da certificação. Quando `True`, `platinum_certified` só pode
  ser `True` se nenhum `blocking_issue` for encontrado. Quando `False`,
  `platinum_certified` é **sempre** `False` — desligar o gate nunca
  libera uma certificação "de gracinha"; só impede que qualquer estado
  seja certificado, mesmo saudável. Nunca deve ser `False` em produção.

Nova regra em `validate_settings()` (perfil produção):
`certification_platinum_require_clean_diagnostics` não pode ser `False`
em produção (senão o endpoint `/certification/platinum` nunca reportaria
`platinum_certified=True`, mesmo com tudo saudável).

Duas rotas novas em `/certification` (`safe_router.py`):
`GET /certification/platinum/live` (snapshot JSON agregado),
`GET /certification/platinum/markdown` (o mesmo snapshot renderizado como
Markdown, `text/markdown`).

Arquivos modificados: `src/app/core/config.py`,
`src/app/core/config_profiles.py`, `src/app/api/safe_router.py`.
Arquivos novos: `src/app/services/certification_service.py`,
`src/app/schemas/certification.py`, `src/app/api/routes/certification.py`.

## 1.8.0 — 2026-06-27 (Missão 49)

Adiciona a Auditoria de Dependências: `requirements.txt` deste repositório
declara 19 dependências (fastapi, uvicorn, sqlalchemy, pydantic,
pydantic-settings, PyJWT, passlib, bcrypt, python-dotenv,
python-multipart, email-validator, httpx, sentry-sdk, pillow,
python-magic, werkzeug, celery, requests, pytest) e **nenhuma delas tem
versão fixa** (`==`) — 19/19, 100% sem pin. Isso significa que um `pip
install -r requirements.txt` executado hoje e outro executado meses
depois podem instalar versões diferentes de qualquer uma dessas
bibliotecas, silenciosamente, sem nenhum aviso no próprio arquivo.
`DependencyAuditService` lê `requirements.txt` em tempo real, usa
`packaging.requirements.Requirement` (biblioteca já presente no ambiente
como dependência transitiva de `pytest`, portanto nenhuma dependência
nova foi declarada) para interpretar cada linha, e cruza cada dependência
declarada com a versão de fato instalada via `importlib.metadata` — sem
nenhuma chamada de rede, API externa, paga ou serviço de terceiros
(nada de PyPI Advisory DB / OSV / safety-db).

Campo novo em `Settings`:

- `dependency_audit_warn_on_unpinned` (default `True`): controla se uma
  dependência sem versão fixa aparece na lista de "issues" do endpoint
  `/dependency-audit/*`, além de aparecer na lista bruta de dependências.
  Nunca deve ser `False` em produção.

Nova regra em `validate_settings()` (perfil produção):
`dependency_audit_warn_on_unpinned` não pode ser `False` em produção.

Duas rotas novas em `/dependency-audit` (`safe_router.py`):
`GET /dependency-audit/live` (snapshot JSON com total declarado, contagem
de fixados/não-fixados/ausentes/divergentes e a lista completa de
dependências), `GET /dependency-audit/markdown` (o mesmo snapshot
renderizado como Markdown, `text/markdown`).

Arquivos modificados: `src/app/core/config.py`,
`src/app/core/config_profiles.py`, `src/app/api/safe_router.py`.
Arquivos novos: `src/app/services/dependency_audit_service.py`,
`src/app/schemas/dependency_audit.py`,
`src/app/api/routes/dependency_audit.py`.

## 1.7.0 — 2026-06-27 (Missão 48)

Adiciona a Documentação Viva: em vez de um `.md` estático que alguém
precisa lembrar de editar a cada mudança (o próprio `README.md` deste
repositório afirma hoje "Requer Python 3.11+" e "261 passed" — nenhum dos
dois reflete o estado atual, Python 3.10 real e 489+ testes após a Missão
47), `DocumentationService` gera um snapshot a partir do estado vivo do
sistema a cada chamada: rotas carregadas/falhas (reusa
`LOADED_ROUTES`/`FAILED_ROUTES`/`ROUTE_MODULES` de `safe_router.py`, mesmo
padrão de import tardio com fallback já usado por
`observability.health_dashboard()`), schema de `Settings` via
`model_fields` (introspecção real, não uma lista mantida à mão), o
conteúdo atual do arquivo `VERSION`, e os problemas correntes de
`validate_settings()` (Missão 41). Qualquer campo cujo nome contenha um
marcador de segredo (`secret`/`password`/`token`/`key`) tem o valor
redigido por padrão — correspondência por substring é deliberadamente
conservadora (ex.: `access_token_expire_minutes` é redigido mesmo sem ser
um segredo de fato) para nunca arriscar expor um segredo real por uma
lista de nomes exatos incompleta.

Campo novo em `Settings`:

- `documentation_redact_secrets` (default `True`): controla se os
  endpoints `/documentation/*` redigem valores de campos identificados
  como segredo. Nunca deve ser `False` em produção.

Nova regra em `validate_settings()` (perfil produção):
`documentation_redact_secrets` não pode ser `False` em produção.

Duas rotas novas em `/documentation` (`safe_router.py`):
`GET /documentation/live` (snapshot JSON), `GET /documentation/markdown`
(o mesmo snapshot renderizado como Markdown, `text/markdown`).

Arquivos modificados: `src/app/core/config.py`,
`src/app/core/config_profiles.py`, `src/app/api/safe_router.py`.
Arquivos novos: `src/app/services/documentation_service.py`,
`src/app/schemas/documentation.py`, `src/app/api/routes/documentation.py`.

## 1.6.0 — 2026-06-27 (Missão 47)

Adiciona o Sistema de Recuperação: a contraparte de **ação** do
`health_report()` da fila (Missão 42). `health_report()` apenas detecta
jobs travados em `status="running"` além do lock timeout — o próprio
docstring documenta a limitação: esses jobs "serão reclamados no próximo
`claim()`". Se nenhum worker estiver chamando `claim()` naquele momento
(fila parada, worker caído, deploy em andamento), o job fica invisível e
parado indefinidamente, mesmo sendo perfeitamente recuperável.
`RecoveryService` age agora, sem esperar pelo próximo `claim()`: job com
tentativas restantes volta para `"retry"` (elegível a reclaim imediato);
job sem tentativas restantes vai para `"dead"`, mesma semântica de
`fail()` (Missão 42) quando esgota as tentativas.

Campo novo em `Settings`:

- `recovery_max_jobs_per_sweep` (default `100`): limite de jobs
  recuperados em uma única chamada de `recover_stale_running_jobs()`,
  para não varrer uma fila inteira de uma vez em produção.

Nova regra em `validate_settings()` (todos os perfis):
`recovery_max_jobs_per_sweep` >= 1.

Duas rotas novas em `/recovery` (`safe_router.py`):
`GET /recovery/report` (somente leitura — reusa `health_report()`),
`POST /recovery/sweep` (`?limit=`, executa a recuperação).

Arquivos modificados: `src/app/core/config.py`,
`src/app/core/config_profiles.py`, `src/app/api/safe_router.py`.
Arquivos novos: `src/app/services/recovery_service.py`,
`src/app/schemas/recovery.py`, `src/app/api/routes/recovery.py`.

## 1.5.0 — 2026-06-27 (Missão 46)

Adiciona o Sistema de Alertas: a contraparte com **estado** do Diagnóstico
Automático (Missão 44, sem estado — recalcula tudo do zero a cada chamada).
Novo modelo `AlertEvent` (tabela `alert_events`, criada automaticamente por
`Base.metadata.create_all()` no schema do banco — sem necessidade de
Alembic) e `AlertService`, que chama
`DiagnosticsService.run_full_diagnostics()` (Missão 44) e converte cada
check não-`ok` em um evento: abre um evento novo (`status="open"`) na
primeira falha de um `check_name`; em falhas repetidas do mesmo check,
atualiza severidade/mensagem do evento já aberto em vez de duplicar
(de-duplicação por `check_name`); quando o check volta a `ok`, marca o
evento aberto como `status="resolved"` com `resolved_at`. Se o mesmo check
falhar de novo depois de resolvido, abre um evento novo — o histórico
preserva ambos.

Campo novo em `Settings`:

- `alert_history_default_limit` (default `50`): quantidade de eventos
  retornados por `AlertService.history()` quando chamado sem `limit`
  explícito.

Nova regra em `validate_settings()` (todos os perfis):
`alert_history_default_limit` >= 1.

Três rotas novas em `/system-alerts` (`safe_router.py`):
`POST /system-alerts/evaluate` (roda a avaliação e persiste),
`GET /system-alerts/active` (eventos com `status="open"`),
`GET /system-alerts/history` (`?limit=`, eventos abertos e resolvidos,
mais recentes primeiro).

Arquivos modificados: `src/app/domain/models.py`, `src/app/core/config.py`,
`src/app/core/config_profiles.py`, `src/app/api/safe_router.py`.
Arquivos novos: `src/app/services/alert_service.py`,
`src/app/schemas/system_alerts.py`, `src/app/api/routes/system_alerts.py`.

## 1.4.0 — 2026-06-27 (Missão 45)

Adiciona configuração do Gerenciamento de Recursos (limpeza ativa do que o
Diagnóstico Automático da Missão 44 apenas reportava): `ResourceManagerService`
purga jobs de fila terminais (`done`/`dead`, mesmo `TERMINAL_STATUSES` de
`QueueService`) mais antigos que um limite configurável, delega a purga de
cache expirado ao `CacheService` (Missão 43) e relata uso de disco dos
diretórios de saída gerenciados (`campaign_kits`, `orchestration_runs`, `ugc`,
`premium_renders`), resolvidos via `safe_project_path()` — mesma função já
usada pelos serviços que escrevem nesses diretórios.

Campo novo em `Settings`:

- `resource_job_retention_days` (default `30`): idade mínima (dias) de um
  job de fila terminal para ser elegível à purga por
  `purge_old_queue_jobs()`, quando chamado sem override explícito.

Nova regra em `validate_settings()` (todos os perfis):
`resource_job_retention_days` >= 1.

Arquivos modificados: `src/app/core/config.py`, `src/app/core/config_profiles.py`,
`src/app/api/safe_router.py`.
Arquivos novos: `src/app/services/resource_manager_service.py`,
`src/app/schemas/resources.py`, `src/app/api/routes/resources.py`.

## 1.3.0 — 2026-06-27 (Missão 44)

Adiciona configuração do Diagnóstico Automático (sem novo estado persistente
— `DiagnosticsService` recalcula um snapshot fresco a cada chamada, agregando
sinais que já existem em `QueueService.health_report()` (Missão 42),
`CacheService` (Missão 43) e `validate_settings()` (Missão 41), mais dois
checks novos: banco de dados (round-trip `SELECT 1`) e disco.

Campos novos em `Settings`:

- `diagnostics_disk_path` (default `"."`): caminho cujo espaço livre é
  monitorado por `DiagnosticsService.check_disk()`.
- `diagnostics_disk_warning_free_mb` (default `500`): abaixo deste limite
  (MB livres), o check de disco reporta `"warning"`.
- `diagnostics_disk_critical_free_mb` (default `100`): abaixo deste limite,
  o check de disco reporta `"critical"`.

Novas regras em `validate_settings()` (todos os perfis):
`diagnostics_disk_warning_free_mb` >= 1; `diagnostics_disk_critical_free_mb`
>= 1; `diagnostics_disk_critical_free_mb` deve ser estritamente menor que
`diagnostics_disk_warning_free_mb` (senão as duas faixas colapsam em uma só
e a distinção "ficando baixo" vs "quase sem espaço" se perde — mesmo
raciocínio do par `queue_retry_backoff_base_seconds`/`_max_seconds` da
Missão 42).

Arquivos modificados: `src/app/core/config.py`, `src/app/core/config_profiles.py`,
`src/app/api/safe_router.py`.
Arquivos novos: `src/app/services/diagnostics_service.py`,
`src/app/schemas/diagnostics.py`, `src/app/api/routes/diagnostics.py`.

## 1.2.0 — 2026-06-27 (Missão 43)

Adiciona configuração do Cache Inteligente (cache zero-custo via SQLite).
Campos novos em `Settings`:

- `cache_default_ttl_seconds` (default `300`): TTL usado por `CacheService.set()`
  quando `ttl_seconds` não é passado explicitamente.
- `cache_max_entries_per_namespace` (default `1000`): limite por namespace
  que aciona evicção LRU (least-recently-accessed) ao ser excedido.
- `cache_backend` (default `"sqlite"`): identifica o backend ativo —
  exposto em `CacheService.stats()["backend"]`, preparado para um futuro
  backend real (KeyDB/Redis) sem mudar o contrato público.

Novas regras em `validate_settings()` (todos os perfis):
`cache_default_ttl_seconds` >= 1; `cache_max_entries_per_namespace` >= 1.
Note que isso valida apenas o *default* da configuração — um chamador do
`CacheService.set()` ainda pode pedir `ttl_seconds<=0` explicitamente para
"sem expiração", o que é um comportamento por chamada, não um valor de
configuração.

Nenhum valor antigo muda de significado — apenas campos novos. Nenhuma
funcionalidade de cache existia antes da Missão 43 (confirmado por
varredura: zero ocorrências de "cache" relevantes no código antes desta
missão).

Arquivos modificados: `src/app/core/config.py`, `src/app/core/config_profiles.py`.
Arquivos novos: `src/app/services/cache_service.py`, `src/app/schemas/cache.py`,
`src/app/api/routes/cache.py`.


## 1.1.0 — 2026-06-27 (Missão 42)

Adiciona configuração do backoff/diagnóstico da fila (Gerenciador
Inteligente de Filas). Campos novos em `Settings`:

- `queue_retry_backoff_base_seconds` (default `5`): base do backoff
  exponencial aplicado a jobs em `retry`.
- `queue_retry_backoff_max_seconds` (default `300`): teto do backoff.
- `queue_starvation_threshold_seconds` (default `600`): tempo de espera
  acima do qual um job é considerado em inanição por `health_report()`.
- `queue_failure_rate_threshold` (default `0.5`): taxa de falha
  (`dead / (done+dead)`) acima da qual uma fila é marcada como
  insalubre (amostra mínima de 5 jobs finalizados).

Novas regras em `validate_settings()` (todos os perfis):
`queue_retry_backoff_base_seconds` >= 1; `queue_retry_backoff_max_seconds`
>= `queue_retry_backoff_base_seconds`; `queue_starvation_threshold_seconds`
>= 1; `0 < queue_failure_rate_threshold <= 1`.

Nenhum valor antigo muda de significado — apenas campos novos com
defaults equivalentes ao comportamento anterior (retry imediato vira
retry com backoff de poucos segundos; nenhum diagnóstico existia antes).

Arquivos modificados: `src/app/core/config.py`, `src/app/core/config_profiles.py`.


## 1.0.0 — 2026-06-27 (Missão 41)

Primeira versão do esquema. Estabelece:

- Quatro perfis de ambiente, via `APP_ENV`: `development` (default quando
  `APP_ENV` não está definido — compatível com toda instalação existente),
  `testing`, `staging` (aceita aliases `homolog`/`homologacao`/`homologação`/
  `stage`), `production`.
- Carregamento de arquivo em cascata: `.env.<perfil>` primeiro, `.env` depois
  (pode sobrescrever). Variáveis de ambiente reais do processo sempre têm
  precedência sobre qualquer arquivo `.env*` (comportamento nativo do
  pydantic-settings, não alterado).
- Validação automática (`validate_settings` / `validate_or_raise`):
  - Perfil `production`: bloqueia (`ConfigValidationError`, processo não
    inicia) se `auth_required=False`, `jwt_secret_key` ainda for o
    placeholder de desenvolvimento ou tiver menos de 32 caracteres,
    `meta_allow_production_real=True` sem confirmação manual obrigatória, ou
    `default_admin_password` ausente. Também avisa (sem bloquear) se
    `meta_env="production"` com `meta_dry_run=True`.
  - Perfil `testing`: bloqueia se `meta_env="production"` ou
    `meta_allow_production_real=True` — protege a suíte de testes contra
    side-effects reais na Meta API.
  - Todos os perfis: `upload_max_bytes` deve ser positivo;
    `queue_default_max_attempts` deve ser >= 1.
- Campo novo em `Settings`: `config_schema_version` (este número, exposto em
  tempo de execução).
- Campo novo em `Settings`: `app_log_level` (`validation_alias="APP_LOG_LEVEL"`)
  — torna documentado/versionado um valor que antes só existia como
  `os.getenv("APP_LOG_LEVEL", ...)` disperso em
  `app/services/observability.py`. A leitura ao vivo de
  `os.environ.get("APP_LOG_LEVEL")` em `init_observability()` foi mantida
  como primeira fonte (ver comentário no próprio arquivo) para não quebrar a
  reconfiguração dinâmica de log level já testada — `app_log_level` é o
  fallback documentado, não a única fonte de verdade.
- `config_fingerprint()`: resumo estável e não sensível da configuração
  ativa (versão do esquema, perfil, total de campos, nomes dos campos
  sensíveis redatados) — não inclui nenhum valor de segredo.

Arquivos novos: `src/app/core/config_profiles.py`,
`src/app/tests/test_m41_centralized_config.py`,
`.env.development.example`, `.env.testing.example`, `.env.staging.example`,
`.env.production.example`.

Arquivos modificados: `src/app/core/config.py` (novos campos +
`get_settings()` perfil-aware), `src/app/services/observability.py`
(eliminação do único `os.getenv` disperso fora de `Settings` em `src/`).
