"""Gold-set: perguntas com resposta e trecho-fonte conhecidos.

Cada item guarda o ``trecho_fonte`` como texto — um substring EXATO do corpus limpo
(ver ``corpus.loaders.limpar_texto``). Na avaliação, o conjunto de chunks relevantes de
uma pergunta é resolvido geometricamente: um chunk é relevante se a interseção de seus
offsets de caractere com os do trecho-fonte cobre pelo menos ``limiar`` do trecho. Isso
é robusto à fronteira do chunking (com sobreposição, um trecho pode cair em 2 chunks).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from ..corpus.chunking import Chunk


class GoldSetError(ValueError):
    """Gold-set inconsistente com o corpus (portão de sanidade)."""


@dataclass(frozen=True)
class ItemGold:
    id: str
    pergunta: str
    resposta: str
    trecho_fonte: str
    tipo: str | None = None   # 'leigo' | 'tecnico' | None (usado no corpus de saúde do estudo)
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
    """Ids dos chunks relevantes para ``item`` — os que contêm o trecho-fonte."""
    texto_doc = textos_doc.get(item.doc_id)
    if texto_doc is None:
        raise GoldSetError(f"item {item.id}: doc_id '{item.doc_id}' não existe no corpus")

    ocorrencias = _ocorrencias(texto_doc, item.trecho_fonte)
    if not ocorrencias:
        raise GoldSetError(
            f"item {item.id}: trecho-fonte não encontrado no doc '{item.doc_id}'. "
            "O trecho precisa ser um substring EXATO do corpus limpo."
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


def construir_relevancia_por_documento(
    itens: list[ItemGold],
    chunks: list[Chunk],
) -> dict[str, set[int]]:
    """Relevância em nível de DOCUMENTO: o gold é o documento inteiro do item.

    Usado em benchmarks como o Pirá, onde a tarefa é recuperar o texto-fonte correto
    (não localizar um trecho dentro dele): todos os chunks do ``doc_id`` do item contam
    como relevantes. Não depende de ``trecho_fonte``.
    """
    chunks_por_doc: dict[str, set[int]] = {}
    for chunk in chunks:
        chunks_por_doc.setdefault(chunk.doc_id, set()).add(chunk.id)

    relevancia: dict[str, set[int]] = {}
    for item in itens:
        relevantes = chunks_por_doc.get(item.doc_id)
        if not relevantes:
            raise GoldSetError(
                f"item {item.id}: doc_id '{item.doc_id}' não tem chunks no índice"
            )
        relevancia[item.id] = set(relevantes)
    return relevancia


def construir_relevancia(
    itens: list[ItemGold],
    chunks: list[Chunk],
    textos_doc: dict[str, str],
    limiar: float,
) -> dict[str, set[int]]:
    """Mapa item_id -> conjunto de chunks relevantes, validando o gold-set inteiro.

    Falha alto (``GoldSetError``) se algum item não localizar o trecho ou não casar com
    nenhum chunk — é o portão que pega bug de chunking/normalização antes de medir nada.
    """
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
