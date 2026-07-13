"""Chatbot RAG: liga a recuperação à geração (o artefato de demonstração, Q3).

Usa a melhor recuperação medida nos marcos anteriores (idealmente híbrida + reranker),
pega o top-k de trechos e pede ao gerador uma resposta em português citando a fonte.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..corpus.chunking import Chunk
from ..retrieval.base import Recuperador
from .generator import Gerador, RespostaGerada


@dataclass(frozen=True)
class RespostaChatbot:
    pergunta: str
    resposta: RespostaGerada
    contextos: list[Chunk]  # trechos recuperados que alimentaram o gerador


class ChatbotRAG:
    def __init__(
        self,
        recuperador: Recuperador,
        chunks: list[Chunk],
        gerador: Gerador,
        top_k_contexto: int = 5,
    ) -> None:
        self._recuperador = recuperador
        self._por_id = {c.id: c for c in chunks}
        self._gerador = gerador
        self._top_k = top_k_contexto

    def responder(self, pergunta: str) -> RespostaChatbot:
        resultados = self._recuperador.buscar(pergunta, self._top_k)
        contextos = [self._por_id[r.chunk_id] for r in resultados]
        resposta = self._gerador.gerar(pergunta, contextos)
        return RespostaChatbot(pergunta=pergunta, resposta=resposta, contextos=contextos)
