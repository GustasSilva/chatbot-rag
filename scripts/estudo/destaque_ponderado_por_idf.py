# -*- coding: utf-8 -*-
"""O destaque melhora se os termos forem ponderados por IDF?

Hoje o criterio conta sobreposicao bruta, entao "de", "em" e "a" pesam o mesmo que
"frequencia". Compara quatro criterios sobre as perguntas que a gramatica reconhece,
com a recuperacao do nucleo (BM25 puro, como ficou apos a separacao).
"""
import re
import sys

sys.path.insert(0, "src")

from rag.compilador.base_conhecimento import BaseConhecimento, _FIM_DE_FRASE
from rag.compilador.intencoes import GRAMATICA_MANUAL, LEXICO_MANUAL, SEMANTICA_MANUAL
from rag.compilador.lexico import AnalisadorLexico
from rag.compilador.sintatico import AnalisadorSintatico
from rag.config import Config
from rag.goldset import carregar_goldset
from rag.pipeline import indexar_manual, montar_esparsa
from rag.recuperacao import tokenizar

cfg = Config()
indice = indexar_manual(cfg)
bm25 = montar_esparsa(indice, cfg)
idf = bm25._idf

lex = AnalisadorLexico(LEXICO_MANUAL)
sin = AnalisadorSintatico(GRAMATICA_MANUAL)
base = BaseConhecimento(bm25, indice.chunks, cfg.top_k_nucleo)
itens = carregar_goldset("data/goldsets/institucional.json")


def frases(texto):
    return [f for f in _FIM_DE_FRASE.split(texto) if f.strip()]


def bruto(fs, termos):
    return max(fs, key=lambda f: len(termos & set(tokenizar(f)))).strip()


def por_idf(fs, termos):
    def peso(f):
        return sum(idf.get(t, 0.0) for t in termos & set(tokenizar(f)))
    return max(fs, key=peso).strip()


def idf_normalizado(fs, termos):
    """IDF dividido pela raiz do tamanho da frase, para nao premiar frase longa."""
    def peso(f):
        toks = set(tokenizar(f))
        soma = sum(idf.get(t, 0.0) for t in termos & toks)
        return soma / (len(toks) ** 0.5 or 1)
    return max(fs, key=peso).strip()


def cobertura_da_consulta(fs, termos):
    """Fracao dos termos DA CONSULTA que a frase cobre, ponderada por IDF."""
    total = sum(idf.get(t, 0.0) for t in termos) or 1.0
    def peso(f):
        return sum(idf.get(t, 0.0) for t in termos & set(tokenizar(f))) / total
    return max(fs, key=peso).strip()


CRITERIOS = [
    ("sobreposicao bruta (em uso)", bruto),
    ("ponderado por IDF", por_idf),
    ("IDF / raiz do tamanho", idf_normalizado),
    ("cobertura da consulta", cobertura_da_consulta),
]

casos = []
for it in itens:
    rec = sin.analisar(lex.analisar(it.pergunta))
    if rec is None:
        continue
    resposta = base.consultar(SEMANTICA_MANUAL.analisar(rec))
    if not resposta.trechos:
        continue
    casos.append((it, resposta.trechos[0].texto, resposta.consulta.texto))

print("Destaque sobre %d perguntas reconhecidas, recuperacao BM25\n" % len(casos))
for nome, criterio in CRITERIOS:
    acertos = 0
    for it, texto, consulta in casos:
        fs = frases(texto)
        if not fs:
            continue
        acertos += it.trecho_fonte in criterio(fs, set(tokenizar(consulta)))
    print("  %-32s %2d/%d" % (nome, acertos, len(casos)))
