# Relatório — Missão 18 / Auditoria Profunda do VideoPipeline

## Regra da Bússola

Missão executada em modo:

```txt
AUDITORIA SEM ALTERAÇÃO
```

Foi proibido:

```txt
alterar código
corrigir código
gerar vídeo real
executar FFmpeg
ativar PremiumRender
ativar SiteBuilder
integrar com Meta
integrar com TikTok
```

Nenhum arquivo do projeto foi modificado.

## Base auditada

Arquivo base:

```txt
projeto_automacao_missao17_content_orchestrator_safe.zip
```

## Memória de partida

Estado anterior registrado:

```txt
Missão 15  — MasterContext implementado
Missão 15A — Memória Mestre homologada
Missão 16  — ContentOrchestrator auditado
Missão 17  — ContentOrchestrator Safe aprovado
Próxima missão — 18, Auditoria Profunda do VideoPipeline
```

## Arquivos auditados

```txt
src/app/services/video_pipeline.py
src/app/api/routes/video_pipeline.py
src/app/schemas/video_pipeline.py
src/app/tests/test_video_pipeline.py
src/app/core/config.py
src/app/services/content_orchestrator_bridge.py
src/app/services/premium_render.py
src/app/api/safe_router.py
```

## Veredito técnico

O `VideoPipeline` é:

```txt
REAL
OPERACIONAL EM TEORIA
NÃO É PLACEHOLDER
NÃO É NOOP
RISCO MÉDIO
```

Ele possui lógica real para criar um vídeo MP4 local, mas depende de FFmpeg e caminho de saída com permissão.

## Classe principal

```txt
VideoRenderPipeline
```

Métodos encontrados:

```txt
__init__
render
_estimate_duration
_script_markdown
_render_voice
_render_elevenlabs
_render_openai_tts
_write_silent_wav
_storyboard
_render_scene_with_ffmpeg
```

Funções auxiliares:

```txt
_safe_slug
_escape_drawtext
_wrap
```

## O que ele recebe

Schema:

```txt
VideoRenderRequest
```

Campos:

```txt
product_name
model: V1/V2/V3/V4/V5/V6
hook
script
cta
language
aspect_ratio: 9:16/1:1/16:9
voice_provider: auto/fallback/elevenlabs/openai
scene_provider: ffmpeg_local/huggingface_svd
duration_seconds
```

## O que ele produz

Schema:

```txt
VideoRenderResponse
```

Campos:

```txt
product_name
model
generated_at
provider
output_folder
script_file
audio_file
video_file
final_mp4
duration_seconds
status
warnings
```

## Fluxo interno

```txt
VideoRenderRequest
        ↓
render()
        ↓
cria output_dir
        ↓
gera script.md
        ↓
gera voiceover.wav
        ↓
gera storyboard.json
        ↓
gera scene_card.mp4
        ↓
gera final_mp4
        ↓
VideoRenderResponse
```

## Arquivos gerados pelo pipeline

```txt
script.md
voiceover.wav
storyboard.json
scene_card.mp4
<produto>_<modelo>_final.mp4
```

## Dependências identificadas

### Dependências internas

```txt
app.core.config.get_settings
app.schemas.video_pipeline.VideoRenderRequest
app.schemas.video_pipeline.VideoRenderResponse
```

### Dependências externas/ambiente

```txt
FFmpeg
subprocess
wave
httpx
ElevenLabs opcional
OpenAI TTS opcional
```

## FFmpeg

O método:

```txt
_render_scene_with_ffmpeg
```

chama:

```txt
shutil.which("ffmpeg")
```

Se FFmpeg não existir, lança:

```txt
RuntimeError("FFmpeg não está instalado no ambiente.")
```

Depois usa `subprocess.run()` para gerar:

```txt
scene_card.mp4
final_mp4
```

Conclusão:

```txt
FFmpeg é requisito crítico para vídeo real.
```

## TTS / voz

Método:

```txt
_render_voice
```

Ordem:

```txt
1. ElevenLabs, se tiver chave.
2. OpenAI TTS, se tiver chave.
3. fallback local com WAV silencioso.
```

Conclusão:

O pipeline foi desenhado para funcionar sem chave externa, usando fallback silencioso.

## Rota FastAPI

Arquivo:

```txt
src/app/api/routes/video_pipeline.py
```

Rota:

```txt
POST /api/v1/video/render
```

Observação crítica:

