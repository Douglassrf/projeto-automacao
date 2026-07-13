from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _payload(**overrides):
    data = {
        "campaign_id": "campanha_teste_001",
        "adset_id": "conjunto_teste_001",
        "action": "pause_campaign",
        "target": "campaign",
        "reason_code": "ZERO_PURCHASE_GUARD",
        "metric_name": "spend_without_purchase",
        "metric_value": 25,
        "threshold_value": 25,
        "daily_spend_brl": 25,
        "current_purchases": 0,
        "confirmed_by_user": True,
        "force_dry_run": True,
    }
    data.update(overrides)
    return data


def test_automation_control_status():
    with TestClient(app) as client:
        response = client.get("/api/v1/automation-control/status")
    assert response.status_code == 200
    data = response.json()
    assert data["automation_level"] in [0, 1, 2]
    assert "notify_only" in data["allowed_actions"]


def test_level_zero_blocks_real_action_and_logs_decision(monkeypatch):
    # B007 (13/07/2026): o Kill Switch (ligado por padrão em .env.example) bloqueia
    # ANTES da checagem de nível, então esta ação já sairia bloqueada mesmo em
    # Nível >0. Para testar especificamente a regra de Nível 0 (isolada do Kill
    # Switch, que tem seu próprio teste abaixo), desligamos o Kill Switch aqui.
    monkeypatch.setenv("KILL_SWITCH_ENABLED", "false")
    # .env.example (raiz) define AUTOMATION_DAILY_SPEND_LIMIT_BRL=6 de proposito
    # (guardrail conservador) -- _payload() manda daily_spend_brl=25, que
    # estouraria esse limite antes mesmo de chegar na checagem de Nivel 0 que
    # este teste quer isolar. Sobe o teto so para este teste, sem mexer no
    # guardrail de producao nem no default seguro da classe (50.0).
    monkeypatch.setenv("AUTOMATION_DAILY_SPEND_LIMIT_BRL", "999")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/automation-control/apply-suggestion", json=_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["blocked"] is True
        assert data["action_executed"] is False
        assert data["decision_log_id"] is not None
        assert "Nível 0" in data["blocked_reason"]
    finally:
        get_settings.cache_clear()


def test_notify_only_is_allowed_in_level_zero(monkeypatch):
    # Mesma razão do teste acima: isola o comportamento de Nível 0 do Kill
    # Switch, que é testado separadamente em
    # test_kill_switch_blocks_notify_only_when_enabled.
    monkeypatch.setenv("KILL_SWITCH_ENABLED", "false")
    # Mesmo motivo do teste anterior: isola do limite conservador de
    # AUTOMATION_DAILY_SPEND_LIMIT_BRL=6 do .env.example.
    monkeypatch.setenv("AUTOMATION_DAILY_SPEND_LIMIT_BRL", "999")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/automation-control/apply-suggestion", json=_payload(action="notify_only"))
        assert response.status_code == 200
        data = response.json()
        assert data["blocked"] is False
        assert data["action_executed"] is False
        assert data["meta_response"]["status"] == "notified"
    finally:
        get_settings.cache_clear()


def test_kill_switch_blocks_notify_only_when_enabled(monkeypatch):
    # B007 — decisão explícita de Douglas (13/07/2026): o Kill Switch é o
    # freio de emergência mais externo e deve bloquear QUALQUER ação enquanto
    # ligado, inclusive notify_only (que só registra log, nunca toca a Meta).
    # Comportamento mais conservador, mantido de propósito — não é bug.
    monkeypatch.setenv("KILL_SWITCH_ENABLED", "true")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/automation-control/apply-suggestion", json=_payload(action="notify_only"))
        assert response.status_code == 200
        data = response.json()
        assert data["blocked"] is True
        assert data["action_executed"] is False
        assert "Kill Switch" in data["blocked_reason"]
    finally:
        get_settings.cache_clear()
