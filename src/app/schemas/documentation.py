from datetime import datetime

from pydantic import BaseModel


class RouteSummaryResponse(BaseModel):
    declared: int
    loaded: int
    failed: int
    loaded_modules: list[str]
    failed_details: list[dict]


class SettingsFieldInfo(BaseModel):
    name: str
    type: str
    secret: bool
    configured: bool
    value: str | None


class DocumentationSnapshotResponse(BaseModel):
    generated_at: datetime
    version_file: str | None
    config_schema_version: str
    environment: str
    routes: RouteSummaryResponse
    settings_field_count: int
    settings_issues: list[str]
    settings_fields: list[SettingsFieldInfo]
