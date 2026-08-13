"""Fábrica do gerador do produto: escolhe o backend conforme a configuração/ambiente.

Mantém o produto (tela e REPL) desacoplado do backend concreto. Se houver um GGUF disponível
(env ``GGUF_MODEL`` ou ``geracao.caminho_modelo_gguf``), usa o backend **llama-cpp com saída JSON
garantida por gramática** — a intervenção de compiladores. Caso contrário, cai no backend
**Ollama** (o comportamento validado até aqui). Assim, ligar a intervenção não exige commitar
nenhum caminho de máquina: basta apontar o GGUF por env ou por config local.
"""
from __future__ import annotations

import os

from .generator import Gerador, GeradorOllama


def construir_gerador(cfg_geracao, perfil: str | None = None) -> Gerador:
    """Devolve o gerador do produto (llama-cpp/JSON se houver GGUF; senão Ollama)."""
    caminho = os.environ.get("GGUF_MODEL") or getattr(cfg_geracao, "caminho_modelo_gguf", None)
    if caminho:
        from .llamacpp import GeradorLlamaCpp  # import tardio: só exige a lib quando usada

        return GeradorLlamaCpp(
            caminho_modelo=caminho,
            perfil=perfil or cfg_geracao.perfil_guardrail,
            temperatura=cfg_geracao.temperatura,
            n_ctx=getattr(cfg_geracao, "n_ctx", 4096),
            n_gpu_layers=getattr(cfg_geracao, "n_gpu_layers", -1),
            modo="json",
        )
    return GeradorOllama.de_config(cfg_geracao, perfil=perfil)
