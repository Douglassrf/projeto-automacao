"""Missao 85 - Release Candidate 1."""
from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc
VERDICT_READY = "rc1_approved"
VERDICT_NOT_READY = "not_ready"


class ReleaseCandidateService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def rc1_report(self) -> dict[str, Any]:
        environment = detect_environment()
        blocking: list[str] = []
        config_issues = validate_settings(self.settings, environment)
        if config_issues and environment.value in ("production", "testing"):
            blocking.extend(config_issues)

        if self.settings.rc1_freeze_enabled is False:
            blocking.append("rc1_freeze_enabled=False: gate fail-closed permanentemente fechado.")

        rc_notes = ROOT / "RELEASE_NOTES_RC1.md"
        if self.settings.rc1_require_checklist and not rc_notes.is_file():
            blocking.append("RELEASE_NOTES_RC1.md ausente.")
        evidence_extra = {"rc1_notes_present": rc_notes.is_file(), "freeze_enabled": self.settings.rc1_freeze_enabled}
        verdict = VERDICT_READY if not blocking else VERDICT_NOT_READY
        return {
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "mission_number": 85,
            "verdict": verdict,
            "ready": verdict == VERDICT_READY,
            "blocking_issues": blocking,
            "blocking_issue_count": len(blocking),
            "evidence": evidence_extra,
        }

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.rc1_report()
        lines = ["# Release Candidate 1 — Relatorio", "", f"- Veredito: **{report['verdict']}**", f"- Pronto: {report['ready']}", ""]
        for issue in report["blocking_issues"] or ["Nenhum."]:
            lines.append(f"- {issue}")
        return "\n".join(lines)


def get_release_candidate_service() -> ReleaseCandidateService:
    return ReleaseCandidateService()

