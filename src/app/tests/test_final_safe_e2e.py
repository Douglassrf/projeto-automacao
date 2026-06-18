from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _product_payload():
    return {
        "product_name": "Codex Final Safe E2E",
        "niche": "produto digital",
        "offer_promise": "Validar automacao de ponta a ponta sem ativar gasto",
        "target_avatar": "Operador que precisa de campanha segura",
        "main_pain": "Risco de publicar antes da homologacao",
        "desired_transformation": "Fluxo auditavel, pausado e sem gasto",
        "ticket_price": 27,
        "pixel_id": "966191649729251",
        "landing_page_url": "https://example.com/codex-final-safe-e2e",
        "checkout_url": "https://checkout.example.com/codex-final-safe-e2e",
        "affiliate_link": "https://checkout.example.com/codex-final-safe-e2e?aff=codex",
        "language": "pt",
        "geo_preset": "BRAZIL",
        "countries": ["BR"],
        "excluded_countries": [],
        "platform": "local-safe",
    }


def test_final_safe_e2e_without_real_meta_write(tmp_path):
    settings = get_settings()
    old_orch = settings.orchestration_output_dir
    settings.orchestration_output_dir = str(tmp_path / "orchestration")
    try:
        with TestClient(app) as client:
            miner = client.post(
                "/api/v1/miner/controlled-real",
                json={
                    "product_name": "Codex Final Safe E2E",
                    "niche": "produto digital",
                    "allow_external_call": False,
                    "ads": [
                        {
                            "title": "Anuncio seguro validado",
                            "copy": "Oferta clara, sem promessa absoluta, com CTA revisavel.",
                            "score": 8.5,
                        }
                    ],
                },
            )
            facebook_miner = client.post(
                "/api/v1/facebook-ad-miner/controlled-real",
                json={
                    "product_name": "Codex Final Safe E2E",
                    "niche": "produto digital",
                    "allow_external_call": False,
                    "use_browser": False,
                    "use_selenium": False,
                    "ads": [
                        {
                            "page_name": "Pagina Exemplo",
                            "ad_text": "Criativo local exportado para validacao controlada.",
                            "active_days": 12,
                        }
                    ],
                },
            )
            orchestration = client.post(
                "/api/v1/orchestration/run",
                json={"product": _product_payload(), "run_mode": "plan_only", "include_site": False, "include_video": False},
            )
            meta = client.post(
                "/api/v1/campaign-operator/v3/launch",
                json={
                    "product_name": "Codex Final Safe E2E",
                    "existing_campaign_id": "52616252576068",
                    "pixel_id": "966191649729251",
                    "landing_page_url": "https://example.com/codex-final-safe-e2e",
                    "affiliate_id": "demo-affiliate",
                    "geo_preset": "BRASIL",
                    "language": "Portuguese_All",
                    "excluded_countries": [],
                    "daily_budget_brl": 6,
                    "mode": "dry_run",
                    "creatives": [
                        {
                            "name": "AD01",
                            "media_type": "image",
                            "copy": "Teste seguro Codex: estrutura pausada validada sem ativar gasto.",
                        }
                    ],
                },
            )
    finally:
        settings.orchestration_output_dir = old_orch

    assert miner.status_code == 200, miner.text
    assert facebook_miner.status_code == 200, facebook_miner.text
    assert orchestration.status_code == 200, orchestration.text
    assert meta.status_code == 200, meta.text

    orchestration_data = orchestration.json()
    meta_data = meta.json()
    assert Path(orchestration_data["pipeline_json"]).exists()
    assert meta_data["dry_run"] is True
    assert meta_data["published"] == 0
    assert meta_data["blocked"] == 0
    assert meta_data["results"][0]["meta_campaign_id"] == "52616252576068"
    assert any(item["name"] == "existing_campaign_scope" and item["status"] == "ok" for item in meta_data["guardrails"])
    assert any(item["name"] == "meta_min_budget" and item["status"] == "ok" for item in meta_data["guardrails"])
