"""
TESTE ISOLADO R11 - NUNCA usa o .env real, NUNCA chama rede real.

Estrategia de seguranca (3 camadas independentes):
1. Settings 100% sintetico, construido com _env_file=None (pydantic-settings
   nunca le nenhum .env, real ou de teste, nesta instancia).
2. Credenciais fake (token/IDs claramente marcados como FAKE, nao tem nenhuma
   relacao com a conta real do usuario).
3. Tripwire de rede: monkeypatch em httpx.get/post/delete que lanca excecao
   imediata se qualquer codigo tentar de fato sair para a rede. Se o tripwire
   NUNCA disparar nos cenarios que devem ficar bloqueados, e SEMPRE disparar
   nos cenarios propositalmente 100% desbloqueados, isso prova que a logica
   de guardrails esta correta nas duas direcoes.
"""
import sys
sys.path.insert(0, "/tmp/projeto_fast/src")

import httpx
from app.core.config import Settings
from app.integrations import meta_marketing as meta_marketing_module
from app.services import meta_campaign_operator as operator_module
from app.schemas.meta_operator import MetaOperatorLaunchRequest, MetaCreativeInput

RESULTS = []

def record(name, ok, detail):
    RESULTS.append((name, ok, detail))
    print(f"[{'OK' if ok else 'FALHOU'}] {name}: {detail}")


class NetworkTripwireError(RuntimeError):
    pass


def _tripwire(*args, **kwargs):
    raise NetworkTripwireError(f"TENTATIVA DE REDE REAL BLOQUEADA PELO TRIPWIRE: args={args} kwargs={kwargs}")


def make_fake_settings(**overrides):
    base = dict(
        _env_file=None,  # NUNCA ler nenhum .env, garantido pelo pydantic-settings
        meta_access_token="FAKE_TOKEN_ISOLATED_TEST_R11_NAO_E_REAL",
        meta_ad_account_id="000000000000001",
        meta_page_id="000000000000002",
        meta_pixel_id="000000000000003",
        meta_instagram_actor_id=None,
        meta_env="sandbox",
        meta_dry_run=False,
        meta_autopublish=True,
        meta_allow_active_launch=True,
        meta_allow_production_real=True,
        meta_require_manual_confirmation=True,
        meta_production_daily_spend_limit_brl=50.0,
        meta_operator_enabled=True,
        meta_created_resources_log="/tmp/r11_isolated/fake_created_resources.jsonl",
    )
    base.update(overrides)
    return Settings(**base)


def make_operator(settings):
    """Constroi MetaCampaignOperator SEM chamar __init__ real (que chamaria
    get_settings() global). Tudo e injetado manualmente."""
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

    operator = object.__new__(operator_module.MetaCampaignOperator)
    operator.settings = settings
    operator.meta_client = client
    from app.integrations.affiliate_provider import AffiliateProvider, AffiliateCredentials
    affiliate_provider = object.__new__(AffiliateProvider)
    affiliate_provider.credentials = AffiliateCredentials(
        provider="fake_isolated_test",
        api_key=None,
        api_secret=None,
        default_affiliate_id="FAKE_AFFILIATE_R11",
    )
    affiliate_provider.mock_enabled = True
    operator.affiliate_provider = affiliate_provider
    return operator, client


def make_payload(**overrides):
    base = dict(
        product_name="Teste R11 Isolado",
        pixel_id="000000000000003",
        landing_page_url="https://example.com/r11",
        geo_preset="BRASIL",
        language="Portuguese_All",
        daily_budget_brl=25,
        mode="dry_run",
        creatives=[MetaCreativeInput(name="AD01", copy="Copy segura.", media_type="image")],
        confirmed_by_user=False,
    )
    base.update(overrides)
    return MetaOperatorLaunchRequest(**base)


