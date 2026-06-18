# BÚSSOLA COMPLETA PARA O CODEX — Projeto Automação / Radar PDF IA

**Objetivo deste documento:** entregar ao Codex um mapa operacional completo do que já foi feito, onde o projeto parou, quais módulos estão funcionando, quais estão em placeholder, quais agentes devem ser ativados e em que ordem, sem derrubar o sistema.

---

## 0. Regra máxima para o Codex

**Não fazer alterações em massa sem antes mapear, compilar e testar.**

O projeto já passou por correções delicadas de importação, rota, porta local e integração inicial. A prioridade agora é evoluir por fases pequenas, com rollback fácil.

Ordem obrigatória para qualquer mudança:

```txt
1. Ler estrutura real do projeto
2. Criar inventário dos arquivos críticos
3. Confirmar imports ativos
4. Fazer alteração pequena
5. Rodar py_compile
6. Subir Uvicorn
7. Testar /docs
8. Testar endpoint alterado
9. Só então avançar para próxima peça
```

---

## 1. Localização e ambiente

Projeto local do usuário:

```txt
C:\Users\USUÁRIO\Desktop\projeto_automacao
```

Raiz correta para rodar o backend:

```txt
C:\Users\USUÁRIO\Desktop\projeto_automacao\src
```

Comando correto para subir FastAPI:

```bat
cd C:\Users\USUÁRIO\Desktop\projeto_automacao\src
python -m uvicorn app.main:app --reload
```

Swagger:

```txt
http://127.0.0.1:8000/docs
```

Endpoint validado:

```txt
GET /miner/test
```

---

## 2. Problemas já resolvidos

### 2.1 Import errado em `main.py`

Erro original:

```txt
ModuleNotFoundError: No module named 'api'
```

Causa encontrada em:

```txt
src/app/main.py
```

Linha antiga incorreta:

```python
from api.router import router
```

Correção aplicada:

```python
from app.api.router import router
```

Resultado: FastAPI passou a carregar corretamente.

---

### 2.2 Execução na pasta errada

O servidor estava sendo executado na raiz errada:

```txt
C:\Users\USUÁRIO\Desktop\projeto_automacao
```

A pasta correta é:

```txt
C:\Users\USUÁRIO\Desktop\projeto_automacao\src
```

---

### 2.3 Confusão entre código Python e comando de terminal

O usuário digitou algumas linhas Python no CMD, por exemplo:

```python
from fastapi import FastAPI
from app.api.router import router
app = FastAPI()
```

Essas linhas **não são comandos de terminal**. Elas devem existir dentro de arquivos `.py`.

O Codex deve evitar instruções ambíguas. Sempre especificar:

```txt
Isto é para colar no arquivo.
```

ou

```txt
Isto é para colar no CMD.
```

---

### 2.4 Porta 8000 saturada / sockets presos

Foi identificado acúmulo de conexões em estados como:

```txt
CLOSE_WAIT
FIN_WAIT_2
```

na porta:

```txt
8000
```

Comando de diagnóstico:

```bat
netstat -ano | findstr :8000
```

Comando de limpeza que funcionou:

```bat
taskkill /f /im python.exe /t
```

Observação: usar esse comando apenas quando houver processo Python travado ou Uvicorn preso. Ele mata todos os processos Python em execução.

---

## 3. Estado das fases já trabalhadas

### Fase 1 — Estrutura do projeto

**Status: concluída.**

Estrutura confirmada:

```txt
src/
└── app/
    ├── main.py
    ├── api/
    │   ├── router.py
    │   └── routes/
    ├── services/
    ├── integrations/
    └── core/
```

Arquivos encontrados durante auditoria:

```txt
app/main.py
app/api/router.py
app/api/routes/ads.py
app/api/routes/miner.py
app/services/ad_processor.py
app/services/automation_processor.py
app/services/miner_engine.py
app/services/meta_campaign_operator.py
app/services/video_pipeline.py
app/services/premium_render.py
app/services/serverless_render.py
app/services/render_tasks.py
app/core/compat/legacy.py
app/integrations/meta_marketing.py
```

Critério de aprovação da fase:

```txt
Arquivos principais existem e imports básicos são localizáveis.
```

Resultado:

```txt
APROVADA
```

---

### Fase 2 — Router e import principal

**Status: concluída.**

Correção crítica aplicada:

```python
from app.api.router import router
```

Critério de aprovação:

```txt
python -m uvicorn app.main:app --reload não pode quebrar com ModuleNotFoundError: api
```

Resultado:

```txt
APROVADA
```

---

### Fase 3 — FastAPI / Uvicorn / Swagger

