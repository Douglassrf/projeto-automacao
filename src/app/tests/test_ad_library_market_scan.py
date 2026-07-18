"""Missão 37W — testes do termômetro de recorrência.

Regra de negócio testada: um produto é sinalizado como "likely_winner_by_recurrence"
quando a mesma página de anunciante tem >= N variações de anúncio ativas ao
mesmo tempo (N definido pelo operador, default 15), escaneando os mercados
fortes (Euro/Dólar por padrão). Nenhum teste aqui depende de rede real.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.ad_library_market_scan import ad_library_market_scan
from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_market_scan_dry_run_flags_the_simulated_winner_cluster():
    """Em dry-run, o client simula um anunciante com 18 variações ativas
    (acima do limiar padrão de 15) e um anunciante fraco com só 2 — o scan
    precisa separar corretamente os dois."""
    result = ad_library_market_scan({"query": "creatina em po", "min_recurring_ads": 15})

    assert result["status"] == "winners_found"
    assert result["dry_run"] is True
    assert result["network_access_used"] is False
    assert result["geo_presets"] == ["EURO_TIER", "USD_TIER1", "BRASIL"]

    winners = result["likely_winners"]
    assert len(winners) >= 1
    assert all(w["active_ads_found"] >= 15 for w in winners)
    assert all("Vencedor" in w["page_name"] for w in winners)

    losers = [c for c in result["candidates"] if c["verdict"] == "insufficient_recurrence"]
    assert any("Fraco" in loser["page_name"] for loser in losers)

    assert "HEUR" in result["heuristic_disclaimer"].upper()


def test_market_scan_requires_query():
    result = ad_library_market_scan({})

    assert result["status"] == "blocked"
    assert "query_required" in result["blocked_reasons"]


def test_market_scan_rejects_unknown_geo_preset():
    result = ad_library_market_scan({"query": "x", "geo_presets": ["MARTE"]})

    assert result["status"] == "blocked"
    assert any("unknown_geo_preset" in reason for reason in result["blocked_reasons"])


def test_market_scan_respects_custom_threshold():
    """Com limiar 20 (o outro número que o Douglas mencionou), o cluster
    simulado de 18 deixa de ser suficiente."""
    result = ad_library_market_scan({"query": "creatina em po", "min_recurring_ads": 20})

    assert result["likely_winners"] == []
    assert all(c["active_ads_found"] < 20 for c in result["candidates"] if c["verdict"] != "likely_winner_by_recurrence")


def test_market_scan_live_mode_groups_and_counts_per_page(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "meta_dry_run", False)
    monkeypatch.setattr(settings, "meta_access_token", "token-de-teste")
    monkeypatch.setattr(settings, "meta_ad_account_id", "123")
    monkeypatch.setattr(settings, "meta_page_id", "456")

    def _make_ad(idx, page_name):
        return {
            "id": f"ad_{page_name}_{idx}",
            "page_name": page_name,
            "ad_creative_bodies": [f"corpo {idx}"],
            "ad_creative_link_titles": [f"titulo {idx}"],
            "ad_snapshot_url": "https://example.com/snap",
        }

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            # 16 anuncios da "Marca Forte" + 3 da "Marca Fraca" em CADA mercado
            ads = [_make_ad(i, "Marca Forte") for i in range(16)]
            ads += [_make_ad(i, "Marca Fraca") for i in range(3)]
            return {"data": ads, "paging": {}}

    monkeypatch.setattr("httpx.get", lambda url, params=None, timeout=None: _FakeResponse())

    result = ad_library_market_scan({"query": "colageno", "geo_presets": ["EURO_TIER"], "min_recurring_ads": 15})

    assert result["dry_run"] is False
    assert result["network_access_used"] is True
    winners = result["likely_winners"]
    assert len(winners) == 1
    assert winners[0]["page_name"] == "Marca Forte"
    assert winners[0]["active_ads_found"] == 16
    assert winners[0]["geo_preset"] == "EURO_TIER"

    losers = [c for c in result["candidates"] if c["page_name"] == "Marca Fraca"]
    assert losers[0]["verdict"] == "insufficient_recurrence"


def test_ad_library_market_scan_endpoint_is_available():
    response = client.post(
        "/api/v1/global-intelligence/ad-library-market-scan",
        json={"query": "whey protein", "min_recurring_ads": 15},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mission"] == "37W"
    assert data["will_execute_real_action"] is False
    assert data["will_activate_spend"] is False
