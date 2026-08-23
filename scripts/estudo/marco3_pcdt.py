"""Marco 3 — Saúde (PCDT) + Reranker (protocolo §6).

Três análises:
1. **Q1 re-teste** — o padrão do Marco 2 (híbrida/esparsa > densa) se sustenta num corpus
   mais difícil, de linguagem clínica?
2. **Gap leigo×técnico** — o cerne do Marco 3: para cada estratégia, a recuperação piora
   quando a pergunta usa vocabulário leigo em vez do técnico? Teste pareado por fato
   (cada fato tem uma versão leigo e uma técnica apontando para o mesmo trecho).
3. **Q2 reranker** — o cross-encoder reordenando o top-k da híbrida melhora recall/MRR o
   suficiente para justificar a latência?

n é pequeno (24 perguntas; 12 pares) — aqui importam direção e tamanho de efeito mais que
significância, como o protocolo prevê para o corpus difícil.

Q3 (chatbot gerando resposta citando fonte) fica adiado — depende do backend do gerador.
"""
from __future__ import annotations

import sys

import numpy as np

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.evaluation.avaliacao import agregar, avaliar_recuperador, series_pareadas
from rag.evaluation.goldset import carregar_goldset, construir_relevancia
from rag.evaluation.relatorio import salvar_agregado, salvar_por_pergunta, salvar_testes
from rag.evaluation.stats import comparar_estrategias, efeito_rank_biserial, _wilcoxon_seguro
from rag.pipeline import construir_indice, montar_reranker, montar_recuperadores

PDFS = {
    "asma": "data/raw/pcdt/asma.pdf",
    "hipertensao": "data/raw/pcdt/hipertensao.pdf",
    "diabetes_t2": "data/raw/pcdt/diabetes_t2.pdf",
    "dor_cronica": "data/raw/pcdt/dor_cronica.pdf",
}
CAMINHO_GOLD = "data/goldsets/saude_pcdt.json"
METRICAS_TESTE = [("recall", 5), ("mrr", None)]


def _valor_recall5(linha) -> float:
    return linha.recall[5]


def _tabela(resumos: dict, ks) -> None:
    cab = "estratégia      " + "  ".join(f"R@{k}" for k in ks) + "   MRR"
    print(cab)
    print("-" * len(cab))
    for nome, resumo in resumos.items():
        cols = "  ".join(f"{resumo[f'recall@{k}']:.2f}" for k in ks)
        print(f"{nome:14s}  {cols}   {resumo['mrr']:.3f}")


def _breakdown_por_tipo(linhas, itens, ks) -> tuple[dict, dict]:
    tipo_por_id = {i.id: i.tipo for i in itens}
    leigo = [l for l in linhas if tipo_por_id[l.pergunta_id] == "leigo"]
    tecnico = [l for l in linhas if tipo_por_id[l.pergunta_id] == "tecnico"]
    return agregar(leigo, ks), agregar(tecnico, ks)


def _teste_leigo_vs_tecnico(linhas, valor_fn) -> tuple[float, float, int]:
    """Wilcoxon pareado por fato: métrica na versão leigo vs. técnica (mesmo fato)."""
    por_id = {l.pergunta_id: l for l in linhas}
    fatos = sorted({pid[:-2] for pid in por_id})  # remove sufixo _l / _t
    leigo = np.array([valor_fn(por_id[f + "_l"]) for f in fatos])
    tecnico = np.array([valor_fn(por_id[f + "_t"]) for f in fatos])
    _, p, n_ef = _wilcoxon_seguro(leigo, tecnico)
    efeito = efeito_rank_biserial(leigo, tecnico)  # >0 => técnico melhor que leigo
    return p, efeito, n_ef


