from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.load_test_mission27a import DEFAULT_BATCHES, run_mission27a_load_test


def test_mission27a_default_batches_are_controlled_10_50_100():
    assert DEFAULT_BATCHES == (10, 50, 100)


def test_mission27a_load_test_records_metrics_and_trace_headers():
    report = run_mission27a_load_test(
        batches=(3, 5),
        concurrency=2,
        client_factory=lambda: TestClient(app),
        persist=True,
    )

    assert report["mission"] == "27A"
    assert report["safe_mode"] is True
    assert report["dry_run"] is True
    assert report["total_requests"] == 8
    assert report["failed_requests"] == 0
    assert report["error_rate_percent"] == 0.0
    assert report["trace_header_coverage_percent"] == 100.0
    assert report["latency_ms"]["p95"] >= 0
    assert Path(report["report_path"]).exists()
    assert report["brain_review"]["agent"] == "CampaignBrainAgent"


def test_mission27a_load_test_endpoint_accepts_small_safe_profile():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/observability/load-test/mission-27a",
            json={"batches": [2], "concurrency": 1, "persist": False},
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mission"] == "27A"
    assert data["total_requests"] == 2
    assert data["failed_requests"] == 0
    assert data["trace_header_coverage_percent"] == 100.0
