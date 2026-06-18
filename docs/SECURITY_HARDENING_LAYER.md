# Security Hardening Layer

Data: 2026-06-05

## Objetivo

Criar a camada oficial de seguranca do Projeto Automacao antes de qualquer uso real em escala com Meta, IA paga, publicacao de sites ou acoes que possam gastar dinheiro.

Esta camada protege APIs, agentes internos, memoria do sistema, tokens, integracoes, comandos sensiveis, decisoes automatizadas e acoes financeiras.

Base conceitual:

- Zero Trust.
- OWASP API Security.
- NIST CSF.
- Human-in-the-loop para acoes de risco.

## Diagnostico Das Reunioes

As duas reunioes fazem sentido e se complementam.

A primeira reuniao foca em seguranca:

- API Gateway.
- RBAC.
- Service Accounts.
- Zero Trust interno.
- Command Validator.
- Human Approval.
- Secrets Vault.
- Audit Log imutavel.
- Rate Limit.
- Incident Response.

A segunda reuniao foca em operacao profissional:

- structured logs.
- correlation ID.
- audit store.
- replay.
- event bus.
- metrics engine.
- dashboard.
- error recovery.
- full factory dry-run.
- production readiness.

Conclusao:

```txt
Nao sao planos concorrentes.
O plano operacional cria visibilidade.
O plano de seguranca cria controle.
Os dois devem virar uma unica camada: Security Hardening Layer.
```

## O Que Ja Existe

### Observabilidade

Status: parcialmente implementado.

Arquivos:

- `src/app/services/observability.py`
- `src/app/main.py`

Ja existe:

- log estruturado em JSONL.
- `correlation_id`.
- `execution_id`.
- `mission_id`.
- eventos de auditoria.
- health dashboard basico.

Melhoria necessaria:

- padronizar ator, role, permissao e escopo em eventos criticos.
- criar verificacao de integridade do audit log.
- conectar replay e metricas.

### Human Approval

Status: parcialmente implementado.

Arquivos:

- `src/app/domain/models.py`
- `src/app/services/campaign_intelligence.py`
- `src/app/services/meta_campaign_operator.py`

Ja existe:

- `MetaActionRequest`.
- status `pending_approval`.
- guardrails para Meta real.
- frase de aprovacao para execucao assistida.

Melhoria necessaria:

- centralizar aprovacao em uma camada unica.
- padronizar status: `pending`, `approved`, `rejected`, `executed`, `failed`, `audited`, `incident`.
- obrigar aprovacao para site, IA cara, Meta real e alteracao de link.

### Segredos

Status: parcialmente implementado.

Ja existe:

- `.env` fora do pacote.
- `.env.example` seguro.
- verificador de pacote final.

Melhoria necessaria:

- criar politica oficial de segredos.
- validar segredo fraco em producao.
- preparar adaptador para vault externo no futuro.

## Lacunas Criticas

### RBAC Profissional

Status: pendente.

Perfis oficiais:

- `OWNER`
- `ADMIN`
- `OPERATOR`
- `VIEWER`
- `AGENT`
- `SERVICE`

Regra:

```txt
Agente nao usa login humano.
Agente usa Service Account.
```

### Zero Trust Interno

Status: pendente.

Toda chamada sensivel deve carregar:

```json
{
  "actor": "CampaignBrain",
  "role": "AGENT",
  "permission": "decision.create",
  "correlation_id": "REQ-2026-0001",
  "origin": "internal",
  "scope": "campaign.safe"
}
```

### Command Validator

Status: pendente.

Antes de qualquer acao sensivel, validar ator, permissao, orcamento maximo, pais, plataforma, objetivo, ID do recurso, escopo, modo dry-run/real e necessidade de aprovacao humana.

Regra:

```txt
Nada de comando livre para Brain, Brian, Meta, IA paga ou execucao real.
```

### API Gateway

Status: especificacao pendente.

No ambiente local atual, a API principal funciona como entrada unica. Para producao, sera necessario expor somente gateway/reverse proxy, esconder portas internas, aplicar rate limit, validar autenticacao, bloquear rotas internas e registrar request logs.

Regra:

```txt
Nenhuma porta interna exposta diretamente na internet.
```

### Incident Response Mode

Status: pendente.

Quando houver incidente:

