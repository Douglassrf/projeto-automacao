# C01_AUTH_FIX_REPORT.md — Missão corretiva C01 (Corrigir autenticação das rotas abertas)

Data: 2026-06-19. Origem da missão: parecer técnico da arquiteta ("APROVADO COM RESSALVAS CRÍTICAS"), que listou rotas sensíveis sem `Depends(get_current_user)` como achado crítico a corrigir antes de qualquer nova homologação.

## 1. O que estava errado

As seguintes rotas existiam sem nenhuma verificação de autenticação — qualquer pessoa com a URL conseguia chamá-las, mesmo sem token:

- `GET /api/v1/miner/test`
- `POST /api/v1/miner/controlled-real`
- `POST /api/v1/facebook-ad-miner/controlled-real`
- `GET /api/v1/campaign-operator/status`
- `POST /api/v1/campaign-operator/v3/launch` (rota mais sensível: dispara publicação real na Meta quando todas as flags são liberadas)
- `POST /api/v1/campaign-operator/rollback`
- `GET /api/v1/campaign-operator/rollback/policy`
- `GET /api/v1/campaign-operator/production/readiness`
- `GET /api/v1/campaign-operator/credentials/review`
- `POST /api/v1/campaign-operator/assisted-execution`
- `POST /api/v1/campaign-operator/post-execution/monitor`
- `POST /api/v1/campaign-operator/production/hardening-review`
- `GET /api/v1/campaign/dry-run/mock`, `POST /api/v1/campaign/dry-run`
- `POST /api/v1/agency-operator/workflows`, `GET /api/v1/agency-operator/workflows`, `POST /api/v1/agency-operator/workflows/{id}/{action}`
- `GET /api/v1/campaign-intelligence-safe/health`, `/summary`, `/summary/mock`, `/mock-seed`
- `POST /api/v1/site-builder/generate`

`src/app/api/routes/video_pipeline.py` foi verificado e **já tinha** `Depends(get_current_user)` em todas as rotas — não precisou de alteração nesta missão (seu problema real, ignorar o retorno do `ai_heavy_security_guard`, é da missão C03, fora do escopo de C01).

## 2. Correção aplicada

Adicionado `current_user: User = Depends(get_current_user)` (com os imports `from app.api.deps import get_current_user` e `from app.domain.models import User`) em 4 arquivos:

| Arquivo | Rotas protegidas | Linhas alteradas |
|---|---|---|
| `src/app/api/routes/meta_operator.py` | 14 rotas (lista completa na seção 1) | 58 linhas (+/-) |
| `src/app/api/routes/agency_operator.py` | 3 rotas | 13 linhas (+/-) |
| `src/app/api/routes/campaign_intelligence_safe.py` | 4 rotas | 21 linhas (+/-) |
| `src/app/api/routes/site_builder.py` | 1 rota (`/generate`) | 11 linhas (+/-) |

`GET /site-builder/health` foi deixado sem autenticação de propósito — é um health-check sem dado sensível, mesmo padrão usado em outros módulos do projeto.

O guard `site_publish_security_guard` em `site_builder.py` é calculado mas não é aplicado para bloquear a chamada — isso é a missão C02, não foi tocado aqui.

## 3. Teste 1 — Evidência isolada de que a correção funciona

Mesma metodologia de isolamento usada na missão R11 (nunca tocar no `.env` real, nunca usar segredo/banco real):

- `AUTH_REQUIRED=true` forçado só por variável de ambiente do processo de teste (env var tem precedência sobre `.env` no pydantic-settings) — o `.env` real **não foi lido nem alterado**.
- `JWT_SECRET_KEY` e `DATABASE_URL` sobrescritos para valores isolados (`ISOLATED_C01_TEST_SECRET_NAO_E_REAL`, banco sqlite isolado em `/tmp`).
- Testado contra as 11 rotas representativas dos 4 arquivos corrigidos, cada uma chamada duas vezes: sem token (deve bloquear) e com token de um usuário de teste criado no banco isolado (deve passar da autenticação).

Resultado real (`test_c01_auth_isolated.py`):

```
[OK] setup_login_isolado_funciona
[OK] SEM_TOKEN_bloqueado__GET_/api/v1/miner/test: status=401
[OK] COM_TOKEN_passa_da_auth__GET_/api/v1/miner/test: status=200
[OK] SEM_TOKEN_bloqueado__POST_/api/v1/miner/controlled-real: status=401
[OK] COM_TOKEN_passa_da_auth__POST_/api/v1/miner/controlled-real: status!=401
[OK] SEM_TOKEN_bloqueado__POST_/api/v1/facebook-ad-miner/controlled-real: status=401
[OK] COM_TOKEN_passa_da_auth__POST_/api/v1/facebook-ad-miner/controlled-real: status!=401
[OK] SEM_TOKEN_bloqueado__GET_/api/v1/campaign-operator/status: status=401
[OK] COM_TOKEN_passa_da_auth__GET_/api/v1/campaign-operator/status: status!=401
[OK] SEM_TOKEN_bloqueado__GET_/api/v1/campaign/dry-run/mock: status=401
[OK] COM_TOKEN_passa_da_auth__GET_/api/v1/campaign/dry-run/mock: status!=401
[OK] SEM_TOKEN_bloqueado__POST_/api/v1/agency-operator/workflows: status=401
[OK] COM_TOKEN_passa_da_auth__POST_/api/v1/agency-operator/workflows: status!=401
[OK] SEM_TOKEN_bloqueado__GET_/api/v1/agency-operator/workflows: status=401
[OK] COM_TOKEN_passa_da_auth__GET_/api/v1/agency-operator/workflows: status!=401
[OK] SEM_TOKEN_bloqueado__GET_/api/v1/campaign-intelligence-safe/health: status=401
[OK] COM_TOKEN_passa_da_auth__GET_/api/v1/campaign-intelligence-safe/health: status!=401
[OK] SEM_TOKEN_bloqueado__GET_/api/v1/campaign-intelligence-safe/summary/mock: status=401
[OK] COM_TOKEN_passa_da_auth__GET_/api/v1/campaign-intelligence-safe/summary/mock: status!=401
[OK] SEM_TOKEN_bloqueado__GET_/api/v1/campaign-intelligence-safe/mock-seed: status=401
[OK] COM_TOKEN_passa_da_auth__GET_/api/v1/campaign-intelligence-safe/mock-seed: status!=401
[OK] SEM_TOKEN_bloqueado__POST_/api/v1/site-builder/generate: status=401
[OK] COM_TOKEN_passa_da_auth__POST_/api/v1/site-builder/generate: status!=401

=== RESUMO ===
23/23 verificacoes passaram conforme esperado.
```

