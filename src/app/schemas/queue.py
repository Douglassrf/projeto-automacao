from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class QueueJobCreate(BaseModel):
    queue_name: str = Field(default="default", min_length=1, max_length=80)
    job_type: str = Field(..., min_length=1, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = 100
    max_attempts: int = 3


class QueueJobResponse(BaseModel):
    id: int
    queue_name: str
    job_type: str
    status: str
    priority: int
    attempts: int
    max_attempts: int
    payload: dict[str, Any]
    result: dict[str, Any]
    error_message: str
    locked_by: str
    locked_at: datetime | None
    next_attempt_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QueueClaimRequest(BaseModel):
    queue_name: str = "default"
    worker_id: str = "local-worker"
    limit: int = Field(default=1, ge=1, le=25)


class QueueCompleteRequest(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)


class QueueFailRequest(BaseModel):
    error_message: str
    retry: bool = True


class QueueStatsResponse(BaseModel):
    backend: str
    queued: int
    running: int
    done: int
    failed: int
    dead: int
    total: int
    recommendation: str
    healthy: bool
    warnings: list[str]


class QueueRequeueRequest(BaseModel):
    reset_attempts: bool = True


class QueueHealthResponse(BaseModel):
    healthy: bool
    stuck_jobs: list[QueueJobResponse]
    starving_jobs: list[QueueJobResponse]
    unhealthy_queues: list[str]
    per_queue: dict[str, dict[str, int]]
    warnings: list[str]
