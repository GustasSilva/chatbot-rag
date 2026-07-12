"""Chunking por tamanho fixo com sobreposição.

Parâmetro fixo neste protocolo (não é eixo de comparação — protocolo §3). O tamanho
é medido em "tokens" de espaço em branco, um tokenizador simples e determinístico
(não o subword do modelo), o que basta para janelar o texto de forma reprodutível.

Cada chunk guarda seus offsets de caractere no texto original, o que permite mapear
o trecho-fonte de uma pergunta do gold-set para o(s) chunk(s) relevante(s).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN = re.compile(r"\S+")


@dataclass(frozen=True)
class Chunk:
    """Um pedaço do corpus com rastreabilidade de posição."""

    id: int              # id global, único no índice
    doc_id: str          # documento de origem
    texto: str           # conteúdo do chunk
    inicio_char: int     # offset inicial no texto do documento
    fim_char: int        # offset final (exclusivo)
    indice_no_doc: int   # posição sequencial dentro do documento


def dividir_em_chunks(
    texto: str,
    doc_id: str,
    tamanho_tokens: int,
    sobreposicao_tokens: int,
    id_inicial: int = 0,
) -> list[Chunk]:
    """Janela deslizante de ``tamanho_tokens`` tokens com ``sobreposicao_tokens`` de overlap."""
    if sobreposicao_tokens >= tamanho_tokens:
        raise ValueError("sobreposicao_tokens deve ser menor que tamanho_tokens")

    spans = [(m.start(), m.end()) for m in _TOKEN.finditer(texto)]
    if not spans:
        return []

    passo = tamanho_tokens - sobreposicao_tokens
    chunks: list[Chunk] = []
    posicao = 0
    while posicao < len(spans):
        janela = spans[posicao : posicao + tamanho_tokens]
        inicio_char = janela[0][0]
        fim_char = janela[-1][1]
        chunks.append(
            Chunk(
                id=id_inicial + len(chunks),
                doc_id=doc_id,
                texto=texto[inicio_char:fim_char],
                inicio_char=inicio_char,
                fim_char=fim_char,
                indice_no_doc=len(chunks),
            )
        )
        if posicao + tamanho_tokens >= len(spans):
            break  # última janela já cobriu o fim do documento
        posicao += passo

    return chunks
