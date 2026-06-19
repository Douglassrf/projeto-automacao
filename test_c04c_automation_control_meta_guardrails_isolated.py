"""
TESTE ISOLADO C04c - terceiro achado da auditoria "ponta a ponta" da C04.
NUNCA usa o .env real, NUNCA chama rede real (usa banco sqlite temporario
proprio + tripwire de rede).

Contexto do achado:

A auditoria de C04 já tinha corrigido dois caminhos com o mesmo padrão de
bug (FacebookMarketingAutomationEngine.v3_execute() e
CampaignIntelligenceService.execute_approved_meta_action()): checavam
META_DRY_RUN, mas nunca META_ENV / META_ALLOW_PRODUCTION_REAL antes de uma
escrita real na Meta.

AutomationControlService.apply_suggestion() (rota
POST /api/v1/automation-control/apply-suggestion) tem o MESMO gap: para
pause_campaign/pause_adset/scale_budget, ela já checa kill switch, limite de
gasto diário, AUTOMATION_LEVEL (0/1/2), AUTOMATION_LEVEL_2_ENABLED e
credenciais configuradas -- uma camada de guardrails própria e robusta --
mas nunca checava META_ENV nem META_ALLOW_PRODUCTION_REAL. Bastava o
operador já ter ligado AUTOMATION_LEVEL=1 + META_DRY_RUN=false + kill switch
desligado (configuração que, sozinha, não distingue sandbox de produção)
para qualquer requisição com confirmed_by_user=true tentar escrever de
verdade na Meta, mesmo que o servidor não tivesse META_ALLOW_PRODUCTION_REAL
habilitado.

Correção aplicada: novo metodo _real_mode_guardrails() (mesmo padrão e mesmo
nome dos outros dois arquivos) chamado em apply_suggestion() antes da
chamada real, só quando a chamada seria de fato real (nunca bloqueia um
pedido de dry_run/force_dry_run). Evento de bloqueio registrado no log de
auditoria imutável.

Estrategia de seguranca (mesmo padrão do C04/C04b):
1. Settings 100% sintetico, _env_file=None (nunca le nenhum .env).
2. Credenciais fake (token/IDs claramente marcados como FAKE).
3. Banco sqlite temporario proprio (nunca o adintelligence.db real).
4. Tripwire de rede: monkeypatch em httpx.get/post/delete que lanca excecao
   imediata se qualquer codigo tentar de fato sair para a rede.
"""
import sys
sys.path.insert(0, "/tmp/projeto_fast/src")
import tempfile

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.session import Base
from app.integrations import meta_marketing as meta_marketing_module
from app.schemas.automation_control import ApplySuggestionRequest
from app.services import automation_control as ac_module

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


_tmp_db_path = tempfile.NamedTemporaryFile(prefix="c04c_isolated_", suffix=".db", delete=False).name
_engine = create_engine(f"sqlite:///{_tmp_db_path}", connect_args={"check_same_thread": False}, future=True)
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


def make_fake_settings(**overrides):
    base = dict(
        _env_file=None,
        meta_access_token="FAKE_TOKEN_ISOLATED_TEST_C04C_NAO_E_REAL",
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
        meta_created_resources_log="/tmp/c04c_isolated/fake_created_resources.jsonl",
        automation_level=1,
        automation_level_2_enabled=False,
        automation_daily_spend_limit_brl=50.0,
        kill_switch_enabled=False,
    )
    base.update(overrides)
    return Settings(**base)


def make_client(settings):
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
    service = object.__new__(ac_module.AutomationControlService)
    service.db = db
    service.meta_client = client
    service.settings = settings
    return service


def make_payload(**overrides):
    data = dict(
        campaign_id="c04c-camp-1",
        adset_id=None,
        action="pause_campaign",
        target="campaign",
        reason_code="ZERO_PURCHASE_GUARD",
        metric_name="spend_without_purchase",
        metric_value=25,
        threshold_value=25,
        daily_spend_brl=10,
        current_purchases=0,
        confirmed_by_user=True,
        force_dry_run=False,
    )
    data.update(overrides)
    return ApplySuggestionRequest(**data)


# ---------------------------------------------------------------------------
# C1: AUTOMATION_LEVEL=1, META_DRY_RUN=false, kill switch desligado, gasto
# dentro do limite, confirmed_by_user=true -- tudo que o guard ANTIGO exigia
# já está satisfeito. META_ENV ausente/invalido (nunca configurado). ANTES
# da correção, isso ia direto para meta_client.apply_campaign_action(
# dry_run=False) e tentava a rede de verdade. Depois, deve bloquear, SEM
# jamais tocar a rede.
# ---------------------------------------------------------------------------
db_c1 = _SessionLocal()
settings_c1 = make_fake_settings(meta_dry_run=False, meta_env="")
client_c1 = make_client(settings_c1)
service_c1 = make_service(settings_c1, client_c1, db_c1)
try:
    resp_c1 = service_c1.apply_suggestion(make_payload())
    record(
        "C1_meta_env_ausente_agora_bloqueado",
        resp_c1.blocked and "guardrails de ambiente" in (resp_c1.blocked_reason or ""),
        f"blocked={resp_c1.blocked}, blocked_reason={resp_c1.blocked_reason!r}",
    )
