from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExistingContentItem(BaseModel):
    title: str = Field(..., min_length=1, max_length=220)
    summary: str | None = Field(default=None, max_length=1000)


class ContentOrchestratorRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=220)
    brief: str = Field(..., min_length=1, max_length=4000)
    target_platform: str = Field("Meta Ads", max_length=80)
    desired_format: Literal["auto", "text", "image", "video"] = "auto"
    existing_content: list[ExistingContentItem] = Field(default_factory=list, max_length=50)
    quality_threshold: float = Field(8.0, ge=0, le=10)


class ContentOrchestratorResponse(BaseModel):
    status: Literal["ok", "erro"]
    acao: str
    proximo_passo: str
    log: dict
    generated_payload: dict | None = None
    created_at: datetime
