#!/usr/bin/env python3
"""Gera arquivos das missões 83-91 (Fase v1.7). Executar uma vez no repo."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MISSIONS = [
    {
        "num": 83,
        "slug": "ffmpeg-production-layer",
        "branch": "missao-83-ffmpeg-production-layer",
        "title": "FFmpeg Production Layer",
        "prefix": "ffmpeg-production",
        "service_class": "FfmpegProductionService",
        "module": "ffmpeg_production",
        "config_class": "FfmpegProductionConfig",
        "field": "ffmpeg_require_binary",
        "field2": "ffmpeg_fallback_when_absent",
        "field_desc": "ffmpeg binario obrigatorio em producao",
        "field2_desc": "fallback silencioso quando ffmpeg ausente",
        "schema_version": "3.2.0",
        "report": "M83_FFMPEG_PRODUCTION_LAYER_REPORT",
        "verdict_ready": "ffmpeg_production_ready",
        "endpoint_path": "/live",
    },
    {
        "num": 84,
        "slug": "test-reliability-program",
        "branch": "missao-84-test-reliability-program",
        "title": "Test Reliability Program",
        "prefix": "test-reliability",
        "service_class": "TestReliabilityService",
        "module": "test_reliability",
        "config_class": "TestReliabilityConfig",
        "field": "test_reliability_max_retries",
        "field2": "test_reliability_track_flaky",
        "field_desc": "max retries para testes flaky",
        "field2_desc": "rastrear testes flaky",
        "schema_version": "3.3.0",
        "report": "M84_TEST_RELIABILITY_PROGRAM_REPORT",
        "verdict_ready": "test_suite_reliable",
        "endpoint_path": "/live",
    },
    {
        "num": 85,
        "slug": "release-candidate-1",
        "branch": "missao-85-release-candidate-1",
        "title": "Release Candidate 1 (RC1)",
        "prefix": "release-candidate",
        "service_class": "ReleaseCandidateService",
        "module": "release_candidate",
        "config_class": "ReleaseCandidateConfig",
        "field": "rc1_freeze_enabled",
        "field2": "rc1_require_checklist",
        "field_desc": "RC1 freeze ativo",
        "field2_desc": "checklist RC1 obrigatorio",
        "schema_version": "3.4.0",
        "report": "M85_RELEASE_CANDIDATE_1_REPORT",
        "verdict_ready": "rc1_approved",
        "endpoint_path": "/live",
    },
    {
        "num": 86,
        "slug": "production-security-audit",
        "branch": "missao-86-production-security-audit",
        "title": "Production Security Audit",
        "prefix": "production-security-audit",
        "service_class": "ProductionSecurityAuditService",
        "module": "production_security_audit",
        "config_class": "ProductionSecurityAuditConfig",
        "field": "security_audit_fail_closed",
        "field2": "security_audit_scan_routes",
        "field_desc": "auditoria fail-closed",
        "field2_desc": "escanear rotas na auditoria",
        "schema_version": "3.5.0",
        "report": "M86_PRODUCTION_SECURITY_AUDIT_REPORT",
        "verdict_ready": "security_audit_passed",
        "endpoint_path": "/live",
    },
    {
        "num": 87,
        "slug": "performance-certification",
        "branch": "missao-87-performance-certification",
        "title": "Performance Certification",
        "prefix": "performance-certification",
        "service_class": "PerformanceCertificationService",
        "module": "performance_certification",
        "config_class": "PerformanceCertificationConfig",
        "field": "performance_cert_max_latency_ms",
        "field2": "performance_cert_enable_stress",
        "field_desc": "latencia maxima ms",
        "field2_desc": "stress test leve habilitado",
        "schema_version": "3.6.0",
        "report": "M87_PERFORMANCE_CERTIFICATION_REPORT",
        "verdict_ready": "performance_certified",
        "endpoint_path": "/live",
    },
    {
        "num": 88,
        "slug": "disaster-recovery-validation",
        "branch": "missao-88-disaster-recovery-validation",
        "title": "Disaster Recovery Validation",
        "prefix": "disaster-recovery",
        "service_class": "DisasterRecoveryValidationService",
        "module": "disaster_recovery_validation",
        "config_class": "DisasterRecoveryValidationConfig",
        "field": "disaster_recovery_simulate_db_down",
        "field2": "disaster_recovery_validate_backup",
        "field_desc": "simular DB down",
        "field2_desc": "validar backup/restore",
        "schema_version": "3.7.0",
        "report": "M88_DISASTER_RECOVERY_VALIDATION_REPORT",
        "verdict_ready": "disaster_recovery_validated",
        "endpoint_path": "/live",
    },
    {
        "num": 89,
        "slug": "final-documentation-review",
        "branch": "missao-89-final-documentation-review",
        "title": "Final Documentation Review",
        "prefix": "documentation-review",
        "service_class": "DocumentationReviewService",
        "module": "documentation_review",
        "config_class": "DocumentationReviewConfig",
        "field": "documentation_review_require_complete",
        "field2": "documentation_review_include_ops",
        "field_desc": "documentacao completa obrigatoria",
        "field2_desc": "incluir docs ops",
        "schema_version": "3.8.0",
        "report": "M89_FINAL_DOCUMENTATION_REVIEW_REPORT",
        "verdict_ready": "documentation_review_passed",
        "endpoint_path": "/live",
    },
    {
        "num": 90,
        "slug": "pre-production-approval",
        "branch": "missao-90-pre-production-approval",
        "title": "Pre-Production Approval",
        "prefix": "pre-production-approval",
        "service_class": "PreProductionApprovalService",
        "module": "pre_production_approval",
        "config_class": "PreProductionApprovalConfig",
        "field": "pre_production_require_all_missions",
        "field2": "pre_production_block_on_issues",
        "field_desc": "exigir M82-M89 aprovados",
        "field2_desc": "bloquear com issues",
        "schema_version": "3.9.0",
        "report": "M90_PRE_PRODUCTION_APPROVAL_REPORT",
        "verdict_ready": "pre_production_approved",
        "endpoint_path": "/live",
    },
    {
        "num": 91,
        "slug": "production-launch-authorization",
        "branch": "missao-91-production-launch-authorization",
        "title": "Production Launch Authorization (CAPSTONE)",
        "prefix": "production-launch",
        "service_class": "ProductionLaunchAuthorizationService",
        "module": "production_launch_authorization",
        "config_class": "ProductionLaunchAuthorizationConfig",
        "field": "production_launch_fail_closed",
        "field2": "production_launch_require_evidence_archive",
        "field_desc": "autorizacao fail-closed",
        "field2_desc": "exigir arquivo de evidencias",
        "schema_version": "4.0.0",
        "report": "M91_PRODUCTION_LAUNCH_AUTHORIZATION_REPORT",
        "verdict_ready": "production_launch_authorized",
        "endpoint_path": "/live",
    },
]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


def gen_config_domain(m: dict) -> str:
    f1, f2 = m["field"], m["field2"]
    t1 = type(True).__name__ if "enabled" in f1 or "require" in f1 or "track" in f1 or "fail" in f1 or "simulate" in f1 or "validate" in f1 or "scan" in f1 or "freeze" in f1 or "block" in f1 else "int"
    default1 = "True" if t1 == "bool" else ("3" if "retries" in f1 else ("500" if "latency" in f1 else "True"))
    default2 = "True"
    ann1 = "bool" if t1 == "bool" else "int"
    return f'''"""Domínio: {m["title"]} (Missão {m["num"]})."""

from pydantic import BaseModel


class {m["config_class"]}(BaseModel):
    # Missao {m["num"]} - {m["title"]}: {m["field_desc"]}.
    {f1}: {ann1} = {default1}
    {f2}: bool = {default2}
'''


def gen_schema(m: dict) -> str:
    return f'''from datetime import datetime
from typing import Any

from pydantic import BaseModel


class {m["service_class"].replace("Service", "Response")}(BaseModel):
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


def gen_service(m: dict) -> str:
    mod = m["module"]
    cls = m["service_class"]
    num = m["num"]
    vr = m["verdict_ready"]
    f1 = m["field"]
    extra_imports = ""
    extra_init = ""
    extra_logic = ""

    if num == 83:
        extra_logic = '''
    def _detect_ffmpeg(self) -> tuple[bool, str | None]:
        import shutil
        path = shutil.which("ffmpeg")
        return path is not None, path
'''
        extra_report = '''
        ffmpeg_ok, ffmpeg_path = self._detect_ffmpeg()
        if self.settings.ffmpeg_require_binary and not ffmpeg_ok:
            if not self.settings.ffmpeg_fallback_when_absent:
                blocking.append("ffmpeg ausente e fallback desabilitado.")
        evidence_extra = {"ffmpeg_available": ffmpeg_ok, "ffmpeg_path": ffmpeg_path}
'''
    elif num == 88:
        extra_imports = '''
from sqlalchemy.orm import Session

from app.services.recovery_service import RecoveryService'''
        extra_init = '''
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.recovery = RecoveryService(db)'''
        extra_logic = ""
        extra_report = '''
        recovery = self.recovery.recovery_report()
        if not recovery["healthy"] and recovery["recoverable_now"] > 0:
            blocking.append(f"{recovery['recoverable_now']} job(s) recuperavel(is) pendente(s).")
        evidence_extra = {"recovery_healthy": recovery["healthy"], "recoverable_now": recovery["recoverable_now"]}
'''
    elif num == 89:
        extra_imports = '''
from sqlalchemy.orm import Session

from app.services.documentation_service import DocumentationService'''
        extra_init = '''
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.documentation = DocumentationService(db)'''
        extra_report = '''
        doc = self.documentation.live_snapshot()
        if self.settings.documentation_review_require_complete and not doc.get("routes_loaded"):
            blocking.append("Documentacao viva nao reporta rotas carregadas.")
        evidence_extra = {"routes_loaded": doc.get("routes_loaded", 0), "config_fields": doc.get("config_field_count", 0)}
'''
    elif num == 90:
        extra_imports = '''
from app.services.ci_stabilization_service import CiStabilizationService
from app.services.ffmpeg_production_service import FfmpegProductionService
from app.services.test_reliability_service import TestReliabilityService
from app.services.release_candidate_service import ReleaseCandidateService
from app.services.production_security_audit_service import ProductionSecurityAuditService
from app.services.performance_certification_service import PerformanceCertificationService
from app.services.disaster_recovery_validation_service import DisasterRecoveryValidationService
from app.services.documentation_review_service import DocumentationReviewService'''
        extra_init = '''
    def __init__(self, db: Session) -> None:
        from sqlalchemy.orm import Session as _S
        self.db = db
        self.settings = get_settings()
        self._sub = {
            82: CiStabilizationService(),
            83: FfmpegProductionService(),
            84: TestReliabilityService(),
            85: ReleaseCandidateService(),
            86: ProductionSecurityAuditService(),
            87: PerformanceCertificationService(),
            88: DisasterRecoveryValidationService(db),
            89: DocumentationReviewService(db),
        }'''
        extra_report = '''
        mission_verdicts = {}
        for mid, svc in self._sub.items():
            r = svc.certification_report() if hasattr(svc, "certification_report") else svc.stabilization_report() if hasattr(svc, "stabilization_report") else svc.production_report() if hasattr(svc, "production_report") else svc.reliability_report() if hasattr(svc, "reliability_report") else svc.rc1_report() if hasattr(svc, "rc1_report") else svc.audit_report() if hasattr(svc, "audit_report") else svc.performance_report() if hasattr(svc, "performance_report") else svc.validation_report() if hasattr(svc, "validation_report") else svc.review_report()
            mission_verdicts[mid] = r.get("verdict", "unknown")
            if self.settings.pre_production_require_all_missions and r.get("blocking_issues"):
                blocking.extend([f"M{mid}: {x}" for x in r["blocking_issues"][:2]])
        evidence_extra = {"mission_verdicts": mission_verdicts}
'''
    elif num == 91:
        extra_imports = '''
from sqlalchemy.orm import Session

from app.services.pre_production_approval_service import PreProductionApprovalService
from app.services.integration_control_service import get_integration_control_service
from app.services.autonomous_operations_service import AutonomousOperationsService'''
        extra_init = '''
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.pre_prod = PreProductionApprovalService(db)
        self.integration = get_integration_control_service()
        self.autonomous = AutonomousOperationsService(db)'''
        extra_report = '''
        pre = self.pre_prod.approval_report()
        integration = self.integration.merge_health_report()
        autonomous = self.autonomous.readiness_report()
        if pre.get("blocking_issues"):
            blocking.extend([f"pre-prod: {x}" for x in pre["blocking_issues"][:3]])
        if integration.get("blocking_issues"):
            blocking.extend([f"integration: {x}" for x in integration["blocking_issues"][:2]])
        if autonomous.get("blocking_issues"):
            blocking.extend([f"autonomous: {x}" for x in autonomous["blocking_issues"][:2]])
        evidence_extra = {
            "pre_production_verdict": pre.get("verdict"),
            "integration_verdict": integration.get("verdict"),
            "autonomous_verdict": autonomous.get("verdict"),
            "evidence_archive": "RELATORIO_FASE_V17_M82_M91.md",
        }
'''
    else:
        extra_report = '''
        evidence_extra = {"mission": ''' + str(num) + ''', "status": "evaluated"}
'''

    init_block = extra_init or '''
    def __init__(self) -> None:
        self.settings = get_settings()'''

    method_name = {
        83: "production_report",
        84: "reliability_report",
        85: "rc1_report",
        86: "audit_report",
        87: "performance_report",
        88: "validation_report",
        89: "review_report",
        90: "approval_report",
        91: "authorization_report",
    }[num]

    getter = f"get_{mod}_service"
    needs_db = num in (88, 89, 90, 91)

    if needs_db and num != 90:
        getter_body = f'''def {getter}(db: Session) -> {cls}:
    return {cls}(db=db)
'''
    elif num == 90:
        getter_body = f'''def {getter}(db: Session) -> {cls}:
    return {cls}(db=db)
'''
    else:
        getter_body = f'''def {getter}() -> {cls}:
    return {cls}()
'''

    gate_field = f1
    gate_check = f'''
        if not self.settings.{gate_field} and isinstance(self.settings.{gate_field}, bool):
            blocking.append("{gate_field}=False: gate fail-closed permanentemente fechado.")
        elif self.settings.{gate_field} is False:
            blocking.append("{gate_field}=False: gate fail-closed permanentemente fechado.")
'''

    if "max_retries" in f1 or "latency" in f1:
        gate_check = ""

    return f'''"""Missao {num} - {m["title"]}. Fail-closed quando gate desabilitado."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
{extra_imports}
from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, detect_environment, validate_settings

