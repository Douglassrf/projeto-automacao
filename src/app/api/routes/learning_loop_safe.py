from pathlib import Path

from fastapi import APIRouter

from app.schemas.learning_loop import CapiIngestRequest, ConversionEventInput, LearningLoopRequest
from app.services.learning_loop import CapiLearningLoopService


router = APIRouter(prefix="/learning-loop-safe", tags=["Learning Loop Safe"])


def _service_with_local_output() -> CapiLearningLoopService:
    """Instancia o LearningLoop com output local seguro.

    Preserva o serviço original e evita escrita em /data quando o ambiente
    não tem permissão para criar diretórios na raiz do sistema.
    """
    service = CapiLearningLoopService()
    project_root = Path(__file__).resolve().parents[4]
    output_dir = project_root / "data" / "campaign_kits"
    output_dir.mkdir(parents=True, exist_ok=True)
    service.settings.kit_output_dir = str(output_dir)
    return service


@router.get("/health")
def learning_loop_safe_health():
    service = _service_with_local_output()
    return {
        "status": "ok",
        "agent": "LearningLoopSafe",
        "mode": "local_safe_activation",
        "meta_real": False,
        "publish_real": False,
        "output_dir": service.settings.kit_output_dir,
    }


@router.post("/capi/ingest")
def ingest_capi_events_safe(payload: CapiIngestRequest):
    service = _service_with_local_output()
    # Segurança: mesmo que o payload peça forward, esta rota força local.
    payload.forward_to_meta = False
    return service.ingest_capi_events(payload)


@router.post("/generate-variations")
def generate_variations_safe(payload: LearningLoopRequest):
    service = _service_with_local_output()
    return service.run_learning_loop(payload)


@router.get("/mock-run")
def learning_loop_mock_run():
    """Executa ciclo completo seguro: evento mock -> V4/V5/V6."""
    service = _service_with_local_output()

    event = ConversionEventInput(
        event_id="evt-learning-safe-001",
        pixel_id="PIXEL_MOCK_123",
        campaign_id="camp-learning-safe-v3",
        campaign_name="Ebook de Receitas Fitness V3 AD01",
        ad_id="ad-learning-safe-001",
        ad_name="AD01 Hook Praticidade",
        creative_id="creative-winner-learning-safe-001",
        creative_name="Criativo campeão seguro",
        product_name="Ebook de Receitas Fitness",
        geo="BRASIL",
        language="Portuguese_All",
        value=147.0,
        currency="BRL",
        purchase_count=2,
        cpa=24.5,
        roas=4.2,
        connect_rate=86.0,
        checkout_rate=28.0,
        hook="Receitas práticas para organizar sua alimentação",
        copy_text="Copy vencedora baseada em praticidade, rotina e promessa moderada.",
        creative_pattern="UGC simples com prova visual, benefício direto e CTA discreto",
        final_url="https://checkout.exemplo.com/ebook-receitas-fitness",
    )

    ingest = service.ingest_capi_events(CapiIngestRequest(events=[event], forward_to_meta=False))
    loop = service.run_learning_loop(LearningLoopRequest(
        product_name="Ebook de Receitas Fitness",
        min_roas=1.0,
        min_purchases=1,
        max_winners=5,
        generate_versions=["V4", "V5", "V6"],
        prepare_war_kit=True,
    ))

    return {
        "status": "ok",
        "mode": "learning_loop_safe_mock",
        "meta_real": False,
        "publish_real": False,
        "ingest": ingest.model_dump(mode="json"),
        "learning_loop": loop.model_dump(mode="json"),
    }
