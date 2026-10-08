"""O Manual em texto: extração do PDF, normalização e divisão em trechos de 180 palavras.

A normalização vem antes da divisão e deixa o texto como uma cadeia contínua, o que permite
achar qualquer passagem pela posição. ``PALAVRA`` é o que conta como palavra na análise léxica
e na busca.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import Config

# Uma "palavra": letras e dígitos. O resto é separador e não entra. Compartilhada pela análise
# léxica e pelo BM25, que é o que mantém as duas de acordo sobre o que é uma palavra.
PALAVRA = re.compile(r"\w+", re.UNICODE)

_ESPACOS = re.compile(r"\s+")
_INVISIVEIS = re.compile("[\u00ad\u200b\u200c\u200d\ufeff]")
# "palavra-" + quebra de linha + "continuação" vira uma palavra só, quando a continuação
# começa em minúscula. Compostos legítimos quebrados por acaso ficam intactos.
_HIFEN_QUEBRA = re.compile("(?<=\\w)-\\n(?=[a-z\u00e0-\u00ff])")
_TOKEN = re.compile(r"\S+")


def sem_acentos(texto: str) -> str:
    """Deixa a letra base ("ausências" -> "ausencias"). Único ponto de dobra de acento."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def limpar_texto(texto: str) -> str:
    """Colapsa espaço em branco e apara as bordas: a normalização canônica do corpus."""
    return _ESPACOS.sub(" ", texto).strip()


def so_alfanumerico(texto: str) -> str:
    """Troca por espaço tudo que não é letra, dígito ou espaço, e colapsa o que sobrar.

    Difere de :data:`PALAVRA` num ponto: o sublinhado, que ``\\w`` aceita como letra, aqui
    separa palavras. Serve a quem compara a frase inteira com uma lista de frases conhecidas,
    e não a quem a quebra em símbolos.
    """
    return limpar_texto("".join(c if c.isalnum() or c.isspace() else " " for c in texto))


def normalizar_pdf(texto: str) -> str:
    """Corrige artefatos de extração de PDF antes do colapso de espaços."""
    texto = unicodedata.normalize("NFC", texto)
    return _HIFEN_QUEBRA.sub("", _INVISIVEIS.sub("", texto))


def carregar_pdf(caminho: str | Path, limpar: bool = True) -> str:
    """Extrai o texto de um PDF via PyMuPDF."""
    import fitz  # import local: só o corpus de PDF precisa do PyMuPDF

    documento = fitz.open(str(caminho))
    try:
        paginas = [documento[i].get_text() for i in range(documento.page_count)]
    finally:
        documento.close()
    texto = "\n".join(paginas)
    return limpar_texto(normalizar_pdf(texto)) if limpar else texto


@dataclass(frozen=True)
class Chunk:
    """Um pedaço do corpus, com a posição que o torna rastreável até o texto original."""

    id: int              # id global, único no índice
    doc_id: str
    texto: str
    inicio_char: int
    fim_char: int        # exclusivo
    indice_no_doc: int


def dividir_em_chunks(
    texto: str,
    doc_id: str,
    tamanho_tokens: int,
    sobreposicao_tokens: int,
    id_inicial: int = 0,
) -> list[Chunk]:
    """Janela deslizante de ``tamanho_tokens`` tokens, com ``sobreposicao_tokens`` de overlap.

    Token aqui é a sequência sem espaço: um tokenizador determinístico, que basta para janelar.
    """
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
        inicio_char, fim_char = janela[0][0], janela[-1][1]
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
            break  # a última janela já cobriu o fim do documento
        posicao += passo

    return chunks


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
    """Lê o Manual do Aluno no caminho da configuração e o indexa. É a etapa 1 do percurso."""
    return construir_indice({"manual": carregar_pdf(cfg.caminho_manual)}, cfg)
