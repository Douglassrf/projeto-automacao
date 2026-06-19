from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.domain.models import User
from app.schemas.site_builder import SiteGenerateRequest
from app.services.observability import immutable_audit_event
from app.services.site_builder_bridge import SiteBuilderBridge
from app.core.route_security import site_publish_security_guard

router = APIRouter(prefix="/site-builder", tags=["site-builder"])


@router.get("/health")
def health():
    return {"ok": True, "module": "site_builder"}


@router.post("/generate")
def generate(payload: SiteGenerateRequest, current_user: User = Depends(get_current_user)):
    # Missão C02: o guard precisa ser a fonte única de verdade. Nunca confiamos em
    # campos extras enviados pelo cliente (ex.: um "confirmed_by_user" no corpo da
    # requisição) -- SiteGenerateRequest não declara esse campo, então o pydantic
    # descarta silenciosamente qualquer tentativa de autoaprovação via payload antes
    # mesmo do guard rodar. O guard é sempre chamado e SEMPRE é respeitado: se
    # bloquear, a execução para aqui -- o site não é gerado e nada é "publicado".
    guard = site_publish_security_guard(payload.model_dump(mode="json"))
    actor_label = getattr(current_user, "email", None) or getattr(current_user, "name", "unknown")

    if guard["status"] == "blocked":
        immutable_audit_event(
            actor=str(actor_label),
            action="site_builder.generate.blocked",
            resource_type="site_builder",
            resource_id=payload.offer.product_name,
            status="blocked",
            details={
                "blocked_reasons": guard["blocked_reasons"],
                "requires_human_approval": guard["requires_human_approval"],
                "deploy_provider": payload.deploy.provider,
                "deploy_dry_run": payload.deploy.dry_run,
            },
        )
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Geração/publicação do site bloqueada pelo guard de segurança.",
                "blocked_reasons": guard["blocked_reasons"],
                "requires_human_approval": guard["requires_human_approval"],
            },
        )

    result = SiteBuilderBridge().safe_generate(
        payload=payload,
        product_name=payload.offer.product_name,
        niche=payload.offer.niche,
    )
    site = result["site_builder"]

    immutable_audit_event(
        actor=str(actor_label),
        action="site_builder.generate.allowed",
        resource_type="site_builder",
        resource_id=site["product_name"],
        status="ok",
        details={
            "deploy_provider": site["deploy_provider"],
            "deploy_status": site["deploy_status"],
        },
    )

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
