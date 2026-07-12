"""Carregamento de documentos e normalização de texto.

A normalização é canônica e feita ANTES do chunking: colapsa qualquer sequência de
espaços em branco (incl. quebras de linha) num único espaço. Isso deixa o texto do
corpus como uma string contínua, o que permite ao gold-set guardar o trecho-fonte
como um substring exato do corpus (ver ``evaluation.goldset``).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

_ESPACOS = re.compile(r"\s+")
# Caracteres invisíveis que atrapalham tokenização e casamento do trecho-fonte.
_INVISIVEIS = re.compile(r"[­​‌‍﻿]")
# Hifenização de quebra de linha: "palavra-\ncontinuação" -> "palavracontinuação".
# Só junta quando a continuação começa em minúscula (continuação de palavra), o que
# evita colar compostos legítimos quebrados por acaso (ex.: nomes próprios, siglas).
_HIFEN_QUEBRA = re.compile(r"(?<=\w)-\n(?=[a-zà-ÿ])")


def limpar_texto(texto: str) -> str:
    """Colapsa espaços em branco e remove bordas — normalização canônica do corpus."""
    return _ESPACOS.sub(" ", texto).strip()


def normalizar_pdf(texto: str) -> str:
    """Corrige artefatos de extração de PDF antes do colapso de espaços.

    Remove hífens suaves/zero-width, refaz palavras hifenizadas na quebra de linha e
    normaliza em NFC — passos que melhoram sobretudo o BM25 (que casa token a token).
    """
    texto = unicodedata.normalize("NFC", texto)
    texto = _INVISIVEIS.sub("", texto)
    texto = _HIFEN_QUEBRA.sub("", texto)
    return texto


def carregar_pdf(caminho: str | Path, limpar: bool = True) -> str:
    """Extrai o texto de um PDF via PyMuPDF (bom com encoding PT-BR)."""
    import fitz  # importado localmente: só o corpus de PDF precisa de PyMuPDF

    documento = fitz.open(str(caminho))
    try:
        paginas = [documento[i].get_text() for i in range(documento.page_count)]
    finally:
        documento.close()
    texto = "\n".join(paginas)
    if not limpar:
        return texto
    return limpar_texto(normalizar_pdf(texto))


def carregar_texto(caminho: str | Path, limpar: bool = True) -> str:
    """Carrega um arquivo ``.txt`` (UTF-8)."""
    conteudo = Path(caminho).read_text(encoding="utf-8")
    return limpar_texto(conteudo) if limpar else conteudo
