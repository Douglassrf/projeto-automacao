from fastapi.testclient import TestClient
from app.main import app


def test_content_orchestrator_blocks_duplicate():
    payload = {
        "title": "Como criar anúncios campeões para afiliados",
        "brief": "Conteúdo sobre dor, transformação, CTA e avatar para afiliados que querem melhorar anúncios.",
        "existing_content": [{"title": "Como criar anuncios campeoes para afiliados", "summary": "Guia antigo sobre anúncios."}],
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/content-orchestrator/route", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "erro"
    assert data["proximo_passo"] == "revisar_ideia_ou_alterar_angulo"


def test_content_orchestrator_routes_image():
    payload = {
        "title": "Imagem de anúncio para ebook de marketing",
        "brief": "Criar uma imagem para público afiliado. A dor é falta de criativo, o benefício é validar campanhas rápido, com CTA para acessar agora e prova por ROAS.",
        "desired_format": "auto",
        "existing_content": [],
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/content-orchestrator/route", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["generated_payload"]["type"] == "image"
    assert data["proximo_passo"] == "huggingface_stable_diffusion"


def test_content_orchestrator_blocks_low_quality():
    payload = {"title": "Post", "brief": "Fazer algo legal", "desired_format": "text"}
    with TestClient(app) as client:
        response = client.post("/api/v1/content-orchestrator/route", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "erro"
    assert data["proximo_passo"] == "melhorar_brief_e_reenviar"
