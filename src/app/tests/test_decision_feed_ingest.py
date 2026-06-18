from fastapi.testclient import TestClient

from app.main import app


def test_import_meta_csv_creates_real_decision_logs():
    csv_content = """campaign_id,campaign_name,spend,link clicks,landing page views,checkouts,purchases,roas
V2-AD01,Produto V2 AD01,60,300,120,4,0,0
V3-AD02,Produto V3 AD02,40,200,170,20,3,2.7
"""
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/logs/decisions/import-csv",
            files={"file": ("meta-export.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["rows_read"] == 2
        assert payload["decisions_created"] >= 3

        latest = client.get("/api/v1/logs/decisions?limit=20")
        assert latest.status_code == 200
        rows = latest.json()
        assert any(item["reason_code"] == "SPEND_WITHOUT_PURCHASE_CRITICAL" for item in rows)
        assert any(item["severity"] == "danger" for item in rows)
        assert any(item["reason_code"] == "ROAS_HEALTHY" for item in rows)


def test_crisis_stress_test_creates_red_timeline_events():
    with TestClient(app) as client:
        response = client.post("/api/v1/logs/decisions/stress-test/crisis")
        assert response.status_code == 200
        data = response.json()
        assert any(item["severity"] == "danger" for item in data)

        summary = client.get("/api/v1/logs/decisions/health-summary")
        assert summary.status_code == 200
        assert summary.json()["status"] in {"critical", "attention", "healthy"}