# ---------------------------------------------------------------------------
# U1: mode="dry_run" explicito, MESMO com todas as flags de ambiente
# desbloqueadas -> effective_dry_run deve ser True so pelo mode.
# ---------------------------------------------------------------------------
httpx.get = _tripwire
httpx.post = _tripwire
httpx.delete = _tripwire

settings_unlocked = make_fake_settings()
operator, client = make_operator(settings_unlocked)
payload = make_payload(mode="dry_run")
try:
    resp = operator.launch_v3(payload)
    record("U1_mode_dry_run_forca_simulacao", resp.dry_run is True and resp.published == 0,
           f"dry_run={resp.dry_run}, published={resp.published}, tripwire não disparou (esperado)")
except NetworkTripwireError as e:
    record("U1_mode_dry_run_forca_simulacao", False, f"TRIPWIRE DISPAROU INESPERADAMENTE: {e}")


# ---------------------------------------------------------------------------
# U2: TUDO desbloqueado de propósito (settings sintéticos 100% liberados +
# payload com confirmed_by_user=True + hash correto + spend simulado abaixo
# do limite) + mode="publish_active" -> o código DEVE tentar uma chamada real
# nesse ponto (é o comportamento correto e esperado quando um humano de fato
# libera tudo). O tripwire deve disparar aqui — isso PROVA que o único jeito
# de chegar perto de uma publicação real é desbloquear deliberadamente todas
# as flags, nunca um payload sozinho.
# ---------------------------------------------------------------------------
operator2, client2 = make_operator(make_fake_settings())
client2.get_ad_account_spend_today_brl = lambda: 0.0  # simula consulta de gasto sem rede real
plans_preview = [operator2._build_plan(make_payload(), c, i) for i, c in enumerate(make_payload().creatives, start=1)]
preview = operator2._build_payload_preview(plans_preview)
payload2 = make_payload(
    mode="publish_active",
    confirmed_by_user=True,
    expected_payload_sha256=preview.payload_sha256,
    daily_budget_brl=25,
    creatives=[MetaCreativeInput(name=f"AD{i:02d}", copy="Copy segura.", media_type="image") for i in range(1, 5)],
)
# recalcula preview com o payload final de 4 criativos para o hash bater de verdade
plans2 = [operator2._build_plan(payload2, c, i) for i, c in enumerate(payload2.creatives, start=1)]
preview2 = operator2._build_payload_preview(plans2)
payload2 = make_payload(
    mode="publish_active",
    confirmed_by_user=True,
    expected_payload_sha256=preview2.payload_sha256,
    daily_budget_brl=25,
    creatives=[MetaCreativeInput(name=f"AD{i:02d}", copy="Copy segura.", media_type="image") for i in range(1, 5)],
)

guardrails2 = operator2._validate_guardrails(payload2, preview2.payload_sha256, 0.0, effective_dry_run=False)
blocked_names = [g.name for g in guardrails2 if g.status == "blocked"]
record("U2a_guardrails_todos_ok_quando_tudo_liberado", len(blocked_names) == 0,
       f"guardrails bloqueados (esperado vazio): {blocked_names}")

try:
    resp2 = operator2.launch_v3(payload2)
    record("U2b_tentativa_real_deveria_disparar_tripwire", False,
           f"PERIGO: launch_v3 NAO tentou rede real e nao teve erro -- resp.dry_run={resp2.dry_run}, published={resp2.published}")
except NetworkTripwireError as e:
    record("U2b_tentativa_real_deveria_disparar_tripwire", True,
           "Confirmado: com TODAS as flags deliberadamente desbloqueadas + payload 100% válido, o código tenta uma chamada real ao Meta (interceptada pelo tripwire antes de qualquer rede) -- comportamento correto e esperado, nao e bug.")


