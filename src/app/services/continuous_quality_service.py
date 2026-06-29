from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings
from app.services.dependency_audit_service import DependencyAuditService

UTC = timezone.utc
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_TESTS_DIR = _PROJECT_ROOT / "src" / "app" / "tests"
_SERVICES_DIR = _PROJECT_ROOT / "src" / "app" / "services"


class ContinuousQualityService:
    """Missao 74 - Continuous Quality Gate.

    Cobertura de testes (contagem de arquivos), indicadores de divida
    tecnica, verificacao de padroes de codigo e relatorio consolidado por
    release. Reutiliza DependencyAuditService (M49) para divida de deps.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.dependency_audit = DependencyAuditService()

    def _test_coverage_indicators(self) -> dict[str, Any]:
        mission_tests = sorted(_TESTS_DIR.glob("test_m*.py"))
        all_tests = sorted(_TESTS_DIR.glob("test_*.py"))
        return {
            "mission_test_files": len(mission_tests),
            "total_test_files": len(all_tests),
            "mission_test_file_names": [p.name for p in mission_tests],
        }

    def _technical_debt_indicators(self) -> dict[str, Any]:
        audit = self.dependency_audit.audit()
        service_files = list(_SERVICES_DIR.glob("*_service.py"))
        unpinned_ratio = (
            audit["unpinned_count"] / max(audit["total_declared"], 1)
        )
        return {
            "unpinned_dependencies": audit["unpinned_count"],
            "missing_dependencies": audit["missing_count"],
            "version_mismatches": audit["version_mismatch_count"],
            "unpinned_ratio": round(unpinned_ratio, 2),
            "service_module_count": len(service_files),
            "debt_score": round(
                audit["unpinned_count"] * 0.5
                + audit["missing_count"] * 10
                + audit["version_mismatch_count"] * 5,
                1,
            ),
        }

    def _code_pattern_checks(self) -> list[dict[str, str]]:
        checks: list[dict[str, str]] = []
        for service_path in sorted(_SERVICES_DIR.glob("*_service.py"))[:20]:
            content = service_path.read_text(encoding="utf-8", errors="ignore")
            has_docstring = '"""' in content[:500]
            has_future = "from __future__ import annotations" in content
            status = "ok" if has_docstring and has_future else "warning"
            if self.settings.quality_gate_enforce_standards and not has_future:
                status = "fail"
            checks.append(
                {
                    "file": service_path.name,
                    "has_module_docstring": str(has_docstring),
                    "has_future_annotations": str(has_future),
                    "status": status,
                }
            )
        return checks

    def _release_report(
        self,
        *,
        coverage: dict[str, Any],
        debt: dict[str, Any],
        patterns: list[dict[str, str]],
    ) -> dict[str, Any]:
        pattern_failures = sum(1 for p in patterns if p["status"] == "fail")
        gate_passed = (
            coverage["mission_test_files"] >= 1
            and debt["missing_dependencies"] == 0
            and pattern_failures == 0
        )
        if self.settings.quality_gate_enforce_standards and pattern_failures > 0:
            gate_passed = False
        return {
            "gate_passed": gate_passed,
            "pattern_failures": pattern_failures,
            "release_ready": gate_passed and debt["version_mismatches"] == 0,
        }

    def quality_report(self) -> dict[str, Any]:
        environment = detect_environment()
        config_validation_issues = validate_settings(self.settings, environment)
        coverage = self._test_coverage_indicators()
        debt = self._technical_debt_indicators()
        patterns = self._code_pattern_checks()
        release = self._release_report(coverage=coverage, debt=debt, patterns=patterns)

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "enforce_standards": self.settings.quality_gate_enforce_standards,
            "test_coverage": coverage,
            "technical_debt": debt,
            "code_pattern_checks": patterns,
            "release_report": release,
            "config_validation_issues": config_validation_issues,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.quality_report()
        lines = [
            "# Continuous Quality Gate",
            "",
            f"- Gerado em: {report['generated_at']}",
            f"- Gate: {'APROVADO' if report['release_report']['gate_passed'] else 'REPROVADO'}",
            "",
            "## Cobertura de testes",
            f"- Arquivos de teste de missao: {report['test_coverage']['mission_test_files']}",
            f"- Total arquivos de teste: {report['test_coverage']['total_test_files']}",
            "",
            "## Divida tecnica",
            f"- Score: {report['technical_debt']['debt_score']}",
            f"- Deps sem pin: {report['technical_debt']['unpinned_dependencies']}",
            "",
            "## Release",
            f"- Release ready: {report['release_report']['release_ready']}",
            "",
        ]
        return "\n".join(lines)
