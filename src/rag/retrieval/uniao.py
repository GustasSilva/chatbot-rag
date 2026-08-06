"""Recuperação por união intercalada de densa + esparsa (alternativa ao RRF).

Feita para ALIMENTAR o reranker. O RRF (``hibrida``) funde as duas listas numa média de
ranks que pode DILUIR um acerto forte de um só recuperador: o item que só a densa (ou só a
esparsa) colocou no topo cai atrás de itens que ambos acharam medianamente. A união não faz
média — intercala as duas ordens (densa[0], esparsa[0], densa[1], esparsa[1], ...) e
deduplica, garantindo que o topo de CADA recuperador entre no pool que vai ao reranker.

Os scores aqui não têm significado próprio (o reranker os sobrescreve no 2º estágio); são
decrescentes só para preservar a ordem de intercalação ao passar por ``ordenar_para_resultados``.
"""
from __future__ import annotations

from itertools import zip_longest

from .base import Recuperador, Resultado, ordenar_para_resultados


class RecuperadorUniao(Recuperador):
    nome = "uniao"

    def __init__(self, densa: Recuperador, esparsa: Recuperador) -> None:
        self._densa = densa
        self._esparsa = esparsa

    def buscar(self, consulta: str, k: int) -> list[Resultado]:
        res_densa = self._densa.buscar(consulta, k)
        res_esparsa = self._esparsa.buscar(consulta, k)

        ordem: list[int] = []
        vistos: set[int] = set()
        for r_densa, r_esparsa in zip_longest(res_densa, res_esparsa):
            for r in (r_densa, r_esparsa):
                if r is not None and r.chunk_id not in vistos:
                    vistos.add(r.chunk_id)
                    ordem.append(r.chunk_id)

        pares = [(chunk_id, float(-posicao)) for posicao, chunk_id in enumerate(ordem)]
        return ordenar_para_resultados(pares, k)
