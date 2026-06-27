from datetime import datetime

from pydantic import BaseModel

from app.schemas.queue import QueueJobResponse


class RecoveryReportResponse(BaseModel):
    healthy: bool
    recoverable_now: int
    requires_external_action: int
    warnings: list[str]


class RecoverySweepResponse(BaseModel):
    swept_at: datetime
    lock_timeout_seconds: int
    found: int
    recovered_to_retry: list[QueueJobResponse]
    recovered_to_dead: list[QueueJobResponse]
    more_pending: bool
