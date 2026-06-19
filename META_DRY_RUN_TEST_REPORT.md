# META_DRY_RUN_TEST_REPORT.md — Missão R10 (Teste Meta dry-run)

Data: 2026-06-19. Commit testado: `700bf363e4d7d313edcb9e6c3b344603ea2101fd`. Backend real (`uvicorn`) rodando, 16 rotas reais do operador Meta testadas via HTTP real (`curl`), incluindo cenários adversariais (tentativa explícita de forçar publicação real). Logs reais lidos em disco antes/depois (`logs/meta_campaign_operator.log`, +14 linhas rastreadas evento a evento). **Nenhum segredo foi impresso em nenhum momento — todas as verificações de credencial usaram apenas presença/comprimento/prefixo mínimo para identificação de formato, nunca o valor completo.**

## 1. Achado central da missão (leia isto primeiro)

Diferente de todas as missões R04–R09, **este projeto tem, no `.env` real do workspace do usuário, credenciais da Meta com formato consistente com credenciais reais e funcionais**, não placeholders:

| Variável | Presente? | Formato observado |
|---|---|---|
| `META_ACCESS_TOKEN` | Sim | 202 caracteres, prefixo de 4 caracteres consistente com o padrão de token de acesso real da Meta (tokens de teste/placeholder não seguem esse padrão) |
| `META_AD_ACCOUNT_ID` | Sim | 15 dígitos numéricos — formato de ID real de conta de anúncios |
| `META_PAGE_ID` | Sim | 15 dígitos numéricos — formato de ID real de página |
| `META_PIXEL_ID` | Sim | 15 dígitos numéricos — formato de ID real de pixel |
| `META_INSTAGRAM_ACTOR_ID` | Presente, vazio | — |

Confirmado também: estas são as mesmas credenciais usadas pelo servidor real testado nesta missão (`/campaign-operator/status` → `configured_credentials:true`) — ou seja, **todas as 16 chamadas desta missão foram feitas contra um servidor com credenciais reais carregadas**, não contra um ambiente de teste com credenciais fictícias. Isto torna os resultados abaixo uma prova mais forte do que testes equivalentes feitos sem credenciais (onde a ausência de credencial sozinha já impediria qualquer chamada real).

**Boa notícia de higiene confirmada**: o arquivo `.env` do workspace real **não está rastreado pelo git** (`git ls-files .env` vazio) e **está corretamente listado no `.gitignore`** (linhas `.env`, `*.env`, `.env.*`, com exceção explícita para `.env.example`). Não há evidência de que este token tenha sido commitado em algum momento do histórico do repositório.

**O que hoje impede uma chamada real à API da Meta, dado que a credencial existe:** exclusivamente quatro variáveis de configuração — `META_DRY_RUN=true`, `META_AUTOPUBLISH=false`, `META_ALLOW_ACTIVE_LAUNCH=false`, `META_REQUIRE_MANUAL_CONFIRMATION=true` — mais a lógica de guardrails internos do `MetaCampaignOperator`, validada nesta missão sob tentativa adversarial direta (testes T6, T7, T8, T13, T14 abaixo). Não há uma segunda camada de "credencial ausente" como rede de segurança nesta área específica do projeto — a rede de segurança é 100% feita de configuração + código.

**Recomendação imediata (antes de R11):** o usuário deve confirmar se este token é de uma conta sandbox/teste dedicada ou de uma conta real de produção vinculada a dinheiro de verdade. Se for produção real, considerar revogar/rotacionar o token no Gerenciador de Negócios da Meta após o fim desta auditoria, mesmo que nenhuma chamada real tenha ocorrido.

## 2. Mapeamento do código (antes do teste)

