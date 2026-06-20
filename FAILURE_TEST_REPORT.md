# R13 (F03) — Relatório de testes de falhas controladas

## Escopo e regras de segurança

- Missão: R13 (F03).
- Base: branch local `work`, após C06 aprovada.
- Entregáveis desta missão: `src/app/tests/test_r13_failure_scenarios.py` e este `FAILURE_TEST_REPORT.md`.
- Regras cumpridas: nenhum segredo real persistido em texto puro; `DEFAULT_ADMIN_PASSWORD` foi usado apenas no ambiente do processo de teste; nenhuma flag Meta real foi alterada; o cenário de Meta API usou monkeypatch/tripwire em `httpx.post`, sem chamada de rede real; o cenário de banco indisponível usou monkeypatch/override de dependência, sem apagar arquivo real.

## Comandos executados

```bash
DEFAULT_ADMIN_PASSWORD='test-only-admin-password' pytest src/app/tests/test_r13_failure_scenarios.py -q
```

```bash
DEFAULT_ADMIN_PASSWORD='test-only-admin-password' pytest
```

## Evidência real — suíte R13 isolada

```text
.........                                                                [100%]
=============================== warnings summary ===============================
../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
9 passed, 1 warning in 1.87s
```

Observação: a suíte R13 tem 9 testes automatizados, mas cobre os 10 cenários obrigatórios porque o teste de token cobre token ausente, inválido/malformado, expirado e adulterado, e o teste de upload cobre extensão inválida, magic bytes inválidos, arquivo vazio e arquivo grande demais.

## Evidência real — suíte completa após inclusão da R13

```text
collected 278 items
...
src/app/tests/test_r13_failure_scenarios.py .........                    [ 67%]
...
FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_image - FileNot...
FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_video - FileNot...
FAILED src/app/tests/test_video_pipeline.py::test_video_pipeline_renders_mp4_with_ffmpeg_fallback
================== 3 failed, 275 passed, 3 warnings in 9.83s ===================
```

As 3 falhas da suíte completa permanecem as mesmas já documentadas na C06: dependência ambiental de `ffmpeg` ausente. A inclusão da R13 adicionou 9 testes aprovados, elevando o total de coletados de 269 para 278 e os aprovados de 266 para 275.

## Matriz dos 10 cenários obrigatórios

| # | Cenário | Teste automatizado | Resultado observado | Avaliação |
|---|---|---|---|---|
| 1 | Login inválido | `test_r13_invalid_login_is_controlled` | HTTP 401 com `E-mail ou senha inválidos.` | Erro controlado; sem stack trace no corpo. |
| 2 | Token inválido/expirado/adulterado | `test_r13_missing_invalid_expired_and_tampered_tokens_are_controlled` | HTTP 401 para token malformado, expirado e adulterado com `Token inválido ou expirado.` | Erro controlado; sem segredo no corpo. |
| 3 | Rota protegida sem auth/token ausente | `test_r13_missing_invalid_expired_and_tampered_tokens_are_controlled` | HTTP 401 com `Login necessário.` em `/api/v1/auth/me` | Erro controlado; não trava. |
| 4 | Upload inválido — extensão perigosa | `test_r13_invalid_upload_extension_magic_empty_and_large_are_controlled` | HTTP 400 com bloqueio de extensão perigosa | Erro controlado; sem stack trace. |
| 5 | Upload inválido — magic bytes incompatíveis | `test_r13_invalid_upload_extension_magic_empty_and_large_are_controlled` | HTTP 400 com mensagem de MIME incompatível ou assinatura inválida | Erro controlado; sem stack trace. |
| 6 | Upload inválido — arquivo vazio | `test_r13_invalid_upload_extension_magic_empty_and_large_are_controlled` | HTTP 400 com mensagem contendo `vazio` | Erro controlado; sem stack trace. |
| 7 | Arquivo grande demais | `test_r13_invalid_upload_extension_magic_empty_and_large_are_controlled` | HTTP 400/413 com mensagem contendo `limite` | Erro controlado; sem stack trace. |
| 8 | Banco de dados indisponível | `test_r13_database_unavailable_does_not_expose_stack_trace` | HTTP 500 genérico via dependency override/monkeypatch | Não apaga DB real; não expõe stack trace nem marcador interno. |
| 9 | Meta API falhando | `test_r13_meta_api_failure_uses_tripwire_without_real_network` | `MetaMarketingError: Falha de conexão com a Meta API.` | Tripwire bloqueia rede real; token placeholder não aparece na mensagem. |
| 10 | FFmpeg ausente | `test_r13_ffmpeg_absent_is_controlled` | `RuntimeError: FFmpeg não está instalado no ambiente.` | Falha controlada em serviço; sem segredo. |
| 11 | Erro interno genérico | `test_r13_generic_internal_error_does_not_expose_stack_trace` | HTTP 500 sem stack trace e sem marcador interno | Cenário extra obrigatório do briefing; controlado no cliente. |
| 12 | Rate limit | `test_r13_rate_limit_is_implemented_and_blocks` e `test_r13_gateway_rate_limit_http_response_is_controlled` | `rate_limit_exceeded` no limiter e HTTP 429 `Rate limit excedido.` no middleware | Implementado; não foi necessário documentar como ausente. |

## Observações por requisito

### Login inválido

O endpoint de login rejeitou credenciais erradas com HTTP 401. O teste valida a mensagem pública controlada e verifica ausência de `traceback` no corpo da resposta.

### Token inválido, expirado e adulterado

Foram cobertas três formas de token ruim:

- token malformado (`not-a-jwt`);
- token expirado assinado com a chave de teste em memória;
- token válido adulterado no último caractere.

Todos retornaram HTTP 401 com `Token inválido ou expirado.`.

### Upload inválido e arquivo grande demais

Foram exercitados quatro subcasos: extensão perigosa, magic bytes incompatíveis, upload vazio e payload acima de `upload_max_bytes`. Todos retornaram erro HTTP controlado e não expuseram stack trace.

### Banco indisponível

O teste substitui a dependência `get_db` do endpoint de auth por uma função que lança `SQLAlchemyError`. Nenhum arquivo de banco real foi apagado ou corrompido.

### Meta API falhando sem rede real

O teste instancia `MetaMarketingClient` com placeholders de teste e substitui `httpx.post` por uma função que lança `httpx.ConnectError`. Isso prova o caminho de erro sem qualquer chamada externa real.

### FFmpeg ausente

O teste substitui `shutil.which` por retorno `None` e confirma a mensagem controlada `FFmpeg não está instalado no ambiente.`.

### Erro interno genérico

O teste força exceção sintética no armazenamento de upload e usa `TestClient(..., raise_server_exceptions=False)` para validar que o cliente recebe HTTP 500 sem stack trace ou detalhe interno sensível.

### Rate limit

Rate limit está implementado. A validação foi dupla: no `InMemoryRateLimiter`, que retorna `RateLimitDecision.BLOCK` e `rate_limit_exceeded`; e no middleware HTTP, que retorna 429 com `Rate limit excedido.` quando o bypass do TestClient é desativado por monkeypatch.

## Conclusão R13

R13 (F03) concluída com evidência real. Os 10 cenários obrigatórios foram cobertos sem rede real, sem segredo real em texto puro, sem tocar flags Meta reais e sem apagar banco real. A suíte R13 isolada passou com `9 passed, 1 warning`. A suíte completa passou nos 9 testes novos e manteve apenas as 3 falhas ambientais de `ffmpeg` já conhecidas da C06.
