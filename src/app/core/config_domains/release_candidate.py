"""Domínio: Release Candidate 1 (Missão 85)."""

from pydantic import BaseModel


class ReleaseCandidateConfig(BaseModel):
    rc1_freeze_enabled: bool = True
    rc1_require_checklist: bool = True
