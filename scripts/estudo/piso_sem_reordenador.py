# -*- coding: utf-8 -*-
"""Existe piso de pontuacao no BM25 que separe pergunta legitima de adversarial?

O piso em uso (-3,2) le a medida do reordenador. Se o BM25 sozinho separasse as duas
populacoes, o reordenador poderia sair do produto inteiro. Este script mede as duas
distribuicoes de score do MELHOR trecho e procura um corte.
"""
import sys

sys.path.insert(0, "src")

from rag.config import Config
from rag.goldset import carregar_goldset
from rag.pipeline import indexar_manual, montar_esparsa

sys.path.insert(0, "scripts/produto")
from institucional_guardrail import ADVERSARIAIS

cfg = Config()
indice = indexar_manual(cfg)
bm25 = montar_esparsa(indice, cfg)

legitimas = [i.pergunta for i in carregar_goldset("data/goldsets/institucional.json")]
adversariais = [q for lista in ADVERSARIAIS.values() for q in lista]


def top1(pergunta):
    r = bm25.buscar(pergunta, 1)
    return r[0].score if r else 0.0


sl = sorted(top1(q) for q in legitimas)
sa = sorted(top1(q) for q in adversariais)

print("BM25, score do melhor trecho\n")
print("%-16s %6s %7s %7s %7s %7s" % ("", "n", "min", "mediana", "max", "media"))
for nome, s in (("legitimas", sl), ("adversariais", sa)):
    print("%-16s %6d %7.2f %7.2f %7.2f %7.2f"
          % (nome, len(s), s[0], s[len(s) // 2], s[-1], sum(s) / len(s)))

print("\nO piso teria de ficar entre o MENOR legitimo e o MAIOR adversarial:")
print("  menor legitimo    : %6.2f" % sl[0])
print("  maior adversarial : %6.2f" % sa[-1])
if sl[0] > sa[-1]:
    print("  -> SEPARAM. Um piso entre os dois valores funcionaria.")
else:
    print("  -> NAO SEPARAM: as duas populacoes se sobrepoem.")

print("\nMelhor corte possivel (o que maximiza acertos nas duas populacoes):")
melhor = None
for corte in sorted(set(sl + sa)):
    passa = sum(1 for s in sl if s >= corte)          # legitima aceita: certo
    barra = sum(1 for s in sa if s < corte)           # adversarial recusada: certo
    if melhor is None or passa + barra > melhor[1] + melhor[2]:
        melhor = (corte, passa, barra)
corte, passa, barra = melhor
print("  corte = %.2f  ->  legitimas aceitas %d/%d | adversariais recusadas %d/%d"
      % (corte, passa, len(sl), barra, len(sa)))
print("  perde-se %d pergunta(s) legitima(s) e vazam %d adversarial(is)"
      % (len(sl) - passa, len(sa) - barra))

print("\nSem recusar nenhuma legitima (piso = menor score legitimo):")
piso = sl[0]
barra = sum(1 for s in sa if s < piso)
print("  piso = %.2f  ->  adversariais recusadas %d/%d" % (piso, barra, len(sa)))
