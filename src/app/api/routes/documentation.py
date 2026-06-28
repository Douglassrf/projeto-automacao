from fastapi.responses import PlainTextResponse
from fastapi import APIRouter

from app.schemas.documentation import DocumentationSnapshotResponse
from app.services.documentation_service import DocumentationService

router = APIRouter(prefix="/documentation", tags=["Documentacao Viva"])


@router.get("/live", response_model=DocumentationSnapshotResponse)
def documentation_live():
    return DocumentationService().live_snapshot()


@router.get("/markdown", response_class=PlainTextResponse)
def documentation_markdown():
    markdown = DocumentationService().render_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")
