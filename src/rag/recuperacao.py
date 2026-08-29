"""Recuperação de trechos do corpus: a infraestrutura que o núcleo e o plano B compartilham.

O BM25 é escrito do zero, com índice invertido e IDF Okapi::

    score(d, Q) = Soma_{t em Q}  IDF(t) . ( f(t,d) . (k1 + 1) )
                                 -----------------------------------------
                                 f(t,d) + k1 . (1 - b + b . |d| / avgdl)

O reranker é um cross-encoder, que lê a pergunta e o candidato JUNTOS: mais preciso e mais
caro. Implementa a mesma interface do BM25, e por isso o envolve sem que nada em volta mude.
Permanece no produto por um motivo prático: o **piso de score** que recusa fora de escopo é
calculado sobre o escore dele.
"""
from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass

from .corpus import Chunk, sem_acentos

_PALAVRA = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class Resultado:
    """Um chunk recuperado, com sua posição (0-based) e a pontuação da estratégia."""

    chunk_id: int
    posicao: int
    score: float


class Recuperador(ABC):
    """Dada uma consulta, devolve o top-k de chunks por relevância decrescente."""

    nome: str

    @abstractmethod
    def buscar(self, consulta: str, k: int) -> list[Resultado]:
        raise NotImplementedError


def ordenar_para_resultados(
    pares_id_score: list[tuple[int, float]], k: int
) -> list[Resultado]:
    """Ordena por score decrescente e monta o top-k. Desempata pelo id, para ser estável."""
    ordenados = sorted(pares_id_score, key=lambda par: (-par[1], par[0]))
    return [
        Resultado(chunk_id=chunk_id, posicao=posicao, score=score)
        for posicao, (chunk_id, score) in enumerate(ordenados[:k])
    ]


def tokenizar(texto: str, dobrar_acentos: bool = False) -> list[str]:
    """Tokenizador PT-BR: minúsculas e palavras (letras acentuadas e dígitos)."""
    texto = texto.lower()
    if dobrar_acentos:
        texto = sem_acentos(texto)
    return _PALAVRA.findall(texto)


class RecuperadorBM25(Recuperador):
    """Índice BM25 sobre uma lista de chunks. É o que executa a consulta canônica do núcleo."""

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

        # Índice invertido (termo -> [(documento, frequência)]) e estatísticas de tamanho.
        self._postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self._tamanhos: list[int] = []
        for posicao, chunk in enumerate(chunks):
            tokens = tokenizar(chunk.texto, dobrar_acentos)
            self._tamanhos.append(len(tokens))
            for termo, freq in Counter(tokens).items():
                self._postings[termo].append((posicao, freq))

        self._n_docs = len(chunks)
        self._avgdl = sum(self._tamanhos) / self._n_docs

        # IDF na forma que nunca fica negativa; df = quantos documentos contêm o termo.
        self._idf = {
            termo: math.log(1 + (self._n_docs - len(postings) + 0.5) / (len(postings) + 0.5))
            for termo, postings in self._postings.items()
        }

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


def _carregar_cross_encoder(modelo: str):
    """Carrega o cross-encoder, preferindo o que já está em disco.

    A biblioteca consulta o repositório remoto mesmo com o modelo baixado, e uma queda de
    rede derruba a montagem inteira do assistente. Aqui a rede só entra quando o modelo
    ainda não está em cache, que é a primeira execução da máquina.
    """
    from sentence_transformers import CrossEncoder  # import tardio: puxa o torch

    try:
        return CrossEncoder(modelo, local_files_only=True)
    except Exception:
        return CrossEncoder(modelo)


class Reranker(Recuperador):
    """Segundo estágio: reordena, por cross-encoder, o top-k de um recuperador base."""

    def __init__(
        self,
        base: Recuperador,
        chunks: list[Chunk],
        modelo: str,
        top_k_entrada: int = 20,
    ) -> None:
        self._base = base
        self._texto_por_id = {c.id: c.texto for c in chunks}
        self._modelo = _carregar_cross_encoder(modelo)
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
