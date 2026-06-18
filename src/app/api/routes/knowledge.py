from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.knowledge import KnowledgeFileResponse, KnowledgeSummaryResponse
from app.services.knowledge_engine import KnowledgeEngineError, get_knowledge_engine

router = APIRouter(prefix="/knowledge", tags=["Marketing Knowledge Core"])


@router.get("/summary", response_model=KnowledgeSummaryResponse)
def knowledge_summary(current_user: User = Depends(get_current_user)):
    engine = get_knowledge_engine()
    try:
        all_files = engine.load_all()
        return KnowledgeSummaryResponse(
            files=sorted(all_files.keys()),
            campaign_models=engine.campaign_models(),
            guardrails=engine.guardrails(),
            connect_rate_warning_below=engine.connect_rate_warning_below(),
        )
    except KnowledgeEngineError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{name}", response_model=KnowledgeFileResponse)
def knowledge_file(name: str, current_user: User = Depends(get_current_user)):
    engine = get_knowledge_engine()
    try:
        return KnowledgeFileResponse(name=name, content=engine.load(name))
    except KnowledgeEngineError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
