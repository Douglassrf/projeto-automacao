# Relatório — Missão 24A / Auditoria Profunda do OrchestrationPipeline

## Regra da Bússola

Missão executada em modo:

```txt
AUDITORIA SEM ALTERAÇÃO
```

Foi proibido:

```txt
alterar código
corrigir imports
executar pipeline real
acionar render real
acionar deploy real
acionar Meta
acionar TikTok
mexer em rotas
mexer em schemas
```

Nenhum arquivo do projeto foi modificado.

## Base auditada

Arquivo base:

```txt
projeto_automacao_missao23_sitebuilder_safe.zip
```

## Memória de partida

Estado anterior registrado:

```txt
Missão 23 — SiteBuilder Safe concluída.
Próxima missão — 24A, Auditoria Profunda do OrchestrationPipeline.
```

## Arquivos auditados

```txt
src/app/services/orchestration_pipeline.py
src/app/api/routes/orchestration.py
src/app/schemas/orchestration.py
src/app/tests/test_orchestration_pipeline.py
src/app/services/miner_engine.py
src/app/services/content_orchestrator_bridge.py
src/app/services/video_pipeline_bridge.py
src/app/services/premium_render_bridge.py
src/app/services/site_builder_bridge.py
src/app/core/compat/legacy.py
src/app/api/safe_router.py
```

## Veredito técnico

O `OrchestrationPipeline` atual está:

```txt
BLUEPRINT ANTIGO
PARCIAL
DESALINHADO COM OS SCHEMAS
DESALINHADO COM OS TESTES
RISCO ALTO PARA EXECUTAR DIRETO
```

Ele compila, mas não implementa o fluxo moderno esperado pelos schemas/testes nem usa os bridges Safe homologados.

## Arquivo principal

```txt
src/app/services/orchestration_pipeline.py
```

Classes encontradas:

```txt
MasterOrchestrator
FreeStackOrchestrator
```

Métodos:

```txt
MasterOrchestrator.__init__
MasterOrchestrator.run_empire_cycle
FreeStackOrchestrator.run
```

## Fluxo atual do MasterOrchestrator

O fluxo atual é:

```txt
MinerEngine()
        ↓
find_high_scale_targets(threshold=15)
        ↓
engine_viralidade_remodel.delay(...)
        ↓
deploy_conversion_site(...)
        ↓
log_event(...)
```

Problemas:

```txt
MinerEngine exige repository no __init__.
MinerEngine auditado não possui find_high_scale_targets.
engine_viralidade_remodel não foi confirmado como API moderna.
deploy_conversion_site vem do SiteBuilder antigo/legacy.
Não usa ContentOrchestrator Safe.
Não usa VideoPipeline Safe.
Não usa PremiumRender Safe.
Não usa SiteBuilder Safe.
Não usa DecisionFeed/Memory/Brain diretamente.
```

## Fluxo atual do FreeStackOrchestrator

Código atual:

```txt
class FreeStackOrchestrator(MasterOrchestrator):
    def run(self, payload=None):
        return {
            "status": "ok",
            "message": "Orquestração pronta",
            "payload": payload.model_dump() if hasattr(payload, "model_dump") else payload
        }
```

Problema:

A rota espera `OrchestrationResponse`, mas esse retorno simples não contém os campos exigidos pelo schema:

```txt
product_name
generated_at
run_mode
output_dir
pipeline_json
bash_runner
n8n_workflow
steps
```

## Rota FastAPI

Arquivo:

```txt
src/app/api/routes/orchestration.py
```

Rotas:

```txt
POST /api/v1/orchestration/run
POST /api/v1/orchestration/webhook-preview
```

Observação crítica:

A rota `/run` usa:

```txt
response_model=OrchestrationResponse
```

e exige autenticação:

```txt
current_user: User = Depends(get_current_user)
```

## Schema esperado

Arquivo:

```txt
src/app/schemas/orchestration.py
```

Schema principal:

```txt
OrchestrationRequest
OrchestrationStep
OrchestrationResponse
```

O schema espera uma orquestração moderna com:

```txt
product
mined_ads
workflow_name
run_mode: plan_only/dry_run/execute_local
include_site
include_video
include_images
include_deploy_payload
n8n_webhook_url
image_provider
voice_provider
video_provider
deploy_provider
```

Resposta esperada:

```txt
product_name
generated_at
run_mode
output_dir
pipeline_json
bash_runner
n8n_workflow
steps
war_kit_folder
site_preview
video_mp4
deploy_payload
warnings
```

## Testes encontrados

Arquivo:

```txt
src/app/tests/test_orchestration_pipeline.py
```

Testes:

```txt
test_orchestration_plan_only_creates_json_bash_and_n8n
test_orchestration_dry_run_generates_assets
test_orchestration_webhook_preview
```

O que os testes esperam:

