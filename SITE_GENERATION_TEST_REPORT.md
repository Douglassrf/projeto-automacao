# SITE_GENERATION_TEST_REPORT.md — Missão R06 (Teste de Geração de Site)

Data: 2026-06-19. Commit testado: `700bf363e4d7d313edcb9e6c3b344603ea2101fd`. Backend real (`uvicorn`) rodando, rotas reais de geração de site testadas via HTTP real (`curl`), nenhum deploy externo real feito (GitHub/Vercel/Netlify), confirmado por leitura direta dos arquivos gerados em disco.

## 1. Mapeamento do código (antes do teste)

- **`SiteBuilder`/`deploy_conversion_site`** (`services/site_builder.py`): módulo legado. Gera `index.html` local e chama `trigger_deploy(dry_run=True)` — o `True` está **hardcoded na chamada**, não vem de parâmetro externo, então é impossível forçar um deploy real por aqui mesmo que se quisesse. Usado hoje só em teste de compatibilidade (`test_site_builder_legacy_compat.py`), nenhuma rota chama esse módulo diretamente.
- **`SiteBuilderBridge`** (`services/site_builder_bridge.py`, Missão 23): camada real usada pelas rotas. Gera `index.html`, `styles.css`, `deploy_payload.json` e um manifesto, sempre com `dry_run_forced: true` e `deploy_real_executed: false` no payload de deploy — não chama GitHub/Vercel/Netlify de fato. Depois registra em `CampaignMemoryStore`, `DecisionFeedStore` e consulta `CampaignBrainAgent.review_before_campaign()`.
- **Duas rotas**: `app/api/routes/site_builder_safe.py` (`/api/v1/site-builder-safe/{health,mock-run}`, `POST /generate`) e `app/api/routes/site_builder.py` (`/api/v1/site-builder/{health}`, `POST /generate`).
- A rota "não-safe" (`site_builder.py`) chama um guardrail extra antes de gerar: `site_publish_security_guard()` (`core/route_security.py`), que usa o `CommandValidator` central do projeto (`core/command_validator.py`) — o mesmo mecanismo que, por mapeamento de código, também protege publicação Meta, uso pesado de IA e troca de link de afiliado. Ele valida plataforma/objetivo/país permitidos, limite de orçamento, e exige `human_approved=True` para qualquer ação real (`dry_run=False`).
- **Achado de código, confirmado por grep**: nenhuma das rotas de site-builder declara `Depends(get_current_user)` — mesmo padrão estrutural do R04/R05.
- **Achado de código adicional**: a rota `POST /api/v1/site-builder/generate` calcula o resultado do guard (`guard = site_publish_security_guard(...)`) mas **nunca usa esse resultado para interromper a execução** — chama `SiteBuilderBridge().safe_generate(...)` de qualquer forma, e só inclui o veredito do guard no campo `security_guard` da resposta. Ou seja, o guard é informativo nessa rota, não impositivo.
- O esquema `SiteGenerateRequest` (`schemas/site_builder.py`) **não tem nenhum campo `confirmed_by_user`** — então não existe forma de, através desse contrato de API, fornecer a aprovação humana que o guard exige para publicar de verdade.

## 2. Testes executados e resultado real

| # | Rota | Cenário | Esperado | Resultado real | Status |
|---|---|---|---|---|---|
| 1 | `GET /site-builder-safe/health` | health check | 200, deploy real desabilitado | 200, `deploy_real_enabled:false`, `github_enabled:false`, `vercel_enabled:false`, `netlify_enabled:false` | ✅ |
| 2 | `GET /site-builder-safe/mock-run` | ciclo completo mock (produto fitness) | 200, gera site local, revisão do Brain aprova | 200, `deploy_real_executed:false`, `brain_decision:"SIM"` | ✅ |
| 3 | (verificação de disco) | confirmar que `mock-run` gerou arquivos de fato | 4 arquivos (`index.html`, `styles.css`, `deploy_payload.json`, `manifest.json`) | Confirmado por `find` real — os 4 arquivos existem | ✅ |
| 4 | `POST /site-builder/generate` | `provider:"local"`, `dry_run:true` | guard `status:"ok"`, sem bloqueio | 200, `security_guard.status:"ok"`, `blocked_reasons:[]` | ✅ |
| 5 | `POST /site-builder/generate` | `provider:"github_vercel"`, `dry_run:false`, **sem** `confirmed_by_user` | guard deve bloquear por falta de aprovação humana | 200 (guard `status:"blocked"`, `blocked_reasons:["human_approval_required"]`) — **mas o site foi gerado normalmente mesmo assim** (`deploy_status:"dry_run_payload_ready"`, arquivos criados) | ⚠️ achado |
| 6 | `POST /site-builder/generate` | mesmo caso 5, mas tentando injetar `confirmed_by_user:true` no JSON raiz da requisição | testar se um chamador pode se autoaprovar simplesmente adicionando o campo | guard continuou `status:"blocked"` — confirma que o schema `SiteGenerateRequest` descarta o campo (não declarado), então a auto-aprovação por payload não é possível | ✅ (comportamento seguro) |
| 7 | (verificação de disco) | confirmar que, mesmo nos casos 5/6, nenhum deploy real foi tentado | `deploy_payload.json` deve mostrar `deploy_real_executed:false` e nenhuma chamada de rede | Confirmado por leitura real do arquivo: `"dry_run_forced": true, "deploy_real_executed": false`, avisos explícitos "GitHub/Vercel/Netlify não foram chamados" | ✅ |
| 8 | `GET /site-builder-safe/health` | **sem nenhum header Authorization** | deveria ser 401 se protegida | 200 — confirma ausência estrutural de auth, mesmo padrão do R04/R05 | ⚠️ achado |

