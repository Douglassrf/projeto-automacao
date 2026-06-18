from app.services.serverless_render import ServerlessRenderPlanner
from app.schemas.serverless_render import ServerlessRenderRequest


def test_serverless_render_job_generates_payloads():
    response = ServerlessRenderPlanner().create_job(
        ServerlessRenderRequest(
            product_name="Ebook Global",
            asset_type="image",
            prompt="Imagem persuasiva para anúncio de produto digital com alto CTR.",
            provider="dry_run",
            dry_run=True,
        )
    )

    assert response.status == "dry_run"
    assert response.job_id.startswith("srv-ebook-global-image")
    assert response.queue_payload_file.endswith("queue_payload.json")
    assert response.aws_lambda_payload_file.endswith("aws_lambda_event.json")
    assert response.google_function_payload_file.endswith("google_cloud_function_event.json")
    assert response.guardrails


def test_serverless_render_video_warns_about_function_limits():
    response = ServerlessRenderPlanner().create_job(
        ServerlessRenderRequest(
            product_name="Curso Fitness",
            asset_type="video",
            prompt="Vídeo vertical curto com hook forte e CTA para compra.",
            provider="aws_lambda",
            dry_run=True,
        )
    )

    assert response.status == "dry_run"
    assert any("Vídeo" in warning for warning in response.warnings)
