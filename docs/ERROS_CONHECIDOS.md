# Erros Conhecidos e Riscos

## Riscos tecnicos

- MinerEngine ainda precisa evoluir para real controlado.
- FacebookAdMiner real ainda deve respeitar rate limits, cache e persistencia.
- LearningLoop real ainda precisa validacao de aprendizado continuo.
- Meta real esta bloqueado ate observabilidade e carga controlada.
- Deploy real esta bloqueado.
- Render real esta bloqueado.

## Riscos operacionais ainda abertos

- Falta teste de carga 10/50/100 execucoes.
- Rollback real continua bloqueado sem confirmacao humana, Brain, credenciais reais e execucao assistida.
- Python real nao esta disponivel neste laptop; `python.exe`, `py.exe` e `python3.exe` apontam para aliases bloqueados da Microsoft Store.

## Resolvido na Missao 27

- Dashboard operacional local criado.
- `correlation_id` global aplicado por middleware.
- `execution_id` e `mission_id` aplicados por middleware.
- Audit log estruturado criado em JSONL.
- Observabilidade passou a gravar dentro da pasta `logs/` do projeto.

## Resolvido no rollback formal

- Politica formal de rollback de producao criada.
- Endpoint `/api/v1/campaign-operator/rollback/policy` validado.
- Rollback real continua protegido por confirmacao humana e Brain.

## Regras

- Nao incluir senhas, tokens, chaves reais ou credenciais.
- Usar apenas `.env.example`.
- Nao iniciar Meta real, MinerEngine real, render real ou deploy real antes da Missao 27A.
