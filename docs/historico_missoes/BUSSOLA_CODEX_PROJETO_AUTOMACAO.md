# BÚSSOLA OPERACIONAL PARA CODEX — Projeto Automação / Radar PDF IA

## 1. Contexto geral do projeto

Projeto local em Windows:

```txt
C:\Users\USUÁRIO\Desktop\projeto_automacao
```

Raiz técnica usada para rodar o backend:

```txt
C:\Users\USUÁRIO\Desktop\projeto_automacao\src
```

Stack principal identificada:

```txt
Backend: FastAPI / Python
Servidor local: Uvicorn
Documentação API: Swagger em /docs
Estrutura modular: app/api, app/services, app/integrations, app/core
```

Objetivo do projeto:

Criar uma automação de análise/mineração de anúncios, funis e campanhas, com módulos como:

```txt
AdProcessor
MinerEngine
FacebookAdMiner
MetaCampaignOperator
MetaMarketingClient
VideoPipeline
PremiumRender
WarKitGenerator
OrchestrationPipeline
```

A auditoria feita até aqui mostrou que a API sobe, o Swagger funciona e a rota `/miner/test` responde, mas o motor real de mineração ainda precisa ser reconstruído ou religado.

---

## 2. Estado final validado até agora

### Fase 1 — Estrutura do projeto

Status: CONCLUÍDA.

Foi confirmado que existe estrutura funcional dentro de:

```txt
src/app/
src/app/api/
src/app/api/routes/
src/app/services/
src/app/core/
src/app/integrations/
```

Arquivos importantes encontrados:

```txt
app/main.py
app/api/router.py
app/api/routes/ads.py
app/api/routes/miner.py
app/services/ad_processor.py
app/services/miner_engine.py
app/services/meta_campaign_operator.py
app/services/video_pipeline.py
app/services/premium_render.py
app/core/compat/legacy.py
```

---

### Fase 2 — Correção do import principal

Problema original:

```txt
ModuleNotFoundError: No module named 'api'
```

Causa:

No arquivo:

```txt
src/app/main.py
```

existia import errado:

```python
from api.router import router
```

Correção aplicada:

```python
from app.api.router import router
```

Comando usado para corrigir via terminal:

```bat
powershell -Command "(Get-Content 'C:\Users\USUÁRIO\Desktop\projeto_automacao\src\app\main.py') -replace 'from api.router import router','from app.api.router import router' | Set-Content 'C:\Users\USUÁRIO\Desktop\projeto_automacao\src\app\main.py'"
```

Validação feita:

```bat
type C:\Users\USUÁRIO\Desktop\projeto_automacao\src\app\main.py
```

Resultado esperado visto:

```python
from app.api.router import router
```

---

### Fase 3 — Inicialização FastAPI / Uvicorn

Comando correto para subir o servidor:

```bat
cd C:\Users\USUÁRIO\Desktop\projeto_automacao\src
python -m uvicorn app.main:app --reload
```

Resultado validado no terminal:

```txt
INFO: Uvicorn running on http://127.0.0.1:8000
INFO: Started server process
INFO: Waiting for application startup.
INFO: Application startup complete.
```

Swagger validado em:

```txt
http://127.0.0.1:8000/docs
```

Resultado: Swagger abriu corretamente.

---

### Fase 4 — Teste da rota /miner/test

Endpoint validado:

```txt
GET /miner/test
```

No Swagger, a rota respondeu com:

```txt
200 OK
```

Isso confirmou:

```txt
FastAPI funcionando
Uvicorn funcionando
Swagger funcionando
Router registrado
Endpoint publicado
API local operacional
```

Conclusão da Fase 4:

```txt
Fase 1: concluída
Fase 2: concluída
Fase 3: concluída
Fase 4: concluída operacionalmente
```

Observação importante:

A rota `/miner/test` validou a ponte do endpoint e depois foi direcionada para teste com `AdProcessor`. Ela NÃO provou ainda que existe mineração real via Facebook Ad Library ou Meta Ads API.

---

## 3. Problema de ambiente já diagnosticado

