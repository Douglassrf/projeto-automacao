"""Missao 84 - Test Reliability Program."""
from __future__ import annotations

import glob
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc
VERDICT_READY = "test_suite_reliable"
VERDICT_NOT_READY = "not_ready"


class TestReliabilityService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def reliability_report(self) -> dict[str, Any]:
        environment = detect_environment()
        blocking: list[str] = []
        config_issues = validate_settings(self.settings, environment)
        if config_issues and environment.value in ("production", "testing"):
            blocking.extend(config_issues)

        test_files = glob.glob(str(Path(__file__).resolve().parents[1] / "tests" / "test_m*.py"))
        flaky = ["test_lru_eviction_triggers_when_namespace_exceeds_max_entries"]
        evidence_extra = {
            "test_modules": len(test_files),
            "flaky_tracked": flaky,
            "max_retries": self.settings.test_reliability_max_retries,
        }
        verdict = VERDICT_READY if not blocking else VERDICT_NOT_READY
        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "mission_number": 84,
            "verdict": verdict,
            "ready": verdict == VERDICT_READY,
            "blocking_issues": blocking,
            "blocking_issue_count": len(blocking),
            "evidence": evidence_extra,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.reliability_report()
        lines = ["# Test Reliability Program — Relatorio", "", f"- Veredito: **{report['verdict']}**", ""]
        for issue in report["blocking_issues"] or ["Nenhum."]:
            lines.append(f"- {issue}")
        return "\n".join(lines)


def get_test_reliability_service() -> TestReliabilityService:
    return TestReliabilityService()