## 3. Achado: o guard de segurança da rota "real" é apenas informativo, não bloqueia a execução

O caso 5 é o teste mais revelador desta missão: pedi explicitamente um deploy não-dry-run (`dry_run:false`) para um provedor externo (`github_vercel`) sem fornecer aprovação humana. O `CommandValidator` calculou corretamente `status:"blocked"` com `blocked_reasons:["human_approval_required"]` — a lógica de decisão está certa. Mas a rota (`app/api/routes/site_builder.py`, função `generate`) **chama `SiteBuilderBridge().safe_generate(...)` antes de checar o resultado do guard**, e nunca usa esse resultado para interromper nada — apenas o anexa à resposta em `security_guard`. O site foi gerado normalmente (200, arquivos criados) mesmo com o guard reportando bloqueio.

**Por que isso não causou dano nesta missão:** `SiteBuilderBridge.safe_generate()` é, por construção própria (Missão 23), sempre dry-run — ela nunca chama GitHub/Vercel/Netlify de fato, independente do que o guard decida. Então, hoje, o resultado prático é seguro (confirmado no caso 7: `deploy_real_executed:false` em disco). **Mas o padrão é uma falha de design que merece registro**: se no futuro alguém adicionar uma chamada real de deploy depois da geração do site nessa mesma função, o guard não vai protegê-la, porque o código nunca testa `if guard["status"] == "blocked": ...`. É o mesmo tipo de problema do R04/R05 (uma proteção existe no código mas não está de fato conectada ao fluxo que deveria proteger) — aqui a proteção nem chega a ser auth, é uma checagem de política que roda e é descartada.

**Ponto positivo confirmado no caso 6:** não há um campo `confirmed_by_user` no schema `SiteGenerateRequest`, então mesmo que alguém tente se autoaprovar adicionando esse campo manualmente no JSON, o Pydantic descarta o campo não declarado antes de chegar ao guard — a tentativa de bypass não funciona. Isso significa que, hoje, é estruturalmente impossível aprovar um deploy real através dessa API, mesmo que o guard fosse de fato respeitado.

## 4. Achado: mesmo padrão de ausência de autenticação do R04/R05, agora nas rotas de site builder

Confirmado por grep (zero `get_current_user` em `site_builder.py` e `site_builder_safe.py`) e por teste HTTP real sem header Authorization (caso 8). Mesma recomendação consolidada para R14.

## 5. O que funcionou corretamente (sem achado negativo)

- Geração de HTML/CSS local funciona corretamente, com escaping de HTML (`html.escape`) nos campos de entrada do usuário (proteção básica contra XSS refletido no próprio site gerado).
- Nenhuma chamada real a GitHub/Vercel/Netlify foi feita em nenhum dos 6 cenários testados — confirmado tanto pela resposta HTTP quanto pela leitura direta do `deploy_payload.json` em disco.
- `CampaignBrainAgent` é consultado após a geração do site e aprova/reprova de forma consistente com o que já foi validado no R05.
- Memória de campanha e Decision Feed são gravados corretamente a cada geração (mesmo padrão de persistência real já confirmado em missões anteriores).
- Módulo legado (`SiteBuilder`/`deploy_conversion_site`) tem o `dry_run=True` fixado no próprio código-fonte (não como parâmetro), tornando-o seguro por construção e não apenas por configuração.

## 6. Conclusão da missão R06

| Item | Resultado |
|---|---|
| Geração de site mock (`/site-builder-safe/mock-run`) | Funciona, arquivos gerados e confirmados em disco |
| Geração de site real controlada (`/site-builder/generate`, dry_run) | Funciona corretamente |
| Bloqueio de deploy real sem aprovação humana | **Guard calcula o bloqueio corretamente, mas a rota não o aplica** — execução prossegue mesmo "bloqueada" (achado de design, sem dano prático hoje porque o módulo de geração nunca executa deploy real de qualquer forma) |
| Tentativa de auto-aprovação via payload (`confirmed_by_user`) | Bloqueada — campo não existe no schema, Pydantic descarta |
| Deploy real a GitHub/Vercel/Netlify | Nunca executado em nenhum cenário, confirmado em disco |
| **Autenticação nas rotas de site builder** | **Ausente — mesmo padrão estrutural do R04/R05** |
| Banco de produção real | Intacto, não tocado |

**Status R06: APROVADO COM RESSALVA.** A geração de site funciona corretamente e o deploy real permanece bloqueado por construção em todos os cenários testados, incluindo tentativas adversariais. Dois achados ficam registrados para a missão de segurança final (R14): (1) ausência de autenticação nas rotas de site builder, consolidando o padrão já visto no R04/R05; (2) o guard de aprovação humana (`site_publish_security_guard`) é calculado mas não é de fato aplicado para interromper a rota — hoje sem risco prático, mas é uma armadilha de design para qualquer evolução futura do código que adicione deploy real ali. Pronto para avançar para R07.
