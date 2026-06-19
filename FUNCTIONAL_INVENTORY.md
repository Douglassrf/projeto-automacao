# FUNCTIONAL_INVENTORY.md — Missão H01

Auditoria funcional total do backend (`src/app`). 274 arquivos `.py`, 40 arquivos de rota, 41 de serviço, 3 repositories. Levantamento read-only, sem alterações de código. Critério: VERDE (funciona, testado, sem risco) / AMARELO (funciona mas com lacuna, dado simulado ou risco a corrigir) / VERMELHO (quebrado, sem teste crítico, ou comportamento enganoso/perigoso). Nada ficou sem classificação.

## 1. Rotas (`app/api/routes/`, 40 arquivos + infraestrutura)

| Área | Arquivos | Classificação | Justificativa |
|---|---|---|---|
| Infraestrutura de roteamento | `safe_router.py`, `router.py`, `main.py` | VERDE | Import dinâmico com try/except por módulo; rota não carregada vira diagnóstico, não crash. 40/40 rotas em disco registradas, nenhuma órfã. |
| Auth | `auth.py` | VERDE | Login/me, testado (`test_auth.py`). |
| Automation / Automation Control | `automation.py`, `automation_control.py` | VERDE | Testado, kill-switch funcional. |
| Ads | `ads.py` | VERDE | Testado indiretamente via `AdProcessor`. |
| Affiliate | `affiliate.py` | AMARELO | Rota funciona, mas a integração por trás (`AffiliateProvider`) é placeholder — ver seção 6. |
| Facebook/Meta core (`facebook.py`, `meta_operator.py`) | — | VERDE | Múltiplas camadas de guardrail testadas (13+ arquivos de teste dedicados); nenhum bypass incondicional encontrado. |
| Meta Updates, Campaign Brain, Campaign Intelligence (+ `_safe`) | — | VERDE | Pares real/safe bem definidos e testados. |
| Decision Logs / Decision Feed | — | VERDE | Testado. |
| Content Orchestrator / Learning Loop / Orchestration (+ `_safe`/`_bridge`) | — | AMARELO | Estrutura "sempre-safe" correta, mas `learning_loop.py` tem bug de status enganoso — ver seção 2 (Achados Críticos). |
| Video / Premium Render / Site Builder / Serverless Render (+ `_safe`/`_bridge`) | — | AMARELO | Bridges corretamente sempre-safe; mas `site_builder.py` real é legacy confirmado (ver seção 2). |
| Upload / UGC | `upload.py`, `ugc_processing.py` | VERDE | Validação real de upload testada. |
| Queue, Observability, Security, Master Context, Knowledge, Hybrid/Zero-Cost Stack, War Kit, Global Intelligence | — | VERDE | Funcionam como planejadores/observabilidade locais, testados, sem chamada externa real fora do esperado. |
| `app/emergency/main.py` (segunda instância FastAPI) | — | VERMELHO | Não conectada ao app principal, não referenciada por nenhum outro módulo — código órfão que pode confundir operação. |
| `src/meta_operator.py` (shim solto) | — | VERMELHO | Arquivo de 1 linha sem nenhum uso identificado — lixo de código. |

## 2. Serviços (`app/services/`, 40 arquivos)

