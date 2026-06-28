"""Missao 48 - Documentacao Viva.

Justificativa real coberta por estes testes: o README.md estatico deste
repositorio afirma "Requer Python 3.11+" e "261 passed", nenhum dos dois
reflete o estado atual (Python 3.10 real no ambiente; suite com 489+
testes apos a Missao 47). `DocumentationService` gera o snapshot a partir
do estado vivo (rotas carregadas via safe_router, schema de Settings via
model_fields, validate_settings(), arquivo VERSION) em vez de depender de
texto estatico copiado a mao.

Cobre: routes_summary() (reusa LOADED_ROUTES/FAILED_ROUTES/ROUTE_MODULES
do safe_router), settings_summary() (introspeccao de Settings.model_fields
+ redacao de campos de segredo por nome), live_snapshot() (agregacao +
validate_settings() real), render_markdown() (documento textual gerado),
os novos endpoints /documentation/* e as novas regras de
validate_settings()/CONFIG_SCHEMA_VERSION (Missao 48).
"""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.config_profiles import CONFIG_SCHEMA_VERSION, Environment, validate_settings
from app.main import app
from app.services.documentation_service import DocumentationService, _is_secret_field


def test_is_secret_field_matches_known_secret_names():
    assert _is_secret_field("jwt_secret_key") is True
    assert _is_secret_field("default_admin_password") is True
    assert _is_secret_field("meta_access_token") is True
    assert _is_secret_field("openai_api_key") is True
    assert _is_secret_field("huggingface_token") is True


def test_is_secret_field_does_not_match_unrelated_names():
    assert _is_secret_field("upload_max_bytes") is False
    assert _is_secret_field("cache_default_ttl_seconds") is False
    assert _is_secret_field("recovery_max_jobs_per_sweep") is False


def test_routes_summary_reuses_safe_router_state():
    from app.api.safe_router import FAILED_ROUTES, LOADED_ROUTES, ROUTE_MODULES

    summary = DocumentationService().routes_summary()
    assert summary["declared"] == len(ROUTE_MODULES)
    assert summary["loaded"] == len(LOADED_ROUTES)
    assert summary["failed"] == len(FAILED_ROUTES)
    assert summary["failed_details"] == FAILED_ROUTES
    # A rota desta propria missao deve estar entre as carregadas.
    assert any("documentation" in module for module in summary["loaded_modules"])


def test_settings_summary_redacts_secret_values_by_default():
    settings = get_settings()
    previous = settings.documentation_redact_secrets
    try:
        settings.documentation_redact_secrets = True
        fields = DocumentationService(settings).settings_summary()
        by_name = {f["name"]: f for f in fields}
        jwt_field = by_name["jwt_secret_key"]
        assert jwt_field["secret"] is True
        assert jwt_field["value"] == "***redacted***"
    finally:
        settings.documentation_redact_secrets = previous


def test_settings_summary_shows_real_value_when_redaction_disabled():
    settings = get_settings()
    previous = settings.documentation_redact_secrets
    try:
        settings.documentation_redact_secrets = False
        fields = DocumentationService(settings).settings_summary()
        by_name = {f["name"]: f for f in fields}
        jwt_field = by_name["jwt_secret_key"]
        assert jwt_field["secret"] is True
        assert jwt_field["value"] == settings.jwt_secret_key
    finally:
        settings.documentation_redact_secrets = previous


def test_settings_summary_never_redacts_non_secret_fields():
    fields = DocumentationService().settings_summary()
    by_name = {f["name"]: f for f in fields}
    upload_field = by_name["upload_max_bytes"]
    assert upload_field["secret"] is False
    assert upload_field["value"] == str(get_settings().upload_max_bytes)


def test_settings_summary_marks_configured_when_value_differs_from_default():
    settings = get_settings()
    previous = settings.upload_max_bytes
    try:
        settings.upload_max_bytes = previous + 12345
        fields = DocumentationService(settings).settings_summary()
        by_name = {f["name"]: f for f in fields}
        assert by_name["upload_max_bytes"]["configured"] is True
    finally:
        settings.upload_max_bytes = previous