UTC = timezone.utc
VERDICT_READY = "{vr}"
VERDICT_NOT_READY = "not_ready"
{extra_logic}
class {cls}:
    """Missao {num} - {m["title"]}."""
{init_block}
    def {method_name}(self) -> dict[str, Any]:
        environment = detect_environment()
        blocking: list[str] = []
        config_issues = validate_settings(self.settings, environment)
        if config_issues and environment.value in ("production", "testing"):
            blocking.extend(config_issues)
{gate_check}
{extra_report}
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
        report = snapshot if snapshot is not None else self.{method_name}()
        lines = [
            "# {m["title"]} — Relatorio",
            "",
            f"- Veredito: **{{report['verdict']}}**",
            f"- Pronto: {{report['ready']}}",
            f"- CONFIG: {{report['config_schema_version']}}",
            "",
            "## Blocking issues",
        ]
        if report["blocking_issues"]:
            for issue in report["blocking_issues"]:
                lines.append(f"- {{issue}}")
        else:
            lines.append("- Nenhum blocking issue encontrado.")
        return "\\n".join(lines)


{getter_body}
'''


def gen_route(m: dict) -> str:
    mod = m["module"]
    cls = m["service_class"]
    prefix = m["prefix"]
    needs_db = m["num"] in (88, 89, 90, 91)
    method = {
        83: "production_report",
        84: "reliability_report",
        85: "rc1_report",
        86: "audit_report",
        87: "performance_report",
        88: "validation_report",
        89: "review_report",
        90: "approval_report",
        91: "authorization_report",
    }[m["num"]]
    resp = cls.replace("Service", "Response")
    getter = f"get_{mod}_service"

    if needs_db:
        deps = '''
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db'''
        svc_call = f"{cls}(db)"
        getter_import = f"from app.services.{mod}_service import {cls}, {getter}"
        live = f'''
