from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.domain.models import Campaign, CampaignMetric, PerformanceTicket, QueueJob
from app.main import app


def _seed_mission():
    db = SessionLocal()
    try:
        key = "mission-m04a-test"
        existing = db.query(Campaign).filter(Campaign.internal_campaign_id == key).first()
        if existing:
            return key
        campaign = Campaign(
            internal_campaign_id=key,
            product_name="M04A Test Product",
            status="ACTIVE",
            desired_status="PAUSED",
            real_status="PAUSED",
            target_roas=2.0,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        db.add(CampaignMetric(campaign_id=campaign.id, roas=3.2, spend=100, purchases=4, source="manual"))
        db.add(PerformanceTicket(campaign_id=campaign.id, severity="yellow", reason_code="needs_review", status="open"))
        db.add(QueueJob(queue_name="mission", job_type="monitoring", status="done", payload_json="{}", result_json="{}"))
        db.commit()
        return key
    finally:
        db.close()


def test_mission_planner_contract_uses_safe_steps():
    mission_id = _seed_mission()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/mission-orchestrator/planner?mission_id={mission_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["module"] == "mission_planner"
    assert data["will_execute_real_action"] is False
    assert [step["id"] for step in data["steps"]] == [
        "research_mining",
        "strategy_intelligence",
        "creatives",
        "site",
        "publication",
        "monitoring",
    ]


def test_mission_timeline_contract_is_read_only():
    mission_id = _seed_mission()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/mission-orchestrator/timeline/{mission_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["module"] == "mission_timeline"
    assert data["read_only"] is True
    assert any(event["source"] == "campaigns" for event in data["events"])


def test_mission_memory_contract_reads_existing_campaigns():
    _seed_mission()
    with TestClient(app) as client:
        response = client.get("/api/v1/mission-orchestrator/memory?limit=100")

    assert response.status_code == 200
    data = response.json()
    assert data["module"] == "mission_memory"
    assert data["read_only"] is True
    assert any(item["mission_id"] == "mission-m04a-test" for item in data["items"])


def test_mission_recovery_contract_does_not_execute_real_actions():
    mission_id = _seed_mission()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/mission-orchestrator/recovery/{mission_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["module"] == "mission_recovery"
    assert data["will_execute_real_action"] is False
    assert "skip_completed_states" in data["resume_policy"]


def test_mission_score_contract_uses_real_metrics():
    mission_id = _seed_mission()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/mission-orchestrator/score?mission_id={mission_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["module"] == "mission_score"
    assert data["inputs"]["latest_roas"] == 3.2
    assert 0 <= data["score"] <= 100


def test_mission_dashboard_contract_uses_dark_grid_layout():
    _seed_mission()
    with TestClient(app) as client:
        response = client.get("/api/v1/mission-orchestrator/dashboard/ui")

    assert response.status_code == 200
    data = response.json()
    assert data["module"] == "mission_dashboard"
    assert data["layout"] == {"theme": "dark", "grid": ["sidebar", "content", "rightbar"]}
    assert data["summary"]["module"] == "mission_score"


def test_mission_orchestrator_routes_require_authentication_when_enabled():
    settings = get_settings()
    previous = settings.auth_required
    settings.auth_required = True
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/mission-orchestrator/dashboard/ui")
        assert response.status_code == 401
    finally:
        settings.auth_required = previous
