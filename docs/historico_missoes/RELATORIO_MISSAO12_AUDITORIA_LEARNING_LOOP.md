# Relatório — Missão 12 / Auditoria Profunda do LearningLoop Original

## Objetivo

Auditar profundamente o `LearningLoop` original sem alterar nenhum arquivo do projeto.

## Regra aplicada

```txt
Não implementar.
Não alterar.
Não apagar.
Não ativar publicação real.
Somente entender.
```

## Arquivos auditados

```txt
src/app/services/learning_loop.py
src/app/api/routes/learning_loop.py
src/app/schemas/learning_loop.py
src/app/tests/test_learning_loop.py
src/app/core/config.py
src/app/services/campaign_brain.py
src/app/services/campaign_intelligence.py
src/app/services/campaign_intelligence_safe.py
src/app/services/capi_enterprise.py
```

## Veredito técnico

O `LearningLoop` original é REAL.

Ele não é apenas placeholder.

Ele já possui lógica para:

```txt
1. Receber eventos CAPI.
2. Gravar eventos em JSONL local.
3. Agrupar eventos por creative_id.
4. Calcular compras, receita, ROAS médio, CPA médio e Connect Rate médio.
5. Identificar criativos vencedores.
6. Gerar variações V4, V5 e V6.
7. Gerar arquivo JSON e README dentro do kit de campanha.
```

## Classe principal

```txt
CapiLearningLoopService
```

Métodos encontrados:

```txt
__init__
ingest_capi_events
run_learning_loop
_generate_variations
_winner_recommendation
_write_learning_output
_read_events
_append_jsonl
_can_forward_to_meta
```

## Fluxo interno real

```txt
CapiIngestRequest
        ↓
ingest_capi_events()
        ↓
logs/capi_events.log
        ↓
run_learning_loop()
        ↓
agrupamento por creative_id
        ↓
WinnerInsight
        ↓
GeneratedVariation V4/V5/V6
        ↓
logs/learning_loop.log
        ↓
/data/campaign_kits/Learning_Loop/<produto>/
```

## Onde ele salva conhecimento

### Eventos CAPI

```txt
logs/capi_events.log
```

### Resultado do loop

```txt
logs/learning_loop.log
```

### Artefatos gerados

```txt
/data/campaign_kits/Learning_Loop/<produto>/
```

Arquivos gerados:

```txt
learning_loop_v4_v5_v6.json
README_LEARNING_LOOP.md
```

## Como ele define vencedor

Ele lê eventos do produto e agrupa por:

```txt
creative_id
```

Depois calcula:

```txt
purchase_count
revenue
avg_roas
avg_cpa
avg_connect_rate
```

Só entra como vencedor se passar nos filtros:

```txt
purchases >= min_purchases
avg_roas >= min_roas
```

Depois ordena por:

```txt
ROAS
compras
Connect Rate
```

## Como gera V4, V5 e V6

O método `_generate_variations()` cria variações usando:

```txt
version
based_on_creative_id
campaign_name
hook
copy_text
image_prompt
video_script
reason
```

As versões padrão vêm do schema:

```txt
["V4", "V5", "V6"]
```

## Rotas existentes

Arquivo:

```txt
src/app/api/routes/learning_loop.py
```

Rotas:

```txt
POST /api/v1/learning-loop/capi/ingest
POST /api/v1/learning-loop/generate-variations
```

## Testes existentes

Arquivo:

```txt
src/app/tests/test_learning_loop.py
```

Existe teste confirmando que:

```txt
1. Um evento CAPI é ingerido.
2. O loop é executado.
3. São geradas variações V4, V5 e V6.
```

Isso é uma evidência forte de que o módulo foi pensado para funcionar.

## Configurações encontradas

Arquivo:

```txt
src/app/core/config.py
```

Configurações relevantes:

```txt
capi_enabled = False
learning_loop_enabled = True
test_budget_brl = 25.0
scale_budget_brl = 50.0
scale_min_roas = 1.0
kit_output_dir = /data/campaign_kits
```

Interpretação:

