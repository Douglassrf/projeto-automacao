from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.schemas.release_candidate import ReleaseCandidateResponse
from app.services.release_candidate_service import get_release_candidate_service

router = APIRouter(prefix="/release-candidate", tags=["Release Candidate 1"])


@router.get("/live", response_model=ReleaseCandidateResponse)
def release_candidate_live():
    return get_release_candidate_service().rc1_report()


@router.get("/markdown", response_class=PlainTextResponse)
def release_candidate_markdown():
    return PlainTextResponse(content=get_release_candidate_service().render_markdown(), media_type="text/markdown")
