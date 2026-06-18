from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.schemas.meta_operator import MetaOperatorLaunchRequest
from app.services.meta_campaign_operator import MetaCampaignOperator
from app.tests.test_meta_campaign_operator import _payload


class FakeRealMetaClient:
    dry_run = False
    credentials = SimpleNamespace(configured=True)

    def get_ad_account_spend_today_brl(self):
        return 0.0

    def publish_campaign_plan(self, plan):
        raise AssertionError("publish_campaign_plan nao deve ser chamado quando producao esta bloqueada")


def test_meta_environment_defaults_to_sandbox_profile():
    with TestClient(app) as client:
        response = client.get("/api/v1/campaign-operator/status")

    assert response.status_code == 200
    data = response.json()
    assert data["production_safety"]["meta_environment"] == "sandbox"
    assert data["production_safety"]["production_real_allowed"] is True


def test_meta_environment_blocks_main_production_without_unlock_flag():
    settings = get_settings()
    old = {
        "meta_env": settings.meta_env,
        "meta_allow_production_real": settings.meta_allow_production_real,
        "meta_autopublish": settings.meta_autopublish,
        "meta_dry_run": settings.meta_dry_run,
        "meta_require_manual_confirmation": settings.meta_require_manual_confirmation,
        "meta_access_token": settings.meta_access_token,
        "meta_ad_account_id": settings.meta_ad_account_id,
        "meta_page_id": settings.meta_page_id,
    }
    try:
        settings.meta_env = "production"
        settings.meta_allow_production_real = False
        settings.meta_autopublish = True
        settings.meta_dry_run = False
        settings.meta_require_manual_confirmation = False
        settings.meta_access_token = "test-token"
        settings.meta_ad_account_id = "123"
        settings.meta_page_id = "456"
        request = MetaOperatorLaunchRequest.model_validate(_payload(mode="publish_paused"))
        response = MetaCampaignOperator(meta_client=FakeRealMetaClient()).launch_v3(request)
    finally:
        for key, value in old.items():
            setattr(settings, key, value)

    assert response.dry_run is False
    assert response.blocked == 4
    assert any(item.name == "production_unlock" and item.status == "blocked" for item in response.guardrails)
