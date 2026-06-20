# RELEASE NOTES v1.0

Versão: 1.0.0
Data: 2026-06-20
Projeto: AdIntelligence Pro / Projeto Automação

## Resumo executivo

A versão **1.0.0** formaliza o primeiro empacotamento estável do Projeto Automação como uma plataforma local de automação e inteligência para campanhas de anúncios, com operação segura por padrão e documentação explícita das funcionalidades reais, limitações e cuidados necessários.

Este release é indicado para continuidade de desenvolvimento, validação local controlada e preparação de próximos ciclos de entrega. Ele não representa um SaaS em produção nem um ambiente com deploy público.

## Principais capacidades entregues

- Backend FastAPI local para automação e inteligência de campanhas.
- Banco SQLite local com migração leve própria.
- Autenticação local com JWT e senha armazenada com hash seguro.
- Motor de mineração/análise de anúncios em modo controlado/local.
- Geração e organização de conteúdo/criativos para campanhas.
- Camada de decisão/aprendizado com eventos auditáveis.
- Operador de campanhas Meta com guardrails rígidos antes de qualquer escrita real.
- Auditoria e observabilidade com logs locais e identificadores de execução.
- Documentação operacional, arquitetura, comandos, segurança, testes e continuidade.

## Postura de segurança do release

A versão 1.0.0 mantém a filosofia de segurança do projeto:

- dry-run por padrão;
- nenhuma credencial real versionada;
- `.env` local obrigatório para segredos;
- senha administrativa padrão removida do código-fonte;
- confirmações humanas explícitas para qualquer ação real de risco;
- arquivos locais sensíveis fora do Git.

## Itens que não fazem parte da entrega produtiva v1.0

Os seguintes tópicos existem como documentação, planejamento ou readiness local, mas não devem ser tratados como funcionalidades produtivas reais nesta versão:

- frontend enterprise;
- billing real;
- multi-tenant real;
- API pública comercial em produção;
- conectores externos reais;
- Vector DB produtivo;
- compliance SaaS completo;
- deploy em nuvem ou pipeline CI/CD.

## Requisitos recomendados

- Python 3.11+.
- Ambiente virtual dedicado.
- Variáveis de ambiente configuradas a partir de `.env.example`.
- Execução dos testes antes de uso operacional relevante.

## Como validar localmente

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows/Git Bash
python -m pip install -r requirements.txt
cp .env.example .env
# editar .env e definir DEFAULT_ADMIN_PASSWORD
python -m pytest -p no:cacheprovider --basetemp .pytest_tmp
```

## Observações para operadores

- Antes de qualquer uso com contas reais Meta Ads, revise `PROJECT_STATUS.md`, `README.md`, a documentação de segurança e as configurações de dry-run.
- Não ative produção real sem autorização humana explícita por escrito, orçamento definido, objetivo claro e validação prévia dos payloads.
- Reexecute a suíte de testes em Python 3.11+ para confirmar o estado local do ambiente antes da operação.

## Arquivos de release

- `VERSION`
- `CHANGELOG_v1.0.md`
- `RELEASE_NOTES_v1.0.md`
- `README.md`
- `PROJECT_STATUS.md`
- `PACKAGE_MANIFEST.json`
