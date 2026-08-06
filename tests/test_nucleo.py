"""Testes unitários do núcleo — rápidos, sem baixar modelo de embedding.

Cobrem o "artesanato" (BM25), métricas, estatística pareada, chunking e resolução de
relevância do gold-set. A plumbing densa/híbrida é testada com um embedder falso
determinístico, para não exigir download de modelo no CI.
"""
from __future__ import annotations

import re

import numpy as np
import pytest

from rag.corpus.chunking import dividir_em_chunks
from rag.corpus.loaders import limpar_texto
from rag.evaluation import stats
from rag.evaluation.goldset import (
    GoldSetError,
    ItemGold,
    construir_relevancia,
    construir_relevancia_por_documento,
)
from rag.evaluation.metrics import recall_em_k, reciprocal_rank
from rag.retrieval.densa import RecuperadorDenso
from rag.retrieval.esparsa import RecuperadorBM25, tokenizar
from rag.retrieval.hibrida import RecuperadorHibrido


# --------------------------------------------------------------------------- #
# Embedder falso: vetor bag-of-words sobre um vocabulário fixo, normalizado.
# Determinístico e offline — só para exercitar a plumbing densa/híbrida.
# --------------------------------------------------------------------------- #
class EmbedderFalso:
    def __init__(self, vocab: list[str]) -> None:
        self._vocab = {termo: i for i, termo in enumerate(vocab)}

    def _vetor(self, texto: str) -> np.ndarray:
        v = np.zeros(len(self._vocab), dtype=np.float32)
        for termo in re.findall(r"\w+", texto.lower()):
            if termo in self._vocab:
                v[self._vocab[termo]] += 1.0
        norma = np.linalg.norm(v)
        return v / norma if norma > 0 else v

    def encode_documentos(self, textos: list[str]) -> np.ndarray:
        return np.vstack([self._vetor(t) for t in textos])

    def encode_consultas(self, textos: list[str]) -> np.ndarray:
        return np.vstack([self._vetor(t) for t in textos])


def _chunks_de(textos: list[str]):
    """Um chunk por texto (tamanho grande o bastante para não subdividir)."""
    from rag.corpus.chunking import Chunk

    return [
        Chunk(id=i, doc_id="d", texto=t, inicio_char=0, fim_char=len(t), indice_no_doc=i)
        for i, t in enumerate(textos)
    ]


# ------------------------------- chunking ---------------------------------- #
def test_chunking_overlap_e_offsets():
    texto = " ".join(f"tok{i}" for i in range(20))
    chunks = dividir_em_chunks(texto, "d", tamanho_tokens=5, sobreposicao_tokens=2)
    # offsets devem recortar exatamente o texto do chunk
    for c in chunks:
        assert texto[c.inicio_char : c.fim_char] == c.texto
    # passo = 5 - 2 = 3 tokens entre janelas -> há sobreposição
    assert chunks[0].texto.split()[-2:] == chunks[1].texto.split()[:2]
    # última janela cobre o fim
    assert chunks[-1].texto.split()[-1] == "tok19"


def test_chunking_rejeita_overlap_grande():
    with pytest.raises(ValueError):
        dividir_em_chunks("a b c", "d", tamanho_tokens=3, sobreposicao_tokens=3)


def test_limpar_texto_colapsa_espacos():
    assert limpar_texto("a\n\n  b\t c ") == "a b c"


# --------------------------------- BM25 ------------------------------------ #
def test_bm25_recupera_documento_obvio():
    docs = _chunks_de(
        [
            "o gato subiu no telhado e dormiu",
            "a matrícula deve ser feita na secretaria",
            "o limite de faltas é de vinte e cinco por cento",
        ]
    )
    bm25 = RecuperadorBM25(docs)
    top = bm25.buscar("quantas faltas posso ter", k=3)
    assert top[0].chunk_id == 2  # o doc sobre faltas vem primeiro


def test_bm25_idf_nao_negativo():
    docs = _chunks_de(["termo comum aqui", "termo comum ali", "raro"])
    bm25 = RecuperadorBM25(docs)
    assert all(v >= 0 for v in bm25._idf.values())


def test_tokenizar_mantem_acentos_e_dobra_opcional():
    assert tokenizar("Matrícula Não") == ["matrícula", "não"]
    assert tokenizar("Matrícula Não", dobrar_acentos=True) == ["matricula", "nao"]


# ------------------------------- densa/híbrida ----------------------------- #
def test_densa_recupera_por_significado():
    textos = ["gato telhado dormiu", "matrícula secretaria prazo", "faltas limite frequência"]
    docs = _chunks_de(textos)
    vocab = sorted({t for texto in textos for t in re.findall(r"\w+", texto.lower())})
    emb = EmbedderFalso(vocab)
    densa = RecuperadorDenso(docs, emb, emb.encode_documentos(textos))
    top = densa.buscar("prazo de matrícula", k=3)
    assert top[0].chunk_id == 1


