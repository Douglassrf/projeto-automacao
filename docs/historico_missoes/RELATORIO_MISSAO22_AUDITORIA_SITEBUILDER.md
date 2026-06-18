# Relatório — Missão 22 / Auditoria Profunda do SiteBuilder

## Regra da Bússola

Missão executada em modo:

```txt
AUDITORIA SEM ALTERAÇÃO
```

Foi proibido:

```txt
alterar código
corrigir código
executar deploy
publicar site
acionar Vercel
acionar Netlify
acionar GitHub
alterar rotas
alterar schemas
```

Nenhum arquivo do projeto foi modificado.

## Base auditada

Arquivo base:

```txt
projeto_automacao_missao21_premiumrender_safe.zip
```

## Memória de partida

Estado anterior registrado:

```txt
Missão 21 — PremiumRender Safe concluída.
Próxima missão — 22, Auditoria Profunda do SiteBuilder.
```

## Arquivos auditados

```txt
src/app/services/site_builder.py
src/app/api/routes/site_builder.py
src/app/schemas/site_builder.py
src/app/core/compat/legacy.py
src/app/services/orchestration_pipeline.py
src/app/core/config.py
src/app/tests/test_site_builder.py
src/app/api/safe_router.py
```

## Veredito técnico

O `SiteBuilder` está:

```txt
PARCIAL
LEGACY
INCOMPLETO NA CAMADA ATIVA
RISCO ALTO PARA ATIVAR DIRETO
```

Ele não está completamente vazio, mas a camada ativa atual não corresponde ao schema e aos testes existentes.

## Arquivo principal

```txt
src/app/services/site_builder.py
```

Funções encontradas:

```txt
load_template
inject_dynamic_content
save_to_deploy_folder
trigger_deploy
deploy_conversion_site
```

Classes encontradas:

```txt
StaticSiteBuilder
SiteBuilder
```

## Problema central encontrado

O arquivo contém múltiplas definições de `StaticSiteBuilder` e importa:

```txt
from app.core.compat.legacy import StaticSiteBuilder
```

O `legacy.py` define:

```txt
StaticSiteBuilder = NoOp
```

Depois o próprio arquivo redefine:

```txt
class SiteBuilder:
    def build(self, *args, **kwargs):
        return {"status": "ok", "module": "site_builder"}

StaticSiteBuilder = SiteBuilder
```

Interpretação:

```txt
Há mistura de código real simples, compatibilidade antiga e NoOp/legacy.
```

## Rota ativa

Arquivo:

```txt
src/app/api/routes/site_builder.py
```

Rota encontrada:

```txt
GET /api/v1/site-builder/health
```

Resposta:

```txt
{"ok": true, "module": "site_builder"}
```

## Rota esperada pelos testes

Arquivo:

```txt
src/app/tests/test_site_builder.py
```

O teste espera:

```txt
POST /api/v1/site-builder/generate
```

Mas essa rota não existe no arquivo ativo auditado.

Conclusão:

```txt
Há desalinhamento entre testes/schemas e rota ativa.
```

## Schemas encontrados

Arquivo:

```txt
src/app/schemas/site_builder.py
```

Classes:

```txt
SiteOfferInput
SiteDeployOptions
SiteGenerateRequest
SiteGenerateResponse
```

Esses schemas são mais maduros do que a implementação ativa.

Eles indicam uma visão planejada para:

```txt
oferta
template
deploy local
github_vercel
vercel
netlify
preview_path
arquivos gerados
deploy_payload
```

Mas a rota ativa ainda não usa esses schemas.

## Testes encontrados

Arquivo:

```txt
src/app/tests/test_site_builder.py
```

Testes:

```txt
test_site_builder_generates_static_files
test_site_builder_dry_run_deploy_payload
```

O que os testes esperam:

```txt
geração de index.html
geração de styles.css
preview_path existente
deploy_status = local_ready
deploy_payload_path para github_vercel dry_run
```

Problema:

A implementação ativa não fornece essa rota nem esse fluxo.

## legacy.py

Arquivo:

```txt
src/app/core/compat/legacy.py
```

Contém classe:

```txt
NoOp
```

E aliases:

```txt
FreeStackOrchestrator = NoOp
MinerEngine = NoOp
StaticSiteBuilder = NoOp
FacebookAdMiner = NoOp
CampaignOperator = NoOp
MetaCampaignOperator = NoOp
VideoPipeline = NoOp
PremiumRender = NoOp
```

Risco:

Qualquer import errado pode trazer uma classe falsa em vez do serviço real.

## Integração com OrchestrationPipeline

Arquivo:

```txt
src/app/services/orchestration_pipeline.py
```

