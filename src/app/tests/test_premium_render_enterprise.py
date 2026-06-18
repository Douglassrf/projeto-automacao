from fastapi.testclient import TestClient

from app.main import app


def test_premium_render_image_dry_run():
    with TestClient(app) as client:
        response = client.post('/api/v1/premium-render/run', json={
            'product_name': 'Produto Teste',
            'asset_type': 'image',
            'prompt': 'Imagem premium de anúncio com iluminação cinematográfica e CTA forte.',
            'provider': 'dry_run',
            'upscale': True,
            'color_grade': 'warm_contrast',
            'dry_run': True
        })
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'dry_run'
    assert data['final_file'].endswith('.jpg')
    assert data['upscaled_file']


def test_worker_blueprint():
    with TestClient(app) as client:
        response = client.get('/api/v1/premium-render/workers/blueprint')
    assert response.status_code == 200
    data = response.json()
    assert data['queue'] == 'render-premium'
    assert 'celery' in data['start_command']


def test_observability_health():
    with TestClient(app) as client:
        response = client.get('/api/v1/observability/health')
    assert response.status_code == 200
    data = response.json()
    assert 'render_error_rate' in data['monitored_signals']
