# VIDEO_PIPELINE_TEST_REPORT.md — Missão R08 (Teste de Vídeo)

Data: 2026-06-19. Commit testado: `700bf363e4d7d313edcb9e6c3b344603ea2101fd`. Backend real (`uvicorn`) rodando, rotas reais de vídeo testadas via HTTP real (`curl`), **ffmpeg real disponível no ambiente e efetivamente executado** em um dos testes (renderização real de um `.mp4` válido), nenhuma chamada de TTS externa real feita (ElevenLabs/OpenAI — sem chave configurada).

## 1. Mapeamento do código (antes do teste)

- **Duas camadas distintas, com nomes parecidos mas comportamento muito diferente**:
  - `VideoPipelineBridge` (`services/video_pipeline_bridge.py`, Missão 19) — camada **segura**, rota `app/api/routes/video_pipeline_safe.py` (`/api/v1/video-pipeline-safe/{health,mock-run}`, `POST /render`). Docstring explícito: "Não executa FFmpeg real por padrão. Não chama ElevenLabs/OpenAI TTS." Sempre grava só `script.md` + `storyboard.json` + manifesto, `render_executed:false`, `ffmpeg_real_executed:false`, `final_mp4:null`.
  - `VideoRenderPipeline` (`services/video_pipeline.py`) — camada **real**, rota `app/api/routes/video_pipeline.py` (`POST /api/v1/video/render`). Esta **de fato chama `ffmpeg` via `subprocess.run()`** duas vezes (monta cena com texto + funde com áudio) e produz um `.mp4` final de verdade. TTS externo (ElevenLabs/OpenAI) só é chamado se `settings.elevenlabs_api_key`/`settings.openai_api_key` estiverem configuradas — confirmado que ambas são `None`/vazias por padrão (grep no `.env` e `config.py`); sem chave, cai em fallback determinístico (`_write_silent_wav`, áudio mudo).
  - **Diferente do War Kit (R07)**: a chamada do War Kit ao `VideoRenderPipeline` é condicionada por `settings.war_kit_execute_video_render` (default `False`). **A rota direta `/api/v1/video/render` não tem essa proteção — ela sempre executa render real, em toda chamada, incondicionalmente.** Ou seja, a flag de config só protege o caminho indireto (via War Kit); o endpoint direto está sempre "ligado".
- A rota real (`video_pipeline.py`) declara `Depends(get_current_user)` e também chama `ai_heavy_security_guard(payload.model_dump(...))` antes de renderizar — mas, igual ao achado do R06, **o retorno do guard nunca é verificado nem usado para interromper a execução, e nem é incluído na resposta** (pior que o R06: lá ao menos o guard aparecia no JSON de resposta).
- A rota segura (`video_pipeline_safe.py`) não declara `Depends(get_current_user)` em nenhuma das 3 rotas — confirmado por grep.
- `scene_provider` no schema (`VideoRenderRequest`) aceita `"ffmpeg_local"` ou `"huggingface_svd"`, mas o código de renderização (`_render_scene_with_ffmpeg`) **nunca lê esse campo para mudar de provedor** — sempre usa ffmpeg local, independente do valor enviado. Achado de nomenclatura, não de segurança.

## 2. Testes executados e resultado real

| # | Rota | Cenário | Esperado | Resultado real | Status |
|---|---|---|---|---|---|
| 1 | `GET /video-pipeline-safe/health` | health check | `ffmpeg_real_enabled:false`, `external_tts_enabled:false` | 200, confirmado; `ffmpeg_available:true` (ffmpeg existe no ambiente, mas a camada safe nunca o chama) | ✅ |
| 2 | `GET /video-pipeline-safe/mock-run` | ciclo mock completo | `render_executed:false`, `final_mp4:null` | 200, confirmado | ✅ |
| 3 | (verificação de disco) | confirmar que o mock-run não gerou nenhum `.mp4` | apenas `script.md`+`storyboard.json`+manifesto | Confirmado por `find` real — 3 arquivos, nenhum `.mp4`/`.wav` | ✅ |
| 4 | `POST /api/v1/video/render` (rota **real**) | payload válido, **sem header Authorization** | declara `Depends(get_current_user)`, mas `AUTH_REQUIRED=false` (R02) deveria deixar passar | 200 — kit de vídeo renderizado mesmo sem token | ⚠️ achado (mesma causa raiz do R02, não novo) |
| 5 | `POST /api/v1/video/render`, **com token real**, payload válido | renderizar de fato com ffmpeg | 200, `status:"created"`, `provider:"fallback_local_silent_wav"` | ✅ |
| 6 | (verificação de disco) | o `.mp4` final é um vídeo real e válido? | magic bytes `ftyp`, stream de vídeo H264 + áudio AAC, 5s | Confirmado via `xxd` (assinatura `ftypisom`) e `ffprobe` (`codec_name=h264`/`codec_name=aac`, `duration=5.000000`) | ✅ |
| 7 | (cálculo isolado do guard) | computar `ai_heavy_security_guard` com `scene_provider:"huggingface_svd"` (provider fora do conjunto dry-run, sem `confirmed_by_user`) | guard deve calcular `status:"blocked"` | Confirmado isoladamente: `{"status":"blocked","blocked_reasons":["human_approval_required"]}` | ✅ (cálculo correto) |
| 8 | `POST /api/v1/video/render` com o **mesmo payload do teste 7** (que o guard isoladamente bloqueia) | a rota deveria impedir a renderização | 200 — renderizou normalmente, `.mp4` gerado de fato em disco, campo `security_guard` **nem aparece** na resposta | ⚠️ **achado crítico** |