def main() -> int:
    cfg = carregar_config()
    corpora = {doc_id: carregar_pdf(caminho) for doc_id, caminho in PDFS.items()}
    itens = carregar_goldset(CAMINHO_GOLD)
    ordem_ids = [i.id for i in itens]
    ks = cfg.recuperacao.ks

    print(f"Marco 3 — Saúde (PCDT) | {len(corpora)} protocolos | {len(itens)} perguntas")
    indice = construir_indice(corpora, cfg)
    relevancia = construir_relevancia(itens, indice.chunks, indice.textos_doc,
                                      cfg.recuperacao.limiar_relevancia)
    recuperadores = montar_recuperadores(indice, cfg)
    print(f"{len(indice.chunks)} chunks | estratégias: {', '.join(recuperadores)}\n")

    linhas_por_estrategia = {
        nome: avaliar_recuperador(rec, itens, relevancia, ks, cfg.recuperacao.top_k)
        for nome, rec in recuperadores.items()
    }
    resumos = salvar_agregado(linhas_por_estrategia, ks, "outputs/marco3_agregado.csv")
    salvar_por_pergunta(linhas_por_estrategia, ks, "outputs/marco3_por_pergunta.csv")

    print("== Q1 — geral ==")
    _tabela(resumos, ks)

    # ---- Q1: sustenta o padrão do Marco 2? ------------------------------------------
    print("\n== Q1 — comparação pareada (Wilcoxon + Holm) ==")
    comparacoes_por_metrica = {}
    for metrica, k in METRICAS_TESTE:
        rotulo = f"recall@{k}" if metrica == "recall" else "mrr"
        vetores = series_pareadas(linhas_por_estrategia, ordem_ids, metrica, k)
        comparacoes = comparar_estrategias(vetores)
        comparacoes_por_metrica[rotulo] = comparacoes
        print(f"  [{rotulo}]")
        for c in comparacoes:
            sig = "*" if c.p_holm < 0.05 else " "
            print(f"   {sig} {c.estrategia_a} vs {c.estrategia_b}: "
                  f"efeito={c.efeito:+.2f} p_holm={c.p_holm:.3f} "
                  f"({c.direcao if c.efeito else 'empate'})")
    salvar_testes(comparacoes_por_metrica, "outputs/marco3_testes_q1.csv")

    # ---- Gap leigo×técnico ----------------------------------------------------------
    print("\n== Gap leigo×técnico (por estratégia) ==")
    print("estratégia      R@5 leigo  R@5 técnico   MRR leigo  MRR técnico   p(R@5)  efeito")
    for nome, linhas in linhas_por_estrategia.items():
        ag_l, ag_t = _breakdown_por_tipo(linhas, itens, ks)
        p, efeito, _ = _teste_leigo_vs_tecnico(linhas, _valor_recall5)
        print(f"{nome:14s}  {ag_l['recall@5']:.2f}       {ag_t['recall@5']:.2f}"
              f"         {ag_l['mrr']:.2f}       {ag_t['mrr']:.2f}"
              f"        {p:.3f}   {efeito:+.2f}")
    print("  (efeito > 0 => técnico recupera melhor que leigo, no mesmo fato)")

    # ---- Q2: reranker sobre a híbrida ------------------------------------------------
    print("\n== Q2 — reranker (cross-encoder) sobre a híbrida ==")
    reranker = montar_reranker(recuperadores["hibrida"], indice, cfg)
    linhas_rerank = avaliar_recuperador(reranker, itens, relevancia, ks, cfg.recuperacao.top_k)
    base = {"hibrida": linhas_por_estrategia["hibrida"], "reranker": linhas_rerank}
    resumo_rr = salvar_agregado(base, ks, "outputs/marco3_q2_reranker.csv")
    _tabela(resumo_rr, ks)
    comp_rr = {}
    for metrica, k in METRICAS_TESTE:
        rotulo = f"recall@{k}" if metrica == "recall" else "mrr"
        vetores = series_pareadas(base, ordem_ids, metrica, k)
        comp_rr[rotulo] = comparar_estrategias(vetores)
        c = comp_rr[rotulo][0]
        print(f"  [{rotulo}] efeito={c.efeito:+.2f} p={c.p_bruto:.3f} ({c.direcao if c.efeito else 'empate'})")

    print("\n" + "=" * 60)
    print("MARCO 3: concluído (Q1 re-teste + gap leigo×técnico + Q2). "
          "Q3/gerador adiado. Saídas em outputs/marco3_*.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
