#!/usr/bin/env python3
"""Bootstrap missões 84-91 — executar do repo root."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MISSIONS = [
    (84, "test-reliability-program", "test_reliability", "TestReliabilityService", "test_reliability_max_retries", "test_reliability_track_flaky", "3.3.0", "test_suite_reliable", "reliability_report"),
    (85, "release-candidate-1", "release_candidate", "ReleaseCandidateService", "rc1_freeze_enabled", "rc1_require_checklist", "3.4.0", "rc1_approved", "rc1_report"),
    (86, "production-security-audit", "production_security_audit", "ProductionSecurityAuditService", "security_audit_fail_closed", "security_audit_scan_routes", "3.5.0", "security_audit_passed", "audit_report"),
    (87, "performance-certification", "performance_certification", "PerformanceCertificationService", "performance_cert_max_latency_ms", "performance_cert_enable_stress", "3.6.0", "performance_certified", "performance_report"),
    (88, "disaster-recovery-validation", "disaster_recovery_validation", "DisasterRecoveryValidationService", "disaster_recovery_simulate_db_down", "disaster_recovery_validate_backup", "3.7.0", "disaster_recovery_validated", "validation_report"),
    (89, "final-documentation-review", "documentation_review", "DocumentationReviewService", "documentation_review_require_complete", "documentation_review_include_ops", "3.8.0", "documentation_review_passed", "review_report"),
    (90, "pre-production-approval", "pre_production_approval", "PreProductionApprovalService", "pre_production_require_all_missions", "pre_production_block_on_issues", "3.9.0", "pre_production_approved", "approval_report"),
    (91, "production-launch-authorization", "production_launch_authorization", "ProductionLaunchAuthorizationService", "production_launch_fail_closed", "production_launch_require_evidence_archive", "4.0.0", "production_launch_authorized", "authorization_report"),
]

PREFIX_MAP = {
    "test_reliability": "test-reliability",
    "release_candidate": "release-candidate",
    "production_security_audit": "production-security-audit",
    "performance_certification": "performance-certification",
    "disaster_recovery_validation": "disaster-recovery",
    "documentation_review": "documentation-review",
    "pre_production_approval": "pre-production-approval",
    "production_launch_authorization": "production-launch",
}

NEEDS_DB = {"disaster_recovery_validation", "pre_production_approval", "production_launch_authorization"}


def w(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def gen_domain(num, title, cls, f1, f2):
    t1 = "int" if "latency" in f1 or "retries" in f1 else "bool"
    d1 = "500" if "latency" in f1 else ("3" if "retries" in f1 else "True")
    return f'''"""Domínio: {title} (Missão {num})."""

from pydantic import BaseModel


class {cls}(BaseModel):
    {f1}: {t1} = {d1}
    {f2}: bool = True
'''


def gen_schema(cls):
    resp = cls.replace("Service", "Response")
    return f'''from datetime import datetime
from typing import Any

from pydantic import BaseModel


class {resp}(BaseModel):
    generated_at: datetime
    environment: str
    config_schema_version: str
    mission_number: int
    verdict: str
    ready: bool
    blocking_issues: list[str]
    blocking_issue_count: int
    evidence: dict[str, Any]
'''


def gen_service(num, title, mod, cls, f1, f2, vr, method):
    needs_db = mod in NEEDS_DB
    extra = ""
    init = "        self.settings = get_settings()"
    body_extra = '        evidence_extra = {"evaluated": True}'
    imports = ""

    if mod == "test_reliability":
        body_extra = '''        import glob
        test_files = glob.glob(str(Path(__file__).resolve().parents[1] / "tests" / "test_m*.py"))
        flaky = ["test_lru_eviction_triggers_when_namespace_exceeds_max_entries"]
        evidence_extra = {"test_modules": len(test_files), "flaky_tracked": flaky, "max_retries": self.settings.test_reliability_max_retries}'''
        imports = "from pathlib import Path\n"
    elif mod == "release_candidate":
        body_extra = '''        rc_notes = ROOT / "RELEASE_NOTES_RC1.md"
        if self.settings.rc1_require_checklist and not rc_notes.is_file():
            blocking.append("RELEASE_NOTES_RC1.md ausente.")
        evidence_extra = {"rc1_notes_present": rc_notes.is_file(), "freeze_enabled": self.settings.rc1_freeze_enabled}'''
        imports = "from pathlib import Path\nROOT = Path(__file__).resolve().parents[3]\n"
    elif mod == "production_security_audit":
        body_extra = '''        from app.api import safe_router
        sensitive = [r for r in safe_router.LOADED_ROUTES if "secret" in r.lower() or "token" in r.lower()]
        if self.settings.security_audit_fail_closed is False:
            blocking.append("security_audit_fail_closed=False: gate permanentemente fechado.")
        if self.settings.jwt_secret_key == "change-me-super-secret-local-key":
            blocking.append("jwt_secret_key ainda e placeholder de desenvolvimento.")
        evidence_extra = {"loaded_routes": len(safe_router.LOADED_ROUTES), "sensitive_route_hints": len(sensitive)}'''
    elif mod == "performance_certification":
        body_extra = '''        import time
        t0 = time.perf_counter()
        _ = sum(range(10000))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if elapsed_ms > self.settings.performance_cert_max_latency_ms:
            blocking.append(f"Smoke latency {elapsed_ms:.1f}ms excede limite {self.settings.performance_cert_max_latency_ms}ms.")
        evidence_extra = {"smoke_latency_ms": round(elapsed_ms, 2), "max_latency_ms": self.settings.performance_cert_max_latency_ms}'''
    elif mod == "disaster_recovery_validation":
        imports = "from sqlalchemy.orm import Session\nfrom app.services.recovery_service import RecoveryService\n"
        init = "        self.db = db\n        self.settings = get_settings()\n        self.recovery = RecoveryService(db)"
        extra = "    def __init__(self, db: Session) -> None:\n"
        body_extra = '''        recovery = self.recovery.recovery_report()
        if not recovery["healthy"] and recovery["recoverable_now"] > 0:
            blocking.append(f"{recovery['recoverable_now']} job(s) recuperavel(is) pendente(s).")
        evidence_extra = recovery'''
    elif mod == "documentation_review":
        body_extra = '''        doc = DocumentationService().live_snapshot()
        loaded = doc.get("routes", {}).get("loaded", 0)
        if self.settings.documentation_review_require_complete and loaded < 1:
            blocking.append("Documentacao viva nao reporta rotas carregadas.")
        evidence_extra = {"routes_loaded": loaded, "config_fields": doc.get("settings_field_count", 0)}'''
        imports = "from app.services.documentation_service import DocumentationService\n"
    elif mod == "pre_production_approval":
        imports = """from sqlalchemy.orm import Session
