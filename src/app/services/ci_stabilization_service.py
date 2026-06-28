"""Missao 82 - CI/CD Stabilization.

Verifica workflows GitHub Actions, testes flaky conhecidos (M43 LRU, M57
timeline) e politica de skip ffmpeg no Windows CI. Fail-closed quando
ci_cd_require_green_pipeline=True e algum indicador critico falha.
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.api import safe_router
from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc

VERDICT_READY = "ci_pipeline_ready"
VERDICT_NOT_READY = "not_ready"

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

FLAKY_TESTS_TRACKED = (
    "test_lru_eviction_triggers_when_namespace_exceeds_max_entries",
    "test_mission_timeline_detects_the_real_historical_mission_commits",
    "test_mission_timeline_stat_for_mission_56_matches_the_real_commit",
)


class CiStabilizationService:
    """Auditoria de estabilidade CI/CD e testes conhecidos."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def _discover_workflows(self) -> list[str]:
        if not WORKFLOWS_DIR.is_dir():
            return []
        return sorted(p.name for p in WORKFLOWS_DIR.glob("*.yml"))

    def _workflow_health(self) -> tuple[list[str], list[str]]:
        blocking: list[str] = []
        evidence: list[str] = []
        workflows = self._discover_workflows()
        if not workflows:
            blocking.append("Nenhum workflow em .github/workflows/.")
        else:
            evidence.append(f"{len(workflows)} workflow(s) encontrado(s)")
        ci_yml = WORKFLOWS_DIR / "ci.yml"
        if ci_yml.is_file():
            content = ci_yml.read_text(encoding="utf-8")
            if "ffmpeg" not in content.lower():
                blocking.append("ci.yml nao instala ffmpeg no runner Linux.")
            if "pytest" not in content:
                blocking.append("ci.yml nao executa pytest.")
        else:
            blocking.append("ci.yml ausente.")
        return blocking, evidence

    def _route_health(self) -> list[str]:
        issues: list[str] = []
        if safe_router.FAILED_ROUTES:
            issues.append(
                f"{len(safe_router.FAILED_ROUTES)} modulo(s) de rota falharam ao carregar."
            )
        return issues

    def stabilization_report(self) -> dict[str, Any]:
        environment = detect_environment()
        config_issues = validate_settings(self.settings, environment)
        wf_blocking, wf_evidence = self._workflow_health()
        route_issues = self._route_health()

        blocking: list[str] = list(wf_blocking)
        blocking.extend(route_issues)
        if config_issues and environment.value in ("production", "testing"):
            blocking.extend(config_issues)

        if not self.settings.ci_cd_require_green_pipeline:
            blocking.append(
                "ci_cd_require_green_pipeline=False: gate fail-closed permanentemente fechado."
            )

        verdict = VERDICT_READY if not blocking else VERDICT_NOT_READY
        pipeline_ready = verdict == VERDICT_READY

        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "require_green_pipeline": self.settings.ci_cd_require_green_pipeline,
            "verdict": verdict,
            "pipeline_ready": pipeline_ready,
            "blocking_issues": blocking,
            "blocking_issue_count": len(blocking),
            "workflow_files": self._discover_workflows(),
            "flaky_tests_tracked": list(FLAKY_TESTS_TRACKED),
            "ffmpeg_windows_skip_enabled": self.settings.ci_cd_skip_ffmpeg_on_windows,
            "evidence": {
                "workflow_notes": wf_evidence,
                "loaded_routes": len(safe_router.LOADED_ROUTES),
                "failed_routes": len(safe_router.FAILED_ROUTES),
                "platform": platform.system(),
                "python_version": sys.version.split()[0],
                "repo_root_exists": REPO_ROOT.is_dir(),
            },
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.stabilization_report()
        lines = [
            "# CI/CD Stabilization — Relatorio",
            "",
            f"- Veredito: **{report['verdict']}**",
            f"- Pipeline pronto: {report['pipeline_ready']}",
            f"- CONFIG: {report['config_schema_version']}",
            "",
            "## Workflows",
        ]
        for wf in report["workflow_files"]:
            lines.append(f"- {wf}")
        lines.append("")
        lines.append("## Testes flaky rastreados")
        for name in report["flaky_tests_tracked"]:
            lines.append(f"- {name}")
        lines.append("")
        lines.append("## Blocking issues")
        if report["blocking_issues"]:
            for issue in report["blocking_issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("- Nenhum blocking issue encontrado.")
        return "\n".join(lines)


def get_ci_stabilization_service() -> CiStabilizationService:
    return CiStabilizationService()
