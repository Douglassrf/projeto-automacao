# Relatorio - Acao Real Meta Pausada

Data: 2026-06-04

## Objetivo

Executar uma acao real controlada na conta Meta `113923608813145`, mantendo todas as protecoes de seguranca:

- nao ativar gasto;
- nao publicar campanha ativa;
- nao apagar campanhas no mesmo dia;
- manter a campanha do Codex pausada;
- registrar o aprendizado para Cerebro e Brian.

## Estado Confirmado

- Conta Meta: `113923608813145`
- Campanha Codex criada: `52616252576068`
- Status da campanha Codex: `PAUSED`
- Effective status da campanha Codex: `PAUSED`
- Total de campanhas listadas: `7`
- Campanhas antigas ainda ativas apos pausa: `0`
- Campanhas pausadas: `7`
- Validacao local anterior: `99 passed`
- Validacao local apos hardening do operador: `101 passed`

## Campanhas Antigas Pausadas

As campanhas antigas ativas foram pausadas conforme autorizacao do usuario. Nada foi deletado hoje.

- `6214056238664` - Publicacao: "Pessoal estamos com esse projeto ajudando..."
- `6201905312064` - Publicacao: "Pode ser melhor! Vem comigo na proxima !"
- `6117819541864` - Publicacao: "Douglas Oliveroficial compartilhou o video de..."
- `6114053951064` - Publicacao: "Natal solidario !"
- `6110886523664` - Publicacao: "Happy Hour nesse sabado dia 04 De novembro aqui..."

## Campanha Codex

A campanha real do Codex foi criada em modo pausado:

- ID: `52616252576068`
- Nome: `Teste Seguro Codex PAUSADO V3 AD01`
- Status: `PAUSED`

Observacao: a campanha ainda nao foi completada com conjunto/anuncio final porque a Meta recusou o orcamento de R$ 5,00 por dia. A plataforma exigiu valor superior a R$ 5,10.

## Hardening Aplicado Apos A Primeira Acao Real

O operador foi reforcado para evitar duplicidade e melhorar a retomada segura:

- `MetaOperatorLaunchRequest` agora aceita `existing_campaign_id`.
- `CampaignPlanItem` carrega `existing_campaign_id` ate o cliente Meta.
- O cliente Meta possui caminho especifico para criar conjunto/anuncio dentro de uma campanha existente.
- O operador bloqueia reuso de campanha existente com mais de 1 criativo.
- O operador bloqueia tentativa real com orcamento menor que R$ 6 por dia, porque R$ 5 foi recusado pela Meta.
- O loop de decisao agora confirma no banco a criacao/reuso de acoes pendentes, mantendo a fila de aprovacao visivel.

## Regra De Seguranca

Nenhuma acao de gasto deve ser feita sem nova autorizacao explicita do usuario.

Para continuar a campanha Codex pausada, sera necessaria autorizacao especifica para um orcamento minimo aceito pela Meta, por exemplo:

`Autorizo continuar a campanha PAUSADA com orcamento de R$ 6 por dia, sem ativar gasto.`

## Delecao

O usuario autorizou pausar hoje e deletar amanha. Como delecao e acao destrutiva, a execucao deve ocorrer apenas em 2026-06-05 ou depois, com nova confirmacao objetiva antes do envio para a API.

Atualizacao em 2026-06-05:

- Confirmacao recebida para seguir o cronograma e excluir campanhas antigas.
- A campanha Codex foi preservada.
- As campanhas antigas permanecem `PAUSED`.
- A Meta bloqueou a exclusao/alteracao real com erro `OAuthException`, codigo `31`, subcodigo `3858385`.
- Mensagem da Meta: a conta precisa ser autenticada no Gerenciador de Anuncios antes de criar ou modificar anuncios.

Acao segura adotada: parar novas tentativas de escrita na Meta ate o usuario concluir a autenticacao exigida pela propria plataforma.

Nova tentativa apos verificacao informada pelo usuario:

- Data: 2026-06-05.
- Campanhas antigas tentadas: `6`.
- Campanhas deletadas via API: `0`.
- Campanhas antigas restantes: `6`.
- Motivo: a Meta ainda retornou `OAuthException 31 / 3858385` em todas as tentativas.
- Estado final seguro: todas as antigas seguem `PAUSED`; Codex segue `PAUSED`.

Conclusao: a exclusao real continua bloqueada pela Meta, nao pelo projeto. O projeto deve continuar apenas com validacoes seguras/dry-run ate a pendencia da Meta desaparecer.

Validacao segura realizada enquanto a escrita real segue bloqueada:

- Fluxo Codex ponta a ponta em `dry_run`: aprovado.
- `existing_campaign_id`: `52616252576068`.
- Tentativas simuladas: `1`.
- Publicacoes reais: `0`.
- Bloqueios no operador: `0`.
- Status simulado: `simulated`.
- Guardrails relevantes: `existing_campaign_scope=ok`, `meta_min_budget=ok`, `spend_guard=ok`.
- Gasto da conta em 2026-06-05: `0`.

## Aprendizado Para Cerebro E Brian

- Pausar antes de deletar reduz risco operacional.
- Campanhas reais devem nascer pausadas enquanto a arquitetura ainda esta em validacao.
- Orcamentos reais precisam respeitar o minimo aceito pela Meta.
- A conta deve permanecer com `0` campanhas antigas ativas antes de qualquer proxima etapa.
- Token e credenciais nao devem aparecer em logs, respostas, ZIPs ou documentacao.
- Em Windows, os testes devem usar `python -m pytest --basetemp .pytest_tmp -p no:cacheprovider` quando a pasta temporaria padrao estiver bloqueada.
- Para terminar a campanha Codex sem duplicar campanha, usar `existing_campaign_id=52616252576068`.
- Se a Meta retornar `OAuthException 31 / 3858385`, nao insistir em chamadas de escrita. O usuario precisa autenticar a conta no Gerenciador de Anuncios e somente depois retomar.
