from __future__ import annotations

import json
import re
from datetime import datetime, timezone
UTC = timezone.utc  # compat Python 3.10 (datetime.UTC requer 3.11+)
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings, safe_project_path
from app.schemas.serverless_render import ServerlessRenderRequest, ServerlessRenderJobResponse


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._ -]", "", value).strip().lower()
    value = re.sub(r"\s+", "-", value)
    return value[:80] or "produto"


class ServerlessRenderPlanner:
    """Planeja render pesado como job serverless/event-driven.

    Mantém o FastAPI leve: ele cria payloads e arquivos de execução, mas o render
    pesado deve rodar em Lambda, Cloud Functions, Cloud Run Job, HF Space ou n8n.
    """

    def __init__(self):
        self.settings = get_settings()

    def create_job(self, payload: ServerlessRenderRequest) -> ServerlessRenderJobResponse:
        now = datetime.now(UTC)
        job_id = f"srv-{_slug(payload.product_name)}-{payload.asset_type}-{uuid4().hex[:8]}"
        output_dir = safe_project_path(self.settings.orchestration_output_dir, "data/orchestration_runs") / "serverless_render_jobs" / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        base_payload = self._base_payload(payload, job_id, now)
        queue_file = output_dir / "queue_payload.json"
        aws_file = output_dir / "aws_lambda_event.json"
        gcp_file = output_dir / "google_cloud_function_event.json"
        gha_file = output_dir / "serverless-render.yml"
        readme_file = output_dir / "README.md"

        queue_file.write_text(json.dumps(base_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        aws_file.write_text(json.dumps(self._aws_event(base_payload), ensure_ascii=False, indent=2), encoding="utf-8")
        gcp_file.write_text(json.dumps(self._gcp_event(base_payload), ensure_ascii=False, indent=2), encoding="utf-8")
        gha_file.write_text(self._github_actions_yaml(payload), encoding="utf-8")
        readme_file.write_text(self._readme(payload, job_id), encoding="utf-8")

        warnings: list[str] = []
        if payload.dry_run:
            warnings.append("Dry-run ativo: nenhum provedor externo foi chamado.")
        if payload.provider in {"aws_lambda", "google_cloud_functions"} and payload.asset_type == "video":
            warnings.append("Vídeo pode estourar limite de tempo/memória em Function; prefira Cloud Run Job ou Hugging Face Space para render longo.")
        if payload.max_cost_usd == 0:
            warnings.append("Guardrail de custo zero ativo: bloquear execução se houver custo estimado maior que US$0.")

        return ServerlessRenderJobResponse(
            status="dry_run" if payload.dry_run else "queued",
            job_id=job_id,
            product_name=payload.product_name,
            asset_type=payload.asset_type,
            provider=payload.provider,
            generated_at=now,
            queue_payload_file=str(queue_file),
            aws_lambda_payload_file=str(aws_file),
            google_function_payload_file=str(gcp_file),
            github_actions_file=str(gha_file),
            estimated_fixed_cost="US$0 fixo; paga apenas execução e deve ficar no Free Tier em baixo volume.",
            next_step=self._next_step(payload),
            guardrails=[
                "dry_run padrão antes de acionar provedor externo",
                "max_cost_usd para bloquear execuções caras",
                "callback_url opcional para retornar status sem prender o backend",
                "storage_target separado do backend para não lotar disco local",
                "logs por job_id para auditoria e retry",
            ],
            warnings=warnings,
        )

    def _base_payload(self, payload: ServerlessRenderRequest, job_id: str, now: datetime) -> dict:
        return {
            "job_id": job_id,
            "created_at": now.isoformat(),
            "product_name": payload.product_name,
            "asset_type": payload.asset_type,
            "prompt": payload.prompt,
            "provider": payload.provider,
            "runtime": payload.target_runtime,
            "storage_target": payload.storage_target,
            "callback_url": str(payload.callback_url) if payload.callback_url else None,
            "max_cost_usd": payload.max_cost_usd,
            "dry_run": payload.dry_run,
            "render_contract": {
                "input": "JSON event",
                "output": "asset_url + metadata + status",
                "retry_safe": True,
            },
        }

    def _aws_event(self, base: dict) -> dict:
        return {"version": "1.0", "source": "adintelligence.serverless_render", "detail-type": "RenderJob", "detail": base}

    def _gcp_event(self, base: dict) -> dict:
        return {"data": base, "attributes": {"event_type": "render_job", "job_id": base["job_id"]}}

    def _github_actions_yaml(self, payload: ServerlessRenderRequest) -> str:
        return f"""name: Serverless Render Job

on:
  workflow_dispatch:
    inputs:
      asset_type:
        description: Asset type
        required: true
        default: {payload.asset_type}
      provider:
        description: Render provider
        required: true
        default: {payload.provider}

jobs:
  render:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Validate render payload
        run: python -m json.tool queue_payload.json
      - name: Dispatch render webhook
        env:
          RENDER_WEBHOOK_URL: ${{{{ secrets.RENDER_WEBHOOK_URL }}}}
          RENDER_WEBHOOK_SECRET: ${{{{ secrets.RENDER_WEBHOOK_SECRET }}}}
        run: |
          echo "Dispatching serverless render job in dry-run safe mode"
          test -f queue_payload.json
"""

    def _readme(self, payload: ServerlessRenderRequest, job_id: str) -> str:
        return f"""# Serverless Render Job — {job_id}

Este job foi criado para renderizar `{payload.asset_type}` fora do backend principal.

## Estratégia
- Backend FastAPI apenas cria o payload.
- Render pesado roda em `{payload.provider}`.
- Resultado volta por callback ou storage.
- Sem cluster próprio e sem auto-scaling manual.

## Arquivos
- `queue_payload.json`: contrato genérico para Redis/n8n/worker.
- `aws_lambda_event.json`: evento pronto para Lambda/EventBridge.
- `google_cloud_function_event.json`: evento pronto para Cloud Functions/PubSub.
- `serverless-render.yml`: workflow GitHub Actions para despachar o job.
"""

    def _next_step(self, payload: ServerlessRenderRequest) -> str:
        if payload.dry_run:
            return "Revisar payload gerado e desativar dry_run apenas quando o webhook/provedor estiver configurado."
        return f"Enviar o payload para {payload.provider} e salvar o resultado em {payload.storage_target}."
