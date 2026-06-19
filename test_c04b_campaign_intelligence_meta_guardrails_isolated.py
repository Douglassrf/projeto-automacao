"""
TESTE ISOLADO C04b - achado colateral da auditoria "ponta a ponta" da C04.
NUNCA usa o .env real, NUNCA chama rede real (usa banco sqlite temporario
proprio + tripwire de rede).

Contexto do achado:

A auditoria de C04 ("auditar essa infraestrutura de ponta a ponta e fechar
qualquer brecha onde uma chamada destinada a sandbox possa vazar para a
conta de produção") encontrou um SEGUNDO caminho com o mesmo padrão de bug
já corrigido em facebook_automation.py:

CampaignIntelligenceService.execute_approved_meta_action() (rota
POST /api/v1/campaign-intelligence/meta-actions/{id}/execute) chama
_apply_loop_action() -> MetaMarketingClient.apply_campaign_action() direto,
checando SOMENTE o client.dry_run (META_DRY_RUN) -- sem nunca checar
META_ENV, META_ALLOW_PRODUCTION_REAL ou META_AUTOPUBLISH, que sao as mesmas
flags que o MetaCampaignOperator e o FacebookMarketingAutomationEngine (apos
a correcao C04 original) exigem antes de qualquer escrita real.

A superficie de ataque aqui e mais estreita que o bug original (exige uma
MetaActionRequest pre-existente com status=approved e payload_hash
confirmado, e so cobre pause_campaign/pause_adset/scale_budget/decrease_bid
em campanhas ja existentes -- nao cria campanha nova do nada), mas o mesmo
"fio desencapado" estava la: bastava META_DRY_RUN=false no servidor (que e
exigido para QUALQUER uso legitimo de producao real) para essa rota aceitar
dry_run=false do cliente e tentar escrever na Meta sem checar ambiente.

Correcao aplicada: novo metodo _real_mode_guardrails() (mesmo padrao de
facebook_automation.py) chamado em execute_approved_meta_action() antes de
_apply_loop_action(); se houver motivo de bloqueio E o cliente pediu
dry_run=false, bloqueia com status=blocked_for_manual_review e grava evento
no log de auditoria imutavel, sem nunca tocar a rede.

Estrategia de seguranca (mesmo padrao do C04/R11):
1. Settings 100% sintetico, _env_file=None (nunca le nenhum .env).
2. Credenciais fake (token/IDs claramente marcados como FAKE).
3. Banco sqlite temporario proprio (nunca o adintelligence.db real).
4. Tripwire de rede: monkeypatch em httpx.get/post/delete que lanca excecao
   imediata se qualquer codigo tentar de fato sair para a rede.
"""
import sys
import tempfile

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.session import Base
from app.domain.models import Campaign, MetaActionRequest
from app.integrations import meta_marketing as meta_marketing_module
from app.services import campaign_intelligence as ci_module

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


# ---------------------------------------------------------------------------
# Banco sqlite TEMPORARIO proprio deste teste -- nunca o adintelligence.db
# real do projeto. Usa o mesmo Base.metadata dos modelos reais, mas com um
# engine isolado.
# ---------------------------------------------------------------------------
_tmp_db_path = tempfile.NamedTemporaryFile(prefix="c04b_isolated_", suffix=".db", delete=False).name
_engine = create_engine(f"sqlite:///{_tmp_db_path}", connect_args={"check_same_thread": False}, future=True)
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


def make_fake_settings(**overrides):
    base = dict(
        _env_file=None,  # NUNCA ler nenhum .env, garantido pelo pydantic-settings
        meta_access_token="FAKE_TOKEN_ISOLATED_TEST_C04B_NAO_E_REAL",
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
        meta_created_resources_log="/tmp/c04b_isolated/fake_created_resources.jsonl",
    )
    base.update(overrides)
    return Settings(**base)


def make_client(settings):
    """MetaMarketingClient sem chamar __init__ real (que chamaria
    get_settings() global). client.dry_run e uma property que le
    credentials.dry_run/configured -- aqui controlada 100% por settings."""
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
    return client


