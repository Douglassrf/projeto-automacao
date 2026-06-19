# INTELLIGENCE_TEST_REPORT.md — Missão R05 (Teste de Inteligência)

Data: 2026-06-19. Commit testado: `700bf363e4d7d313edcb9e6c3b344603ea2101fd`. Backend real (`uvicorn`) rodando, rotas reais de inteligência/cérebro consultivo testadas via HTTP real (`curl`), nenhuma chamada externa real feita.

## 1. Mapeamento do código (antes do teste)

Três subsistemas de inteligência consultiva, todos `read_only:true`/`dry_run:true`/`can_execute:false` por construção:

- **`CampaignBrainAgent`** (`campaign_brain.py`): cérebro estratégico. `review_before_campaign()` analisa nicho/produto/orçamento/métricas e consulta memória evolutiva, `CampaignIntelligenceSafe` e `MetaUpdateWatcher`, retornando `decision` (SIM/NÃO), `confidence`, `blocked_reasons` e `recommended_solution`. Detecta nichos sensíveis (`emagrecimento`, `saude`, `cripto`, `apostas`, etc.) e promessas de risco (`garantido`, `milagroso`, `cura`, `100%`, `sem esforço`, `enriqueça rápido`) por busca de texto simples. `learn_after_campaign()` só grava em JSONL local, não executa nada.
- **`CampaignIntelligenceSafe`** (`campaign_intelligence_safe.py`): análise comparativa local sobre logs de decisão (`decision_feed.log`, `campaign_brain_memory.log`), sem banco de dados, sem rede.
- **`MetaUpdateWatcher`** (`meta_update_watcher.py`): registro manual/local de atualizações de política Meta, usado para avaliar risco contextual.
- Rotas reais montadas via `safe_router.py`: `GET /api/v1/brain/health`, `POST /api/v1/brain/review`, `GET /api/v1/brain/review/mock`, `POST /api/v1/brain/learn`, `GET /api/v1/brain/learn/mock`, `GET /api/v1/campaign-intelligence-safe/{health,summary,summary/mock,mock-seed}`, `GET/POST /api/v1/meta-updates/{health,list,register,assess,mock}`.
- **Achado de código, confirmado por grep**: nenhuma dessas rotas (`campaign_brain.py`, `campaign_intelligence_safe.py`, `meta_updates.py`) declara `Depends(get_current_user)` — mesmo padrão estrutural já confirmado no R04 para `meta_operator.py`.
- Por contraste, existe um quarto módulo, **`campaign_intelligence.py`** (rotas `/api/v1/campaign-intelligence/*`), que é a versão "real" com gravação em banco (criação de campanhas, métricas, regras de escala, aprovação/execução de ações Meta) — **essa sim declara `Depends(get_current_user)` em toda rota**, confirmado por leitura completa do arquivo (21 rotas, todas com `current_user: User = Depends(get_current_user)`).

## 2. Testes executados e resultado real

| # | Rota | Cenário | Esperado | Resultado real | Status |
|---|---|---|---|---|---|
| 1 | `GET /api/v1/brain/health` | health check | 200, modo consultivo | 200, `read_only:true`, `dry_run:true`, `can_execute:false` | ✅ |
| 2 | `GET /api/v1/brain/review/mock` | produto fitness, métricas boas, V1/R$25 | `decision:"SIM"` | 200, `decision:"SIM"`, `confidence:86`, `blocked_reasons:[]` | ✅ |
| 3 | `POST /api/v1/brain/review` | produto "Curso Emagrecimento **Garantido**", orçamento R$500 em V1, métricas fracas | deve **bloquear** (promessa de risco + orçamento acima do limite da etapa) | 200, `decision:"NÃO"`, `confidence:12`, `blocked_reasons:["budget_above_v1_limit","high_meta_policy_risk"]`, `meta_risk.level:"alto"`, `risky_promises:["garantido"]` | ✅ |
| 4 | `GET /api/v1/brain/learn/mock` | registrar aprendizado mock | grava em JSONL local, não executa campanha | 200, `stored.memory_file` confirmado por leitura real do arquivo (linha nova com `outcome:"WINNER"` apareceu em `campaign_brain_memory.log`) | ✅ |
| 5 | `GET /api/v1/campaign-intelligence-safe/health` | health check | 200, `database_required:false`, `external_api:false` | 200, confirmado | ✅ |
| 6 | `GET /api/v1/campaign-intelligence-safe/summary/mock` | análise comparativa mock | 200, dados agregados de logs locais | 200, `source_counts.decision_feed_total:300` | ✅ |
| 7 | `GET /api/v1/meta-updates/mock` | gera atualização mockada | 200, grava registro | 200, `status:"stored"` | ✅ |
| 8 | `POST /api/v1/meta-updates/register` | registrar atualização real de teste | 200, grava em `meta_updates.log` | 200, confirmado por leitura real do arquivo (nova linha `"source":"teste_r05"` presente) | ✅ |
| 9 | `GET /api/v1/meta-updates/list` | listar atualizações | retornar as 3 entradas (2 antigas + 1 nova) | 200, `count:3`, nova entrada presente | ✅ |
| 10 | `brain/health`, `campaign-intelligence-safe/health`, `meta-updates/list` | **sem nenhum header Authorization** | deveria ser 401 se fossem protegidas | **200 nas três** — confirma ausência estrutural de auth | ⚠️ achado |

