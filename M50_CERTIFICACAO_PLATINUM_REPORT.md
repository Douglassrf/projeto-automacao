# Missão 50 — Certificação Platinum v1.3

## Objetivo

Entregar um veredito único, automatizado e não-hipotético sobre o estado de
saúde do sistema — agregando diagnósticos (M44), alertas (M46), recuperação
de fila (M47) e auditoria de dependências (M49) — sem duplicar a lógica de
nenhum desses serviços, e sem nenhuma chamada de rede/API paga/serviço
externo. Esta é a missão de fechamento das dez (41–50): se as nove
anteriores funcionam de verdade em conjunto, `CertificationService` deve
conseguir provar isso (ou refutar isso) lendo o estado real do sistema.

## Justificativa real (não hipotética)

Ao final da Missão 49 o repositório tinha nove subsistemas de
observabilidade/operacional (config, fila, cache, diagnóstico, recursos,
alertas, recuperação, documentação, auditoria de dependências) funcionando
de forma isolada, cada um com sua própria rota e seus próprios testes. Não
havia nenhum lugar único que respondesse à pergunta "o sistema está
realmente certificável agora?" sem alguém abrir 5+ endpoints manualmente e
interpretar os resultados. `CertificationService` resolve isso compondo os
serviços já existentes (reuso, não reimplementação) em um único veredito
booleano (`platinum_certified`) com a lista exata de motivos quando
negativo (`blocking_issues`).

## O que foi entregue

`CertificationService` (`src/app/services/certification_service.py`, 257
linhas), sem duplicar lógica já existente — reusa diretamente:

- `DiagnosticsService.run_full_diagnostics()` (M44)
- `AlertService.active_alerts()` (M46 — deliberadamente não `.evaluate()`,
  para a leitura de certificação ser somente-leitura/sem efeito colateral)
- `RecoveryService.recovery_report()` (M47)
- `ResourceManagerService.disk_usage_report()` (M45)
- `DependencyAuditService().audit()` (M49)

`_blocking_issues()` define exatamente 4 condições bloqueantes:

1. `diagnostics_status != "ok"`
2. qualquer `AlertEvent` ativo
3. `dependency_audit.missing_count > 0` ou `.version_mismatch_count > 0`
   (explicitamente **não** bloqueante: `unpinned_count`, por decisão de
   design da própria M49 — dependência sem versão fixa é aviso, não
   defeito)
4. `not queue_recovery["healthy"]`

`certify()` retorna `platinum_certified=True` somente se `_blocking_issues()`
estiver vazia **e** `certification_platinum_require_clean_diagnostics=True`
(o padrão). Gate "fail-closed": desligar essa flag (`False`) nunca aprova
automaticamente — torna a certificação permanentemente inatingível até a
flag ser religada. `render_markdown()` segue o mesmo padrão das Missões
44/48.

Campo novo em `Settings` (`src/app/core/config.py`):
`certification_platinum_require_clean_diagnostics: bool = True`.

Nova regra em `validate_settings()` (perfil produção,
`src/app/core/config_profiles.py`): rejeita
`certification_platinum_require_clean_diagnostics=False` em produção.
`CONFIG_SCHEMA_VERSION` sobe de `1.8.0` para `1.9.0`.

Duas rotas novas em `/certification` (`safe_router.py` registra o módulo
imediatamente após `"dependency_audit"`):

- `GET /api/v1/certification/platinum/live` — veredito completo em JSON
  (`CertificationResponse`).
- `GET /api/v1/certification/platinum/markdown` — o mesmo veredito
  renderizado como Markdown (`text/markdown`).

### Arquivos novos

| Arquivo | Conteúdo | Linhas |
|---|---|---|
| `src/app/services/certification_service.py` | `CertificationService` | 257 |
| `src/app/schemas/certification.py` | `MissionCoveredInfo`, `DependencyAuditSummary`, `CertificationResponse` | 39 |
| `src/app/api/routes/certification.py` | rotas `/certification/platinum/live` e `/markdown` | 20 |
| `src/app/tests/test_m50_certification_service.py` | 24 testes novos | 430 |

### Arquivos modificados

```
$ git diff --stat -- CONFIG_CHANGELOG.md src/app/api/safe_router.py src/app/core/config.py src/app/core/config_profiles.py
 CONFIG_CHANGELOG.md             | 47 +++++++++++++++++++++++++++++++++++++++++
 src/app/api/safe_router.py      |  1 +
 src/app/core/config.py          | 10 +++++++++
 src/app/core/config_profiles.py | 15 ++++++++++++-
 4 files changed, 72 insertions(+), 1 deletion(-)
```

## Evidência

### Teste novo, isolado (segmento anterior)

```
$ python -m pytest -q app/tests/test_m50_certification_service.py
........................                                                  [100%]
24 passed, 1 warning in 33.64s
```

### 3 execuções completas da suíte total (exigência do CLAUDE.md)

