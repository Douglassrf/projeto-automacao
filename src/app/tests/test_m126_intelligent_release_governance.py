"""Missao 126 - Intelligent Release Governance.

Cobertura:
1. Cada um dos 5 requisitos isolado (passa quando o sinal real esta
   limpo, bloqueia quando nao esta) usando fakes com contador de
   chamadas - prova de reuso direto, nunca reimplementacao.
2. `validate_release()` agrega corretamente: `release_approved` so e
   True quando os 5 passam; `failed_requirements` lista exatamente os
   que falharam, ordenados.
3. `render_markdown()` - com tudo aprovado e com bloqueios.
4. Teste contra o repositorio real (sem mocks) - smoke test honesto,
   sem TestClient aninhado.
5. Registro real via `provide()` no container.
6. Endpoints HTTP `/live` e `/markdown`, incluindo teste de override de
   DI (prova que a rota nao esta hardcoded).
"""

from __future__ import annotations

from app.core.container import get_intelligent_release_governance_service, registered_providers
from app.db.session import SessionLocal
from app.main import app as real_app
from app.services.intelligent_release_governance_service import (
    IntelligentReleaseGovernanceService,
)
from fastapi.testclient import TestClient


def _service(**kwargs) -> IntelligentReleaseGovernanceService:
    db = SessionLocal()
    return IntelligentReleaseGovernanceService(db, **kwargs)


class _FakeEnterpriseReadiness:
    def __init__(self, complete: bool, missing: list[str] | None = None) -> None:
        self._complete = complete
        self._missing = missing or []
        self.calls = 0

    def mission_test_coverage(self) -> dict:
        self.calls += 1
        return {"complete": self._complete, "missions_without_dedicated_suite": self._missing}


class _FakeUnifiedCertification:
    def __init__(self, unified_certified: bool) -> None:
        self._unified_certified = unified_certified
        self.calls = 0

    def certify(self) -> dict:
        self.calls += 1
        return {
            "unified_certified": self._unified_certified,
            "platinum_certified": self._unified_certified,
            "gold_certified": self._unified_certified,
        }


class _FakeDependencyAudit:
    def __init__(self, missing_count: int = 0, version_mismatch_count: int = 0, unpinned_count: int = 0) -> None:
        self._missing_count = missing_count
        self._version_mismatch_count = version_mismatch_count
        self._unpinned_count = unpinned_count
        self.calls = 0

    def audit(self) -> dict:
        self.calls += 1
        return {
            "missing_count": self._missing_count,
            "version_mismatch_count": self._version_mismatch_count,
            "unpinned_count": self._unpinned_count,
            "issues": [],
        }


class _FakeDocumentation:
    def __init__(self, failed_routes: int = 0, settings_issues: list[str] | None = None) -> None:
        self._failed_routes = failed_routes
        self._settings_issues = settings_issues or []
        self.calls = 0

    def live_snapshot(self) -> dict:
        self.calls += 1
        return {
            "routes": {"declared": 5, "loaded": 5 - self._failed_routes, "failed": self._failed_routes},
            "settings_issues": self._settings_issues,
        }


# --- requisito: testes ------------------------------------------------------


def test_tests_requirement_passes_when_coverage_complete():
    fake = _FakeEnterpriseReadiness(complete=True)
    svc = _service(enterprise_readiness=fake)
    result = svc.tests_requirement()
    assert result["passed"] is True
    assert fake.calls == 1


def test_tests_requirement_blocks_when_coverage_incomplete():
    fake = _FakeEnterpriseReadiness(complete=False, missing=["999"])
    svc = _service(enterprise_readiness=fake)
    result = svc.tests_requirement()
    assert result["passed"] is False
    assert "1" in result["detail"]


# --- requisito: certificacoes ------------------------------------------------


def test_certifications_requirement_passes_when_unified_certified():
    fake = _FakeUnifiedCertification(unified_certified=True)
    svc = _service(unified_certification=fake)
    result = svc.certifications_requirement()
    assert result["passed"] is True
    assert fake.calls == 1


def test_certifications_requirement_blocks_when_not_unified_certified():
    fake = _FakeUnifiedCertification(unified_certified=False)
    svc = _service(unified_certification=fake)
    result = svc.certifications_requirement()
    assert result["passed"] is False


# --- requisito: seguranca (politica estrita: unpinned bloqueia) ------------


def test_security_requirement_passes_when_nothing_unpinned():
    fake = _FakeDependencyAudit(unpinned_count=0)
    svc = _service(dependency_audit=fake)
    result = svc.security_requirement()
    assert result["passed"] is True
    assert fake.calls == 1


def test_security_requirement_blocks_when_anything_unpinned():
    fake = _FakeDependencyAudit(unpinned_count=1)
    svc = _service(dependency_audit=fake)
    result = svc.security_requirement()
    assert result["passed"] is False


# --- requisito: documentacao -------------------------------------------------


def test_documentation_requirement_passes_when_clean():
    fake = _FakeDocumentation(failed_routes=0, settings_issues=[])
    svc = _service(documentation=fake)
    result = svc.documentation_requirement()
    assert result["passed"] is True
    assert fake.calls == 1


def test_documentation_requirement_blocks_on_failed_route():
    fake = _FakeDocumentation(failed_routes=1, settings_issues=[])
    svc = _service(documentation=fake)
    result = svc.documentation_requirement()
    assert result["passed"] is False


def test_documentation_requirement_blocks_on_settings_issue():
    fake = _FakeDocumentation(failed_routes=0, settings_issues=["jwt_secret_key padrao inseguro"])
    svc = _service(documentation=fake)
    result = svc.documentation_requirement()
    assert result["passed"] is False


