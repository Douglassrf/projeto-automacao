from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.real_mode_gate import real_mode_readiness_gate
from app.core.operational_handoff import operational_handoff_checklist
from app.core.meta_sandbox_setup import meta_sandbox_setup_check
from app.core.first_sandbox_payload import first_sandbox_paused_payload
from app.core.sandbox_readiness import sandbox_readiness_report
from app.core.sandbox_execution_contract import sandbox_execution_contract
from app.core.security_brain_bridge import security_brain_review
from app.core.security_status import security_hardening_status
from app.domain.models import User

router = APIRouter(prefix="/security", tags=["Security Hardening"])


@router.get("/status")
def get_security_status(current_user: User = Depends(get_current_user)):
    return security_hardening_status()


@router.post("/real-mode-gate")
def post_real_mode_gate(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return real_mode_readiness_gate(payload)


@router.post("/brain-review")
def post_security_brain_review(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return security_brain_review(payload)


@router.post("/sandbox-readiness")
def post_sandbox_readiness(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return sandbox_readiness_report(payload)


@router.post("/sandbox-execution-contract")
def post_sandbox_execution_contract(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return sandbox_execution_contract(payload)


@router.get("/operational-handoff")
def get_operational_handoff(current_user: User = Depends(get_current_user)):
    return operational_handoff_checklist()


@router.post("/meta-sandbox-setup")
def post_meta_sandbox_setup(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return meta_sandbox_setup_check(payload)


@router.post("/first-sandbox-payload")
def post_first_sandbox_payload(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return first_sandbox_paused_payload(payload)
