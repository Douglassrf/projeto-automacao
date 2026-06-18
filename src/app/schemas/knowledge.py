from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeSummaryResponse(BaseModel):
    files: list[str]
    campaign_models: dict[str, str]
    guardrails: list[str]
    connect_rate_warning_below: float


class KnowledgeFileResponse(BaseModel):
    name: str = Field(..., min_length=1)
    content: dict
