from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

WorkflowStatus = Literal["CREATED", "REVIEW_PENDING", "APPROVED", "SCHEDULED", "PUBLISHED", "FAILED", "RETRYING"]


class AgencyWorkflowCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=220)
    brief: str = Field(..., min_length=10, max_length=4000)
    platform: Literal["Instagram", "Facebook", "WhatsApp", "TikTok", "Meta Ads"] = "Instagram"
    content_type: Literal["post", "story", "reels", "ad", "reply"] = "post"
    requires_approval: bool = True


class AgencyWorkflowActionRequest(BaseModel):
    notes: str | None = Field(default="", max_length=1000)


class AgencyWorkflowResponse(BaseModel):
    id: int
    workflow_key: str
    title: str
    platform: str
    content_type: str
    status: str
    draft: dict
    approval_notes: str = ""
    failure_reason: str = ""
    created_at: datetime
    updated_at: datetime


class AgencyWorkflowListResponse(BaseModel):
    total: int
    items: list[AgencyWorkflowResponse]
