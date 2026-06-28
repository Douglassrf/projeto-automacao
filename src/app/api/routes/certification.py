from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.certification import CertificationResponse
from app.services.certification_service import CertificationService

router = APIRouter(prefix="/certification", tags=["Certificacao Platinum v1.3"])


@router.get("/platinum/live", response_model=CertificationResponse)
def certification_platinum_live(db: Session = Depends(get_db)):
    return CertificationService(db).certify()


@router.get("/platinum/markdown", response_class=PlainTextResponse)
def certification_platinum_markdown(db: Session = Depends(get_db)):
    markdown = CertificationService(db).render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