# --- requisito: dependencias (missing/mismatch, distinto de seguranca) -----


def test_dependencies_requirement_passes_when_nothing_missing_or_mismatched():
    fake = _FakeDependencyAudit(missing_count=0, version_mismatch_count=0, unpinned_count=19)
    svc = _service(dependency_audit=fake)
    result = svc.dependencies_requirement()
    assert result["passed"] is True


def test_dependencies_requirement_blocks_on_missing():
    fake = _FakeDependencyAudit(missing_count=1)
    svc = _service(dependency_audit=fake)
    result = svc.dependencies_requirement()
    assert result["passed"] is False


def test_dependencies_requirement_blocks_on_version_mismatch():
    fake = _FakeDependencyAudit(version_mismatch_count=1)
    svc = _service(dependency_audit=fake)
    result = svc.dependencies_requirement()
    assert result["passed"] is False


def test_security_and_dependencies_each_call_audit_independently():
    fake = _FakeDependencyAudit()
    svc = _service(dependency_audit=fake)
    svc.security_requirement()
    svc.dependencies_requirement()
    assert fake.calls == 2


# --- agregacao: validate_release() ------------------------------------------


def test_validate_release_is_approved_when_all_five_pass():
    svc = _service(
        enterprise_readiness=_FakeEnterpriseReadiness(complete=True),
        unified_certification=_FakeUnifiedCertification(unified_certified=True),
        dependency_audit=_FakeDependencyAudit(),
        documentation=_FakeDocumentation(),
    )
    report = svc.validate_release()
    assert report["release_approved"] is True
    assert report["failed_requirements"] == []
    assert set(report["requirements"].keys()) == {
        "tests",
        "certifications",
        "security",
        "documentation",
        "dependencies",
    }


def test_validate_release_blocks_and_lists_exact_failed_requirements():
    svc = _service(
        enterprise_readiness=_FakeEnterpriseReadiness(complete=False),
        unified_certification=_FakeUnifiedCertification(unified_certified=True),
        dependency_audit=_FakeDependencyAudit(unpinned_count=3),
        documentation=_FakeDocumentation(),
    )
    report = svc.validate_release()
    assert report["release_approved"] is False
    assert report["failed_requirements"] == ["security", "tests"]


def test_validate_release_blocks_when_only_dependencies_axis_fails():
    svc = _service(
        enterprise_readiness=_FakeEnterpriseReadiness(complete=True),
        unified_certification=_FakeUnifiedCertification(unified_certified=True),
        dependency_audit=_FakeDependencyAudit(missing_count=2),
        documentation=_FakeDocumentation(),
    )
    report = svc.validate_release()
    assert report["release_approved"] is False
    assert report["failed_requirements"] == ["dependencies"]


# --- render_markdown ---------------------------------------------------------


def test_render_markdown_shows_release_approved_when_clean():
    svc = _service(
        enterprise_readiness=_FakeEnterpriseReadiness(complete=True),
        unified_certification=_FakeUnifiedCertification(unified_certified=True),
        dependency_audit=_FakeDependencyAudit(),
        documentation=_FakeDocumentation(),
    )
    text = svc.render_markdown()
    assert "RELEASE APROVADA" in text
    assert "BLOQUEANTE" not in text


def test_render_markdown_lists_blocking_requirements_when_present():
    svc = _service(
        enterprise_readiness=_FakeEnterpriseReadiness(complete=False),
        unified_certification=_FakeUnifiedCertification(unified_certified=True),
        dependency_audit=_FakeDependencyAudit(),
        documentation=_FakeDocumentation(),
    )
    text = svc.render_markdown()
    assert "RELEASE BLOQUEADA" in text
    assert "tests" in text
    assert "BLOQUEANTE" in text


# --- smoke test contra o repositorio real (sem mocks, sem TestClient) ------


def test_validate_release_against_real_repository_has_well_typed_fields():
    svc = _service()
    report = svc.validate_release()
    assert isinstance(report["release_approved"], bool)
    assert isinstance(report["failed_requirements"], list)
    for name in ("tests", "certifications", "security", "documentation", "dependencies"):
        assert name in report["requirements"]
        assert isinstance(report["requirements"][name]["passed"], bool)
    # render_markdown nao deve levantar excecao contra o relatorio real
    assert isinstance(svc.render_markdown(report), str)


# --- registro via container --------------------------------------------------


def test_intelligent_release_governance_service_is_registered_via_provide():
    assert "IntelligentReleaseGovernanceService" in registered_providers()


# --- endpoints HTTP -----------------------------------------------------------


def test_release_governance_live_endpoint_returns_real_computed_report():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/release-governance/live")
    assert response.status_code == 200
    body = response.json()
    assert "release_approved" in body
    assert "requirements" in body


def test_release_governance_markdown_endpoint_returns_text():
    with TestClient(real_app) as client:
        response = client.get("/api/v1/release-governance/markdown")
    assert response.status_code == 200
    assert "Governanca Inteligente de Release" in response.text or "Governança Inteligente de Release" in response.text


def test_release_governance_endpoint_is_overridable_via_container_not_hardcoded():
    fake_report = {
        "generated_at": "2026-06-28T00:00:00Z",
        "release_approved": True,
        "failed_requirements": [],
        "requirements": {},
    }

    class _StubService:
        def validate_release(self):
            return fake_report

    def _override():
        return _StubService()

    real_app.dependency_overrides[get_intelligent_release_governance_service] = _override
    try:
        with TestClient(real_app) as client:
            response = client.get("/api/v1/release-governance/live")
        assert response.json() == fake_report
    finally:
        del real_app.dependency_overrides[get_intelligent_release_governance_service]
