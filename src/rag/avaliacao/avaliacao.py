"""Orquestração da avaliação: roda um recuperador sobre o gold-set e coleta métricas.

Produz uma métrica POR PERGUNTA (não só a média), porque é disso que os testes
estatísticos pareados precisam — o Wilcoxon compara as estratégias pergunta a pergunta.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..recuperacao.base import Recuperador
from .goldset import ItemGold
from .metrics import recall_em_k, reciprocal_rank


@dataclass(frozen=True)
class LinhaAvaliacao:
    pergunta_id: str
    estrategia: str
    rr: float
    recall: dict[int, float]  # k -> 0/1


def avaliar_recuperador(
    recuperador: Recuperador,
    itens: list[ItemGold],
    relevancia: dict[str, set[int]],
    ks: tuple[int, ...],
    profundidade: int,
) -> list[LinhaAvaliacao]:
    """Roda ``recuperador`` em cada pergunta e devolve uma linha de métricas por pergunta."""
    profundidade = max(profundidade, max(ks))
    linhas: list[LinhaAvaliacao] = []
    for item in itens:
        resultados = recuperador.buscar(item.pergunta, profundidade)
        ids = [r.chunk_id for r in resultados]
        relevantes = relevancia[item.id]
        linhas.append(
            LinhaAvaliacao(
                pergunta_id=item.id,
                estrategia=recuperador.nome,
                rr=reciprocal_rank(ids, relevantes),
                recall={k: recall_em_k(ids, relevantes, k) for k in ks},
            )
        )
    return linhas


def _valor(linha: LinhaAvaliacao, metrica: str, k: int | None) -> float:
    if metrica == "mrr":
        return linha.rr
    if metrica == "recall":
        if k is None:
            raise ValueError("recall exige um k")
        return linha.recall[k]
    raise ValueError(f"métrica desconhecida: {metrica}")


def agregar(linhas: list[LinhaAvaliacao], ks: tuple[int, ...]) -> dict[str, float]:
    """Média das métricas (MRR e Recall@k) sobre todas as perguntas de uma estratégia."""
    n = len(linhas)
    if n == 0:
        raise ValueError("sem linhas para agregar")
    resumo = {"n": n, "mrr": float(np.mean([l.rr for l in linhas]))}
    for k in ks:
        resumo[f"recall@{k}"] = float(np.mean([l.recall[k] for l in linhas]))
    return resumo


def series_pareadas(
    linhas_por_estrategia: dict[str, list[LinhaAvaliacao]],
    ordem_ids: list[str],
    metrica: str,
    k: int | None = None,
) -> dict[str, np.ndarray]:
    """Vetores de métrica alinhados pela MESMA ordem de perguntas entre as estratégias.

    O alinhamento explícito por ``ordem_ids`` é deliberado: garante que os pares do
    Wilcoxon vêm exatamente das mesmas perguntas (o erro clássico de desalinhar pares
    por um filtro aplicado a só um dos lados — corrigido de projetos anteriores).
    """
    vetores: dict[str, np.ndarray] = {}
    for estrategia, linhas in linhas_por_estrategia.items():
        por_id = {l.pergunta_id: l for l in linhas}
        faltando = set(ordem_ids) - set(por_id)
        if faltando:
            raise ValueError(f"estratégia '{estrategia}' sem perguntas: {sorted(faltando)}")
        vetores[estrategia] = np.array(
            [_valor(por_id[pid], metrica, k) for pid in ordem_ids], dtype=float
        )
    return vetores