## 3. Confirmado: render real funciona corretamente (não é decorativo nem mock disfarçado)

O teste 5/6 prova que esta rota é genuinamente funcional: o ffmpeg do ambiente foi de fato invocado (dois processos `subprocess.run`), gerando um arquivo `.mp4` de 38.599 bytes com stream de vídeo H264 e stream de áudio AAC, com a duração exata pedida (5s), confirmado por `ffprobe`. Não é um arquivo vazio nem um mock — é um render real e válido. O áudio ficou mudo porque nenhuma chave de TTS (ElevenLabs/OpenAI) está configurada — comportamento de fallback correto e seguro, sem qualquer chamada de rede externa.

## 4. Achado crítico: o guard de IA pesada é calculado, mas totalmente descartado — pior que o achado do R06

No R06, a rota de site builder ao menos incluía o resultado do guard no JSON de resposta (`security_guard`), mesmo sem usá-lo para bloquear. Aqui, a rota `video_pipeline.py` chama `ai_heavy_security_guard(...)` e **descarta completamente o valor retornado** — não verifica `status`, não inclui no response, nada. O teste 7+8 prova isso de forma definitiva: calculei o guard isoladamente com um payload que força `dry_run=False` e `human_approved=False` (usando `scene_provider:"huggingface_svd"`, fora do conjunto considerado "seguro" pela própria lógica do guard) e confirmei que ele retorna `status:"blocked"` com `blocked_reasons:["human_approval_required"]`. Em seguida enviei exatamente esse payload para a rota real — ela renderizou normalmente, gerando um `.mp4` real em disco, como se o guard nunca tivesse sido chamado.

**Risco prático hoje:** o `scene_provider:"huggingface_svd"` não tem implementação real diferente — o código sempre usa ffmpeg local, então mesmo "ignorando" o bloqueio, nada além de um render local (CPU/disco do próprio servidor) acontece; nenhuma chamada de IA pesada de nuvem é feita de fato (não existe código de integração com Hugging Face neste arquivo). O dano real está em (a) consumo de CPU/disco do servidor por qualquer chamador, sem controle de aprovação, e (b) o padrão de design: se um provedor de vídeo pesado de nuvem for implementado no futuro reaproveitando este mesmo fluxo, o guard não vai protegê-lo, porque o resultado já é ignorado hoje.

**Recomendação para R14:** aplicar o mesmo padrão de correção do R06 (usar o retorno de `ai_heavy_security_guard` para de fato interromper a execução quando `status == "blocked"`), e adicionalmente revisar este caso porque aqui a omissão é mais severa — nem é exposta no JSON de resposta para visibilidade externa.

## 5. Achado: ausência de autenticação nas rotas safe (mesmo padrão do R04/R05/R06)

Confirmado por grep: zero `Depends` em `video_pipeline_safe.py`. Mesma recomendação consolidada para R14.

## 6. O que funcionou corretamente (sem achado negativo)

- Render real local com ffmpeg funciona de ponta a ponta, produzindo arquivo de vídeo válido (H264+AAC) com a duração correta.
- Fallback de áudio mudo funciona corretamente quando nenhuma chave de TTS está configurada — nenhuma chamada de rede externa ocorreu.
- Camada "safe" (`VideoPipelineBridge`) nunca executa ffmpeg nem TTS, mesmo tendo ffmpeg disponível no ambiente — a separação de responsabilidade entre a camada segura e a real está correta nesse sentido.
- Flag de config `war_kit_execute_video_render` continua protegendo corretamente o caminho indireto via War Kit (confirmado no R07).

## 7. Conclusão da missão R08

| Item | Resultado |
|---|---|
| Render real de vídeo (`/api/v1/video/render`) | Funciona corretamente, `.mp4` real e válido confirmado (H264+AAC, ffprobe) |
| Fallback de áudio sem chave de TTS | Funciona, sem chamada externa real |
| Camada safe (`/video-pipeline-safe/*`) | Funciona, nunca executa ffmpeg real, confirmado em disco |
| **Guard de IA pesada (`ai_heavy_security_guard`) na rota real** | **Calculado corretamente de forma isolada, mas totalmente ignorado pela rota — execução prossegue mesmo com guard "blocked", nem aparece na resposta (achado crítico, mais severo que o do R06)** |
| Autenticação na rota real (`/api/v1/video/render`) | Presente no código, neutralizada pelo `AUTH_REQUIRED=false` (mesma causa raiz do R02) |
| Autenticação nas rotas safe | Ausente — mesmo padrão estrutural do R04/R05/R06 |
| Banco de produção real | Intacto, não tocado |

**Status R08: APROVADO COM RESSALVA.** O pipeline de vídeo real funciona genuinamente — confirmado com um render de ffmpeg de fato executado e validado por `ffprobe`, não um mock. A camada segura está corretamente isolada do ffmpeg real. O achado crítico desta missão é a confirmação de que o guard de segurança de IA pesada é calculado mas nunca aplicado nem exposto na rota real de vídeo — um padrão já visto no R06, porém mais grave aqui pela ausência total de visibilidade do resultado do guard na resposta. Registrado como prioridade alta para R14, junto com a ausência de autenticação nas rotas safe. Pronto para avançar para R09.
