"""Rotas de distribuicao multiplataforma (Shorts, LinkedIn, X, Snapchat, Kwai)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import distribution_engine

router = APIRouter(prefix="/distribution", tags=["Distribuicao Multiplataforma"])


class DistributeRequest(BaseModel):
    product: str = Field(..., min_length=2)
    source_script: str = Field(..., min_length=10, description="Roteiro/copy campeao gerado pela pesquisa")
    source_platform: str = Field("tiktok", description="tiktok ou facebook")
    landing_url: str = Field("")
    language: str = Field("pt-BR")


@router.get("/status")
def status():
    import os

    return {
        "status": "ok",
        "platforms": {
            k: {
                "nome": p["nome"],
                "publicacao_automatica": "ativa" if os.getenv(p["token_env"]) else f"pendente ({p['token_env']})",
            }
            for k, p in distribution_engine.PLATFORMS.items()
        },
    }


@router.post("/pack")
def pack(payload: DistributeRequest):
    return distribution_engine.distribute(
        payload.product,
        payload.source_script,
        payload.source_platform,
        payload.landing_url,
        payload.language,
    )