def test_hibrida_funde_sem_erro():
    textos = ["gato telhado", "matrícula secretaria", "faltas limite"]
    docs = _chunks_de(textos)
    vocab = sorted({t for texto in textos for t in re.findall(r"\w+", texto.lower())})
    emb = EmbedderFalso(vocab)
    densa = RecuperadorDenso(docs, emb, emb.encode_documentos(textos))
    esparsa = RecuperadorBM25(docs)
    hibrida = RecuperadorHibrido(densa, esparsa, metodo="rrf")
    top = hibrida.buscar("limite de faltas", k=3)
    assert top[0].chunk_id == 2


def test_uniao_intercala_topo_de_cada_e_deduplica():
    """A união intercala densa[0], esparsa[0], ... e deduplica — o topo de CADA
    recuperador entra no pool sem diluição (ao contrário da média do RRF)."""
    from rag.retrieval.base import Recuperador, Resultado
    from rag.retrieval.uniao import RecuperadorUniao

    class _RecFixo(Recuperador):
        nome = "fixo"

        def __init__(self, ids: list[int]) -> None:
            self._ids = ids

        def buscar(self, consulta: str, k: int) -> list[Resultado]:
            return [Resultado(chunk_id=c, posicao=i, score=float(-i))
                    for i, c in enumerate(self._ids[:k])]

    densa = _RecFixo([10, 20, 30])    # densa coloca 10 no topo
    esparsa = _RecFixo([40, 20, 50])  # esparsa coloca 40 no topo (20 é comum)
    top = RecuperadorUniao(densa, esparsa).buscar("q", k=4)
    ids = [r.chunk_id for r in top]

    assert ids[:2] == [10, 40]          # topo de cada um entra sem diluição
    assert ids == [10, 40, 20, 30]      # 20 deduplicado; ordem de intercalação mantida
    assert len(ids) == len(set(ids))    # sem duplicatas


# ------------------------------- métricas ---------------------------------- #
def test_recall_e_mrr():
    ids = [5, 3, 9, 1]
    relevantes = {9}
    assert recall_em_k(ids, relevantes, 1) == 0.0
    assert recall_em_k(ids, relevantes, 3) == 1.0
    assert reciprocal_rank(ids, relevantes) == pytest.approx(1 / 3)
    assert reciprocal_rank(ids, {42}) == 0.0


# ------------------------------- estatística ------------------------------- #
def test_holm_ajusta_valores():
    ajustado = stats.holm([0.01, 0.04, 0.03])
    assert ajustado == pytest.approx([0.03, 0.06, 0.06])


def test_wilcoxon_seguro_empate_total():
    a = np.array([1.0, 1.0, 1.0])
    est, p, n_ef = stats._wilcoxon_seguro(a, a.copy())
    assert n_ef == 0 and p == 1.0 and np.isnan(est)


def test_efeito_rank_biserial_direcao():
    a = np.array([0.0, 0.0, 0.0])
    b = np.array([1.0, 1.0, 1.0])
    assert stats.efeito_rank_biserial(a, b) == pytest.approx(1.0)   # b supera a
    assert stats.efeito_rank_biserial(b, a) == pytest.approx(-1.0)  # simétrico


def test_comparar_exige_pareamento():
    with pytest.raises(ValueError):
        stats.comparar_estrategias({"a": np.array([1, 2, 3]), "b": np.array([1, 2])})


# ------------------------------- gold-set ---------------------------------- #
def test_relevancia_localiza_trecho():
    texto = limpar_texto("O limite de faltas é de vinte e cinco por cento da carga horária.")
    chunks = dividir_em_chunks(texto, "doc", tamanho_tokens=6, sobreposicao_tokens=2)
    item = ItemGold(
        id="q1",
        pergunta="qual o limite de faltas?",
        resposta="25%",
        trecho_fonte="vinte e cinco por cento",
    )
    relevancia = construir_relevancia([item], chunks, {"doc": texto}, limiar=0.5)
    assert relevancia["q1"]  # ao menos um chunk relevante


def test_relevancia_trecho_inexistente_falha():
    texto = limpar_texto("texto qualquer sem o trecho procurado")
    chunks = dividir_em_chunks(texto, "doc", tamanho_tokens=6, sobreposicao_tokens=2)
    item = ItemGold(id="q", pergunta="?", resposta="x", trecho_fonte="frase que não existe")
    with pytest.raises(GoldSetError):
        construir_relevancia([item], chunks, {"doc": texto}, limiar=0.5)


