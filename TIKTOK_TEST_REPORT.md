# TIKTOK_TEST_REPORT.md — Missão R09 (Teste TikTok)

Data: 2026-06-19. Commit testado: `700bf363e4d7d313edcb9e6c3b344603ea2101fd`. Backend real (`uvicorn`) rodando, rotas reais testadas via HTTP real (`curl`), banco SQLite real consultado diretamente (`sqlite3`), logs reais lidos em disco. **Achado central da missão: não existe nenhuma integração real (nem mock funcional dedicado) com a API do TikTok neste projeto** — confirmado por grep amplo e por leitura de código, não apenas por ausência de teste.

## 1. Mapeamento do código (antes do teste)

- **Busca exaustiva por uma rota dedicada de TikTok**: `grep -rn "tiktok" src/app/api/routes/` retornou **zero arquivos**. Não existe `api/routes/tiktok.py` nem qualquer rota cujo path contenha `/tiktok`.
- **Busca por chamada real à API do TikTok**: `grep -rn "ads.tiktok.com|open.tiktokapis|business-api.tiktok"` em todo `src/` retornou **zero ocorrências**. Não há URL, SDK, client HTTP ou qualquer código que chame a API real do TikTok em nenhum lugar do projeto.
- A palavra "TikTok"/"tiktok" aparece em 17 arquivos, mas sempre em um destes 4 papéis, nenhum deles uma integração funcional:
  1. **Camada de Global Intelligence** (`core/global_intelligence_contract.py`, `core/global_operator_hub.py`, `core/market_radar.py`, `core/real_connectors_readiness.py`): "tiktok" é uma das 5 strings de plataforma suportadas (`meta, google, tiktok, linkedin, pinterest`) para normalização de sinal de anúncio, ranking de oportunidades e checklist de credenciais necessárias para uma futura conexão real. Todas as funções retornam explicitamente `will_execute_real_action:false`/`will_activate_spend:false`, e o módulo de readiness **bloqueia ativamente** qualquer tentativa de habilitar rede ou carregar credenciais (`enable_network`/`load_credentials` geram `blocked_reasons`, não habilitam nada).
  2. **Bridges/orquestradores "safe"** (`video_pipeline_bridge.py`, `site_builder_bridge.py`, `premium_render_bridge.py`, `content_orchestrator_bridge.py`, `orchestration_pipeline_safe.py`, `learning_loop_bridge.py`): todos retornam um campo hardcoded `"tiktok_real": false` em seus health-checks/manifestos, e os próprios docstrings declaram "Não chama TikTok". Nenhum desses arquivos contém qualquer código que tente chamar TikTok — é uma flag declarativa de "isto está desligado", não uma integração desligada por config.
  3. **`agency_operator.py`** (serviço + rota + schema): uma máquina de estados de workflow de conteúdo gravada em banco (Create → Approve → Schedule → Publish), onde `platform: Literal["Instagram","Facebook","WhatsApp","TikTok","Meta Ads"]` é apenas um campo de metadado salvo na linha do banco. A transição `publish` apenas grava `status="PUBLISHED"` na tabela `content_workflows` — confirmado por leitura completa do arquivo e por grep (`requests.`/`httpx.`/`urllib.`/`http.client`: zero ocorrências) que não existe nenhuma chamada de rede nesse fluxo.
  4. **Metadados/roadmap**: `master_context.py` lista "TikTok Engine futuro" como item de roadmap (explicitamente marcado "futuro"); `commercial_api_snapshot.py` lista "tiktok" como plataforma incluída nos planos comerciais "growth"/"enterprise" (metadado de billing, não acesso funcional).
- Rotas reais e externamente acessíveis que tocam essas funções: `POST /api/v1/global-intelligence/{normalize-ad,market-radar,operator-dry-run,real-connectors-readiness}` (todas declaram `Depends(get_current_user)`), `GET/POST /api/v1/orchestration-safe/{health,mock-run,run}` (**nenhuma declara auth**), `POST /api/v1/agency-operator/workflows` e `POST /api/v1/agency-operator/workflows/{id}/{action}` (**declaram apenas `Depends(get_db)`, nenhuma declara `get_current_user`** — achado novo, ainda não visto nas missões R04–R08).

## 2. Testes executados e resultado real

