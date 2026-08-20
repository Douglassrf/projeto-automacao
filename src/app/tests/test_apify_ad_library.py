from app.services import ad_library_real, apify_ad_library


def test_free_mode_caps_run_and_normalizes(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-token")
    monkeypatch.setenv("APIFY_FREE_MODE", "true")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{
                "adArchiveId": "ad-1",
                "pageId": "page-1",
                "pageName": "Loja Exemplo",
                "bodyText": "Texto do anuncio",
                "title": "Oferta",
                "platforms": ["facebook"],
            }]

    class Client:
        def __init__(self, *args, **kwargs):
            self.request = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, **kwargs):
            assert "token=" not in url
            assert kwargs["headers"]["Authorization"] == "Bearer test-token"
            assert kwargs["json"]["maxAds"] == 50
            return Response()

    monkeypatch.setattr(apify_ad_library.httpx, "Client", Client)
    result = apify_ad_library.fetch_ads("produto", country="BR", limit=300)

    assert result["status"] == "ok"
    assert result["free_mode"] is True
    assert result["applied_limit"] == 50
    assert result["ads"][0]["page_name"] == "Loja Exemplo"
    assert result["ads"][0]["ad_creative_bodies"] == ["Texto do anuncio"]


def test_search_uses_apify_provider_without_meta_token(monkeypatch):
    monkeypatch.setenv("AD_LIBRARY_PROVIDER", "apify")
    monkeypatch.delenv("META_AD_LIBRARY_TOKEN", raising=False)
    monkeypatch.setattr(
        apify_ad_library,
        "fetch_ads",
        lambda *args, **kwargs: {
            "status": "ok",
            "provider": "apify",
            "actor": "test/actor",
            "free_mode": True,
            "requested_limit": 20,
            "applied_limit": 20,
            "ads": [{
                "id": str(i),
                "page_id": "page-1",
                "page_name": "Loja Exemplo",
                "ad_creative_bodies": ["Texto"],
                "ad_creative_link_titles": ["Oferta"],
                "ad_snapshot_url": None,
            } for i in range(15)],
        },
    )

    result = ad_library_real.search_ad_library(
        "produto", currency="BRL", min_active_ads=15, limit=20
    )

    assert result["status"] == "ok"
    assert result["provider"] == "apify"
    assert result["mode"] == "real_ad_library_apify"
    assert result["winners_found"] == 1
    assert result["winners"][0]["classification"] == "BRONZE"


def test_missing_apify_token_is_honest(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    result = apify_ad_library.fetch_ads("produto", country="BR", limit=20)
    assert result["status"] == "error"
    assert result["error"] == "missing_apify_token"
