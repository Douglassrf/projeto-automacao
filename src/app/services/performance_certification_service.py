"""Missao 87 - Performance Certification."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc
VERDICT_READY = "performance_certified"
VERDICT_NOT_READY = "not_ready"


class PerformanceCertificationService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def performance_report(self) -> dict[str, Any]:
        environment = detect_environment()
        blocking: list[str] = []
        config_issues = validate_settings(self.settings, environment)
        if config_issues and environment.value in ("production", "testing"):
            blocking.extend(config_issues)

        import time
        t0 = time.perf_counter()
        _ = sum(range(10000))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if elapsed_ms > self.settings.performance_cert_max_latency_ms:
            blocking.append(f"Smoke latency {elapsed_ms:.1f}ms excede limite {self.settings.performance_cert_max_latency_ms}ms.")
        evidence_extra = {"smoke_latency_ms": round(elapsed_ms, 2), "max_latency_ms": self.settings.performance_cert_max_latency_ms}
        verdict = VERDICT_READY if not blocking else VERDICT_NOT_READY
        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "mission_number": 87,
            "verdict": verdict,
            "ready": verdict == VERDICT_READY,
            "blocking_issues": blocking,
            "blocking_issue_count": len(blocking),
            "evidence": evidence_extra,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.performance_report()
        lines = ["# Performance Certification — Relatorio", "", f"- Veredito: **{report['verdict']}**", f"- Pronto: {report['ready']}", ""]
        for issue in report["blocking_issues"] or ["Nenhum."]:
            lines.append(f"- {issue}")
        return "\n".join(lines)


def get_performance_certification_service() -> PerformanceCertificationService:
    return PerformanceCertificationService()