| # | Rota | Cenário | Esperado | Resultado real | Status |
|---|---|---|---|---|---|
| 1 | `POST /global-intelligence/normalize-ad` | sinal TikTok completo (headline, body, métricas reais) | normalizado, `will_execute_real_action:false` | 200, `status:"normalized"`, `signal_quality:85`, `ctr_percent:3.5`, `cpa:15.0179` (420.50/28, cálculo correto) | ✅ |
| 2 | `POST /global-intelligence/market-radar` | 2 sinais TikTok + 1 sinal Meta | TikTok corretamente agrupado/ranqueado | 200, `status:"radar_ready"`, TikTok ficou em 1º lugar (`heat_score:100` vs Meta `78.75`) | ✅ |
| 3 | `POST /global-intelligence/real-connectors-readiness` | `platforms:["tiktok"]` | apenas checklist, sem rede/credencial | 200, `connectors[0].platform:"tiktok"`, `network_enabled:false`, `credentials_loaded:false`, `real_write_enabled:false`, requisitos listados (`sandbox_app, advertiser_id, access_token, manual_approval`) | ✅ |
| 4 | mesmo, **adversarial**: `enable_network:true, load_credentials:true` | tentar forçar habilitação de rede/credenciais | deve bloquear ativamente | 200, `blocked_reasons` agora inclui `"network_enable_forbidden_in_readiness"` e `"credential_loading_forbidden_in_readiness"` — nenhum dos dois foi habilitado | ✅ |
| 5 | `POST /global-intelligence/operator-dry-run` | `platform:"tiktok"`, orçamento válido (R$5) | plano dry-run, sem execução real | 200, `will_create_real_campaign:false`, `will_activate_spend:false`, `requires_human_approval:true`, `execution_mode:"dry_run_only"` (bloqueado por campos de criativo incompletos no brief, comportamento conservador esperado) | ✅ |
| 6 | mesmo, **adversarial**: orçamento R$5000 | deve bloquear por orçamento acima do limite inicial | 200, `blocked_reasons` inclui `"dry_run_budget_above_initial_limit"`, e o plano grava `daily_budget_brl:5` (clamped, nunca o valor pedido) | ✅ |
| 7 | `GET /orchestration-safe/mock-run` | ciclo completo (content+vídeo+imagens+site, todos bridges safe) | `tiktok_real:false` mantido fim a fim | 200, 8 steps todos `ok`, manifesto com `blocked.tiktok_real:true` (= bloqueio ativo) | ✅ |
| 8 | `POST /agency-operator/workflows` | criar workflow `platform:"TikTok"`, `requires_approval:true` | grava no banco, status inicial `REVIEW_PENDING` | 200, `id:1`, `status:"REVIEW_PENDING"`, `platform:"TikTok"` | ✅ |
| 9 | `POST /agency-operator/workflows/1/{approve,schedule,publish}` em sequência | transições de estado, sem chamada externa | status final `PUBLISHED`, nenhuma chamada de rede | 200 nas 3 chamadas, `status:"PUBLISHED"` | ✅ |
| 10 | (verificação de banco) | confirmar persistência real | `SELECT` direto no SQLite deve mostrar a linha | `(1, 'TikTok', 'PUBLISHED')` confirmado via `sqlite3` direto no arquivo `.db` | ✅ |
| 11 | (verificação de código) | confirmar zero chamada de rede em `agency_operator.py` | nenhuma ocorrência de `requests.`/`httpx.`/`urllib.`/`http.client` | confirmado por grep — nenhuma ocorrência | ✅ |
| 12 | (verificação de disco) | confirmar que `CampaignBrainAgent.learn_after_campaign` gravou as entradas reais desta rodada | linhas com `"Global Signal tiktok"`/`"Global Operator tiktok"` no log | confirmado por leitura real de `campaign_brain_memory.log` — 612 ocorrências da palavra "tiktok" no arquivo, com as entradas desta rodada (timestamps `15:04:08.xxx`) presentes | ✅ |
| 13 | `POST /global-intelligence/normalize-ad` **sem header Authorization** | rota declara `Depends(get_current_user)` | deveria ser 401 se a proteção fosse efetiva | 200 — mesma causa raiz do R02 (`AUTH_REQUIRED=false`) | ⚠️ achado (já mapeado, não novo) |
| 14 | `GET /orchestration-safe/health` **sem header Authorization** | rota não declara `Depends` nenhum | 200 esperado (não há proteção alguma no código) | 200, confirmado — estrutural, mesmo padrão do R04/R05/R06/R08 | ⚠️ achado (já mapeado, não novo) |

## 3. Confirmado: TikTok não tem nenhuma porta de saída real neste projeto

A busca por `ads.tiktok.com`, `open.tiktokapis.com` e `business-api.tiktok.com` em todo o código-fonte (`src/`) não encontrou nenhuma ocorrência. Isso é diferente de todas as missões anteriores (R04–R08), onde sempre havia pelo menos uma camada "real" por trás da camada "safe" (ex.: `VideoRenderPipeline` chamando `ffmpeg` de fato, ou `SiteBuilderBridge` com um guard real de aprovação). Para TikTok, **não existe camada real nenhuma** — todo o código relacionado a TikTok é: (a) cálculo local de inteligência/ranking que aceita "tiktok" como rótulo de plataforma, (b) flags hardcoded `false` declarando que a integração está desligada, ou (c) um campo de metadado salvo em banco que nunca dispara rede. Os testes 3 e 4 são os mais importantes: mesmo pedindo explicitamente para habilitar rede e carregar credenciais (`enable_network:true, load_credentials:true`), o código bloqueia ativamente essas duas tentativas com motivos nomeados — não é apenas "a funcionalidade não foi implementada", é "a tentativa de habilitação é detectada e rejeitada por código".

