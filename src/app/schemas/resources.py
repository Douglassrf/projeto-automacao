from typing import Any

from pydantic import BaseModel


class DirectoryUsageEntry(BaseModel):
    path: str
    size_mb: float
    file_count: int


class DiskUsageReportResponse(BaseModel):
    total_size_mb: float
    directories: dict[str, DirectoryUsageEntry]


class CleanupResultResponse(BaseModel):
    queue_jobs_deleted: int
    queue_cutoff: str
    cache_entries_purged: int


class QueuePurgeResultResponse(BaseModel):
    deleted: int
    cutoff: str
    max_age_days: int
