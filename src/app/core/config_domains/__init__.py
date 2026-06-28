"""Missão 51 — Configuration Modularization Engine.

Cada módulo neste pacote declara UM domínio de configuração isolado, como
uma subclasse de `pydantic.BaseModel` (nunca `BaseSettings` diretamente —
quem carrega variáveis de ambiente/arquivo .env é o `Settings` final,
montado em `app.core.config_loader`).

Para adicionar uma nova área de configuração:

1. Crie um novo arquivo aqui, ex.: `config_domains/minha_feature.py`.
2. Declare `class MinhaFeatureConfig(BaseModel): meu_campo: str = "default"`.
3. Pronto. NENHUMA edição em `config.py` ou `config_loader.py` é
   necessária — a descoberta é automática (`pkgutil.iter_modules`).

Esse é o critério de sucesso da Missão 51: nenhuma funcionalidade nova
precisa mais editar o arquivo central de configuração.

Regra: nomes de campo precisam ser únicos em TODOS os domínios. Uma
colisão de nome é detectada e levanta `ConfigCollisionError` na
inicialização (falha rápida, nunca silenciosa) — ver `config_loader.py`.
"""
