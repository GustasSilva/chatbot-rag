"""Montagem do pipeline: documentos → chunks → índices → recuperadores.

Uma fábrica única garante que as 3 estratégias compartilham exatamente os mesmos chunks
e o mesmo embedding — só a estratégia de busca muda (protocolo §7). O embedding denso é
calculado uma vez e reaproveitado pela densa e pela híbrida.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from .config import Config
from .corpus.chunking import Chunk, dividir_em_chunks
from .embeddings import Embedder
from .retrieval.base import Recuperador
from .retrieval.densa import RecuperadorDenso
from .retrieval.esparsa import RecuperadorBM25
from .retrieval.hibrida import RecuperadorHibrido
from .retrieval.reranker import Reranker

ESTRATEGIAS_PADRAO = ("densa", "esparsa", "hibrida")


@dataclass
class IndiceCorpus:
    """Estado indexado de um corpus, pronto para montar recuperadores."""

    chunks: list[Chunk]
    textos_doc: dict[str, str]
    embedder: Embedder | None = None
    matriz_densa: np.ndarray | None = None


def construir_indice(
    documentos: dict[str, str],
    cfg: Config,
    embedder: Embedder | None = None,
    calcular_densa: bool = True,
) -> IndiceCorpus:
    """Chunka todos os documentos e (opcionalmente) pré-computa os embeddings densos.

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

    matriz = None
    if calcular_densa:
        embedder = embedder or Embedder.de_config(cfg.embeddings)
        matriz = embedder.encode_documentos([c.texto for c in chunks])

    return IndiceCorpus(chunks, dict(documentos), embedder, matriz)


def montar_recuperadores(
    indice: IndiceCorpus,
    cfg: Config,
    incluir: Iterable[str] = ESTRATEGIAS_PADRAO,
) -> dict[str, Recuperador]:
    """Instancia as estratégias pedidas, reaproveitando chunks e embedding do índice."""
    incluir = set(incluir)
    precisa_densa = bool(incluir & {"densa", "hibrida"})
    precisa_esparsa = bool(incluir & {"esparsa", "hibrida"})

    densa = esparsa = None
    if precisa_densa:
        if indice.embedder is None or indice.matriz_densa is None:
            raise ValueError("índice sem embedding denso — construa com calcular_densa=True")
        densa = RecuperadorDenso(indice.chunks, indice.embedder, indice.matriz_densa)
    if precisa_esparsa:
        esparsa = RecuperadorBM25(
            indice.chunks, cfg.bm25.k1, cfg.bm25.b, cfg.bm25.dobrar_acentos
        )

    recuperadores: dict[str, Recuperador] = {}
    if "densa" in incluir:
        recuperadores["densa"] = densa
    if "esparsa" in incluir:
        recuperadores["esparsa"] = esparsa
    if "hibrida" in incluir:
        recuperadores["hibrida"] = RecuperadorHibrido(
            densa,
            esparsa,
            metodo=cfg.hibrida.metodo,
            rrf_k=cfg.hibrida.rrf_k,
            peso_densa=cfg.hibrida.peso_densa,
            peso_esparsa=cfg.hibrida.peso_esparsa,
        )
    return recuperadores


def montar_reranker(base: Recuperador, indice: IndiceCorpus, cfg: Config) -> Reranker:
    """Envolve um recuperador base com o cross-encoder de reranqueamento (Q2)."""
    return Reranker(
        base=base,
        chunks=indice.chunks,
        modelo=cfg.reranker.modelo,
        top_k_entrada=cfg.reranker.top_k_entrada,
    )


def montar_recuperador_produto(indice: IndiceCorpus, cfg: Config) -> Recuperador:
    """A configuração de recuperação do PRODUTO: BM25 + cross-encoder. Um lugar só.

    Difere da vencedora do estudo comparativo (híbrida + reranker) por razão medida: com a
    consulta canônica, BM25 puro deu resultado idêntico. O cross-encoder fica pelo ``piso_score``,
    que é o guardrail do plano B. Detalhe em ``docs/decisoes.md`` §10.
    """
    esparsa = montar_recuperadores(indice, cfg, incluir=["esparsa"])["esparsa"]
    return montar_reranker(esparsa, indice, cfg)
