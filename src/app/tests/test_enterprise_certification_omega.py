from app.core.enterprise_certification import (
    complete_audit_report,
    douglas_gold_certification,
    omega_enterprise_report,
    security_engineering_report,
)
from app.main import app
from fastapi.testclient import TestClient


def test_omega_enterprise_report_contains_all_missions():
    report = omega_enterprise_report()
    assert report["missions"]["omega13"]["mission"] == "Ω13"
    assert report["missions"]["omega14"]["objective"] == "Funciona em qualquer computador"
    assert report["missions"]["omega20"]["status"] == "NÃO HOMOLOGADO"


def test_douglas_gold_never_partially_homologates():
    partial = douglas_gold_certification({"codigo_aprovado": True})
    assert partial["status"] == "NÃO HOMOLOGADO"
    assert "testes_aprovados" in partial["motivo"]

    full = douglas_gold_certification(
        {
            "codigo_aprovado": True,
            "testes_aprovados": True,
            "docker_aprovado": True,
            "github_aprovado": True,
            "release_publicada": True,
            "performance_aprovada": True,
            "seguranca_aprovada": True,
            "observabilidade_aprovada": True,
            "instalacao_limpa_aprovada": True,
            "auditoria_aprovada": True,
        }
    )
    assert full["status"] == "PROJETO HOMOLOGADO"


def test_audit_and_security_reports_are_structured():
    audit = complete_audit_report()
    security = security_engineering_report()
    assert set(audit["findings"]) >= {"rotas_orfas", "todos_esquecidos", "duplicacoes_arquivo"}
    assert "sbom" in security
    assert security["artifact_signature"] == security["integrity_sha256"]


def test_enterprise_certification_routes():
    client = TestClient(app)
    response = client.get("/api/v1/enterprise-certification/omega-report")
    assert response.status_code == 200
    assert response.json()["missions"]["omega18"]["panel"]["professional_mode"] is True

    response = client.post("/api/v1/enterprise-certification/douglas-gold", json={"gates": {"codigo_aprovado": True}})
    assert response.status_code == 200
    assert response.json()["status"] == "NÃO HOMOLOGADO"