```txt
CAPI real começa desativado.
LearningLoop está habilitado.
Orçamento de teste R$25 está preservado.
Escala inicial R$50 está preservada.
```

## Integração atual com o Brain

O `CampaignBrainAgent` já lê a existência de:

```txt
logs/capi_events.log
logs/learning_loop.log
```

Mas a auditoria não encontrou chamada direta do Brain para:

```txt
CapiLearningLoopService.run_learning_loop()
```

Conclusão:

```txt
O Brain sabe que a memória de aprendizado existe,
mas ainda não aciona nem interpreta profundamente o LearningLoop.
```

## Integração atual com CampaignIntelligence

O `CampaignIntelligence` original possui campos relacionados a CAPI e métricas.

Mas a auditoria não confirmou uma ponte direta automática:

```txt
CampaignIntelligence → LearningLoop
```

Conclusão:

```txt
Existe compatibilidade conceitual,
mas a ponte ainda precisa ser desenhada com cuidado.
```

## Integração com CAPI Enterprise

Existe também:

```txt
src/app/services/capi_enterprise.py
```

Esse módulo é mais avançado para:

```txt
normalização
hashing
event_id
deduplicação Pixel+CAPI
envio dry-run/real controlado
```

Conclusão:

```txt
LearningLoop é o cérebro de aprendizado por conversão.
CapiEnterprise é a camada mais robusta de ingestão/event_id/deduplicação.
```

Esses dois módulos devem ser integrados futuramente, mas não de uma vez.

## Pontos positivos

```txt
LearningLoop é real.
Já grava eventos localmente.
Já identifica vencedores.
Já gera V4/V5/V6.
Já gera JSON e README de saída.
Já possui testes automatizados.
CAPI real fica bloqueado por configuração.
O orçamento R$25 está preservado no config.
```

## Pontos negativos

```txt
Rotas exigem autenticação.
Brain ainda não aciona LearningLoop diretamente.
DecisionFeed ainda não registra as variações geradas.
CampaignIntelligenceSafe ainda não lê learning_loop.log.
LearningLoop não chama VideoPipeline nem PremiumRender.
LearningLoop não valida risco Meta das novas variações.
LearningLoop não passa as novas variações pelo Brain antes do dry-run.
```

## Classificação

```txt
Status: REAL
Maturidade: PARCIALMENTE PRONTO
Risco: MÉDIO se ativar direto
Valor estratégico: MUITO ALTO
```

## Resposta da pergunta principal

O LearningLoop já é um cérebro evolutivo?

Resposta:

```txt
Ele é um motor evolutivo parcial.
```

Ele já aprende com conversões e gera variações V4/V5/V6.

Mas ainda não é um cérebro completo porque falta conectar:

```txt
LearningLoop
    ↓
CampaignBrainAgent
    ↓
DecisionFeed
    ↓
CampaignIntelligenceSafe
    ↓
VideoPipeline / PremiumRender
    ↓
MetaCampaignOperator Dry Run
```

## Próxima missão recomendada

A próxima missão deve ser:

```txt
MISSÃO 13 — Ativação Controlada do LearningLoop em modo local seguro
```

Objetivo:

```txt
Criar rotas seguras ou testes locais sem autenticação pesada para:
1. ingerir evento CAPI mockado;
2. rodar LearningLoop;
3. gerar V4/V5/V6;
4. registrar decisão no DecisionFeed;
5. não publicar nada;
6. não chamar Meta real.
```

## Ordem segura recomendada

```txt
1. Criar LearningLoopSafe route ou mock endpoint.
2. Ingerir evento mockado.
3. Rodar generate-variations.
4. Confirmar V4/V5/V6.
5. Registrar resumo no DecisionFeed.
6. Expor o resultado para o Brain.
7. Só depois pensar em VideoPipeline/PremiumRender.
```

## Conclusão

A auditoria confirmou que o LearningLoop original é uma das peças mais valiosas do projeto.

Ele já contém o começo do mecanismo de evolução automática:

```txt
conversão → vencedor → V4/V5/V6
```

O próximo passo não é recriar esse módulo.

O próximo passo é ativá-lo com segurança e conectá-lo gradualmente ao Brain.
