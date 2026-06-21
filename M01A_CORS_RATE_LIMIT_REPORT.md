# M01-A — CORS e Rate Limiting Report

## Escopo executado
- CORS centralizado no app FastAPI com `CORSMiddleware`, allowlist explícita via `CORS_ORIGINS` e sem wildcard por padrão.
- Rate limiting HTTP configurável por variáveis de ambiente, reaproveitando o guard central existente da API.
- Respostas bloqueadas por rate limit mantêm status `429` e agora incluem o header `Retry-After`.
- Variáveis novas documentadas em `.env.example`, sem segredos reais.
- Testes automatizados adicionados para:
  - Origin permitida pela allowlist de CORS.
  - Origin fora da allowlist bloqueada.
  - Rate limit HTTP retornando `429` e `Retry-After` ao exceder o limite configurado no teste.
- Teste legado R14 atualizado para refletir a nova exigência aprovada de CORS restritivo.
- Fixture de testes ajustada para prover uma senha administrativa apenas em ambiente de teste quando `DEFAULT_ADMIN_PASSWORD` não está definido, preservando a exigência de senha real na aplicação.

## Restrições confirmadas
- Nenhuma credencial real adicionada.
- Nenhum push ou merge direto executado.
- Nenhuma alteração relacionada a TikTok.
- Nenhuma alteração de integração, chamada, credencial ou flag operacional de Meta/Facebook Ads. As regras já existentes de categorização de rate limit foram mantidas e apenas passaram a receber limites configuráveis.
- Nenhuma remoção, afrouxamento ou bypass da autenticação de produção (`AUTH_REQUIRED`, `Depends(get_current_user)`).

## Evidência literal de testes

### Teste focado M01-A
Comando:
```bash
pytest src/app/tests/test_m01a_cors_rate_limit.py -q
```

Saída:
```text
...                                                                      [100%]
=============================== warnings summary ===============================
../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
3 passed, 1 warning in 1.59s
```

### Regressão completa
Comando:
```bash
pytest -q
```

Saída:
```text
........................................................................ [ 24%]
........................................................................ [ 49%]
........................................................................ [ 74%]
........................................................................ [ 99%]
.                                                                        [100%]
=============================== warnings summary ===============================
../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(

src/app/tests/test_production_hardening_review.py::test_production_hardening_can_be_ready_with_rotated_secret_and_limits
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/jwt/api_jwt.py:368: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
289 passed, 3 warnings in 14.20s
```

## Limitações conhecidas
- O rate limiter permanece em memória, portanto os contadores não são compartilhados entre múltiplos processos/instâncias. Para deployment horizontal, recomenda-se backend compartilhado (ex.: Redis/KeyDB) em missão futura.
- O bypass existente para `TestClient` foi preservado para compatibilidade com a suíte legada; os testes M01-A usam `User-Agent` explícito para exercitar o middleware de rate limit.
- Alterações de `CORS_ORIGINS` em runtime exigem reinicialização da aplicação, pois o middleware CORS é configurado na criação do app.
