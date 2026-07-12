"""Interface do gerador de respostas (Q3 / Marco 3).

O núcleo científico (Q1/Q2) usa só métricas de recuperação e NÃO depende do LLM. A
geração entra apenas no artefato de demonstração (Marco 3), com um LLM fixo e temperatura
0 para reprodutibilidade (protocolo §3). O backend concreto (Claude API, local, ...) será
escolhido e implementado quando o Marco 3 chegar — por isso aqui há só o contrato.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..corpus.chunking import Chunk


@dataclass(frozen=True)
class RespostaGerada:
    texto: str
    fontes: list[int]  # ids dos chunks citados como fonte


class Gerador(ABC):
    """Gera a resposta final a partir da pergunta e dos chunks recuperados."""

    @abstractmethod
    def gerar(self, pergunta: str, contextos: list[Chunk]) -> RespostaGerada:
        raise NotImplementedError


class GeradorNaoConfigurado(Gerador):
    """Placeholder explícito: falha alto se alguém tentar gerar antes do Marco 3."""

    def gerar(self, pergunta: str, contextos: list[Chunk]) -> RespostaGerada:
        raise NotImplementedError(
            "Geração adiada para o Marco 3 (Q3). Escolha o backend do LLM (ex.: Claude API "
            "ou local) e implemente um Gerador concreto com temperatura 0."
        )
