from app.integrations.deriv import DerivClient
from app.schemas.deriv import DerivProposalRequest


def test_deriv_status_starts_safe_in_mock_mode():
    status = DerivClient().status()

    assert status["configured"] is True
    assert status["mode"] == "mock"
    assert status["can_trade"] is False


def test_deriv_ping_uses_mock_echo_by_default():
    response = DerivClient().ping()

    assert response["mock"] is True
    assert response["echo_req"] == {"ping": 1}


def test_deriv_proposal_dry_run_builds_safe_payload_without_buying():
    response = DerivClient().proposal(
        DerivProposalRequest(symbol="R_100", amount=1, duration=5, dry_run=True)
    )

    assert response["status"] == "ready"
    assert response["dry_run"] is True
    assert response["request"]["proposal"] == 1
    assert response["request"]["symbol"] == "R_100"
    assert response["response"] is None
