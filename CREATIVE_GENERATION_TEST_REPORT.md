# CREATIVE_GENERATION_TEST_REPORT.md — Missão R07 (Teste de Criativos)

Data: 2026-06-19. Commit testado: `700bf363e4d7d313edcb9e6c3b344603ea2101fd`. Backend real (`uvicorn`) rodando, rota real `POST /api/v1/war-kit/generate` testada via HTTP real (`curl`), com e sem token JWT real, nenhuma chamada externa real (IA de imagem, render de vídeo, upload de nuvem) feita.

## 1. Mapeamento do código (antes do teste)

- **`WarKitGenerator`** (`services/war_kit_generator.py`): gera um "kit de campanha" completo a partir do DNA do produto — pastas `Criativos/`, `Copies/`, `PDFs/`, `Videos/`, `Meta_Upload/`. Tudo é gerado por templates locais determinísticos (`_copy_pack`, `_image_prompts`, `_video_scripts`, `_pdf_content`), sem chamada a nenhuma API externa de IA (o próprio docstring confirma: "usa templates locais determinísticos"; pontos de extensão para OpenAI/Ollama existem mas não estão implementados).
- Gera um PDF mínimo real (não um mock) via geração manual do formato `%PDF-1.4` (sem libs externas).
- `render_video_assets` (opcional): se `true` e a flag de ambiente `WAR_KIT_EXECUTE_VIDEO_RENDER` não estiver habilitada (default `False`), o resultado é apenas `mode:"queued_render_job"` — não executa render nenhum, só monta o payload de requisição para o pipeline de vídeo separado (R08).
- `push_to_storage` (opcional): delega a `CampaignKitStorageProvider.upload_folder()`, cujo provider default é `"local"` (grava só localmente). Os adaptadores S3/Drive existem como stub (`status:"adapter_ready"`/`"skipped"`) e não fazem upload real — confirmado por leitura do código (`integrations/storage_provider.py`), sem nenhuma chamada de SDK de nuvem.
- Rota `POST /api/v1/war-kit/generate` (`api/routes/war_kit.py`) **declara corretamente `Depends(get_current_user)`** — diferente das rotas dos R04/R05/R06, esta rota já segue o padrão correto de exigir autenticação no código.

## 2. Testes executados e resultado real

| # | Cenário | Esperado | Resultado real | Status |
|---|---|---|---|---|
| 1 | `POST /war-kit/generate`, kit completo (pdf+imagens+vídeos+copies+meta), **sem header Authorization** | Como a rota declara `Depends(get_current_user)`, isso é uma checagem real de código — porém `AUTH_REQUIRED=false` no `.env` (achado do R02) faz `get_current_user` devolver o admin padrão sem token | 200 — kit gerado normalmente sem token, **mas pela mesma causa raiz do R02** (config, não falta de código) | ⚠️ achado (já mapeado, não novo) |
| 2 | Mesmo payload, **com token JWT real** (login real feito) | 200, kit completo gerado | 200, `total_files:15`, todas as 5 pastas presentes | ✅ |
| 3 | (verificação de disco) | confirmar 15 arquivos reais no kit | Confirmado por `find` real — README, manifest, knowledge_context, 3 copy packs, 3 image prompts, 3 video scripts, PDF .md + .pdf, Meta payload | ✅ |
| 4 | Validar o PDF gerado (`_write_minimal_pdf`) | deve ter assinatura `%PDF-` real | Confirmado: `head -c 8` retornou `%PDF-1.4` | ✅ |
| 5 | `push_to_storage:true`, sem credenciais S3/Drive configuradas | não deve fazer upload de nuvem real | `storage_status:"stored_local"` — confirma que ficou só local (provider default), nenhuma tentativa de rede | ✅ |
| 6 | `render_video_assets:true`, sem `WAR_KIT_EXECUTE_VIDEO_RENDER` habilitado (tentativa de forçar render pesado) | deve apenas enfileirar, não executar ffmpeg | `mode:"queued_render_job"`, payload de request preparado, nenhum MP4 gerado | ✅ |

## 3. Confirmado: nenhuma chamada de IA externa real ocorre na geração de criativos

Inspecionei o código de geração de copy, prompts de imagem e roteiros de vídeo (`_copy_pack`, `_image_prompts`, `_video_scripts`) — são 100% templates de string local usando o "DNA da oferta" enviado no payload e o `knowledge_engine` (regras internas de copy/criativo). Não há chamada de rede, chave de API de IA de imagem/texto, nem dependência de serviço externo. Isso foi confirmado tanto por leitura do código quanto pela execução real (kit gerado em ~instantâneo, sem latência de rede, com conteúdo determinístico baseado no payload).

## 4. Achado: rota corretamente protegida por código, mas neutralizada pela mesma causa raiz do R02

Diferente do padrão visto no R04/R05/R06, a rota de War Kit **declara corretamente `Depends(get_current_user)`** — ou seja, no nível de código, está certa. O teste 1 mostra que, mesmo assim, uma chamada sem nenhum header `Authorization` retornou 200 e gerou o kit completo. Isso não é um achado novo: é a mesma causa raiz documentada no R02 (`AUTH_REQUIRED=false` no `.env`/`.env.example` faz `get_current_user` devolver o usuário admin padrão para qualquer chamador, sem token). A diferença em relação ao R04/R05/R06 é que, **se a equipe corrigir apenas o R02 (`AUTH_REQUIRED=true`)**, esta rota específica já ficará protegida de verdade, sem precisar de nenhuma mudança de código adicional — não é o caso das rotas de mineração/inteligência/site builder, que precisam de uma correção de código própria além da config.

## 5. O que funcionou corretamente (sem achado negativo)

- Geração completa do kit (copy, imagem, vídeo, PDF, payload Meta) funciona de ponta a ponta com dados reais de entrada.
- PDF gerado é um arquivo PDF real e válido (assinatura de magic bytes confirmada), não um texto renomeado.
- Tentativa de forçar render de vídeo pesado corretamente contida — apenas enfileira, não executa ffmpeg nem qualquer geração de IA de vídeo.
- Tentativa de upload para nuvem corretamente contida — nenhuma chamada real a S3/Drive, mesmo pedindo explicitamente `push_to_storage:true`.
- Avisos (`warnings`) corretos quando nenhum anúncio minerado é enviado, orientando o usuário a revisar antes de publicar.

## 6. Conclusão da missão R07

| Item | Resultado |
|---|---|
| Geração de copy/imagem/vídeo (templates locais) | Funciona corretamente, sem chamada de IA externa real |
| Geração de PDF real | Funciona, arquivo `%PDF-1.4` válido confirmado |
| Bloqueio de render de vídeo pesado não solicitado explicitamente | Funciona — apenas enfileira |
| Bloqueio de upload real para nuvem (S3/Drive) | Funciona — fica local por padrão, adaptadores são stub |
| Autenticação declarada no código da rota | **Presente** (ponto positivo, diferente do R04/R05/R06) |
| Autenticação efetiva em runtime | Ausente — mesma causa raiz do R02 (`AUTH_REQUIRED=false`), não um achado novo |
| Banco de produção real | Intacto, não tocado |

**Status R07: APROVADO.** A geração de criativos funciona corretamente, de forma determinística e sem nenhuma chamada externa real, mesmo sob tentativa adversarial de forçar render de vídeo ou upload de nuvem. A rota já está corretamente protegida por código — a exposição observada decorre exclusivamente da mesma causa raiz já registrada no R02, sem necessidade de nova recomendação. Pronto para avançar para R08.