**Status: concluída.**

Evidências:

```txt
INFO: Uvicorn running on http://127.0.0.1:8000
INFO: Application startup complete.
```

Swagger abriu em:

```txt
http://127.0.0.1:8000/docs
```

Critério de aprovação:

```txt
/docs precisa abrir e listar endpoints.
```

Resultado:

```txt
APROVADA
```

---

### Fase 4 — Ponte inicial `/miner/test`

**Status: concluída operacionalmente.**

Endpoint validado:

```txt
GET /miner/test
```

Retorno anterior validado com status HTTP:

```txt
200 OK
```

Depois foi orientado criar uma ponte temporária usando:

```txt
AdProcessor
MemoryRepository
AdAnalysisRequest
```

Código usado/esperado para rota de teste:

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

Atenção: este código deve estar no arquivo de rota correto conforme o roteamento atual. Codex deve confirmar onde `app.main` inclui `router` antes de mexer.

Critério de aprovação:

```txt
GET /miner/test precisa retornar status ok e modo ad_processor_conectado.
```

Resultado:

```txt
APROVADA COMO PONTE TEMPORÁRIA
```

---

## 4. Diagnóstico dos módulos reais e placeholders

### 4.1 `AdProcessor`

Arquivo:

```txt
app/services/ad_processor.py
```

Status:

```txt
REAL / possui lógica de negócio
```

Funções/métodos identificados ou esperados:

```txt
process()
_percent()
_classify()
_score()
_insight()
_slugify()
```

Lógica identificada:

```txt
connect_rate
checkout_rate
purchase_rate
checkout_to_purchase_rate
score
insight
slug
preview_url
```

Trecho importante identificado:

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
```

`_slugify()` usa:

```python
unicodedata.normalize("NFKD", value)
```

Parecer:

```txt
AdProcessor é o cérebro de análise. Não deve ser transformado em cliente direto da API Meta neste momento.
```

Arquitetura correta:

```txt
MetaMarketingClient / FacebookAdMiner
        ↓
coleta dados externos
        ↓
MinerEngine
        ↓
AdProcessor
        ↓
score, insight, diagnóstico, preview_url
```

---

### 4.2 `MinerEngine`

Arquivo:

```txt
app/services/miner_engine.py
```

Conteúdo encontrado:

```python
class MinerEngine:
    pass

from app.core.compat.legacy import MinerEngine
```

Status:

```txt
PLACEHOLDER / NÃO REAL
```

Parecer:

```txt
MinerEngine precisa ser reconstruído como orquestrador real.
```

Não assumir que ele minera algo hoje.

---

### 4.3 `legacy.py`

Arquivo:

```txt
app/core/compat/legacy.py
```

Conteúdo relevante encontrado:

```python
class NoOp:
    def mine(self, *args, **kwargs): return {}

MinerEngine = NoOp
FacebookAdMiner = NoOp
CampaignOperator = NoOp
MetaCampaignOperator = NoOp
VideoPipeline = NoOp
```

Status:

```txt
PLACEHOLDER / CAMADA DE COMPATIBILIDADE
```

Parecer:

```txt
legacy.py foi criado para impedir que imports antigos quebrem a aplicação.
Não é o motor real do sistema.
```

Regra:

```txt
Não conectar novas funcionalidades ao legacy.py.
Usar serviços reais em app/services e app/integrations.
```

---

### 4.4 `FacebookAdMiner`

Resultado da busca:

```txt
app/core/compat/legacy.py: FacebookAdMiner = NoOp
```

Status:

```txt
NÃO LOCALIZADO COMO IMPLEMENTAÇÃO REAL
```

Parecer:

```txt
FacebookAdMiner real precisa ser criado ou recuperado.
```

---

### 4.5 `MetaCampaignOperator`

Arquivo real encontrado:

```txt
app/services/meta_campaign_operator.py
```

Busca mostrou:

```txt
app/core/compat/legacy.py: MetaCampaignOperator = NoOp
app/services/meta_campaign_operator.py: class MetaCampaignOperator:
```

Status:

```txt
REAL EXISTE
```

Import importante identificado:

```python
from app.integrations.meta_marketing import MetaMarketingClient
```

Parecer:

```txt
MetaCampaignOperator real não depende do MinerEngine.
Ele parece operar via MetaMarketingClient.
```

Fluxo provável:

```txt
MetaCampaignOperator
        ↓
MetaMarketingClient
        ↓