# ---------------------------------------------------------------------------
# U3: mesma config 100% desbloqueada, EXCETO meta_autopublish=False
# -> deve bloquear, tripwire NAO deve disparar.
# ---------------------------------------------------------------------------
operator3, client3 = make_operator(make_fake_settings(meta_autopublish=False))
client3.get_ad_account_spend_today_brl = lambda: 0.0
try:
    resp3 = operator3.launch_v3(payload2)
    blocked3 = [g.name for g in resp3.guardrails if g.status == "blocked"]
    record("U3_sem_autopublish_bloqueia", resp3.dry_run is True and "autopublish" in blocked3,
           f"dry_run={resp3.dry_run}, guardrails bloqueados={blocked3}, published={resp3.published}")
except NetworkTripwireError as e:
    record("U3_sem_autopublish_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")


# ---------------------------------------------------------------------------
# U4: mesma config 100% desbloqueada, EXCETO meta_allow_active_launch=False,
# mode="publish_active" -> deve bloquear por active_launch.
# ---------------------------------------------------------------------------
operator4, client4 = make_operator(make_fake_settings(meta_allow_active_launch=False))
client4.get_ad_account_spend_today_brl = lambda: 0.0
try:
    resp4 = operator4.launch_v3(payload2)
    blocked4 = [g.name for g in resp4.guardrails if g.status == "blocked"]
    record("U4_sem_active_launch_bloqueia", "active_launch" in blocked4,
           f"guardrails bloqueados={blocked4}, published={resp4.published}")
except NetworkTripwireError as e:
    record("U4_sem_active_launch_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")


# ---------------------------------------------------------------------------
# U5: tudo desbloqueado MAS confirmed_by_user=False -> deve bloquear por
# manual_confirmation.
# ---------------------------------------------------------------------------
operator5, client5 = make_operator(make_fake_settings())
client5.get_ad_account_spend_today_brl = lambda: 0.0
payload5 = make_payload(
    mode="publish_active",
    confirmed_by_user=False,
    daily_budget_brl=25,
    creatives=[MetaCreativeInput(name=f"AD{i:02d}", copy="Copy segura.", media_type="image") for i in range(1, 5)],
)
try:
    resp5 = operator5.launch_v3(payload5)
    blocked5 = [g.name for g in resp5.guardrails if g.status == "blocked"]
    record("U5_sem_confirmacao_manual_bloqueia", "manual_confirmation" in blocked5,
           f"guardrails bloqueados={blocked5}, published={resp5.published}")
except NetworkTripwireError as e:
    record("U5_sem_confirmacao_manual_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")


# ---------------------------------------------------------------------------
# U6: tudo desbloqueado + confirmed_by_user=True, MAS hash de payload nao
# corresponde -> deve bloquear por payload_integrity.
# ---------------------------------------------------------------------------
operator6, client6 = make_operator(make_fake_settings())
client6.get_ad_account_spend_today_brl = lambda: 0.0
payload6 = make_payload(
    mode="publish_active",
    confirmed_by_user=True,
    expected_payload_sha256="0" * 64,
    daily_budget_brl=25,
    creatives=[MetaCreativeInput(name=f"AD{i:02d}", copy="Copy segura.", media_type="image") for i in range(1, 5)],
)
try:
    resp6 = operator6.launch_v3(payload6)
    blocked6 = [g.name for g in resp6.guardrails if g.status == "blocked"]
    record("U6_hash_payload_incorreto_bloqueia", "payload_integrity" in blocked6,
           f"guardrails bloqueados={blocked6}, published={resp6.published}")
except NetworkTripwireError as e:
    record("U6_hash_payload_incorreto_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")


# ---------------------------------------------------------------------------
# U7: tudo desbloqueado, mas gasto diário simulado JÁ no limite -> spend_guard
# deve bloquear.
# ---------------------------------------------------------------------------
operator7, client7 = make_operator(make_fake_settings(meta_production_daily_spend_limit_brl=50.0))
client7.get_ad_account_spend_today_brl = lambda: 50.0  # ja no limite
try:
    resp7 = operator7.launch_v3(payload2)
    blocked7 = [g.name for g in resp7.guardrails if g.status == "blocked"]
    record("U7_limite_de_gasto_atingido_bloqueia", "spend_guard" in blocked7,
           f"guardrails bloqueados={blocked7}, published={resp7.published}")
