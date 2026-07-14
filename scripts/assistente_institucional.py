"""Assistente do Manual do Aluno — chat livre (item 6 do plano): o produto demonstrável.

REPL de input aberto sobre a pilha validada cientificamente: recuperação **híbrida +
reranker**, **piso de score** (recusa fora-de-escopo antes do LLM) e gerador local (Ollama,
temperatura 0) no **perfil institucional** do guardrail. Não é um serviço oficial — mostra um
disclaimer no cabeçalho e cita a fonte (trecho do Manual) de cada resposta.

Exige Ollama no ar + o modelo do config. Uso:
    python scripts/assistente_institucional.py
Encerra com 'sair'/'exit'/'quit', Ctrl-C ou fim da entrada (EOF). Também aceita perguntas
por pipe (ex.: echo "qual o limite de faltas?" | python scripts/assistente_institucional.py).
"""
from __future__ import annotations

import sys

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.generation.chatbot import ChatbotRAG
from rag.generation.generator import GeradorOllama
from rag.pipeline import construir_indice, montar_reranker, montar_recuperadores

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
SAIR = {"sair", "exit", "quit"}
DISCLAIMER = (
    "Assistente NAO-OFICIAL, baseado apenas no Manual do Aluno. Pode errar; confirme\n"
    "  informacoes importantes (prazos, valores, datas) na secretaria ou no Manual oficial."
)


def _preview(texto: str, n: int = 110) -> str:
    t = " ".join(texto.split())
    return t if len(t) <= n else t[:n].rstrip() + "..."


def main() -> int:
    cfg = carregar_config()
    print("Carregando indice e modelos (pode levar alguns segundos)...", flush=True)
    indice = construir_indice({"manual": carregar_pdf(CAMINHO_PDF)}, cfg)
    rer = montar_reranker(montar_recuperadores(indice, cfg, incluir=["hibrida"])["hibrida"], indice, cfg)
    gerador = GeradorOllama.de_config(cfg.geracao, perfil="institucional")
    chatbot = ChatbotRAG(rer, indice.chunks, gerador, cfg.geracao.top_k_contexto,
                         piso_score=cfg.geracao.piso_score_reranker)
    por_id = {c.id: c for c in indice.chunks}

    print("\n" + "=" * 72)
    print("  Assistente do Manual do Aluno")
    print("  " + DISCLAIMER)
    print("=" * 72)
    print("Faca uma pergunta (ou 'sair' para encerrar).\n")

    while True:
        try:
            pergunta = input("Voce> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not pergunta:
            continue
        if pergunta.lower() in SAIR:
            break

        resp = chatbot.responder(pergunta)
        print(f"\nAssistente> {resp.resposta.texto}")
        if resp.resposta.fontes:
            print("\nFontes (trechos do Manual):")
            for fid in resp.resposta.fontes:
                chunk = por_id.get(fid)
                if chunk:
                    print(f"  - {_preview(chunk.texto)}")
            print("  (confirme no Manual oficial antes de decidir algo importante)")
        print()

    print("Ate mais!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