## 3. Confirmado: detecção de risco funciona de fato, não é decorativa

O caso 3 é o teste mais importante: usei deliberadamente um nome de produto com a palavra "garantido" (uma das promessas de risco hardcoded em `SENSITIVE_NICHES`/`risky_promises`) e um orçamento de R$500 numa etapa V1 (cujo limite recomendado é R$25). O `CampaignBrainAgent` bloqueou corretamente nos dois eixos simultaneamente (`budget_above_v1_limit` e `high_meta_policy_risk`), reduziu a confiança para 12 (de uma base de 60) e recomendou a ação corretiva certa ("Reduzir orçamento da V1 para R$ 25"). Isso comprova que a lógica de revisão de risco é real, não apenas um campo decorativo na resposta.

## 4. Achado: mesmo padrão de ausência de autenticação do R04, agora em 3 rotas adicionais de inteligência

Confirmado por grep (zero `get_current_user` em `campaign_brain.py`, `campaign_intelligence_safe.py`, `meta_updates.py`) e por teste HTTP real sem header Authorization (caso 10): as rotas de cérebro consultivo, inteligência comparativa local e watcher de atualizações Meta não exigem nenhuma credencial — nem por configuração (`AUTH_REQUIRED`), nem por código (a dependency nunca é declarada). Isso é o mesmo padrão estrutural do R04, agora confirmado num segundo grupo de rotas.

**Ponto positivo de design encontrado nesta missão:** o módulo "real" `campaign_intelligence.py` (que grava em banco e pode aprovar/executar ações Meta) **declara corretamente `Depends(get_current_user)` em todas as 21 rotas** — ou seja, o time aplicou autenticação consistentemente onde a ação tem efeito de banco/produção, mas deixou de aplicá-la nas rotas "consultivas"/mock. Isso sugere que a ausência de auth nas rotas consultivas é uma omissão sistemática (mesmo padrão repetido), não um caso isolado — reforça a recomendação do R04 de tratar isso de forma abrangente na missão de segurança final (R14), revisando todas as rotas sem `Depends(get_current_user)` de uma vez, não rota por rota.

*Não corrigido nesta missão*, pela mesma razão do R04 (mudança de contrato de API, não apenas de config) — registrado como extensão do achado do R04 para a lista de pendências do R14.

## 5. O que funcionou corretamente (sem achado negativo)

- `CampaignBrainAgent` aplica corretamente a matriz de etapas (V1–V6), limites de orçamento por etapa, e detecção de nicho sensível/promessa de risco.
- `learn_after_campaign` e `register` realmente persistem em disco (confirmado por leitura direta dos arquivos `.log`, não apenas pela resposta HTTP).
- `CampaignIntelligenceSafe` opera inteiramente sobre logs locais, sem dependência de banco de dados ou rede (`database_required:false`, `external_api:false`).
- Nenhuma chamada externa real foi feita durante este teste.
- Contraste positivo: o módulo de inteligência "real" (`campaign_intelligence.py`, com banco de dados) aplica autenticação corretamente em 100% das suas rotas.

## 6. Conclusão da missão R05

| Item | Resultado |
|---|---|
| `CampaignBrainAgent` (revisão de risco/orçamento) | Funciona corretamente, bloqueio real testado e confirmado |
| `CampaignBrainAgent.learn_after_campaign` | Funciona, grava em disco, não executa campanha |
| `CampaignIntelligenceSafe` (análise comparativa local) | Funciona, sem banco/rede |
| `MetaUpdateWatcher` (registro e listagem) | Funciona, grava e lista corretamente |
| **Autenticação nas rotas consultivas (`/brain`, `/campaign-intelligence-safe`, `/meta-updates`)** | **Ausente — mesmo padrão estrutural do R04, confirmado com HTTP real sem token (200 ao invés de 401)** |
| Autenticação no módulo real (`/campaign-intelligence`, com banco) | Presente em 100% das rotas (ponto positivo) |
| Banco de produção real | Intacto, não tocado |

**Status R05: APROVADO COM RESSALVA.** A lógica de inteligência consultiva (revisão de risco, detecção de promessas problemáticas, limites de orçamento por etapa) funciona corretamente e de forma real, não decorativa. A ausência de autenticação nas rotas consultivas confirma e amplia o achado do R04 — fica consolidado como item único para a missão de segurança final (R14): aplicar `Depends(get_current_user)` em todas as rotas "safe"/consultivas/mock que hoje não a possuem. Pronto para avançar para R06.