Meta Ads API
```

Próximo passo para Codex:

```bat
findstr /s /i "MetaMarketingClient" *.py
findstr /s /i "class MetaMarketingClient" *.py
```

---

### 4.6 `VideoPipeline`, `PremiumRender`, renderização e workers

Arquivos encontrados:

```txt
app/services/video_pipeline.py
app/services/premium_render.py
app/services/serverless_render.py
app/services/render_tasks.py
celery_app.py
```

Status:

```txt
CÓDIGO REAL ENCONTRADO, NÃO APENAS PLACEHOLDER
```

Evidências vistas:

```txt
subprocess.run(...)
ffmpeg
celery_app
render_worker_queue
json.dumps(record, ensure_ascii=False)
```

Parecer:

```txt
Pipeline de renderização parece existir e deve ser ativado depois da mineração e análise estarem estáveis.
```

---

## 5. Mapa de agentes do projeto

Os agentes abaixo devem ser ativados progressivamente, um por vez, sempre com teste entre eles. O objetivo é evitar que uma ativação simultânea derrube o sistema.

### Agente 1 — Arquiteto de Estrutura

Função:

```txt
Mapear estrutura, imports, rotas e dependências.
```

Pode fazer:

```txt
- Inventário de arquivos
- Mapa de dependências
- Localizar NoOp
- Localizar imports quebrados
```

Não pode fazer sem aprovação:

```txt
- Reescrever arquivos grandes
- Alterar main.py depois de validado
- Alterar roteamento global sem teste
```

Critério de aprovação:

```txt
py_compile nos arquivos alterados + /docs abrindo.
```

Status atual:

```txt
ATIVO / FASE 1-4 CONCLUÍDAS
```

---

### Agente 2 — Testador de Integridade

Função:

```txt
Compilar, subir servidor, testar endpoints e validar retornos.
```

Comandos obrigatórios:

```bat
cd C:\Users\USUÁRIO\Desktop\projeto_automacao\src
python -m py_compile app\services\ad_processor.py
python -m py_compile app\services\miner_engine.py
python -m uvicorn app.main:app --reload
```

Testes no navegador:

```txt
http://127.0.0.1:8000/docs
GET /miner/test
```

Status atual:

```txt
ATIVAR AGORA / ANTES DA FASE 5
```

---

### Agente 3 — MinerEngine Orquestrador

Função:

```txt
Reconstruir o MinerEngine real sem depender do legacy.py.
```

Responsabilidade:

```txt
- Receber nicho/produto/métricas
- Chamar AdProcessor
- Salvar resultado em repository
- Retornar JSON padronizado
```

Primeira versão recomendada:

```txt
Sem API externa ainda.
Usar dados mockados controlados.
Objetivo: provar orquestração interna.
```

Critério de aprovação:

```txt
/miner/test retorna resultado vindo do MinerEngine real, não NoOp.
```

Status:

```txt
PRÓXIMA FASE / FASE 5
```

---

### Agente 4 — FacebookAdMiner / Coletor

Função:

```txt
Criar ou recuperar minerador real de anúncios.
```

Responsabilidade futura:

```txt
- Buscar anúncios ou receber dados de fonte externa
- Normalizar métricas
- Entregar payload compatível com AdAnalysisRequest
```

Regra:

```txt
Não conectar API externa antes do MinerEngine interno passar nos testes.
```

Status:

```txt
AGUARDAR FASE 5.2
```

---

### Agente 5 — MetaMarketingClient

Função:

```txt
Validar ou estruturar integração com Meta Ads API.
```

Responsabilidade:

```txt
- Timeouts explícitos
- Tratamento de exceção
- Não travar servidor
- Não abrir conexões sem fechamento
```

Bibliotecas recomendadas:

```txt
httpx com timeout
requests com timeout obrigatório
```

Regra:

```txt
AdProcessor não deve virar cliente de API.
MetaMarketingClient deve ser a camada externa.
```

Status:

```txt
VALIDAR APÓS FASE 5 INTERNA
```

---

### Agente 6 — MetaCampaignOperator

Função:

```txt
Criar campanhas ou simular criação usando dados aprovados.
```

Status atual:

```txt
IMPLEMENTAÇÃO REAL ENCONTRADA
```

Regra:

```txt
Não acionar criação real de campanha sem modo dry_run primeiro.
```

Fase de ativação:

```txt
Depois que mineração/análise estiver estável.
```

---

### Agente 7 — VideoPipeline / PremiumRender

Função:

```txt
Renderizar criativos, vídeos, war kits e materiais.
```

Status atual:

```txt
CÓDIGO REAL ENCONTRADO
```

Regra:

```txt
Só ativar depois que dados de anúncio e campanha estiverem padronizados.
```

Motivo:

```txt
Renderização pode acionar ffmpeg, subprocessos e filas; ativar cedo pode aumentar instabilidade.
```

---

### Agente 8 — Segurança / Antiqueda

Função:

```txt
Garantir timeouts, limites e isolamento.
```

Checklist:

```txt
- timeout em chamadas externas
- try/except com erro claro
- não bloquear event loop
- não criar loops infinitos
- não iniciar workers automaticamente no import
- não fazer requests externos durante import de módulo
```

Status:

```txt
OBRIGATÓRIO EM TODAS AS FASES
```

---

## 6. Plano da Fase 5 — próximo trabalho real

### Fase 5.0 — Congelar base funcional

Objetivo:

```txt
Garantir que Fase 1-4 não quebrem.
```

Comandos:

```bat
cd C:\Users\USUÁRIO\Desktop\projeto_automacao\src
python -m py_compile app\main.py
python -m py_compile app\services\ad_processor.py
python -m uvicorn app.main:app --reload
```

Teste:

```txt
/docs abre
/miner/test retorna 200
```

---

### Fase 5.1 — Criar MinerEngine real mínimo

Objetivo:

```txt
Substituir placeholder por orquestrador real, sem API externa.
```

Regra:

```txt
Não usar legacy.py.
Não remover legacy.py ainda.
```

Estrutura recomendada:

```python
from app.schemas.ads import AdAnalysisRequest
from app.services.ad_processor import AdProcessor


