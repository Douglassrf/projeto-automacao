# Missão 41 — Configuração Centralizada

Data UTC: 2026-06-27.
Autorização de escopo: Douglas autorizou explicitamente suspender a regra
"Fase Ômega apenas / sem funcionalidade nova" do `CLAUDE.md` para o conjunto
de Missões 41–50, atribuídas ao Claude ("essas são as suas").

## Objetivo (conforme especificação do Douglas)

Eliminar configuração crítica dispersa no código; perfis para
Dev/Teste/Homologação/Produção; validação automática de configurações
inválidas; versionamento de configuração. Critério de aceite: nenhuma
configuração crítica permanece dispersa no código.

## O que foi entregue

### 1. Perfis de ambiente (Dev/Teste/Homologação/Produção)

Novo módulo `src/app/core/config_profiles.py`, com `Environment` (enum:
`development`, `testing`, `staging`, `production`) e `detect_environment()`,
que lê `APP_ENV` (com aliases em português: `homolog`/`homologacao`/
`homologação`/`stage` → staging; `teste` → testing; `producao`/`produção` →
production). **Sem `APP_ENV` definido (caso de toda instalação existente
hoje), o perfil resolvido é `development`** e o comportamento é idêntico ao
de antes.

`env_file_candidates(environment)` retorna `(".env.<perfil>", ".env")` —
pydantic-settings carrega o primeiro como base e o segundo (se existir)
sobrescreve. Arquivos inexistentes são ignorados silenciosamente. Variáveis
de ambiente reais do processo continuam tendo precedência máxima (garantia
nativa do pydantic-settings, não alterada).

`get_settings()` em `src/app/core/config.py` foi atualizado para usar isso:

```python
@lru_cache
def get_settings() -> Settings:
    environment = detect_environment()
    settings = Settings(_env_file=env_file_candidates(environment))
    validate_or_raise(settings, environment)
    return settings
```

### 2. Validação automática de configurações inválidas

`validate_settings(settings, environment)` retorna a lista de problemas
encontrados (não lança). `validate_or_raise()` lança `ConfigValidationError`
(com todos os problemas, não só o primeiro) quando o perfil é `production`
ou `testing` — os dois perfis onde uma configuração inválida tem maior
chance de causar dano real ou mascarar um teste.

Regras implementadas:

- **production**: bloqueia se `auth_required=False`; se `jwt_secret_key`
  ainda for o placeholder de desenvolvimento ou tiver menos de 32
  caracteres; se `meta_allow_production_real=True` sem
  `meta_require_manual_confirmation=True`; se `default_admin_password` for
  `None`. Avisa (sem bloquear) se `meta_env="production"` com
  `meta_dry_run=True`.
- **testing**: bloqueia se `meta_env="production"` ou
  `meta_allow_production_real=True` — protege a suíte de testes de
  side-effects reais na Meta API.
- **todos os perfis**: `upload_max_bytes` deve ser positivo;
  `queue_default_max_attempts` deve ser >= 1.

### 3. Versionamento de configuração

`CONFIG_SCHEMA_VERSION = "1.0.0"`, exposto como campo `config_schema_version`
em `Settings` e em `config_fingerprint()`. Histórico em `CONFIG_CHANGELOG.md`
(novo arquivo). Esta é a versão do **esquema de configuração**, separada da
versão do produto (`VERSION` = `1.1.0`, inalterada).

`config_fingerprint(settings)` retorna um resumo estável e não sensível
(versão do esquema, perfil ativo, total de campos, nomes dos campos
sensíveis — nunca os valores) — útil para diagnóstico sem expor segredos.

### 4. Eliminação de configuração dispersa

Varredura de `os.getenv`/`os.environ.get` em `src/app` (fora de testes e do
próprio `config_profiles.py`) encontrou **uma única ocorrência**:
`app/services/observability.py`, lendo `APP_LOG_LEVEL` diretamente do
ambiente. Esse valor agora é um campo documentado e versionado em `Settings`
(`app_log_level`, `validation_alias="APP_LOG_LEVEL"`), visível em
`config_fingerprint()` e coberto por `validate_settings()`.

A leitura ao vivo de `os.environ.get("APP_LOG_LEVEL")` foi **mantida** em
`init_observability()` como primeira fonte, por uma razão testada
explicitamente no repositório: `get_settings()` é cacheado por `@lru_cache`
(singleton de processo), então um valor setado em `Settings` não reagiria a
uma mudança de ambiente em tempo de execução sem reiniciar o processo. Essa
capacidade de reconfiguração dinâmica já é coberta por um teste pré-existente
(`test_m06a_observability.py::test_m06a_structured_logging_uses_json_and_configurable_level`)
e precisava ser preservada. A solução final usa três níveis de fallback,
preservando o comportamento testado anteriormente e ainda expondo o campo
versionado:

```python
level_name = (
    os.environ.get("APP_LOG_LEVEL")
    or settings.app_log_level
    or getattr(settings, "observability_log_level", "INFO")
).upper()
```

Após esta mudança, **zero** ocorrências de `os.getenv`/`os.environ.get`
restam fora de `config_profiles.py` e do fallback documentado acima.

### Arquivos novos

