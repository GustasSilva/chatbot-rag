"""Testes unitários da infraestrutura — rápidos, sem baixar modelo.

Cobrem o BM25 escrito à mão, a divisão em trechos, a resolução de relevância do
conjunto de referência e o plano B: guardrail, saudação, multiturno e piso de score.
Os testes do núcleo de compilador estão nos arquivos por fase (léxico, sintático,
semântico, base de conhecimento, diálogo).
"""
from __future__ import annotations

import re

import pytest

from rag.corpus import dividir_em_chunks
from rag.corpus import limpar_texto
from rag.goldset import GoldSetError, ItemGold, construir_relevancia
from rag.recuperacao import RecuperadorBM25, tokenizar


def _chunks_de(textos: list[str]):
    """Um chunk por texto (tamanho grande o bastante para não subdividir)."""
    from rag.corpus import Chunk

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


# ------------------------------- geração ----------------------------------- #
def test_extrair_fontes_citadas():
    """Parser de citação: aceita [1], [1, 2] e [1,2]; ignora fora do intervalo."""
    from rag.corpus import Chunk
    from rag.ia import extrair_fontes_citadas

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
    from rag.ia import GeradorOllama

    g = GeradorOllama(modelo="inexistente")  # __init__ não conecta em lugar nenhum
    r = g.gerar("qualquer pergunta", [])
    assert r.fontes == []
    assert "não encontrei" in r.texto.lower()


def test_eh_saudacao_dispara_so_em_saudacao_pura():
    """O detector é conservador: True só quando a mensagem é SÓ saudação; qualquer
    pergunta substantiva (inclusive fora de escopo) devolve False e segue para o pipeline."""
    from rag.apresentacao import eh_saudacao

    for t in ["olá", "Oi!", "bom dia", "tudo bem?", "Olá, tudo bem?",
              "e aí, beleza?", "boa noite", "opa"]:
        assert eh_saudacao(t), f"deveria ser saudação: {t!r}"

    for t in ["qual o limite de faltas?", "me conta uma piada", "qual o tratamento para asma?",
              "você gosta de mim?", "olá, qual o limite de faltas?", "qual a data das provas?"]:
        assert not eh_saudacao(t), f"NÃO deveria ser saudação: {t!r}"


def test_saudacao_curto_circuita_sem_recuperar_nem_gerar():
    """Com saudar=True, uma saudação pura devolve a mensagem amigável sem tocar no
    recuperador nem no gerador; sem saudar=True, segue o fluxo normal."""
    from rag.corpus import Chunk
    from rag.apresentacao import RESPOSTAS_SAUDACAO
    from rag.ia import ChatbotRAG
    from rag.ia import Gerador, RespostaGerada
    from rag.recuperacao import Recuperador, Resultado

    chunk = Chunk(id=1, doc_id="d", texto="x", inicio_char=0, fim_char=1, indice_no_doc=0)

    class _RecEspiao(Recuperador):
        nome = "espiao"
        chamado = False

        def buscar(self, consulta, k):
            self.__class__.chamado = True
            return [Resultado(chunk_id=1, posicao=0, score=5.0)]

    class _GerFixo(Gerador):
        def gerar(self, pergunta, contextos, historico=None):
            return RespostaGerada("resposta do LLM", [1])

    _RecEspiao.chamado = False
    bot = ChatbotRAG(_RecEspiao(), [chunk], _GerFixo(), piso_score=None, saudar=True)
    r = bot.responder("olá, tudo bem?")
    assert r.texto in RESPOSTAS_SAUDACAO
    assert r.trechos == [] and r.fontes == []
    assert _RecEspiao.chamado is False  # não recuperou nada

    # Pergunta de verdade passa pelo pipeline mesmo com saudar=True.
    _RecEspiao.chamado = False
    r2 = bot.responder("qual o limite de faltas?")
    assert r2.texto == "resposta do LLM"
    assert _RecEspiao.chamado is True


