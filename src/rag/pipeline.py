"""Montagem do pipeline: documentos → chunks → índice → recuperador.

Uma fábrica única garante que o produto monte sempre a mesma coisa: BM25 sobre os chunks e o
cross-encoder por cima. Quem consulta o Manual é a consulta canônica produzida pelo núcleo, já
escrita nas palavras do próprio documento, e nesse caminho o BM25 basta. O cross-encoder
permanece porque o **piso de score** que recusa fora de escopo é calculado sobre o escore dele.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .corpus.chunking import Chunk, dividir_em_chunks
from .recuperacao.base import Recuperador
from .recuperacao.esparsa import RecuperadorBM25
from .recuperacao.reranker import Reranker


@dataclass
class IndiceCorpus:
    """Estado indexado de um corpus, pronto para montar recuperadores."""

    chunks: list[Chunk]
    textos_doc: dict[str, str]


def construir_indice(documentos: dict[str, str], cfg: Config) -> IndiceCorpus:
    """Divide todos os documentos em chunks.

    ``documentos`` mapeia doc_id -> texto já normalizado (``corpus.loaders.limpar_texto``).
    """
    chunks: list[Chunk] = []
    for doc_id, texto in documentos.items():
        chunks.extend(
            dividir_em_chunks(
                texto,
                doc_id,
                cfg.chunking.tamanho_tokens,
                cfg.chunking.sobreposicao_tokens,
                id_inicial=len(chunks),
            )
        )
    if not chunks:
        raise ValueError("nenhum chunk gerado — corpus vazio?")

    return IndiceCorpus(chunks, dict(documentos))


def montar_esparsa(indice: IndiceCorpus, cfg: Config) -> RecuperadorBM25:
    """BM25 sobre os chunks do índice. É o que executa a consulta canônica do núcleo."""
    return RecuperadorBM25(indice.chunks, cfg.bm25.k1, cfg.bm25.b, cfg.bm25.dobrar_acentos)


def montar_reranker(base: Recuperador, indice: IndiceCorpus, cfg: Config) -> Reranker:
    """Envolve um recuperador base com o cross-encoder de reranqueamento."""
    return Reranker(
        base=base,
        chunks=indice.chunks,
        modelo=cfg.reranker.modelo,
        top_k_entrada=cfg.reranker.top_k_entrada,
    )


def montar_recuperador_produto(indice: IndiceCorpus, cfg: Config) -> Recuperador:
    """A configuração de recuperação do produto: BM25 + cross-encoder. Um lugar só."""
    return montar_reranker(montar_esparsa(indice, cfg), indice, cfg)