Durante o processo, houve travamento da porta 8000.

Sintomas observados:

```txt
Navegador girando
Swagger não carregando
Uvicorn aparentemente travado
Porta 8000 ocupada
Conexões CLOSE_WAIT e FIN_WAIT_2 no netstat
```

Comando de diagnóstico:

```bat
netstat -ano | findstr :8000
```

Solução que funcionou:

```bat
taskkill /f /im python.exe /t
```

Motivo técnico:

O Windows manteve processos Python/Uvicorn filhos segurando a porta 8000. A flag `/t` foi necessária para matar toda a árvore de processos.

Protocolo futuro se a porta travar novamente:

```bat
netstat -ano | findstr :8000
taskkill /f /im python.exe /t
cd C:\Users\USUÁRIO\Desktop\projeto_automacao\src
python -m uvicorn app.main:app --reload
```

---

## 4. Descoberta crítica: MinerEngine e FacebookAdMiner são placeholders

Arquivo auditado:

```txt
src/app/services/miner_engine.py
```

Conteúdo encontrado:

```python
class MinerEngine:
    pass

from app.core.compat.legacy import MinerEngine
```

Isso significa que o `MinerEngine` ativo não possui implementação real.

Arquivo auditado:

```txt
src/app/core/compat/legacy.py
```

Conteúdo relevante encontrado:

```python
class NoOp:
    ...
    def mine(self, *args, **kwargs): return {}

MinerEngine = NoOp
FacebookAdMiner = NoOp
CampaignOperator = NoOp
MetaCampaignOperator = NoOp
VideoPipeline = NoOp
```

Diagnóstico:

```txt
MinerEngine real: NÃO encontrado ativo
FacebookAdMiner real: NÃO encontrado ativo
Legacy: usando NoOp
NoOp: classe que não faz nada
mine(): retorna {}
```

Conclusão:

O motor de mineração real ainda precisa ser reconstruído ou religado. A API está funcionando, mas a mineração real não está implementada nesse ponto.

---

## 5. Módulos reais encontrados

Apesar de MinerEngine e FacebookAdMiner estarem em NoOp, vários módulos reais existem.

Foram localizados arquivos como:

```txt
app/services/ad_processor.py
app/services/automation_processor.py
app/services/campaign_intelligence.py
app/services/meta_campaign_operator.py
app/services/facebook_automation.py
app/services/video_pipeline.py
app/services/premium_render.py
app/services/serverless_render.py
app/services/render_tasks.py
app/services/war_kit_generator.py
app/services/orchestration_pipeline.py
```

Diagnóstico arquitetural:

```txt
API: real
Swagger: real
AdProcessor: real
MetaCampaignOperator: real
VideoPipeline: real
PremiumRender: real
Render/Workers/Celery: aparentemente reais
MinerEngine: placeholder
FacebookAdMiner: placeholder
```

---

## 6. AdProcessor — estado identificado

Arquivo:

```txt
src/app/services/ad_processor.py
```

Foi identificado que ele tem lógica real de negócio:

```txt
connect_rate
checkout_rate
purchase_rate
checkout_to_purchase_rate
score
status
insight
slug
preview_url
repository.save(...)
```

Trecho relevante visto:

```python
if connect_rate < 75:
    alerts.append("Connect Rate abaixo de 75%; revise carregamento, domínio, velocidade e rastreamento da página.")
else:
    alerts.append("Connect Rate saudável; a maioria dos cliques está chegando na página.")

if checkout_rate < 20:
    alerts.append("Poucas pessoas avançam para checkout; revise promessa, preço, prova e CTA da página.")

if purchase_rate >= 2:
    alerts.append("Taxa de compra com bom sinal inicial; vale testar novos criativos e remodelar a oferta.")
elif checkout_to_purchase_rate < 20:
    alerts.append("Muitos chegam ao checkout, mas poucos compram; revise preço, confiança e meios de pagamento.")

return " ".join(alerts)
```

Slugify visto:

```python
@staticmethod
def _slugify(value: str) -> str:
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "produto"
```

Parecer:

O `AdProcessor` é o cérebro de análise de métricas. Ele não deve ser confundido com coletor externo da API da Meta.

Arquitetura recomendada:

```txt
MetaMarketingClient / FacebookAdMiner
        ↓
coleta dados externos
        ↓
MinerEngine
        ↓
AdProcessor
        ↓
gera score, insight e diagnóstico
```

---

## 7. Teste temporário criado em /miner/test

Foi criado ou solicitado um teste temporário parecido com este:

```python
from fastapi import APIRouter
from app.schemas.ads import AdAnalysisRequest
from app.services.ad_processor import AdProcessor

router = APIRouter()


class MemoryRepository:
    def save(self, data: dict):
        return data


@router.get("/miner/test")
async def minerar_nicho():
    payload = AdAnalysisRequest(
        user_id=1,
        product_name="Ebook de Receitas Fitness",
        active_ads=22,
        cpc=1.35,
        link_clicks=1000,
        landing_page_views=820,
        checkout_starts=210,
        purchases=28,
    )

    processor = AdProcessor(repository=MemoryRepository())
    result = processor.process(payload)

    return {
        "status": "ok",
        "fase": "fase_4",
        "modo": "ad_processor_conectado",
        "resultado": result,
    }
```

Objetivo desse teste:

Validar a ponte:

```txt
FastAPI route → AdAnalysisRequest → AdProcessor → response JSON
```

Atenção para o Codex:

Verificar exatamente em qual arquivo esse código foi colado. Pode ter sido em:

```txt
app/api/router.py
```

ou em algum arquivo de rota específica. O Codex deve conferir se alguma rota importante foi sobrescrita.

Tarefa para o Codex:

1. Verificar `app/api/router.py`.
2. Verificar `app/api/routes/miner.py`.
3. Verificar `app/api/routes/ads.py`.
4. Confirmar se endpoints importantes não foram apagados.
5. Consolidar `/miner/test` em local correto.

---

## 8. Comandos úteis já usados na auditoria

Listar todos os arquivos Python:

```bat
cd C:\Users\USUÁRIO\Desktop\projeto_automacao\src
dir *.py /s
```

Buscar MinerEngine:

```bat
findstr /s /i "class MinerEngine" *.py
```

Buscar FacebookAdMiner:

```bat
findstr /s /i "FacebookAdMiner" *.py
```

Buscar AdProcessor:

```bat
findstr /s /i "AdProcessor" *.py
```

Buscar MetaCampaignOperator:

```bat
findstr /s /i "MetaCampaignOperator" *.py
```

Abrir arquivo no terminal:

```bat
type app\services\ad_processor.py
```

Mostrar arquivo página por página:

```bat
more app\services\meta_campaign_operator.py
```

Sair do `more`:

```txt
Q
```

Cancelar comando travado:

```txt
Ctrl + C
```

Compilar arquivo Python isolado:

```bat
python -m py_compile app\services\ad_processor.py
```

Subir servidor:

```bat
python -m uvicorn app.main:app --reload
```

---

## 9. Ponto exato onde paramos

Paramos na transição entre:

```txt
Fase 4 concluída operacionalmente
```

e

```txt
Fase 5 — reconstrução/conexão do MinerEngine real
```

Estado atual:

```txt
Servidor FastAPI: OK
Swagger: OK
Endpoint /miner/test: OK
AdProcessor: existe e tem lógica real
MetaCampaignOperator: existe e tem classe real
MinerEngine: placeholder
FacebookAdMiner: placeholder
Legacy: usando NoOp
```

Próximo teste recomendado antes de alterar código:

```bat
cd C:\Users\USUÁRIO\Desktop\projeto_automacao\src
python -m py_compile app\services\ad_processor.py
```

Depois:

```bat
python -m uvicorn app.main:app --reload
```

Depois no navegador:

```txt
http://127.0.0.1:8000/docs
```

Testar:

```txt
GET /miner/test
```

Resultado esperado:

```json
{
  "status": "ok",
  "fase": "fase_4",
  "modo": "ad_processor_conectado",
  "resultado": {
    "...": "..."
  }
}
```