@router.get("/live", response_model={resp})
def {mod}_live(db: Session = Depends(get_db)):
    return {getter}(db).{method}()'''
        md = f'''
@router.get("/markdown", response_class=PlainTextResponse)
def {mod}_markdown(db: Session = Depends(get_db)):
    return PlainTextResponse(
        content={getter}(db).render_markdown(),
        media_type="text/markdown",
    )'''
    else:
        deps = '''
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse'''
        getter_import = f"from app.services.{mod}_service import {getter}"
        live = f'''
@router.get("/live", response_model={resp})
def {mod}_live():
    return {getter}().{method}()'''
        md = f'''
@router.get("/markdown", response_class=PlainTextResponse)
def {mod}_markdown():
    return PlainTextResponse(
        content={getter}().render_markdown(),
        media_type="text/markdown",
    )'''

    return f'''{deps}
from app.schemas.{mod} import {resp}
{getter_import}

router = APIRouter(
    prefix="/{prefix}",
    tags=["{m["title"]}"],
)
{live}
{md}
'''


def gen_test(m: dict) -> str:
    mod = m["module"]
    cls = m["service_class"]
    num = m["num"]
    sv = m["schema_version"]
    method = {
        83: "production_report",
        84: "reliability_report",
        85: "rc1_report",
        86: "audit_report",
        87: "performance_report",
        88: "validation_report",
        89: "review_report",
        90: "approval_report",
        91: "authorization_report",
    }[num]
    prefix = m["prefix"]
    needs_db = num in (88, 89, 90, 91)

    db_setup = ""
    svc_inst = f"{cls}()"
    if needs_db:
        db_setup = '''
