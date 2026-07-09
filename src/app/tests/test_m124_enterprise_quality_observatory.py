"""Missao 124 - Enterprise Quality Observatory (Fase v2.1).

Cobertura desta suite: (1) cada uma das seis dimensoes
(`bug_observatory`, `performance_observatory`, `coverage_observatory`,
`tech_debt_observatory`, `stability_observatory`,
`security_observatory`) e reuso DIRETO e comprovado (via fakes com
contador de chamadas) dos motores das Missoes 46/59/60/58/47/49 - nunca
recalculado aqui; (2) prova explicita de que `coverage_observatory()`
chama apenas `mission_test_coverage()`, nunca o `readiness_report()`
inteiro da Missao 60 (cadeia cara/lenta); (3) a heuristica documentada
de `security_observatory()` (missing_count + version_mismatch_count ->
bloqueante; unpinned_count -> nunca bloqueante) testada nos tres casos;
(4) `quality_report()` agrega as seis dimensoes em
`monitored_dimensions` com classificacao correta em
healthy/unhealthy/untracked, incluindo o caso `tech_debt` sempre
`healthy=None` por desenho; (5) `render_markdown()` reflete os
marcadores OK/ATENCAO/INFORMATIVO; (6) smoke test contra o repositorio
real (isolado, por chamar ArchitectureStressTestService.stress_report()
que sobe um TestClient real - mesmo custo documentado nas Missoes
59/60); (7) registro via `provide()` e endpoints HTTP refletindo o
service real via container de DI (Missao 52), nunca hardcoded na rota.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.container import get_enterprise_quality_observatory_service, registered_providers
from app.db.session import SessionLocal
from app.main import app as real_app
from app.services.enterprise_quality_observatory_service import (
    EnterpriseQualityObservatoryService,
)

UTC = timezone.utc


def _service(**kwargs):
    db = SessionLocal()
    return EnterpriseQualityObservatoryService(db, **kwargs), db


# --- fakes (contador de chamadas comprova reuso direto, nunca recalculo) ---


class _FakeAlertService:
    def __init__(self, alerts=None):
        self._alerts = alerts if alerts is not None else []
        self.active_alerts_calls = 0

    def active_alerts(self):
        self.active_alerts_calls += 1
        return self._alerts


class _FakeStressTest:
    def __init__(self, report=None):
        self._report = report if report is not None else {"clean": True}
        self.stress_report_calls = 0

    def stress_report(self):
        self.stress_report_calls += 1
        return self._report


class _FakeEnterpriseReadiness:
    def __init__(self, coverage=None):
        self._coverage = coverage if coverage is not None else {
            "total_missions_checked": 0,
            "missions_with_dedicated_suite": [],
            "missions_without_dedicated_suite": [],
            "complete": True,
        }
        self.mission_test_coverage_calls = 0
        self.readiness_report_calls = 0

    def mission_test_coverage(self):
        self.mission_test_coverage_calls += 1
        return self._coverage

    def readiness_report(self):
        # Nunca deve ser chamado por EnterpriseQualityObservatoryService -
        # e a cadeia cara/lenta da Missao 60. Existe aqui so para provar,
        # via contador, que isso de fato nunca acontece.
        self.readiness_report_calls += 1
        raise AssertionError("readiness_report() nao deveria ser chamado pela Missao 124")


class _FakeTechDebtManager:
    def __init__(self, report=None):
        self._report = report if report is not None else {"summary": {"total_debt_items": 0}}
        self.debt_report_calls = 0

    def debt_report(self):
        self.debt_report_calls += 1
        return self._report


class _FakeRecoveryService:
    def __init__(self, report=None):
        self._report = report if report is not None else {
            "healthy": True,
            "recoverable_now": 0,
            "requires_external_action": 0,
            "warnings": [],
        }
        self.recovery_report_calls = 0

    def recovery_report(self):
        self.recovery_report_calls += 1
        return self._report


class _FakeDependencyAudit:
    def __init__(self, audit=None):
        self._audit = audit if audit is not None else {
            "total_declared": 1,
            "pinned_count": 0,
            "unpinned_count": 1,
            "missing_count": 0,
            "version_mismatch_count": 0,
            "issues": [],
            "dependencies": [],
        }
        self.audit_calls = 0

    def audit(self):
        self.audit_calls += 1
        return self._audit


def _full_fake_service():
    alert = _FakeAlertService()
    stress = _FakeStressTest()
    readiness = _FakeEnterpriseReadiness()
    debt = _FakeTechDebtManager()
    recovery = _FakeRecoveryService()
    audit = _FakeDependencyAudit()
    service, db = _service(
        alert_service=alert,
        stress_test=stress,
        enterprise_readiness=readiness,
        tech_debt_manager=debt,
        recovery_service=recovery,
        dependency_audit=audit,
    )
    return service, db, {
        "alert": alert,
        "stress": stress,
        "readiness": readiness,
        "debt": debt,
        "recovery": recovery,
        "audit": audit,
    }


# --- dimensoes individuais: reuso direto, sem recalculo --------------------


def test_bug_observatory_reuses_alert_service_active_alerts_directly():
    alerts = [
        {"check_name": "queue", "severity": "critical"},
        {"check_name": "disk", "severity": "warning"},
        {"check_name": "cache", "severity": "warning"},
    ]
    fake = _FakeAlertService(alerts)
    service, db = _service(alert_service=fake)
    try:
        result = service.bug_observatory()
        assert fake.active_alerts_calls == 1
        assert result["active_alert_count"] == 3
        assert result["by_severity"] == {"critical": 1, "warning": 2}
        assert result["clean"] is False
        assert result["alerts"] == alerts
    finally:
        db.close()


def test_bug_observatory_clean_when_no_active_alerts():
    fake = _FakeAlertService([])
    service, db = _service(alert_service=fake)
    try:
        result = service.bug_observatory()
        assert result["clean"] is True
        assert result["active_alert_count"] == 0
    finally:
        db.close()


def test_performance_observatory_reuses_stress_report_directly():
    fake = _FakeStressTest({"clean": False, "endpoints": ["x"]})
    service, db = _service(stress_test=fake)
    try:
        result = service.performance_observatory()
        assert fake.stress_report_calls == 1
        assert result == {"clean": False, "endpoints": ["x"]}
    finally:
        db.close()


def test_coverage_observatory_calls_only_mission_test_coverage_never_readiness_report():
    fake = _FakeEnterpriseReadiness({"complete": False, "missions_without_dedicated_suite": [99]})
    service, db = _service(enterprise_readiness=fake)
    try:
        result = service.coverage_observatory()
        assert fake.mission_test_coverage_calls == 1
        assert fake.readiness_report_calls == 0
        assert result["complete"] is False
        assert result["missions_without_dedicated_suite"] == [99]
    finally:
        db.close()


def test_tech_debt_observatory_reuses_debt_report_directly():
    fake = _FakeTechDebtManager({"summary": {"total_debt_items": 7}})
    service, db = _service(tech_debt_manager=fake)
    try:
        result = service.tech_debt_observatory()
        assert fake.debt_report_calls == 1
        assert result["summary"]["total_debt_items"] == 7
    finally:
        db.close()


def test_stability_observatory_reuses_recovery_report_directly():
    fake = _FakeRecoveryService({"healthy": False, "warnings": ["fila parada"]})
    service, db = _service(recovery_service=fake)
    try:
        result = service.stability_observatory()
        assert fake.recovery_report_calls == 1
        assert result["healthy"] is False
        assert result["warnings"] == ["fila parada"]
    finally:
        db.close()


# --- heuristica documentada de security_observatory ------------------------


def test_security_observatory_clean_when_no_missing_or_mismatch_even_with_unpinned():
    fake = _FakeDependencyAudit({"missing_count": 0, "version_mismatch_count": 0, "unpinned_count": 19})
    service, db = _service(dependency_audit=fake)
    try:
        result = service.security_observatory()
        assert fake.audit_calls == 1
        assert result["clean"] is True
        assert result["unpinned_count"] == 19
    finally:
        db.close()


def test_security_observatory_not_clean_when_missing_count_positive():
    fake = _FakeDependencyAudit({"missing_count": 1, "version_mismatch_count": 0, "unpinned_count": 0})
    service, db = _service(dependency_audit=fake)
    try:
        result = service.security_observatory()
        assert result["clean"] is False
    finally:
        db.close()


def test_security_observatory_not_clean_when_version_mismatch_positive():
    fake = _FakeDependencyAudit({"missing_count": 0, "version_mismatch_count": 1, "unpinned_count": 0})
    service, db = _service(dependency_audit=fake)
    try:
        result = service.security_observatory()
        assert result["clean"] is False
    finally:
        db.close()


# --- quality_report(): agregacao das seis dimensoes -------------------------


def test_quality_report_classifies_dimensions_into_healthy_unhealthy_untracked():
    service, db, fakes = _full_fake_service()
    fakes["alert"]._alerts = [{"check_name": "queue", "severity": "critical"}]  # bugs -> unhealthy
    fakes["stress"]._report = {"clean": True}  # performance -> healthy
    fakes["readiness"]._coverage = {"complete": True, "missions_without_dedicated_suite": []}  # coverage -> healthy
    fakes["debt"]._report = {"summary": {"total_debt_items": 5}}  # tech_debt -> untracked
    fakes["recovery"]._report = {"healthy": False, "warnings": ["fila travada"]}  # stability -> unhealthy
    fakes["audit"]._audit = {
        "missing_count": 0,
        "version_mismatch_count": 0,
        "unpinned_count": 19,
        "issues": [],
    }  # security -> healthy
    try:
        report = service.quality_report()

        assert fakes["alert"].active_alerts_calls == 1
        assert fakes["stress"].stress_report_calls == 1
        assert fakes["readiness"].mission_test_coverage_calls == 1
        assert fakes["readiness"].readiness_report_calls == 0
        assert fakes["debt"].debt_report_calls == 1
        assert fakes["recovery"].recovery_report_calls == 1
        assert fakes["audit"].audit_calls == 1

        assert report["healthy_dimensions"] == ["coverage", "performance", "security"]
        assert report["unhealthy_dimensions"] == ["bugs", "stability"]
        assert report["untracked_dimensions"] == ["tech_debt"]
        assert report["monitored_dimensions"]["tech_debt"]["healthy"] is None
        assert report["monitored_dimensions"]["bugs"]["value"] == 1
        assert isinstance(report["generated_at"], datetime)
    finally:
        db.close()


def test_quality_report_all_healthy_scenario():
    service, db, fakes = _full_fake_service()
    try:
        report = service.quality_report()
        assert report["unhealthy_dimensions"] == []
        assert report["healthy_dimensions"] == ["bugs", "coverage", "performance", "security", "stability"]
        assert report["untracked_dimensions"] == ["tech_debt"]
    finally:
        db.close()


# --- render_markdown ---------------------------------------------------------


def test_render_markdown_shows_markers_for_each_dimension():
    service, db, fakes = _full_fake_service()
    fakes["alert"]._alerts = [{"check_name": "queue", "severity": "critical"}]
    fakes["recovery"]._report = {"healthy": False, "warnings": ["fila travada"]}
    try:
        markdown = service.render_markdown()
        assert markdown.startswith("# Observatorio de Qualidade Enterprise (Missao 124)")
        assert "`bugs`: ATENCAO" in markdown
        assert "`stability`: ATENCAO" in markdown
        assert "`tech_debt`: INFORMATIVO" in markdown
        assert "`performance`: OK" in markdown
        assert "Dimensoes com atencao" in markdown
        assert "IMPORTANTE" in markdown
        assert "Missao 60" in markdown
    finally:
        db.close()


def test_render_markdown_omits_attention_line_when_nothing_unhealthy():
    service, db, fakes = _full_fake_service()
    try:
        markdown = service.render_markdown()
        assert "Dimensoes com atencao" not in markdown
    finally:
        db.close()


# --- smoke test contra o repositorio real (isolado: stress_report() real) --


def test_quality_report_against_real_repository_has_well_typed_fields():
    service, db = _service()
    try:
        report = service.quality_report()
        for key in ("bugs", "performance", "coverage", "tech_debt", "stability", "security"):
            assert key in report
        dims = report["monitored_dimensions"]
        assert dims["tech_debt"]["healthy"] is None
        assert isinstance(dims["bugs"]["healthy"], bool)
        assert isinstance(dims["performance"]["healthy"], bool)
        assert isinstance(dims["coverage"]["healthy"], bool)
        assert isinstance(dims["stability"]["healthy"], bool)
        assert isinstance(dims["security"]["healthy"], bool)
        markdown = service.render_markdown(report)
        assert markdown.startswith("# Observatorio de Qualidade Enterprise (Missao 124)")
    finally:
        db.close()


# --- registro + endpoints HTTP ----------------------------------------------


def test_enterprise_quality_observatory_service_is_registered_via_provide():
    assert "EnterpriseQualityObservatoryService" in registered_providers()


def test_quality_observatory_live_endpoint_returns_real_computed_report():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/quality-observatory/live")
        assert response.status_code == 200
        data = response.json()
        assert "monitored_dimensions" in data
        assert "security" in data


def test_quality_observatory_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/quality-observatory/markdown")
        assert response.status_code == 200
        assert "Observatorio de Qualidade Enterprise" in response.text


def test_quality_observatory_endpoint_is_overridable_via_container_not_hardcoded():
    class _StubObservatory:
        def quality_report(self):
            return {"monitored_dimensions": "stub-marker"}

        def render_markdown(self, report=None):
            return "stub markdown"

    real_app.dependency_overrides[get_enterprise_quality_observatory_service] = lambda: _StubObservatory()
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/quality-observatory/live")
            assert response.json() == {"monitored_dimensions": "stub-marker"}
    finally:
        real_app.dependency_overrides.pop(get_enterprise_quality_observatory_service, None)
