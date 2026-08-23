"""Q3 — Chatbot RAG de saúde citando fonte (artefato de demonstração, protocolo §1/§6).

Usa a melhor recuperação medida (híbrida + reranker) sobre os 4 PCDTs e um gerador local
(Ollama, Llama 3.1 8B Q4; temperatura 0). Para cada pergunta: recupera o top-k, gera a
resposta em PT citando o trecho e mostra as fontes. Mede a latência de geração — se o 8B
ficar lento demais, rodar com ``--fallback`` (Llama 3.2 3B).

Uso:  python scripts/estudo/marco3_chatbot.py [--fallback]
"""
from __future__ import annotations

import sys
import time

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.generation.chatbot import ChatbotRAG
from rag.generation.generator import GeradorOllama
from rag.pipeline import construir_indice, montar_reranker, montar_recuperadores

PDFS = {
    "asma": "data/raw/pcdt/asma.pdf",
    "hipertensao": "data/raw/pcdt/hipertensao.pdf",
    "diabetes_t2": "data/raw/pcdt/diabetes_t2.pdf",
    "dor_cronica": "data/raw/pcdt/dor_cronica.pdf",
}

# Demonstração: perguntas leigo/técnico nos 4 domínios + 1 fora do corpus (guardrail).
PERGUNTAS_DEMO = [
    "Qual é o primeiro remédio para tratar o diabetes tipo 2?",
    "A partir de quanto tempo uma dor é considerada crônica?",
    "Quais são os sintomas respiratórios característicos da asma?",
    "A partir de que valor a pressão arterial já exige confirmação diagnóstica?",
    "O paracetamol ajuda na dor do joelho com artrose?",
    "Qual é o horário de funcionamento da biblioteca da faculdade?",  # fora do corpus
]


def main(argv: list[str]) -> int:
    usar_fallback = "--fallback" in argv
    cfg = carregar_config()

    corpora = {doc_id: carregar_pdf(caminho) for doc_id, caminho in PDFS.items()}
    indice = construir_indice(corpora, cfg)
    # Melhor recuperação: reranker sobre a híbrida.
    hibrida = montar_recuperadores(indice, cfg, incluir=["hibrida"])["hibrida"]
    recuperador = montar_reranker(hibrida, indice, cfg)

    gerador = GeradorOllama.de_config(cfg.geracao, usar_fallback=usar_fallback)
    chatbot = ChatbotRAG(recuperador, indice.chunks, gerador, cfg.geracao.top_k_contexto)
    doc_por_id = {c.id: c.doc_id for c in indice.chunks}

    print(f"Q3 — Chatbot RAG de saúde | modelo: {gerador.modelo} | "
          f"recuperação: {recuperador.nome} | top_k={cfg.geracao.top_k_contexto}\n")

    latencias = []
    for pergunta in PERGUNTAS_DEMO:
        inicio = time.perf_counter()
        r = chatbot.responder(pergunta)
        dt = time.perf_counter() - inicio
        latencias.append(dt)

        fontes_txt = ", ".join(sorted({doc_por_id[cid] for cid in r.resposta.fontes})) or "—"
        docs_recuperados = ", ".join(dict.fromkeys(c.doc_id for c in r.contextos))
        print(f"P: {pergunta}")
        print(f"R: {r.resposta.texto}")
        print(f"   fontes citadas: {fontes_txt} | trechos recuperados de: {docs_recuperados}")
        print(f"   [latência de geração: {dt:.1f}s]\n")

    media = sum(latencias) / len(latencias)
    print("=" * 60)
    print(f"Latência média de geração: {media:.1f}s (modelo {gerador.modelo})")
    if not usar_fallback and media > 15:
        print("Latência alta — considere rodar com --fallback (Llama 3.2 3B) para a demonstração.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
