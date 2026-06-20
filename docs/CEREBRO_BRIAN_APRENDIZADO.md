# Brain e Aprendizado

## O Brain

O Brain é a camada estratégica e consultiva do projeto. Ele recebe informações de campanhas, métricas, histórico e contexto operacional para emitir recomendações seguras antes de qualquer avanço.

No projeto, o papel do Brain é representado principalmente por:

- `CampaignBrainAgent`
- `DecisionFeedStore`
- `CampaignMemoryStore`
- `MasterContextStore`

## Como o Brain aprende

1. Uma missão executa uma ação em modo Safe.
2. O resultado é enviado ao CampaignBrain.
3. O Brain revisa o contexto.
4. A decisão é registrada no DecisionFeed.
5. O aprendizado é gravado no CampaignMemory.
6. O MasterContext atualiza o estado do projeto.
7. A próxima missão usa esse histórico como memória.

## Como os agentes registram aprendizado

Os agentes registram aprendizado usando registros estruturados com:

- produto;
- nicho;
- etapa;
- resultado;
- lição;
- recomendação;
- métricas;
- origem;
- output gerado.

Esses registros alimentam CampaignMemory, DecisionFeed e MasterContext.

## Regra permanente para todas as missoes

A partir da Missao 27A, toda missao deve usar o Brain como copiloto obrigatorio.

Antes de executar:

1. Ler `logs/master_context.json`.
2. Ler as ultimas entradas de `logs/decision_feed.log`.
3. Ler as ultimas entradas de `logs/campaign_brain_memory.log`.
4. Confirmar a ultima missao homologada.
5. Confirmar a proxima missao recomendada.
6. Pedir uma avaliacao consultiva ao Brain quando a tarefa envolver risco, mudanca de comportamento, testes, integracao real ou producao.
7. Para seguranca e modo real assistido, consultar `/api/v1/security/status`, `/api/v1/security/real-mode-gate` e `/api/v1/security/brain-review`.

Durante a execucao:

1. Manter tudo em Safe / Dry Run ate homologacao explicita.
2. Usar o historico do Brain para evitar repetir erros.
3. Registrar decisoes relevantes no DecisionFeed.
4. Registrar aprendizados no CampaignMemory.
5. Preservar `correlation_id`, `execution_id` e `mission_id` em rotas e logs quando aplicavel.

Depois de executar:

1. Rodar validacoes automatizadas proporcionais ao risco.
2. Atualizar MasterContext com o resultado real.
3. Gravar resumo no DecisionFeed.
4. Gravar aprendizado no CampaignMemory.
5. Atualizar a documentacao de proximos passos.

Regra de seguranca:

```txt
Nenhuma missao deve avancar ignorando o Brain.
Se a memoria estiver divergente da realidade validada por testes, corrigir a memoria antes de continuar.
```
