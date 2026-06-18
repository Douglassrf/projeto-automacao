from fastapi import APIRouter

from app.services.campaign_brain import CampaignBrainAgent


router = APIRouter(prefix="/brain", tags=["Campaign Brain"])


@router.get("/health")
def brain_health():
    brain = CampaignBrainAgent()
    return {
        "status": "ok",
        "agent": "CampaignBrainAgent",
        "mode": "consultivo_read_only_memoria_evolutiva",
        "read_only": brain.read_only,
        "dry_run": brain.dry_run,
        "can_execute": brain.can_execute,
    }


@router.post("/review")
def review_before_campaign(payload: dict):
    brain = CampaignBrainAgent()
    return brain.review_before_campaign(payload)


@router.get("/review/mock")
def review_mock():
    brain = CampaignBrainAgent()
    return brain.review_before_campaign({
        "product_name": "Ebook de Receitas Fitness",
        "niche": "emagrecimento",
        "campaign_stage": "V1",
        "budget_brl": 25,
        "metrics": {
            "connect_rate": 82,
            "checkout_rate": 25.61,
            "purchase_rate": 3.41,
        },
    })


@router.post("/learn")
def learn_after_campaign(payload: dict):
    """Registra aprendizado local controlado.

    Não executa campanha.
    Não chama API externa.
    Não altera MetaCampaignOperator.
    """
    brain = CampaignBrainAgent()
    return brain.learn_after_campaign(payload)


@router.get("/learn/mock")
def learn_mock():
    brain = CampaignBrainAgent()
    return brain.learn_after_campaign({
        "product_name": "Ebook de Receitas Fitness",
        "niche": "emagrecimento",
        "campaign_stage": "V1",
        "outcome": "WINNER",
        "lesson": "Criativo com promessa moderada e foco em praticidade teve melhor sinal inicial. Manter orçamento de descoberta em R$25 antes de validar V2.",
        "metrics": {
            "connect_rate": 82,
            "checkout_rate": 25.61,
            "purchase_rate": 3.41,
            "roas": 1.8,
        },
    })
