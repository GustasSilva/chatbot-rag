"""Marco 2 — Pirá 2.0 (protocolo §6).

Primeira resposta estatisticamente válida a Q1: agora as perguntas divergem entre as
estratégias e n é grande (test split), então o Wilcoxon+Holm tem poder de verdade —
diferente do Marco 1, que saturava.

Setup (fiel ao paper, arXiv:2309.10945): corpus = todos os abstracts PT únicos (cada um é
um documento); queries = split de test; gold = o abstract da pergunta (relevância por
documento). PORTÃO: o BM25 fica na faixa da literatura (o paper reporta BM25 > 90% para
k >= 6), sinalizando que a montagem do corpus/tokenização está correta.

Nota: o e5 trunca em ~512 subtokens; abstracts longos (mediana ~255 palavras) são cortados
no lado denso — limitação conhecida do embedding, registrada.
"""
from __future__ import annotations

import dataclasses
import sys

from rag.config import ConfigChunking, carregar_config
from rag.dados.pira import carregar_pira
from rag.avaliacao.avaliacao import avaliar_recuperador, series_pareadas
from rag.avaliacao.goldset import construir_relevancia_por_documento
from rag.avaliacao.relatorio import salvar_agregado, salvar_por_pergunta, salvar_testes
from rag.avaliacao.stats import comparar_estrategias
from rag.pipeline import construir_indice, montar_recuperadores

DIR_PIRA = "data/raw/pira"
SPLIT = "test"
LIMIAR_PORTAO_BM25 = 0.85  # recall@10 do BM25 esperado na faixa do paper (>90% p/ k>=6)
METRICAS_TESTE = [("recall", 5), ("mrr", None)]


def _rotulo(metrica: str, k: int | None) -> str:
    return f"recall@{k}" if metrica == "recall" else "mrr"


def main() -> int:
    cfg = carregar_config()
    # Cada abstract é UM documento (retrieval em nível de documento, como o benchmark).
    # Tamanho grande o bastante para nunca subdividir o maior abstract.
    cfg = dataclasses.replace(cfg, chunking=ConfigChunking(tamanho_tokens=2000, sobreposicao_tokens=0))

    documentos, itens = carregar_pira(DIR_PIRA, split=SPLIT)
    ordem_ids = [item.id for item in itens]
    ks = cfg.recuperacao.ks

    print(f"Marco 2 — Pirá 2.0 | corpus={len(documentos)} abstracts | "
          f"queries={len(itens)} (split={SPLIT})")
    indice = construir_indice(documentos, cfg)
    relevancia = construir_relevancia_por_documento(itens, indice.chunks)
    recuperadores = montar_recuperadores(indice, cfg)
    print(f"{len(indice.chunks)} chunks (1 por abstract) | "
          f"estratégias: {', '.join(recuperadores)}\n")

    linhas_por_estrategia = {
        nome: avaliar_recuperador(rec, itens, relevancia, ks, cfg.recuperacao.top_k)
        for nome, rec in recuperadores.items()
    }
    resumos = salvar_agregado(linhas_por_estrategia, ks, "outputs/marco2_agregado.csv")
    salvar_por_pergunta(linhas_por_estrategia, ks, "outputs/marco2_por_pergunta.csv")

    cab = "estratégia   " + "  ".join(f"R@{k}" for k in ks) + "   MRR"
    print(cab)
    print("-" * len(cab))
    for nome, resumo in resumos.items():
        cols = "  ".join(f"{resumo[f'recall@{k}']:.2f}" for k in ks)
        print(f"{nome:11s}  {cols}   {resumo['mrr']:.3f}")

    # ---- Q1: testes pareados (Wilcoxon + Holm), agora com poder estatístico ----------
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
                  f"p_holm={c.p_holm:.4f} efeito={c.efeito:+.2f} "
                  f"({c.direcao if c.efeito != 0 else 'empate'})")
    salvar_testes(comparacoes_por_metrica, "outputs/marco2_testes.csv")

    # ---- Portão de sanidade (BM25 na faixa da literatura) ----------------------------
    bm25_r10 = resumos["esparsa"]["recall@10"]
    print("\n" + "=" * 60)
    print(f"BM25 (esparsa) recall@10 = {bm25_r10:.2f} (portão > {LIMIAR_PORTAO_BM25:.2f}; "
          f"paper: BM25 > 0.90 para k>=6)")
    if bm25_r10 > LIMIAR_PORTAO_BM25:
        print("PORTÃO MARCO 2: PASSOU — BM25 na faixa da literatura; Q1 tem validade estatística.")
        print("Saídas em outputs/marco2_*.csv")
        return 0
    print("PORTÃO MARCO 2: FALHOU — BM25 fora da faixa; revisar corpus/tokenização.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
