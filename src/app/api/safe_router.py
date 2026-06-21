from importlib import import_module
from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")
FAILED_ROUTES = []
LOADED_ROUTES = []

ROUTE_MODULES = [
    "ads",
    "affiliate",
    "upload",
    "automation",
    "auth",
    "facebook",
    "meta_operator",
    "campaign_templates",
    "campaign_brain",
    "master_context",
    "meta_updates",
    "war_kit",
    "learning_loop",
    "learning_loop_safe",
    "learning_loop_bridge",
    "knowledge",
    "decision_logs",
    "decision_feed_safe",
    "automation_control",
    "video_pipeline",
    "site_builder",
    "orchestration",
    "hybrid_stack",
    "zero_cost_stack",
    "content_orchestrator",
    "content_orchestrator_safe",
    "video_pipeline_safe",
    "premium_render_safe",
    "site_builder_safe",
    "orchestration_safe",
    "serverless_render",
    "queue",
    "ugc_processing",
    "capi_enterprise",
    "premium_render",
    "observability",
    "security",
    "agency_operator",
    "campaign_intelligence",
    "campaign_intelligence_safe",
    "global_intelligence",
    "mission_orchestrator",
]

@api_router.get("/health")
def api_health_check():
    return {"status": "ok", "scope": "api", "loaded_routes": len(LOADED_ROUTES), "failed_routes": len(FAILED_ROUTES)}

@api_router.get("/diagnostics/routes")
def route_diagnostics():
    return {"loaded": LOADED_ROUTES, "failed": FAILED_ROUTES}

for module_name in ROUTE_MODULES:
    full_name = f"app.api.routes.{module_name}"
    try:
        module = import_module(full_name)
        router = getattr(module, "router", None)
        if router is None:
            FAILED_ROUTES.append({"module": full_name, "error": "router attribute not found"})
            continue
        api_router.include_router(router)
        LOADED_ROUTES.append(full_name)
    except Exception as exc:
        FAILED_ROUTES.append({"module": full_name, "error": f"{type(exc).__name__}: {exc}"})
