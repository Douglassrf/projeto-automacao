# Serverless Render Job — srv-curso-fitness-video-32d35507

Este job foi criado para renderizar `video` fora do backend principal.

## Estratégia
- Backend FastAPI apenas cria o payload.
- Render pesado roda em `aws_lambda`.
- Resultado volta por callback ou storage.
- Sem cluster próprio e sem auto-scaling manual.

## Arquivos
- `queue_payload.json`: contrato genérico para Redis/n8n/worker.
- `aws_lambda_event.json`: evento pronto para Lambda/EventBridge.
- `google_cloud_function_event.json`: evento pronto para Cloud Functions/PubSub.
- `serverless-render.yml`: workflow GitHub Actions para despachar o job.
