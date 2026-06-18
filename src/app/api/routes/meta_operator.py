from fastapi import APIRouter

from app.services.miner_engine import MinerEngine
from app.services.facebook_ad_miner import FacebookAdMiner
from app.services.campaign_brain import CampaignBrainAgent
from app.services.meta_campaign_operator import MetaCampaignOperator
from app.schemas.meta_operator import MetaCreativeInput, MetaOperatorLaunchRequest, MetaOperatorRollbackRequest
from app.core.route_security import meta_production_security_guard, with_security_guard


router = APIRouter(tags=["Miner / Meta Operator"])


class MemoryRepository:
    """Repositório temporário em memória para teste seguro."""

    def save(self, data: dict):
        return data


@router.get("/miner/test")
async def minerar_nicho():
    """Teste controlado do MinerEngine.

    Não chama API externa.
    Não faz scraping.
    Não cria campanha real.
    """
    miner = MinerEngine(repository=MemoryRepository())
    return miner.analyze_mock()


@router.post("/miner/controlled-real")
def miner_controlled_real(payload: dict):
    """Missao 28: MinerEngine real controlado por fonte local auditavel.

    Continua bloqueando chamadas externas, scraping, navegador, Selenium e Meta real.
    """
    miner = MinerEngine(repository=MemoryRepository())
    return miner.controlled_real_mine(
        product_name=str(payload.get("product_name") or "Produto Controlado"),
        niche=str(payload.get("niche") or payload.get("nicho") or "produto digital"),
        ads=payload.get("ads") if isinstance(payload.get("ads"), list) else None,
        max_ads=int(payload.get("max_ads") or 10),
        allow_external_call=bool(payload.get("allow_external_call", False)),
        source_label=str(payload.get("source_label") or "api_local_payload"),
        user_id=int(payload.get("user_id") or 1),
    )


@router.post("/facebook-ad-miner/controlled-real")
def facebook_ad_miner_controlled_real(payload: dict):
    """Missao 29: FacebookAdMiner real controlado via export local auditavel."""
    miner = FacebookAdMiner(repository=MemoryRepository(), dry_run=True, can_external_call=False)
    return miner.controlled_real_collect(
        product_name=str(payload.get("product_name") or "Produto Facebook Miner"),
        niche=str(payload.get("niche") or payload.get("nicho") or "produto digital"),
        local_export_ads=payload.get("ads") if isinstance(payload.get("ads"), list) else None,
        max_ads=int(payload.get("max_ads") or 20),
        source_label=str(payload.get("source_label") or "api_local_ad_library_export"),
        allow_external_call=bool(payload.get("allow_external_call", False)),
        use_browser=bool(payload.get("use_browser", False)),
        use_selenium=bool(payload.get("use_selenium", False)),
        source_url=payload.get("source_url"),
        user_id=int(payload.get("user_id") or 1),
    )


@router.get("/campaign-operator/status")
def campaign_operator_status():
    return MetaCampaignOperator().status()


@router.post("/campaign-operator/v3/launch")
def campaign_operator_launch_v3(payload: MetaOperatorLaunchRequest):
    return MetaCampaignOperator().launch_v3(payload)


@router.post("/campaign-operator/rollback")
def campaign_operator_rollback(payload: MetaOperatorRollbackRequest):
    return MetaCampaignOperator().rollback_created_campaigns(payload)


@router.post("/campaign-operator/rollback/policy")
def campaign_operator_rollback_policy(payload: dict):
    return MetaCampaignOperator().rollback_policy(payload)


@router.post("/campaign-operator/production/readiness")
def campaign_operator_production_readiness(payload: dict):
    response = MetaCampaignOperator().production_readiness(payload)
    return with_security_guard(response, meta_production_security_guard(payload))


@router.post("/campaign-operator/production/credential-review")
def campaign_operator_credential_review(payload: dict):
    response = MetaCampaignOperator().credential_payload_review(payload)
    return with_security_guard(response, meta_production_security_guard(payload))


@router.post("/campaign-operator/production/assisted-execution")
def campaign_operator_assisted_execution(payload: dict):
    response = MetaCampaignOperator().assisted_execution_gate(payload)
    return with_security_guard(response, meta_production_security_guard(payload))


@router.post("/campaign-operator/production/post-execution-monitor")
def campaign_operator_post_execution_monitor(payload: dict):
    return MetaCampaignOperator().post_execution_monitor(payload)


@router.post("/campaign-operator/production/hardening-review")
def campaign_operator_production_hardening(payload: dict):
    return MetaCampaignOperator().production_hardening_review(payload)


