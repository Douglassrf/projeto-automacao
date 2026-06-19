"""
Missão C02 - Aplicar guard de aprovação humana no site builder.

Cobre os 3 critérios de aceite exigidos:
1. payload normal (dry_run=True) funciona normalmente;
2. payload bloqueado (dry_run=False, sem aprovação) NÃO gera o site;
3. tentativa de burlar a aprovação enviando "confirmed_by_user": true direto no
   corpo da requisição (campo que o schema SiteGenerateRequest não declara)
   continua bloqueada -- prova que a autoaprovação via payload não funciona.

Também verifica que o guard bloqueado é registrado no log de auditoria
imutável (hash-chain), e que a cadeia permanece válida depois do teste.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.immutable_audit import ImmutableAuditLog
from app.main import app
from app.services.observability import _immutable_audit_file


def _payload(product="C02 Teste Guard", dry_run=True, provider="local"):
    return {
        "offer": {
            "product_name": product,
            "niche": "Produto digital",
            "target_geo": "USD Tier 1",
            "language": "en",
            "headline": "Discover a practical method to improve your results today",
            "subheadline": "A direct digital guide built for fast execution and clear next steps.",
            "benefits": ["Clear step-by-step", "Mobile-first experience", "Instant access"],
            "pain_points": ["Too many scattered tactics", "No clear execution path"],
            "checkout_url": "https://checkout.example.com/product",
            "cta_text": "Access now",
        },
        "template": "direct_response",
        "deploy": {"provider": provider, "dry_run": dry_run},
    }


def test_c02_payload_normal_dry_run_ainda_funciona(tmp_path):
    """Critério 1: payload normal (o caminho usado em todas as missões R)
    continua funcionando depois da correção -- nada de regressão."""
    settings = get_settings()
    old = settings.site_output_dir
    settings.site_output_dir = str(tmp_path / "sites")
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/site-builder/generate", json=_payload())
    finally:
        settings.site_output_dir = old

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["security_guard"]["status"] == "ok"
    assert "index.html" in data["files"]
    assert Path(data["preview_path"]).exists()


def test_c02_payload_bloqueado_nao_gera_site(tmp_path):
    """Critério 2: deploy.dry_run=False sem nenhuma aprovação real deve ser
    bloqueado ANTES de qualquer geração de arquivo -- e o site não pode
    existir no disco depois da chamada."""
    settings = get_settings()
    old = settings.site_output_dir
    sites_dir = tmp_path / "sites"
    settings.site_output_dir = str(sites_dir)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/site-builder/generate",
                json=_payload(product="C02 Bloqueado", dry_run=False, provider="vercel"),
            )
    finally:
        settings.site_output_dir = old

    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert "human_approval_required" in detail["blocked_reasons"]
    assert detail["requires_human_approval"] is True
    # Nenhum arquivo deve ter sido criado para este produto.
    assert not sites_dir.exists() or not any(sites_dir.rglob("*C02_Bloqueado*"))
    assert not sites_dir.exists() or not any(sites_dir.rglob("index.html"))


def test_c02_tentativa_de_autoaprovacao_via_payload_falha(tmp_path):
    """Critério 3: mesmo enviando "confirmed_by_user": true diretamente no
    corpo da requisição (campo inexistente no schema SiteGenerateRequest),
    a tentativa de bypass deve continuar bloqueada -- prova de que não dá
    para se autoaprovar só editando o JSON."""
    settings = get_settings()
    old = settings.site_output_dir
    sites_dir = tmp_path / "sites"
    settings.site_output_dir = str(sites_dir)
    try:
        malicious_payload = _payload(product="C02 Bypass", dry_run=False, provider="netlify")
        malicious_payload["confirmed_by_user"] = True  # campo que o schema ignora
        malicious_payload["deploy"]["confirmed_by_user"] = True  # tentativa alternativa
        with TestClient(app) as client:
            response = client.post("/api/v1/site-builder/generate", json=malicious_payload)
    finally:
        settings.site_output_dir = old

    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert "human_approval_required" in detail["blocked_reasons"]
    assert not sites_dir.exists() or not any(sites_dir.rglob("*C02_Bypass*"))


def test_c02_guard_bloqueado_fica_registrado_no_audit_log_imutavel(tmp_path):
    """Critério 'registrar audit log': a tentativa bloqueada precisa aparecer
    no log de auditoria imutável (hash-chain), e a cadeia precisa continuar
    válida (sem corrupção) depois do evento."""
    audit_path = _immutable_audit_file()
    audit_before = ImmutableAuditLog(audit_path)
    verification_before = audit_before.verify()
    events_before = verification_before.total_events

    settings = get_settings()
    old = settings.site_output_dir
    settings.site_output_dir = str(tmp_path / "sites")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/site-builder/generate",
                json=_payload(product="C02 Audit Check", dry_run=False, provider="vercel"),
            )
    finally:
        settings.site_output_dir = old

    assert response.status_code == 403

    audit_after = ImmutableAuditLog(audit_path)
    verification_after = audit_after.verify()
    assert verification_after.ok, f"cadeia de auditoria corrompida: {verification_after.reason}"
    assert verification_after.total_events == events_before + 1

    last_line = audit_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert "site_builder.generate.blocked" in last_line
    assert "C02 Audit Check" in last_line
