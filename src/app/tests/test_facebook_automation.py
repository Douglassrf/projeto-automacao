from fastapi.testclient import TestClient

from app.main import app


def _item(active_ads=28):
    return {
        "external_id": "fb-test-1",
        "product_name": "PDF Teste Facebook",
        "creative_original": "Oferta validada: https://checkout.exemplo.com/teste",
        "destination_url": "https://checkout.exemplo.com/teste",
        "active_ads": active_ads,
        "cpc": 1.1,
        "ctr": 2.2,
        "cpm": 22,
        "spend": 100,
        "revenue": 260,
        "link_clicks": 200,
        "landing_page_views": 170,
        "checkout_starts": 60,
        "purchases": 8,
    }


def test_v1_strategy_marks_winner():
    with TestClient(app) as client:
        response = client.post("/api/v1/facebook/v1/strategy", json={"items": [_item()]})
    assert response.status_code == 200
    data = response.json()
    assert data["winners"] == 1
    assert data["decisions"][0]["decision"] == "winner"


def test_v2_generates_campaign_plan_with_affiliate_link():
    with TestClient(app) as client:
        response = client.post("/api/v1/facebook/v2/campaign-plan", json={"affiliate_id": "fb-aff", "items": [_item()]})
    assert response.status_code == 200
    data = response.json()
    assert data["approved_for_plan"] == 3
    assert "aff_id=fb-aff" in data["plans"][0]["affiliate"]["affiliate_link"]
    assert data["plans"][0]["manual_review_required"] is False
    assert {plan["campaign_model"] for plan in data["plans"]} == {"V1_VALIDACAO", "V2_ESCALA_CONTROLADA", "V3_AUTOMACAO_PRINCIPAL"}


def test_v3_execute_is_dry_run_or_review_blocked_by_default():
    with TestClient(app) as client:
        response = client.post("/api/v1/facebook/v3/execute", json={"items": [_item()], "publish_to_meta": True})
    assert response.status_code == 200
    data = response.json()
    assert data["attempted"] == 3
    assert data["published"] == 0
    assert data["results"][0]["status"] in {"blocked_for_manual_review", "simulated"}
    assert any(result["campaign_model"] == "V3_AUTOMACAO_PRINCIPAL" for result in data["results"])


def test_v2_dedicated_simulation_matches_four_creative_structure():
    payload = {
        "product_name": "Produto Digital LATAM",
        "pixel_id": "1234567890",
        "destination_url": "https://checkout.exemplo.com/produto",
        "primary_text": "Compra ahora y accede al método completo.",
        "daily_budget_brl": 50,
        "creatives": [
            {"ad_name": "AD01", "media_name": "criativo-01.mp4", "media_type": "video"},
            {"ad_name": "AD02", "media_name": "criativo-02.mp4", "media_type": "video"},
            {"ad_name": "AD03", "media_name": "criativo-03.jpg", "media_type": "image"},
            {"ad_name": "AD04", "media_name": "criativo-04.jpg", "media_type": "image"},
        ],
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/facebook/v2/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["campaign_name"] == "Produto Digital LATAM V2"
    assert data["daily_budget_brl"] == 50
    assert data["structure_valid"] is True
    assert len(data["ads"]) == 4
    assert [ad["ad_name"] for ad in data["ads"]] == ["AD01", "AD02", "AD03", "AD04"]
    assert all(ad["same_copy"] and ad["same_link"] and ad["media_original_format"] for ad in data["ads"])
    assert data["targeting"]["geo_locations"]["countries"] == ["AR", "CL", "CO", "PE", "MX", "EC"]
    assert data["targeting"]["excluded_geo_locations"]["countries"] == ["BR"]
    assert data["targeting"]["user_device_connection"] == "wifi_only"


def _subniches(count):
    return [
        {
            "name": f"Subnicho {i}",
            "audience_pain": f"dor específica {i}",
            "promise_angle": f"promessa direta {i}",
            "media_direction": "UGC com benefício claro",
        }
        for i in range(1, count + 1)
    ]


def test_campaign_suite_builds_v1_v2_v3_as_distinct_campaigns_with_required_subniches():
    payload = {
        "product_name": "Produto Digital Campeão",
        "pixel_id": "px-12345",
        "material": {
            "pdf_title": "Guia Produto Digital Campeão",
            "landing_page_url": "https://exemplo.com/pagina",
            "checkout_url": "https://exemplo.com/checkout",
            "language": "Spanish (All)",
            "main_copy": "Compra ahora y accede al método completo.",
            "product_description": "Material educativo com passo a passo.",
        },
        "language": "Spanish (All)",
        "v1_subniches": _subniches(5),
        "v2_subniches": _subniches(4),
        "v3_subniches": _subniches(5),
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/facebook/campaign-suite/build", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_campaigns"] == 3
    assert data["total_adsets"] == 14
    assert data["total_ads"] == 14
    by_type = {campaign["campaign_type"]: campaign for campaign in data["campaigns"]}
    assert by_type["V1"]["total_adsets"] == 5
    assert by_type["V2"]["total_adsets"] == 4
    assert by_type["V3"]["total_adsets"] == 5
    assert by_type["V1"]["campaign_name"] == "Produto Digital Campeão V1"
    assert by_type["V2"]["campaign_name"] == "Produto Digital Campeão V2"
    assert by_type["V3"]["campaign_name"] == "Produto Digital Campeão V3"
    first_adset = by_type["V1"]["adsets"][0]
    assert first_adset["conversion_event"] == "Purchase"
    assert first_adset["pixel_id"] == "px-12345"
    assert len(first_adset["assets"]) == 4
    assert {asset["asset_type"] for asset in first_adset["assets"]} == {"pdf_content", "image", "video", "ad_copy"}
