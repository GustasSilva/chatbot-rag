"""Reranker: segundo estágio que reordena o top-k de um recuperador base.

Um cross-encoder lê a pergunta e cada candidato JUNTOS (não vetores separados como no
1º estágio), então é mais preciso e mais caro. O estudo comparativo mediu se esse ganho
de qualidade compensa a latência extra — por isso o reranker é um ``Recuperador`` como os
outros e passa exatamente pela mesma avaliação (Recall@k, MRR). No produto ele permanece
por um segundo motivo: o **piso de score** que recusa fora de escopo é calculado sobre o
escore dele.
"""
from __future__ import annotations

from ..corpus.chunking import Chunk
from .base import Recuperador, Resultado, ordenar_para_resultados


class Reranker(Recuperador):
    def __init__(
        self,
        base: Recuperador,
        chunks: list[Chunk],
        modelo: str,
        top_k_entrada: int = 20,
    ) -> None:
        from sentence_transformers import CrossEncoder  # import tardio (puxa torch)

        self._base = base
        self._texto_por_id = {c.id: c.texto for c in chunks}
        self._modelo = CrossEncoder(modelo)
        self._top_k_entrada = top_k_entrada
        self.nome = f"reranker[{base.nome}]"

    def buscar(self, consulta: str, k: int) -> list[Resultado]:
        candidatos = self._base.buscar(consulta, self._top_k_entrada)
        if not candidatos:
            return []
        pares = [(consulta, self._texto_por_id[r.chunk_id]) for r in candidatos]
        scores = self._modelo.predict(pares)
        recombinados = [
            (candidatos[i].chunk_id, float(scores[i])) for i in range(len(candidatos))
        ]
        return ordenar_para_resultados(recombinados, k)
