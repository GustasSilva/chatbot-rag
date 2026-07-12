"""Métricas de recuperação, calculadas por pergunta.

São objetivas e reprodutíveis: não dependem de julgar a resposta gerada pelo LLM
(protocolo §4). Ambas operam sobre a lista de ids de chunk ranqueada por uma estratégia
e o conjunto de chunks relevantes daquela pergunta.

- ``recall_em_k``:      o trecho correto está entre os k primeiros? (0/1 por pergunta)
- ``reciprocal_rank``:  1 / (posição do primeiro relevante); 0 se nenhum foi recuperado.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence


def recall_em_k(ids_ranqueados: Sequence[int], relevantes: Iterable[int], k: int) -> float:
    """1.0 se algum chunk relevante aparece nas ``k`` primeiras posições, senão 0.0.

    Com um único trecho-fonte por pergunta isto equivale a hit@k; com vários relevantes
    continua sendo "acertou ao menos um", que é o que importa para responder a pergunta.
    """
    if k <= 0:
        raise ValueError("k deve ser positivo")
    relevantes = set(relevantes)
    return 1.0 if any(cid in relevantes for cid in ids_ranqueados[:k]) else 0.0


def reciprocal_rank(ids_ranqueados: Sequence[int], relevantes: Iterable[int]) -> float:
    """1 / posição (1-based) do primeiro chunk relevante; 0.0 se nenhum aparece."""
    relevantes = set(relevantes)
    for posicao, cid in enumerate(ids_ranqueados, start=1):
        if cid in relevantes:
            return 1.0 / posicao
    return 0.0