- **11 rotas do operador Meta** em `api/routes/meta_operator.py`: `GET status`, `POST v3/launch`, `POST rollback`, `POST rollback/policy`, `POST production/{readiness,credential-review,assisted-execution,post-execution-monitor,hardening-review}`, `GET campaign/dry-run/mock`, `POST campaign/dry-run`. **Nenhuma declara `Depends(get_current_user)`** — confirmado por leitura completa do arquivo.
- **Fórmula mestra de segurança** em `launch_v3()`: `effective_dry_run = payload.mode=="dry_run" OR meta_client.dry_run OR NOT settings.meta_autopublish`. Três condições independentes ligadas por OU — qualquer uma sendo verdadeira força simulação. Hoje, com `META_DRY_RUN=true` e `META_AUTOPUBLISH=false`, **duas das três condições já são verdadeiras**, então mesmo que uma falhasse a outra ainda protegeria.
- **Guardrails nomeados** (`_validate_guardrails`, 11 checagens): `operator_enabled`, `meta_environment`, `purchase_event`, `autopublish`, `active_launch`, `geo`, `exclude_brazil` (warning), `creative_volume` (warning), `meta_min_budget`, `spend_guard`, `manual_confirmation`/`payload_integrity`. Resultado de cada guardrail é **de fato aplicado por criativo** — diferente do achado do R06/R08 (guard calculado e descartado), aqui um guardrail bloqueado marca o resultado daquele criativo como `status:"blocked"` com `meta_campaign_id:null`.
- **`MetaMarketingClient`** (`integrations/meta_marketing.py`): todo método capaz de chamada real (`publish_campaign_plan`, `get_campaign_status`, `get_campaign_spend`, `remove_campaign`, etc.) tem um `if self.dry_run: return {...}` antes de qualquer `httpx.get/post/delete`. Confirmado por leitura das 7 ocorrências — é a única camada do projeto até agora (R01-R09) onde a integração real de fato existe e é de fato alcançável por código, tornando este o teste de maior risco real da auditoria.
- **`credential_payload_review`/`production_hardening_review`**: ambos retornam `secrets_redacted:true` e nunca incluem o valor do token — apenas booleanos (`access_token_present`, etc.). Confirmado por leitura do código e, nesta missão, por teste HTTP real (seção 4).
- **`assisted_execution_gate`**: exige frase exata `"EU APROVO EXECUCAO REAL ASSISTIDA"` + `credential_payload_review` pronto + `rollback_policy` pronto + ambiente Meta válido. Mesmo com tudo "ready", a função **nunca publica** (`published:false, executed:false` hardcoded) — o máximo que ela faz é sinalizar `status:"ready_for_human_execution"`, exigindo uma ação humana fora da API.

## 3. Testes executados e resultado real