def make_service(settings, client, db):
    service = object.__new__(ci_module.CampaignIntelligenceService)
    service.db = db
    service.meta_client = client
    service.settings = settings
    return service


def seed_approved_action(db, suffix):
    campaign = Campaign(
        internal_campaign_id=f"c04b-camp-{suffix}",
        meta_campaign_id=f"meta_c04b_{suffix}",
        meta_adset_id=f"meta_adset_c04b_{suffix}",
        product_name=f"Produto Teste C04b {suffix}",
        status="ACTIVE",
        daily_budget=25.0,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    row = MetaActionRequest(
        request_key=f"c04b-req-{suffix}",
        campaign_id=campaign.id,
        meta_campaign_id=campaign.meta_campaign_id,
        meta_adset_id=campaign.meta_adset_id,
        action="pause_campaign",
        target="campaign",
        proposed_payload_json="{}",
        payload_hash="fakehash",
        status="approved",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return campaign, row


# ---------------------------------------------------------------------------
# B1: O "segundo gatilho esquecido". Servidor em modo real (meta_dry_run=
# false) com as flags de seguranca no estado padrao SEGURO (autopublish=
# false), e o cliente chama /execute pedindo dry_run=false numa acao ja
# aprovada. ANTES da correcao, isso ia direto para
# self.meta_client.apply_campaign_action(dry_run=False) e tentava a rede de
# verdade. Depois da correcao, deve bloquear, SEM jamais tocar a rede.
# ---------------------------------------------------------------------------
db_b1 = _SessionLocal()
settings_b1 = make_fake_settings(meta_dry_run=False, meta_autopublish=False)
client_b1 = make_client(settings_b1)
service_b1 = make_service(settings_b1, client_b1, db_b1)
campaign_b1, row_b1 = seed_approved_action(db_b1, "b1")
try:
    service_b1.execute_approved_meta_action(request_id=row_b1.id, confirmed_by_user=True, dry_run=False)
    db_b1.refresh(row_b1)
    record(
        "B1_segundo_gatilho_agora_bloqueado",
        row_b1.status == "failed" and "guardrails de ambiente" in (row_b1.failure_reason or ""),
        f"row.status={row_b1.status}, failure_reason={row_b1.failure_reason!r}",
    )
except NetworkTripwireError as e:
    record("B1_segundo_gatilho_agora_bloqueado", False, f"PERIGO: TRIPWIRE DISPAROU -- guard nao bloqueou antes da rede: {e}")
finally:
    db_b1.close()


# ---------------------------------------------------------------------------
# B2: Mesmo cenario, mas agora o SERVIDOR libera tudo deliberadamente
# (autopublish=true, env=sandbox, dry_run=false) -- um humano configurou o
# ambiente para escrever de verdade em sandbox. Aqui o codigo DEVE tentar a
# chamada real (tripwire deve disparar) -- prova que o guard novo nao quebrou
# o caminho legitimo.
# ---------------------------------------------------------------------------
db_b2 = _SessionLocal()
settings_b2 = make_fake_settings(meta_dry_run=False, meta_autopublish=True, meta_env="sandbox")
client_b2 = make_client(settings_b2)
service_b2 = make_service(settings_b2, client_b2, db_b2)
campaign_b2, row_b2 = seed_approved_action(db_b2, "b2")
try:
    resp_b2 = service_b2.execute_approved_meta_action(request_id=row_b2.id, confirmed_by_user=True, dry_run=False)
    record("B2_ambiente_liberado_deveria_tentar_rede", False,
           f"PERIGO: nao tentou rede real -- resp={resp_b2}")
except NetworkTripwireError as e:
    record("B2_ambiente_liberado_deveria_tentar_rede", True,
           "Confirmado: com as flags server-side deliberadamente liberadas, o codigo tenta a chamada real (interceptada pelo tripwire) -- caminho legitimo preservado.")
finally:
    db_b2.close()


# ---------------------------------------------------------------------------
# B3: Regressao - comportamento padrao (meta_dry_run=true) com dry_run=True
# pedido pelo cliente (uso comum). Deve continuar simulando normalmente,
# igual a antes da correcao -- prova que nao ha regressao no uso comum.
# ---------------------------------------------------------------------------
db_b3 = _SessionLocal()
settings_b3 = make_fake_settings()  # defaults seguros, meta_dry_run=True
client_b3 = make_client(settings_b3)
service_b3 = make_service(settings_b3, client_b3, db_b3)
campaign_b3, row_b3 = seed_approved_action(db_b3, "b3")
try:
    resp_b3 = service_b3.execute_approved_meta_action(request_id=row_b3.id, confirmed_by_user=True, dry_run=True)
    db_b3.refresh(row_b3)
    record(
        "B3_regressao_uso_comum_continua_simulando",
        row_b3.status == "executed_dry_run",
        f"row.status={row_b3.status}",
    )
except NetworkTripwireError as e:
    record("B3_regressao_uso_comum_continua_simulando", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")
finally:
    db_b3.close()


# ---------------------------------------------------------------------------
# B4: Servidor com META_ENV=production e autopublish=true, MAS sem
# META_ALLOW_PRODUCTION_REAL -- deve bloquear por production_real_not_allowed,
# mesmo com autopublish=true e dry_run=false pedido pelo cliente.
# ---------------------------------------------------------------------------
db_b4 = _SessionLocal()
settings_b4 = make_fake_settings(meta_dry_run=False, meta_autopublish=True, meta_env="production", meta_allow_production_real=False)
client_b4 = make_client(settings_b4)
service_b4 = make_service(settings_b4, client_b4, db_b4)
campaign_b4, row_b4 = seed_approved_action(db_b4, "b4")
try:
    resp_b4 = service_b4.execute_approved_meta_action(request_id=row_b4.id, confirmed_by_user=True, dry_run=False)
    db_b4.refresh(row_b4)
    record(
        "B4_producao_sem_allow_production_real_bloqueia",
        row_b4.status == "failed" and "production_real_not_allowed" in (row_b4.failure_reason or ""),
        f"row.status={row_b4.status}, failure_reason={row_b4.failure_reason!r}",
    )
except NetworkTripwireError as e:
    record("B4_producao_sem_allow_production_real_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")
finally:
    db_b4.close()


# ---------------------------------------------------------------------------
# B5: Servidor em modo real com guardrails reprovados (autopublish=false),
# MAS o cliente pede dry_run=True explicitamente (preview/simulacao). Isso
# NAO deve ser bloqueado pelo guard -- pedir simulacao e sempre seguro,
# mesmo com o servidor em modo real mal configurado. Prova que o guard novo
# nao super-bloqueia o caminho de simulacao legitimo.
# ---------------------------------------------------------------------------
db_b5 = _SessionLocal()
settings_b5 = make_fake_settings(meta_dry_run=False, meta_autopublish=False)
client_b5 = make_client(settings_b5)
service_b5 = make_service(settings_b5, client_b5, db_b5)
campaign_b5, row_b5 = seed_approved_action(db_b5, "b5")
try:
    resp_b5 = service_b5.execute_approved_meta_action(request_id=row_b5.id, confirmed_by_user=True, dry_run=True)
    db_b5.refresh(row_b5)
    record(
        "B5_cliente_pede_dry_run_true_nunca_bloqueia",
        row_b5.status == "executed_dry_run",
        f"row.status={row_b5.status}",
    )
except NetworkTripwireError as e:
    record("B5_cliente_pede_dry_run_true_nunca_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")
finally:
    db_b5.close()


# ---------------------------------------------------------------------------
print("\n=== RESUMO ===")
total = len(RESULTS)
passed = sum(1 for _, ok, _ in RESULTS if ok)
print(f"{passed}/{total} cenarios passaram conforme esperado.")
for name, ok, detail in RESULTS:
    print(f"  {'PASS' if ok else 'FAIL'} | {name}")
sys.exit(0 if passed == total else 1)
