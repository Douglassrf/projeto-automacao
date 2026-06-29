"""Missao 83 - FFmpeg Production Layer."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc
VERDICT_READY = "ffmpeg_production_ready"
VERDICT_NOT_READY = "not_ready"


class FfmpegProductionService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _detect_ffmpeg(self) -> tuple[bool, str | None]:
        path = shutil.which("ffmpeg")
        return path is not None, path

    def production_report(self) -> dict[str, Any]:
        environment = detect_environment()
        blocking: list[str] = []
        ffmpeg_ok, ffmpeg_path = self._detect_ffmpeg()

        if self.settings.ffmpeg_require_binary and not ffmpeg_ok:
            if not self.settings.ffmpeg_fallback_when_absent:
                blocking.append("ffmpeg ausente e fallback desabilitado.")
            else:
                blocking.append(
                    "ffmpeg ausente com require_binary=True (fallback ativo mas nao certifica producao)."
                )

        verdict = VERDICT_READY if not blocking else VERDICT_NOT_READY
        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "mission_number": 83,
            "verdict": verdict,
            "ready": verdict == VERDICT_READY,
            "blocking_issues": blocking,
            "blocking_issue_count": len(blocking),
            "ffmpeg_available": ffmpeg_ok,
            "ffmpeg_path": ffmpeg_path,
            "fallback_enabled": self.settings.ffmpeg_fallback_when_absent,
            "evidence": {
                "require_binary": self.settings.ffmpeg_require_binary,
                "install_hint": "apt-get install ffmpeg (Linux) ou choco install ffmpeg (Windows)",
            },
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.production_report()
        lines = [
            "# FFmpeg Production Layer — Relatorio",
            "",
            f"- Veredito: **{report['verdict']}**",
            f"- ffmpeg disponivel: {report['ffmpeg_available']}",
            f"- path: {report['ffmpeg_path']}",
            "",
            "## Blocking issues",
        ]
        for issue in report["blocking_issues"] or ["Nenhum."]:
            lines.append(f"- {issue}")
        return "\n".join(lines)


def get_ffmpeg_production_service() -> FfmpegProductionService:
    return FfmpegProductionService()
