from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.schemas.documentation_review import DocumentationReviewResponse
from app.services.documentation_review_service import get_documentation_review_service

router = APIRouter(prefix="/documentation-review", tags=["Final Documentation Review"])


@router.get("/live", response_model=DocumentationReviewResponse)
def documentation_review_live():
    return get_documentation_review_service().review_report()


@router.get("/markdown", response_class=PlainTextResponse)
def documentation_review_markdown():
    return PlainTextResponse(content=get_documentation_review_service().render_markdown(), media_type="text/markdown")
