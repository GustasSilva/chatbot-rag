"""Testes estatísticos pareados para Q1/Q2.

Wilcoxon pareado sobre a métrica por pergunta, entre cada par de estratégias, com
correção de Holm para as comparações múltiplas (protocolo §5). Reporta direção,
tamanho de efeito (rank-biserial pareado) e p-valor — não só "deu significativo".

Cuidado central com o pareamento: os vetores comparados vêm alinhados pela mesma ordem
de perguntas (ver ``avaliacao.series_pareadas``). Nunca filtrar/descartar um lado sem o
outro — isso quebra os pares e invalida o teste.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy.stats import rankdata, wilcoxon


@dataclass(frozen=True)
class ComparacaoPar:
    estrategia_a: str
    estrategia_b: str
    n: int              # nº de pares (perguntas)
    n_efetivo: int      # pares com diferença != 0 (os que o Wilcoxon usa)
    mediana_a: float
    mediana_b: float
    estatistica: float
    p_bruto: float
    p_holm: float
    efeito: float       # rank-biserial pareado em [-1, 1]; > 0 => B supera A
    direcao: str        # descrição legível de quem venceu


def _wilcoxon_seguro(a: np.ndarray, b: np.ndarray) -> tuple[float, float, int]:
    """Wilcoxon pareado, tratando o caso degenerado de todas as diferenças nulas."""
    diferencas = b - a
    n_efetivo = int(np.count_nonzero(diferencas))
    if n_efetivo == 0:
        return float("nan"), 1.0, 0  # estratégias empatam em todas as perguntas
    estatistica, p = wilcoxon(a, b)  # zero_method='wilcox' (padrão) descarta empates
    return float(estatistica), float(p), n_efetivo


def efeito_rank_biserial(a: np.ndarray, b: np.ndarray) -> float:
    """Correlação rank-biserial pareada. > 0 indica que B tende a superar A."""
    diferencas = b - a
    diferencas = diferencas[diferencas != 0]
    if diferencas.size == 0:
        return 0.0
    ranks = rankdata(np.abs(diferencas))
    soma_positiva = ranks[diferencas > 0].sum()
    soma_negativa = ranks[diferencas < 0].sum()
    total = soma_positiva + soma_negativa
    return float((soma_positiva - soma_negativa) / total)


def holm(pvalores: list[float]) -> list[float]:
    """Correção de Holm-Bonferroni (step-down); devolve p ajustados na ordem original."""
    m = len(pvalores)
    ordem = sorted(range(m), key=lambda i: pvalores[i])
    ajustado = [0.0] * m
    acumulado_max = 0.0
    for rank, indice in enumerate(ordem):
        valor = (m - rank) * pvalores[indice]
        acumulado_max = max(acumulado_max, valor)
        ajustado[indice] = min(1.0, acumulado_max)
    return ajustado


def comparar_estrategias(vetores: dict[str, np.ndarray]) -> list[ComparacaoPar]:
    """Compara todas as estratégias par a par, com Holm sobre o conjunto de comparações."""
    tamanhos = {len(v) for v in vetores.values()}
    if len(tamanhos) != 1:
        raise ValueError("vetores de tamanhos diferentes — pareamento quebrado")

    pares = list(combinations(vetores.keys(), 2))
    parciais = []
    p_brutos: list[float] = []
    for nome_a, nome_b in pares:
        a, b = vetores[nome_a], vetores[nome_b]
        estatistica, p, n_efetivo = _wilcoxon_seguro(a, b)
        efeito = efeito_rank_biserial(a, b)
        parciais.append((nome_a, nome_b, a, b, estatistica, p, n_efetivo, efeito))
        p_brutos.append(p)

    p_ajustados = holm(p_brutos)

    comparacoes: list[ComparacaoPar] = []
    for (nome_a, nome_b, a, b, estatistica, p, n_efetivo, efeito), p_holm in zip(
        parciais, p_ajustados
    ):
        if efeito > 0:
            direcao = f"{nome_b} > {nome_a}"
        elif efeito < 0:
            direcao = f"{nome_a} > {nome_b}"
        else:
            direcao = "empate"
        comparacoes.append(
            ComparacaoPar(
                estrategia_a=nome_a,
                estrategia_b=nome_b,
                n=len(a),
                n_efetivo=n_efetivo,
                mediana_a=float(np.median(a)),
                mediana_b=float(np.median(b)),
                estatistica=estatistica,
                p_bruto=p,
                p_holm=p_holm,
                efeito=efeito,
                direcao=direcao,
            )
        )
    return comparacoes