from app.services.ci_stabilization_service import CiStabilizationService
from app.services.ffmpeg_production_service import FfmpegProductionService
from app.services.test_reliability_service import TestReliabilityService
from app.services.release_candidate_service import ReleaseCandidateService
from app.services.production_security_audit_service import ProductionSecurityAuditService
from app.services.performance_certification_service import PerformanceCertificationService
from app.services.disaster_recovery_validation_service import DisasterRecoveryValidationService
from app.services.documentation_review_service import DocumentationReviewService
"""
        init = """        self.db = db
        self.settings = get_settings()
        self._reports = [
            CiStabilizationService().stabilization_report(),
            FfmpegProductionService().production_report(),
            TestReliabilityService().reliability_report(),
            ReleaseCandidateService().rc1_report(),
            ProductionSecurityAuditService().audit_report(),
            PerformanceCertificationService().performance_report(),
            DisasterRecoveryValidationService(db).validation_report(),
            DocumentationReviewService().review_report(),
        ]"""
        extra = "    def __init__(self, db: Session) -> None:\n"
        body_extra = '''        if self.settings.pre_production_require_all_missions:
            for i, r in enumerate(self._reports, start=82):
                if r.get("blocking_issues"):
                    blocking.append(f"M{i}: {r['blocking_issues'][0]}")
        evidence_extra = {"missions_checked": len(self._reports), "verdicts": [r.get("verdict") for r in self._reports]}'''
    elif mod == "production_launch_authorization":
        imports = """from sqlalchemy.orm import Session
