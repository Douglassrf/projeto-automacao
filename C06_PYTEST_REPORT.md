# C06 (F02) — Relatório da suíte pytest completa

## Escopo

- Missão: C06 (F02).
- Base de execução: branch local `work`, HEAD `808ba57` (`Merge pull request #1 from Douglassrf/codex/corrigir-guard-de-ia-pesada-na-rota-de-video`).
- Objetivo: executar a suíte pytest completa a partir do estado já mesclado da C03, sem assumir contagem de cabeça, e registrar evidência real.
- Segurança operacional: não houve segredo persistido em arquivo; `DEFAULT_ADMIN_PASSWORD` foi definido apenas no ambiente do processo de teste. Não foi feita chamada de rede real nem alteração de flags Meta reais.

## Comando executado

```bash
DEFAULT_ADMIN_PASSWORD='test-only-admin-password' pytest
```

## Ambiente observado

```text
Python 3.14.4
pytest 9.0.3
rootdir: /workspace/projeto-automacao
configfile: pytest.ini
testpaths: src/app/tests
```

Observação: a exigência era Python 3.11+; a execução ocorreu em Python 3.14.4, portanto dentro do requisito mínimo.

## Evidência real da execução

Trechos finais relevantes do output colado da execução:

```text
collected 269 items
...
FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_image - FileNot...
FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_video - FileNot...
FAILED src/app/tests/test_video_pipeline.py::test_video_pipeline_renders_mp4_with_ffmpeg_fallback
================== 3 failed, 266 passed, 3 warnings in 11.47s ==================
```

Falha 1 — `test_process_ugc_image`:

```text
E                   FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
```

Falha 2 — `test_process_ugc_video`:

```text
E                   FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
```

Falha 3 — `test_video_pipeline_renders_mp4_with_ffmpeg_fallback`:

```text
E           AssertionError: {"detail":"Falha ao renderizar vídeo: FFmpeg não está instalado no ambiente."}
E           assert 500 == 200
```

Warnings observados:

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256.
InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256.
```

## Resultado consolidado

- Coletados: 269 testes.
- Passaram: 266 testes.
- Falharam: 3 testes.
- Warnings: 3.
- Duração reportada pelo pytest: 11.47s.

## Diferença contra a expectativa 265 + 4 = 269

A suíte coletou exatamente 269 itens, compatível com o baseline informado de 265 testes mais 4 testes novos da C03.

A contagem de aprovação final não foi 269 passed porque 3 testes dependem de `ffmpeg` disponível no ambiente atual e falharam por ausência desse binário. Assim, o resultado final observado foi:

```text
266 passed + 3 failed = 269 collected
```

Essa diferença reproduz o baseline pós-C03 já conhecido pelo briefing: 266 passed e 3 falhas relacionadas a ffmpeg/ambiente.

## Conclusão C06

C06 (F02) executada com evidência real. A suíte completa foi rodada, coletou 269 testes, e o resultado real foi `266 passed, 3 failed, 3 warnings`. As falhas são ambientais por ausência de `ffmpeg`; não há evidência nesta execução de regressão funcional fora desse ponto de ambiente.
