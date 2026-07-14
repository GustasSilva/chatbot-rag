"""Chatbot RAG: liga a recuperação à geração (o artefato de demonstração, Q3).

Usa a melhor recuperação medida nos marcos anteriores (idealmente híbrida + reranker),
pega o top-k de trechos e pede ao gerador uma resposta em português citando a fonte.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..corpus.chunking import Chunk
from ..retrieval.base import Recuperador
from .generator import RECUSA_PADRAO, Gerador, RespostaGerada


@dataclass(frozen=True)
class RespostaChatbot:
    pergunta: str
    resposta: RespostaGerada
    contextos: list[Chunk]  # trechos recuperados que alimentaram o gerador


class ChatbotRAG:
    """Liga recuperação e geração, com um piso de score opcional como guardrail.

    ``piso_score`` recusa a pergunta ANTES de chamar o LLM quando nem o melhor trecho
    recuperado tem confiança suficiente (score do 1º estágio abaixo do piso). É defesa em
    profundidade contra vazamento: perguntas fora do domínio puxam trechos lexicalmente
    vizinhos e um guardrail brando pode respondê-los; o piso barra esses casos e ainda
    economiza a latência do LLM. O valor é específico do recuperador — só faz sentido com
    o reranker (cross-encoder, logits) e é calibrado contra o gold-set do corpus.
    """

    def __init__(
        self,
        recuperador: Recuperador,
        chunks: list[Chunk],
        gerador: Gerador,
        top_k_contexto: int = 5,
        piso_score: float | None = None,
    ) -> None:
        self._recuperador = recuperador
        self._por_id = {c.id: c for c in chunks}
        self._gerador = gerador
        self._top_k = top_k_contexto
        self._piso_score = piso_score

    def responder(self, pergunta: str) -> RespostaChatbot:
        resultados = self._recuperador.buscar(pergunta, self._top_k)
        if self._piso_score is not None and (
            not resultados or resultados[0].score < self._piso_score
        ):
            return RespostaChatbot(pergunta, RespostaGerada(RECUSA_PADRAO, []), [])
        contextos = [self._por_id[r.chunk_id] for r in resultados]
        resposta = self._gerador.gerar(pergunta, contextos)
        return RespostaChatbot(pergunta=pergunta, resposta=resposta, contextos=contextos)
