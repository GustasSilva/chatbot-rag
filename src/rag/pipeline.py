"""Montagem: do PDF ao assistente pronto para responder.

``montar_assistente`` é a montagem única do produto, e é só ela que os pontos de entrada
precisam chamar. As funções abaixo dela são os degraus, expostos porque as medições montam
variações (só BM25, ou sem plano B nenhum) para isolar o que estão medindo.
"""
from __future__ import annotations

from dataclasses import dataclass

from .compilador.base_conhecimento import BaseConhecimento
from .compilador.dialogo import Dialogo
from .config import Config
from .corpus import Chunk, carregar_pdf, dividir_em_chunks
from .ia import ChatbotRAG, GeradorOllama
from .recuperacao import Recuperador, RecuperadorBM25, Reranker


@dataclass
class IndiceCorpus:
    """Estado indexado de um corpus, pronto para montar recuperadores."""

    chunks: list[Chunk]
    textos_doc: dict[str, str]


def construir_indice(documentos: dict[str, str], cfg: Config) -> IndiceCorpus:
    """Divide os documentos em chunks. ``documentos`` mapeia doc_id -> texto já normalizado."""
    chunks: list[Chunk] = []
    for doc_id, texto in documentos.items():
        chunks.extend(
            dividir_em_chunks(
                texto, doc_id, cfg.tamanho_chunk, cfg.sobreposicao, id_inicial=len(chunks)
            )
        )
    if not chunks:
        raise ValueError("nenhum chunk gerado — corpus vazio?")

    return IndiceCorpus(chunks, dict(documentos))


def indexar_manual(cfg: Config) -> IndiceCorpus:
    """Lê o Manual do Aluno no caminho da configuração e o indexa."""
    return construir_indice({"manual": carregar_pdf(cfg.caminho_manual)}, cfg)


def montar_esparsa(indice: IndiceCorpus, cfg: Config) -> RecuperadorBM25:
    """Só o BM25. É ele que executa a consulta canônica do núcleo."""
    return RecuperadorBM25(indice.chunks, cfg.k1, cfg.b, cfg.dobrar_acentos)


def montar_recuperador_produto(indice: IndiceCorpus, cfg: Config) -> Recuperador:
    """A recuperação do produto: BM25 com o cross-encoder por cima."""
    return Reranker(
        base=montar_esparsa(indice, cfg),
        chunks=indice.chunks,
        modelo=cfg.modelo_reranker,
        top_k_entrada=cfg.top_k_reranker,
    )


def montar_plano_b(
    recuperador: Recuperador, indice: IndiceCorpus, cfg: Config, saudar: bool = True
) -> ChatbotRAG:
    """O chatbot RAG que responde o que a gramática não reconhece."""
    return ChatbotRAG(
        recuperador,
        indice.chunks,
        GeradorOllama.de_config(cfg),
        cfg.top_k_contexto,
        piso_score=cfg.piso_score,
        saudar=saudar,
    )


def montar_assistente(
    cfg: Config | None = None, com_plano_b: bool = True, saudar: bool = True
) -> Dialogo:
    """O assistente inteiro: Manual indexado, recuperação, núcleo de compilador e plano B.

    ``com_plano_b=False`` deixa o assistente sem modelo de linguagem nenhum, que é a
    demonstração de que quem entende a pergunta é o compilador.
    """
    cfg = cfg or Config()
    indice = indexar_manual(cfg)
    recuperador = montar_recuperador_produto(indice, cfg)
    plano_b = montar_plano_b(recuperador, indice, cfg, saudar) if com_plano_b else None
    base = BaseConhecimento(recuperador, indice.chunks, cfg.top_k_nucleo)
    return Dialogo.de_manual(base, plano_b, cfg.max_intencoes)