A suíte (109 arquivos de teste, 550 testes coletados) foi dividida em 37
lotes de 3 arquivos cada (`/tmp/m50_agent_files.txt`, ordem fixa), uma
chamada de shell por lote — disciplina herdada das Missões 47–49, recalibrada
nesta missão para lotes de 3 arquivos (ver Incidentes). As 3 execuções
completas foram delegadas a um subagente operando no mesmo sandbox/sessão
(mesmo filesystem `/tmp/work/repo`, sem git, somente leitura de testes), e
os resultados foram verificados de forma independente por mim, lendo os
logs brutos diretamente — não apenas aceitando o relato do subagente.

**Execução 1** (`/tmp/m50_logs/exec1/batch_00.log` .. `batch_36.log`):
```
$ grep -h -oE "[0-9]+ passed" /tmp/m50_logs/exec1/batch_*.log | awk -F' ' '{s+=$1} END{print s, "passed"}'
550 passed
$ grep -l "FAILED\|ERROR" /tmp/m50_logs/exec1/batch_*.log | wc -l
0
```

**Execução 2** (`/tmp/m50_logs/exec2/`):
```
550 passed
0 arquivos com FAILED/ERROR
```

**Execução 3** (`/tmp/m50_logs/exec3/`):
```
550 passed
0 arquivos com FAILED/ERROR
```

Total: **550 passed, 0 failed, 0 errors em cada uma das 3 execuções
completas e independentes** (1.650 execuções de teste no total, contando
as 3 rodadas).

### Evidência específica do lote contendo os testes novos da Missão 50

`/tmp/m50_chunk_18` = `test_m50_certification_service.py`,
`test_market_radar.py`, `test_meta_action_abstraction.py` (24 testes da
M50 + 6 dos outros dois arquivos = 30):

```
$ tail -10 /tmp/m50_logs/exec1/batch_18.log
...
30 passed, 1 warning in 14.28s

$ tail -10 /tmp/m50_logs/exec2/batch_18.log
...
30 passed, 1 warning in 21.89s

$ tail -10 /tmp/m50_logs/exec3/batch_18.log
...
30 passed, 1 warning in 21.98s
```

### Veredito real da Missão 50 contra o estado atual do repositório

Executado diretamente (não simulado) com `CertificationService(db).certify()`
contra o banco de desenvolvimento real (`sqlite:///./adintelligence.db`),
em 2026-06-28 01:02:33 UTC:

```json
{
  "environment": "development",
  "config_schema_version": "1.9.0",
  "strict_mode": true,
  "config_validation_issues": [],
  "diagnostics_status": "critical",
  "active_alerts_count": 337,
  "dependency_audit_summary": {
    "total_declared": 19, "pinned_count": 0, "unpinned_count": 19,
    "missing_count": 0, "version_mismatch_count": 0
  },
  "queue_recovery": {
    "healthy": false,
    "recoverable_now": 4,
    "requires_external_action": 795
  },
  "blocking_issues": [
    "Diagnosticos com status 'critical' (...).",
    "337 alerta(s) ativo(s) nao resolvido(s): ...",
    "Fila de jobs nao saudavel: ha job(s) travado(s) e/ou em inanicao pendente(s) de recuperacao (RecoveryService)."
  ],
  "platinum_certified": false
}
```

**Veredito honesto: `platinum_certified = false` neste exato momento.**
Isso não é uma falha da Missão 50 — é o serviço funcionando como
projetado e detectando um problema real: `adintelligence.db` é o banco de
desenvolvimento único, reaproveitado ao longo de toda a maratona M41–M50
(não um banco efêmero por teste), e acumulou estado de exercícios manuais
das Missões 42 (filas) e 46 (alertas) — 337 `AlertEvent` nunca resolvidos
e 795 `QueueJob` esperando há mais de 600s, restos de quando esses serviços
foram exercitados fora do contexto isolado dos testes automatizados. Os
550 testes automatizados passam porque cada teste usa fixtures de banco
isoladas/efêmeras (SQLite em memória ou arquivo temporário por sessão de
teste) — só o banco de desenvolvimento persistente carrega esse histórico.
A dependência não-fixada (19/19) aparece no relatório mas, por design da
própria M49, não é bloqueante.

Isso confirma que o gate funciona corretamente nos dois sentidos: não
aprova com base em "os testes passam", e não esconde sujeira real
acumulada no ambiente. Limpar esse banco de desenvolvimento está fora do
escopo desta missão (seria uma ação de "ambiente", e tocar nos 795 jobs/337
alertas reais arriscaria mascarar dados que podem ser úteis para auditoria
posterior) — fica registrado como achado real, não como pendência da
Missão 50.

## Incidentes durante o desenvolvimento

