# Missão 46 — Sistema de Alertas

Data UTC: 2026-06-27.
Autorização de escopo: Douglas autorizou explicitamente suspender a regra
"Fase Ômega apenas / sem funcionalidade nova" do `CLAUDE.md` para o conjunto
de Missões 41–50, atribuídas ao Claude ("essas são as suas").

## Objetivo

Não há texto de especificação de Douglas além do nome da missão (mesma
situação das Missões 44 e 45). Por análise do código e do padrão das
Missões 41-45, "Sistema de Alertas" foi entendido como: a contraparte
**com estado** do Diagnóstico Automático (Missão 44). A Missão 44 é
somente leitura — recalcula tudo do zero a cada chamada e nunca persiste
nada. O Sistema de Alertas fecha esse gap: transforma cada problema
detectado em um evento (`AlertEvent`) que abre quando o check falha,
permanece aberto enquanto o problema persistir (sem duplicar a cada
reavaliação), e é resolvido automaticamente quando o check volta a `ok`.

## Justificativa real (não hipotética)

A Missão 44 já expõe `DiagnosticsService.run_full_diagnostics()`, que
devolve uma lista de checks com `status` em `{"ok", "warning", "critical"}`.
Sem nenhum componente de estado, qualquer consumidor (dashboard, rota,
notificação) que queira saber "isso já estava quebrado ontem ou é novo?"
ou "quantas vezes esse check falhou nas últimas 24h?" não tem como
responder — cada chamada é um snapshot isolado, sem histórico. O
`AlertService` resolve exatamente essa lacuna, reaproveitando
`DiagnosticsService` em vez de duplicar a lógica de verificação.

## O que foi entregue

### 1. `AlertEvent` (`src/app/domain/models.py`, novo modelo)

Tabela `alert_events`: `check_name`, `severity`, `message`, `status`
(`"open"` ou `"resolved"`), `first_seen_at`, `last_seen_at`, `resolved_at`.
Criada automaticamente por `Base.metadata.create_all()` (fixture de sessão
em `conftest.py`) — não precisa de migração Alembic, mesma convenção já
documentada no repositório para tabelas novas.

### 2. `AlertService` (`src/app/services/alert_service.py`, novo)

- `evaluate()` — chama `DiagnosticsService.run_full_diagnostics()` (Missão
  44) e, para cada check:
  - `status == ok` e existe evento aberto → resolve (`status="resolved"`,
    `resolved_at`).
  - `status == ok` e não existe evento aberto → nada a fazer.
  - `status != ok` e existe evento aberto → atualiza severidade/mensagem/
    `last_seen_at` no mesmo evento (de-duplicação — não cria linha nova a
    cada reavaliação do mesmo problema contínuo).
  - `status != ok` e não existe evento aberto → cria evento novo
    (`status="open"`).
  - Retorna resumo: `overall_status`, `evaluated_at`, e as listas
    `opened`/`updated`/`resolved` (nomes dos checks).
- `active_alerts()` — eventos com `status="open"`, mais recentes primeiro.
- `history(limit=None)` — eventos abertos e resolvidos, mais recentes
  primeiro; `limit` explícito ou `settings.alert_history_default_limit`
  (default 50).

No máximo um evento `"open"` por `check_name` por vez. Se o mesmo check
falhar de novo depois de resolvido, abre um evento novo — o histórico
preserva ambos (testado explicitamente, ver `test_evaluate_reopens_a_new_event_after_resolution_if_it_fails_again`).

### 3. Configuração (`src/app/core/config.py`, `config_profiles.py`)

Campo novo: `alert_history_default_limit: int = 50`. Regra nova em
`validate_settings()` (todos os perfis): `>= 1`. `CONFIG_SCHEMA_VERSION`
`1.4.0` → `1.5.0`.

### 4. API (`src/app/schemas/system_alerts.py`, `src/app/api/routes/system_alerts.py`, novos)

Três rotas em `/system-alerts`, registradas em `safe_router.py`
(`ROUTE_MODULES`):

| Rota | Método | Função |
|---|---|---|
| `/system-alerts/evaluate` | POST | `AlertService.evaluate()` — roda a avaliação e persiste |
| `/system-alerts/active` | GET | `AlertService.active_alerts()` |
| `/system-alerts/history` | GET (`?limit=`) | `AlertService.history()` |

### Arquivos novos

| Arquivo | Conteúdo |
|---|---|
| `src/app/services/alert_service.py` | `AlertService` |
| `src/app/schemas/system_alerts.py` | 2 schemas de resposta |
| `src/app/api/routes/system_alerts.py` | 3 rotas |
| `src/app/tests/test_m46_alert_system.py` | 22 testes |

### Arquivos modificados

```
$ git diff --stat -- src/app/domain/models.py src/app/core/config.py src/app/core/config_profiles.py src/app/api/safe_router.py
 src/app/api/safe_router.py      |  1 +
 src/app/core/config.py          |  3 +++
 src/app/core/config_profiles.py |  8 +++++++-
 src/app/domain/models.py        | 22 ++++++++++++++++++++++
 4 files changed, 33 insertions(+), 1 deletion(-)
```

## Evidência — suíte completa, 3 execuções consecutivas

**Nota sobre o método de captura**: igual às Missões 42-45, o ambiente
desta sessão tem um teto de ~45s por chamada de terminal, e a suíte
completa (470 testes, +22 desde a Missão 45) ultrapassa esse teto em
execução única. Cada execução completa abaixo foi dividida em sub-lotes de
arquivos de teste (união exaustiva, sem sobreposição, confirmada via
`pytest -q --collect-only` = `470 tests collected`), cada sub-lote rodado
em uma chamada separada até completar. Nenhum teste foi pulado; a soma de
cada execução fecha em `470`.

