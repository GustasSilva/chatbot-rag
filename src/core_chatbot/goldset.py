"""Gold-set: perguntas com resposta e trecho-fonte conhecidos, usado pelas medições.

Cada item guarda o ``trecho_fonte`` como subcadeia EXATA do corpus limpo (``corpus.limpar_texto``).
Os chunks relevantes de uma pergunta saem da geometria: um chunk conta se a interseção dos seus
offsets com os do trecho-fonte cobre ao menos ``limiar`` do trecho. Assim a fronteira do
chunking não atrapalha, porque com sobreposição um mesmo trecho pode cair em dois chunks.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .corpus import Chunk


class GoldSetError(ValueError):
    """Gold-set inconsistente com o corpus: o portão de sanidade das medições."""


@dataclass(frozen=True)
class ItemGold:
    id: str
    pergunta: str
    resposta: str
    trecho_fonte: str
    tipo: str | None = None
    doc_id: str = "doc"


def carregar_goldset(caminho: str | Path) -> list[ItemGold]:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return [ItemGold(**item) for item in dados["itens"]]


def salvar_goldset(itens: list[ItemGold], caminho: str | Path, corpus: str) -> None:
    payload = {"corpus": corpus, "itens": [asdict(i) for i in itens]}
    Path(caminho).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _ocorrencias(texto_doc: str, trecho: str) -> list[tuple[int, int]]:
    """Todas as ocorrências (início, fim) de ``trecho`` em ``texto_doc``."""
    ocorrencias: list[tuple[int, int]] = []
    inicio = texto_doc.find(trecho)
    while inicio != -1:
        ocorrencias.append((inicio, inicio + len(trecho)))
        inicio = texto_doc.find(trecho, inicio + 1)
    return ocorrencias


def resolver_relevancia(
    item: ItemGold,
    chunks: list[Chunk],
    textos_doc: dict[str, str],
    limiar: float,
) -> set[int]:
    """Ids dos chunks que contêm o trecho-fonte do item."""
    texto_doc = textos_doc.get(item.doc_id)
    if texto_doc is None:
        raise GoldSetError(f"item {item.id}: doc_id '{item.doc_id}' não existe no corpus")

    ocorrencias = _ocorrencias(texto_doc, item.trecho_fonte)
    if not ocorrencias:
        raise GoldSetError(
            f"item {item.id}: trecho-fonte não encontrado no doc '{item.doc_id}'. "
            "O trecho precisa ser uma subcadeia EXATA do corpus limpo."
        )

    relevantes: set[int] = set()
    for inicio, fim in ocorrencias:
        tamanho = fim - inicio
        for chunk in chunks:
            if chunk.doc_id != item.doc_id:
                continue
            intersecao = max(0, min(fim, chunk.fim_char) - max(inicio, chunk.inicio_char))
            if tamanho > 0 and intersecao / tamanho >= limiar:
                relevantes.add(chunk.id)
    return relevantes


def construir_relevancia(
    itens: list[ItemGold],
    chunks: list[Chunk],
    textos_doc: dict[str, str],
    limiar: float,
) -> dict[str, set[int]]:
    """Mapa item -> chunks relevantes, falhando alto se algum item não casar com nenhum chunk."""
    relevancia: dict[str, set[int]] = {}
    for item in itens:
        relevantes = resolver_relevancia(item, chunks, textos_doc, limiar)
        if not relevantes:
            raise GoldSetError(
                f"item {item.id}: trecho localizado, mas nenhum chunk atingiu o limiar "
                f"de relevância ({limiar}). Revise o trecho-fonte ou o limiar."
            )
        relevancia[item.id] = relevantes
    return relevancia
