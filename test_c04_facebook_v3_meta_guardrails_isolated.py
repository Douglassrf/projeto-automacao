"""
TESTE ISOLADO C04 - NUNCA usa o .env real, NUNCA chama rede real.

Contexto do bug encontrado (C04 - Proteger credenciais Meta sandbox vs producao):

O motor V1/V2/V3 (FacebookMarketingAutomationEngine, usado pela rota
POST /api/v1/facebook/v3/execute) chamava MetaMarketingClient.publish_campaign_plan()
direto, sem checar NENHUMA das flags server-side (META_ENV, META_ALLOW_PRODUCTION_REAL,
META_AUTOPUBLISH, META_ALLOW_ACTIVE_LAUNCH) que o operador oficial
(MetaCampaignOperator.launch_v3) ja exige antes de publicar de verdade.

Na pratica, isso significava que bastava o cliente da API enviar, no corpo da
requisicao:
    publish_to_meta=true, execution_mode="automatic_v3",
    budget.require_manual_review=false, budget.allow_active_launch=true
para publicar uma campanha ACTIVE (gastando de verdade) assim que o servidor
tivesse META_DRY_RUN=false e credenciais configuradas -- sem checar se o
ambiente era sandbox ou producao, sem checar META_ALLOW_ACTIVE_LAUNCH, sem
checar META_AUTOPUBLISH, sem aprovacao humana, sem hash de payload. Um segundo
"gatilho" para a mesma arma, esquecido sem trava.

Estrategia de seguranca (3 camadas independentes, mesmo padrao do R11/C02):
1. Settings 100% sintetico, construido com _env_file=None (pydantic-settings
   nunca le nenhum .env, real ou de teste, nesta instancia).
2. Credenciais fake (token/IDs claramente marcados como FAKE).
3. Tripwire de rede: monkeypatch em httpx.get/post/delete que lanca excecao
   imediata se qualquer codigo tentar de fato sair para a rede.
"""
import sys
sys.path.insert(0, "/tmp/projeto_fast/src")

import httpx
from app.core.config import Settings
from app.integrations import meta_marketing as meta_marketing_module
from app.services import facebook_automation as facebook_automation_module
from app.schemas.facebook_marketing import (
    CampaignPlanItem,
    CampaignPlanResponse,
    V3ExecutionRequest,
)
from datetime import datetime, timezone

RESULTS = []


def record(name, ok, detail):
    RESULTS.append((name, ok, detail))
    print(f"[{'OK' if ok else 'FALHOU'}] {name}: {detail}")


class NetworkTripwireError(RuntimeError):
    pass


def _tripwire(*args, **kwargs):
    raise NetworkTripwireError(f"TENTATIVA DE REDE REAL BLOQUEADA PELO TRIPWIRE: args={args} kwargs={kwargs}")


httpx.get = _tripwire
httpx.post = _tripwire
httpx.delete = _tripwire


def make_fake_settings(**overrides):
    base = dict(
        _env_file=None,  # NUNCA ler nenhum .env, garantido pelo pydantic-settings
        meta_access_token="FAKE_TOKEN_ISOLATED_TEST_C04_NAO_E_REAL",
        meta_ad_account_id="000000000000001",
        meta_page_id="000000000000002",
        meta_pixel_id="000000000000003",
        meta_instagram_actor_id=None,
        meta_env="sandbox",
        meta_dry_run=True,
        meta_autopublish=False,
        meta_allow_active_launch=False,
        meta_allow_production_real=False,
        meta_require_manual_confirmation=True,
        meta_production_daily_spend_limit_brl=50.0,
        meta_operator_enabled=True,
        meta_created_resources_log="/tmp/c04_isolated/fake_created_resources.jsonl",
    )
    base.update(overrides)
    return Settings(**base)


def make_engine(settings):
    """Constroi FacebookMarketingAutomationEngine SEM chamar __init__ real
    (que chamaria get_settings() global). Cliente Meta injetado manualmente,
    com credenciais sinteticas e dry_run controlado pelo cenario."""
    client = object.__new__(meta_marketing_module.MetaMarketingClient)
    client.credentials = meta_marketing_module.MetaCredentials(
        access_token=settings.meta_access_token,
        ad_account_id=settings.meta_ad_account_id,
        page_id=settings.meta_page_id,
        instagram_actor_id=settings.meta_instagram_actor_id,
        api_version="v20.0",
        dry_run=settings.meta_dry_run,
    )
    client.base_url = "https://graph.facebook.com/v20.0"

    engine = object.__new__(facebook_automation_module.FacebookMarketingAutomationEngine)
    engine.meta_client = client
    engine.affiliate_provider = None  # nao usado: v2_campaign_plan e substituido abaixo
    return engine, client


