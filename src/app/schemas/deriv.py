from pydantic import BaseModel, Field


class DerivStatusResponse(BaseModel):
    configured: bool
    mode: str
    endpoint: str
    app_id: str
    default_symbol: str
    can_trade: bool
    notes: list[str]


class DerivPingResponse(BaseModel):
    status: str
    mode: str
    response: dict


class DerivTickRequest(BaseModel):
    symbol: str | None = None


class DerivTickResponse(BaseModel):
    status: str
    mode: str
    symbol: str
    response: dict


class DerivProposalRequest(BaseModel):
    symbol: str | None = None
    amount: float = Field(default=1.0, gt=0)
    basis: str = "stake"
    contract_type: str = "CALL"
    currency: str | None = None
    duration: int = Field(default=5, gt=0)
    duration_unit: str = "t"
    dry_run: bool = True


class DerivProposalResponse(BaseModel):
    status: str
    mode: str
    dry_run: bool
    request: dict
    response: dict | None = None
    warnings: list[str]
