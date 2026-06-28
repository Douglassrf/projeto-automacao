"""Domínio: API Compatibility Center (Missão 76)."""

from pydantic import BaseModel


class ApiCompatibilityConfig(BaseModel):
    # Missao 76 - API Compatibility Center
    api_compatibility_enforce_deprecation_policy: bool = True
