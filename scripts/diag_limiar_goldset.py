"""Calibra o piso de score do reranker contra o gold-set institucional (50 perguntas).

Um piso só é seguro se as perguntas LEGÍTIMAS ficarem acima dele (senão reintroduz a
over-refusal que o perfil institucional resolveu). Mede a distribuição do score top-1 das
50 perguntas do gold-set e quantas cairiam abaixo de limiares candidatos.
Uso: python scripts/diag_limiar_goldset.py
"""
from __future__ import annotations

import json
import statistics

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.pipeline import construir_indice, montar_reranker, montar_recuperadores

GOLDSET = "data/goldsets/institucional.json"
LIMIARES = [-2.5, -3.0, -3.5]


def main() -> int:
    cfg = carregar_config()
    itens = json.load(open(GOLDSET, encoding="utf-8"))["itens"]
    indice = construir_indice({"manual": carregar_pdf("data/raw/manual_aluno_unip_2026.pdf")}, cfg)
    rer = montar_reranker(montar_recuperadores(indice, cfg, incluir=["hibrida"])["hibrida"], indice, cfg)

    scores = []
    for it in itens:
        res = rer.buscar(it["pergunta"], 1)
        s = res[0].score if res else float("-inf")
        scores.append((s, it["id"], it["pergunta"]))
    scores.sort()

    vals = [s for s, _, _ in scores]
    print(f"Gold-set: {len(vals)} perguntas legítimas")
    print(f"min={min(vals):+.2f}  mediana={statistics.median(vals):+.2f}  max={max(vals):+.2f}\n")
    print("5 menores scores (mais perto de serem barradas por engano):")
    for s, pid, q in scores[:5]:
        print(f"  {s:+7.2f}  {pid}  {q}")
    print()
    for lim in LIMIARES:
        abaixo = [(s, pid, q) for s, pid, q in scores if s < lim]
        print(f"limiar {lim:+.1f}: {len(abaixo)}/{len(vals)} perguntas legítimas seriam recusadas")
        for s, pid, q in abaixo:
            print(f"      {s:+7.2f}  {pid}  {q}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
