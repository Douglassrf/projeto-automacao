"""Domínio: Final Documentation Review (Missão 89)."""

from pydantic import BaseModel


class DocumentationReviewConfig(BaseModel):
    documentation_review_require_complete: bool = True
    documentation_review_include_ops: bool = True
