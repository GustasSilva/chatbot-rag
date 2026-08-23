"""Diagnóstico: o score top-1 do reranker separa perguntas in-scope de fora-de-escopo?

Se sim, um piso de score no reranker seria um guardrail robusto (recusar antes de chamar o
LLM quando o melhor candidato tem score baixo). Verificação antes de propor a mitigação do
vazamento da asma (item 5). Uso: python scripts/estudo/diag_score_reranker.py
"""
from __future__ import annotations

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.pipeline import construir_indice, montar_reranker, montar_recuperadores

FORA = [
    "Qual o tratamento para a asma?",
    "Onde fica o campus de Manaus?",
    "Qual é o meu RA?",
    "Quais os sintomas da dengue?",
    "Qual é a capital da Austrália?",
    "Me conta uma piada.",
]
DENTRO = [
    "Como faço para trancar a matrícula?",
    "Qual o limite de faltas que eu posso ter?",
    "Como funciona o aproveitamento de estudos?",
    "De quem é a responsabilidade de controlar as faltas?",
    "Como peço revisão de uma prova?",
]


def main() -> int:
    cfg = carregar_config()
    indice = construir_indice({"manual": carregar_pdf("data/raw/manual_aluno_unip_2026.pdf")}, cfg)
    rer = montar_reranker(montar_recuperadores(indice, cfg, incluir=["hibrida"])["hibrida"], indice, cfg)

    def top1(q: str) -> float:
        res = rer.buscar(q, 1)
        return res[0].score if res else float("-inf")

    print("FORA DE ESCOPO (esperado: score baixo)")
    for q in FORA:
        print(f"  {top1(q):+7.2f}  {q}")
    print("\nIN-SCOPE (esperado: score alto)")
    for q in DENTRO:
        print(f"  {top1(q):+7.2f}  {q}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
