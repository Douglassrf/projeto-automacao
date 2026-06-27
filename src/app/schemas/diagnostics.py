from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DiagnosticCheckResponse(BaseModel):
    name: str
    status: str
    message: str
    details: dict[str, Any]


class DiagnosticsReportResponse(BaseModel):
    status: str
    generated_at: datetime
    summary: dict[str, int]
    checks: list[DiagnosticCheckResponse]
