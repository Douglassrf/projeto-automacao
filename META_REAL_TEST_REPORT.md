# META_REAL_TEST_REPORT.md — Missão R11 (Teste Meta real controlado)

Data: 2026-06-19. **Nenhuma chamada de rede real foi feita à Meta nesta missão.** Todas as 11 verificações abaixo rodaram contra uma camada 100% isolada e sintética (sem ler o `.env` real, sem usar credenciais reais), com um "tripwire" de rede que aborta a execução com erro caso qualquer código tente de fato sair para `httpx.get/post/delete`. Isso é deliberado: o usuário confirmou que as credenciais Meta no `.env` real são de produção, ligadas a dinheiro de verdade, então R11 não tentou validar a publicação real em si — validou se a lógica de bloqueio (guardrails) do operador é confiável o suficiente para, no futuro, autorizar um teste real com orçamento mínimo.

## 1. Achado central da missão (leia isto primeiro)

Ao montar o ambiente isolado para testar o cenário "tudo desbloqueado de propósito", a primeira execução de U1 (`mode="dry_run"` explícito) **disparou o tripwire de rede inesperadamente** — ou seja, o código tentou de fato enviar um POST para `https://graph.facebook.com/v20.0/act_.../campaigns`, mesmo com o chamador pedindo explicitamente modo dry-run.

Investigação (leitura de código, não suposição):

- `launch_v3()` calcula `effective_dry_run = payload.mode == "dry_run" OR self.meta_client.dry_run OR NOT settings.meta_autopublish` — três condições independentes ligadas por OU.
- Quando `effective_dry_run` era `True`, o código antigo chamava `self._publish_plan(plan)`, que delega para `MetaMarketingClient.publish_campaign_plan()`.
- **Esse método do client decide sozinho, de forma independente, se chama a rede real** — usando apenas `self.meta_client.dry_run` (que depende só de `META_DRY_RUN` e de credenciais completas). Ele não sabe nada sobre `payload.mode` nem sobre `settings.meta_autopublish`.
- Resultado: das três condições do OU em `launch_v3()`, **duas (`mode=="dry_run"` e `not autopublish`) não ofereciam proteção real nenhuma contra uma chamada de rede** — apenas rotulavam o resultado como `"simulated"` depois do fato. Só a terceira condição (`meta_client.dry_run`, isto é, `META_DRY_RUN`) de fato impedia a chamada.
- **Verificação no `.env` real (sem expor segredo, só os booleanos):** `META_ENV=sandbox`, `META_DRY_RUN=true`, `META_AUTOPUBLISH=false`, `META_ALLOW_ACTIVE_LAUNCH=false`, `META_ALLOW_PRODUCTION_REAL=false`. Como `META_DRY_RUN=true` hoje, essa falha **não é explorável no ambiente real atual** — mas é uma falha de defesa em profundidade real: se algum dia `META_DRY_RUN` fosse alterado para `false` (mesmo mantendo `META_AUTOPUBLISH=false`), um pedido explicitamente marcado `mode="dry_run"` ainda dispararia uma chamada real à Meta.

### Correção aplicada (código de produção, não só o teste)

Arquivo: `src/app/services/meta_campaign_operator.py`.

- Adicionado o método `_simulate_plan()`, que monta o mesmo formato de resultado simulado que o client já usa internamente (`dry_campaign_...`, mensagens de dry-run), **sem nunca chamar `self.meta_client`** — ou seja, sem nenhum código capaz de rede no caminho.
- O ramo `if effective_dry_run:` dentro de `launch_v3()` agora chama `self._simulate_plan(plan)` em vez de `self._publish_plan(plan)`.
- Efeito: agora, quando `effective_dry_run` é `True` por **qualquer um** dos três motivos do OU, nenhum código de rede é executado — não depende mais só do estado interno do client.

## 2. Metodologia de isolamento (por que é seguro testar isto sem risco)

Três camadas independentes, todas confirmadas em execução real:

