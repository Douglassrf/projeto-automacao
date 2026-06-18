# Modo Economico Seguro

Objetivo: economizar tokens sem reduzir seguranca, qualidade ou continuidade.

## Regra Principal

```txt
Usar arquivos como memoria longa e o chat apenas para decisoes curtas, status e bloqueios.
```

## Fluxo Padrao

1. Ler somente os arquivos necessarios da missao atual.
2. Consultar `logs/master_context.json`, `logs/decision_feed.log` e `logs/campaign_brain_memory.log`.
3. Implementar com patches pequenos.
4. Nao repetir codigo existente no chat.
5. Rodar teste especifico primeiro.
6. Rodar suite completa apenas no fechamento da missao ou mudanca critica.
7. Gravar relatorios longos em `docs/` ou `logs/`, nao no chat.
8. Responder no chat apenas com resumo, testes, bloqueios e proximo passo.

## Padrao De Resposta No Chat

```txt
Feito:
- item essencial

Validado:
- teste e resultado

Proximo:
- acao recomendada
```

## Quando Pode Usar Mais Tokens

- Falha critica em teste.
- Risco de producao real.
- Alteracao em contrato de API.
- Mudanca em seguranca, credenciais, pagamento ou Meta real.
- Pedido explicito do usuario por explicacao detalhada.

## O Que Evitar

- Colar logs grandes no chat.
- Repetir arquivos inteiros.
- Relatar cada detalhe quando o resultado ja esta em arquivo.
- Rodar buscas amplas sem necessidade.
- Fazer resumo longo quando o usuario pediu continuidade pratica.

## Cerebro E Brian

O Cerebro e o Brian continuam obrigatorios, mas em modo economico:

- ler apenas as ultimas entradas relevantes;
- registrar aprendizado final em JSONL;
- nao repetir toda a memoria no chat;
- usar `MasterContext` como estado oficial.