Importa:

```txt
from .site_builder import deploy_conversion_site
```

Fluxo pretendido:

```txt
MinerEngine
        ↓
engine_viralidade_remodel
        ↓
deploy_conversion_site
```

Problemas já vistos:

```txt
MinerEngine chamado sem repository.
find_high_scale_targets pode não existir.
engine_viralidade_remodel vem de PremiumRender/task.
deploy_conversion_site grava deploy/index.html e chama trigger_deploy print.
```

Conclusão:

O OrchestrationPipeline depende de SiteBuilder, mas a integração atual é frágil.

## Configurações de deploy

Arquivo:

```txt
src/app/core/config.py
```

Configurações encontradas:

```txt
site_output_dir = /data/generated_sites
github_token = 
github_owner = None
vercel_token = 
vercel_team_id = None
netlify_token = 
```

Riscos:

```txt
/data/generated_sites pode falhar por permissão.
Tokens de deploy não configurados.
Deploy real não deve ser acionado.
```

## Dependências encontradas

```txt
os
arquivos locais
deploy/index.html
schemas Pydantic
config site_output_dir
github/vercel/netlify planejados
legacy.NoOp
```

## Fluxo funcional atual

O fluxo mínimo que existe no serviço é:

```txt
load_template
        ↓
inject_dynamic_content
        ↓
save_to_deploy_folder
        ↓
trigger_deploy
```

Mas ele é simplificado demais e grava em:

```txt
deploy/index.html
```

fora da estrutura controlada por `site_output_dir`.

## Fluxo quebrado atual

O fluxo esperado por testes/schemas seria:

```txt
POST /site-builder/generate
        ↓
SiteGenerateRequest
        ↓
gerar index.html/styles.css
        ↓
preview_path
        ↓
dry_run deploy payload
        ↓
SiteGenerateResponse
```

Esse fluxo não está implementado na rota ativa.

## Pontos positivos

```txt
Existe arquivo site_builder.py.
Existe rota health.
Existe schema maduro.
Existem testes planejando geração real.
Existe configuração de deploy.
Existe função deploy_conversion_site usada pelo OrchestrationPipeline.
```

## Pontos negativos / riscos

```txt
Rota generate ausente.
SiteBuilder.build é apenas stub simples.
StaticSiteBuilder aparece múltiplas vezes.
legacy.py contém NoOp.
Schemas não estão conectados à rota.
Testes não batem com a rota ativa.
Deploy é apenas print.
save_to_deploy_folder grava em deploy/index.html.
Não usa site_output_dir.
Não há proteção clara contra deploy real.
Não há integração segura com Brain/Memory/DecisionFeed.
```

## Classificação

```txt
Status: PARCIAL
Maturidade: LEGACY/STUB
Risco: ALTO
Valor estratégico: ALTO
```

## Parecer do arquiteto

O `SiteBuilder` não deve ser ativado como está.

Ele precisa de reparo controlado antes de entrar na fábrica completa.

O reparo deve usar os schemas existentes como contrato oficial:

```txt
SiteGenerateRequest
SiteGenerateResponse
```

E deve criar uma camada segura:

```txt
SiteBuilderSafe
```

com:

```txt
output local dentro do projeto
dry_run obrigatório
sem deploy real
index.html
styles.css
deploy_payload.json quando provider != local
DecisionFeed
CampaignMemory
Brain
```

## Impacto na Missão 23

A Missão 23 originalmente era:

```txt
Reparo Controlado do OrchestrationPipeline
```

Mas a auditoria mostra que antes de reparar o OrchestrationPipeline completo, é necessário reparar o SiteBuilder de forma controlada.

Recomendação ajustada:

```txt
Missão 23 — SiteBuilder Safe / Reparo Controlado do SiteBuilder
Missão 24 — Reparo Controlado do OrchestrationPipeline
Missão 25 — Fábrica Completa em Dry Run
Missão 26 — Homologação Geral / Pacote Final
```

## Próxima missão recomendada

```txt
Missão 23 — SiteBuilder Safe / Reparo Controlado do SiteBuilder
```

Objetivo:

```txt
Criar rota segura /site-builder-safe/generate
ou corrigir rota controlada usando schemas existentes,
sem deploy real,
com output local,
com dry_run obrigatório,
com registro em Memory/DecisionFeed/Brain.
```

## Conclusão

A Missão 22 confirmou que o SiteBuilder é a peça mais frágil da fábrica até agora.

Ele possui intenção arquitetural, schemas e testes, mas a implementação ativa é legacy/stub e incompleta.

Nenhum arquivo do projeto foi alterado nesta missão.