---

## 10. Missão do Codex a partir daqui

O Codex deve executar uma auditoria ponta a ponta do projeto com foco nestas tarefas:

### Tarefa 1 — Inventário real

Gerar lista completa de:

```txt
rotas
services
schemas
integrations
models
repositories
tests
workers
```

### Tarefa 2 — Mapear imports quebrados

Verificar imports que apontam para:

```python
from app.core.compat.legacy import ...
```

e distinguir:

```txt
módulo real
módulo NoOp
módulo ausente
módulo duplicado
```

### Tarefa 3 — Validar AdProcessor

Confirmar que `AdProcessor` possui:

```txt
process()
_percent()
_classify()
_score()
_insight()
_slugify()
```

e que compila sem erro.

### Tarefa 4 — Consolidar rota /miner/test

Verificar se o endpoint `/miner/test` está no arquivo correto.

Ideal:

```txt
app/api/routes/miner.py
```

ou então centralizado em:

```txt
app/api/router.py
```

dependendo da arquitetura atual.

Evitar duplicidade de rotas.

### Tarefa 5 — Criar MinerEngine real mínimo

Criar implementação real mínima para substituir o placeholder.

Objetivo inicial:

```txt
MinerEngine.run_test()
MinerEngine.analyze_payload()
MinerEngine.process_ad_metrics()
```

Fluxo mínimo:

```txt
MinerEngine
    ↓
AdProcessor
    ↓
MemoryRepository ou repository real
    ↓
resultado JSON
```

Exemplo de comportamento esperado:

```python
engine = MinerEngine(repository=MemoryRepository())
result = engine.process(payload)
```

### Tarefa 6 — Não conectar Meta API ainda

Não integrar API real da Meta antes de estabilizar:

```txt
schemas
AdProcessor
MinerEngine
router
tests
```

A conexão externa deve vir depois, por meio de:

```txt
MetaMarketingClient
FacebookAdMiner
timeouts explícitos
httpx/aiohttp
tratamento de exceções
```

### Tarefa 7 — Criar testes

Criar ou validar testes para:

```txt
AdProcessor
MinerEngine
/miner/test
/imports principais
```

Comandos esperados:

```bat
python -m py_compile app\services\ad_processor.py
python -m py_compile app\services\miner_engine.py
python -m pytest
```

Se o projeto não estiver pronto para `pytest`, ao menos usar `py_compile` por arquivo.

---

## 11. Diretrizes importantes para o Codex

1. Não apagar arquivos sem backup.
2. Não substituir módulos reais por NoOp.
3. Não mexer na API Meta ainda.
4. Não criar solução genérica sem mapear imports reais.
5. Antes de alterar `miner_engine.py`, verificar quem importa ele.
6. Antes de alterar `router.py`, verificar quais rotas já estão registradas.
7. Se houver duplicidade entre `app/api/router.py` e `app/api/routes/*.py`, consolidar com cuidado.
8. Manter compatibilidade com o comando:

```bat
python -m uvicorn app.main:app --reload
```

9. Manter Swagger funcionando em:

```txt
http://127.0.0.1:8000/docs
```

10. Garantir que `/miner/test` responda `200 OK`.

---

## 12. Plano sugerido de execução para o Codex

### Etapa A — Auditoria sem alteração

Rodar:

```bat
cd C:\Users\USUÁRIO\Desktop\projeto_automacao\src
python -m py_compile app\main.py
python -m py_compile app\services\ad_processor.py
python -m py_compile app\services\miner_engine.py
findstr /s /i "NoOp" *.py
findstr /s /i "legacy" *.py
findstr /s /i "MinerEngine" *.py
findstr /s /i "AdProcessor" *.py
```

Gerar relatório.

### Etapa B — Corrigir ponte interna

Reescrever `app/services/miner_engine.py` para não importar `MinerEngine` de `legacy.py`.

Implementar um `MinerEngine` real mínimo que usa `AdProcessor`.

### Etapa C — Ajustar rota de teste