def test_multiturn_recupera_pela_pergunta_reescrita_e_gera_com_historico():
    """Com histórico, o ChatbotRAG recupera pela pergunta REESCRITA (autônoma) e passa o
    histórico ao gerador. Sem histórico, usa a pergunta original e não reescreve."""
    from rag.corpus import Chunk
    from rag.ia import ChatbotRAG
    from rag.ia import Gerador, RespostaGerada
    from rag.recuperacao import Recuperador, Resultado

    chunk = Chunk(id=1, doc_id="d", texto="x", inicio_char=0, fim_char=1, indice_no_doc=0)

    class _RecGrava(Recuperador):
        nome = "grava"
        consulta_usada = None

        def buscar(self, consulta, k):
            self.__class__.consulta_usada = consulta
            return [Resultado(chunk_id=1, posicao=0, score=5.0)]

    class _GerReescreve(Gerador):
        historico_recebido = "nao chamado"
        reescreveu = False

        def gerar(self, pergunta, contextos, historico=None):
            self.__class__.historico_recebido = historico
            return RespostaGerada("ok", [1])

        def reescrever_consulta(self, pergunta, historico):
            self.__class__.reescreveu = True
            return "PERGUNTA REESCRITA AUTONOMA"

    hist = [("qual a data das provas?", "25/5 a 30/5 ...")]
    bot = ChatbotRAG(_RecGrava(), [chunk], _GerReescreve(), piso_score=None)

    _GerReescreve.reescreveu = False
    bot.responder("e as presenciais?", historico=hist)
    assert _RecGrava.consulta_usada == "PERGUNTA REESCRITA AUTONOMA"  # recuperou pela reescrita
    assert _GerReescreve.historico_recebido == hist                   # gerou com o histórico
    assert _GerReescreve.reescreveu is True

    # Sem histórico: usa a pergunta original e NÃO reescreve (comportamento de turno único).
    _GerReescreve.reescreveu = False
    bot.responder("qual o limite de faltas?")
    assert _RecGrava.consulta_usada == "qual o limite de faltas?"
    assert _GerReescreve.reescreveu is False
    assert _GerReescreve.historico_recebido is None


def test_piso_score_recusa_antes_de_gerar():
    """O piso de score recusa fora-de-escopo (score baixo) SEM chamar o gerador; acima
    do piso, gera normalmente."""
    from rag.corpus import Chunk
    from rag.ia import ChatbotRAG
    from rag.ia import Gerador, RespostaGerada
    from rag.recuperacao import Recuperador, Resultado

    chunk = Chunk(id=1, doc_id="d", texto="conteúdo", inicio_char=0, fim_char=8, indice_no_doc=0)

    class _RecFixo(Recuperador):
        nome = "fixo"

        def __init__(self, score: float) -> None:
            self._score = score

        def buscar(self, consulta: str, k: int) -> list[Resultado]:
            return [Resultado(chunk_id=1, posicao=0, score=self._score)]

    class _GeradorEspiao(Gerador):
        chamado = False

        def gerar(self, pergunta, contextos, historico=None):
            self.__class__.chamado = True
            return RespostaGerada("resposta gerada", [1])

    # Abaixo do piso: recusa, contexto vazio, gerador NÃO chamado.
    _GeradorEspiao.chamado = False
    bot = ChatbotRAG(_RecFixo(-4.0), [chunk], _GeradorEspiao(), top_k_contexto=5, piso_score=-3.2)
    r = bot.responder("pergunta fora de escopo")
    assert "não encontrei" in r.texto.lower()
    assert r.trechos == []
    assert _GeradorEspiao.chamado is False

    # Acima do piso: gera normalmente.
    _GeradorEspiao.chamado = False
    bot_ok = ChatbotRAG(_RecFixo(1.5), [chunk], _GeradorEspiao(), top_k_contexto=5, piso_score=-3.2)
    r_ok = bot_ok.responder("pergunta in-scope")
    assert r_ok.texto == "resposta gerada"
    assert _GeradorEspiao.chamado is True
