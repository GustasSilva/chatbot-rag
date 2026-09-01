# -*- coding: utf-8 -*-
"""Por que o destaque erra em 18 das 44? Quantas sao inalcancaveis por construcao?

O criterio de acerto e "o trecho-fonte cabe inteiro na frase destacada". Se o trecho-fonte
atravessa fronteira de frase, nenhuma frase isolada pode conte-lo, e o caso e perdido antes
de qualquer criterio de escolha. Separa os dois tipos de falha.
"""
import sys

sys.path.insert(0, "src")

from rag.compilador.base_conhecimento import BaseConhecimento, _FIM_DE_FRASE, destacar
from rag.compilador.intencoes import GRAMATICA_MANUAL, LEXICO_MANUAL, SEMANTICA_MANUAL
from rag.compilador.lexico import AnalisadorLexico
from rag.compilador.sintatico import AnalisadorSintatico
from rag.config import Config
from rag.goldset import carregar_goldset
from rag.pipeline import indexar_manual, montar_esparsa

cfg = Config()
indice = indexar_manual(cfg)
bm25 = montar_esparsa(indice, cfg)
lex = AnalisadorLexico(LEXICO_MANUAL)
sin = AnalisadorSintatico(GRAMATICA_MANUAL)
base = BaseConhecimento(bm25, indice.chunks, cfg.top_k_nucleo)

acerto = alcancavel_e_errou = inalcancavel = sem_trecho = 0
exemplos_inalcancavel = []
exemplos_errou = []

for it in carregar_goldset("data/goldsets/institucional.json"):
    rec = sin.analisar(lex.analisar(it.pergunta))
    if rec is None:
        continue
    resposta = base.consultar(SEMANTICA_MANUAL.analisar(rec))
    if not resposta.trechos:
        continue

    texto = resposta.trechos[0].texto
    if it.trecho_fonte in resposta.destaque:
        acerto += 1
        continue

    if it.trecho_fonte not in texto:
        sem_trecho += 1
        continue

    frases = [f for f in _FIM_DE_FRASE.split(texto) if f.strip()]
    if any(it.trecho_fonte in f for f in frases):
        alcancavel_e_errou += 1
        if len(exemplos_errou) < 3:
            exemplos_errou.append((it.id, it.trecho_fonte[:60], resposta.destaque[:60]))
    else:
        inalcancavel += 1
        if len(exemplos_inalcancavel) < 3:
            exemplos_inalcancavel.append((it.id, it.trecho_fonte[:78]))

total = acerto + alcancavel_e_errou + inalcancavel + sem_trecho
print("Destaque sobre %d perguntas reconhecidas\n" % total)
print("  acertou ........................................ %2d" % acerto)
print("  errou, mas alguma frase continha o trecho ...... %2d" % alcancavel_e_errou)
print("  INALCANCAVEL: o trecho-fonte cruza fronteira ... %2d" % inalcancavel)
print("  o trecho-fonte nem esta no chunk devolvido ..... %2d" % sem_trecho)
print()
alcancaveis = acerto + alcancavel_e_errou
if alcancaveis:
    print("  sobre os casos em que o acerto e possivel: %d/%d = %.0f%%"
          % (acerto, alcancaveis, 100.0 * acerto / alcancaveis))

print("\n  Exemplos de trecho-fonte que cruza fronteira de frase:")
for i, t in exemplos_inalcancavel:
    print("    [%s] %s..." % (i, t))
print("\n  Exemplos de erro de escolha (havia frase certa):")
for i, fonte, dest in exemplos_errou:
    print("    [%s] fonte:    %s..." % (i, fonte))
    print("         destaque: %s..." % dest)
