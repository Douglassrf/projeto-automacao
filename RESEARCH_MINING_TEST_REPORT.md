# RESEARCH_MINING_TEST_REPORT.md — Missão R04 (Teste de Pesquisa/Mineração)

Data: 2026-06-19. Commit testado: `700bf363e4d7d313edcb9e6c3b344603ea2101fd`. Backend real (`uvicorn`) rodando, três rotas reais de mineração testadas via HTTP real (`curl`), banco SQLite isolado, nenhuma chamada externa real feita (Meta/Facebook/Selenium/navegador), confirmado pela própria resposta de cada chamada.

## 1. Mapeamento do código (antes do teste)

- `FacebookAdMiner.mine()` (`facebook_ad_miner.py`): mock puro, documentado no próprio docstring ("Não chama API externa. Não usa Selenium. Não abre navegador. Não faz scraping."). Retorna 2 anúncios fake fixos.
- `MinerEngine.analyze_mock()` (`miner_engine.py`): chama `mine()` acima + `AdProcessor` + `CampaignBrainAgent`, monta um pacote de análise mockado completo.
- `MinerEngine.controlled_real_mine()` (Missão 28) e `FacebookAdMiner.controlled_real_collect()` (Missão 29): caminhos "real controlado" — aceitam dados fornecidos localmente (`ads`/`local_export_ads`), e bloqueiam explicitamente (`status: "blocked"`) se `allow_external_call`/`can_external_call`/`use_browser`/`use_selenium`/`source_url` forem usados.
- Três rotas reais e externamente acessíveis, montadas via `safe_router.py` (`prefix=/api/v1`), módulo `meta_operator.py`: `GET /api/v1/miner/test`, `POST /api/v1/miner/controlled-real`, `POST /api/v1/facebook-ad-miner/controlled-real`.
- **Achado de código, confirmado por grep**: nenhuma das três funções de rota declara `Depends(get_current_user)`, e `api_router.include_router(router)` (em `safe_router.py`) também não passa `dependencies=[Depends(...)]`. Ou seja, essas três rotas não têm proteção de autenticação nem por dependency local nem por dependency global — diferente do `AUTH_REQUIRED=false` do R02 (que é um interruptor de configuração), aqui a própria rota nunca declara a exigência de token.

## 2. Testes executados e resultado real

| # | Rota | Método | Cenário | Esperado | Resultado real | Status |
|---|---|---|---|---|---|---|
| 1 | `/api/v1/miner/test` | GET | mock puro, com token válido | 200, dados mockados, `external_calls_made:0` | 200, `status:"ok"`, pacote completo com `mining_package.external_calls_made:0`, `scraping_used:false`, `selenium_used:false`, `browser_used:false` | ✅ |
| 2 | `/api/v1/miner/controlled-real` | POST | export local de 1 anúncio (Missão 28), com token | 200, `status:"approved"`, relatório gravado em disco | 200, `status:"approved"`, `external_calls_made:0`, relatório real gravado em `logs/miner_controlled/miner28_d50539a03e.json` (confirmado por listagem real do diretório) | ✅ |
| 3 | `/api/v1/facebook-ad-miner/controlled-real` | POST | export local de 1 anúncio (Missão 29), com token | 200, `status:"approved"`, relatório gravado em disco | 200, `status:"approved"`, `ads_collected:1`, `external_calls_made:0`, relatório real gravado em `logs/facebook_ad_miner/fbminer29_16dd62b51d.json` (confirmado por leitura real do arquivo) | ✅ |
| 4 | `/api/v1/facebook-ad-miner/controlled-real` | POST | tentativa de forçar `allow_external_call:true`, `use_browser:true`, `use_selenium:true`, `source_url:"https://exemplo.com"` | bloqueado | `status:"blocked"`, `blocked_reasons:["external_call_blocked","browser_blocked","selenium_blocked","source_url_blocked_until_manual_approval"]`, `external_calls_made:0` | ✅ |
| 5 | `/api/v1/miner/test` | GET | **sem nenhum header Authorization** | deveria ser 401 (rota é de produção, deveria exigir login) | **200** — retorna o pacote mockado completo sem token nenhum | ⚠️ achado |
| 6 | `/api/v1/miner/controlled-real` | POST | **sem nenhum header Authorization** | deveria ser 401 | **200** — processa e aprova normalmente, sem token | ⚠️ achado |
| 7 | `/api/v1/facebook-ad-miner/controlled-real` | POST | **sem nenhum header Authorization** | deveria ser 401 | **200** — processa e aprova normalmente, sem token | ⚠️ achado |

## 3. Confirmado: guardrail de bloqueio de chamada real é por construção, não promessa