```txt
pipeline_json existe
bash_runner existe
n8n_workflow existe
war_kit_folder é None no plan_only
warnings contém plan_only
dry_run gera war_kit_folder
dry_run gera site_preview
dry_run gera video_mp4
site_preview existe
video_mp4 existe
steps >= 6
webhook-preview responde received
```

Problema:

O serviço ativo `FreeStackOrchestrator.run()` não gera esses arquivos nem esses campos.

## Compilação

Arquivos auditados compilam:

```txt
orchestration_pipeline.py OK
routes/orchestration.py OK
schemas/orchestration.py OK
test_orchestration_pipeline.py OK
miner_engine.py OK
legacy.py OK
```

Conclusão:

```txt
Não é erro de sintaxe.
É erro arquitetural/funcional.
```

## Dependências reais disponíveis hoje

Já homologadas:

```txt
ContentOrchestratorBridge
VideoPipelineBridge
PremiumRenderBridge
SiteBuilderBridge
CampaignBrainAgent
CampaignMemoryStore
DecisionFeedStore
MasterContextStore
```

Essas são as peças corretas que a Missão 24B deve usar.

## Dependências legacy/problemáticas

Encontradas no fluxo atual:

```txt
engine_viralidade_remodel
deploy_conversion_site
find_high_scale_targets
legacy.NoOp
MasterOrchestrator antigo
```

Risco:

```txt
Ativar esse fluxo como está pode quebrar por método inexistente,
constructor incompatível ou chamar uma função antiga de deploy/render.
```

## Fluxo esperado para a Missão 24B

A correção controlada deve criar ou substituir com segurança:

```txt
OrchestrationPipelineSafe
        ↓
MasterContextStore.startup_checklist()
        ↓
ContentOrchestratorBridge.run_mock_cycle()
        ↓
VideoPipelineBridge.run_mock_cycle()
        ↓
PremiumRenderBridge.run_mock_cycle()
        ↓
SiteBuilderBridge.run_mock_cycle()
        ↓
DecisionFeedStore
        ↓
CampaignMemoryStore
        ↓
CampaignBrainAgent
        ↓
OrchestrationResponse
```

## Arquivos que a Missão 24B deve gerar

```txt
pipeline.json
run.sh
n8n_workflow.json
orchestration_manifest.json
```

Em modo `dry_run`, pode também apontar para:

```txt
site_preview
video manifest ou placeholder
premium render manifest
site deploy payload
```

Sem render real e sem deploy real.

## Pontos positivos

```txt
Existe schema maduro.
Existe rota de orchestration.
Existe teste de fluxo plan_only e dry_run.
Existem bridges Safe homologados.
Existe MasterContext.
Existe Memory/DecisionFeed/Brain.
```

## Pontos negativos / riscos

```txt
Serviço ativo não atende o schema.
Serviço ativo não atende os testes.
MasterOrchestrator usa chamadas antigas.
MinerEngine é instanciado sem repository.
find_high_scale_targets pode não existir.
SiteBuilder antigo ainda é chamado via deploy_conversion_site.
Premium antigo é chamado via engine_viralidade_remodel.
Rota exige autenticação.
Não existe camada orchestration-safe.
```

## Classificação

```txt
Status: BLUEPRINT ANTIGO
Maturidade: PARCIAL
Risco: ALTO
Valor estratégico: CRÍTICO
```

## Plano de reparo recomendado — Missão 24B

Criar:

```txt
src/app/services/orchestration_pipeline_safe.py
src/app/api/routes/orchestration_safe.py
```

Ou reparar `FreeStackOrchestrator` de forma controlada para usar os bridges Safe.

Critérios:

```txt
Não chamar Meta real.
Não chamar TikTok.
Não executar render real.
Não executar deploy real.
Não usar legacy.NoOp.
Não chamar engine_viralidade_remodel.
Não chamar deploy_conversion_site antigo.
Não usar find_high_scale_targets.
Usar apenas bridges Safe homologados.
```

Fluxo mínimo:

```txt
plan_only:
    gerar pipeline_json
    gerar bash_runner
    gerar n8n_workflow
    não executar bridges

dry_run:
    gerar pipeline_json
    gerar bash_runner
    gerar n8n_workflow
    executar bridges Safe
    coletar outputs
    registrar Memory/DecisionFeed/Brain
```

## Próxima missão recomendada

```txt
Missão 24B — Reparo Controlado do OrchestrationPipeline
```

Objetivo:

```txt
Criar OrchestrationPipeline Safe usando os bridges Safe homologados e retornando OrchestrationResponse válido.
```

## Conclusão

A Missão 24A confirmou que o OrchestrationPipeline é o ponto mais crítico restante.

Ele possui schema e testes ambiciosos, mas o serviço ativo ainda é antigo e desalinhado.

A Missão 24B deve reparar essa ponte central sem ativar nenhum recurso real de render, deploy, Meta ou TikTok.
