from datetime import datetime

from pydantic import BaseModel


class DependencyEntry(BaseModel):
    name: str | None
    declared: str
    pinned: bool
    pinned_version: str | None
    installed_version: str | None
    missing: bool
    version_mismatch: bool


class DependencyAuditResponse(BaseModel):
    generated_at: datetime
    requirements_file: str
    environment: str
    total_declared: int
    pinned_count: int
    unpinned_count: int
    missing_count: int
    version_mismatch_count: int
    issues: list[str]
    dependencies: list[DependencyEntry]
