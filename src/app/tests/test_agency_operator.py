from fastapi.testclient import TestClient
from app.main import app


def test_agency_operator_workflow_lifecycle():
    with TestClient(app) as client:
        create = client.post('/api/v1/agency-operator/workflows', json={
            'title': 'Post de prova para Instagram',
            'brief': 'Gerar postagem com promessa clara, prova e CTA para produto digital.',
            'platform': 'Instagram',
            'content_type': 'post',
            'requires_approval': True,
        })
        assert create.status_code == 200, create.text
        data = create.json()
        assert data['status'] == 'REVIEW_PENDING'
        assert data['draft']['headline'] == 'Post de prova para Instagram'

        approved = client.post(f"/api/v1/agency-operator/workflows/{data['id']}/approve", json={'notes': 'Aprovado no teste'})
        assert approved.status_code == 200, approved.text
        assert approved.json()['status'] == 'APPROVED'

        published = client.post(f"/api/v1/agency-operator/workflows/{data['id']}/publish", json={'notes': 'Publicado em dry-run'})
        assert published.status_code == 200, published.text
        assert published.json()['status'] == 'PUBLISHED'

        listed = client.get('/api/v1/agency-operator/workflows')
        assert listed.status_code == 200
        assert listed.json()['total'] >= 1
