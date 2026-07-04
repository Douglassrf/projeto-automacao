from fastapi import APIRouter, HTTPException, status

from app.integrations.deriv import DerivClient, DerivIntegrationError
from app.schemas.deriv import (
    DerivPingResponse,
    DerivProposalRequest,
    DerivProposalResponse,
    DerivStatusResponse,
    DerivTickRequest,
    DerivTickResponse,
)

router = APIRouter(prefix="/deriv", tags=["Deriv API"])


@router.get("/status", response_model=DerivStatusResponse)
def deriv_status():
    return DerivClient().status()


@router.post("/ping", response_model=DerivPingResponse)
def deriv_ping():
    try:
        response = DerivClient().ping()
    except DerivIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"status": "ok", "mode": "mock" if response.get("mock") else "real", "response": response}


@router.post("/ticks", response_model=DerivTickResponse)
def deriv_ticks(payload: DerivTickRequest):
    client = DerivClient()
    symbol = payload.symbol or client.default_symbol
    try:
        response = client.tick(symbol)
    except DerivIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"status": "ok", "mode": "mock" if response.get("mock") else "real", "symbol": symbol, "response": response}


@router.post("/proposal", response_model=DerivProposalResponse)
def deriv_proposal(payload: DerivProposalRequest):
    try:
        return DerivClient().proposal(payload)
    except DerivIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