| Serviço | Classificação | Justificativa |
|---|---|---|
| AdProcessor, AgencyOperatorService, AutomationControlService, AutomationProcessor, ContentOrchestrator, DecisionFeedService, FacebookMarketingAutomationEngine, HybridNoGpuStackPlanner, KnowledgeEngine, ObservabilityService, QueueService, UGCEdgeProcessor, UploadSecurity, ZeroCostStackPlanner | VERDE | Testados, sem chamada externa não controlada, sem dado mock fora de teste. |
| CampaignBrainAgent | VERDE | `read_only=True`/`dry_run=True` hardcoded por design — comportamento intencional e correto. |
| CampaignIntelligenceService, MetaCampaignOperator, MetaMarketingClient | VERDE | Maior superfície de risco do projeto (publicação real na Meta), mas com 6+ try/except, múltiplas camadas de aprovação e 13+ arquivos de teste dedicados. Nenhum sinal de risco de código encontrado. |
| CapiEnterpriseService | VERDE | Chamada real implementada corretamente, PII hasheada (SHA-256) antes de envio, gate de dry-run correto. |
| CampaignIntelligenceSafe, CampaignMemoryStore, MasterContextStore, MetaUpdateWatcher, LearningLoopBrainBridge, PremiumRenderBridge, ContentOrchestratorBridge | AMARELO | Sem teste dedicado encontrado (cobertura só indireta). Funcionalmente corretos (sempre-safe), mas não comprovados isoladamente. |
| **learning_loop.py** | **VERMELHO** | **Bug de integridade de dado**: quando o gate permite forward (`capi_enabled` + token configurados), o código marca `did_forward=True`/`forwarded_to_meta=True` mas o próprio comentário no código diz que é "placeholder seguro" — **não existe chamada HTTP real**. Ou seja, o sistema pode reportar "enviado à Meta" sem ter enviado. Precisa ser corrigido antes de qualquer uso com `capi_enabled=True` real. |
| FacebookAdMiner, MinerEngine | AMARELO | `mine()` retorna mock fixo sempre, mesmo no fluxo padrão (não é falha, é o estado real do projeto — mineração de anúncios reais nunca foi implementada). Documentado, mas precisa ficar claro para o usuário que não existe coleta real. |
| decision_ingest.py (`create_crisis_scenario`) | AMARELO | Dados sintéticos hardcoded residem no código de produção do serviço, não em teste — deveria ser movido para fixture de teste. |
| **premium_render.py** (`_ViralidadeRemodelTask`) | AMARELO | Classe órfã que simula `delay()` de Celery sem de fato enfileirar nada; instanciada em module-level sem nenhuma referência externa. Código morto a remover. |
| **site_builder.py** (real, não-bridge) | VERMELHO | Confirma o risco já documentado pelo próprio projeto em `master_context.py`: `load_template()` retorna string fixa (não carrega template real); `trigger_deploy`/`deploy_conversion_site` têm `dry_run=True` hardcoded sem nenhum caminho de código para deploy real. É puramente legado/vestigial. |
| war_kit_generator.py | AMARELO | Gerador de PDF interno descarta silenciosamente caracteres não-latin1 — pode corromper conteúdo em português com acentuação. |
| serverless_render.py | AMARELO | Retorna status `"queued"` (não `"dry_run"`) mesmo sendo 100% local — nome e status podem induzir o usuário a pensar que houve despacho real. |
| VideoRenderPipeline | VERDE | Chamadas reais implementadas corretamente (ElevenLabs/OpenAI), com fallback seguro; URLs hardcoded no código-fonte deveriam ir para `settings` (nota de manutenção, não bug). |
| orchestration_pipeline.py (`MasterOrchestrator`/`FreeStackOrchestrator`) | AMARELO | Shim de compatibilidade com zero lógica própria, conforme já documentado pelo projeto. |

## 3. Repositories (`app/repositories/`, 3 arquivos)

| Repository | Classificação | Justificativa |
|---|---|---|
| AdRepository, UserRepository | AMARELO | Funcionais, sem SQL injection (uso de ORM com binds), mas sem tratamento de erro local (violação de integridade propaga sem captura) e sem teste unitário dedicado. |
| DecisionLogRepository | AMARELO | Mesmo padrão acima, mais o agravante de usar estilo de Query API diferente (legado) do que `AdRepository` — inconsistência de padrão dentro do projeto. |

## 4. Processors / Pipelines

| Processor | Classificação | Justificativa |
|---|---|---|
| AdProcessor, AutomationProcessor, ZeroCostStackPlanner, HybridNoGpuStackPlanner, ServerlessRenderPlanner | VERDE/AMARELO | Ver detalhamento nas seções 1–2; sem dependência externa real, comportamento como documentado. |
| MetaCampaignOperator | VERDE | Único ponto de publicação real, sob múltiplas camadas de guardrail testadas. |
| VideoRenderPipeline, PremiumRenderPipeline | VERDE | Processamento real (FFmpeg/Pillow/TTS) funcional, com bridges sempre-safe corretos ao lado. |
| **`app/core/compat/legacy.py` (classe `NoOp`)** | **VERMELHO** | Código morto/órfão: define aliases (`MinerEngine=NoOp`, `MetaCampaignOperator=NoOp` etc.) que **nenhum módulo de produção importa** — só é referenciado por um teste de compatibilidade legado. Risco de confusão grave se alguém importar por engano pensando ser a implementação real. Recomenda-se remover ou isolar claramente. |
| Celery worker (`render_tasks.py`) | AMARELO | Único worker assíncrono real conectado, mas `settings.celery_enabled=False` por padrão — não está ativo em runtime normal. |

## 5. Middleware (`app/core/`, `app/main.py`, `app/middleware.py`)

