"""Missão 51 — Configuration Modularization Engine.

Descobre, agrega e valida todos os domínios de configuração declarados em
`app.core.config_domains/*.py`, produzindo o conjunto de campos usado para
montar a classe `Settings` final em `app.core.config`.

Este módulo é o único lugar que sabe COMO os domínios são combinados.
`config.py` e os domínios em si não precisam saber um do outro — por
isso uma nova área de configuração nunca exige editar este arquivo nem
`config.py`: basta criar um novo arquivo em `config_domains/`.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from app.core import config_domains


class ConfigCollisionError(ValueError):
    """Dois domínios diferentes declararam o mesmo nome de campo.

    Isso nunca deve acontecer silenciosamente: um dos dois valores
    simplesmente desapareceria da configuração final sem aviso. É
    detectado e levantado já na importação do módulo (falha rápida),
    nunca em tempo de requisição.
    """


def discover_domain_models() -> list[type[BaseModel]]:
    """Varre `config_domains/` e devolve toda classe `BaseModel` que é
    DEFINIDA (não apenas importada) em cada submódulo do pacote.

    Ordem: alfabética pelo nome do arquivo, para que a composição final
    de `Settings` seja determinística e independente da ordem de
    iteração do filesystem.
    """
    models: list[type[BaseModel]] = []
    module_infos = sorted(
        pkgutil.iter_modules(config_domains.__path__), key=lambda m: m.name
    )
    for module_info in module_infos:
        module = importlib.import_module(f"{config_domains.__name__}.{module_info.name}")
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            is_local_basemodel = (
                isinstance(attr, type)
                and issubclass(attr, BaseModel)
                and attr is not BaseModel
                and attr.__module__ == module.__name__
            )
            if is_local_basemodel:
                models.append(attr)
    return models


def build_domain_fields() -> dict[str, tuple[Any, FieldInfo]]:
    """Agrega os campos de todos os domínios descobertos em um dict
    pronto para `pydantic.create_model(..., **fields)`.

    Validação automática na inicialização (critério da Missão 51): se
    dois domínios declararem o mesmo nome de campo, levanta
    `ConfigCollisionError` imediatamente, com os dois módulos
    responsáveis nomeados na mensagem.
    """
    fields: dict[str, tuple[Any, FieldInfo]] = {}
    owner_module: dict[str, str] = {}

    for model in discover_domain_models():
        for field_name, field_info in model.model_fields.items():
            if field_name in fields:
                raise ConfigCollisionError(
                    f"Campo de configuração '{field_name}' declarado em mais de "
                    f"um domínio de config_domains/: '{owner_module[field_name]}' "
                    f"e '{model.__module__}'. Nomes de campo precisam ser únicos "
                    "em todo o pacote config_domains/ — renomeie um dos dois."
                )
            owner_module[field_name] = model.__module__
            fields[field_name] = (field_info.annotation, field_info)

    return fields


def domain_summary() -> dict[str, list[str]]:
    """Mapa {nome_do_modulo: [campos]} — usado por testes e por
    endpoints de diagnóstico/documentação para listar de onde vem cada
    campo de configuração sem precisar reabrir o `Settings` monolítico."""
    summary: dict[str, list[str]] = {}
    for model in discover_domain_models():
        module_short_name = model.__module__.rsplit(".", maxsplit=1)[-1]
        summary[module_short_name] = list(model.model_fields.keys())
    return summary
