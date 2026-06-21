from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app


def test_health_reports_database_ok():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["database"] == "ok"


def test_health_reports_503_when_database_unavailable(monkeypatch):
    class BrokenConnection:
        def __enter__(self):
            raise OperationalError("SELECT 1", {}, Exception("db unavailable"))

        def __exit__(self, exc_type, exc, tb):
            return False

    class BrokenEngine:
        def connect(self):
            return BrokenConnection()

    monkeypatch.setattr("app.main.engine", BrokenEngine())

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["database"] == "unavailable"
    assert body["detail"] == "OperationalError"