1. **`Settings` 100% sintético**, construído com `_env_file=None` — o pydantic-settings nunca lê nenhum `.env`, real ou de teste, nesta instância.
2. **Credenciais falsas**, claramente marcadas (`FAKE_TOKEN_ISOLATED_TEST_R11_NAO_E_REAL`, IDs `000000000000001/2/3`), sem nenhuma relação com a conta real.
3. **Tripwire de rede**: `httpx.get`/`httpx.post`/`httpx.delete` substituídos por uma função que lança `NetworkTripwireError` imediatamente se qualquer código tentar de fato sair para a rede. Em todos os cenários onde a expectativa é "deve ficar bloqueado", o tripwire **não pode disparar** sem o teste falhar; nos cenários onde a expectativa é "humano libera tudo de propósito, então a tentativa de rede é o comportamento correto", o tripwire **precisa disparar** para o teste passar.

`MetaCampaignOperator` e `MetaMarketingClient` foram construídos via `object.__new__(...)`, com atributos (`settings`, `meta_client`, `credentials`, `affiliate_provider`) montados manualmente — nunca passando pelo `__init__` real, que chamaria `get_settings()` global e leria o `.env` real.

## 3. Resultado real da bateria de testes (após a correção)

Execução real (`python3 test_meta_guardrails_isolated_R11.py`), log completo:

```
[OK] U1_mode_dry_run_forca_simulacao: dry_run=True, published=0, tripwire nao disparou (esperado)
[OK] U2a_guardrails_todos_ok_quando_tudo_liberado: guardrails bloqueados (esperado vazio): []
[OK] U2b_tentativa_real_deveria_disparar_tripwire: Confirmado: com TODAS as flags deliberadamente
     desbloqueadas + payload válido, o código tenta uma chamada real ao Meta (interceptada pelo
     tripwire antes de qualquer rede) -- comportamento correto e esperado, não é bug.
[OK] U3_sem_autopublish_bloqueia: dry_run=True, guardrails bloqueados=['autopublish'], published=0
[OK] U4_sem_active_launch_bloqueia: guardrails bloqueados=['active_launch', 'payload_integrity'], published=0
[OK] U5_sem_confirmacao_manual_bloqueia: guardrails bloqueados=['manual_confirmation'], published=0
[OK] U6_hash_payload_incorreto_bloqueia: guardrails bloqueados=['payload_integrity'], published=0
[OK] U7_limite_de_gasto_atingido_bloqueia: guardrails bloqueados=['spend_guard'], published=0
[OK] U8_falha_ao_consultar_gasto_bloqueia: guardrails bloqueados=['spend_guard'], account_spend_today_brl=None, published=0
[OK] U9a_rollback_com_recursos_reais_deveria_tentar_rede: Confirmado: rollback só tenta rede real
     quando há recursos cadastrados E confirmed_by_user=True E force_dry_run=False (interceptado pelo tripwire).
[OK] U9b_rollback_sem_confirmacao_bloqueia_sem_tentar_rede: resp=dry_run=False action='delete'
     attempted=1 executed=0 blocked=True message='Rollback real exige confirmação manual.' results=[]

=== RESUMO ===
11/11 cenarios passaram conforme esperado.
```

