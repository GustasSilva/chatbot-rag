"""Acurácia de resposta do assistente institucional (item 4 do plano).

Roda o pipeline completo (pergunta → busca → geração, perfil institucional) nas ~50
perguntas do gold-set e mede o que é OBJETIVO e automatizável:

- **recuperação**: o chunk-fonte gold está entre os trechos enviados ao LLM? (top-k)
- **citação**: a fonte citada pelo LLM inclui o chunk gold? (só quando respondeu)
- **recusa**: respondeu ou recusou?

A correção de conteúdo ("contém a info certa?") NÃO é decidida por LLM-juiz aqui (protocolo
§4): as respostas são salvas em outputs/institucional_respostas.txt para revisão manual, ao
lado da resposta-gabarito e do trecho-fonte. Assim os erros podem ser classificados em
recuperação vs geração vs citação, sem misturar os tipos.

Exige Ollama + o modelo. Uso: python scripts/institucional_acuracia.py
"""
from __future__ import annotations

import csv
import sys
import unicodedata

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.evaluation.goldset import carregar_goldset, construir_relevancia
from rag.generation.chatbot import ChatbotRAG
from rag.generation.generator import GeradorOllama
from rag.pipeline import construir_indice, montar_recuperador_produto

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
CAMINHO_GOLD = "data/goldsets/institucional.json"
DOC = "manual"


def _recusou(texto: str) -> bool:
    n = "".join(c for c in unicodedata.normalize("NFKD", texto.lower())
                if not unicodedata.combining(c))
    return "nao encontrei" in n


def main() -> int:
    cfg = carregar_config()
    corpus = carregar_pdf(CAMINHO_PDF)
    itens = carregar_goldset(CAMINHO_GOLD)

    indice = construir_indice({DOC: corpus}, cfg, calcular_densa=False)
    relevancia = construir_relevancia(itens, indice.chunks, indice.textos_doc,
                                      cfg.recuperacao.limiar_relevancia)
    rer = montar_recuperador_produto(indice, cfg)
    gerador = GeradorOllama.de_config(cfg.geracao, perfil="institucional")
    chatbot = ChatbotRAG(rer, indice.chunks, gerador, cfg.geracao.top_k_contexto,
                         piso_score=cfg.geracao.piso_score_reranker)

    print(f"Acurácia institucional | {len(itens)} perguntas | perfil={gerador.perfil} "
          f"| modelo={gerador.modelo}\n")

    linhas_csv = []
    revisao = []
    n_recusou = n_hit = n_cit_ok = n_respondeu = 0
    for item in itens:
        r = chatbot.responder(item.pergunta)
        recuperados = {c.id for c in r.contextos}
        gold = relevancia[item.id]
        hit = bool(recuperados & gold)
        recusou = _recusou(r.resposta.texto)
        cit_ok = bool(set(r.resposta.fontes) & gold)

        n_hit += hit
        n_recusou += recusou
        if not recusou:
            n_respondeu += 1
            n_cit_ok += cit_ok

        linhas_csv.append({
            "id": item.id, "pergunta": item.pergunta,
            "recuperacao_hit": int(hit), "recusou": int(recusou),
            "citacao_ok": "" if recusou else int(cit_ok),
            "fontes_citadas": " ".join(map(str, r.resposta.fontes)),
            "chunks_gold": " ".join(map(str, sorted(gold))),
            "resposta": r.resposta.texto,
        })
        revisao.append(
            f"[{item.id}] {'RECUSOU ' if recusou else ''}hit={int(hit)} cit_ok={int(cit_ok)}\n"
            f"  P: {item.pergunta}\n  Gerada:  {r.resposta.texto}\n"
            f"  Gabarito: {item.resposta}\n  Fonte:   «{item.trecho_fonte[:90]}»\n")

    with open("outputs/institucional_acuracia.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas_csv[0]))
        w.writeheader(); w.writerows(linhas_csv)
    with open("outputs/institucional_respostas.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(revisao))

    n = len(itens)
    print(f"recuperação (chunk gold no top-{cfg.geracao.top_k_contexto}): {n_hit}/{n} = {n_hit/n:.0%}")
    print(f"recusou: {n_recusou}/{n} = {n_recusou/n:.0%}  | respondeu: {n_respondeu}/{n}")
    if n_respondeu:
        print(f"citação certa (entre as respondidas): {n_cit_ok}/{n_respondeu} = {n_cit_ok/n_respondeu:.0%}")
    print("\nRespostas para revisão de conteúdo em outputs/institucional_respostas.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
