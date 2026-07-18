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