except NetworkTripwireError as e:
    record("U7_limite_de_gasto_atingido_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")


# ---------------------------------------------------------------------------
# U8: tudo desbloqueado, mas consulta de gasto falha (simulando API real
# indisponível) -> spend_guard deve bloquear por não conseguir confirmar.
# ---------------------------------------------------------------------------
operator8, client8 = make_operator(make_fake_settings())
def _raise_meta_error():
    raise meta_marketing_module.MetaMarketingError("Falha simulada ao consultar gasto.")
client8.get_ad_account_spend_today_brl = _raise_meta_error
try:
    resp8 = operator8.launch_v3(payload2)
    blocked8 = [g.name for g in resp8.guardrails if g.status == "blocked"]
    record("U8_falha_ao_consultar_gasto_bloqueia", "spend_guard" in blocked8 and resp8.account_spend_today_brl is None,
           f"guardrails bloqueados={blocked8}, account_spend_today_brl={resp8.account_spend_today_brl}, published={resp8.published}")
except NetworkTripwireError as e:
    record("U8_falha_ao_consultar_gasto_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")


# ---------------------------------------------------------------------------
# U9: rollback - lista de recursos criados FAKE nao vazia, force_dry_run=False
# + confirmed_by_user=True -> deve tentar de fato chamar remove_campaign,
# que deve disparar o tripwire (prova que so chega na rede com confirmacao
# explicita E recursos reais cadastrados).
# ---------------------------------------------------------------------------
from app.schemas.meta_operator import MetaOperatorRollbackRequest
operator9, client9 = make_operator(make_fake_settings())
operator9._read_created_resources = lambda: [{"campaign_id": "fake_campaign_999", "creative_name": "AD01"}]
rollback_payload = MetaOperatorRollbackRequest(action="pause", force_dry_run=False, confirmed_by_user=True)
try:
    resp9 = operator9.rollback_created_campaigns(rollback_payload)
    record("U9a_rollback_com_recursos_reais_deveria_tentar_rede", False,
           f"PERIGO: rollback nao tentou rede real -- resp={resp9}")
except NetworkTripwireError as e:
    record("U9a_rollback_com_recursos_reais_deveria_tentar_rede", True,
           "Confirmado: rollback so tenta rede real quando ha recursos cadastrados E confirmed_by_user=True E force_dry_run=False (interceptado pelo tripwire).")

# U9b: mesma lista de recursos, mas confirmed_by_user=False -> deve bloquear
# ANTES de qualquer tentativa, sem tripwire.
operator9b, client9b = make_operator(make_fake_settings())
operator9b._read_created_resources = lambda: [{"campaign_id": "fake_campaign_999", "creative_name": "AD01"}]
rollback_payload_b = MetaOperatorRollbackRequest(action="delete", force_dry_run=False, confirmed_by_user=False)
try:
    resp9b = operator9b.rollback_created_campaigns(rollback_payload_b)
    record("U9b_rollback_sem_confirmacao_bloqueia_sem_tentar_rede", resp9b.blocked is True,
           f"resp={resp9b}")
except NetworkTripwireError as e:
    record("U9b_rollback_sem_confirmacao_bloqueia_sem_tentar_rede", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")


# ---------------------------------------------------------------------------
print("\n=== RESUMO ===")
total = len(RESULTS)
passed = sum(1 for _, ok, _ in RESULTS if ok)
print(f"{passed}/{total} cenarios passaram conforme esperado.")
for name, ok, detail in RESULTS:
    print(f"  {'PASS' if ok else 'FAIL'} | {name}")
sys.exit(0 if passed == total else 1)