**23/23 — sem token bloqueia (401), com token passa.** Critério de aceite da missão C01 cumprido com evidência real.

## 4. Teste 2 — Suíte de regressão completa (com correção de 2 testes quebrados)

Primeira rodada da suíte completa (`pytest src/app/tests/ -q`) após a correção: **258 passaram, 3 falharam.**

Investigação das 3 falhas:

| Teste | Causa raiz | Veredito |
|---|---|---|
| `test_production_hardening_review.py::test_production_hardening_blocks_default_jwt_without_exposing_secret` | O teste força `settings.auth_required = True` de propósito (simula produção) e chama `POST /campaign-operator/production/hardening-review` sem token — antes da C01 a rota não verificava nada, agora bloqueia com 401 antes de chegar no corpo da rota. | **Regressão real causada pela correção C01** — corrigida (ver abaixo) |
| `test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits` | Mesma causa do teste acima. | **Regressão real causada pela correção C01** — corrigida (ver abaixo) |
| `test_meta_production_safety.py::test_meta_operator_blocks_real_publish_without_manual_confirmation` | Investigado isoladamente: a falha real é `ImportError: Using SOCKS proxy, but the 'socksio' package is not installed`, disparada porque o sandbox Linux desta sessão tem variáveis de ambiente `ALL_PROXY=socks5h://localhost:1080` configuradas globalmente, e o `httpx` tenta honrar o proxy ao montar o client. **Nada a ver com autenticação** — confirmado rodando o teste sozinho e lendo o traceback completo (erro de import, não um `401`). | **Falso positivo do ambiente de teste, não é regressão da C01** |

Correção aplicada nos 2 testes legítimos: ambos agora criam um usuário de teste isolado (`UserRepository` + `hash_password`) no próprio banco de teste e geram um token real via `create_access_token`, passado como header `Authorization: Bearer <token>` na chamada — sem nunca usar credencial real. Diff:

```
src/app/tests/test_production_hardening_review.py | 48 +++++++++----------
1 file changed, 24 insertions(+), 24 deletions(-)
```

Para eliminar o falso positivo do ambiente, instalado `socksio` no sandbox de teste (`pip install socksio`) — não é uma alteração de código do projeto, é só uma dependência ausente no ambiente isolado de execução dos testes.

**Resultado final, suíte completa:**

```
261 passed, 1 warning in 22.71s
```

**261/261 — zero falhas, zero regressões.**

## 5. Achado colateral (não relacionado à autenticação, registrado por transparência)

Durante a investigação, identifiquei que `git status`/`git diff` no mount deste sandbox não detectavam as edições recém-feitas nos 5 arquivos acima (cache de stat desatualizado do mount Windows↔Linux — o mesmo tipo de desincronização já visto na missão R11, mas afetando o índice do git em vez do conteúdo lido diretamente). Confirmado comparando `git hash-object` (lê o conteúdo real) com o blob do índice (`git ls-files -s`): eram diferentes, mas `git status` dizia "nothing to commit". Corrigido com `touch` + `git update-index --refresh`. **Isso é relevante para qualquer commit futuro** (inclusive o que será delegado ao Codex/GitHub): antes de confiar em `git status`/`git diff` neste ambiente após edições, vale rodar esse refresh para evitar comitar uma versão desatualizada por engano.

## 6. Ponto de decisão para o Douglas (não é decisão minha)

A correção do código está completa e comprovada, mas o `.env` real continua com `AUTH_REQUIRED=false` — ou seja, **hoje, em produção, a autenticação ainda não é exigida de fato**, porque a flag desliga a obrigatoriedade independentemente do `Depends` estar presente no código (esse é o comportamento documentado de `get_current_user`: com `auth_required=False`, ele retorna um usuário demo sem checar nada).

A correção desta missão é necessária mas não suficiente por si só — falta a decisão de virar `AUTH_REQUIRED=true` no `.env` real. Essa é uma decisão de produto/segurança que não devo tomar sozinho, porque pode quebrar qualquer integração hoje que dependa do acesso sem login (ex.: scripts internos, chamadas do agência-operador sem fluxo de login implementado no lado cliente). Recomendo que, antes de virar a flag em produção, seja confirmado que existe um fluxo de login funcional em todos os clientes que chamam essas rotas.

## 7. Status final

**MISSÃO C01: CONCLUÍDA COM EVIDÊNCIA REAL.**

- Critério de aceite ("rota sensível sem token → 401/403; com token válido → funciona") comprovado em 23/23 verificações isoladas.
- Suíte de regressão completa: 261/261 testes passando, sem nenhum teste fraco ou comportamento mascarado.
- Nenhum segredo real, banco real ou `.env` real foi tocado, lido por valor, ou exposto em nenhum momento.
- Decisão de ativar `AUTH_REQUIRED=true` em produção entregue ao Douglas (seção 6).
