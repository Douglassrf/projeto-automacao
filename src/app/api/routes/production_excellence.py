from typing import Any

from fastapi import APIRouter

from app.schemas.production_excellence import ProductionExcellenceFullResponse, ProductionExcellenceResponse
from app.services.production_excellence_service import ProductionExcellenceService

router = APIRouter(prefix="/production-excellence", tags=["Production Excellence v1.8"])


def _service() -> ProductionExcellenceService:
    return ProductionExcellenceService()


@router.get("/monitoring-center", response_model=ProductionExcellenceResponse)
def monitoring_center():
    return _service().monitoring_center()


@router.get("/incidents")
def incident_history():
    return {"incidents": _service().incident_history()}


@router.post("/incidents/classify")
def classify_incident(signal: dict[str, Any]):
    return _service().classify_incident(signal)


@router.get("/service-levels")
def service_levels():
    return _service().service_levels()


@router.get("/capacity-planning")
def capacity_planning():
    return _service().capacity_planning()


@router.get("/analytics")
def operational_analytics():
    return _service().operational_analytics()


@router.get("/compliance")
def continuous_compliance():
    return _service().compliance()


@router.get("/knowledge-center")
def knowledge_center():
    return _service().knowledge_center()


@router.get("/maintenance-planner")
def maintenance_planner():
    return _service().maintenance_planner()


@router.get("/executive-governance")
def executive_governance():
    return _service().executive_governance()


@router.get("/certification")
def production_certification():
    return _service().production_certification()


@router.get("/full-center", response_model=ProductionExcellenceFullResponse)
def full_center():
    return _service().full_center()