Comando base (mesmo de M41-M45, fragmentado em arquivos):
```
cd /tmp/work/repo && PATH="$PWD/tools:$PATH" python -m pytest -q <subconjunto de arquivos>
```

**Execução 1** (8 sub-lotes):
```
82 passed, 1 warning in 21.37s
37 passed, 1 warning in 3.31s
189 passed, 1 warning in 18.78s
31 passed, 1 warning in 7.43s
47 passed, 3 warnings in 17.38s
44 passed, 1 warning in 5.20s
38 passed, 1 warning in 9.47s
2 passed, 1 warning in 2.29s
```
Total: `82+37+189+31+47+44+38+2 = 470 passed`, 0 falhas.

**Execução 2** (7 sub-lotes):
```
82 passed, 1 warning in 21.37s
37 passed, 1 warning in 3.15s
189 passed, 1 warning in 9.52s
31 passed, 1 warning in 5.30s
47 passed, 3 warnings in 5.34s
44 passed, 1 warning in 4.91s
40 passed, 1 warning in 4.32s   (inclui test_assisted_execution_gate.py)
```
Total: `82+37+189+31+47+44+40 = 470 passed`, 0 falhas.

**Execução 3** (5 sub-lotes):
```
82 passed, 1 warning in 11.03s
68 passed, 1 warning in 6.62s
91 passed, 3 warnings in 8.64s
40 passed, 1 warning in 4.28s
189 passed, 1 warning in 8.95s
```
Total: `82+68+91+40+189 = 470 passed`, 0 falhas.

**Contagem total confirmada**:
```
$ python -m pytest -q --collect-only
470 tests collected in 3.81s
```

**Arquivo da Missão 46 isolado**:
```
$ python -m pytest -q src/app/tests/test_m46_alert_system.py
......................                                                   [100%]
22 passed, 1 warning in 2.28s
```

Baseline antes da Missão 46 (Missão 45): `448 passed`. Delta: `+22` (os 22
testes novos de `test_m46_alert_system.py`), `448 + 22 = 470` — confere
exatamente com `--collect-only`.

## Incidentes durante o desenvolvimento (e correções)

1. **Lentidão e flakiness de infraestrutura no início da sessão** — ao
   tentar capturar a Execução 1, várias chamadas de terminal retornaram
   erro de infraestrutura do próprio ambiente de execução
   (`"bash failed on resume, create, and re-resume... process with name
   ... already running"`) ou ficaram com saída parcial (só pontos de
   progresso, sem linha de resumo final), mesmo para lotes pequenos
   (3-6 arquivos) que historicamente terminavam em segundos. Isolado por
   bisseção: `src/app/tests/test_assisted_execution_gate.py` (2 testes,
   pré-existente, não tocado por esta missão) ficou travado por 35s+ sem
   nenhuma saída em 3 tentativas seguidas (confirmado com
   `timeout 35 ... > arquivo; echo "EXIT:$?"` → `EXIT:124`, arquivo de
   saída com 0 bytes). Investigação no código (`meta_operator.py`,
   `meta_campaign_operator.py`, `api/deps.py`) não encontrou nenhuma
   chamada de rede real (`requests`/`httpx`/`socket`) nesse fluxo — a rota
   só monta um payload e valida regras de aprovação humana, sem I/O
   externo. Confirmado pela tentativa seguinte: o mesmo arquivo, isolado,
   passou em `2.29s` sem nenhuma mudança de código. Conclusão: foi
   instabilidade pontual da infraestrutura de execução desta sessão
   (sandbox), não um problema no código testado nem relacionado às
   mudanças da Missão 46 (o arquivo afetado não importa nada de
   `alert_service.py`/`system_alerts.py`/`AlertEvent`). Resolvido
   simplesmente tentando de novo; nas Execuções 2 e 3 esse mesmo arquivo
   passou normalmente dentro de lotes maiores, sem isolamento especial.
2. **Teto de 45s por chamada vs. suíte em 470 testes** — mesmo padrão
   documentado nas Missões 42-45: a suíte completa não cabe em uma única
   chamada de terminal. Resolvido da mesma forma (divisão em sub-lotes de
   arquivos, sem sobreposição, soma exata confirmada contra
   `--collect-only` em cada uma das 3 execuções).

## Critério de aceite

`AlertEvent` + `AlertService` implementados e testados (22 testes, 100%
passando); reaproveita `DiagnosticsService.run_full_diagnostics()` (Missão
44) em vez de duplicar lógica de verificação; de-duplicação por
`check_name` confirmada por teste (no máximo um evento `open` por check);
resolução automática ao voltar a `ok` confirmada por teste; reabertura
após resolução confirmada por teste (preserva os dois eventos no
histórico); 3 rotas novas registradas em `safe_router.py`; configuração
nova validada (`alert_history_default_limit >= 1`); `CONFIG_SCHEMA_VERSION`
em `1.5.0`, documentado em `CONFIG_CHANGELOG.md`; suíte completa
(470 testes) em `0` falhas, confirmada em 3 execuções consecutivas.

## Próximos passos

Commit local na branch `missao-46-sistema-de-alertas` (sem push/PR —
Douglas fará o push de todas as Missões 41-50 de uma vez, quando estiverem
completas). Em seguida, Missão 47 (Testes de Recuperação).
