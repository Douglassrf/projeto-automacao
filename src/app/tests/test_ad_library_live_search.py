"""Missão 37V — testes do garimpo real de anúncio (Meta Ad Library API).

Nenhum destes testes faz uma requisição de rede real: o modo dry-run é
exercitado sem qualquer mock (é o comportamento padrão sem credencial), e o
modo "live" é exercitado com `httpx.get` mockado, provando que o parsing e a
normalização funcionam com um payload no formato real da Ad Library API sem
depender de internet disponível em CI/sandbox.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.ad_library_live_search import ad_library_search_live
from app.core.config import get_settings
from app.integrations.meta_marketing import MetaMarketingClient
from app.main import app

client = TestClient(app)


def test_search_ad_library_dry_run_returns_simulated_sample_without_network(monkeypatch):
    """Sem META_ACCESS_TOKEN / com META_DRY_RUN=true (padrão), nunca sai uma
    requisição real — e isso precisa ficar claramente marcado na resposta."""
    settings = get_settings()
    monkeypatch.setattr(settings, "meta_dry_run", True)
    monkeypatch.setattr(settings, "meta_access_token", None)

    def _fail_if_called(*args, **kwargs):  # pragma: no cover - só existe para provar que não é chamado
        raise AssertionError("httpx.get não deveria ser chamado em dry-run")

    monkeypatch.setattr("httpx.get", _fail_if_called)

    result = ad_library_search_live({"query": "curso de ingles", "countries": ["BR"], "limit": 1})

    assert result["status"] == "ad_library_live_search_ready"
    assert result["dry_run"] is True
    assert result["network_access_used"] is False
    assert result["results_count"] == 1
    assert result["results_preview"][0]["normalized_signal"]["platform"] == "meta"
    assert "meta_ad_library_api_dry_run_simulated" == result["source"]


def test_search_ad_library_requires_query():
    result = ad_library_search_live({"countries": ["BR"]})

    assert result["status"] == "blocked"
    assert "query_required" in result["blocked_reasons"]
    assert result["network_access_used"] is False


def test_search_ad_library_live_mode_parses_real_meta_response_shape(monkeypatch):
    """Com credenciais + dry_run=false, a chamada real deve usar o endpoint
    /ads_archive da Graph API e o resultado precisa ser corretamente
    normalizado pelo mesmo contrato usado no resto da Global Intelligence."""
    settings = get_settings()
    monkeypatch.setattr(settings, "meta_dry_run", False)
    monkeypatch.setattr(settings, "meta_access_token", "token-de-teste")
    monkeypatch.setattr(settings, "meta_ad_account_id", "123")
    monkeypatch.setattr(settings, "meta_page_id", "456")

    captured = {}

    class _FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {
                        "id": "123456789",
                        "page_name": "Loja Exemplo",
                        "ad_creative_bodies": ["Compre agora com 20% off"],
                        "ad_creative_link_titles": ["Frete gratis hoje"],
                        "ad_snapshot_url": "https://www.facebook.com/ads/library/?id=123456789",
                        "ad_delivery_start_time": "2026-07-01",
                        "languages": ["pt"],
                        "publisher_platforms": ["facebook", "instagram"],
                    }
                ],
                "paging": {},
            }

    def _fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse()

    monkeypatch.setattr("httpx.get", _fake_get)

    result = ad_library_search_live({"query": "frete gratis", "countries": ["BR"], "niche": "ecommerce"})

    assert "/ads_archive" in captured["url"]
    assert captured["params"]["search_terms"] == "frete gratis"

    assert result["status"] == "ad_library_live_search_ready"
    assert result["dry_run"] is False
    assert result["network_access_used"] is True
    assert result["results_count"] == 1
    signal = result["results_preview"][0]["normalized_signal"]
    assert signal["creative"]["headline"] == "Frete gratis hoje"
    assert signal["creative"]["body"] == "Compre agora com 20% off"
    assert result["results_preview"][0]["meta_ad_archive_id"] == "123456789"
    assert "não expõe métricas de performance" in result["notes"][0]


def test_search_ad_library_without_configured_credentials_stays_safe_even_with_dry_run_false(monkeypatch):
    """Mesmo que alguém force META_DRY_RUN=false, sem access_token + ad_account_id
    + page_id configurados o client.dry_run continua True (mesma regra usada em
    todo o resto do MetaMarketingClient) — então isto nunca deve tentar uma
    chamada de rede real nem vazar um MetaMarketingError por token ausente."""
    settings = get_settings()
    monkeypatch.setattr(settings, "meta_dry_run", False)
    monkeypatch.setattr(settings, "meta_access_token", None)

    def _fail_if_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError("httpx.get não deveria ser chamado sem credenciais configuradas")

    monkeypatch.setattr("httpx.get", _fail_if_called)

    client_obj = MetaMarketingClient()
    assert client_obj.dry_run is True

    result = client_obj.search_ad_library(search_terms="qualquer coisa")
    assert result["dry_run"] is True


def test_ad_library_search_live_endpoint_is_available():
    response = client.post(
        "/api/v1/global-intelligence/ad-library-search-live",
        json={"query": "emagrecimento", "countries": ["BR"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mission"] == "37V"
    assert data["will_execute_real_action"] is False
    assert data["will_activate_spend"] is False
