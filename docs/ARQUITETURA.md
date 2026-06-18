# Arquitetura do Projeto Automação

## Estado atual

Status consolidado: **SAFE DRY RUN READY**.

O projeto está estruturado como uma fábrica segura para mineração, inteligência, geração de conteúdo, vídeo, render, site e orquestração, ainda sem produção real.

## Fluxo macro

```txt
MasterContext
        ↓
OrchestrationPipeline Safe
        ↓
ContentOrchestrator Safe
        ↓
VideoPipeline Safe
        ↓
PremiumRender Safe
        ↓
SiteBuilder Safe
        ↓
DecisionFeed
        ↓
CampaignMemory
        ↓
CampaignBrain
```

## Componentes principais

- `MasterContext`: memória mestre e controle de missão.
- `CampaignMemory`: aprendizado histórico.
- `DecisionFeed`: trilha de decisões.
- `CampaignBrain`: análise estratégica.
- `ContentOrchestratorBridge`: camada segura de conteúdo.
- `VideoPipelineBridge`: camada segura de vídeo.
- `PremiumRenderBridge`: camada segura de render premium.
- `SiteBuilderBridge`: camada segura de páginas.
- `OrchestrationPipelineSafe`: orquestra a fábrica inteira em dry-run.

## Bloqueios de segurança

- Meta real: OFF.
- TikTok real: OFF.
- Deploy real: OFF.
- Render real: OFF.
- GitHub/Vercel/Netlify reais: OFF.
- Chaves reais: não incluídas.

## Próxima fase

Missão 27: Observabilidade, auditoria e operação controlada.
