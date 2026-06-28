"""Domínio: workers enterprise, observabilidade e render premium."""

from pydantic import BaseModel


class EnterpriseObservabilityConfig(BaseModel):
    celery_enabled: bool = False
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    render_worker_queue: str = "render-premium"
    sentry_dsn: str | None = None
    observability_enabled: bool = True
    observability_log_level: str = "INFO"
    premium_render_output_dir: str = "/data/premium_renders"
    premium_render_dry_run: bool = True
    premium_render_provider_image: str = "local_ffmpeg"
    premium_render_provider_video: str = "local_ffmpeg"
    premium_render_upscale_enabled: bool = True
    premium_render_color_lut: str = "warm_contrast"
