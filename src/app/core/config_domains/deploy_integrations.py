"""Domínio: integrações de deploy (GitHub, Vercel, Netlify)."""

from pydantic import BaseModel


class DeployIntegrationsConfig(BaseModel):
    github_token: str | None = None
    github_owner: str | None = None
    vercel_token: str | None = None
    vercel_team_id: str | None = None
    netlify_token: str | None = None
