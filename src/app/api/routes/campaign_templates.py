from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.hypothesis_test_template import hypothesis_test_01_template
from app.domain.models import User

router = APIRouter(prefix="/campaign-templates", tags=["Campaign Templates"])


@router.post("/hypothesis-test-01")
def post_hypothesis_test_01(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return hypothesis_test_01_template(payload)