def make_plan(campaign_status="PAUSED"):
    return CampaignPlanItem(
        external_id="c04-fake-1",
        product_name="Produto Teste C04",
        campaign_model="V3_AUTOMACAO_PRINCIPAL",
        priority=3,
        action="Campanha principal otimizada para conversão/venda",
        existing_campaign_id=None,
        campaign_name="ADI V3_AUTOMACAO_PRINCIPAL | Produto Teste C04 | Auto",
        adset_name="ADI V3_AUTOMACAO_PRINCIPAL | Produto Teste C04 | BR | Auto",
        ad_name="ADI V3_AUTOMACAO_PRINCIPAL | Produto Teste C04 | Criativo 01",
        objective="OUTCOME_SALES",
        daily_budget_brl=25.0,
        optimization_goal="OFFSITE_CONVERSIONS",
        billing_event="IMPRESSIONS",
        campaign_status=campaign_status,
        adset_status=campaign_status,
        ad_status=campaign_status,
        promoted_object="purchase_or_checkout_conversion",
        audience_notes=["teste isolado c04"],
        targeting={"geo_locations": {"countries": ["BR"]}},
        creative_variations=["criativo-01.jpg"],
        copy_variations=["Copy segura de teste."],
        affiliate=None,
        manual_review_required=False,
        automation_notes=[],
    )


def patch_v2(engine, campaign_status):
    """Substitui v2_campaign_plan por um plano fixo, isolando o teste da
    pontuacao V1 (que exige dados de ads realistas) e focando exatamente no
    guard novo dentro de v3_execute."""
    plan = make_plan(campaign_status=campaign_status)
    response = CampaignPlanResponse(
        generated_at=datetime.now(timezone.utc),
        mode="automatic_v3_ready",
        total_items=1,
        approved_for_plan=1,
        plans=[plan],
    )
    engine.v2_campaign_plan = lambda payload: response
    return plan


def make_payload(allow_active_launch, require_manual_review=False):
    return V3ExecutionRequest(
        publish_to_meta=True,
        execution_mode="automatic_v3",
        budget={
            "daily_budget_brl": 25,
            "max_daily_budget_brl": 150,
            "max_campaigns_per_run": 3,
            "require_manual_review": require_manual_review,
            "allow_active_launch": allow_active_launch,
        },
        items=[{
            "external_id": "c04-fake-1",
            "product_name": "Produto Teste C04",
            "creative_original": "Oferta de teste isolado C04: https://example.com/checkout",
            "active_ads": 28,
            "link_clicks": 200,
            "landing_page_views": 170,
            "checkout_starts": 60,
            "purchases": 8,
            "spend": 100,
            "revenue": 260,
        }],
    )


# ---------------------------------------------------------------------------
# T1: O EXPLOIT ORIGINAL. Cliente envia publish_to_meta=true,
# execution_mode=automatic_v3, require_manual_review=false,
# allow_active_launch=true (tentando forcar status ACTIVE) -- mas o servidor
# esta em "modo real" (meta_dry_run=false, credenciais configuradas) com as
# flags de seguranca no estado padrao SEGURO (autopublish=false,
# allow_active_launch=false, env=sandbox). ANTES da correcao C04, isso
# publicava uma campanha ACTIVE real sem checar nada disso. Depois da
# correcao, deve bloquear, SEM jamais tocar a rede.
# ---------------------------------------------------------------------------
settings_t1 = make_fake_settings(meta_dry_run=False, meta_autopublish=False, meta_allow_active_launch=False)
engine_t1, client_t1 = make_engine(settings_t1)
plan_t1 = patch_v2(engine_t1, campaign_status="ACTIVE")
payload_t1 = make_payload(allow_active_launch=True)
import app.services.facebook_automation as fa_module
fa_module.get_settings = lambda: settings_t1
try:
    resp_t1 = engine_t1.v3_execute(payload_t1)
    record(
        "T1_exploit_original_agora_bloqueado",
        resp_t1.published == 0 and resp_t1.results[0].status == "blocked_for_manual_review",
        f"published={resp_t1.published}, status={resp_t1.results[0].status}, messages={resp_t1.results[0].messages}",
    )
except NetworkTripwireError as e:
    record("T1_exploit_original_agora_bloqueado", False, f"PERIGO: TRIPWIRE DISPAROU -- guard nao bloqueou antes da rede: {e}")


# ---------------------------------------------------------------------------
# T2: Mesmo payload do exploit, mas agora o SERVIDOR libera tudo
# deliberadamente (autopublish=true, allow_active_launch=true, env=sandbox,
# dry_run=false) -- ou seja, um humano configurou o ambiente para publicar de
# verdade em sandbox. Aqui o codigo DEVE tentar a chamada real (tripwire deve
# disparar) -- prova que o guard novo nao quebrou o caminho legitimo.
# ---------------------------------------------------------------------------
settings_t2 = make_fake_settings(meta_dry_run=False, meta_autopublish=True, meta_allow_active_launch=True, meta_env="sandbox")
engine_t2, client_t2 = make_engine(settings_t2)
plan_t2 = patch_v2(engine_t2, campaign_status="ACTIVE")
payload_t2 = make_payload(allow_active_launch=True)
fa_module.get_settings = lambda: settings_t2
try:
    resp_t2 = engine_t2.v3_execute(payload_t2)
    record("T2_ambiente_liberado_deveria_tentar_rede", False,
           f"PERIGO: nao tentou rede real -- published={resp_t2.published}, status={resp_t2.results[0].status}")
