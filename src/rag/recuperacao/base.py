"""Contrato comum dos recuperadores.

O BM25 e o reranker devolvem a mesma estrutura, uma lista de ``Resultado`` ordenada do mais
para o menos relevante, de modo que um pode envolver o outro sem que nada em volta mude.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Resultado:
    """Um chunk recuperado, com sua posição (0-based) e pontuação na estratégia."""

    chunk_id: int
    posicao: int
    score: float


class Recuperador(ABC):
    """Estratégia de recuperação: dada uma consulta, devolve o top-k de chunks."""

    nome: str

    @abstractmethod
    def buscar(self, consulta: str, k: int) -> list[Resultado]:
        """Devolve até ``k`` resultados ordenados por relevância decrescente."""
        raise NotImplementedError


def ordenar_para_resultados(
    pares_id_score: list[tuple[int, float]], k: int
) -> list[Resultado]:
    """Ordena ``(chunk_id, score)`` por score decrescente e monta os ``Resultado`` do top-k.

    Desempate estável e determinístico pelo ``chunk_id`` (evita variação entre execuções
    quando dois chunks têm o mesmo score).
    """
    ordenados = sorted(pares_id_score, key=lambda par: (-par[1], par[0]))
    return [
        Resultado(chunk_id=chunk_id, posicao=posicao, score=score)
        for posicao, (chunk_id, score) in enumerate(ordenados[:k])
    ]
