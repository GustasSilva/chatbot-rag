"""Recuperação densa: similaridade vetorial (embedding da pergunta vs. dos chunks).

Como os embeddings são normalizados em L2, o produto interno é a similaridade de
cosseno. O corpus é pequeno o bastante (centenas a poucos milhares de chunks) para
uma busca exaustiva em NumPy — sem necessidade de um índice ANN (faiss).
"""
from __future__ import annotations

import numpy as np

from ..corpus.chunking import Chunk
from ..embeddings import Embedder
from .base import Recuperador, Resultado, ordenar_para_resultados


class RecuperadorDenso(Recuperador):
    nome = "densa"

    def __init__(
        self,
        chunks: list[Chunk],
        embedder: Embedder,
        matriz_embeddings: np.ndarray | None = None,
    ) -> None:
        if not chunks:
            raise ValueError("recuperador denso exige ao menos um chunk")
        self._chunk_ids = [c.id for c in chunks]
        self._embedder = embedder
        # Aceita embeddings pré-computados (cache) ou os calcula na hora.
        self._emb = (
            matriz_embeddings
            if matriz_embeddings is not None
            else embedder.encode_documentos([c.texto for c in chunks])
        )
        if self._emb.shape[0] != len(chunks):
            raise ValueError("nº de embeddings não bate com nº de chunks")

    def buscar(self, consulta: str, k: int) -> list[Resultado]:
        vetor = self._embedder.encode_consultas([consulta])[0]
        scores = self._emb @ vetor  # cosseno (embeddings normalizados)
        pares = [
            (self._chunk_ids[i], float(scores[i])) for i in range(len(self._chunk_ids))
        ]
        return ordenar_para_resultados(pares, k)
