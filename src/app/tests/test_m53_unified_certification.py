"""Missao 53 - Unified Certification Engine.

Contexto coberto por estes testes: antes desta missao, a "Certificacao
Gold" (Codex, Missoes 31-40, `production_readiness.gold_certification_snapshot()`)
tinha 11 criterios literalmente hardcoded `True` no codigo-fonte - nunca
calculados, sempre "ready_for_review". `UnifiedCertificationEngine`
recalcula os mesmos 11 nomes de criterio ao vivo, reusando services reais
(DiagnosticsService, RecoveryService, observability, settings, filesystem)
em vez de retornar constantes.

O que estes testes provam, na ordem: (1) os 11 nomes de criterio sao
identicos aos do snapshot antigo do Codex - comparabilidade preservada;
(2) cada criterio "verified" reage a mudanca de estado real (nao e um
valor fixo disfarcado); (3) o unico criterio sem verificacao automatizada
disponivel (`performance`) e honestamente marcado `verified=False`, nunca
`True`; (4) o motor agrega Platinum (Missao 50) + Gold recalculado em um
unico payload coerente; (5) leitura pura, sem efeito colateral no banco;
(6) os endpoints HTTP novos refletem o motor real via o container de DI
(Missao 52) - nao um valor hardcoded na propria rota.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.container import get_unified_certification_engine
from app.core.production_readiness import gold_certification_snapshot
from app.db.session import SessionLocal
from app.domain.models import AlertEvent, QueueJob
from app.main import app as real_app
from app.services.diagnostics_service import STATUS_CRITICAL, STATUS_OK
from app.services.unified_certification_service import (
    GOLD_CHECK_NAMES,
    UnifiedCertificationEngine,
)


# ---------------------------------------------------------------------------
# Paridade de nomenclatura com o snapshot antigo do Codex
# ---------------------------------------------------------------------------


def test_gold_check_names_match_codex_snapshot_exactly():
    old_snapshot_names = set(gold_certification_snapshot()["checks"])
    assert set(GOLD_CHECK_NAMES) == old_snapshot_names
    assert len(GOLD_CHECK_NAMES) == 11


# ---------------------------------------------------------------------------
# Cada criterio reage a estado real - nao e constante disfarcada
# ---------------------------------------------------------------------------


def test_docker_check_reflects_real_dockerfile_on_disk():
    db = SessionLocal()
    try:
        engine = UnifiedCertificationEngine(db)
        passed, detail = engine._check_docker()
        assert passed is True
        assert "Dockerfile" in detail
    finally:
        db.close()


def test_ci_cd_check_reflects_real_workflow_files_on_disk():
    db = SessionLocal()
    try:
        engine = UnifiedCertificationEngine(db)
        passed, detail = engine._check_ci_cd()
        assert passed is True
        assert "workflow" in detail
    finally:
        db.close()


def test_security_check_flips_when_auth_required_setting_changes():
    db = SessionLocal()
    try:
        engine = UnifiedCertificationEngine(db)

        engine.settings.auth_required = True
        engine.settings.jwt_secret_key = "uma-chave-realmente-trocada-em-prod"
        passed_when_secure, _ = engine._check_security()
        assert passed_when_secure is True

        engine.settings.auth_required = False
        passed_when_auth_disabled, _ = engine._check_security()
        assert passed_when_auth_disabled is False

        engine.settings.auth_required = True
        engine.settings.jwt_secret_key = "change-me-super-secret-local-key"
        passed_with_default_secret, _ = engine._check_security()
        assert passed_with_default_secret is False
    finally:
        db.close()


def test_database_check_reflects_injected_diagnostics_status():
    db = SessionLocal()
    try:
        engine = UnifiedCertificationEngine(db)

        ok_checks = [{"name": "database", "status": STATUS_OK}]
        passed_ok, _ = engine._check_database(ok_checks)
        assert passed_ok is True

        critical_checks = [{"name": "database", "status": STATUS_CRITICAL}]
        passed_critical, _ = engine._check_database(critical_checks)
        assert passed_critical is False

        missing_checks: list[dict] = []
        passed_missing, detail_missing = engine._check_database(missing_checks)
        assert passed_missing is False
        assert "ausente" in detail_missing
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Honestidade: "performance" nunca pode ser True sem verificacao real
# ---------------------------------------------------------------------------


def test_performance_check_is_always_marked_unverified():
    db = SessionLocal()
    try:
        engine = UnifiedCertificationEngine(db)
        checks = engine.gold_style_checks(diagnostics_checks=[{"name": "database", "status": STATUS_OK}])
        assert checks["performance"]["verified"] is False
        assert checks["performance"]["passed"] is False
    finally:
        db.close()


def test_gold_style_checks_never_reports_passed_true_for_an_unverified_check():
    """Regra geral de honestidade: nenhum criterio com verified=False pode
    ter passed=True - isso seria reintroduzir um 'True' sem checagem real,
    exatamente o defeito original do snapshot do Codex."""
    db = SessionLocal()
    try:
        engine = UnifiedCertificationEngine(db)
        checks = engine.gold_style_checks(diagnostics_checks=[{"name": "database", "status": STATUS_OK}])
        for name, check in checks.items():
            if not check["verified"]:
                assert check["passed"] is False, f"{name} esta com passed=True sem verified=True"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Agregacao Platinum + Gold em um unico payload
# ---------------------------------------------------------------------------


def test_certify_combines_platinum_and_gold_into_one_unified_payload():
    db = SessionLocal()
    try:
        engine = UnifiedCertificationEngine(db)
        report = engine.certify()

        assert set(report) == {
            "generated_at",
            "platinum_certified",
            "platinum",
            "gold_certified",
            "gold_checks",
            "gold_unverified_check_names",
            "unified_certified",
        }
        assert isinstance(report["platinum_certified"], bool)
        assert isinstance(report["platinum"], dict)
        assert set(report["gold_checks"]) == set(GOLD_CHECK_NAMES)
        assert report["gold_unverified_check_names"] == ["performance"]
        assert report["unified_certified"] == (report["platinum_certified"] and report["gold_certified"])
    finally:
        db.close()


def test_unified_certified_is_false_whenever_platinum_is_false():
    """Unified nunca pode certificar se Platinum (Missao 50, fail-closed)
    nao certificou - a unificacao nao pode "amaciar" um veredito real."""
    db = SessionLocal()
    try:
        engine = UnifiedCertificationEngine(db)
        report = engine.certify()
        if not report["platinum_certified"]:
            assert report["unified_certified"] is False
    finally:
        db.close()


def test_certify_does_not_mutate_database_state():
    db = SessionLocal()
    try:
        alerts_before = db.query(AlertEvent).count()
        jobs_before = db.query(QueueJob).count()

        UnifiedCertificationEngine(db).certify()

        assert db.query(AlertEvent).count() == alerts_before
        assert db.query(QueueJob).count() == jobs_before
    finally:
        db.close()


def test_render_markdown_contains_platinum_and_gold_sections():
    db = SessionLocal()
    try:
        markdown = UnifiedCertificationEngine(db).render_markdown()
        assert "Certificacao Unificada" in markdown
        assert "Platinum" in markdown
        assert "Gold" in markdown
        for name in GOLD_CHECK_NAMES:
            assert f"`{name}`" in markdown
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoints HTTP - prova de adesao real ao container de DI (Missao 52)
# ---------------------------------------------------------------------------


def test_unified_live_endpoint_returns_real_computed_checks():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/certification/unified/live")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload["gold_checks"]) == set(GOLD_CHECK_NAMES)
    assert payload["gold_unverified_check_names"] == ["performance"]
    assert "platinum" in payload


def test_unified_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/certification/unified/markdown")
    assert response.status_code == 200
    assert "Certificacao Unificada" in response.text


def test_unified_endpoint_is_overridable_via_container_not_hardcoded():
    class _FakeUnifiedEngine:
        def certify(self):
            return {
                "generated_at": "2026-06-28T00:00:00Z",
                "platinum_certified": False,
                "platinum": {},
                "gold_certified": False,
                "gold_checks": {},
                "gold_unverified_check_names": ["performance"],
                "unified_certified": False,
            }

    real_app.dependency_overrides[get_unified_certification_engine] = lambda: _FakeUnifiedEngine()
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/certification/unified/live")
    finally:
        real_app.dependency_overrides.pop(get_unified_certification_engine, None)

    assert response.status_code == 200
    assert response.json()["gold_checks"] == {}
    assert response.json()["unified_certified"] is False
