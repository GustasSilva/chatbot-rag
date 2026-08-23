"""Recuperação híbrida: combina a densa e a esparsa.

Dois métodos de fusão (protocolo §3 cita "soma ponderada ou fusão de ranks"):

- ``rrf`` (Reciprocal Rank Fusion): soma 1/(rrf_k + posição) entre as listas. Usa só a
  ordem, então é imune à diferença de escala entre score de cosseno e score BM25. Padrão.
- ``soma_ponderada``: normaliza cada lista de scores em [0, 1] (min–max) e soma com pesos.

A fusão opera sobre um pool mais profundo que ``k`` em cada estratégia, senão um bom
candidato que aparece fora do top-k de uma das listas nunca entraria na combinação.
"""
from __future__ import annotations

from collections import defaultdict

from .base import Recuperador, Resultado, ordenar_para_resultados


class RecuperadorHibrido(Recuperador):
    nome = "hibrida"

    def __init__(
        self,
        densa: Recuperador,
        esparsa: Recuperador,
        metodo: str = "rrf",
        rrf_k: int = 60,
        peso_densa: float = 0.5,
        peso_esparsa: float = 0.5,
        profundidade_fusao: int = 100,
    ) -> None:
        if metodo not in ("rrf", "soma_ponderada"):
            raise ValueError(f"método de fusão desconhecido: {metodo}")
        self._densa = densa
        self._esparsa = esparsa
        self._metodo = metodo
        self._rrf_k = rrf_k
        self._peso_densa = peso_densa
        self._peso_esparsa = peso_esparsa
        self._profundidade = profundidade_fusao

    def buscar(self, consulta: str, k: int) -> list[Resultado]:
        pool = max(k, self._profundidade)
        res_densa = self._densa.buscar(consulta, pool)
        res_esparsa = self._esparsa.buscar(consulta, pool)

        if self._metodo == "rrf":
            fundido = self._fundir_rrf(res_densa, res_esparsa)
        else:
            fundido = self._fundir_soma_ponderada(res_densa, res_esparsa)

        return ordenar_para_resultados(fundido, k)

    def _fundir_rrf(
        self, res_densa: list[Resultado], res_esparsa: list[Resultado]
    ) -> list[tuple[int, float]]:
        combinado: dict[int, float] = defaultdict(float)
        for resultados in (res_densa, res_esparsa):
            for r in resultados:
                combinado[r.chunk_id] += 1.0 / (self._rrf_k + r.posicao + 1)
        return list(combinado.items())

    def _fundir_soma_ponderada(
        self, res_densa: list[Resultado], res_esparsa: list[Resultado]
    ) -> list[tuple[int, float]]:
        norm_densa = self._normalizar(res_densa)
        norm_esparsa = self._normalizar(res_esparsa)
        combinado: dict[int, float] = defaultdict(float)
        for chunk_id, s in norm_densa.items():
            combinado[chunk_id] += self._peso_densa * s
        for chunk_id, s in norm_esparsa.items():
            combinado[chunk_id] += self._peso_esparsa * s
        return list(combinado.items())

    @staticmethod
    def _normalizar(resultados: list[Resultado]) -> dict[int, float]:
        """Min–max dos scores para [0, 1]; lista vazia ou constante vira zeros."""
        if not resultados:
            return {}
        scores = [r.score for r in resultados]
        menor, maior = min(scores), max(scores)
        amplitude = maior - menor
        if amplitude == 0:
            return {r.chunk_id: 0.0 for r in resultados}
        return {r.chunk_id: (r.score - menor) / amplitude for r in resultados}
