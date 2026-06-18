from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def test_sqlite_queue_lifecycle_via_api():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/queue/jobs",
            json={
                "queue_name": "render",
                "job_type": "video_render",
                "payload": {"product": "Demo", "duration": 15},
                "priority": 10,
                "max_attempts": 2,
            },
        )
        assert response.status_code == 200
        job = response.json()
        assert job["status"] == "queued"
        assert job["payload"]["product"] == "Demo"

        claim = client.post("/api/v1/queue/jobs/claim", json={"queue_name": "render", "worker_id": "worker-1", "limit": 1})
        assert claim.status_code == 200
        claimed = claim.json()[0]
        assert claimed["status"] == "running"
        assert claimed["attempts"] >= 1

        complete = client.post(f"/api/v1/queue/jobs/{claimed['id']}/complete", json={"result": {"file": "out.mp4"}})
        assert complete.status_code == 200
        assert complete.json()["status"] == "done"
        assert complete.json()["result"]["file"] == "out.mp4"


def test_sqlite_queue_retry_then_dead_via_api():
    queue_name = f"meta-{uuid4().hex[:8]}"
    with TestClient(app) as client:
        created = client.post("/api/v1/queue/jobs", json={"queue_name": queue_name, "job_type": "publish", "payload": {}, "max_attempts": 1}).json()
        claimed = client.post("/api/v1/queue/jobs/claim", json={"queue_name": queue_name, "worker_id": "worker-1", "limit": 1}).json()[0]
        assert claimed["id"] == created["id"]

        failed = client.post(f"/api/v1/queue/jobs/{claimed['id']}/fail", json={"error_message": "Meta API timeout", "retry": True})
        assert failed.status_code == 200
        assert failed.json()["status"] == "dead"
        assert failed.json()["error_message"] == "Meta API timeout"


def test_queue_stats_via_api():
    with TestClient(app) as client:
        client.post("/api/v1/queue/jobs", json={"queue_name": "default", "job_type": "content", "payload": {}})
        stats = client.get("/api/v1/queue/stats")
        assert stats.status_code == 200
        data = stats.json()
        assert data["backend"] in {"sqlite", "keydb"}
        assert data["total"] >= 1
        assert "recommendation" in data
