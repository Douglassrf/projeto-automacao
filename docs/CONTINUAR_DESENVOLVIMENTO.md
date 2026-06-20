# Instrucoes para Continuar o Desenvolvimento

## Modo Economico Seguro

Antes de qualquer trabalho, seguir `docs/MODO_ECONOMICO_SEGURO.md`.

Regras praticas:

- ler somente arquivos relevantes;
- implementar por patches pequenos;
- nao repetir codigo inteiro no chat;
- colocar relatorios longos em arquivos;
- responder no chat apenas com resumo, validacao, bloqueios e proximo passo;
- rodar teste especifico primeiro e suite completa apenas no fechamento.

## Ritual obrigatorio de inicio

Toda nova missao deve usar o Brain como apoio operacional.

Antes de implementar:

1. Ler `logs/master_context.json`.
2. Ler as ultimas entradas de `logs/decision_feed.log`.
3. Ler as ultimas entradas de `logs/campaign_brain_memory.log`.
4. Confirmar ultima missao homologada e proxima missao recomendada.
5. Usar o Brain para revisar risco, decisao e aprendizado esperado.

Depois de implementar:

1. Rodar validacoes.
2. Registrar decisao no DecisionFeed.
3. Registrar aprendizado no CampaignMemory.
4. Atualizar MasterContext e documentacao.

## Como validar localmente

1. Usar o Python validado no laptop:

```powershell
C:\Users\USUÁRIO\AppData\Local\Programs\Python\Python312\python.exe
```

2. Instalar dependencias com:

```powershell
C:\Users\USUÁRIO\AppData\Local\Programs\Python\Python312\python.exe -m pip install -r requirements.txt
```

3. Rodar os testes da Missao 27:

```bash
C:\Users\USUÁRIO\AppData\Local\Programs\Python\Python312\python.exe -m pytest src/app/tests/test_observability_mission27.py -q
```

4. Rodar a suite existente antes de avancar:

```bash
C:\Users\USUÁRIO\AppData\Local\Programs\Python\Python312\python.exe -m pytest src/app/tests -q
```

5. Abrir Swagger:

```bash
cd src
python -m uvicorn app.main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## Estado atual

Missao 27A foi implementada e validada neste laptop.

Resultado validado:

```txt
80 passed, 2 warnings
```

Carga controlada validada:

```txt
10 / 50 / 100 execucoes
160 requisicoes totais
0 falhas
0.0% erro
100.0% cobertura de trace headers
p95 98.57 ms
```

## Proxima missao

Missao 28 - MinerEngine Real Controlado.

Foco:

- manter Safe / Dry Run como padrao;
- limitar escopo de mineracao real;
- exigir auditoria e rollback;
- consultar Brain antes de cada mudanca;
- registrar todas as decisoes e aprendizados.

## Regras

- Nao chamar Meta real.
- Nao chamar provedores externos reais.
- Nao fazer deploy real.
- Toda missao deve registrar aprendizado em CampaignMemory, DecisionFeed e MasterContext.
