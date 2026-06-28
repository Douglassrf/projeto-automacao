"""Missao 71 - Operational Intelligence Hub.

Cobre: consolidacao de metricas dos modulos existentes (diagnosticos,
alertas, cache, fila, recursos, recuperacao, auditoria de dependencias,
certificacao) em um painel unificado com eixos stability/performance/
risk/global_project_state; regras puras (_overall_status, _risk_indicators)
testadas com entradas sinteticas; o novo campo de configuracao
`operational_intelligence_include_unpinned_in_risk`; validate_settings()
e CONFIG_SCHEMA_VERSION; e os dois novos endpoints.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.db.session import SessionLocal
from app.domain.models import QueueJob
from app.main import app
from app.services.diagnostics_service import STATUS_CRITICAL, STATUS_OK, STATUS_WARNING
from app.services.operational_intelligence_service import (
    GLOBAL_CRITICAL,
    GLOBAL_DEGRADED,
    GLOBAL_HEALTHY,
    MODULES_TRACKED,
    OperationalIntelligenceService,
)

UTC = timezone.utc


def _queue_name() -> str:
    return f"m71-queue-{uuid4().hex[:8]}"


def _make_stuck_job(db, *, queue_name: str, locked_seconds_ago: int) -> QueueJob:
    job = QueueJob(
        queue_name=queue_name,
        job_type="m71-test-job",
        status="running",
        attempts=1,
        max_attempts=3,
        locked_by="worker-morto",
        locked_at=datetime.now(UTC) - timedelta(seconds=locked_seconds_ago),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _clean_dependency_audit():
    return {
        "missing_count": 0,
        "version_mismatch_count": 0,
        "unpinned_count": 19,
    }


# ---------------------------------------------------------------------------
# Formato do painel agregado
# ---------------------------------------------------------------------------


def test_health_panel_returns_expected_top_level_shape():
    db = SessionLocal()
    try:
        panel = OperationalIntelligenceService(db).health_panel()
        expected_keys = {
            "generated_at",
            "environment",
            "config_schema_version",
            "include_unpinned_in_risk",
            "global_project_state",
            "stability",
            "performance",
            "risk_indicators",
            "modules_tracked",
        }
        assert expected_keys <= set(panel.keys())
        assert isinstance(panel["generated_at"], datetime)
        assert panel["config_schema_version"] == CONFIG_SCHEMA_VERSION
        assert len(panel["modules_tracked"]) == len(MODULES_TRACKED)
    finally:
        db.close()


def test_health_panel_global_state_has_four_axes():
    db = SessionLocal()
    try:
        panel = OperationalIntelligenceService(db).health_panel()
        gps = panel["global_project_state"]
        assert "overall_status" in gps
        assert gps["overall_status"] in {GLOBAL_HEALTHY, GLOBAL_DEGRADED, GLOBAL_CRITICAL}
        assert "modules_health" in gps
        assert len(gps["modules_health"]) == 8
    finally:
        db.close()


def test_health_panel_uses_real_dependency_audit_state():
    db = SessionLocal()
    try:
        panel = OperationalIntelligenceService(db).health_panel()
        risk = panel["risk_indicators"]
        assert risk["dependency_unpinned_count"] == 19
        assert risk["dependency_missing_count"] == 0
    finally:
        db.close()


def test_modules_tracked_lists_eight_operational_modules():
    assert len(MODULES_TRACKED) == 8
    modules = [m["module"] for m in MODULES_TRACKED]
    assert "diagnostics" in modules
    assert "certification" in modules


# ---------------------------------------------------------------------------
# _overall_status() - regra pura
# ---------------------------------------------------------------------------


def test_overall_status_healthy_when_all_clean_and_unpinned_suppressed():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.operational_intelligence_include_unpinned_in_risk
    try:
        settings.operational_intelligence_include_unpinned_in_risk = False
        service = OperationalIntelligenceService(db)
        status = service._overall_status(
            diagnostics_status=STATUS_OK,
            active_alerts_count=0,
            queue_recovery_healthy=True,
            dependency_audit=_clean_dependency_audit(),
            blocking_issues=[],
            config_validation_issues=[],
        )
        assert status == GLOBAL_HEALTHY
    finally:
        settings.operational_intelligence_include_unpinned_in_risk = previous
        db.close()


def test_overall_status_degraded_when_unpinned_included():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.operational_intelligence_include_unpinned_in_risk
    try:
        settings.operational_intelligence_include_unpinned_in_risk = True
        service = OperationalIntelligenceService(db)
        status = service._overall_status(
            diagnostics_status=STATUS_OK,
            active_alerts_count=0,
            queue_recovery_healthy=True,
            dependency_audit=_clean_dependency_audit(),
            blocking_issues=[],
            config_validation_issues=[],
        )
        assert status == GLOBAL_DEGRADED
    finally:
        settings.operational_intelligence_include_unpinned_in_risk = previous
        db.close()


def test_overall_status_critical_on_diagnostics_critical():
    db = SessionLocal()
    try:
        service = OperationalIntelligenceService(db)
        status = service._overall_status(
            diagnostics_status=STATUS_CRITICAL,
            active_alerts_count=0,
            queue_recovery_healthy=True,
            dependency_audit=_clean_dependency_audit(),
            blocking_issues=[],
            config_validation_issues=[],
        )
        assert status == GLOBAL_CRITICAL
    finally:
        db.close()


def test_overall_status_critical_on_missing_dependencies():
    db = SessionLocal()
    try:
        service = OperationalIntelligenceService(db)
        audit = _clean_dependency_audit()
        audit["missing_count"] = 1
        status = service._overall_status(
            diagnostics_status=STATUS_OK,
            active_alerts_count=0,
            queue_recovery_healthy=True,
            dependency_audit=audit,
            blocking_issues=[],
            config_validation_issues=[],
        )
        assert status == GLOBAL_CRITICAL
    finally:
        db.close()


def test_overall_status_critical_on_unhealthy_queue_recovery():
    db = SessionLocal()
    try:
        service = OperationalIntelligenceService(db)
        status = service._overall_status(
            diagnostics_status=STATUS_OK,
            active_alerts_count=0,
            queue_recovery_healthy=False,
            dependency_audit=_clean_dependency_audit(),
            blocking_issues=[],
            config_validation_issues=[],
        )
        assert status == GLOBAL_CRITICAL
    finally:
        db.close()


def test_overall_status_degraded_on_active_alerts():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.operational_intelligence_include_unpinned_in_risk
    try:
        settings.operational_intelligence_include_unpinned_in_risk = False
        service = OperationalIntelligenceService(db)
        status = service._overall_status(
            diagnostics_status=STATUS_OK,
            active_alerts_count=2,
            queue_recovery_healthy=True,
            dependency_audit={"missing_count": 0, "version_mismatch_count": 0, "unpinned_count": 0},
            blocking_issues=[],
            config_validation_issues=[],
        )
        assert status == GLOBAL_DEGRADED
    finally:
        settings.operational_intelligence_include_unpinned_in_risk = previous
        db.close()


# ---------------------------------------------------------------------------
# _risk_indicators() - regra pura
# ---------------------------------------------------------------------------


def test_risk_indicators_includes_unpinned_when_flag_enabled():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.operational_intelligence_include_unpinned_in_risk
    try:
        settings.operational_intelligence_include_unpinned_in_risk = True
        service = OperationalIntelligenceService(db)
        risk = service._risk_indicators(
            dependency_audit=_clean_dependency_audit(),
            config_validation_issues=[],
            blocking_issues=[],
            resource_usage={"total_size_mb": 0.0},
        )
        assert risk["risk_count"] >= 1
        assert any("sem versao fixa" in item for item in risk["risks"])
    finally:
        settings.operational_intelligence_include_unpinned_in_risk = previous
        db.close()


def test_risk_indicators_suppresses_unpinned_when_flag_disabled():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.operational_intelligence_include_unpinned_in_risk
    try:
        settings.operational_intelligence_include_unpinned_in_risk = False
        service = OperationalIntelligenceService(db)
        risk = service._risk_indicators(
            dependency_audit=_clean_dependency_audit(),
            config_validation_issues=[],
            blocking_issues=[],
            resource_usage={"total_size_mb": 0.0},
        )
        assert not any("sem versao fixa" in item for item in risk["risks"])
    finally:
        settings.operational_intelligence_include_unpinned_in_risk = previous
        db.close()


def test_risk_indicators_accumulates_blocking_and_config_issues():
    db = SessionLocal()
    settings = get_settings()
    previous = settings.operational_intelligence_include_unpinned_in_risk
    try:
        settings.operational_intelligence_include_unpinned_in_risk = False
        service = OperationalIntelligenceService(db)
        risk = service._risk_indicators(
            dependency_audit={"missing_count": 0, "version_mismatch_count": 0, "unpinned_count": 0},
            config_validation_issues=["config invalida"],
            blocking_issues=["fila nao saudavel"],
            resource_usage={"total_size_mb": 12.5},
        )
        assert risk["risk_count"] == 2
        assert risk["blocking_issue_count"] == 1
        assert risk["config_validation_issue_count"] == 1
        assert risk["disk_total_size_mb"] == 12.5
    finally:
        settings.operational_intelligence_include_unpinned_in_risk = previous
        db.close()


# ---------------------------------------------------------------------------
# Integracao real - stuck job degrada painel
# ---------------------------------------------------------------------------


def test_real_stuck_job_makes_overall_status_critical():
    db = SessionLocal()
    settings = get_settings()
    try:
        _make_stuck_job(
            db,
            queue_name=_queue_name(),
            locked_seconds_ago=settings.queue_lock_timeout_seconds + 60,
        )
        panel = OperationalIntelligenceService(db).health_panel()
        assert panel["global_project_state"]["overall_status"] == GLOBAL_CRITICAL
        assert panel["stability"]["queue_recovery_healthy"] is False
    finally:
        db.close()


def test_health_panel_does_not_mutate_queue_jobs():
    db = SessionLocal()
    try:
        before = db.query(QueueJob).count()
        OperationalIntelligenceService(db).health_panel()
        OperationalIntelligenceService(db).health_panel()
        after = db.query(QueueJob).count()
        assert after == before
    finally:
        db.close()


# ---------------------------------------------------------------------------
# render_markdown()
# ---------------------------------------------------------------------------


def test_render_markdown_contains_key_sections():
    db = SessionLocal()
    try:
        md = OperationalIntelligenceService(db).render_markdown()
        assert "# Operational Intelligence Hub" in md
        assert "## Estabilidade" in md
        assert "## Desempenho" in md
        assert "## Indicadores de risco" in md
        assert "## Modulos rastreados" in md
    finally:
        db.close()


def test_render_markdown_accepts_precomputed_snapshot():
    db = SessionLocal()
    try:
        service = OperationalIntelligenceService(db)
        snapshot = service.health_panel()
        md = service.render_markdown(snapshot)
        assert snapshot["global_project_state"]["overall_status"] in md
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def test_health_panel_live_endpoint_returns_expected_shape():
    client = TestClient(app)
    response = client.get("/api/v1/operational-intelligence/health-panel/live")
    assert response.status_code == 200
    body = response.json()
    assert "global_project_state" in body
    assert "stability" in body
    assert "performance" in body
    assert "risk_indicators" in body
    assert len(body["modules_tracked"]) == 8
    assert body["risk_indicators"]["dependency_unpinned_count"] == 19


def test_health_panel_markdown_endpoint_returns_text_markdown():
    client = TestClient(app)
    response = client.get("/api/v1/operational-intelligence/health-panel/markdown")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "# Operational Intelligence Hub" in response.text


# ---------------------------------------------------------------------------
# Configuracao (Missao 71)
# ---------------------------------------------------------------------------


def test_config_schema_version_bumped_for_mission_71():
    current = tuple(int(part) for part in CONFIG_SCHEMA_VERSION.split("."))
    assert current >= (2, 0, 0)


def test_validate_settings_rejects_disabled_unpinned_risk_in_production():
    settings = get_settings()
    previous = settings.operational_intelligence_include_unpinned_in_risk
    try:
        settings.operational_intelligence_include_unpinned_in_risk = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("operational_intelligence_include_unpinned_in_risk" in issue for issue in issues)
    finally:
        settings.operational_intelligence_include_unpinned_in_risk = previous


def test_validate_settings_accepts_default_unpinned_risk_in_production():
    settings = get_settings()
    previous = settings.operational_intelligence_include_unpinned_in_risk
    try:
        settings.operational_intelligence_include_unpinned_in_risk = True
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert not any("operational_intelligence_include_unpinned_in_risk" in issue for issue in issues)
    finally:
        settings.operational_intelligence_include_unpinned_in_risk = previous


def test_validate_settings_ignores_unpinned_risk_flag_outside_production():
    settings = get_settings()
    previous = settings.operational_intelligence_include_unpinned_in_risk
    try:
        settings.operational_intelligence_include_unpinned_in_risk = False
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert not any("operational_intelligence_include_unpinned_in_risk" in issue for issue in issues)
    finally:
        settings.operational_intelligence_include_unpinned_in_risk = previous
