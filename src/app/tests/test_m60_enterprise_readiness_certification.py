"""Missao 60 - Enterprise Readiness Certification.

Cobertura desta suite: (1) `mission_test_coverage()` contra a timeline
real do git, e contra timeline sintetica com numero de missao sem
arquivo de teste correspondente (prova que o eixo realmente detecta
falha, nao so "passa hoje"); (2) `readiness_report()` e um agregador
puro de `EvolutionDashboardService.current_snapshot()` (M57),
`ArchitectureStressTestService.stress_report()` (M59) e
`TechDebtManagerService.debt_report()` (M58) - provado via fakes
injetados no construtor, nunca monkeypatch de modulo; (3) cada um dos
5 eixos bloqueantes, isoladamente, e capaz de derrubar
`enterprise_ready` para False quando falha; (4) eixos informativos
(`timeline_health`, `tech_debt_summary`) nunca entram em
`blocking_axes`; (5) `render_markdown()` produz texto coerente,
incluindo o aviso obrigatorio de que este veredito nao substitui a
certificacao oficial da Fase Omega; (6) `EnterpriseReadinessService`
PRECISA de `db` (porque `EvolutionDashboardService` precisa,
transitivamente, via `UnifiedCertificationEngine`) e por isso usa
`provide()`, igual `get_evolution_dashboard_service` (Missao 57) -
confirmado que aparece em `registered_providers()`; (7) os endpoints
HTTP novos refletem o service real via o container de DI (Missao 52),
nao um valor hardcoded na propria rota.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.container import get_enterprise_readiness_service, registered_providers
from app.db.session import SessionLocal
from app.main import app as real_app
from app.services.enterprise_readiness_service import EnterpriseReadinessService


def _service() -> tuple[EnterpriseReadinessService, "Session"]:
    db = SessionLocal()
    return EnterpriseReadinessService(db), db


# --- fakes --------------------------------------------------------------


class _FakeEvolutionDashboard:
    def __init__(self, snapshot=None, timeline=None, health=None):
        self._snapshot = snapshot or {
            "unified_certified": True,
            "architecture_clean": True,
            "code_review_clean": True,
        }
        self._timeline = timeline if timeline is not None else []
        self._health = health or {
            "total_missions_detected": 0,
            "missing_mission_numbers": [],
            "duplicate_mission_numbers": [],
        }
        self.snapshot_calls = 0
        self.timeline_calls = 0

    def current_snapshot(self):
        self.snapshot_calls += 1
        return self._snapshot

    def mission_timeline(self):
        self.timeline_calls += 1
        return self._timeline

    def timeline_health(self, timeline=None):
        return self._health


class _FakeStressTest:
    def __init__(self, clean=True):
        self._clean = clean

    def stress_report(self):
        return {"clean": self._clean}


class _FakeTechDebtManager:
    def __init__(self, total=0, files=0, score=0):
        self._summary = {
            "total_debt_items": total,
            "files_with_debt": files,
            "total_priority_score": score,
        }

    def debt_report(self):
        return {"summary": self._summary}


def _fake_service(
    snapshot=None,
    timeline=None,
    health=None,
    stress_clean=True,
    debt_total=0,
):
    db = SessionLocal()
    service = EnterpriseReadinessService(
        db,
        evolution_dashboard=_FakeEvolutionDashboard(snapshot=snapshot, timeline=timeline, health=health),
        stress_test=_FakeStressTest(clean=stress_clean),
        tech_debt_manager=_FakeTechDebtManager(total=debt_total),
    )
    return service, db


# --- mission_test_coverage(): contra o repositorio real -----------------


def test_mission_test_coverage_against_the_real_repository_finds_no_gap():
    """Cobertura da serie propria desta missao (51-60) precisa ser
    completa no clone real. Numeros de outras series (ex.: 71-80) podem
    aparecer em `missions_without_dedicated_suite` quando o clone local
    tem branches paralelas buscadas (mission_timeline usa `git log --all`,
    Missao 57) sem o respectivo arquivo de teste estar no checkout atual -
    isso reflete o estado real do disco, nao e uma lacuna da serie 51-60,
    entao o teste verifica especificamente a propria serie, nao o total
    global (que depende de quais branches o clone local buscou)."""
    service, db = _service()
    try:
        coverage = service.mission_test_coverage()
        assert coverage["total_missions_checked"] >= 19
        own_series = set(range(51, 60))
        gap_in_own_series = own_series & set(coverage["missions_without_dedicated_suite"])
        assert gap_in_own_series == set()
        assert 59 in coverage["missions_with_dedicated_suite"]
    finally:
        db.close()


def test_mission_test_coverage_detects_a_synthetic_missing_suite():
    service, db = _service()
    try:
        fake_timeline = [
            {"mission_number": 59},
            {"mission_number": 99999},
        ]
        coverage = service.mission_test_coverage(fake_timeline)
        assert coverage["total_missions_checked"] == 2
        assert 59 in coverage["missions_with_dedicated_suite"]
        assert 99999 in coverage["missions_without_dedicated_suite"]
        assert coverage["complete"] is False
    finally:
        db.close()


def test_mission_test_coverage_handles_an_empty_timeline_without_crashing():
    service, db = _service()
    try:
        coverage = service.mission_test_coverage([])
        assert coverage["total_missions_checked"] == 0
        assert coverage["missions_with_dedicated_suite"] == []
        assert coverage["missions_without_dedicated_suite"] == []
        assert coverage["complete"] is True
    finally:
        db.close()


def test_mission_test_coverage_defaults_to_the_real_git_timeline_when_none_passed():
    service, db = _service()
    try:
        coverage_default = service.mission_test_coverage()
        timeline = service.evolution_dashboard.mission_timeline()
        coverage_explicit = service.mission_test_coverage(timeline)
        assert coverage_default == coverage_explicit
    finally:
        db.close()


# --- readiness_report(): agregador puro ----------------------------------


def test_readiness_report_is_a_pure_aggregator_of_its_three_collaborators():
    service, db = _fake_service(
        snapshot={
            "unified_certified": True,
            "architecture_clean": True,
            "code_review_clean": True,
        },
        timeline=[{"mission_number": 59}],
        stress_clean=True,
        debt_total=42,
    )
    try:
        report = service.readiness_report()
        assert report["blocking_axes"]["unified_certified"] is True
        assert report["blocking_axes"]["architecture_clean"] is True
        assert report["blocking_axes"]["code_review_clean"] is True
        assert report["blocking_axes"]["stress_clean"] is True
        assert report["blocking_axes"]["mission_test_coverage_complete"] is True
        assert report["enterprise_ready"] is True
        assert report["tech_debt_summary"]["total_debt_items"] == 42
        assert service.evolution_dashboard.snapshot_calls == 1
        assert service.evolution_dashboard.timeline_calls == 1
    finally:
        db.close()


def test_readiness_report_never_recalculates_snapshot_axes_itself():
    """Os tres axes vindos de current_snapshot() sao repassados como
    estao - nunca reabertos/recalculados por este servico."""
    service, db = _fake_service(
        snapshot={
            "unified_certified": False,
            "architecture_clean": False,
            "code_review_clean": False,
        },
        timeline=[],
    )
    try:
        report = service.readiness_report()
        assert report["current_snapshot"]["unified_certified"] is False
        assert report["blocking_axes"]["unified_certified"] is False
        assert report["blocking_axes"]["architecture_clean"] is False
        assert report["blocking_axes"]["code_review_clean"] is False
    finally:
        db.close()


def test_readiness_report_against_the_real_repository_returns_well_typed_fields():
    service, db = _service()
    try:
        report = service.readiness_report()
        assert isinstance(report["enterprise_ready"], bool)
        for value in report["blocking_axes"].values():
            assert isinstance(value, bool)
        assert isinstance(report["mission_test_coverage"], dict)
        assert isinstance(report["timeline_health"], dict)
        assert isinstance(report["tech_debt_summary"], dict)
    finally:
        db.close()


# --- cada eixo bloqueante isoladamente derruba enterprise_ready ----------


def test_unified_certified_false_alone_blocks_enterprise_ready():
    service, db = _fake_service(
        snapshot={
            "unified_certified": False,
            "architecture_clean": True,
            "code_review_clean": True,
        },
        timeline=[],
    )
    try:
        report = service.readiness_report()
        assert report["enterprise_ready"] is False
        assert report["blocking_axes"]["architecture_clean"] is True
    finally:
        db.close()


def test_architecture_clean_false_alone_blocks_enterprise_ready():
    service, db = _fake_service(
        snapshot={
            "unified_certified": True,
            "architecture_clean": False,
            "code_review_clean": True,
        },
        timeline=[],
    )
    try:
        assert service.readiness_report()["enterprise_ready"] is False
    finally:
        db.close()


def test_code_review_clean_false_alone_blocks_enterprise_ready():
    service, db = _fake_service(
        snapshot={
            "unified_certified": True,
            "architecture_clean": True,
            "code_review_clean": False,
        },
        timeline=[],
    )
    try:
        assert service.readiness_report()["enterprise_ready"] is False
    finally:
        db.close()


def test_stress_clean_false_alone_blocks_enterprise_ready():
    service, db = _fake_service(
        snapshot={
            "unified_certified": True,
            "architecture_clean": True,
            "code_review_clean": True,
        },
        timeline=[],
        stress_clean=False,
    )
    try:
        assert service.readiness_report()["enterprise_ready"] is False
    finally:
        db.close()


def test_mission_test_coverage_incomplete_alone_blocks_enterprise_ready():
    service, db = _fake_service(
        snapshot={
            "unified_certified": True,
            "architecture_clean": True,
            "code_review_clean": True,
        },
        timeline=[{"mission_number": 99999}],
        stress_clean=True,
    )
    try:
        report = service.readiness_report()
        assert report["blocking_axes"]["mission_test_coverage_complete"] is False
        assert report["enterprise_ready"] is False
    finally:
        db.close()


def test_all_five_axes_true_makes_enterprise_ready_true():
    service, db = _fake_service(
        snapshot={
            "unified_certified": True,
            "architecture_clean": True,
            "code_review_clean": True,
        },
        timeline=[{"mission_number": 59}],
        stress_clean=True,
    )
    try:
        assert service.readiness_report()["enterprise_ready"] is True
    finally:
        db.close()


# --- eixos informativos nunca bloqueiam -----------------------------------


def test_timeline_health_gap_does_not_block_enterprise_ready():
    service, db = _fake_service(
        snapshot={
            "unified_certified": True,
            "architecture_clean": True,
            "code_review_clean": True,
        },
        timeline=[{"mission_number": 59}],
        health={
            "total_missions_detected": 1,
            "missing_mission_numbers": [1, 2, 3],
            "duplicate_mission_numbers": [],
        },
        stress_clean=True,
    )
    try:
        report = service.readiness_report()
        assert report["timeline_health"]["missing_mission_numbers"] == [1, 2, 3]
        assert "timeline_health" not in report["blocking_axes"]
        assert report["enterprise_ready"] is True
    finally:
        db.close()


def test_tech_debt_summary_never_appears_in_blocking_axes():
    service, db = _fake_service(
        snapshot={
            "unified_certified": True,
            "architecture_clean": True,
            "code_review_clean": True,
        },
        timeline=[{"mission_number": 59}],
        stress_clean=True,
        debt_total=999,
    )
    try:
        report = service.readiness_report()
        assert report["tech_debt_summary"]["total_debt_items"] == 999
        assert "tech_debt_summary" not in report["blocking_axes"]
        assert report["enterprise_ready"] is True
    finally:
        db.close()


# --- render_markdown() ----------------------------------------------------


def test_render_markdown_reports_enterprise_ready_verdict_when_true():
    service, db = _fake_service(
        snapshot={
            "unified_certified": True,
            "architecture_clean": True,
            "code_review_clean": True,
        },
        timeline=[{"mission_number": 59}],
        stress_clean=True,
    )
    try:
        text = service.render_markdown()
        assert "ENTERPRISE READY" in text
        assert "NAO PRONTO" not in text
    finally:
        db.close()


def test_render_markdown_reports_not_ready_verdict_when_false():
    service, db = _fake_service(
        snapshot={
            "unified_certified": False,
            "architecture_clean": True,
            "code_review_clean": True,
        },
        timeline=[],
    )
    try:
        text = service.render_markdown()
        assert "NAO PRONTO PARA ENTERPRISE" in text
        assert "`unified_certified`: FALHOU" in text
    finally:
        db.close()


def test_render_markdown_lists_missions_without_dedicated_suite_when_present():
    service, db = _fake_service(
        snapshot={
            "unified_certified": True,
            "architecture_clean": True,
            "code_review_clean": True,
        },
        timeline=[{"mission_number": 99999}],
        stress_clean=True,
    )
    try:
        text = service.render_markdown()
        assert "Missoes SEM suite dedicada" in text
        assert "99999" in text
    finally:
        db.close()


def test_render_markdown_includes_the_phase_omega_disclaimer():
    service, db = _service()
    try:
        text = service.render_markdown()
        assert "Fase Omega" in text
        assert "v1.1.0" in text
    finally:
        db.close()


def test_render_markdown_against_the_real_repository_does_not_crash():
    service, db = _service()
    try:
        text = service.render_markdown()
        assert "Certificacao de Prontidao Enterprise" in text
    finally:
        db.close()


# --- registro no container (igual M57, diferente de M55/M56/M58/M59) -----


def test_enterprise_readiness_service_is_registered_via_provide_unlike_m58_m59():
    assert "EnterpriseReadinessService" in registered_providers()


# --- endpoints HTTP --------------------------------------------------------


def test_enterprise_readiness_live_endpoint_returns_real_computed_report():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/enterprise-readiness/live")
        assert response.status_code == 200
        data = response.json()
        assert "enterprise_ready" in data
        assert "blocking_axes" in data
        assert "mission_test_coverage" in data


def test_enterprise_readiness_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/enterprise-readiness/markdown")
        assert response.status_code == 200
        assert "Certificacao de Prontidao Enterprise" in response.text


def test_enterprise_readiness_endpoint_is_overridable_via_container_not_hardcoded():
    class _StubReadiness:
        def readiness_report(self):
            return {"enterprise_ready": "stub-marker"}

        def render_markdown(self, report=None):
            return "stub markdown"

    real_app.dependency_overrides[get_enterprise_readiness_service] = lambda: _StubReadiness()
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/enterprise-readiness/live")
            assert response.json()["enterprise_ready"] == "stub-marker"
    finally:
        real_app.dependency_overrides.pop(get_enterprise_readiness_service, None)