| Arquivo | Conteúdo |
|---|---|
| `src/app/core/config_profiles.py` | Perfis, validação, fingerprint, versionamento |
| `src/app/tests/test_m41_centralized_config.py` | 30 testes (16 funções, uma parametrizada com 15 casos) |
| `.env.development.example` | Exemplo do perfil development |
| `.env.testing.example` | Exemplo do perfil testing |
| `.env.staging.example` | Exemplo do perfil staging/homologação |
| `.env.production.example` | Exemplo do perfil production |
| `CONFIG_CHANGELOG.md` | Histórico do esquema de configuração |

### Arquivos modificados

| Arquivo | Mudança |
|---|---|
| `src/app/core/config.py` | +29/-1 linhas: campos `config_schema_version`, `app_log_level`; `get_settings()` perfil-aware |
| `src/app/services/observability.py` | +17/-1 linhas: eliminação do `os.getenv` disperso, com fallback documentado |

```
$ git diff --stat src/app/core/config.py src/app/services/observability.py
 src/app/core/config.py            | 29 ++++++++++++++++++++++++++++-
 src/app/services/observability.py | 17 ++++++++++++++++-
 2 files changed, 44 insertions(+), 2 deletions(-)
```

## Compatibilidade

Nenhuma variável de ambiente nova é exigida. Sem `APP_ENV` definido (estado
de toda instalação hoje), o comportamento é idêntico ao anterior: perfil
`development`, carrega só `.env` (já que `.env.development` tipicamente não
existe), nenhuma validação bloqueante é executada.

## Evidência — suíte completa, 3 execuções consecutivas

Comando (replica `pytest.ini` + shim ffmpeg do `conftest.py`):

```
cd /tmp/work/repo && PATH="$PWD/tools:$PATH" python -m pytest -q
```

**Execução 1:**
```
332 passed, 3 warnings in 17.90s
```

**Execução 2:**
```
332 passed, 3 warnings in 24.12s
```

**Execução 3:**
```
332 passed, 3 warnings in 21.14s
```

**Execução 4 (saída completa capturada):**
```
........................................................................ [ 21%]
........................................................................ [ 43%]
........................................................................ [ 65%]
........................................................................ [ 86%]
............................................                             [100%]
=============================== warnings summary ===============================
../venv/lib/python3.10/site-packages/fastapi/testclient.py:1
  /tmp/work/venv/lib/python3.10/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /tmp/work/venv/lib/python3.10/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /tmp/work/venv/lib/python3.10/site-packages/jwt/api_jwt.py:368: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
332 passed, 3 warnings in 19.13s
```

Baseline antes da Missão 41 (mesma execução, mesmo ambiente): `302 passed`.
Delta: `+30` (os 30 testes novos de `test_m41_centralized_config.py`). Os 3
avisos (`InsecureKeyLengthWarning` x2 + `StarletteDeprecationWarning` x1) já
existiam antes da Missão 41 e são de testes/dependências pré-existentes, não
relacionados a esta mudança.

## Incidentes durante o desenvolvimento (e correções)

1. **Regressão real detectada e corrigida**: a primeira versão da migração
   de `APP_LOG_LEVEL` quebrou
   `test_m06a_observability.py::test_m06a_structured_logging_uses_json_and_configurable_level`,
   porque `get_settings()` é cacheado por `@lru_cache` e o teste depende de
   reconfiguração dinâmica via `monkeypatch.setenv` em tempo de execução.
   Corrigido preservando a leitura ao vivo de `os.environ` como primeira
   fonte (ver seção 4 acima). Confirmado: suíte completa voltou a
   `302 passed` (baseline) antes de adicionar os testes novos da Missão 41.
2. **Poluição de estado entre testes (autocausada)**: um teste novo
   (`test_config_fingerprint_never_exposes_secret_values`) mutava
   `settings.jwt_secret_key` no singleton cacheado sem restaurar,
   contaminando testes posteriores na mesma sessão (`test_r13_failure_scenarios.py`,
   `test_scaling_engine.py`) — 8 falhas determinísticas, confirmadas em duas
   execuções idênticas antes da correção. Corrigido com `try/finally`,
   seguindo o padrão de mutação segura já estabelecido no repositório
   (`test_m06a_observability.py`).
3. **Segunda poluição, mais sutil**: três testes que chamavam
   `get_settings.cache_clear()` para testar a troca de perfil em tempo de
   execução destruíam o singleton mutado uma única vez por
   `tests/conftest.py::ensure_database_schema` (fixture de sessão que define
   `settings.default_admin_password = "test-admin-password"` quando ausente
   — essa fixture roda só uma vez por sessão e nunca de novo). Isso quebrava
   testes de login (`test_r13_failure_scenarios.py`,
   `test_scaling_engine.py`) que rodam depois, com
   `default_admin_password=None`. Corrigido: cada teste que chama
   `cache_clear()` agora recria o mesmo invariante no `finally`
   (`get_settings(); if .default_admin_password is None: ... = "test-admin-password"`),
   respeitando o contrato implícito da fixture de sessão em vez de o violar.

## Critério de aceite

Nenhuma configuração crítica permanece dispersa no código: confirmado por
varredura (`grep -rn "os.getenv\|os.environ.get" src/app`), restando apenas
a leitura documentada e justificada em `observability.py` (ver seção 4) e a
leitura de `APP_ENV` em `config_profiles.py` (necessária antes de
`Settings` existir, para decidir quais arquivos `.env*` carregar — é, por
definição, a única variável que não pode viver dentro do próprio `Settings`
que ela ajuda a construir).

## Próximos passos

PR aberto para `master` com esta entrega — não mesclado, aguardando revisão
do Douglas. Em seguida, Missão 42 (Gerenciador Inteligente de Filas).
