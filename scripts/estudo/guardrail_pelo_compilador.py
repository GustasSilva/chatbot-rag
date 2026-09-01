# -*- coding: utf-8 -*-
"""O proprio compilador pode servir de guardrail, dispensando o cross-encoder?

Hipotese: entre as perguntas que a gramatica NAO reconhece, as legitimas disparam mais
simbolos de ASSUNTO do que as adversariais, que costumam disparar so marcadores
interrogativos. Se separar, o detector de escopo passa a ser o proprio front-end.

Compara as duas populacoes que de fato chegam ao caminho auxiliar:
  - as perguntas do gold-set que a gramatica nao reconheceu;
  - as 31 adversariais.
"""
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "scripts/produto")

from rag.compilador.intencoes import ASSUNTOS, GRAMATICA_MANUAL, LEXICO_MANUAL
from rag.compilador.lexico import AnalisadorLexico, simbolos
from rag.compilador.sintatico import AnalisadorSintatico
from rag.goldset import carregar_goldset

from institucional_guardrail import ADVERSARIAIS

lex = AnalisadorLexico(LEXICO_MANUAL)
sin = AnalisadorSintatico(GRAMATICA_MANUAL)


def perfil(pergunta):
    """(assuntos distintos, simbolos distintos) que a pergunta dispara."""
    s = set(simbolos(lex.analisar(pergunta)))
    return len(s & set(ASSUNTOS)), len(s)


itens = carregar_goldset("data/goldsets/institucional.json")
nao_reconhecidas = [i.pergunta for i in itens if sin.analisar(lex.analisar(i.pergunta)) is None]
adversariais = [q for lista in ADVERSARIAIS.values() for q in lista]

print("Perguntas que chegam ao caminho auxiliar\n")
print("LEGITIMAS nao reconhecidas pela gramatica (%d):" % len(nao_reconhecidas))
for q in nao_reconhecidas:
    a, t = perfil(q)
    print("   assuntos=%d simbolos=%d  %s" % (a, t, q[:62]))

print("\nADVERSARIAIS (%d), por categoria:" % len(adversariais))
for cat, lista in ADVERSARIAIS.items():
    vals = [perfil(q)[0] for q in lista]
    print("   %-38s assuntos: %s" % (cat[:38], vals))

la = [perfil(q)[0] for q in nao_reconhecidas]
aa = [perfil(q)[0] for q in adversariais]
print("\n%-14s %5s %5s %5s" % ("", "min", "max", "media"))
print("%-14s %5d %5d %5.2f" % ("legitimas", min(la), max(la), sum(la) / len(la)))
print("%-14s %5d %5d %5.2f" % ("adversariais", min(aa), max(aa), sum(aa) / len(aa)))

print("\nExiste corte por numero de ASSUNTOS?")
melhor = None
for corte in range(0, max(aa + la) + 2):
    passa = sum(1 for v in la if v >= corte)
    barra = sum(1 for v in aa if v < corte)
    print("   corte >= %d : legitimas aceitas %d/%d | adversariais recusadas %2d/%d"
          % (corte, passa, len(la), barra, len(aa)))
    if melhor is None or passa + barra > melhor[1] + melhor[2]:
        melhor = (corte, passa, barra)
print("\n   melhor: corte >= %d, %d/%d legitimas e %d/%d adversariais"
      % (melhor[0], melhor[1], len(la), melhor[2], len(aa)))