| # | Rota | Cenário | Esperado | Resultado real | Status |
|---|---|---|---|---|---|
| 1 | `GET /campaign-operator/status` | health/status | `configured_credentials` deve refletir a realidade | 200, `dry_run:true`, `autopublish_allowed:false`, `active_launch_allowed:false`, **`configured_credentials:true`** (achado central) | ✅ |
| 2 | `GET /campaign/dry-run/mock` | produto fitness fixo, Brain aprova | `decision:"SIM"`, dry-run simulado | 200, `decision:"SIM"`, `confidence:83`, `operator_response.dry_run:true`, todos os 11 guardrails `ok` | ✅ |
| 3 | `POST /campaign/dry-run` | produto "Curso Emagrecimento **Garantido**" (nicho sensível + promessa de risco) | Brain deve bloquear antes mesmo de chamar o operador | 200, `status:"blocked_by_brain"`, `decision:"NÃO"`, `confidence:56`, `blocked_reasons:["high_meta_policy_risk"]`, `operator_response:null` (operador nem foi chamado) | ✅ |
| 4 | `POST /campaign/dry-run` | produto seguro, payload mínimo válido | dry-run simulado normalmente | 200, `decision:"SIM"` (confidence 96), `operator dry_run:true`, `meta_campaign_id` com prefixo `dry_` | ✅ |
| 5 | `POST /campaign-operator/v3/launch` | `mode:"dry_run"` direto na rota real (não pelo wrapper) | simulado, sem publicar | 200, `dry_run:true`, `published:0`, `blocked:0`, `results[0].status:"simulated"`, `meta_campaign_id` prefixo `dry_` | ✅ |
| 6 | `POST /campaign-operator/v3/launch` **ADVERSARIAL** | `mode:"publish_active"`, `confirmed_by_user:true`, pixel_id com formato real de 15 dígitos, sem hash aprovado | deve permanecer bloqueado mesmo pedindo publicação ativa real | 200, **`dry_run:true` mesmo assim**, `published:0`, `blocked:1`; guardrails `autopublish` e `active_launch` retornaram `blocked` explicitamente; resultado do criativo: `status:"blocked"`, `meta_campaign_id:null` | ✅ |
| 7 | `POST /campaign-operator/v3/launch` **ADVERSARIAL** | `mode:"publish_paused"`, `confirmed_by_user:true`, orçamento R$500 (10x o limite), 4 criativos | deve bloquear pelos mesmos motivos, em escala | 200, `dry_run:true`, `published:0`, `blocked:4` (todos os 4 criativos), guardrail `autopublish:blocked` em todos | ✅ |
| 8 | `POST /campaign-operator/rollback` **ADVERSARIAL** | `action:"delete"`, `force_dry_run:false`, `confirmed_by_user:true` | tentar forçar rollback real destrutivo | 200, `dry_run:true`, `attempted:0`, `executed:0` — `attempted:0` porque não existe nenhum recurso real criado para reverter (`meta_created_resources.jsonl` nunca existiu) | ✅ |
| 9 | `POST /campaign-operator/rollback/policy` | checklist formal de rollback | informativo, sem execução | 200, `status:"dry_run_ready"`, `executed:false`, `would_execute_real_rollback:false` | ✅ |
| 10 | `POST /campaign-operator/production/readiness` | checklist de prontidão para produção | bloqueado por falta de aprovação humana | 200, `status:"blocked"`, guard de rota também `blocked` (`human_approval_required`) — duas camadas concordam | ✅ |
| 11 | `POST /campaign-operator/production/credential-review` | payload de lançamento completo, sem confirmações | verificar mascaramento total de credenciais | 200, `status:"blocked"`, `secrets_redacted:true`, campo `credentials` só com booleanos (`access_token_present:true`, etc.) — **grep no JSON de resposta por padrão do token real: 0 ocorrências** | ✅ |
| 12 | `POST /campaign-operator/production/assisted-execution` | frase de aprovação **errada** (`"eu aprovo"`) | deve bloquear por frase incorreta | 200, `status:"blocked"`, `approval_phrase:blocked` (frase exata exigida) | ✅ |
| 13 | `POST /campaign-operator/production/assisted-execution` **ADVERSARIAL MÁXIMO** | frase exata correta + `confirmed_by_user`+`rollback_policy_ack`+`brain_approval_ack` todos `true` (cooperação total do chamador) | mesmo assim deve continuar bloqueado, pois `dry_run`/`autopublish` ainda não permitem produção real | 200, `status:"blocked"` (não chegou a `ready_for_human_execution`), `approval_phrase:ok` mas `credential_payload_review:blocked` (por `dry_run_disabled`/`autopublish` ainda bloqueados); `published:false, executed:false`; grep por token real: 0 ocorrências | ✅ |
| 14 | `POST /campaign-operator/production/post-execution-monitor` **ADVERSARIAL** | `force_dry_run:false`, `allow_real_insights:true` (tentar forçar consulta real de gasto) | `effective_dry_run` deve permanecer `true` pela condição `meta_client.dry_run` | 200, `dry_run:true`, `executed_actions:[]`, `monitored_campaigns:[]` (zero recursos reais para monitorar de qualquer forma) | ✅ |
| 15 | `POST /campaign-operator/production/hardening-review` | auditoria de configuração | deve detectar corretamente o ambiente atual | 200, `status:"blocked"` — apontou corretamente `auth_required:blocked` (mesma causa raiz do R02) e `kill_switch_reviewed:warning`; confirmou `dry_run_currently_safe:ok` e `autopublish_currently_blocked:ok` | ✅ |
| 16 | `GET /campaign-operator/status` **sem header Authorization** | nenhuma das 11 rotas declara `Depends(get_current_user)` | 200 esperado (sem proteção alguma no código) | 200, confirmado — mesmo padrão estrutural do R04–R09 | ⚠️ achado (já mapeado, não novo) |

## 4. Confirmado: nenhum segredo foi exposto em nenhuma resposta HTTP ou linha de log

Os testes 11 e 13 enviaram deliberadamente payloads completos pedindo revisão/execução assistida, justamente os cenários onde uma implementação descuidada poderia "ecoar" a credencial de volta na resposta para depuração. Em ambos os casos, fiz `grep` bruto no JSON de resposta salvo em disco pelo prefixo de identificação do token real — **zero ocorrências nos dois arquivos**. As 14 novas linhas escritas em `logs/meta_campaign_operator.log` durante esta missão (1813 → 1827 linhas, uma linha por evento interno, rastreadas e contadas uma a uma) também foram verificadas da mesma forma — **zero ocorrências**. Isso confirma que o desenho de "nunca expor segredo" (`secrets_redacted:true` declarado no código) é also verdadeiro na prática, não apenas uma promessa de docstring.

## 5. Confirmado: a dupla camada de guardrails é a mais robusta de toda a auditoria até agora

