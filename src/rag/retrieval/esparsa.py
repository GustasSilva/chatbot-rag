"""Recuperação esparsa: BM25 Okapi implementado do zero.

Este é o "artesanato de CC" do projeto (protocolo §3) — nenhuma biblioteca de busca
pronta. A pontuação BM25 de um documento ``d`` para uma consulta ``Q`` é:

    score(d, Q) = Σ_{t ∈ Q}  IDF(t) · ( f(t,d) · (k1 + 1) )
                                       ---------------------------------------------
                                       f(t,d) + k1 · (1 − b + b · |d| / avgdl)

onde f(t,d) é a frequência do termo t em d, |d| o tamanho do documento, avgdl o tamanho
médio, e IDF(t) = ln( 1 + (N − df(t) + 0.5) / (df(t) + 0.5) ) (forma que nunca é negativa).

Um índice invertido (termo → lista de (doc, frequência)) faz a busca visitar apenas os
documentos que contêm algum termo da consulta.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict

from ..corpus.chunking import Chunk
from .base import Recuperador, Resultado, ordenar_para_resultados

_PALAVRA = re.compile(r"\w+", re.UNICODE)


def _remover_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def tokenizar(texto: str, dobrar_acentos: bool = False) -> list[str]:
    """Tokenizador PT-BR: minúsculas + palavras (letras acentuadas e dígitos)."""
    texto = texto.lower()
    if dobrar_acentos:
        texto = _remover_acentos(texto)
    return _PALAVRA.findall(texto)


class RecuperadorBM25(Recuperador):
    """Índice BM25 sobre uma lista de chunks."""

    nome = "esparsa"

    def __init__(
        self,
        chunks: list[Chunk],
        k1: float = 1.5,
        b: float = 0.75,
        dobrar_acentos: bool = False,
    ) -> None:
        if not chunks:
            raise ValueError("BM25 exige ao menos um chunk")
        self.k1 = k1
        self.b = b
        self.dobrar_acentos = dobrar_acentos
        self._chunk_ids = [c.id for c in chunks]

        # Índice invertido + estatísticas de tamanho.
        self._postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self._tamanhos: list[int] = []
        for posicao, chunk in enumerate(chunks):
            tokens = tokenizar(chunk.texto, dobrar_acentos)
            self._tamanhos.append(len(tokens))
            for termo, freq in Counter(tokens).items():
                self._postings[termo].append((posicao, freq))

        self._n_docs = len(chunks)
        self._avgdl = sum(self._tamanhos) / self._n_docs

        # IDF pré-calculado por termo (df = nº de documentos que contêm o termo).
        self._idf: dict[str, float] = {}
        for termo, postings in self._postings.items():
            df = len(postings)
            self._idf[termo] = math.log(1 + (self._n_docs - df + 0.5) / (df + 0.5))

    def _pontuar(self, consulta: str) -> dict[int, float]:
        scores: dict[int, float] = defaultdict(float)
        for termo in tokenizar(consulta, self.dobrar_acentos):
            postings = self._postings.get(termo)
            if postings is None:
                continue  # termo fora do vocabulário do corpus
            idf = self._idf[termo]
            for posicao, freq in postings:
                norma = 1 - self.b + self.b * self._tamanhos[posicao] / self._avgdl
                scores[posicao] += idf * (freq * (self.k1 + 1)) / (freq + self.k1 * norma)
        return scores

    def buscar(self, consulta: str, k: int) -> list[Resultado]:
        scores = self._pontuar(consulta)
        pares = [(self._chunk_ids[pos], score) for pos, score in scores.items()]
        return ordenar_para_resultados(pares, k)