## 4. Achado novo: rotas de `agency-operator` não exigem autenticação (nenhuma, nem por código nem por config)

Confirmado por leitura de `api/routes/agency_operator.py`: as três rotas (`POST /workflows`, `GET /workflows`, `POST /workflows/{id}/{action}`) declaram apenas `Depends(get_db)` — nunca `Depends(get_current_user)`. O teste 8 confirma na prática: criei, aprovei, agendei e publiquei um workflow completo (incluindo a transição para `PUBLISHED`) sem nenhum header `Authorization`, e tudo funcionou normalmente, com persistência real no banco. Isso é o mesmo padrão estrutural já visto em `meta_operator.py` (R04), `campaign_brain.py`/`campaign_intelligence_safe.py`/`meta_updates.py` (R05), `site_builder.py`/`site_builder_safe.py` (R06) e `video_pipeline_safe.py` (R08) — mas é a primeira vez que esse padrão é confirmado especificamente nas rotas de `agency-operator`. Registrado como extensão da lista consolidada para R14.

**Risco prático hoje:** baixo para dano externo (a transição `publish` não chama nenhuma API real, apenas muda uma string de status no banco), mas qualquer chamador anônimo pode criar/aprovar/"publicar" workflows de conteúdo no banco de produção sem nenhuma credencial, o que pode poluir dados reais ou ser usado para gerar volume de registros falsos.

## 5. O que funcionou corretamente (sem achado negativo)

- Normalização de sinal TikTok calcula métricas corretamente (CTR, CPA, signal_quality) e ranqueia junto com outras plataformas no Market Radar sem favorecimento nem erro de cálculo.
- O checklist de readiness de conectores reais (`real_connectors_readiness`) bloqueia ativamente qualquer tentativa de habilitar rede ou credenciais, mesmo sob requisição explícita adversarial — não é um bloqueio passivo por ausência de implementação, é um bloqueio ativo por código.
- O planejador de operador (`global_operator_dry_run`) sempre força `daily_budget_brl` para o teto de R$5 (`min(daily_budget, 5)`), independente do valor pedido, e nunca marca `will_activate_spend:true`.
- A orquestração completa (`orchestration-safe/mock-run`), que inclui vídeo, imagens e site, mantém `tiktok_real:false` íntegro fim a fim, mesmo acionando os 4 bridges safe em sequência.
- O workflow de `agency-operator` persiste corretamente no banco real (confirmado por leitura direta via `sqlite3`, não apenas pela resposta HTTP) e a transição `publish` é, de fato, apenas uma mudança de status — nenhuma chamada de rede ocorre, confirmado por grep no código-fonte.
- `CampaignBrainAgent.learn_after_campaign` grava entradas reais e rastreáveis em disco para cada chamada relacionada a TikTok, confirmado por leitura direta do log.

## 6. Conclusão da missão R09

| Item | Resultado |
|---|---|
| Integração real com a API do TikTok | **Não existe** — confirmado por busca exaustiva de URL/SDK no código-fonte |
| Normalização e ranking de sinais TikTok (inteligência local) | Funciona corretamente, cálculos validados |
| Bloqueio de habilitação de rede/credenciais reais (readiness) | Funciona, bloqueio ativo confirmado sob tentativa adversarial |
| Bloqueio de orçamento/execução real no operador dry-run | Funciona, clamp e bloqueio confirmados |
| Orquestração completa com TikTok desligado | Funciona, `tiktok_real:false` íntegro |
| Workflow de conteúdo TikTok (`agency-operator`) | Funciona como rastreador de status em banco; nenhuma chamada de rede |
| **Autenticação nas rotas de `agency-operator`** | **Ausente — achado novo, mesmo padrão estrutural do R04/R05/R06/R08** |
| Autenticação nas rotas de `global-intelligence` | Presente no código, neutralizada pelo `AUTH_REQUIRED=false` (mesma causa raiz do R02) |
| Autenticação nas rotas de `orchestration-safe` | Ausente — mesmo padrão estrutural já confirmado em outras rotas safe |
| Banco de produção real | Intacto, apenas a linha de teste criada nesta missão foi gravada |

**Status R09: APROVADO.** Não há funcionalidade real de TikTok para comprometer: tudo o que existe é inteligência local (normalização, ranking, planejamento dry-run), flags de bloqueio declarativo e um rastreador de status em banco — nenhum desses caminhos faz ou pode fazer uma chamada de rede real ao TikTok, mesmo sob tentativa adversarial direta de habilitar rede/credenciais. O único achado da missão é estrutural de autenticação (rotas de `agency-operator` sem `Depends(get_current_user)`), consistente com o padrão já registrado nas missões anteriores — adicionado à lista consolidada para R14, sem necessidade de correção imediata nesta missão. Pronto para avançar para R10.
