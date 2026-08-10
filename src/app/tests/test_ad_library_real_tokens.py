from app.services import ad_library_real


def test_token_status_tries_all_candidates_until_one_is_valid(monkeypatch):
    monkeypatch.setenv("META_AD_LIBRARY_TOKEN", "expired-token")
    monkeypatch.setenv("chaveeeeeeeee", "valid-token")

    def fake_validate(value: str):
        if value == "valid-token":
            return {"valid": True, "reason": "ok", "message": "aceito"}
        return {"valid": False, "reason": "expired", "message": "expirado"}

    monkeypatch.setattr(ad_library_real, "validate_token", fake_validate)

    status = ad_library_real.token_status()

    assert status["token_valid"] is True
    assert status["source"] == "chaveeeeeeeee"
    assert status["candidates_available"] == [
        "META_AD_LIBRARY_TOKEN",
        "chaveeeeeeeee",
    ]


def test_token_status_reports_preferred_candidate_when_all_are_invalid(monkeypatch):
    monkeypatch.setenv("META_AD_LIBRARY_TOKEN", "expired-token")
    monkeypatch.setenv("chaveeeeeeee", "also-expired")
    monkeypatch.setattr(
        ad_library_real,
        "validate_token",
        lambda value: {"valid": False, "reason": "expired", "message": value},
    )

    status = ad_library_real.token_status()

    assert status["token_valid"] is False
    assert status["source"] == "META_AD_LIBRARY_TOKEN"
    assert status["message"] == "expired-token"
