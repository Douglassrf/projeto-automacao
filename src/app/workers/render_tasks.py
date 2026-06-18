from __future__ import annotations

from app.schemas.premium_render import PremiumRenderRequest
from app.services.premium_render import PremiumRenderPipeline
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.render_tasks.run_premium_render", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def run_premium_render(payload: dict) -> dict:
    request = PremiumRenderRequest(**payload)
    response = PremiumRenderPipeline().render(request)
    return response.model_dump(mode="json")