class MinerEngine:
    def __init__(self, repository):
        self.repository = repository
        self.processor = AdProcessor(repository=repository)

    def analyze_mock(self):
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
        return self.processor.process(payload)
```

Critério de aprovação:

```txt
/miner/test usa MinerEngine real e retorna resultado do AdProcessor.
```

---

### Fase 5.2 — Criar repository mínimo

Objetivo:

```txt
Evitar MemoryRepository espalhado em rota.
```

Repository temporário aceitável:

```python
class MemoryRepository:
    def save(self, data: dict):
        return data
```

Futuro:

```txt
SQLite / banco real / histórico por usuário
```

---

### Fase 5.3 — Endpoint limpo

Objetivo:

```txt
Rota não deve conter lógica de negócio pesada.
```

Fluxo desejado:

```txt
GET /miner/test
    ↓
MinerEngine.analyze_mock()
    ↓
AdProcessor.process()
    ↓
resultado JSON
```

---

### Fase 5.4 — Teste de compilação e servidor

Após qualquer alteração:

```bat
python -m py_compile app\services\miner_engine.py
python -m py_compile app\api\router.py
python -m uvicorn app.main:app --reload
```

---

### Fase 5.5 — Só depois: API externa

Somente após o motor interno passar:

```txt
- localizar MetaMarketingClient real
- validar timeouts
- criar modo dry_run
- testar sem credenciais reais primeiro
```

---

## 7. Protocolo antiqueda

Sempre que o sistema travar:

### 7.1 Diagnóstico

```bat
netstat -ano | findstr :8000
```

### 7.2 Se houver muitos sockets presos ou Uvicorn travado

```bat
taskkill /f /im python.exe /t
```

### 7.3 Subir novamente

```bat
cd C:\Users\USUÁRIO\Desktop\projeto_automacao\src
python -m uvicorn app.main:app --reload
```

### 7.4 Testar

```txt
http://127.0.0.1:8000/docs
```

---

## 8. Comandos úteis para o Codex / terminal

Listar arquivos Python:

```bat
dir *.py /s
```

Procurar MinerEngine:

```bat
findstr /s /i "class MinerEngine" *.py
findstr /s /i "MinerEngine" *.py
```

Procurar FacebookAdMiner:

```bat
findstr /s /i "FacebookAdMiner" *.py
```

Procurar MetaMarketingClient:

```bat
findstr /s /i "MetaMarketingClient" *.py
findstr /s /i "class MetaMarketingClient" *.py
```

Procurar AdProcessor:

```bat
findstr /s /i "AdProcessor" *.py
```

Abrir arquivo no terminal:

```bat
type app\services\ad_processor.py
```

Paginar arquivo grande:

```bat
more app\services\meta_campaign_operator.py
```

Sair do `more`:

```txt
Q
```

---

## 9. O que o Codex NÃO deve fazer

Não fazer:

```txt
- Não reescrever o projeto inteiro.
- Não deletar legacy.py sem substituir imports antigos.
- Não ativar todos os agentes ao mesmo tempo.
- Não conectar API Meta antes do MinerEngine interno passar.
- Não colocar chamadas externas dentro do AdProcessor.
- Não iniciar ffmpeg, celery ou workers automaticamente no import.
- Não mexer em main.py se /docs estiver funcionando.
- Não trocar estrutura de pastas sem mapa de imports.
```

---

## 10. Critérios de aprovação por fase daqui até o final

### Fase 5 — MinerEngine real interno

Aprovada quando:

```txt
/miner/test retorna resultado vindo de MinerEngine real + AdProcessor.
```

### Fase 6 — Coletor / FacebookAdMiner

Aprovada quando:

```txt
Coletor entrega dados normalizados compatíveis com AdAnalysisRequest.
```

### Fase 7 — MetaMarketingClient

Aprovada quando:

```txt
Cliente externo tem timeout, tratamento de erro e modo dry_run.
```

### Fase 8 — MetaCampaignOperator

Aprovada quando:

```txt
Operador consegue simular campanha sem criação real.
```

### Fase 9 — Renderização / War Kit

Aprovada quando:

```txt
VideoPipeline/PremiumRender rodam somente quando chamados, sem travar import.
```

### Fase 10 — Orquestração completa

Aprovada quando:

```txt
Entrada de produto/nicho → mineração → análise → score → kit → campanha dry_run.
```

### Fase 11 — Produção controlada

Aprovada quando:

```txt
Logs, timeouts, histórico, erro amigável, rollback e configuração por .env funcionam.
```

---

## 11. Resumo executivo para o Codex

O projeto não está morto. A infraestrutura está de pé.

Já foi validado:

```txt
FastAPI ✅
Uvicorn ✅
Swagger ✅
Router ✅
/miner/test ✅
AdProcessor ✅ lógica real
MetaCampaignOperator ✅ classe real encontrada
VideoPipeline ✅ código real encontrado
PremiumRender ✅ código real encontrado
```

Problemas reais restantes:

```txt
MinerEngine ❌ placeholder
FacebookAdMiner ❌ NoOp
MetaMarketingClient 🔎 precisa confirmar implementação completa
Integração externa Meta ❌ ainda não validar
Orquestração final ❌ pendente
```

Próxima ação recomendada:

```txt
1. Rodar py_compile no AdProcessor.
2. Confirmar /miner/test atual.
3. Criar MinerEngine real mínimo usando AdProcessor.
4. Mover MemoryRepository para local próprio.
5. Testar /miner/test novamente.
6. Só depois investigar MetaMarketingClient e API externa.
```

---

## 12. Prompt pronto para colar no Codex

Use este prompt no Codex:

```txt
Você está assumindo o projeto C:\Users\USUÁRIO\Desktop\projeto_automacao.

