# -*- coding: utf-8 -*-
"""Duas medicoes que faltavam para decidir sobre o cross-encoder.

A) Quanto o reordenador melhora a RECUPERACAO do caminho auxiliar (top-5)? Compara-se com
   o BM25 puro, sem chamar a LLM, porque o que interessa e se o trecho certo chega ao modelo.

B) Da para barrar a categoria ambigua ("horario da cantina") por criterio proprio: a pergunta
   contem palavra de conteudo que NAO OCORRE em lugar nenhum do Manual? Cantina, wi-fi e
   estacionamento nao estao no documento; se separar, o criterio se constroi com o indice
   invertido que ja existe.
"""
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "scripts/produto")

from rag.config import Config
from rag.goldset import carregar_goldset, construir_relevancia
from rag.pipeline import indexar_manual, montar_esparsa, montar_recuperador_produto
from rag.recuperacao import tokenizar

from institucional_guardrail import ADVERSARIAIS

cfg = Config()
indice = indexar_manual(cfg)
itens = carregar_goldset("data/goldsets/institucional.json")
relev = construir_relevancia(itens, indice.chunks, indice.textos_doc, cfg.limiar_relevancia)

bm25 = montar_esparsa(indice, cfg)
rer = montar_recuperador_produto(indice, cfg)

print("=" * 72)
print("A) RECUPERACAO DO CAMINHO AUXILIAR (top-%d, pergunta crua)" % cfg.top_k_contexto)
print("=" * 72)
for nome, rec in (("so BM25", bm25), ("BM25 + reordenador", rer)):
    acertos = sum(
        bool({r.chunk_id for r in rec.buscar(it.pergunta, cfg.top_k_contexto)} & relev[it.id])
        for it in itens
    )
    print("  %-22s trecho certo entre os %d enviados ao modelo: %d/%d"
          % (nome, cfg.top_k_contexto, acertos, len(itens)))

print()
print("=" * 72)
print("B) CRITERIO PROPRIO PARA A CATEGORIA AMBIGUA")
print("   'a pergunta traz palavra de conteudo ausente de todo o Manual?'")
print("=" * 72)

vocabulario = set(bm25._postings)
print("  termos distintos no indice do Manual: %d" % len(vocabulario))
print()


def forasteiras(pergunta):
    """Termos da pergunta que nao ocorrem em trecho algum do Manual."""
    return sorted(t for t in set(tokenizar(pergunta, cfg.dobrar_acentos))
                  if t not in vocabulario)


print("  AMBIGUAS (as 8 que o compilador sozinho nao pega):")
for q in ADVERSARIAIS["ambíguas (parecem institucionais)"]:
    f = forasteiras(q)
    print("    [%s] %-46s %s" % ("BARRA" if f else "passa", q[:45], " ".join(f) or "(nenhuma)"))

todas_adv = [q for lista in ADVERSARIAIS.values() for q in lista]
barradas = sum(1 for q in todas_adv if forasteiras(q))
com_forasteira = [i for i in itens if forasteiras(i.pergunta)]

print()
print("  Aplicado ao conjunto todo:")
print("    adversariais barradas .............. %d/%d" % (barradas, len(todas_adv)))
print("    legitimas recusadas POR ENGANO ..... %d/%d" % (len(com_forasteira), len(itens)))
print()
print("  Exemplos de legitima que o criterio recusaria:")
for i in com_forasteira[:6]:
    print("    ! %-46s %s" % (i.pergunta[:45], " ".join(forasteiras(i.pergunta))))
