"""Modelo de embedding FIXO do experimento (sentence-transformers / multilingual-e5).

O mesmo embedding é usado nas 3 estratégias que dependem dele (densa e híbrida) e no
corpus inteiro — para isolar o efeito da estratégia de busca, não do embedding (§7).

Modelos e5 exigem prefixos: ``query:`` nas consultas e ``passage:`` nos documentos.
Com normalização L2, o produto interno entre dois vetores já é a similaridade de cosseno.
"""
from __future__ import annotations

import numpy as np

from .config import ConfigEmbeddings


class Embedder:
    """Encapsula o SentenceTransformer, aplicando prefixos e normalização e5."""

    def __init__(
        self,
        modelo: str,
        prefixo_consulta: str,
        prefixo_documento: str,
        normalizar_l2: bool,
        batch_size: int,
        dispositivo: str | None = None,
    ) -> None:
        from sentence_transformers import SentenceTransformer  # import tardio (puxa torch)

        self._modelo = SentenceTransformer(modelo, device=dispositivo)
        self.nome_modelo = modelo
        self.prefixo_consulta = prefixo_consulta
        self.prefixo_documento = prefixo_documento
        self.normalizar_l2 = normalizar_l2
        self.batch_size = batch_size

    @classmethod
    def de_config(cls, cfg: ConfigEmbeddings) -> "Embedder":
        return cls(
            modelo=cfg.modelo,
            prefixo_consulta=cfg.prefixo_consulta,
            prefixo_documento=cfg.prefixo_documento,
            normalizar_l2=cfg.normalizar_l2,
            batch_size=cfg.batch_size,
            dispositivo=cfg.dispositivo,
        )

    def _codificar(self, textos: list[str], prefixo: str) -> np.ndarray:
        entradas = [prefixo + t for t in textos]
        return self._modelo.encode(
            entradas,
            batch_size=self.batch_size,
            normalize_embeddings=self.normalizar_l2,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)

    def encode_documentos(self, textos: list[str]) -> np.ndarray:
        return self._codificar(textos, self.prefixo_documento)

    def encode_consultas(self, textos: list[str]) -> np.ndarray:
        return self._codificar(textos, self.prefixo_consulta)