| Middleware/Guard | Classificação | Justificativa |
|---|---|---|
| `observability_trace_middleware` (global) | VERDE | Correlation/execution/mission id, rate limit e log funcionando. |
| InMemoryRateLimiter / ApiGatewayGuard | AMARELO | Funciona e testado, mas é só em memória (não escala entre processos, reseta no restart) e tem bypass documentado via header `User-Agent: testclient` — aceitável para testes, mas **deve ser revisado antes de ambiente com múltiplos workers/produção real**. |
| **`UploadSizeLimitMiddleware`** | **VERMELHO** | Implementado, mas **nunca registrado** em `app.add_middleware` — a proteção de tamanho de upload **não está ativa** na aplicação real, apesar de existir o código. |
| **CORS** | **VERMELHO** | `settings.cors_origins`/`allowed_origins` existem na configuração, mas **`CORSMiddleware` nunca é importado nem registrado** — configuração 100% órfã, sem efeito algum. |
| `get_current_user` (auth via Depends) | AMARELO | Quando `auth_required=False`, ignora token completamente e retorna admin default sem checagem — comportamento correto para ambiente local, mas **risco real se essa flag for deixada `False` em produção**. A suíte de testes desliga essa flag globalmente (relevante para H04). |
| route_security guards, CommandValidator, RBAC (`security_hardening.py`), ZeroTrustInternalValidator | VERDE | Testados, sem bypass incondicional encontrado; somente `OWNER` pode `meta.real.execute`. |
| `security.py` (JWT/hash) | AMARELO | `jwt_secret_key` tem default fraco `"change-me-super-secret-local-key"` — funcional, mas **deve ser obrigatoriamente sobrescrito por `.env` antes de qualquer uso real**, hoje não há trava que impeça rodar com o default fraco. |

## 6. Integrações externas

| Integração | Classificação | Justificativa |
|---|---|---|
| MetaMarketingClient (Graph API) | VERDE | Chamadas reais implementadas corretamente, dry-run por padrão e por credencial incompleta, sem segredo hardcoded. |
| CapiEnterpriseService (Meta CAPI) | VERDE | Implementação real correta, PII hasheada antes do envio. |
| VideoRenderPipeline → ElevenLabs/OpenAI TTS | VERDE | Chamadas reais corretas com fallback seguro. |
| **AffiliateProvider** (Hotmart/Kiwify/Eduzz/Braip) | **VERMELHO** | **Funcionalidade anunciada mas nunca implementada**: mesmo com credenciais configuradas, nenhuma chamada HTTP real existe — o próprio código tem comentário `"Placeholder adapter point"`. Configurar a credencial não ativa nada real; só muda um campo de status. |
| **CampaignKitStorageProvider** (S3 / Google Drive) | **VERMELHO** | Mesmo padrão: sem `boto3`/SDK Google importado em nenhum lugar; com bucket configurado, retorna apenas `"adapter_ready"` — nenhum upload real ocorre. |
| ActivityLogger | VERDE | Logger local, sem dependência externa, funcional. |

## Resumo

| Cor | Contagem aproximada de itens | Significado |
|---|---|---|
| VERDE | ~30 módulos/áreas | Funciona, testado, sem ação necessária agora. |
| AMARELO | ~15 módulos/áreas | Funciona, mas com lacuna de teste, dado simulado em código de produção, ou configuração órfã — corrigir antes de "ligar para valer". |
| VERMELHO | 7 itens | Bug real (status enganoso em `learning_loop.py`), proteção implementada mas inativa (upload size limit, CORS), funcionalidade anunciada e nunca implementada (Affiliate, Storage S3/Drive), ou código órfão/morto (`legacy.py NoOp`, `emergency/main.py`, `src/meta_operator.py` shim). **Nenhum destes é "explosão" — nenhum executa ação real perigosa por engano —, mas todos precisam de correção antes de qualquer promessa de "produção real".**

## Achados críticos a corrigir antes de qualquer ativação real (ordem de prioridade)

1. **`learning_loop.py`** — corrigir o campo `forwarded_to_meta`/`did_forward` para não reportar sucesso quando a chamada é apenas placeholder. Isso é uma inconsistência de dado, não um simples "TODO".
2. **CORS ausente** e **UploadSizeLimitMiddleware não registrado** — registrar os dois em `app/main.py` antes de qualquer exposição além de `localhost`.
3. **`jwt_secret_key` com default fraco** — adicionar validação que bloqueia boot se o valor default for usado fora de ambiente de teste.
4. **AffiliateProvider e CampaignKitStorageProvider** — decidir entre implementar de fato ou deixar explícito na UI/documentação que são "não implementados", para não dar falsa sensação de integração ativa.
5. Remover ou isolar código órfão: `app/core/compat/legacy.py` (NoOp), `app/emergency/main.py`, `src/meta_operator.py`.

Nenhuma das classificações acima envolveu execução de código real, chamada externa real, ou alteração de dado — levantamento 100% read-only.
