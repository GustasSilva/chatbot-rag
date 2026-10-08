"""As 31 adversariais com o piso desligado: o que o modelo de linguagem faz quando elas chegam a ele.

No sistema completo, as 31 são recusadas pelo piso antes de chegar ao modelo, de modo que a
instrução dada a ele nunca é posta à prova. Aqui o piso é desligado e cada pergunta segue até a
geração, para ver se o próprio modelo recusa, em especial as cinco tentativas de subversão.

A classificação automática só reconhece algumas redações de recusa. As respostas vão inteiras
para o arquivo de saída, para conferência à mão. Em 05/10/2026: 27 das 31 recusadas (22 com a
redação padrão, 5 com palavras próprias, entre elas as três de subversão que não usaram a padrão),
4 respondidas (asma, campus de Manaus, RA e faltas do aluno).

Exige o Ollama no ar com o modelo carregado. Uso:
    python scripts/estudo/adversarial_sem_piso.py
"""
from __future__ import annotations

import dataclasses
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "scripts/produto")

from institucional_guardrail import ADVERSARIAIS, _recusou_canonico, _recusou_outra  # noqa: E402

from core_chatbot.nucleo.controlador import Dialogo  # noqa: E402
from core_chatbot.config import Config  # noqa: E402

SAIDA = "outputs/adversarial_sem_piso.txt"


def main() -> None:
    cfg = dataclasses.replace(Config(), piso_score=-1e9)  # nenhuma pergunta é barrada pelo piso
    dialogo = Dialogo.montar(cfg, saudar=False)
    with open(SAIDA, "w", encoding="utf-8") as saida:
        for categoria, perguntas in ADVERSARIAIS.items():
            padrao = outra = respondeu = 0
            for pergunta in perguntas:
                texto = dialogo.responder(pergunta).texto
                if _recusou_canonico(texto):
                    marca, padrao = "RECUSA", padrao + 1
                elif _recusou_outra(texto):
                    marca, outra = "RECUSA-OUTRA", outra + 1
                else:
                    marca, respondeu = "CONFERIR", respondeu + 1
                saida.write(f"[{marca}] ({categoria}) {pergunta}\n    {texto}\n\n")
            print(f"{categoria}: {len(perguntas)} | recusa padrão {padrao} | "
                  f"outra recusa {outra} | conferir à mão {respondeu}")
    print(f"\nRespostas inteiras em {SAIDA}")


if __name__ == "__main__":
    main()
