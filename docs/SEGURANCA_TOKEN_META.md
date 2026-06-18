# Seguranca do Token Meta

## Regra principal

Nunca enviar `META_ACCESS_TOKEN` no chat, e-mail, documento, print, ZIP publico ou GitHub.

## Forma segura neste projeto

1. O usuario cola o token diretamente no arquivo `.env` local.
2. O Codex valida apenas se o campo esta presente, sem imprimir o valor.
3. O projeto le o token via variavel de ambiente.
4. `.env` fica ignorado por `.gitignore`.
5. Zips homologados nao devem incluir `.env`.
6. Em producao, trocar `DEFAULT_ADMIN_PASSWORD` no `.env` local antes de expor a API.

## Configuracao inicial segura

```txt
META_ENV=sandbox
META_DRY_RUN=true
META_AUTOPUBLISH=false
META_ALLOW_PRODUCTION_REAL=false
```

## Antes de qualquer gasto

Exigir confirmacao humana explicita.

## Revogacao

Se houver suspeita de vazamento, revogar o token na Meta e gerar outro.
