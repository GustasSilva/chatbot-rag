"""Marco 0 — Smoke test (protocolo §6).

Pipeline completo rodando em poucas perguntas TRIVIAIS sobre um texto curtíssimo.
PORTÃO: as 3 estratégias recuperam o trecho óbvio no topo-1. Como a geração está adiada
(Q3/Marco 3), o portão do LLM é substituído pela verificação de que o chunk-fonte certo é
recuperado — que é o que sustenta a geração.

As perguntas são deliberadamente triviais (o vocabulário da pergunta aparece na fonte):
num smoke test uma falha deve sinalizar bug de plumbing, não a fraqueza esperada de um
método. O gap léxico leigo×técnico é objeto de estudo do Marco 3, não daqui (§2, §7).

Usa o embedding REAL (e5); na primeira execução baixa o modelo (~440 MB).
"""
from __future__ import annotations

import sys

from rag.config import carregar_config
from rag.corpus.loaders import limpar_texto
from rag.evaluation.avaliacao import agregar, avaliar_recuperador
from rag.evaluation.goldset import ItemGold, construir_relevancia
from rag.pipeline import construir_indice, montar_recuperadores

# Texto curtíssimo e controlado: cada fato é um documento próprio, com vocabulário distinto.
DOCUMENTOS = {
    "fundacao": "O Instituto Aurora foi fundado em 1998 na cidade de Ouro Preto.",
    "biblioteca": "A biblioteca central abre de segunda a sexta, das oito às vinte e duas horas.",
    "faltas": "O limite de faltas permitido é de vinte e cinco por cento da carga horária.",
    "dependencia": "A matrícula em disciplina de dependência é feita pela secretaria on-line.",
    "laboratorio": "O laboratório de química fica no terceiro andar do bloco B.",
    "trancamento": "O prazo para trancamento de matrícula encerra no fim do primeiro bimestre.",
}
DOCUMENTOS = {doc_id: limpar_texto(texto) for doc_id, texto in DOCUMENTOS.items()}

# Perguntas triviais: cada palavra-chave da pergunta aparece na fonte esperada.
GOLD = [
    ItemGold("s1", "Em que ano o Instituto Aurora foi fundado?",
             "Em 1998.", "Instituto Aurora foi fundado em 1998", doc_id="fundacao"),
    ItemGold("s2", "Em que horas a biblioteca central abre?",
             "Das oito às vinte e duas horas.",
             "biblioteca central abre de segunda a sexta, das oito às vinte e duas horas",
             doc_id="biblioteca"),
    ItemGold("s3", "Qual é o limite de faltas permitido?",
             "Vinte e cinco por cento da carga horária.",
             "limite de faltas permitido é de vinte e cinco por cento", doc_id="faltas"),
    ItemGold("s4", "Em que andar fica o laboratório de química?",
             "No terceiro andar do bloco B.",
             "laboratório de química fica no terceiro andar", doc_id="laboratorio"),
    ItemGold("s5", "Qual é o prazo para trancamento de matrícula?",
             "Até o fim do primeiro bimestre.",
             "prazo para trancamento de matrícula encerra no fim do primeiro bimestre",
             doc_id="trancamento"),
]


def main() -> int:
    cfg = carregar_config()
    indice = construir_indice(DOCUMENTOS, cfg)
    relevancia = construir_relevancia(
        GOLD, indice.chunks, indice.textos_doc, cfg.recuperacao.limiar_relevancia
    )
    recuperadores = montar_recuperadores(indice, cfg)

    print(f"corpus: {len(indice.chunks)} chunks | perguntas: {len(GOLD)}\n")

    ks = cfg.recuperacao.ks
    todos_ok = True
    for nome, recuperador in recuperadores.items():
        linhas = avaliar_recuperador(recuperador, GOLD, relevancia, ks, cfg.recuperacao.top_k)
        resumo = agregar(linhas, ks)
        ok = resumo["recall@1"] == 1.0  # portão: trecho óbvio no topo-1 em todas as perguntas
        todos_ok &= ok
        marca = "OK " if ok else "FALHOU"
        print(f"[{marca}] {nome:9s} | recall@1={resumo['recall@1']:.2f} "
              f"recall@3={resumo['recall@3']:.2f} recall@5={resumo['recall@5']:.2f} "
              f"mrr={resumo['mrr']:.3f}")

    print()
    if todos_ok:
        print("PORTÃO MARCO 0: PASSOU — as 3 estratégias recuperam o trecho óbvio no topo-1.")
        return 0
    print("PORTÃO MARCO 0: FALHOU — há bug de chunking/embedding/BM25 antes de prosseguir.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
