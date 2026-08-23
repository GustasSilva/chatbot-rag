"""Experimento — fusão para o reranker: RRF vs UNIÃO intercalada.

Testa a hipótese do "miss do diabetes" (relatório/memória): a fusão RRF pode DILUIR um
acerto forte de um só recuperador e deixá-lo fora do top-k que alimenta o reranker. A
alternativa é alimentar o reranker com a UNIÃO intercalada de densa+esparsa (sem média de
ranks). Os DOIS braços dão ao reranker a mesma verba de candidatos (`reranker.top_k_entrada`),
isolando o efeito da FUSÃO, não do tamanho do pool.

Braços (2º estágio): `reranker[hibrida-RRF]` vs `reranker[uniao]`.
Métrica: Recall@k e MRR por pergunta; Wilcoxon pareado + tamanho de efeito (rank-biserial).
Corpora: saúde (PCDT, onde o miss foi achado) e Pirá 2.0 (poder estatístico, n=227).

Exige os modelos (e5 + cross-encoder) e os corpora em data/raw/. Uso:
    python scripts/estudo/exp_fusao_reranker.py
"""
from __future__ import annotations

import dataclasses
import sys

from rag.config import ConfigChunking, carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.dados.pira import carregar_pira
from rag.avaliacao.avaliacao import avaliar_recuperador, series_pareadas
from rag.avaliacao.goldset import (
    carregar_goldset,
    construir_relevancia,
    construir_relevancia_por_documento,
)
from rag.avaliacao.relatorio import salvar_agregado
from rag.avaliacao.stats import comparar_estrategias
from rag.pipeline import construir_indice, montar_reranker, montar_recuperadores
from rag.recuperacao.uniao import RecuperadorUniao

PDFS_SAUDE = {
    "asma": "data/raw/pcdt/asma.pdf",
    "hipertensao": "data/raw/pcdt/hipertensao.pdf",
    "diabetes_t2": "data/raw/pcdt/diabetes_t2.pdf",
    "dor_cronica": "data/raw/pcdt/dor_cronica.pdf",
}
GOLD_SAUDE = "data/goldsets/saude_pcdt.json"
DIR_PIRA = "data/raw/pira"
METRICAS_TESTE = [("recall", 5), ("mrr", None)]


def comparar_fusao(nome_corpus, slug, indice, itens, relevancia, cfg) -> None:
    ks = cfg.recuperacao.ks
    ordem_ids = [i.id for i in itens]
    recs = montar_recuperadores(indice, cfg)
    uniao = RecuperadorUniao(recs["densa"], recs["esparsa"])
    rr_rrf = montar_reranker(recs["hibrida"], indice, cfg)
    rr_uniao = montar_reranker(uniao, indice, cfg)

    def avaliar(rec):
        return avaliar_recuperador(rec, itens, relevancia, ks, cfg.recuperacao.top_k)

    linhas = {
        "hibrida_rrf": avaliar(recs["hibrida"]),   # 1º estágio (referência)
        "rerank_rrf": avaliar(rr_rrf),             # braço A: reranker sobre a RRF
        "rerank_uniao": avaliar(rr_uniao),         # braço B: reranker sobre a união
    }

    print(f"\n{'=' * 64}\n== {nome_corpus} | n={len(itens)} | {len(indice.chunks)} chunks ==")
    resumos = salvar_agregado(linhas, ks, f"outputs/exp_fusao_{slug}.csv")
    cab = f"{'estrategia':16s}" + "  ".join(f"R@{k}" for k in ks) + "   MRR"
    print(cab)
    print("-" * len(cab))
    for nome, resumo in resumos.items():
        cols = "  ".join(f"{resumo[f'recall@{k}']:.2f}" for k in ks)
        print(f"{nome:16s}{cols}   {resumo['mrr']:.3f}")

    # Comparação pareada do que importa: os dois rerankers.
    duo = {"rerank_rrf": linhas["rerank_rrf"], "rerank_uniao": linhas["rerank_uniao"]}
    print("  Wilcoxon pareado (rerank_rrf vs rerank_uniao):")
    for metrica, k in METRICAS_TESTE:
        rotulo = f"recall@{k}" if metrica == "recall" else "mrr"
        vetores = series_pareadas(duo, ordem_ids, metrica, k)
        c = comparar_estrategias(vetores)[0]
        direcao = c.direcao if c.efeito else "empate"
        print(f"    [{rotulo:9s}] efeito={c.efeito:+.2f}  p={c.p_bruto:.3f}  ({direcao})")

    # Ganhos/perdas por pergunta em recall@5: onde a união recupera o que a RRF perdeu.
    r_rrf = {l.pergunta_id: l.recall[5] for l in linhas["rerank_rrf"]}
    r_uni = {l.pergunta_id: l.recall[5] for l in linhas["rerank_uniao"]}
    ganhou = [p for p in ordem_ids if r_uni[p] > r_rrf[p]]
    perdeu = [p for p in ordem_ids if r_uni[p] < r_rrf[p]]
    print(f"  recall@5 por pergunta — uniao GANHA {len(ganhou)}, PERDE {len(perdeu)} (vs RRF)")
    if ganhou:
        print(f"    ganhou: {ganhou}")
    if perdeu:
        print(f"    perdeu: {perdeu}")


def main() -> int:
    cfg = carregar_config()

    # ---- Saúde (PCDT): chunking normal, relevância por substring do trecho-fonte -------
    corpora = {doc: carregar_pdf(p) for doc, p in PDFS_SAUDE.items()}
    itens = carregar_goldset(GOLD_SAUDE)
    indice = construir_indice(corpora, cfg)
    relevancia = construir_relevancia(itens, indice.chunks, indice.textos_doc,
                                      cfg.recuperacao.limiar_relevancia)
    comparar_fusao("SAÚDE (PCDT)", "saude", indice, itens, relevancia, cfg)

    # ---- Pirá 2.0: 1 abstract = 1 documento, relevância por documento ------------------
    cfg_pira = dataclasses.replace(
        cfg, chunking=ConfigChunking(tamanho_tokens=2000, sobreposicao_tokens=0))
    documentos, itens_pira = carregar_pira(DIR_PIRA, split="test")
    indice_pira = construir_indice(documentos, cfg_pira)
    relevancia_pira = construir_relevancia_por_documento(itens_pira, indice_pira.chunks)
    comparar_fusao("PIRÁ 2.0", "pira", indice_pira, itens_pira, relevancia_pira, cfg_pira)

    print(f"\n{'=' * 64}\nExperimento concluído. Saídas em outputs/exp_fusao_*.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
