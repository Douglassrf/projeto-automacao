from fastapi import APIRouter

from app.schemas.site_builder import SiteGenerateRequest
from app.services.site_builder_bridge import SiteBuilderBridge
from app.core.route_security import site_publish_security_guard

router = APIRouter(prefix="/site-builder", tags=["site-builder"])


@router.get("/health")
def health():
    return {"ok": True, "module": "site_builder"}


@router.post("/generate")
def generate(payload: SiteGenerateRequest):
    guard = site_publish_security_guard(payload.model_dump(mode="json"))
    result = SiteBuilderBridge().safe_generate(
        payload=payload,
        product_name=payload.offer.product_name,
        niche=payload.offer.niche,
    )
    site = result["site_builder"]
    return {
        "product_name": site["product_name"],
        "template": site["template"],
        "output_dir": site["output_dir"],
        "preview_path": site["preview_path"],
        "files": [path.split("\\")[-1].split("/")[-1] for path in site["files"]],
        "deploy_provider": site["deploy_provider"],
        "deploy_status": site["deploy_status"],
        "deploy_url": None,
        "deploy_payload_path": site["deploy_payload_path"],
        "warnings": site["warnings"],
        "security_guard": guard,
    }
