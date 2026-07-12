"""Utilidades de saída: serialização das métricas e comparações em CSV.

Sem pandas — ``csv`` da biblioteca padrão basta e mantém o núcleo leve.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .avaliacao import LinhaAvaliacao, agregar
from .stats import ComparacaoPar


def salvar_por_pergunta(
    linhas_por_estrategia: dict[str, list[LinhaAvaliacao]],
    ks: tuple[int, ...],
    caminho: str | Path,
) -> None:
    campos = ["pergunta_id", "estrategia", "rr"] + [f"recall@{k}" for k in ks]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        for estrategia, linhas in linhas_por_estrategia.items():
            for linha in linhas:
                registro = {"pergunta_id": linha.pergunta_id, "estrategia": estrategia,
                            "rr": round(linha.rr, 4)}
                registro.update({f"recall@{k}": linha.recall[k] for k in ks})
                escritor.writerow(registro)


def salvar_agregado(
    linhas_por_estrategia: dict[str, list[LinhaAvaliacao]],
    ks: tuple[int, ...],
    caminho: str | Path,
) -> dict[str, dict[str, float]]:
    resumos = {est: agregar(linhas, ks) for est, linhas in linhas_por_estrategia.items()}
    campos = ["estrategia", "n", "mrr"] + [f"recall@{k}" for k in ks]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        for estrategia, resumo in resumos.items():
            registro = {"estrategia": estrategia, "n": resumo["n"],
                        "mrr": round(resumo["mrr"], 4)}
            registro.update({f"recall@{k}": round(resumo[f"recall@{k}"], 4) for k in ks})
            escritor.writerow(registro)
    return resumos


def salvar_testes(
    comparacoes_por_metrica: dict[str, list[ComparacaoPar]],
    caminho: str | Path,
) -> None:
    campos = ["metrica", "estrategia_a", "estrategia_b", "n", "n_efetivo",
              "mediana_a", "mediana_b", "estatistica", "p_bruto", "p_holm",
              "efeito", "direcao"]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        for metrica, comparacoes in comparacoes_por_metrica.items():
            for c in comparacoes:
                escritor.writerow({
                    "metrica": metrica,
                    "estrategia_a": c.estrategia_a, "estrategia_b": c.estrategia_b,
                    "n": c.n, "n_efetivo": c.n_efetivo,
                    "mediana_a": round(c.mediana_a, 4), "mediana_b": round(c.mediana_b, 4),
                    "estatistica": round(c.estatistica, 4) if c.estatistica == c.estatistica else "",
                    "p_bruto": round(c.p_bruto, 5), "p_holm": round(c.p_holm, 5),
                    "efeito": round(c.efeito, 4), "direcao": c.direcao,
                })
