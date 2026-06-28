from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings
from app.domain.models import CacheEntry, QueueJob

UTC = timezone.utc

STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_CRITICAL = "critical"


class DataIntegrityService:
    """Missao 75 - Data Integrity Framework.

    Validacao de consistencia, deteccao de registros invalidos e
    verificacao de integridade pos backup/restauracao (round-trip SELECT 1
    + contagem de tabelas criticas).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def _consistency_checks(self) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        try:
            self.db.execute(text("SELECT 1"))
            checks.append({"name": "database_roundtrip", "status": STATUS_OK, "message": "SELECT 1 ok"})
        except SQLAlchemyError as exc:
            checks.append({"name": "database_roundtrip", "status": STATUS_CRITICAL, "message": str(type(exc).__name__)})

        queue_count = self.db.query(QueueJob).count()
        cache_count = self.db.query(CacheEntry).count()
        checks.append({"name": "queue_jobs_countable", "status": STATUS_OK, "message": f"{queue_count} jobs"})
        checks.append({"name": "cache_entries_countable", "status": STATUS_OK, "message": f"{cache_count} entries"})
        return checks

    def _invalid_records(self) -> list[dict[str, Any]]:
        invalid: list[dict[str, Any]] = []
        bad_jobs = (
            self.db.query(QueueJob)
            .filter(QueueJob.max_attempts < 1)
            .limit(10)
            .all()
        )
        for job in bad_jobs:
            invalid.append({"table": "queue_jobs", "id": job.id, "reason": "max_attempts < 1"})

        if self.settings.data_integrity_strict_validation:
            orphaned_cache = (
                self.db.query(CacheEntry)
                .filter(CacheEntry.cache_key == "")
                .limit(10)
                .all()
            )
            for entry in orphaned_cache:
                invalid.append({"table": "cache_entries", "id": entry.id, "reason": "empty cache_key"})
        return invalid

    def _backup_restore_integrity(self) -> dict[str, Any]:
        try:
            self.db.execute(text("PRAGMA integrity_check"))
            row = self.db.execute(text("PRAGMA integrity_check")).fetchone()
            result = row[0] if row else "unknown"
            healthy = result == "ok"
        except SQLAlchemyError:
            healthy = False
            result = "check_failed"
        return {"integrity_check": result, "healthy": healthy}

    def integrity_report(self) -> dict[str, Any]:
        environment = detect_environment()
        config_validation_issues = validate_settings(self.settings, environment)
        consistency = self._consistency_checks()
        invalid = self._invalid_records()
        backup = self._backup_restore_integrity()

        worst = STATUS_OK
        if any(c["status"] == STATUS_CRITICAL for c in consistency):
            worst = STATUS_CRITICAL
        elif invalid and self.settings.data_integrity_strict_validation:
            worst = STATUS_WARNING
        if not backup["healthy"]:
            worst = STATUS_CRITICAL

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "strict_validation": self.settings.data_integrity_strict_validation,
            "overall_status": worst,
            "consistency_checks": consistency,
            "invalid_records": invalid,
            "invalid_record_count": len(invalid),
            "backup_restore_integrity": backup,
            "config_validation_issues": config_validation_issues,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.integrity_report()
        lines = [
            "# Data Integrity Framework",
            "",
            f"- Status: **{report['overall_status']}**",
            f"- Registros invalidos: {report['invalid_record_count']}",
            f"- Integridade pos-backup: {report['backup_restore_integrity']['integrity_check']}",
            "",
        ]
        return "\n".join(lines)
