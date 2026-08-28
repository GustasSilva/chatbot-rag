"""Fábrica do gerador do plano B.

Mantém o produto (tela e REPL) desacoplado do backend concreto. Hoje há um só: o Ollama, com
modelo fixo e temperatura 0, para que o comportamento seja reprodutível.
"""
from __future__ import annotations

from .generator import Gerador, GeradorOllama


def construir_gerador(cfg_geracao, perfil: str | None = None) -> Gerador:
    """Devolve o gerador do plano B."""
    return GeradorOllama.de_config(cfg_geracao, perfil=perfil)
