from fastapi import APIRouter

from app.schemas.final_readiness import FinalReadinessFullResponse
from app.services.final_readiness_service import FinalReadinessService

router = APIRouter(prefix="/final-readiness", tags=["Final Readiness v1.9"])


def _service() -> FinalReadinessService:
    return FinalReadinessService()


@router.get("/chaos-engineering")
def chaos_engineering():
    return _service().chaos_engineering()


@router.get("/data-integrity-certification")
def data_integrity_certification():
    return _service().data_integrity_certification()


@router.get("/security-red-team")
def security_red_team():
    return _service().security_red_team()


@router.get("/long-running-stability")
def long_running_stability():
    return _service().long_running_stability()


@router.get("/api-contract-lock")
def api_contract_lock():
    return _service().api_contract_lock()


@router.get("/disaster-recovery-drill")
def disaster_recovery_drill():
    return _service().disaster_recovery_drill()


@router.get("/uat")
def user_acceptance_test():
    return _service().user_acceptance_test()


@router.get("/production-readiness-board")
def production_readiness_board():
    return _service().production_readiness_board()


@router.get("/go-no-go")
def final_go_no_go():
    return _service().final_go_no_go()


@router.get("/full-certification", response_model=FinalReadinessFullResponse)
def full_certification():
    return _service().full_certification()
