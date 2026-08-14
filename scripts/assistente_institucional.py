"""Assistente do Manual do Aluno — chat livre (item 6 do plano): o produto demonstrável.

REPL de input aberto. Quem responde é o **controlador** (`rag.nlu.dialogo`): o núcleo de
compilador entende a pergunta (léxico → gramática de intenções → parser → semântica) e responde
direto do Manual, **sem modelo de linguagem no caminho**; o que a gramática não reconhece cai no
**plano B**, a pilha validada cientificamente — recuperação **híbrida + reranker**, **piso de
score** (recusa fora-de-escopo antes do LLM) e gerador local (Ollama, temperatura 0) no
**perfil institucional** do guardrail. Cada resposta indica de onde veio. Não é um serviço
oficial — mostra um disclaimer no cabeçalho e cita a fonte (trecho do Manual).

Exige Ollama no ar + o modelo do config **para o plano B**; as intenções que o núcleo reconhece
respondem sem ele. Uso:
    python scripts/assistente_institucional.py
Encerra com 'sair'/'exit'/'quit', Ctrl-C ou fim da entrada (EOF). Também aceita perguntas
por pipe (ex.: echo "qual o limite de faltas?" | python scripts/assistente_institucional.py).
"""
from __future__ import annotations

import sys

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.generation.chatbot import ChatbotRAG
from rag.generation.fabrica import construir_gerador
from rag.nlu.base_conhecimento import BaseConhecimento
from rag.nlu.dialogo import Dialogo, Origem
from rag.pipeline import construir_indice, montar_recuperador_produto

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
SAIR = {"sair", "exit", "quit"}
RODAPE_ORIGEM = {
    Origem.NUCLEO: "(trecho do Manual, localizado pela gramatica de intencoes -- sem IA)",
    Origem.PLANO_B: "(redigida pelo assistente a partir dos trechos consultados)",
}
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
    indice = construir_indice({"manual": carregar_pdf(CAMINHO_PDF)}, cfg, calcular_densa=False)
    rer = montar_recuperador_produto(indice, cfg)
    gerador = construir_gerador(cfg.geracao, perfil="institucional")
    plano_b = ChatbotRAG(rer, indice.chunks, gerador, cfg.geracao.top_k_contexto,
                         piso_score=cfg.geracao.piso_score_reranker, saudar=True)
    dialogo = Dialogo.de_manual(BaseConhecimento(rer, indice.chunks), plano_b)

    print("\n" + "=" * 72)
    print("  Assistente do Manual do Aluno")
    print("  " + DISCLAIMER)
    print("=" * 72)
    print("Faca uma pergunta (ou 'sair' para encerrar).\n")

    historico: list[tuple[str, str]] = []  # turnos anteriores (contexto p/ follow-ups)
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

        resp = dialogo.responder(pergunta, historico=historico)
        historico = (historico + [(pergunta, resp.texto)])[-4:]  # últimos 4 turnos
        print(f"\nAssistente> {resp.texto}")
        recusa = "não encontrei essa informação" in resp.texto.strip().lower()
        # Sem trecho não houve consulta ao Manual (recusa do piso, saudação, não entendi):
        # nesses casos nem o rodapé de origem nem as fontes fazem sentido.
        if resp.trechos and not recusa:
            print(f"  {RODAPE_ORIGEM[resp.origem]}")
            citados = set(resp.fontes)
            print("\nFontes (trechos consultados; * = citado na resposta):")
            for n, chunk in enumerate(resp.trechos, start=1):
                marca = "*" if chunk.id in citados else " "
                print(f"  {marca}[{n}] {_preview(chunk.texto)}")
            print("  (confirme no Manual oficial antes de decidir algo importante)")
        print()

    print("Ate mais!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