Garantir que `/miner/test` chame o `MinerEngine` real mínimo.

### Etapa D — Validar

Rodar:

```bat
python -m py_compile app\services\miner_engine.py
python -m py_compile app\services\ad_processor.py
python -m uvicorn app.main:app --reload
```

Abrir:

```txt
http://127.0.0.1:8000/docs
```

Testar:

```txt
GET /miner/test
```

### Etapa E — Só depois planejar Meta API real

Após estabilizar o motor interno:

```txt
MetaMarketingClient
FacebookAdMiner
timeouts
retry
tratamento de erro
logs
repository persistente
```

---

## 13. Resumo executivo para o Codex

O projeto não está morto. A infraestrutura funciona.

Já foi validado:

```txt
FastAPI sobe
Swagger abre
/miner/test responde
AdProcessor existe
MetaCampaignOperator existe
VideoPipeline existe
PremiumRender existe
```

Problema central:

```txt
MinerEngine e FacebookAdMiner ainda estão como NoOp/placeholder.
```

Missão imediata:

```txt
Criar ou religar MinerEngine real mínimo usando AdProcessor,
sem conectar ainda API externa da Meta.
```

Objetivo da próxima entrega:

```txt
/miner/test deve responder 200 OK usando:
Router → MinerEngine real → AdProcessor → resultado JSON
```

Somente depois disso avançar para coleta real externa.

---

## 14. Prompt pronto para enviar ao Codex

Use este prompt no Codex:

```txt
Você é um engenheiro sênior/Staff Python FastAPI. Faça auditoria ponta a ponta deste projeto local.

Contexto:
O projeto fica em C:\Users\USUÁRIO\Desktop\projeto_automacao.
A raiz de execução é C:\Users\USUÁRIO\Desktop\projeto_automacao\src.
O comando validado para subir é:
python -m uvicorn app.main:app --reload

Já foi validado:
- FastAPI sobe.
- Swagger abre em http://127.0.0.1:8000/docs.
- /miner/test responde 200 OK.
- app/main.py foi corrigido de from api.router import router para from app.api.router import router.
- AdProcessor existe e tem lógica real de análise.
- MetaCampaignOperator existe como classe real.
- VideoPipeline e PremiumRender parecem ter código real.
- MinerEngine está placeholder.
- FacebookAdMiner está placeholder.
- app/core/compat/legacy.py define NoOp e atribui MinerEngine = NoOp, FacebookAdMiner = NoOp.

Objetivo:
Não conectar API externa da Meta ainda.
Primeiro estabilizar o motor interno.

Tarefas:
1. Auditar rotas, services, schemas, integrations e imports.
2. Localizar todos os usos de legacy.py e NoOp.
3. Verificar se /miner/test foi colocado no arquivo correto e se não apagou rotas importantes.
4. Validar app/services/ad_processor.py.
5. Reescrever app/services/miner_engine.py para ter um MinerEngine real mínimo, sem importar de legacy.py.
6. Fazer MinerEngine usar AdProcessor.
7. Ajustar /miner/test para chamar MinerEngine real.
8. Rodar py_compile nos arquivos alterados.
9. Subir com python -m uvicorn app.main:app --reload.
10. Confirmar Swagger e /miner/test 200 OK.

Regras:
- Não apagar arquivos sem backup.
- Não substituir módulo real por NoOp.
- Não criar integração Meta API ainda.
- Não mexer em produção.
- Manter compatibilidade com Windows CMD.
- Explicar cada alteração feita e por quê.

Entrega esperada:
- Relatório do que foi encontrado.
- Lista de arquivos alterados.
- Código final do MinerEngine mínimo.
- Endpoint /miner/test funcionando com fluxo Router → MinerEngine → AdProcessor.
```

---

## 15. Conclusão

O trabalho realizado até aqui concluiu as fases de infraestrutura e roteamento.

Agora o Codex deve continuar a partir da reconstrução do `MinerEngine` real mínimo, usando o `AdProcessor` como cérebro de análise.

Não avançar para API real da Meta antes de fechar e testar essa ponte interna.
