"""Executa a consulta no Manual e escolhe a frase que se mostra ao aluno, sem modelo de linguagem."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..corpus import Chunk
from ..recuperacao import Recuperador, tokenizar
from .fase3_semantica import Consulta

# Fim de frase: ponto, exclamação ou interrogação seguidos de espaço.
_FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class RespostaNucleo:
    """A consulta executada, os trechos encontrados e a frase destacada do primeiro."""

    consulta: Consulta
    trechos: tuple[Chunk, ...]
    destaque: str

    @property
    def encontrou(self) -> bool:
        return bool(self.trechos)


def destacar(texto: str, consulta: str) -> str:
    """A frase do trecho com mais termos em comum com a consulta; no empate, a primeira.

    Usa a mesma separação em termos da busca, para o destaque não discordar da recuperação.
    """
    frases = [frase for frase in _FIM_DE_FRASE.split(texto) if frase.strip()]
    if not frases:
        return texto.strip()
    termos = set(tokenizar(consulta))
    return max(frases, key=lambda frase: len(termos & set(tokenizar(frase)))).strip()


class BaseConhecimento:
    """Liga a consulta ao Manual indexado."""

    def __init__(
        self,
        recuperador: Recuperador,
        chunks: list[Chunk],
        top_k: int = 3,
    ) -> None:
        self._recuperador = recuperador
        self._por_id = {chunk.id: chunk for chunk in chunks}
        self._top_k = top_k

    def consultar(self, consulta: Consulta) -> RespostaNucleo:
        resultados = self._recuperador.buscar(consulta.texto, self._top_k)
        trechos = tuple(self._por_id[resultado.chunk_id] for resultado in resultados)
        destaque = destacar(trechos[0].texto, consulta.texto) if trechos else ""
        return RespostaNucleo(consulta, trechos, destaque)
