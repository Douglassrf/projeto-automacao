from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FinalReadinessFullResponse(BaseModel):
    generated_at: datetime
    missions: list[int]
    sections: dict[str, Any]
    final_decision: str
    production_ready: bool