Os testes 6, 7, 8, 13 e 14 são, juntos, o teste mais adversarial de toda a sequência R04–R10: cada um tentou, por um vetor diferente, obter alguma forma de execução real ou de exposição de dado sensível — modo de publicação ativa, orçamento 10x acima do limite, rollback destrutivo forçado, frase de aprovação completa com todas as confirmações auxiliares marcadas como verdadeiras, e tentativa de forçar consulta real de gasto. Em **nenhum dos cinco casos** o sistema chegou a um estado de publicação real, e em nenhum caso o `meta_created_resources.jsonl` (que só é escrito no caminho de publicação real) chegou a ser criado — confirmado por verificação direta em disco antes e depois da bateria completa. Diferente do achado do R06 (guard calculado mas nunca aplicado) e do R08 (guard calculado e completamente descartado, pior caso da auditoria), aqui o resultado do guardrail é **lido e usado** para marcar cada criativo como `blocked` individualmente, e a fórmula `effective_dry_run` tem três condições redundantes ligadas por OU — uma defesa em profundidade real, não apenas decorativa.

## 6. Achado (já mapeado, não novo): ausência de autenticação nas rotas do operador Meta

Confirmado por leitura de código (zero `Depends(get_current_user)` nas 11 rotas) e por teste HTTP real (caso 16). Mesmo padrão estrutural das missões R04–R09 — consolidado para a lista do R14, sem necessidade de correção nesta missão.

## 7. O que funcionou corretamente (sem achado negativo)

- `effective_dry_run` bloqueia simulação em 100% dos cenários testados, incluindo os 5 cenários adversariais acima.
- Guardrails nomeados (`autopublish`, `active_launch`, `creative_volume`, etc.) são calculados e **aplicados de fato** ao resultado de cada criativo — não apenas informativos.
- `CampaignBrainAgent` bloqueia corretamente produtos com nicho sensível/promessa de risco antes mesmo de o operador ser chamado (`/campaign/dry-run`, teste 3).
- Mascaramento de credenciais é real em toda resposta HTTP e em todo log gravado, confirmado por grep direto, não apenas por inspeção de código.
- `assisted_execution_gate` nunca publica nem executa, mesmo no cenário de cooperação total do chamador (frase certa + todas as confirmações), porque depende de `credential_payload_review`, que por sua vez depende de `META_DRY_RUN=false`+`META_AUTOPUBLISH=true` — nenhum dos dois pode ser setado via payload de API, apenas via configuração de ambiente do servidor.
- `production_hardening_review` audita corretamente o próprio ambiente e identifica com precisão o achado de auth do R02 como bloqueante.
- `.env` com a credencial real está corretamente fora do controle de versão (gitignored, nunca commitado).

## 8. Conclusão da missão R10

| Item | Resultado |
|---|---|
| Credenciais reais da Meta configuradas no ambiente | **Sim — achado central da missão, ver seção 1** |
| `.env` protegido contra versionamento | Sim — gitignored, nunca commitado |
| Bloqueio de publicação real sob tentativa adversarial (modo ativo, orçamento alto, rollback forçado, frase de aprovação completa) | Funciona em 100% dos 5 cenários testados |
| Mascaramento de segredos em resposta HTTP e em log | Funciona, confirmado por grep direto, zero ocorrências |
| Guardrails nomeados aplicados de fato (não apenas calculados) | **Sim — o melhor resultado de toda a auditoria R04–R09 neste quesito** |
| `meta_created_resources.jsonl` (só existe após publicação real) | Nunca criado, antes ou depois dos 16 testes |
| **Autenticação nas rotas do operador Meta** | **Ausente — mesmo padrão estrutural do R04–R09** |
| Banco de produção real | Intacto, não tocado |

**Status R10: APROVADO COM ALERTA.** A lógica de simulação e os guardrails do operador Meta são, de longe, os mais robustos de toda a auditoria até agora — resistiram a cinco tentativas adversariais distintas sem nunca aproximar-se de uma publicação real, e o mascaramento de credenciais é genuíno em toda superfície testada. O alerta da missão não é de código: é a confirmação de que **credenciais reais da Meta estão configuradas no ambiente de teste/produção local**, protegidas hoje exclusivamente por flags de configuração (`META_DRY_RUN`, `META_AUTOPUBLISH`, `META_ALLOW_ACTIVE_LAUNCH`) e pelos guardrails internos — sem uma segunda rede de segurança por ausência de credencial, como existia implicitamente em todas as outras missões. Recomenda-se que o usuário confirme a natureza dessas credenciais (sandbox vs. produção real) antes de avançar para R11, e que R11 ("Teste Meta real controlado") seja desenhado para validar os mesmos caminhos por meios que não dependam de jamais flipar `META_DRY_RUN`/`META_AUTOPUBLISH` no ambiente com credenciais reais carregadas. Pronto para avançar para R11, com essa restrição de desenho explicitada.