| # | Cenário | Esperado | Resultado | Status |
|---|---|---|---|---|
| U1 | `mode="dry_run"` explícito, mesmo com **todas** as flags de ambiente desbloqueadas | `effective_dry_run` deve ser `True` só pelo `mode`, sem tentar rede | `dry_run=True`, `published=0`, tripwire **não** disparou — confirma a correção | ✅ |
| U2a | Tudo desbloqueado de propósito (ambiente liberado, payload válido, hash correto, gasto simulado abaixo do limite) | Todos os 11 guardrails devem ficar `ok` | `blocked=[]` | ✅ |
| U2b | Mesmo cenário do U2a, `mode="publish_active"` | O código **deve** tentar uma chamada real (é o único jeito de publicar de verdade) | Tripwire disparou — comportamento correto, prova que só humano liberando tudo chega perto da rede | ✅ |
| U3 | Tudo liberado, exceto `META_AUTOPUBLISH=false` | Bloquear por `autopublish`, sem tentar rede | Bloqueado corretamente | ✅ |
| U4 | Tudo liberado, exceto `META_ALLOW_ACTIVE_LAUNCH=false`, `mode="publish_active"` | Bloquear por `active_launch` | Bloqueado corretamente | ✅ |
| U5 | Tudo liberado, `confirmed_by_user=False` | Bloquear por `manual_confirmation` | Bloqueado corretamente | ✅ |
| U6 | Tudo liberado, hash do payload errado | Bloquear por `payload_integrity` | Bloqueado corretamente | ✅ |
| U7 | Tudo liberado, gasto diário simulado já no limite | Bloquear por `spend_guard` | Bloqueado corretamente | ✅ |
| U8 | Tudo liberado, consulta de gasto falha (erro simulado) | Bloquear por `spend_guard` (gasto desconhecido = inseguro) | Bloqueado corretamente | ✅ |
| U9a | Rollback com recursos fake cadastrados + confirmação + `force_dry_run=False` | Deve tentar rede real (única forma de rollback de verdade) | Tripwire disparou — correto | ✅ |
| U9b | Mesmo rollback, sem confirmação do usuário | Bloquear **antes** de qualquer tentativa de rede | `blocked=True`, sem tripwire | ✅ |

**11 de 11 cenários passaram conforme o resultado esperado**, incluindo o cenário U1 que motivou a correção — antes da correção, U1 falhava (tripwire disparava onde não devia); depois da correção, passa.

## 4. Verificação de segurança das credenciais reais

Nenhum valor de credencial foi lido, impresso ou logado nesta missão. A única consulta ao `.env` real foi um `grep` restrito às linhas de flag booleana (`META_ENV`, `META_DRY_RUN`, `META_AUTOPUBLISH`, `META_ALLOW_ACTIVE_LAUNCH`, `META_ALLOW_PRODUCTION_REAL`), confirmando que o ambiente real permanece travado em dry-run (`META_DRY_RUN=true`, `META_AUTOPUBLISH=false`, `META_ALLOW_ACTIVE_LAUNCH=false`). **O `.env` real não foi alterado em nenhum momento desta missão.**

## 5. Veredito sobre o pedido original da missão R11

A ordem master pedia: *"Validar com conta real: token; ad account; permissões; pixel; página; criação mínima controlada"*, com regra explícita: *"Se não houver autorização: Status = BLOQUEADO POR CREDENCIAL/CONTA REAL."*

Distinção importante:

- **Confirmado**: as credenciais no `.env` são reais, de produção, ligadas a dinheiro de verdade (confirmação do usuário, R10).
- **Não confirmado**: o usuário **não autorizou explicitamente** um teste real com gasto/criação mínima controlada contra a conta principal.

Por isso, esta missão entrega o que era seguro e útil entregar sem essa autorização — uma validação rigorosa e adversarial da lógica de guardrails que protegeria um teste real, incluindo a descoberta e correção de uma falha real de defesa em profundidade — mas não executa a criação mínima controlada contra a conta real.

**STATUS FINAL DA MISSÃO R11: BLOQUEADO POR FALTA DE AUTORIZAÇÃO EXPLÍCITA PARA TESTE COM GASTO REAL.**
Guardrails: validados, com 1 falha real encontrada e corrigida (evidência completa acima). Teste real contra conta principal: não executado, conforme regra de fallback da própria ordem master.

**Próxima ação recomendada**: se o usuário quiser de fato avançar com um teste real controlado, a via seguro é abrir uma conta de anúncios sandbox/teste dedicada na Meta (Business Manager → Contas de teste), nunca a conta principal — isso já está refletido na missão corretiva C05 do plano em vigor.
