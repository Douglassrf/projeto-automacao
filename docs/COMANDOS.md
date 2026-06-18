# Comandos para Instalar, Rodar e Testar

## Windows / Git Bash

Atalhos finais no Windows:

```bat
INICIAR_PROJETO_FINAL.bat
VALIDAR_PROJETO_FINAL.bat
TESTAR_API_LOCAL.bat
VERIFICAR_PACOTE_FINAL.bat
```

```bash
cd projeto_automacao
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cd src
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Acessar:

```txt
http://127.0.0.1:8000/docs
```

## Testes

```bash
cd projeto_automacao
source .venv/Scripts/activate
python -m pytest -p no:cacheprovider --basetemp .pytest_tmp
```

## CompilaÃ§Ã£o rÃ¡pida

```bash
cd projeto_automacao
python -m compileall src/app
```

## Pacote Final Seguro

```txt
docs/inventarios/projeto_automacao_homologacao_final_segura_20260605.zip
```

Validar pacote:

```bat
VERIFICAR_PACOTE_FINAL.bat
```

## ObservaÃ§Ã£o

Se estiver no Windows CMD, use:

```bat
.venv\Scripts\activate
```

