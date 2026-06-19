# BACKEND_ROOT_TEST_REPORT.md — Missão R02 (Teste do Backend Raiz)

Data: 2026-06-19. Commit testado: `700bf363e4d7d313edcb9e6c3b344603ea2101fd`. Backend real (`uvicorn app.main:app`) subido como processo de fato, testado via HTTP real (`curl`) contra `127.0.0.1:8000`, banco SQLite isolado (`/tmp/test_adintelligence_r02.db`), nenhuma escrita no banco de produção real.

## 1. Boot do servidor

```
PYTHONPATH=src python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir src
```

Sobe sem erro. Nota: para o servidor carregar o `.env` corretamente E encontrar o módulo `app`, é necessário rodar da raiz do projeto com `--app-dir src` (ou `PYTHONPATH=src`) — confirma na prática o achado do R01 de que `cd src && uvicorn ...` (como o README sugere) faz o `.env` não ser encontrado.

## 2. Endpoints testados via HTTP real

| Endpoint | Método | Resultado | Status |
|---|---|---|---|
| `/api/v1/health` | GET | `{"status":"ok","loaded_routes":41,"failed_routes":0}` | 200 ✅ |
| `/diagnostics` | GET | `{"ok":true,"motor":"ligado",...}` | 200 ✅ |
| `/api/v1/diagnostics/routes` | GET | 41 rotas carregadas, 0 falhas | 200 ✅ |
| `/docs` (Swagger) | GET | HTML servido | 200 ✅ |
| `/openapi.json` | GET | schema servido | 200 ✅ |
| `/api/v1/auth/login` (credenciais corretas) | POST | `access_token` JWT real retornado | 200 ✅ |
| `/api/v1/auth/login` (senha errada) | POST | `{"detail":"E-mail ou senha inválidos."}` | 401 ✅ |
| `/api/v1/auth/me` (com token válido) | GET | dados reais do usuário admin | 200 ✅ |
| `/api/v1/rota/que/nao/existe` | GET | `{"detail":"Not Found"}` | 404 ✅ |
| `/api/v1/automation-control/status` | GET | nível 0 (manual), `dry_run:true` | 200 ✅ |

Fluxo de autenticação completo (login → token → endpoint protegido → dados corretos) funciona de ponta a ponta com banco real isolado e credencial real do `.env`.

## 3. Achado crítico confirmado com evidência ao vivo: autenticação não está ativa

```
curl http://127.0.0.1:8000/api/v1/auth/me   (SEM nenhum header Authorization)
→ HTTP 200, retorna os dados completos do usuário admin (id, nome, e-mail, nível de acesso)
```

Esperado seria `401`. Causa raiz confirmada:

- `config.py` define o default seguro: `auth_required: bool = True`.
- Mas o `.env` real do projeto (e também o `.env.example`, o template que qualquer novo setup copia) define explicitamente `AUTH_REQUIRED=false`.
- Com `auth_required=False`, a dependency `get_current_user` ignora qualquer token e devolve o admin padrão sem checagem nenhuma — comportamento já havia sido sinalizado como AMARELO na auditoria funcional (H01, item 68), e agora está **confirmado com requisição HTTP real, sem mock**.

**Risco real:** qualquer pessoa com acesso à URL do backend (não só `localhost`, se exposto em rede) consegue ler dados de usuário e endpoints "protegidos" sem credencial nenhuma, enquanto a configuração permanecer como está hoje (idêntica à de qualquer novo clone do projeto, pois `.env.example` já vem assim).

*Não corrigido nesta missão* — mudar esse valor padrão é uma decisão de produto/segurança que afeta como o ambiente de desenvolvimento local funciona hoje (a suíte de testes e o uso local atual dependem de `AUTH_REQUIRED=false` para não exigir login a cada chamada). Fica registrado como recomendação prioritária: exigir `AUTH_REQUIRED=true` antes de qualquer exposição fora de `localhost`, e remover o valor `false` do `.env.example` (ou documentar bem alto que é só para dev local).

## 4. Achado confirmado com evidência ao vivo: CORS não está ativo

```
curl -X OPTIONS /api/v1/health -H "Origin: http://exemplo-externo.com" -H "Access-Control-Request-Method: GET"
→ HTTP 405 Method Not Allowed, NENHUM header Access-Control-Allow-* na resposta
```

Confirma ao vivo o achado AMARELO/VERMELHO do H01: `CORSMiddleware` nunca é registrado em `app/main.py`, apesar de `cors_origins`/`allowed_origins` existirem na configuração. Nenhum navegador front-end externo conseguiria de fato chamar essa API hoje (preflight falha), mas isso também significa que a config de CORS existente é inteiramente decorativa.

## 5. O que funcionou corretamente (sem achado negativo)

- 41/41 rotas carregam sem erro de import.
- Diagnóstico de saúde, Swagger e OpenAPI servidos corretamente.
- Hashing de senha e emissão/validação de JWT funcionam corretamente (login certo → token válido; login errado → 401; token válido → dados corretos).
- 404 correto para rota inexistente (sem stack trace exposto).
- `/api/v1/automation-control/status` reporta corretamente o estado real e conservador do sistema: nível de automação 0 (somente sugestão, execução manual), `dry_run: true` — concorda com o que o H01 já havia documentado sobre a postura de segurança do automation control.
- Nenhuma chamada externa real foi feita (Meta, TikTok, etc.) durante este teste — escopo limitado ao backend raiz, como pedido pela missão.

## 6. Conclusão da missão R02

| Item | Resultado |
|---|---|
| Servidor sobe e aceita conexões reais | Sim |
| Rotas carregadas | 41/41 |
| Login real (certo/errado) | 200 / 401, corretos |
| Endpoint protegido com token | 200, dados corretos |
| **Endpoint "protegido" sem token** | **200 (deveria ser 401) — `AUTH_REQUIRED=false` no `.env`/`.env.example`** |
| CORS | Ausente (confirmado, sem header) |
| 404 para rota inexistente | Correto |
| Banco de produção real | Intacto, não tocado (banco isolado usado neste teste) |

**Status R02: APROVADO COM RESSALVA.** O backend raiz funciona corretamente em todos os fluxos testados. Duas lacunas de segurança já mapeadas no H01 foram confirmadas com evidência HTTP real e ficam registradas como pendência de decisão (não bloqueiam o restante da bateria de testes local, mas bloqueiam qualquer exposição fora de `localhost`). Pronto para avançar para R03.