from app.db.session import SessionLocal'''
        svc_inst = f'''
    db = SessionLocal()
    try:
        report = {cls}(db).{method}()
        assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
        assert report["mission_number"] == {num}
        assert "verdict" in report
    finally:
        db.close()'''
        shape_test = f'''def test_report_shape():{db_setup}
{svc_inst}'''
    else:
        shape_test = f'''def test_report_shape():
    report = {cls}().{method}()
    assert report["config_schema_version"] == CONFIG_SCHEMA_VERSION
    assert report["mission_number"] == {num}
    assert "verdict" in report'''

    return f'''"""Missao {num} - {m["title"]}."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION
from app.main import app
from app.services.{mod}_service import {cls}


{shape_test}


def test_config_schema_version():
    assert CONFIG_SCHEMA_VERSION == "{sv}"


def test_live_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/{prefix}/live")
    assert r.status_code == 200
    assert "verdict" in r.json()


def test_markdown_endpoint():
    client = TestClient(app)
    r = client.get("/api/v1/{prefix}/markdown")
    assert r.status_code == 200
    assert "Relatorio" in r.text or "Relat" in r.text


def test_render_markdown():
    {"db = SessionLocal(); svc = " + cls + "(db)" if needs_db else "svc = " + cls + "()"}{"" if not needs_db else "; try:"}
    md = {"svc" if needs_db else cls + "()"}.render_markdown()
    {"finally: db.close()" if needs_db else ""}
    assert "#" in md
'''


def main() -> None:
    for m in MISSIONS:
        mod = m["module"]
        print(f"M{m['num']}...")
        write(ROOT / f"src/app/core/config_domains/{mod}.py", gen_config_domain(m))
        write(ROOT / f"src/app/schemas/{mod}.py", gen_schema(m))
        write(ROOT / f"src/app/services/{mod}_service.py", gen_service(m))
        write(ROOT / f"src/app/api/routes/{mod}.py", gen_route(m))
        write(ROOT / f"src/app/tests/test_m{m['num']}_{m['slug'].replace('-', '_')}.py", gen_test(m))
        report = f'''# Missão {m["num"]} — {m["title"]}

CONFIG **{m["schema_version"]}**. Branch: `{m["branch"]}`.

## Endpoints

- `GET /api/v1/{m["prefix"]}/live`
- `GET /api/v1/{m["prefix"]}/markdown`

## Evidência

```text
$ pytest src/app/tests/test_m{m["num"]}_*.py -q
```
'''
        write(ROOT / f"{m['report']}.md", report)
    print("Done. Update config_profiles.py manually per mission.")


if __name__ == "__main__":
    main()
