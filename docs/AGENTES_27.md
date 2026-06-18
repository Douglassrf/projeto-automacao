# Lista dos 27 Agentes e Função de Cada Um

1. **MasterContextAgent** — Mantém estado mestre do projeto, última missão, próxima missão e checklist operacional.
2. **CampaignMemoryAgent** — Registra aprendizados, histórico de campanhas, resultados e lições.
3. **DecisionFeedAgent** — Centraliza decisões, pareceres, próximos passos e recomendações do Brain.
4. **CampaignBrainAgent** — Revisa campanhas, riscos, métricas, copy, orçamento e recomendações antes de avanço.
5. **AdProcessorAgent** — Calcula métricas de anúncios: connect rate, checkout rate, purchase rate e score.
6. **MinerEngineAgent** — Motor de mineração/análise; atualmente precisa evoluir para real controlado.
7. **FacebookAdMinerAgent** — Coleta/minera anúncios candidatos; atualmente controlado/dry-run ou pendente de real.
8. **MetaUpdateWatcherAgent** — Monitora atualizações e mudanças de ambiente Meta em modo seguro.
9. **MetaCampaignOperatorAgent** — Opera campanhas Meta em dry-run; produção real ainda bloqueada.
10. **CampaignIntelligenceAgent** — Consolida inteligência de campanha e visão panorâmica de decisão.
11. **LearningLoopAgent** — Registra e processa aprendizado para evolução controlada.
12. **LearningLoopBridgeAgent** — Conecta LearningLoop ao Brain, DecisionFeed e CampaignMemory.
13. **ContentOrchestratorAgent** — Organiza conteúdo, briefs e roteamento criativo.
14. **ContentOrchestratorBridgeAgent** — Camada Safe do ContentOrchestrator com Memory/DecisionFeed/Brain.
15. **VideoPipelineAgent** — Pipeline de vídeo; produção real bloqueada até fase específica.
16. **VideoPipelineBridgeAgent** — Camada Safe do vídeo, gera script/storyboard/manifest sem render real.
17. **PremiumRenderAgent** — Render premium de imagem/vídeo; produção real bloqueada.
18. **PremiumRenderBridgeAgent** — Camada Safe do PremiumRender, gera payload/manifest sem providers externos.
19. **SiteBuilderAgent** — Geração de páginas/sites; implementação real ainda controlada via Safe.
20. **SiteBuilderBridgeAgent** — Camada Safe do SiteBuilder, gera index/css/deploy_payload sem deploy real.
21. **OrchestrationPipelineAgent** — Orquestra o fluxo da fábrica.
22. **OrchestrationPipelineSafeAgent** — Orquestra bridges Safe e gera OrchestrationResponse válido.
23. **ObservabilityAgent** — Responsável por logs, telemetria, tracing e health dashboard na Missão 27.
24. **AuditLoggerAgent** — Responsável por trilha de auditoria, execution_id/correlation_id/mission_id.
25. **LoadTestAgent** — Responsável por teste de carga controlado na Missão 27A.
26. **QueueHealthAgent** — Responsável por detectar filas travadas, locks e concorrência.
27. **RecoveryAgent** — Responsável por cenários de recuperação após falha e rollback seguro.