def test_relevancia_por_documento():
    """Relevância em nível de documento (usada no Pirá): todos os chunks do doc do item."""
    from rag.corpus.chunking import Chunk

    chunks = [
        Chunk(id=0, doc_id="A", texto="a1", inicio_char=0, fim_char=2, indice_no_doc=0),
        Chunk(id=1, doc_id="A", texto="a2", inicio_char=0, fim_char=2, indice_no_doc=1),
        Chunk(id=2, doc_id="B", texto="b1", inicio_char=0, fim_char=2, indice_no_doc=0),
    ]
    item = ItemGold(id="q", pergunta="?", resposta="x", trecho_fonte="", doc_id="A")
    relevancia = construir_relevancia_por_documento([item], chunks)
    assert relevancia["q"] == {0, 1}  # ambos os chunks do doc A, nenhum do B

    item_orfao = ItemGold(id="q2", pergunta="?", resposta="x", trecho_fonte="", doc_id="Z")
    with pytest.raises(GoldSetError):
        construir_relevancia_por_documento([item_orfao], chunks)


# ------------------------------- geração ----------------------------------- #
def test_extrair_fontes_citadas():
    """Parser de citação: aceita [1], [1, 2] e [1,2]; ignora fora do intervalo."""
    from rag.corpus.chunking import Chunk
    from rag.generation.generator import extrair_fontes_citadas

    ctx = [
        Chunk(id=10, doc_id="d", texto="a", inicio_char=0, fim_char=1, indice_no_doc=0),
        Chunk(id=20, doc_id="d", texto="b", inicio_char=0, fim_char=1, indice_no_doc=1),
        Chunk(id=30, doc_id="d", texto="c", inicio_char=0, fim_char=1, indice_no_doc=2),
    ]
    assert extrair_fontes_citadas("resposta [1, 2].", ctx) == [10, 20]  # vírgula no colchete
    assert extrair_fontes_citadas("veja [1] e [3].", ctx) == [10, 30]   # colchetes separados
    assert extrair_fontes_citadas("cita [9] inválido.", ctx) == []       # fora do intervalo
    assert extrair_fontes_citadas("sem citação.", ctx) == []


def test_guardrail_contexto_vazio_recusa():
    """Sem contexto recuperado, o gerador recusa sem sequer chamar o LLM (não alucina)."""
    from rag.generation.generator import GeradorOllama

    g = GeradorOllama(modelo="inexistente")  # __init__ não conecta em lugar nenhum
    r = g.gerar("qualquer pergunta", [])
    assert r.fontes == []
    assert "não encontrei" in r.texto.lower()


def test_perfil_guardrail_seleciona_prompt():
    """O perfil escolhe o system prompt; perfil inválido falha alto."""
    from rag.generation.generator import (
        _SISTEMA_ESTRITO,
        _SISTEMA_INSTITUCIONAL,
        GeradorOllama,
    )

    assert GeradorOllama(modelo="x", perfil="estrito")._sistema == _SISTEMA_ESTRITO
    assert GeradorOllama(modelo="x", perfil="institucional")._sistema == _SISTEMA_INSTITUCIONAL
    with pytest.raises(ValueError):
        GeradorOllama(modelo="x", perfil="inexistente")


def test_piso_score_recusa_antes_de_gerar():
    """O piso de score recusa fora-de-escopo (score baixo) SEM chamar o gerador; acima
    do piso, gera normalmente."""
    from rag.corpus.chunking import Chunk
    from rag.generation.chatbot import ChatbotRAG
    from rag.generation.generator import Gerador, RespostaGerada
    from rag.retrieval.base import Recuperador, Resultado

    chunk = Chunk(id=1, doc_id="d", texto="conteúdo", inicio_char=0, fim_char=8, indice_no_doc=0)

    class _RecFixo(Recuperador):
        nome = "fixo"

        def __init__(self, score: float) -> None:
            self._score = score

        def buscar(self, consulta: str, k: int) -> list[Resultado]:
            return [Resultado(chunk_id=1, posicao=0, score=self._score)]

    class _GeradorEspiao(Gerador):
        chamado = False

        def gerar(self, pergunta, contextos):
            self.__class__.chamado = True
            return RespostaGerada("resposta gerada", [1])

    # Abaixo do piso: recusa, contexto vazio, gerador NÃO chamado.
    _GeradorEspiao.chamado = False
    bot = ChatbotRAG(_RecFixo(-4.0), [chunk], _GeradorEspiao(), top_k_contexto=5, piso_score=-3.2)
    r = bot.responder("pergunta fora de escopo")
    assert "não encontrei" in r.resposta.texto.lower()
    assert r.contextos == []
    assert _GeradorEspiao.chamado is False

    # Acima do piso: gera normalmente.
    _GeradorEspiao.chamado = False
    bot_ok = ChatbotRAG(_RecFixo(1.5), [chunk], _GeradorEspiao(), top_k_contexto=5, piso_score=-3.2)
    r_ok = bot_ok.responder("pergunta in-scope")
    assert r_ok.resposta.texto == "resposta gerada"
    assert _GeradorEspiao.chamado is True
