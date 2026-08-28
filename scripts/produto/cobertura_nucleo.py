"""Cobertura do núcleo de compilador (passo 7 do plano do pivô).

Mede o quanto o chatbot responde **sem IA** — nenhuma etapa aqui chama modelo de linguagem.
A pergunta passa por léxico → gramática de intenções → parser → semântica → Manual, e o que
não é reconhecido é contado como "sobra para o plano B", sem ser respondido.

Quatro números, na ordem em que importam:

- **reconhecimento**: quantas perguntas a gramática reconhece sozinha (a cobertura do núcleo);
- **acerto quando reconhece**: o chunk-gold está entre os trechos consultados? o trecho-fonte
  cabe inteiro no destaque exibido?
- **falso positivo**: reconheceu a intenção mas trouxe o trecho errado — o modo perigoso, que
  responde com confiança a coisa errada (foi assim que a pergunta do aluno-atleta foi pega);
- **o que falta**: para cada pergunta não reconhecida, os símbolos que o léxico já produziu.
  Perguntas com dois ou mais símbolos distintos precisam **só de uma regra** (duas linhas em
  ``intencoes``); as demais precisam de vocabulário antes.

Ressalva de leitura: medir cobertura nas mesmas perguntas que serviram para escrever as regras
é **in-sample**. O número diz o que a gramática cobre HOJE, não o que ela generaliza — para isso,
derive as regras dos tópicos do Manual e deixe parte das perguntas de fora ao escrever.

Uso:
    python scripts/produto/cobertura_nucleo.py       # pilha do produto (BM25 + reranker)
    COBERTURA_RAPIDA=1 python scripts/produto/cobertura_nucleo.py   # só BM25, sem carregar modelo
"""
from __future__ import annotations

import csv
import os
import sys

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.avaliacao.goldset import carregar_goldset, construir_relevancia
from rag.compilador.base_conhecimento import BaseConhecimento
from rag.compilador.intencoes import GRAMATICA_MANUAL, LEXICO_MANUAL, REGRAS, SEMANTICA_MANUAL
from rag.compilador.lexico import AnalisadorLexico, simbolos
from rag.compilador.sintatico import AnalisadorSintatico
from rag.pipeline import construir_indice, montar_esparsa, montar_recuperador_produto

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
CAMINHO_GOLD = "data/goldsets/institucional.json"
CAMINHO_CSV = "outputs/cobertura_nucleo.csv"
DOC = "manual"
TOP_K = 3  # mesmo padrão que o produto usa em BaseConhecimento


def _montar_recuperador(cfg, rapido: bool):
    """Recuperador do produto (BM25 + reranker) ou só BM25, para o laço de feedback."""
    indice = construir_indice({DOC: carregar_pdf(CAMINHO_PDF)}, cfg)
    if rapido:
        return indice, montar_esparsa(indice, cfg)
    return indice, montar_recuperador_produto(indice, cfg)


def main() -> int:
    rapido = bool(os.environ.get("COBERTURA_RAPIDA"))
    cfg = carregar_config()
    itens = carregar_goldset(CAMINHO_GOLD)

    print("Carregando indice" + ("" if rapido else " e modelos") + "...", flush=True)
    indice, recuperador = _montar_recuperador(cfg, rapido)
    relevancia = construir_relevancia(
        itens, indice.chunks, indice.textos_doc, cfg.recuperacao.limiar_relevancia
    )

    lexico = AnalisadorLexico(LEXICO_MANUAL)
    sintatico = AnalisadorSintatico(GRAMATICA_MANUAL)
    base = BaseConhecimento(recuperador, indice.chunks, TOP_K)

    linhas = []
    por_regra: dict[str, list[str]] = {}
    n_reconhecidas = n_hit = n_destaque = 0
    for item in itens:
        tokens = lexico.analisar(item.pergunta)
        reconhecimento = sintatico.analisar(tokens)
        linha = {
            "id": item.id,
            "pergunta": item.pergunta,
            "reconhecida": int(reconhecimento is not None),
            "intencao": "",
            "hit_recuperacao": "",
            "trecho_no_destaque": "",
            "simbolos": " ".join(simbolos(tokens)),
            "falta": "",
        }

        if reconhecimento is None:
            # Dois ou mais símbolos distintos: o léxico já entende a pergunta, falta a regra.
            distintos = len(set(simbolos(tokens)))
            linha["falta"] = "regra" if distintos >= 2 else "vocabulario"
        else:
            resposta = base.consultar(SEMANTICA_MANUAL.analisar(reconhecimento))
            hit = bool({t.id for t in resposta.trechos} & relevancia[item.id])
            no_destaque = item.trecho_fonte in resposta.destaque

            n_reconhecidas += 1
            n_hit += hit
            n_destaque += no_destaque
            por_regra.setdefault(reconhecimento.intencao, []).append(item.id)
            linha["intencao"] = reconhecimento.intencao
            linha["hit_recuperacao"] = int(hit)
            linha["trecho_no_destaque"] = int(no_destaque)

        linhas.append(linha)

    with open(CAMINHO_CSV, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)

    _relatar(itens, linhas, por_regra, n_reconhecidas, n_hit, n_destaque, recuperador.nome)
    return 0


def _relatar(itens, linhas, por_regra, n_reconhecidas, n_hit, n_destaque, nome_recuperador):
    total = len(itens)
    print(f"\nCobertura do nucleo | {total} perguntas | recuperador={nome_recuperador} "
          f"| top-{TOP_K} | sem LLM\n")
    print(f"reconhecidas pelo nucleo: {n_reconhecidas}/{total} = {n_reconhecidas/total:.0%}")
    print(f"sobra para o plano B:     {total - n_reconhecidas}/{total}")

    if n_reconhecidas:
        falsos = n_reconhecidas - n_hit
        print(f"\ndas reconhecidas:")
        print(f"  chunk-gold entre os trechos: {n_hit}/{n_reconhecidas}")
        print(f"  trecho-fonte no destaque:    {n_destaque}/{n_reconhecidas}")
        print(f"  FALSO POSITIVO (trecho errado): {falsos}")
        if falsos:
            errados = [l["id"] for l in linhas if l["hit_recuperacao"] == 0]
            print(f"    -> {errados}  (regra generica demais: separe em uma mais especifica)")

    mortas = sorted(set(REGRAS) - set(por_regra))
    print(f"\nregras: {len(REGRAS)} escritas | {len(por_regra)} disparam")
    for intencao, ids in sorted(por_regra.items()):
        print(f"  {intencao:24s} {len(ids):2d}  {' '.join(ids)}")
    if mortas:
        print(f"  nunca disparam: {mortas}")

    faltas = [l for l in linhas if l["falta"]]
    so_regra = [l for l in faltas if l["falta"] == "regra"]
    print(f"\nnao reconhecidas: {len(so_regra)} precisam so de REGRA | "
          f"{len(faltas) - len(so_regra)} precisam de VOCABULARIO tambem")
    for linha in so_regra[:10]:
        print(f"  {linha['id']}: {linha['simbolos']}")
    if len(so_regra) > 10:
        print(f"  ... e mais {len(so_regra) - 10} (lista completa em {CAMINHO_CSV})")
    print(f"\nDetalhe por pergunta em {CAMINHO_CSV}")


if __name__ == "__main__":
    sys.exit(main())