def test_settings_summary_covers_every_settings_field():
    settings = get_settings()
    fields = DocumentationService(settings).settings_summary()
    assert len(fields) == len(type(settings).model_fields)


def test_live_snapshot_shape_and_reused_values():
    snapshot = DocumentationService().live_snapshot()
    assert snapshot["config_schema_version"] == CONFIG_SCHEMA_VERSION
    assert snapshot["environment"] in [e.value for e in Environment]
    assert isinstance(snapshot["routes"], dict)
    assert snapshot["settings_field_count"] == len(snapshot["settings_fields"])
    assert isinstance(snapshot["settings_issues"], list)
    assert snapshot["generated_at"] is not None


def test_live_snapshot_reads_version_file():
    snapshot = DocumentationService().live_snapshot()
    # O arquivo VERSION existe na raiz deste repositorio (ver VERSION).
    assert snapshot["version_file"] is not None
    assert snapshot["version_file"] != ""


def test_render_markdown_contains_key_sections():
    md = DocumentationService().render_markdown()
    assert "# Documentacao Viva" in md
    assert "## Rotas" in md
    assert "## Configuracao" in md
    assert "***redacted***" in md or "jwt_secret_key" in md


def test_render_markdown_accepts_precomputed_snapshot():
    svc = DocumentationService()
    snapshot = svc.live_snapshot()
    md = svc.render_markdown(snapshot)
    assert str(snapshot["config_schema_version"]) in md


def test_live_endpoint_returns_expected_shape():
    client = TestClient(app)
    response = client.get("/api/v1/documentation/live")
    assert response.status_code == 200
    body = response.json()
    assert body["config_schema_version"] == CONFIG_SCHEMA_VERSION
    assert "routes" in body
    assert "settings_fields" in body
    assert isinstance(body["settings_fields"], list)


def test_live_endpoint_redacts_secrets_in_http_response():
    client = TestClient(app)
    response = client.get("/api/v1/documentation/live")
    body = response.json()
    by_name = {f["name"]: f for f in body["settings_fields"]}
    assert by_name["jwt_secret_key"]["value"] == "***redacted***"


def test_markdown_endpoint_returns_text_markdown():
    client = TestClient(app)
    response = client.get("/api/v1/documentation/markdown")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "# Documentacao Viva" in response.text


def test_config_schema_version_bumped_for_mission_48():
    # Comparação por tupla (não igualdade estrita): a Missão 48 bumpou de
    # 1.6.0 para 1.7.0. Missões futuras (ex.: 49, 50) bumpam de novo - esta
    # asserção verifica que o bump da Missão 48 permanece em vigor (>= 1.7.0),
    # sem quebrar quando uma missão posterior aumentar a versão de novo.
    current = tuple(int(part) for part in CONFIG_SCHEMA_VERSION.split("."))
    assert current >= (1, 7, 0)


def test_validate_settings_rejects_disabled_redaction_in_production():
    settings = get_settings()
    previous = settings.documentation_redact_secrets
    try:
        settings.documentation_redact_secrets = False
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert any("documentation_redact_secrets" in issue for issue in issues)
    finally:
        settings.documentation_redact_secrets = previous


def test_validate_settings_accepts_default_redaction_in_production():
    settings = get_settings()
    previous = settings.documentation_redact_secrets
    try:
        settings.documentation_redact_secrets = True
        issues = validate_settings(settings, Environment.PRODUCTION)
        assert not any("documentation_redact_secrets" in issue for issue in issues)
    finally:
        settings.documentation_redact_secrets = previous


def test_validate_settings_ignores_redaction_flag_outside_production():
    settings = get_settings()
    previous = settings.documentation_redact_secrets
    try:
        settings.documentation_redact_secrets = False
        issues = validate_settings(settings, Environment.DEVELOPMENT)
        assert not any("documentation_redact_secrets" in issue for issue in issues)
    finally:
        settings.documentation_redact_secrets = previous
