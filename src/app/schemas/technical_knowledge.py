from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TechnicalKnowledgeResponse(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    include_draft_adrs: bool
    include_draft_modules: bool
    module_catalog: list[dict[str, Any]]
    module_catalog_total: int
    architectural_decisions: list[dict[str, str]]
    lessons_learned: list[dict[str, str]]
    cross_references: list[dict[str, str]]
    routes_summary: dict[str, Any]
    documentation_field_count: int
    config_validation_issues: list[str]
