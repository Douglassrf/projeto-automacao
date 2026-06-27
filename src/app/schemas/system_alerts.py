from datetime import datetime

from pydantic import BaseModel


class AlertEventResponse(BaseModel):
    id: int
    check_name: str
    severity: str
    message: str
    status: str
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None


class AlertEvaluationResponse(BaseModel):
    overall_status: str
    evaluated_at: datetime
    opened: list[str]
    updated: list[str]
    resolved: list[str]