except NetworkTripwireError as e:
    record("T2_ambiente_liberado_deveria_tentar_rede", True,
           "Confirmado: com TODAS as flags server-side deliberadamente liberadas, o codigo tenta a chamada real (interceptada pelo tripwire) -- caminho legitimo preservado.")


# ---------------------------------------------------------------------------
# T3: Regressao - comportamento padrao (meta_dry_run=true, como vem por
# padrao no .env.example) com o MESMO payload do exploit (publish_to_meta=true
# etc.) e status PAUSED (como o V1/V2/V3 gera por padrao quando o cliente nao
# pede allow_active_launch). Deve continuar simulando normalmente, igual a
# antes da correcao -- prova que nao ha regressao no uso comum.
# ---------------------------------------------------------------------------
settings_t3 = make_fake_settings()  # defaults seguros, meta_dry_run=True
engine_t3, client_t3 = make_engine(settings_t3)
plan_t3 = patch_v2(engine_t3, campaign_status="PAUSED")
payload_t3 = make_payload(allow_active_launch=False)
fa_module.get_settings = lambda: settings_t3
try:
    resp_t3 = engine_t3.v3_execute(payload_t3)
    record(
        "T3_regressao_uso_comum_continua_simulando",
        resp_t3.results[0].status == "simulated" and resp_t3.results[0].dry_run is True,
        f"status={resp_t3.results[0].status}, dry_run={resp_t3.results[0].dry_run}",
    )
except NetworkTripwireError as e:
    record("T3_regressao_uso_comum_continua_simulando", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")


# ---------------------------------------------------------------------------
# T4: Servidor com META_ENV=production e autopublish=true, MAS sem
# META_ALLOW_PRODUCTION_REAL -- deve bloquear por production_real_not_allowed,
# mesmo com autopublish=true e dry_run=false.
# ---------------------------------------------------------------------------
settings_t4 = make_fake_settings(meta_dry_run=False, meta_autopublish=True, meta_env="production", meta_allow_production_real=False)
engine_t4, client_t4 = make_engine(settings_t4)
plan_t4 = patch_v2(engine_t4, campaign_status="PAUSED")
payload_t4 = make_payload(allow_active_launch=False)
fa_module.get_settings = lambda: settings_t4
try:
    resp_t4 = engine_t4.v3_execute(payload_t4)
    msg = " ".join(resp_t4.results[0].messages)
    record(
        "T4_producao_sem_allow_production_real_bloqueia",
        resp_t4.published == 0 and "production_real_not_allowed" in msg,
        f"published={resp_t4.published}, messages={resp_t4.results[0].messages}",
    )
except NetworkTripwireError as e:
    record("T4_producao_sem_allow_production_real_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")


# ---------------------------------------------------------------------------
# T5: Servidor com autopublish=true e env=sandbox (logo real_mode_guardrails
# vazio), MAS allow_active_launch=false -- e o plano pedido e ACTIVE. Deve
# bloquear especificamente pelo check de active_launch, isolando essa trava
# da trava geral de autopublish/meta_env.
# ---------------------------------------------------------------------------
settings_t5 = make_fake_settings(meta_dry_run=False, meta_autopublish=True, meta_env="sandbox", meta_allow_active_launch=False)
engine_t5, client_t5 = make_engine(settings_t5)
plan_t5 = patch_v2(engine_t5, campaign_status="ACTIVE")
payload_t5 = make_payload(allow_active_launch=True)
fa_module.get_settings = lambda: settings_t5
try:
    resp_t5 = engine_t5.v3_execute(payload_t5)
    msg = " ".join(resp_t5.results[0].messages)
    record(
        "T5_active_sem_allow_active_launch_bloqueia",
        resp_t5.published == 0 and "META_ALLOW_ACTIVE_LAUNCH" in msg,
        f"published={resp_t5.published}, messages={resp_t5.results[0].messages}",
    )
except NetworkTripwireError as e:
    record("T5_active_sem_allow_active_launch_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")


# ---------------------------------------------------------------------------
print("\n=== RESUMO ===")
total = len(RESULTS)
passed = sum(1 for _, ok, _ in RESULTS if ok)
print(f"{passed}/{total} cenarios passaram conforme esperado.")
for name, ok, detail in RESULTS:
    print(f"  {'PASS' if ok else 'FAIL'} | {name}")
sys.exit(0 if passed == total else 1)
