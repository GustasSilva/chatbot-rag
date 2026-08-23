"""Marco 1 — Manual do Aluno (protocolo §6).

Roda as 3 estratégias (densa, esparsa/BM25, híbrida) sobre o gold-set do manual,
calcula Recall@k/MRR por pergunta e a primeira bateria Wilcoxon+Holm (Q1).

PORTÃO: ao menos uma estratégia atinge recall razoável (> 70% em k=5). Se nenhuma
atingir, há bug de chunking/embedding a resolver antes de prosseguir para o Pirá (Marco 2).
"""
from __future__ import annotations

import sys

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.evaluation.avaliacao import avaliar_recuperador, series_pareadas
from rag.evaluation.goldset import carregar_goldset, construir_relevancia
from rag.evaluation.relatorio import salvar_agregado, salvar_por_pergunta, salvar_testes
from rag.evaluation.stats import comparar_estrategias
from rag.pipeline import construir_indice, montar_recuperadores

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
CAMINHO_GOLD = "data/goldsets/manual_aluno.json"
DOC_ID = "manual"
LIMIAR_PORTAO = 0.70  # recall@5 mínimo em ao menos uma estratégia

# Métricas sobre as quais rodar o teste pareado (protocolo §5).
METRICAS_TESTE = [("recall", 3), ("recall", 5), ("mrr", None)]


def _rotulo(metrica: str, k: int | None) -> str:
    return f"recall@{k}" if metrica == "recall" else "mrr"


def main() -> int:
    cfg = carregar_config()
    corpus = carregar_pdf(CAMINHO_PDF)
    itens = carregar_goldset(CAMINHO_GOLD)
    ordem_ids = [item.id for item in itens]
    ks = cfg.recuperacao.ks

    print(f"Marco 1 — Manual do Aluno | corpus + gold-set de {len(itens)} perguntas")
    indice = construir_indice({DOC_ID: corpus}, cfg)
    relevancia = construir_relevancia(itens, indice.chunks, indice.textos_doc,
                                      cfg.recuperacao.limiar_relevancia)
    recuperadores = montar_recuperadores(indice, cfg)
    print(f"{len(indice.chunks)} chunks | estratégias: {', '.join(recuperadores)}\n")

    # ---- Avaliação por estratégia -------------------------------------------------
    linhas_por_estrategia = {
        nome: avaliar_recuperador(rec, itens, relevancia, ks, cfg.recuperacao.top_k)
        for nome, rec in recuperadores.items()
    }
    resumos = salvar_agregado(linhas_por_estrategia, ks, "outputs/marco1_agregado.csv")
    salvar_por_pergunta(linhas_por_estrategia, ks, "outputs/marco1_por_pergunta.csv")

    cab = "estratégia   " + "  ".join(f"R@{k}" for k in ks) + "   MRR"
    print(cab)
    print("-" * len(cab))
    for nome, resumo in resumos.items():
        cols = "  ".join(f"{resumo[f'recall@{k}']:.2f}" for k in ks)
        print(f"{nome:11s}  {cols}   {resumo['mrr']:.3f}")

    melhor_r5 = max(resumos[n]["recall@5"] for n in resumos)
    melhor_nome = max(resumos, key=lambda n: resumos[n]["recall@5"])
    r5_saturado = all(resumos[n]["recall@5"] >= 0.99 for n in resumos)

    # ---- Q1: testes pareados (Wilcoxon + Holm) ------------------------------------
    print("\nQ1 — comparação pareada (Wilcoxon + Holm):")
    comparacoes_por_metrica: dict[str, list] = {}
    for metrica, k in METRICAS_TESTE:
        rotulo = _rotulo(metrica, k)
        vetores = series_pareadas(linhas_por_estrategia, ordem_ids, metrica, k)
        comparacoes = comparar_estrategias(vetores)
        comparacoes_por_metrica[rotulo] = comparacoes
        print(f"\n  [{rotulo}]")
        for c in comparacoes:
            sig = "*" if c.p_holm < 0.05 else " "
            print(f"   {sig} {c.estrategia_a} vs {c.estrategia_b}: "
                  f"p_holm={c.p_holm:.3f} efeito={c.efeito:+.2f} "
                  f"({c.direcao if c.efeito != 0 else 'empate'})")
    salvar_testes(comparacoes_por_metrica, "outputs/marco1_testes.csv")

    # ---- Portão -------------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"Melhor recall@5: {melhor_nome} = {melhor_r5:.2f} (portão > {LIMIAR_PORTAO:.2f})")
    if melhor_r5 > LIMIAR_PORTAO:
        print("PORTÃO MARCO 1: PASSOU — recuperação razoável; seguir para o Marco 2 (Pirá).")
        if r5_saturado:
            print("NOTA: Recall@5 saturado (~100% nas 3 estratégias) — o corpus não "
                  "discrimina.\n      Marco 1 valida o ENCANAMENTO, não responde Q1; a "
                  "discriminação vem no Marco 2.")
        print("Saídas em outputs/marco1_*.csv")
        return 0
    print("PORTÃO MARCO 1: FALHOU — investigar chunking/embedding/BM25 antes de prosseguir.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
