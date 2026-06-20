# C03_VIDEO_AI_GUARD_FIX_REPORT.md — Missão corretiva C03 (Guard de IA pesada/vídeo)

Data: 2026-06-19.

## 1. O que estava errado

`POST /api/v1/video/render` (`src/app/api/routes/video_pipeline.py`) chamava `ai_heavy_security_guard(...)`, mas descartava o resultado. Quando o payload solicitava um provider de cena pesado (`scene_provider="huggingface_svd"`) sem aprovação humana válida, o guard indicava bloqueio, porém a rota seguia para `VideoRenderPipeline().render(payload)`.

Havia ainda um efeito colateral de tratamento de erro: se a rota passasse a levantar `HTTPException(403)` dentro do bloco `try` antigo, o `except Exception` converteria o bloqueio em `500`. A correção precisou deixar a decisão do guard antes do processamento e fora do `try` que encapsula falhas reais de renderização.

## 2. Correção aplicada

Arquivo alterado: `src/app/api/routes/video_pipeline.py`.

- O resultado de `ai_heavy_security_guard(payload.model_dump(mode="json"))` agora é armazenado e respeitado.
- Se `guard["status"] == "blocked"`, a rota registra `video_pipeline.render.blocked` via `app.services.observability.immutable_audit_event(...)` e levanta `HTTPException(403)` antes de instanciar/chamar o pipeline pesado.
- O corpo do erro retorna somente mensagem controlada, `blocked_reasons` e `requires_human_approval`.
- A auditoria grava ator autenticado, produto, providers solicitados e motivos de bloqueio, sem tokens, senhas, chaves ou valores sensíveis.
- Nenhum campo de autoaprovação foi adicionado ao schema. Como `VideoRenderRequest` não declara `confirmed_by_user`, uma tentativa de injetar esse campo no JSON continua sendo descartada pelo Pydantic antes do guard, portanto não aprova a execução.

## 3. Teste — evidência real dos critérios de aceite + tripwire de rede

Arquivo novo: `src/app/tests/test_c03_video_ai_guard_enforced.py` (4 testes).

Comando executado:

```bash
pytest src/app/tests/test_c03_video_ai_guard_enforced.py -q
```

Saída literal:

```text
....                                                                     [100%]
=============================== warnings summary ===============================
../../root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1
  /root/.pyenv/versions/3.14.4/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
4 passed, 1 warning in 1.84s
```

Cobertura dos critérios:

| Critério da missão | Teste | Resultado |
|---|---|---|
| Payload normal continua funcionando | `test_c03_payload_normal_ffmpeg_local_continua_funcionando` | `200`, status `created`, arquivos finais presentes. Como este container não tem binário `ffmpeg`, o teste isola apenas a etapa local de cena com stub de arquivo e mantém o restante do pipeline real (schema, rota, guard, escrita de script/áudio/resposta). |
| Payload bloqueado retorna 403 | `test_c03_payload_bloqueado_retorna_403_e_nao_gera_arquivos` | `403`, `requires_human_approval == True`, `blocked_reasons` contém `human_approval_required`. |
| Nada pesado é gerado quando bloqueado | `test_c03_payload_bloqueado_retorna_403_e_nao_gera_arquivos` e `test_c03_tentativa_de_autoaprovacao_via_payload_extra_continua_bloqueada` | Diretório temporário de kits permanece vazio (`not list((tmp_path / "kits").rglob("*"))`). |
| Autoaprovação via campo extra continua bloqueada | `test_c03_tentativa_de_autoaprovacao_via_payload_extra_continua_bloqueada` | JSON com `confirmed_by_user: true` continua recebendo `403`; o campo extra não chega ao guard. |
| Audit log imutável com hash-chain válido | `test_c03_guard_bloqueado_registra_audit_log_imutavel` | Último evento contém `video_pipeline.render.blocked`, contém `human_approval_required`, e `ImmutableAuditLog(...).verify().ok is True`. |
| Nenhuma rede real | Todos os testes C03 | `monkeypatch` em `httpx.get`, `httpx.post` e `httpx.delete` lança `AssertionError` se qualquer chamada de rede real for tentada. |

## 4. Suíte de regressão completa

Primeira execução, sem credencial sintética de admin no ambiente:

```bash
pytest src/app/tests/ -q
```

Saída literal relevante:

```text
16 failed, 253 passed, 3 warnings in 8.99s
```

Falhas não relacionadas ao C03:

- 13 falhas por `DEFAULT_ADMIN_PASSWORD` ausente/nulo em testes que forçam autenticação real (`test_auth.py`, `test_campaign_intelligence.py`, `test_meta_action_abstraction.py`, `test_meta_sync_worker.py`, `test_scaling_engine.py`). Não foi lido nem alterado `.env` real.
- 3 falhas por ausência do binário `ffmpeg` neste container (`test_ugc_processing.py::test_process_ugc_image`, `test_ugc_processing.py::test_process_ugc_video`, `test_video_pipeline.py::test_video_pipeline_renders_mp4_with_ffmpeg_fallback`).

Segunda execução, com senha sintética apenas no ambiente do processo de teste (sem tocar `.env`):

```bash
DEFAULT_ADMIN_PASSWORD='<valor-sintetico-redigido>' pytest src/app/tests/ -q
```

Saída literal:

```text
. [ 53%]
........................................................................ [ 80%]
..............................FF....F................                    [100%]
=================================== FAILURES ===================================
____________________________ test_process_ugc_image ____________________________
...
E                   FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
...
____________________________ test_process_ugc_video ____________________________
...
E                   FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
...
_____________ test_video_pipeline_renders_mp4_with_ffmpeg_fallback _____________
...
>           assert response.status_code == 200, response.text
E           AssertionError: {"detail":"Falha ao renderizar vídeo: FFmpeg não está instalado no ambiente."}
E           assert 500 == 200
...
3 failed, 266 passed, 3 warnings in 9.83s
```

Interpretação: com credencial sintética, todas as falhas de autenticação desaparecem. Restam apenas as 3 falhas de ambiente por `ffmpeg` ausente. Os 4 testes novos C03 passaram dentro da suíte (total esperado neste branch: 269 testes = 265 baseline informado + 4 C03; resultado observado com senha sintética e sem ffmpeg: 266 passed + 3 failed por ambiente).

## 5. Achados colaterais

- Este container está executando `Python 3.14.4` (`python --version`), acima do mínimo Python 3.11+ solicitado para revalidação posterior em C06.
- `ffmpeg` não está instalado no PATH (`which ffmpeg` não retornou caminho). Isso impede a suíte completa de ficar verde neste container, mas não decorre da alteração C03.
- Nenhum segredo real foi impresso. A credencial usada na segunda regressão foi sintética e temporária, definida apenas para o processo de teste e redigida no relatório.

## 6. Status final

**MISSÃO C03: CORREÇÃO APLICADA COM EVIDÊNCIA REAL.**

O guard de IA pesada/vídeo deixou de ser decorativo: payload bloqueado retorna `403`, não chama processamento pesado, não gera arquivos no disco, registra evento no audit log imutável e mantém a hash-chain válida. Payload normal permanece funcional no teste isolado C03 sob limitação de ambiente sem `ffmpeg`.