O caso 4 é o teste mais importante da missão: chamei a rota de "real controlado" pedindo explicitamente `allow_external_call`, `use_browser`, `use_selenium` e `source_url`, simulando alguém tentando forçar uma coleta real. O código bloqueou corretamente, listando cada motivo (`blocked_reasons`), e `external_calls_made` permaneceu `0`. Isso confirma que o guardrail das Missões 28/29 é uma checagem real no código (`if allow_external_call: ... status: "blocked"` em `miner_engine.py` linha 131; lógica equivalente em `facebook_ad_miner.py`), não apenas um comentário ou docstring.

Também inspecionei os 162 relatórios já acumulados em `logs/miner_controlled/` (de execuções anteriores do projeto, antes deste teste) — todos seguem o mesmo formato, com `external_calls_made: 0` consistente, reforçando que esse comportamento é estável, não um acaso desta rodada de teste.

## 4. Achado: rotas de mineração não exigem autenticação — estrutural, não apenas configuração

Diferente do achado do R02 (`AUTH_REQUIRED=false` no `.env`, que é um interruptor de configuração — bastaria mudar para `true` para corrigir), aqui o problema é estrutural: as três rotas de `meta_operator.py` nunca declaram `Depends(get_current_user)` em nenhum nível (nem na função da rota, nem no `include_router`). **Mesmo que `AUTH_REQUIRED` fosse `true` hoje, essas três rotas continuariam abertas**, porque a dependency de autenticação nunca é referenciada nesse arquivo — confirmado por `grep` (zero ocorrências de `get_current_user` em `meta_operator.py`) e por teste HTTP real sem nenhum header Authorization (casos 5, 6 e 7 acima), todos retornando 200.

**Risco real:** qualquer pessoa com acesso à URL do backend pode disparar mineração "real controlada" (Missões 28/29) sem nenhuma credencial. O risco prático é abrandado porque essas rotas só aceitam dados fornecidos no próprio payload da requisição (não há scraping nem chamada externa), mas ainda assim permitem consumo de recursos do servidor, geração de arquivos em `logs/`, e gravação de "aprendizado" na memória de campanha (`CampaignMemoryStore`) por qualquer chamador anônimo.

*Não corrigido nesta missão* — adicionar a proteção de autenticação é uma mudança de código (não apenas de config) que afeta o contrato da API; fica registrado como recomendação prioritária para R14 (segurança final): adicionar `Depends(get_current_user)` nas três rotas de `meta_operator.py`, ou um `dependencies=[Depends(get_current_user)]` no `include_router` correspondente.

## 5. O que funcionou corretamente (sem achado negativo)

- Mock puro (`/miner/test`) determinístico, sem nenhuma chamada externa.
- Caminhos "real controlado" (Missões 28 e 29) aceitam dados locais e processam corretamente, com `CampaignBrainAgent` consultivo (`read_only:true`, `dry_run:true`, `can_execute:false`) revisando cada decisão.
- Bloqueio de tentativa de forçar chamada externa/navegador/Selenium/URL de origem funciona exatamente como o código promete, com motivos de bloqueio explícitos.
- Relatórios de auditoria são gravados de fato em disco (`logs/miner_controlled/`, `logs/facebook_ad_miner/`), não apenas retornados na resposta HTTP — confirmado por leitura real dos arquivos após as chamadas.
- `CampaignIntelligenceSafe` e `MetaUpdateWatcher` (subsistemas chamados pelo `CampaignBrainAgent`) operam em modo local/consultivo, sem rede.

## 6. Conclusão da missão R04

| Item | Resultado |
|---|---|
| Mock de mineração (`/miner/test`) | Funciona, determinístico, zero chamada externa |
| Mineração real controlada (Missão 28) | Funciona, aprova com dados locais, relatório gravado em disco |
| FacebookAdMiner real controlado (Missão 29) | Funciona, aprova com dados locais, relatório gravado em disco |
| Bloqueio de chamada externa/navegador/Selenium forçados | Funciona, com motivos de bloqueio explícitos |
| **Autenticação nas 3 rotas de mineração** | **Ausente — estrutural (nunca declarada), confirmado com HTTP real sem token (200 ao invés de 401)** |
| Banco de produção real | Intacto, não tocado |

**Status R04: APROVADO COM RESSALVA.** A lógica de mineração e os guardrails contra chamada externa real funcionam corretamente e com defesa por construção (não apenas por configuração). A ausência de autenticação nessas três rotas é um achado novo e mais grave que o do R02 (estrutural, não apenas `AUTH_REQUIRED=false`), registrado como recomendação prioritária para a missão de segurança final (R14). Pronto para avançar para R05.