except NetworkTripwireError as e:
    record("C1_meta_env_ausente_agora_bloqueado", False, f"PERIGO: TRIPWIRE DISPAROU -- guard nao bloqueou antes da rede: {e}")
finally:
    db_c1.close()


# ---------------------------------------------------------------------------
# C2: Mesmo cenário, mas o SERVIDOR libera META_ENV=sandbox deliberadamente
# -- um humano configurou o ambiente para escrever de verdade em sandbox.
# Aqui o código DEVE tentar a chamada real (tripwire deve disparar) -- prova
# que o guard novo não quebrou o caminho legítimo.
# ---------------------------------------------------------------------------
db_c2 = _SessionLocal()
settings_c2 = make_fake_settings(meta_dry_run=False, meta_env="sandbox")
client_c2 = make_client(settings_c2)
service_c2 = make_service(settings_c2, client_c2, db_c2)
try:
    resp_c2 = service_c2.apply_suggestion(make_payload())
    record("C2_ambiente_liberado_deveria_tentar_rede", False,
           f"PERIGO: nao tentou rede real -- resp.meta_response={resp_c2.meta_response}")
except NetworkTripwireError as e:
    record("C2_ambiente_liberado_deveria_tentar_rede", True,
           "Confirmado: com META_ENV=sandbox deliberadamente liberado, o codigo tenta a chamada real (interceptada pelo tripwire) -- caminho legitimo preservado.")
finally:
    db_c2.close()


# ---------------------------------------------------------------------------
# C3: Regressão - comportamento padrão (meta_dry_run=true) com
# force_dry_run=false pedido pelo payload (uso comum: nível 1, usuário
# confirma). Deve continuar simulando normalmente -- prova que não há
# regressão no uso comum mais frequente da automação.
# ---------------------------------------------------------------------------
db_c3 = _SessionLocal()
settings_c3 = make_fake_settings()  # defaults seguros, meta_dry_run=True
client_c3 = make_client(settings_c3)
service_c3 = make_service(settings_c3, client_c3, db_c3)
try:
    resp_c3 = service_c3.apply_suggestion(make_payload())
    record(
        "C3_regressao_uso_comum_continua_simulando",
        resp_c3.blocked is False and resp_c3.dry_run is True,
        f"blocked={resp_c3.blocked}, dry_run={resp_c3.dry_run}",
    )
except NetworkTripwireError as e:
    record("C3_regressao_uso_comum_continua_simulando", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")
finally:
    db_c3.close()


# ---------------------------------------------------------------------------
# C4: Servidor com META_ENV=production, MAS sem META_ALLOW_PRODUCTION_REAL
# -- deve bloquear por production_real_not_allowed, mesmo com todas as
# outras camadas (kill switch, gasto, nível, confirmação) satisfeitas.
# ---------------------------------------------------------------------------
db_c4 = _SessionLocal()
settings_c4 = make_fake_settings(meta_dry_run=False, meta_env="production", meta_allow_production_real=False)
client_c4 = make_client(settings_c4)
service_c4 = make_service(settings_c4, client_c4, db_c4)
try:
    resp_c4 = service_c4.apply_suggestion(make_payload())
    record(
        "C4_producao_sem_allow_production_real_bloqueia",
        resp_c4.blocked and "production_real_not_allowed" in (resp_c4.blocked_reason or ""),
        f"blocked={resp_c4.blocked}, blocked_reason={resp_c4.blocked_reason!r}",
    )
except NetworkTripwireError as e:
    record("C4_producao_sem_allow_production_real_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")
finally:
    db_c4.close()


# ---------------------------------------------------------------------------
# C5: Servidor em estado inseguro (meta_dry_run=false, meta_env ausente),
# MAS o payload pede force_dry_run=true explicitamente (preview/simulação).
# Isso NÃO deve ser bloqueado pelo guard novo -- pedir simulação é sempre
# seguro. Prova que o guard novo não super-bloqueia o caminho de simulação
# legítimo.
# ---------------------------------------------------------------------------
db_c5 = _SessionLocal()
settings_c5 = make_fake_settings(meta_dry_run=False, meta_env="")
client_c5 = make_client(settings_c5)
service_c5 = make_service(settings_c5, client_c5, db_c5)
try:
    resp_c5 = service_c5.apply_suggestion(make_payload(force_dry_run=True))
    record(
        "C5_cliente_pede_force_dry_run_nunca_bloqueia",
        resp_c5.blocked is False and resp_c5.dry_run is True,
        f"blocked={resp_c5.blocked}, dry_run={resp_c5.dry_run}",
    )
except NetworkTripwireError as e:
    record("C5_cliente_pede_force_dry_run_nunca_bloqueia", False, f"TRIPWIRE DISPAROU (NAO deveria): {e}")
finally:
    db_c5.close()


# ---------------------------------------------------------------------------
print("\n=== RESUMO ===")
total = len(RESULTS)
passed = sum(1 for _, ok, _ in RESULTS if ok)
print(f"{passed}/{total} cenarios passaram conforme esperado.")
for name, ok, detail in RESULTS:
    print(f"  {'PASS' if ok else 'FAIL'} | {name}")
sys.exit(0 if passed == total else 1)
