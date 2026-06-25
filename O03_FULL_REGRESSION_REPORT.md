# O03 — FULL REGRESSION REPORT

Data UTC: 2026-06-23
Commit base validado: eeae21e
Missão: revalidar end-to-end os módulos existentes (Upload, Site Builder, Brain, Vídeos, TikTok, Meta, Dashboard, Mission Control, Smart Notifications, Douglas Memory) sem introduzir funcionalidade nova.

## Veredito

**REPROVADO / BLOQUEADO POR AMBIENTE PARA VÍDEO.**

A suíte de regressão foi executada **3 vezes consecutivas** conforme a regra da Fase Ômega. Em todas as 3 execuções o resultado foi o mesmo:

- `299 passed`
- `3 failed`
- `3 warnings`

As 3 falhas são relacionadas a processamento/geração de mídia por `ffmpeg`, que está indisponível neste ambiente. A regra operacional do usuário determina tratar `ffmpeg` real indisponível como limitação permanente do ambiente e **não fingir validação com shim**.

## Comandos executados

```bash
python -m pytest --version && for i in 1 2 3; do echo "===== O03 FULL REGRESSION RUN $i/3 ====="; python -m pytest src/app/tests -q; done 2>&1 | tee /tmp/o03_pytest_runs.log
```

```bash
{ echo '===== ENV CHECK ====='; date -u; git rev-parse --short HEAD; command -v ffmpeg || echo 'ffmpeg: not found'; echo '===== FAILURE SUMMARY ====='; rg -n "FAILED|short test summary|[0-9]+ failed, [0-9]+ passed" /tmp/o03_pytest_runs.log; } 2>&1 | tee /tmp/o03_env_summary.log
```

## Evidência literal — ambiente

```text
===== ENV CHECK =====
Tue Jun 23 13:01:37 UTC 2026
eeae21e
ffmpeg: not found
===== FAILURE SUMMARY =====
452:=========================== short test summary info ============================
453:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_image - FileNot...
454:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_video - FileNot...
455:FAILED src/app/tests/test_video_pipeline.py::test_video_pipeline_renders_mp4_with_ffmpeg_fallback
456:3 failed, 299 passed, 3 warnings in 14.41s
908:=========================== short test summary info ============================
909:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_image - FileNot...
910:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_video - FileNot...
911:FAILED src/app/tests/test_video_pipeline.py::test_video_pipeline_renders_mp4_with_ffmpeg_fallback
912:3 failed, 299 passed, 3 warnings in 11.28s
1364:=========================== short test summary info ============================
1365:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_image - FileNot...
1366:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_video - FileNot...
1367:FAILED src/app/tests/test_video_pipeline.py::test_video_pipeline_renders_mp4_with_ffmpeg_fallback
1368:3 failed, 299 passed, 3 warnings in 12.91s
```

## Resultado por execução

| Execução | Resultado | Observação |
|---|---:|---|
| Run 1/3 | 3 failed, 299 passed, 3 warnings | Falhas em UGC/video por ausência de `ffmpeg` |
| Run 2/3 | 3 failed, 299 passed, 3 warnings | Falhas repetidas em UGC/video por ausência de `ffmpeg` |
| Run 3/3 | 3 failed, 299 passed, 3 warnings | Falhas repetidas em UGC/video por ausência de `ffmpeg` |

## Falhas identificadas

1. `src/app/tests/test_ugc_processing.py::test_process_ugc_image`
   - Falha: `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'`
2. `src/app/tests/test_ugc_processing.py::test_process_ugc_video`
   - Falha: `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'`
3. `src/app/tests/test_video_pipeline.py::test_video_pipeline_renders_mp4_with_ffmpeg_fallback`
   - Falha: endpoint retornou `500` com `{"detail":"Falha ao renderizar vídeo: FFmpeg não está instalado no ambiente."}` em vez de `200`.

## Interpretação por módulo O03

- Upload: coberto pela suíte geral; sem falha específica fora do bloqueio de mídia.
- Site Builder: coberto pela suíte geral; sem falha específica fora do bloqueio de mídia.
- Brain: coberto pela suíte geral; sem falha específica fora do bloqueio de mídia.
- Vídeos: **bloqueado/reprovado no ambiente** porque depende de `ffmpeg` real.
- TikTok: coberto pela suíte geral; sem falha específica fora do bloqueio de mídia.
- Meta: coberto pela suíte geral; sem falha específica fora do bloqueio de mídia.
- Dashboard: coberto pela suíte geral; sem falha específica fora do bloqueio de mídia.
- Mission Control: coberto pela suíte geral; sem falha específica fora do bloqueio de mídia.
- Smart Notifications: coberto pela suíte geral; sem falha específica fora do bloqueio de mídia.
- Douglas Memory: coberto pela suíte geral; sem falha específica fora do bloqueio de mídia.

## Evidência literal — resumo das 3 execuções

```text
1:===== O03 FULL REGRESSION RUN 1/3 =====
203:E                   FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
205:/root/.pyenv/versions/3.14.4/lib/python3.14/subprocess.py:1990: FileNotFoundError
401:E                   FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
403:/root/.pyenv/versions/3.14.4/lib/python3.14/subprocess.py:1990: FileNotFoundError
425:E           AssertionError: {"detail":"Falha ao renderizar vídeo: FFmpeg não está instalado no ambiente."}
452:=========================== short test summary info ============================
453:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_image - FileNot...
454:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_video - FileNot...
455:FAILED src/app/tests/test_video_pipeline.py::test_video_pipeline_renders_mp4_with_ffmpeg_fallback
456:3 failed, 299 passed, 3 warnings in 14.41s
457:===== O03 FULL REGRESSION RUN 2/3 =====
659:E                   FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
661:/root/.pyenv/versions/3.14.4/lib/python3.14/subprocess.py:1990: FileNotFoundError
857:E                   FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
859:/root/.pyenv/versions/3.14.4/lib/python3.14/subprocess.py:1990: FileNotFoundError
881:E           AssertionError: {"detail":"Falha ao renderizar vídeo: FFmpeg não está instalado no ambiente."}
908:=========================== short test summary info ============================
909:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_image - FileNot...
910:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_video - FileNot...
911:FAILED src/app/tests/test_video_pipeline.py::test_video_pipeline_renders_mp4_with_ffmpeg_fallback
912:3 failed, 299 passed, 3 warnings in 11.28s
913:===== O03 FULL REGRESSION RUN 3/3 =====
1115:E                   FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
1117:/root/.pyenv/versions/3.14.4/lib/python3.14/subprocess.py:1990: FileNotFoundError
1313:E                   FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
1315:/root/.pyenv/versions/3.14.4/lib/python3.14/subprocess.py:1990: FileNotFoundError
1337:E           AssertionError: {"detail":"Falha ao renderizar vídeo: FFmpeg não está instalado no ambiente."}
1364:=========================== short test summary info ============================
1365:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_image - FileNot...
1366:FAILED src/app/tests/test_ugc_processing.py::test_process_ugc_video - FileNot...
1367:FAILED src/app/tests/test_video_pipeline.py::test_video_pipeline_renders_mp4_with_ffmpeg_fallback
1368:3 failed, 299 passed, 3 warnings in 12.91s
```

## Conclusão O03

O03 não pode ser certificado como “0 failed” neste ambiente. A evidência real mostra uma regressão/bloqueio reprodutível em 3 execuções consecutivas, exclusivamente associado à indisponibilidade do `ffmpeg` real para processamento de mídia.

Conforme a regra fixa da fase, não foi feita tentativa de reinstalar `ffmpeg` e não foi usado shim para fingir processamento real de vídeo.
