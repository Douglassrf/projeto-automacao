from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.container import get_certification_service, get_unified_certification_engine
from app.db.session import get_db
from app.schemas.certification import CertificationResponse
from app.services.certification_service import CertificationService
from app.services.unified_certification_service import UnifiedCertificationEngine

router = APIRouter(prefix="/certification", tags=["Certificacao Platinum v1.3"])


@router.get("/platinum/live", response_model=CertificationResponse)
def certification_platinum_live(
    certification: CertificationService = Depends(get_certification_service),
):
    return certification.certify()


@router.get("/platinum/markdown", response_class=PlainTextResponse)
def certification_platinum_markdown(
    certification: CertificationService = Depends(get_certification_service),
):
    markdown = certification.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")


@router.get("/unified/live")
def certification_unified_live(
    unified: UnifiedCertificationEngine = Depends(get_unified_certification_engine),
):
    """Missao 53 - retorna o veredito Platinum (Missao 50) e os 11
    criterios Gold (Codex, Missoes 31-40) recalculados ao vivo, em vez do
    snapshot hardcoded de `gold_certification_snapshot()`."""
    return unified.certify()


@router.get("/unified/markdown", response_class=PlainTextResponse)
def certification_unified_markdown(
    unified: UnifiedCertificationEngine = Depends(get_unified_certification_engine),
):
    markdown = unified.render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")


@router.get("/", include_in_schema=False)
def certification_root(db: Session = Depends(get_db)):
    return {"status": "ok"}