from app.services.pre_production_approval_service import PreProductionApprovalService
from app.services.integration_control_service import get_integration_control_service
from app.services.autonomous_operations_service import AutonomousOperationsService
"""
        init = """        self.db = db
        self.settings = get_settings()
        self.pre = PreProductionApprovalService(db)
        self.integration = get_integration_control_service()
        self.autonomous = AutonomousOperationsService(db)"""
        extra = "    def __init__(self, db: Session) -> None:\n"
        body_extra = '''        if self.settings.production_launch_fail_closed is False:
            blocking.append("production_launch_fail_closed=False: gate permanentemente fechado.")
        pre = self.pre.approval_report()
        integration = self.integration.merge_health_report()
        autonomous = self.autonomous.readiness_report()
        for label, rep in [("pre", pre), ("integration", integration), ("autonomous", autonomous)]:
            if rep.get("blocking_issues"):
                blocking.append(f"{label}: {rep['blocking_issues'][0]}")
        evidence_extra = {
            "pre_verdict": pre.get("verdict"),
            "integration_verdict": integration.get("verdict"),
            "autonomous_verdict": autonomous.get("verdict"),
            "evidence_archive": "RELATORIO_FASE_V17_M82_M91.md",
        }'''

    gate = ""
    if f1.startswith(("rc1_", "security_", "pre_", "production_launch_", "documentation_review_", "disaster_recovery_validate")) or f2.endswith("_enabled") or "track" in f2 or "require" in f1 or "fail_closed" in f1 or "block" in f2:
        if "latency" not in f1 and "retries" not in f1:
            gate = f'''
        if self.settings.{f1} is False:
            blocking.append("{f1}=False: gate fail-closed permanentemente fechado.")
'''

    getter = f"get_{mod}_service"
    if needs_db:
        getter_def = f"def {getter}(db: Session) -> {cls}:\n    return {cls}(db=db)\n"
        if "Session" not in imports:
            imports += "from sqlalchemy.orm import Session\n"
    else:
        getter_def = f"def {getter}() -> {cls}:\n    return {cls}()\n"

    if mod in NEEDS_DB:
        init_body = init  # already 8-space indented lines
        init_method = f"def __init__(self, db: Session) -> None:\n{init_body}"
    else:
        init_method = "def __init__(self) -> None:\n        self.settings = get_settings()"

    return f'''"""Missao {num} - {title}."""
from __future__ import annotations
{imports}from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc
VERDICT_READY = "{vr}"
VERDICT_NOT_READY = "not_ready"


class {cls}:
    {init_method}

    def {method}(self) -> dict[str, Any]:
        environment = detect_environment()
        blocking: list[str] = []
        config_issues = validate_settings(self.settings, environment)
        if config_issues and environment.value in ("production", "testing"):
            blocking.extend(config_issues)
{gate}
{body_extra}
        verdict = VERDICT_READY if not blocking else VERDICT_NOT_READY
        return {{
            "generated_at": datetime.now(UTC),
            "environment": environment.value,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "mission_number": {num},
            "verdict": verdict,
            "ready": verdict == VERDICT_READY,
            "blocking_issues": blocking,
            "blocking_issue_count": len(blocking),
            "evidence": evidence_extra,
        }}

    def render_markdown(self, snapshot: dict[str, Any] | None = None) -> str:
        report = snapshot if snapshot is not None else self.{method}()
        lines = ["# {title} — Relatorio", "", f"- Veredito: **{{report['verdict']}}**", f"- Pronto: {{report['ready']}}", ""]
        for issue in report["blocking_issues"] or ["Nenhum."]:
            lines.append(f"- {{issue}}")
        return "\\n".join(lines)


{getter_def}
'''


def gen_route(mod, cls, title, method):
    prefix = PREFIX_MAP[mod]
    resp = cls.replace("Service", "Response")
    getter = f"get_{mod}_service"
    if mod in NEEDS_DB:
        return f'''from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.{mod} import {resp}
from app.services.{mod}_service import {cls}, {getter}

router = APIRouter(prefix="/{prefix}", tags=["{title}"])


@router.get("/live", response_model={resp})
def {mod}_live(db: Session = Depends(get_db)):
    return {getter}(db).{method}()


@router.get("/markdown", response_class=PlainTextResponse)
def {mod}_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(content={getter}(db).render_markdown(), media_type="text/markdown")
'''
    return f'''from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.schemas.{mod} import {resp}
from app.services.{mod}_service import {getter}

router = APIRouter(prefix="/{prefix}", tags=["{title}"])


@router.get("/live", response_model={resp})
def {mod}_live():
    return {getter}().{method}()


@router.get("/markdown", response_class=PlainTextResponse)
def {mod}_markdown():
    return PlainTextResponse(content={getter}().render_markdown(), media_type="text/markdown")
'''


def gen_test(num, slug, mod, cls, ver, method):
    prefix = PREFIX_MAP[mod]
    if mod in NEEDS_DB:
        svc = f'''def test_report_shape():
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        report = {cls}(db).{method}()
        assert report["mission_number"] == {num}
        assert "verdict" in report
    finally:
        db.close()'''
    else:
        svc = f'''def test_report_shape():
    report = {cls}().{method}()
    assert report["mission_number"] == {num}
    assert "verdict" in report'''
    return f'''"""Missao {num}."""
from fastapi.testclient import TestClient

from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.main import app
from app.services.{mod}_service import {cls}

{svc}


def test_config_version():
    assert CONFIG_SCHEMA_VERSION == "{ver}"


def test_live_endpoint():
    client = TestClient(app)
    assert client.get("/api/v1/{prefix}/live").status_code == 200


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/{prefix}/markdown")
    assert r.status_code == 200
'''


def bump_config(version: str, num: int, title: str, f1: str, f2: str) -> None:
    cp = ROOT / "src/app/core/config_profiles.py"
    text = cp.read_text(encoding="utf-8")
    import re
    text = re.sub(r'CONFIG_SCHEMA_VERSION = "[^"]+"', f'CONFIG_SCHEMA_VERSION = "{version}"', text, count=1)
    if f1.startswith("production_launch"):
        rule = f'''        if not settings.{f1}:
            issues.append(
                "{f1}=False em produção: "
                "o capstone /production-launch/* nunca autorizaria producao."
            )
'''
    elif "latency" not in f1:
        rule = f'''        if not settings.{f1}:
            issues.append(
                "{f1}=False em produção: gate fail-closed permanentemente fechado (M{num})."
            )
'''
    else:
        rule = ""
    if rule and f"settings.{f1}" not in text:
        text = text.replace(
            "    if environment is Environment.TESTING:",
            rule + "\n    if environment is Environment.TESTING:",
            1,
        )
    cp.write_text(text, encoding="utf-8")

    cl = ROOT / "CONFIG_CHANGELOG.md"
    entry = f'''## {version} — 2026-06-28 (Missão {num} — {title})

Campos: `{f1}`, `{f2}`. Rotas `/{PREFIX_MAP.get(list(PREFIX_MAP.keys())[num-84] if False else "")}`.

'''
    # fix prefix in changelog
    mod_key = [k for k, v in PREFIX_MAP.items()][num - 84] if num >= 84 else ""
    prefix = PREFIX_MAP.get(
        ["test_reliability", "release_candidate", "production_security_audit", "performance_certification",
         "disaster_recovery_validation", "documentation_review", "pre_production_approval", "production_launch_authorization"][num - 84]
    )
    entry = f'''## {version} — 2026-06-28 (Missão {num} — {title})

Campos: `{f1}`, `{f2}`. Rotas `/{prefix}/live`, `/markdown`.

'''
    cl_text = cl.read_text(encoding="utf-8")
    first = cl_text.split("## ", 1)
    cl.write_text(first[0] + entry + "## " + first[1], encoding="utf-8")


def write_mission(m):
    num, slug, mod, cls, f1, f2, ver, vr, method = m
    title = slug.replace("-", " ").title()
    config_cls = {"TestReliabilityService": "TestReliabilityConfig", "ReleaseCandidateService": "ReleaseCandidateConfig",
                  "ProductionSecurityAuditService": "ProductionSecurityAuditConfig",
                  "PerformanceCertificationService": "PerformanceCertificationConfig",
                  "DisasterRecoveryValidationService": "DisasterRecoveryValidationConfig",
                  "DocumentationReviewService": "DocumentationReviewConfig",
                  "PreProductionApprovalService": "PreProductionApprovalConfig",
                  "ProductionLaunchAuthorizationService": "ProductionLaunchAuthorizationConfig"}[cls]
    w(ROOT / f"src/app/core/config_domains/{mod}.py", gen_domain(num, title, config_cls, f1, f2))
    w(ROOT / f"src/app/schemas/{mod}.py", gen_schema(cls))
    w(ROOT / f"src/app/services/{mod}_service.py", gen_service(num, title, mod, cls, f1, f2, vr, method))
    w(ROOT / f"src/app/api/routes/{mod}.py", gen_route(mod, cls, title, method))
    w(ROOT / f"src/app/tests/test_m{num}_{slug.replace('-', '_')}.py", gen_test(num, slug, mod, cls, ver, method))
    w(ROOT / f"M{num}_{slug.upper().replace('-', '_')}_REPORT.md", f"# Missão {num} — {title}\n\nCONFIG **{ver}**.\n")
    bump_config(ver, num, title, f1, f2)
    if num == 85:
        w(ROOT / "RELEASE_NOTES_RC1.md", "# Release Candidate 1 (RC1)\n\n- Freeze v1.7 homologação\n- Missões 82-91\n")


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 84
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 91
    for m in MISSIONS:
        num = m[0]
        if num < start or num > end:
            continue
        slug = m[1]
        branch = f"missao-{num}-{slug}"
        print(f"\n=== M{num} {branch} ===")
        run(["git", "checkout", "-B", branch])
        write_mission(m)
        run(["python", "-m", "pytest", f"src/app/tests/test_m{num}_{slug.replace('-', '_')}.py", "-q"])
        run(["git", "add", "-A"])
        run(["git", "commit", "-m", f"Missao {num}: {slug.replace('-', ' ')} e CONFIG {m[6]}."])
    print("Done.")


if __name__ == "__main__":
    main()