def _build_dry_run_payload() -> MetaOperatorLaunchRequest:
    """Payload seguro para simulação do MetaCampaignOperator."""
    creatives = [
        MetaCreativeInput(
            name="Criativo V3 AD01",
            copy="Descubra receitas fitness simples para organizar sua alimentação sem promessas milagrosas.",
            media_type="image",
        ),
        MetaCreativeInput(
            name="Criativo V3 AD02",
            copy="Planeje refeições práticas com orientação clara, foco em rotina e melhoria gradual.",
            media_type="image",
        ),
        MetaCreativeInput(
            name="Criativo V3 AD03",
            copy="Uma abordagem simples para melhorar sua rotina alimentar com receitas fáceis.",
            media_type="image",
        ),
        MetaCreativeInput(
            name="Criativo V3 AD04",
            copy="Receitas práticas para quem busca mais organização e consistência no dia a dia.",
            media_type="image",
        ),
    ]

    return MetaOperatorLaunchRequest(
        product_name="Ebook de Receitas Fitness",
        pixel_id="dry_pixel_123",
        landing_page_url="https://example.com/ebook-receitas-fitness",
        geo_preset="BRASIL",
        language="Portuguese_All",
        excluded_countries=[],
        daily_budget_brl=25,
        mode="dry_run",
        creatives=creatives,
        confirmed_by_user=False,
    )


@router.get("/campaign/dry-run/mock")
def campaign_dry_run_mock():
    """Simula campanha após revisão do Brain.

    Segurança:
    - mode=dry_run
    - não publica campanha
    - não gasta dinheiro
    - não exige credenciais Meta reais
    """
    brain = CampaignBrainAgent()
    brain_review = brain.review_before_campaign({
        "product_name": "Ebook de Receitas Fitness",
        "niche": "emagrecimento",
        "campaign_stage": "V3",
        "budget_brl": 25,
        "metrics": {
            "connect_rate": 82,
            "checkout_rate": 25.61,
            "purchase_rate": 3.41,
        },
        "copy": "Receitas fitness simples sem promessas milagrosas.",
    })

    if brain_review.get("decision") != "SIM":
        return {
            "status": "blocked_by_brain",
            "published": False,
            "would_publish": False,
            "brain_review": brain_review,
            "operator_response": None,
        }

    operator = MetaCampaignOperator()
    payload = _build_dry_run_payload()
    response = operator.launch_v3(payload)

    return {
        "status": "dry_run_ok",
        "published": False,
        "would_publish": True,
        "brain_review": brain_review,
        "operator_response": response.model_dump(mode="json"),
    }


@router.post("/campaign/dry-run")
def campaign_dry_run(payload: dict):
    """Dry-run de campanha com dados enviados pelo usuário/sistema.

    O Brain revisa antes. O operador só roda se a decisão for SIM.
    O modo real continua bloqueado: esta rota força dry_run.
    """
    product_name = payload.get("product_name") or "Produto Teste"
    niche = payload.get("niche") or payload.get("nicho") or ""
    budget_brl = float(payload.get("budget_brl") or payload.get("budget") or 25)

    brain = CampaignBrainAgent()
    brain_review = brain.review_before_campaign({
        "product_name": product_name,
        "niche": niche,
        "campaign_stage": payload.get("campaign_stage") or "V3",
        "budget_brl": budget_brl,
        "metrics": payload.get("metrics") or {},
        "copy": payload.get("copy") or "",
        "offer": payload.get("offer") or "",
    })

    if brain_review.get("decision") != "SIM":
        return {
            "status": "blocked_by_brain",
            "published": False,
            "would_publish": False,
            "brain_review": brain_review,
            "operator_response": None,
        }

    creative_text = payload.get("copy") or "Criativo seguro para teste dry-run sem promessa absoluta."
    request = MetaOperatorLaunchRequest(
        product_name=product_name,
        pixel_id=str(payload.get("pixel_id") or "dry_pixel_123"),
        landing_page_url=payload.get("landing_page_url") or "https://example.com/dry-run",
        geo_preset=payload.get("geo_preset") or "BRASIL",
        language=payload.get("language") or "Portuguese_All",
        excluded_countries=payload.get("excluded_countries") or [],
        daily_budget_brl=budget_brl,
        mode="dry_run",
        creatives=[
            MetaCreativeInput(
                name="Criativo Dry Run AD01",
                copy=creative_text,
                media_type="image",
            )
        ],
        confirmed_by_user=False,
    )

    operator = MetaCampaignOperator()
    response = operator.launch_v3(request)

    return {
        "status": "dry_run_ok",
        "published": False,
        "would_publish": True,
        "brain_review": brain_review,
        "operator_response": response.model_dump(mode="json"),
    }
