import json

from fastapi.testclient import TestClient

from app.main import app
from app.services.final_readiness_service import FinalReadinessService


def test_chaos_engineering_degrades_and_recovers_without_corruption():
    report = FinalReadinessService().chaos_engineering()

    assert {item["scenario"] for item in report["scenarios"]} == {
        "database_unavailable",
        "meta_api_down",
        "disk_full",
        "low_memory",
        "unexpected_restart",
        "connection_loss",
    }
    assert report["controlled_degradation"] is True
    assert report["recovers_without_corruption"] is True
    assert all(item["data_corruption_detected"] is False for item in report["scenarios"])


def test_data_integrity_and_security_are_certified():
    service = FinalReadinessService()

    integrity = service.data_integrity_certification()
    security = service.security_red_team()

    assert integrity["corruption_count"] == 0
    assert integrity["checks"]["sqlite_consistency"] == "pragma_integrity_ok"
    assert security["critical_vulnerabilities"] == 0
    assert all(finding["critical_findings"] == 0 for finding in security["findings"])


def test_long_running_api_contract_dr_uat_and_board_are_green():
    service = FinalReadinessService()

    assert service.long_running_stability()["memory_leak_detected"] is False
    assert service.api_contract_lock()["compatibility_policy"] == "breaking_changes_require_new_major_version"
    assert service.disaster_recovery_drill()["complete_recovery"] is True
    assert service.user_acceptance_test()["accepted"] is True
    assert service.production_readiness_board()["board_decision"] == "approved_for_production"


def test_final_go_no_go_fails_closed_without_real_evidence(monkeypatch, tmp_path):
    missing_evidence = tmp_path / "missing-final-readiness-evidence.json"
    monkeypatch.setenv("FINAL_READINESS_EVIDENCE", str(missing_evidence))

    with TestClient(app) as client:
        response = client.get("/api/v1/final-readiness/full-certification")

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_decision"] == "NO_GO"
    assert payload["production_ready"] is False
    final = payload["sections"]["final_go_no_go"]
    assert set(final["blockers"]) == {
        "ci",
        "docker_o07",
        "pytest_full",
        "security",
        "o10",
        "pending_prs",
        "branch_protection",
        "e2e",
    }
    assert final["checklist"]["ci"]["reason"] == "Required evidence 'ci' is absent."


def test_final_go_no_go_only_goes_with_complete_green_evidence(monkeypatch, tmp_path):
    evidence_file = tmp_path / "final-readiness-evidence.json"
    evidence = {
        key: {
            "source": f"source/{key}",
            "evidence": f"evidence for {key}",
            "timestamp": "2026-06-29T00:00:00Z",
            "verdict": "PASS",
            "reason": f"{key} green with real evidence",
        }
        for key in (
            "ci",
            "docker_o07",
            "pytest_full",
            "security",
            "o10",
            "pending_prs",
            "branch_protection",
            "e2e",
        )
    }
    evidence_file.write_text(json.dumps(evidence), encoding="utf-8")
    monkeypatch.setenv("FINAL_READINESS_EVIDENCE", str(evidence_file))

    payload = FinalReadinessService().full_certification()

    assert payload["final_decision"] == "GO"
    assert payload["production_ready"] is True
    assert payload["sections"]["final_go_no_go"]["blockers"] == []
    assert all(item["verdict"] == "GO" for item in payload["sections"]["final_go_no_go"]["checklist"].values())