- forcar dry-run.
- bloquear escrita real.
- bloquear usuario/IP/ator.
- preservar logs.
- congelar tokens.
- gerar relatorio.
- notificar administrador.

## Missoes Oficiais

### Missao 35A - Security Spec Oficial

Status: concluida.

Entregas:

- consolidar reunioes.
- mapear o que ja existe.
- mapear lacunas.
- definir ordem segura de implementacao.

### Missao 35B - RBAC + Service Accounts

Status: concluida.

Entregas esperadas:

- enum de roles oficiais.
- matriz de permissoes.
- contexto de ator.
- service accounts para agentes.
- testes de permissao.

Arquivos:

- `src/app/core/security_hardening.py`
- `src/app/tests/test_security_hardening_rbac.py`

### Missao 35C - Command Validator

Status: concluida.

Arquivos:

- `src/app/core/command_validator.py`
- `src/app/tests/test_command_validator.py`

Entregas:

- validacao de ator e permissao.
- validacao de plataforma, pais e objetivo.
- limite de orcamento.
- validacao de ID de recurso.
- exigencia de aprovacao humana para acao real.

### Missao 35D - Zero Trust Internal Calls

Status: concluida.

Arquivos:

- `src/app/core/zero_trust.py`
- `src/app/tests/test_zero_trust_internal_calls.py`

Entregas:

- validacao de origem e destino registrados.
- validacao de permissao da origem.
- validacao de `correlation_id`, `execution_id` e `mission_id`.
- validacao de escopo por origem e destino.
- envelope auditavel para chamada interna.

### Missao 35E - Audit Log Imutavel

Status: concluida.

Arquivos:

- `src/app/core/immutable_audit.py`
- `src/app/tests/test_immutable_audit_log.py`

Entregas:

- audit log append-only.
- cadeia `previous_hash` e `event_hash`.
- verificador de integridade.
- deteccao de adulteracao.

### Missao 35F - Human Approval Layer

Status: concluida.

Arquivos:

- `src/app/core/human_approval.py`
- `src/app/tests/test_human_approval_layer.py`

Entregas:

- camada central de aprovacao.
- status padronizados.
- hash de payload.
- permissao separada para solicitar e decidir.
- integracao opcional com audit log imutavel.

### Missao 35G - Secrets Vault Policy

Status: concluida.

Arquivos:

- `src/app/core/secrets_policy.py`
- `src/app/tests/test_secrets_policy.py`

Entregas:

- politica local de segredos.
- mascaramento seguro.
- detector de segredo ausente/fraco/default.
- readiness para modo real.

### Missao 35H - Incident Response Mode

Status: concluida.

Arquivos:

- `src/app/core/incident_response.py`
- `src/app/tests/test_incident_response_mode.py`

Entregas:

- modo emergencia.
- dry-run forcado.
- bloqueio de execucao real.
- indicacao de rotacao de tokens.
- relatorio de incidente.

### Missao 35I - Rate Limit Inteligente

Status: concluida.

Arquivos:

- `src/app/core/rate_limit.py`
- `src/app/tests/test_rate_limit.py`

Entregas:

- limites por IP, usuario, agente, rota e tipo de acao.
- regras para login, comandos sensiveis, IA pesada, Meta API e chamadas internas.
- resultado auditavel com limite, restante, reset e decisao.
- testes dedicados.

## Ordem Recomendada

```txt
35A Security Spec Oficial
35B RBAC + Service Accounts
35C Command Validator
35D Zero Trust Internal Calls
35E Audit Log Imutavel
35F Human Approval Layer
35G Secrets Vault Policy
35H Incident Response Mode
35I Rate Limit Inteligente
```

## Regra De Producao

Antes de qualquer Meta real em escala:

```txt
RBAC ativo
Command Validator ativo
Human Approval ativo
Audit Log imutavel ativo
Incident Response ativo
Secrets Policy validada
Rate Limit ativo
```

## Status Final

```txt
SECURITY HARDENING LAYER CONCLUIDA EM MODO SEGURO
```

## Veredito Tecnico

O plano foi aplicado em modo seguro.

O projeto agora possui base local para identidade, permissao, validacao de comandos, Zero Trust, aprovacao humana, auditoria imutavel, politica de segredos, resposta a incidente e rate limit antes de qualquer operacao real profissional em escala.
