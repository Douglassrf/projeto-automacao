from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from app.integrations.activity_logger import AFFILIATE_ACTIVITY_LOG
from app.main import app


def _replace_link(index: int) -> int:
    payload = {
        "ad_id": index,
        "creative_original": f"Oferta simultânea {index}: https://produto.exemplo.com/oferta-{index}",
        "network": "generic",
        "user_affiliate_id": f"afiliado-{index}",
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/affiliate/replace-link", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["activity_logged"] is True
    assert f"aff_id=afiliado-{index}" in data["affiliate_link"]
    return response.status_code


def test_five_simultaneous_affiliate_replacements_are_logged():
    AFFILIATE_ACTIVITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    AFFILIATE_ACTIVITY_LOG.write_text("", encoding="utf-8")

    with ThreadPoolExecutor(max_workers=5) as executor:
        statuses = list(executor.map(_replace_link, range(1, 6)))

    assert statuses == [200, 200, 200, 200, 200]
    lines = [line for line in AFFILIATE_ACTIVITY_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 5

    with TestClient(app) as client:
        response = client.get("/api/v1/affiliate/activity", params={"limit": 10})

    assert response.status_code == 200
    activity = response.json()
    assert len(activity) == 5
    assert {str(item["ad_id"]) for item in activity} == {"1", "2", "3", "4", "5"}
