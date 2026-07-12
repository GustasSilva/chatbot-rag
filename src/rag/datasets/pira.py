"""Adaptador do Pirá 2.0 (C4AI/USP) para o benchmark de recuperação em português.

Fonte oficial: https://github.com/C4AI/Pira (licença CC BY 4.0). Paper: arXiv:2309.10945.

Tarefa de IR (protocolo, Marco 2): dada uma pergunta, recuperar o texto-fonte (abstract)
correto dentre todo o corpus. Mapeamento para o nosso framework:

- **corpus**: todos os abstracts em PT (``abstract_translated_pt``), deduplicados — cada
  abstract único é um documento.
- **queries**: as perguntas em PT (``question_pt_origin``) do split escolhido.
- **gold**: para cada pergunta, o documento é o seu próprio abstract (relevância em nível
  de documento — ver ``evaluation.goldset.construir_relevancia_por_documento``).
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..corpus.loaders import limpar_texto
from ..evaluation.goldset import ItemGold

csv.field_size_limit(1_000_000)  # abstracts são longos

ARQUIVOS_SPLIT = {"train": "train.csv", "validation": "validation.csv", "test": "test.csv"}
TODOS_SPLITS = ("train.csv", "validation.csv", "test.csv")


def _ler_linhas(caminho: Path):
    with open(caminho, encoding="utf-8") as arquivo:
        yield from csv.DictReader(arquivo)


def carregar_pira(dir_dados: str | Path, split: str = "test") -> tuple[dict[str, str], list[ItemGold]]:
    """Devolve ``(documentos, itens)`` do benchmark de recuperação em PT.

    O corpus é global (abstracts de TODOS os splits, deduplicados), como no paper; as
    queries vêm apenas do ``split`` pedido (padrão ``test``, para comparabilidade).
    """
    dir_dados = Path(dir_dados)
    if split not in ARQUIVOS_SPLIT:
        raise ValueError(f"split inválido: {split} (use {list(ARQUIVOS_SPLIT)})")

    # 1) Corpus: dedup dos abstracts em ordem de primeira aparição -> doc_id estável.
    doc_por_abstract: dict[str, str] = {}
    documentos: dict[str, str] = {}
    for nome in TODOS_SPLITS:
        for linha in _ler_linhas(dir_dados / nome):
            abstract = limpar_texto(linha.get("abstract_translated_pt") or "")
            if abstract and abstract not in doc_por_abstract:
                doc_id = f"pira-{len(doc_por_abstract):04d}"
                doc_por_abstract[abstract] = doc_id
                documentos[doc_id] = abstract

    # 2) Queries do split, ligadas ao doc do seu abstract.
    itens: list[ItemGold] = []
    ids_usados: set[str] = set()
    for linha in _ler_linhas(dir_dados / ARQUIVOS_SPLIT[split]):
        pergunta = limpar_texto(linha.get("question_pt_origin") or "")
        abstract = limpar_texto(linha.get("abstract_translated_pt") or "")
        if not pergunta or abstract not in doc_por_abstract:
            continue
        item_id = linha.get("id_qa") or f"q{len(itens)}"
        while item_id in ids_usados:  # garante unicidade (o Wilcoxon indexa por id)
            item_id += "_"
        ids_usados.add(item_id)
        itens.append(
            ItemGold(
                id=item_id,
                pergunta=pergunta,
                resposta=limpar_texto(linha.get("answer_pt_origin") or ""),
                trecho_fonte="",  # não usado: relevância é por documento
                doc_id=doc_por_abstract[abstract],
            )
        )
    return documentos, itens
