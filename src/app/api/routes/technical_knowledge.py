from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.technical_knowledge import TechnicalKnowledgeResponse
from app.services.technical_knowledge_service import TechnicalKnowledgeService

router = APIRouter(
    prefix="/technical-knowledge",
    tags=["Technical Knowledge Base"],
)


@router.get("/base/live", response_model=TechnicalKnowledgeResponse)
def technical_knowledge_base_live(db: Session = Depends(get_db)):
    return TechnicalKnowledgeService(db).knowledge_base()


@router.get("/base/markdown", response_class=PlainTextResponse)
def technical_knowledge_base_markdown(db: Session = Depends(get_db)):
    markdown = TechnicalKnowledgeService(db).render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
