"""Domínio: CI/CD Stabilization (Missão 82)."""

from pydantic import BaseModel


class CiStabilizationConfig(BaseModel):
    # Missao 82 - CI/CD Stabilization: gate fail-closed para pipeline verde.
    # Quando True (padrao), verdict so e READY se workflows e testes criticos
    # estiverem saudaveis. Nunca False em producao.
    ci_cd_require_green_pipeline: bool = True
    ci_cd_skip_ffmpeg_on_windows: bool = True
