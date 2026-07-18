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
