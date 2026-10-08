"""Assistente do Manual do Aluno — chat livre (item 6 do plano): o produto demonstrável.

REPL de input aberto. Quem responde é o **controlador** (`core_chatbot.nucleo.controlador`): o núcleo de
compilador entende a pergunta (léxico → gramática de intenções → parser → semântica) e responde
direto do Manual, **sem modelo de linguagem no caminho**; o que a gramática não reconhece cai no
**plano B**, a pilha validada cientificamente — recuperação **BM25 + reranker**, **piso de
score** (recusa fora-de-escopo antes do LLM) e gerador local (Ollama, temperatura 0) no
**perfil institucional** do guardrail. Cada resposta indica de onde veio. Não é um serviço
oficial — mostra um disclaimer no cabeçalho e cita a fonte (trecho do Manual).

Exige Ollama no ar + o modelo do config **para o plano B**; as intenções que o núcleo reconhece
respondem sem ele. Uso:
    python scripts/produto/assistente_institucional.py
Encerra com 'sair'/'exit'/'quit', Ctrl-C ou fim da entrada (EOF). Também aceita perguntas
por pipe (ex.: echo "qual o limite de faltas?" | python scripts/produto/assistente_institucional.py).
"""
from __future__ import annotations

import sys

from core_chatbot.nucleo.controlador import Dialogo, Origem

SAIR = {"sair", "exit", "quit"}
RODAPE_ORIGEM = {
    Origem.NUCLEO: "(trecho do Manual, localizado pela gramatica de intencoes -- sem IA)",
    Origem.PLANO_B: "(redigida pelo assistente a partir dos trechos consultados)",
}
DISCLAIMER = (
    "Assistente NAO-OFICIAL, baseado apenas no Manual do Aluno. Pode errar; confirme\n"
    "  informacoes importantes (prazos, valores, datas) na secretaria ou no Manual oficial."
)


def main() -> int:
    print("Carregando indice e modelos (pode levar alguns segundos)...", flush=True)
    dialogo = Dialogo.montar()

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

        atendimento = dialogo.atender(pergunta, historico, n_janela=110)
        historico = (historico + [(pergunta, atendimento.texto)])[-4:]  # últimos 4 turnos
        print(f"\nAssistente> {atendimento.texto}")
        # Sem fonte não houve consulta ao Manual (recusa do piso, saudação, não entendi):
        # nesses casos nem o rodapé de origem nem as fontes fazem sentido.
        if atendimento.fontes:
            print(f"  {RODAPE_ORIGEM[atendimento.origem]}")
            print("\nFontes (trechos consultados; * = citado na resposta):")
            for f in atendimento.fontes:
                print(f"  {'*' if f['citada'] else ' '}[{f['n']}] {f['texto']}")
            print("  (confirme no Manual oficial antes de decidir algo importante)")
        print()

    print("Ate mais!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
