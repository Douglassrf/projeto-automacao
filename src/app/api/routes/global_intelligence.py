from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.ad_library_model import ad_library_data_model
from app.core.ad_library_search import ad_library_search_local
from app.core.billing_readiness import billing_readiness_local
from app.core.commercial_api_snapshot import commercial_api_snapshot
from app.core.country_intelligence import country_intelligence_profile
from app.core.creative_intelligence import creative_intelligence_analysis
from app.core.data_moat import data_moat_local_snapshot
from app.core.executive_reports import executive_report_local
from app.core.global_intelligence_contract import normalize_global_ad_signal
from app.core.global_miner_hub import global_miner_hub_local
from app.core.global_opportunity_brief import global_opportunity_brief
from app.core.global_operator_hub import global_operator_dry_run
from app.core.enterprise_dashboard_snapshot import enterprise_dashboard_snapshot
from app.core.frontend_enterprise_spec import frontend_enterprise_spec
from app.core.landing_intelligence import landing_intelligence_analysis
from app.core.market_radar import market_radar_local_report
from app.core.multi_tenant_readiness import multi_tenant_readiness
from app.core.offer_intelligence import offer_intelligence_analysis
from app.core.opportunity_alerts import opportunity_alerts_local
from app.core.public_api_readiness import public_api_readiness
from app.core.real_connectors_readiness import real_connectors_readiness
from app.core.release_readiness import release_readiness_local
from app.core.saas_compliance import saas_compliance_local
from app.core.saturation_monitor import saturation_monitor_local
from app.core.scale_forecast import scale_forecast_local
from app.core.vector_db_readiness import vector_db_readiness
from app.core.winning_ad_score import winning_ad_score
from app.domain.models import User

router = APIRouter(prefix="/global-intelligence", tags=["Global Intelligence"])


@router.post("/normalize-ad")
def post_normalize_global_ad(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return normalize_global_ad_signal(payload)


@router.post("/market-radar")
def post_market_radar(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return market_radar_local_report(payload)


@router.post("/winning-ad-score")
def post_winning_ad_score(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return winning_ad_score(payload)


@router.post("/creative-analysis")
def post_creative_analysis(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return creative_intelligence_analysis(payload)


@router.post("/country-profile")
def post_country_profile(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return country_intelligence_profile(payload)


@router.post("/landing-analysis")
def post_landing_analysis(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return landing_intelligence_analysis(payload)


@router.post("/offer-analysis")
def post_offer_analysis(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return offer_intelligence_analysis(payload)


@router.post("/opportunity-brief")
def post_opportunity_brief(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return global_opportunity_brief(payload)


@router.post("/operator-dry-run")
def post_operator_dry_run(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return global_operator_dry_run(payload)


@router.post("/enterprise-snapshot")
def post_enterprise_snapshot(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return enterprise_dashboard_snapshot(payload)


@router.post("/miner-hub-local")
def post_miner_hub_local(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return global_miner_hub_local(payload)


@router.post("/data-moat-local")
def post_data_moat_local(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return data_moat_local_snapshot(payload)


@router.post("/commercial-api-snapshot")
def post_commercial_api_snapshot(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return commercial_api_snapshot(payload)


@router.post("/billing-readiness")
def post_billing_readiness(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return billing_readiness_local(payload)


@router.post("/multi-tenant-readiness")
def post_multi_tenant_readiness(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return multi_tenant_readiness(payload)


@router.post("/public-api-readiness")
def post_public_api_readiness(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return public_api_readiness(payload)


@router.post("/frontend-enterprise-spec")
def post_frontend_enterprise_spec(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return frontend_enterprise_spec(payload)


@router.post("/real-connectors-readiness")
def post_real_connectors_readiness(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return real_connectors_readiness(payload)


@router.post("/vector-db-readiness")
def post_vector_db_readiness(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return vector_db_readiness(payload)


@router.post("/ad-library-model")
def post_ad_library_model(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return ad_library_data_model(payload)


@router.post("/ad-library-search")
def post_ad_library_search(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return ad_library_search_local(payload)


@router.post("/saas-compliance")
def post_saas_compliance(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return saas_compliance_local(payload)


@router.post("/executive-report")
def post_executive_report(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return executive_report_local(payload)


@router.post("/opportunity-alerts")
def post_opportunity_alerts(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return opportunity_alerts_local(payload)


@router.post("/saturation-monitor")
def post_saturation_monitor(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return saturation_monitor_local(payload)


@router.post("/scale-forecast")
def post_scale_forecast(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return scale_forecast_local(payload)


@router.post("/release-readiness")
def post_release_readiness(payload: dict | None = None, current_user: User = Depends(get_current_user)):
    return release_readiness_local(payload)
