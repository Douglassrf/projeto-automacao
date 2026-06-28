"""Missao 50 - Certificacao Platinum v1.3.

Capstone das Missoes 41-49: CertificationService nao reimplementa
diagnostico/alerta/fila/recurso/dependencia - apenas agrega o que cada
servico anterior ja calcula e aplica uma unica regra de veredito.

Cobre: o formato do snapshot agregado, a regra de bloqueio
(`_blocking_issues`) isolada de qualquer estado real de banco (testada
com entradas sinteticas, para nao depender de "o banco de testes
compartilhado esta limpo agora"), a regra de veredito "fail-closed"
(`certification_platinum_require_clean_diagnostics`), o caso real de
integracao (um job de fila travado torna a certificacao nao-platinum),
a garantia de que certify() nao tem efeito colateral, os dois novos
endpoints e a nova regra de validate_settings()/CONFIG_SCHEMA_VERSION.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.domain.models import AlertEvent, QueueJob
from app.main import app
from app.services.certification_service import MISSIONS_COVERED, CertificationService
from app.services.diagnostics_service import STATUS_OK

UTC = timezone.utc


def _queue_name() -> str:
    return f"m50-queue-{uuid4().hex[:8]}"


def _make_stuck_job(db, *, queue_name: str, locked_seconds_ago: int) -> QueueJob:
    job = QueueJob(
        queue_name=queue_name,
        job_type="m50-test-job",
        status="running",
        attempts=1,
        max_attempts=3,
        locked_by="worker-que-morreu",
        locked_at=datetime.now(UTC) - timedelta(seconds=locked_seconds_ago),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Formato do snapshot agregado
# ---------------------------------------------------------------------------


def test_certify_returns_expected_top_level_shape():
    db = SessionLocal()
    try:
        snapshot = CertificationService(db).certify()
        expected_keys = {
            "generated_at",
            "environment",
            "config_schema_version",
            "strict_mode",
            "config_validation_issues",
            "diagnostics_status",
            "diagnostics_summary",
            "active_alerts_count",
            "active_alerts",
            "dependency_audit_summary",
            "queue_recovery",
            "resource_usage",
            "missions_covered",
            "blocking_issues",
            "platinum_certified",
        }
        assert expected_keys <= set(snapshot.keys())
        assert isinstance(snapshot["generated_at"], datetime)
        assert isinstance(snapshot["platinum_certified"], bool)
        assert isinstance(snapshot["blocking_issues"], list)
        assert snapshot["config_schema_version"] == CONFIG_SCHEMA_VERSION
    finally:
        db.close()


def test_certify_uses_real_dependency_audit_repo_state():
    db = SessionLocal()
    try:
        snapshot = CertificationService(db).certify()
        dep = snapshot["dependency_audit_summary"]
        # Mesmo estado real verificado na Missao 49: 19 dependencias
        # declaradas, nenhuma fixada.
        assert dep["total_declared"] == 19
        assert dep["unpinned_count"] == 19
        # Falta de pin e informativo (Missao 49) - nunca aparece como
        # bloqueante na certificacao Platinum.
        assert not any("sem versão fixa" in issue for issue in snapshot["blocking_issues"])
        assert not any("unpinned" in issue.lower() for issue in snapshot["blocking_issues"])
    finally:
        db.close()


def test_missions_covered_lists_all_nine_prior_missions():
    assert len(MISSIONS_COVERED) == 9
    numbers = [m["mission"] for m in MISSIONS_COVERED]
    assert numbers == [str(n) for n in range(41, 50)]


# ---------------------------------------------------------------------------
# _blocking_issues() - regra pura, testada com entradas sinteticas
# ---------------------------------------------------------------------------


def _clean_inputs():
    return dict(
        diagnostics={"status": STATUS_OK},
        active_alerts=[],
        dependency_audit={
            "missing_count": 0,
            "version_mismatch_count": 0,
            "unpinned_count": 19,
        },
        queue_recovery={"healthy": True},
    )


def test_blocking_issues_empty_when_all_inputs_clean():
    db = SessionLocal()
    try:
        service = CertificationService(db)
        assert service._blocking_issues(**_clean_inputs()) == []
    finally:
        db.close()


def test_blocking_issues_flags_non_ok_diagnostics_status():
    db = SessionLocal()
    try:
        service = CertificationService(db)
        inputs = _clean_inputs()
        inputs["diagnostics"] = {"status": "critical"}
        issues = service._blocking_issues(**inputs)
        assert len(issues) == 1
        assert "critical" in issues[0]
    finally:
        db.close()


def test_blocking_issues_flags_active_alerts():
    db = SessionLocal()
    try:
        service = CertificationService(db)
        inputs = _clean_inputs()
        inputs["active_alerts"] = [{"check_name": "queue"}, {"check_name": "disk"}]
        issues = service._blocking_issues(**inputs)
        assert len(issues) == 1
        assert "2 alerta" in issues[0]
        assert "disk" in issues[0] and "queue" in issues[0]
    finally:
        db.close()


def test_blocking_issues_flags_missing_dependencies():
    db = SessionLocal()
    try:
        service = CertificationService(db)
        inputs = _clean_inputs()
        inputs["dependency_audit"] = {
            "missing_count": 2,
            "version_mismatch_count": 0,
            "unpinned_count": 19,
        }
        issues = service._blocking_issues(**inputs)
        assert len(issues) == 1
        assert "2 dependencia" in issues[0] and "ausente" in issues[0]
    finally:
        db.close()


def test_blocking_issues_flags_version_mismatch_dependencies():
    db = SessionLocal()
    try:
        service = CertificationService(db)
        inputs = _clean_inputs()
        inputs["dependency_audit"] = {
            "missing_count": 0,
            "version_mismatch_count": 1,
            "unpinned_count": 19,
        }
        issues = service._blocking_issues(**inputs)
        assert len(issues) == 1
        assert "1 dependencia" in issues[0] and "diferente da versao fixada" in issues[0]
    finally:
        db.close()


def test_blocking_issues_ignores_unpinned_dependencies():
    db = SessionLocal()
    try:
        service = CertificationService(db)
        inputs = _clean_inputs()
        inputs["dependency_audit"] = {
            "missing_count": 0,
            "version_mismatch_count": 0,
            "unpinned_count": 19,
        }
        assert service._blocking_issues(**inputs) == []
    finally:
        db.close()


def test_blocking_issues_flags_unhealthy_queue_recovery():
    db = SessionLocal()
    try:
        service = CertificationService(db)
        inputs = _clean_inputs()
        inputs["queue_recovery"] = {"healthy": False}
        issues = service._blocking_issues(**inputs)
        assert len(issues) == 1
        assert "fila" in issues[0].lower()
    finally:
        db.close()


def test_blocking_issues_accumulates_multiple_independent_problems():
    db = SessionLocal()
    try:
        service = CertificationService(db)
        issues = service._blocking_issues(
            diagnostics={"status": "warning"},
            active_alerts=[{"check_name": "queue"}],
            dependency_audit={"missing_count": 1, "version_mismatch_count": 0, "unpinned_count": 19},
            queue_recovery={"healthy": False},
        )
        assert len(issues) == 4
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Regra de veredito "fail-closed"
# ---------------------------------------------------------------------------


def test_platinum_certified_true_when_strict_and_no_blocking_issues():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.certification_platinum_require_clean_diagnostics
    try:
        settings.certification_platinum_require_clean_diagnostics = True
        service = CertificationService(db)
        service._blocking_issues = lambda *args, **kwargs: []
        snapshot = service.certify()
        assert snapshot["strict_mode"] is True
        assert snapshot["blocking_issues"] == []
        assert snapshot["platinum_certified"] is True
    finally:
        settings.certification_platinum_require_clean_diagnostics = previous
        db.close()


def test_platinum_certified_false_when_blocking_issues_present():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.certification_platinum_require_clean_diagnostics
    try:
        settings.certification_platinum_require_clean_diagnostics = True
        service = CertificationService(db)
        service._blocking_issues = lambda *args, **kwargs: ["problema sintetico"]
        snapshot = service.certify()
        assert snapshot["blocking_issues"] == ["problema sintetico"]
        assert snapshot["platinum_certified"] is False
    finally:
        settings.certification_platinum_require_clean_diagnostics = previous
        db.close()


def test_platinum_certified_false_when_strict_mode_disabled_even_with_no_issues():
    # O gate e fail-closed por design: desliga-lo nunca libera uma
    # certificacao "de gracinha", mesmo que blocking_issues esteja vazio.
    db = SessionLocal()
    settings = get_settings()
    previous = settings.certification_platinum_require_clean_diagnostics
    try:
        settings.certification_platinum_require_clean_diagnostics = False
        service = CertificationService(db)
        service._blocking_issues = lambda *args, **kwargs: []
        snapshot = service.certify()
        assert snapshot["strict_mode"] is False
        assert snapshot["blocking_issues"] == []
        assert snapshot["platinum_certified"] is False
    finally:
        settings.certification_platinum_require_clean_diagnostics = previous
        db.close()


# ---------------------------------------------------------------------------
# Integracao real com banco - caso concreto de nao-certificacao
# ---------------------------------------------------------------------------


def test_real_stuck_job_makes_certification_not_platinum():
    db = SessionLocal()
    settings = get_settings()
    try:
        _make_stuck_job(
            db,
            queue_name=_queue_name(),
            locked_seconds_ago=settings.queue_lock_timeout_seconds + 60,
        )
        snapshot = CertificationService(db).certify()
        assert snapshot["platinum_certified"] is False
        assert snapshot["queue_recovery"]["healthy"] is False
        assert len(snapshot["blocking_issues"]) >= 1
    finally:
        db.close()


def test_certify_does_not_mutate_alert_events():
    db = SessionLocal()
    try:
        before = db.query(AlertEvent).count()
        CertificationService(db).certify()
        CertificationService(db).certify()
        after = db.query(AlertEvent).count()
        assert after == before
    finally:
        db.close()


# ---------------------------------------------------------------------------
# render_markdown()
# ---------------------------------------------------------------------------


def test_render_markdown_contains_key_sections():
    db = SessionLocal()
    try:
        md = CertificationService(db).render_markdown()
        assert "# Certificacao Platinum v1.3" in md
        assert "## Veredito" in md
        assert "## Auditoria de dependencias" in md
        assert "## Recuperacao de fila" in md
        assert "## Missoes cobertas" in md
        assert "Missao 41" in md and "Missao 49" in md
    finally:
        db.close()


def test_render_markdown_accepts_precomputed_snapshot():
    db = SessionLocal()
    try:
        service = CertificationService(db)
        snapshot = service.certify()
        md = service.render_markdown(snapshot)
        if snapshot["platinum_certified"]:
            assert "PLATINUM CERTIFICADO" in md
        else:
            assert "NAO CERTIFICADO" in md
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def test_certification_live_endpoint_returns_expected_shape():
    client = TestClient(app)
    response = client.get("/api/v1/certification/platinum/live")
    assert response.status_code == 200
    body = response.json()
    assert "platinum_certified" in body
    assert "blocking_issues" in body
    assert len(body["missions_covered"]) == 9
    assert body["dependency_audit_summary"]["total_declared"] == 19


def test_certification_markdown_endpoint_returns_text_markdown():
    client = TestClient(app)
    response = client.get("/api/v1/certification/platinum/markdown")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "# Certificacao Platinum v1.3" in response.text


# ---------------------------------------------------------------------------
# Configuracao (Missao 50)
# ---------------------------------------------------------------------------


def test_config_schema_version_bumped_for_mission_50():
    current = tuple(int(part) for part in CONFIG_SCHEMA_VERSION.split("."))
    assert current >= (1, 9, 0)


def test_validate_settings_rejects_disabled_certification_gate_in_production():
    settings = get_settings()
    previous = settings.certification_platinum_require_clean_diagnostics
    try:
        settings.certification_platinum_require_clean_diagnostics = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("certification_platinum_require_clean_diagnostics" in issue for issue in issues)
    finally:
        settings.certification_platinum_require_clean_diagnostics = previous


def test_validate_settings_accepts_default_certification_gate_in_production():
    settings = get_settings()
    previous = settings.certification_platinum_require_clean_diagnostics
    try:
        settings.certification_platinum_require_clean_diagnostics = True
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert not any("certification_platinum_require_clean_diagnostics" in issue for issue in issues)
    finally:
        settings.certification_platinum_require_clean_diagnostics = previous


def test_validate_settings_ignores_certification_gate_flag_outside_production():
    settings = get_settings()
    previous = settings.certification_platinum_require_clean_diagnostics
    try:
        settings.certification_platinum_require_clean_diagnostics = False
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert not any("certification_platinum_require_clean_diagnostics" in issue for issue in issues)
    finally:
        settings.certification_platinum_require_clean_diagnostics = previous