A rota exige autenticação:

```txt
current_user: User = Depends(get_current_user)
```

Conclusão:

Para testes seguros sem login, uma camada `VideoPipelineSafe` será necessária na próxima missão.

## Configurações relevantes

Arquivo:

```txt
src/app/core/config.py
```

Configurações encontradas:

```txt
kit_output_dir = /data/campaign_kits
elevenlabs_api_key = 
openai_api_key = 
video_provider = ffmpeg_local
war_kit_execute_video_render = False
huggingface_token = 
huggingface_video_space = None
```

## Risco de permissão

O output padrão usa:

```txt
/data/campaign_kits
```

Esse mesmo padrão já causou problema na Missão 13 com o LearningLoop.

Risco:

```txt
ambientes sem permissão para criar /data podem falhar.
```

Recomendação:

Na Missão 19, criar camada safe com output local:

```txt
data/campaign_kits
```

dentro do projeto.

## Testes encontrados

Arquivo:

```txt
src/app/tests/test_video_pipeline.py
```

Testes principais:

```txt
test_video_pipeline_renders_mp4_with_ffmpeg_fallback
test_war_kit_can_render_video_assets
```

O primeiro teste altera temporariamente:

```txt
settings.kit_output_dir
```

para uma pasta `tmp_path`, exatamente como fizemos no LearningLoop Safe.

Conclusão:

O próprio teste confirma que a forma segura é usar output local controlado.

## Relação com War Kit

Foram encontradas referências em:

```txt
app/schemas/war_kit.py
app/services/war_kit_generator.py
```

Indício:

```txt
VideoPipeline já foi pensado para gerar assets dentro do War Kit.
```

Mas esta auditoria não ativou War Kit.

## Relação com ContentOrchestrator Safe

O ContentOrchestrator Safe gera payload com:

```txt
type: video
tool: huggingface_zerogpu_video_or_ffmpeg_pipeline
```

Mas ainda não chama `VideoRenderPipeline`.

Conclusão:

A Missão 19 deve criar a ponte segura:

```txt
ContentOrchestrator Safe
        ↓
VideoPipeline Safe
```

sem render pesado real inicialmente.

## Pontos positivos

```txt
Não é placeholder.
Tem classe real.
Tem schema claro.
Tem rota FastAPI.
Tem teste real.
Tem fallback de áudio local.
Gera storyboard.
Gera script.
Gera MP4 via FFmpeg.
Suporta V1 a V6.
Suporta 9:16, 1:1 e 16:9.
```

## Pontos negativos / riscos

```txt
Rota atual exige autenticação.
Depende de FFmpeg instalado.
Usa subprocess.
Caminho padrão /data pode falhar por permissão.
TTS externo pode chamar ElevenLabs/OpenAI se houver chaves.
Pode gerar arquivos pesados.
Ainda não está conectado ao Brain/DecisionFeed.
Ainda não está conectado ao ContentOrchestrator Safe.
```

## Classificação

```txt
Status: REAL
Maturidade: PARCIALMENTE OPERACIONAL
Risco: MÉDIO
Valor estratégico: MUITO ALTO
```

## Parecer do arquiteto

O `VideoPipeline` é uma peça real da fábrica.

Ele já consegue, em tese, gerar vídeo final `.mp4`, mas não deve ser ativado diretamente pelo fluxo principal ainda.

Antes disso, precisa de uma camada segura que:

```txt
1. Force voice_provider=fallback.
2. Use output local do projeto.
3. Bloqueie providers externos.
4. Verifique FFmpeg.
5. Permita mock/dry-run.
6. Registre resultado no DecisionFeed.
7. Envie resumo ao Brain.
```

## Próxima missão recomendada

```txt
Missão 19 — VideoPipeline Safe
```

Objetivo:

```txt
Criar camada segura para validar o VideoPipeline sem derrubar FastAPI e sem usar providers externos.
```

Permitido:

```txt
dry run
mock render
output local
teste de disponibilidade do FFmpeg
registro em memória
registro no DecisionFeed
revisão pelo Brain
```

Proibido:

```txt
render pesado
Meta real
TikTok
PremiumRender
SiteBuilder
providers externos
```

## Conclusão

A Missão 18 confirmou que o VideoPipeline é real e estratégico, mas possui riscos técnicos que justificam uma ativação controlada na Missão 19.

Nenhum arquivo do projeto foi alterado nesta missão.