Leia primeiro este documento inteiro. Não faça alteração em massa.

Missão atual: continuar a partir da Fase 5.

Estado validado:
- FastAPI sobe com python -m uvicorn app.main:app --reload dentro de src.
- Swagger abre em http://127.0.0.1:8000/docs.
- GET /miner/test já respondeu 200 OK.
- main.py foi corrigido para usar from app.api.router import router.
- AdProcessor existe e possui lógica real.
- MinerEngine atual é placeholder/pass e/ou aponta para legacy.py.
- legacy.py define NoOp para MinerEngine, FacebookAdMiner e outros.
- MetaCampaignOperator real existe em app/services/meta_campaign_operator.py.
- VideoPipeline e PremiumRender parecem ter código real.

Regras:
1. Não mexa em main.py se o Swagger estiver funcionando.
2. Não remova legacy.py ainda.
3. Não conecte API externa agora.
4. Não coloque chamada da Meta dentro do AdProcessor.
5. Criar primeiro MinerEngine real mínimo, usando AdProcessor e dados mockados.
6. Testar tudo com py_compile antes de subir Uvicorn.
7. Ativar agentes progressivamente: Arquiteto → Testador → MinerEngine → Coletor → MetaClient → MetaOperator → Render.
8. Após cada alteração, testar /docs e /miner/test.

Primeira tarefa:
- Auditar app/services/ad_processor.py.
- Rodar py_compile.
- Auditar app/services/miner_engine.py.
- Substituir o placeholder por um MinerEngine mínimo real que chame AdProcessor.
- Ajustar /miner/test para usar MinerEngine, não lógica pesada direta na rota.
- Retornar relatório do que foi alterado e comandos de teste.
```

---

## 13. Conclusão

Este documento é a bússola operacional. Ele deve guiar o Codex para continuar sem perder o histórico, sem repetir erros e sem derrubar a aplicação.

O princípio central é:

```txt
Ativar um agente por vez, testar, estabilizar e só então passar ao próximo.
```
