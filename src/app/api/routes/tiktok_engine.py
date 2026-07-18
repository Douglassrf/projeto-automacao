"""Rotas TikTok: mineracao real + remodelagem de video + anuncio pronto + V1/V2/V3."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import tiktok_engine

router = APIRouter(prefix="/tiktok", tags=["TikTok - Mineracao e V1-V3"])


class TikTokMineRequest(BaseModel):
    keyword: str = Field(..., min_length=2)
    region: str = Field("BR", description="BR, US ou EU")
    limit: int = Field(50, ge=5, le=50)


class TikTokPipelineRequest(BaseModel):
    keyword: str = Field(..., min_length=2)
    region: str = Field("BR", description="BR, US ou EU")
    product_name: str | None = None


@router.get("/status")
def status():
    return {
        "status": "ok",
        "token_configured": tiktok_engine._get_token() is not None,
        "regions": list(tiktok_engine.REGION_MAP.keys()),
        "classification": "OURO / PRATA / BRONZE por curtidas + tempo ativo",
        "stages": {k: v["goal"] for k, v in tiktok_engine.TIKTOK_STAGES.items()},
        "message": (
            "Pronto para minerar o TikTok Creative Center."
            if tiktok_engine._get_token()
            else "Falta TIKTOK_ACCESS_TOKEN nas variaveis da Vercel (business-api.tiktok.com)."
        ),
    }


@router.post("/mine")
def mine(payload: TikTokMineRequest):
    return tiktok_engine.mine_top_ads(payload.keyword, region=payload.region, limit=payload.limit)


@router.post("/pipeline")
def pipeline(payload: TikTokPipelineRequest):
    return tiktok_engine.run_tiktok_pipeline(
        payload.keyword, region=payload.region, product_name=payload.product_name
    )


@router.get("/stages")
def stages():
    return {"status": "ok", "escada": tiktok_engine.TIKTOK_STAGES}


class TikTokRenderRequest(BaseModel):
    product_name: str = Field(..., min_length=2)
    keyword: str | None = None
    region: str = Field("BR")
    voice_provider: str = Field("auto", description="auto usa edge-tts gratuito se nao houver chave paga")


@router.post("/render-video")
def render_video(payload: TikTokRenderRequest):
    """Gera o roteiro remodelado e RENDERIZA o video 9:16 com voz (ffmpeg + edge-tts).

    Observacao: a renderizacao usa ffmpeg local — funciona no servidor proprio/PC;
    na Vercel serverless o ffmpeg nao esta disponivel.
    """
    from app.schemas.video_pipeline import VideoRenderRequest
    from app.services.video_pipeline import VideoRenderPipeline

    script_data = tiktok_engine.remodel_video_script(payload.product_name)
    raw = script_data.get("script")
    if isinstance(raw, dict):
        script_text = " ".join(str(v) for k, v in raw.items() if k not in {"texto_na_tela", "audio"})
        hook = raw.get("hook_0_3s", f"Voce precisa conhecer o {payload.product_name}!")
    else:
        script_text = str(raw)
        hook = script_text.splitlines()[0][:200] if script_text else payload.product_name

    render_req = VideoRenderRequest(
        product_name=payload.product_name,
        model="V1",
        hook=str(hook)[:220],
        script=script_text[:4000],
        cta="Comprar agora",
        language="pt-BR",
        aspect_ratio="9:16",
        voice_provider=payload.voice_provider,
        duration_seconds=35,
    )
    result = VideoRenderPipeline().render(render_req)
    return {
        "status": "ok",
        "roteiro": script_data,
        "render": result,
    }


class ReferenceAnalysisRequest(BaseModel):
    reference: str = Field(..., min_length=5, description="Link ou descricao do video que viralizou")
    product: str = Field(..., min_length=2)
    niche: str = Field("")
    objective: str = Field("VENDAS")


@router.post("/analyze-reference")
def analyze_reference(payload: ReferenceAnalysisRequest):
    """Auditoria de Alta Performance (4 camadas) de um video viral de referencia."""
    from app.services import viral_director

    return viral_director.analyze_reference(
        payload.reference, payload.product, payload.niche, payload.objective
    )


class ViralScriptRequest(BaseModel):
    product: str = Field(..., min_length=2)
    niche: str = Field("")
    angle: str = Field("")


@router.post("/viral-script")
def viral_script(payload: ViralScriptRequest):
    """Roteiro viral cena a cena (Diretor Criativo) pronto para o render-premium."""
    from app.services import viral_director

    return viral_director.build_viral_script(payload.product, payload.niche, payload.angle)


class PremiumVideoRequest(BaseModel):
    product_name: str = Field(..., min_length=2)
    image_urls: list[str] = Field(..., min_length=1, description="3-8 fotos do produto (URLs ou caminhos locais)")
    script: str | None = Field(None, description="Roteiro; se vazio, a DeepSeek gera")
    cta: str = Field("COMPRAR AGORA")
    language: str = Field("pt-BR")
    music_path: str | None = Field(None, description="Caminho local de um mp3 de trilha (opcional)")


@router.post("/render-premium")
def render_premium(payload: PremiumVideoRequest):
    """Video estilo TikTok viral: fotos reais do produto + zoom cinematografico +
    cortes rapidos + legendas grandes + narracao neural. Roda localmente (FFmpeg)."""
    from app.services.premium_video import PremiumVideoRenderer

    script = payload.script
    if not script:
        data = tiktok_engine.remodel_video_script(payload.product_name)
        raw = data.get("script")
        if isinstance(raw, dict):
            script = " ".join(str(v) for k, v in raw.items() if k not in {"texto_na_tela", "audio"})
        else:
            # remover rotulos tipo 'HOOK (0-3s):' do roteiro da IA
            import re as _re
            script = _re.sub(r"^[A-Z_+ ]+\(\d+-\d+s\):\s*", "", str(raw), flags=_re.MULTILINE)

    return PremiumVideoRenderer().render(
        product_name=payload.product_name,
        script=script or payload.product_name,
        image_sources=payload.image_urls,
        cta=payload.cta,
        language=payload.language,
        music_path=payload.music_path,
    )