1. **Limite de ~45s por chamada de shell do sandbox, sem processos em
   segundo plano sobrevivendo entre chamadas** — descoberta estrutural
   nova nesta missão, mais severa do que a instabilidade intermitente já
   documentada nas Missões 47–49. Investigação: (a) tempos de cold-start
   da primeira chamada de pytest em uma sessão nova são altos
   (30s+ mesmo para poucos testes), caindo para ~4–8s nas chamadas
   seguintes; (b) tentativas de `nohup`/`setsid && disown` para rodar
   pytest em segundo plano e consultar o progresso em chamadas
   subsequentes falharam de forma reproduzível — o processo aparecia em
   `ps aux` imediatamente após o lançamento, mas já não existia (e o log
   não avançava) na chamada seguinte, confirmando que processos filhos não
   sobrevivem ao reset de sessão RPC entre chamadas. **Decisão**:
   recalibrar para lotes de 3 arquivos por chamada de `pytest -q` (testado
   e confirmado estável; lotes de 5–7 arquivos estouravam o limite de
   forma repetível, não-intermitente) e delegar a 37 lotes × 3 execuções
   (111 chamadas) a um subagente operando no mesmo sandbox, para não gastar
   uma quantidade desproporcional de chamadas na conversa principal. Os
   resultados do subagente foram conferidos de forma independente,
   inspecionando os logs brutos diretamente, antes de serem tratados como
   evidência estabelecida.

2. **`test_assisted_execution_gate.py` é lento (~17–20s para 2 testes)**
   — investigado via busca binária com outras combinações de arquivos
   (descartando flakiness genérica) até isolar este arquivo especificamente.
   Causa: o arquivo abre `with TestClient(app) as client:` duas vezes,
   disparando o ciclo de startup completo do FastAPI duas vezes. Confirmado
   (via busca por `requests.`/`httpx.`/`urlopen`/`socket.` perto do código
   de `assisted_execution_gate` em `meta_campaign_operator.py`) que não há
   nenhuma chamada de rede real pendurando — é custo de inicialização do
   próprio framework, não um bug funcional. **Decisão**: característica
   pré-existente do ambiente, não uma regressão da Missão 50 e fora do
   escopo de correção (regra do CLAUDE.md de não introduzir escopo novo);
   documentada aqui, não remediada.

3. **Banco de desenvolvimento real não está "limpo"** — ver seção Evidência
   acima. Não é um incidente de desenvolvimento da Missão 50 em si, mas é
   o resultado mais importante desta missão: o veredito de certificação
   honesto, hoje, é `false`, por acúmulo real de estado nas Missões 42/46,
   não por defeito do `CertificationService`.

## Critério de aceite

- [x] `CertificationService` implementado, reusando 100% dos serviços das
      Missões 44/45/46/47/49 sem duplicar lógica.
- [x] Gate fail-closed (`certification_platinum_require_clean_diagnostics`)
      com regra de produção em `validate_settings()`.
- [x] Duas rotas novas (`/certification/platinum/live`,
      `/certification/platinum/markdown`).
- [x] `CONFIG_SCHEMA_VERSION` 1.8.0 → 1.9.0, `CONFIG_CHANGELOG.md`
      atualizado.
- [x] 24 testes novos, 100% passando isoladamente (`24 passed` em 33.64s)
      e como parte da suíte completa (`30 passed` no lote que os contém,
      nas 3 execuções).
- [x] 3 execuções completas da suíte total (550 testes), 0 falhas em
      todas as 3 — evidência verificada de forma independente a partir
      dos logs brutos, não apenas do relato do subagente que executou.
- [x] Veredito real (não hipotético) gerado contra o banco de
      desenvolvimento atual, com `platinum_certified` e `blocking_issues`
      reportados honestamente (resultado: `false`, por motivos reais e
      documentados — não um teste sintético).
- [x] Nenhuma API paga, serviço de nuvem ou chamada de rede usada.
- [x] Apenas arquivos relevantes da Missão 50 preparados para commit
      (nenhum `git add -A`).

## Próximos passos

Commit local na branch `missao-50-certificacao-platinum-v1.3` (sem push —
por instrução de Douglas, o push das 10 missões será feito por ele
pessoalmente ao final). Com a Missão 50 commitada, as Missões 41–50
(Configuração Centralizada, Gerenciador Inteligente de Filas, Cache
Inteligente, Diagnóstico Automático, Gerenciamento de Recursos, Sistema de
Alertas, Testes de Recuperação, Documentação Viva, Auditoria de
Dependências, Certificação Platinum v1.3) estão completas e commitadas em
branches separadas, aguardando revisão e push manual de Douglas. Sugestão
para quando Douglas revisar: o achado de `platinum_certified=false` no
banco de desenvolvimento atual (337 alertas + 795 jobs parados, herdados
das Missões 42/46) provavelmente vale uma limpeza manual antes de declarar
o ambiente "pronto", mas essa decisão é dele — não foi tocada aqui, por
estar fora do escopo desta missão.
