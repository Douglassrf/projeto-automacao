from fastapi.testclient import TestClient

from app.core.winning_ad_score import winning_ad_score
from app.main import app


def test_winning_ad_score_scores_strong_signal_without_execution():
    result = winning_ad_score(
        {
            "platform": "google",
            "country": "US",
            "headline": "Stop wasting ad budget",
            "body": "Find winning creative before scaling your next campaign.",
            "cta": "SIGN_UP",
            "format": "short_video",
            "landing_url": "https://example.com",
            "domain": "example.com",
            "impressions": 1000,
            "clicks": 80,
            "spend": 40,
            "leads": 8,
            "niche": "saas",
            "ticket": 99,
            "trend_score": 85,
        }
    )

    assert result["status"] == "scored"
    assert result["will_execute_real_action"] is False
    assert result["score"]["global_score"] >= 80
    assert result["score"]["verdict"] == "likely_winner"
    assert result["brian_learning"]["stored"]["status"] == "stored"


def test_winning_ad_score_blocks_invalid_signal():
    result = winning_ad_score({"platform": "unknown", "headline": "", "body": ""})

    assert result["status"] == "blocked"
    assert result["score"] is None
    assert "unsupported_platform" in result["blocked_reasons"]


def test_winning_ad_score_endpoint_is_available():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/global-intelligence/winning-ad-score",
            json={"platform": "meta", "headline": "Headline boa", "body": "Texto bom para teste", "impressions": 10},
        )

    assert response.status_code == 200
    assert response.json()["mission"] == "37C"
