"""Experimento: efeito da decodificação restrita por gramática na citação de fonte.

Roda as 50 perguntas do gold-set institucional pela pilha REAL (híbrida + reranker) e, com os
MESMOS contextos recuperados, gera a resposta com o ``GeradorLlamaCpp`` de duas formas:

  - SEM restrição (baseline): equivale ao comportamento atual (só *pede* a citação no prompt);
  - COM restrição: o autômato força a saída ao formato ``[n]`` bem-formado.

Mede, para cada uma, a **taxa de citação bem-formada** (a resposta tem >= 1 ``[n]`` válido, i.e.
``fontes`` não vazio) e, para a versão restrita, **quantas vezes a máscara bloqueou o token de
maior logit do modelo** — a prova de que o autômato de fato interveio na decodificação.

Pré-requisitos: ``llama-cpp-python`` instalado + GGUF (env ``GGUF_MODEL`` ou
``config.geracao.caminho_modelo_gguf``). Variáveis úteis: ``GGUF_NGL`` (camadas na GPU),
``EXP_LIMITE`` (roda só as N primeiras perguntas, para um teste rápido).

Uso:  GGUF_MODEL=<caminho> python scripts/estudo/exp_gramatica.py
"""
from __future__ import annotations

import json
import os

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.generation.llamacpp import GeradorLlamaCpp
from rag.pipeline import construir_indice, montar_reranker, montar_recuperadores

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
CAMINHO_GOLDSET = "data/goldsets/institucional.json"


def _carregar_perguntas() -> list[str]:
    with open(CAMINHO_GOLDSET, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    return [item["pergunta"] for item in dados["itens"]]


def main() -> None:
    cfg = carregar_config()
    caminho = os.environ.get("GGUF_MODEL") or getattr(cfg.geracao, "caminho_modelo_gguf", None)
    if not caminho:
        raise SystemExit("Defina a env GGUF_MODEL ou geracao.caminho_modelo_gguf.")

    print("Carregando índice, recuperadores e modelo...", flush=True)
    indice = construir_indice({"manual": carregar_pdf(CAMINHO_PDF)}, cfg)
    recuperador = montar_reranker(
        montar_recuperadores(indice, cfg, incluir=["hibrida"])["hibrida"], indice, cfg
    )
    por_id = {c.id: c for c in indice.chunks}
    gerador = GeradorLlamaCpp(
        caminho_modelo=caminho,
        perfil="institucional",
        temperatura=cfg.geracao.temperatura,
        # Prompt real (top_k trechos do Manual) chega a ~2000 tokens; 4096 deixa folga para a
        # resposta caber sem ser cortada pela janela de contexto (era a causa do "sem citação").
        n_ctx=int(os.environ.get("GGUF_NCTX", "4096")),
        n_gpu_layers=int(os.environ.get("GGUF_NGL", "-1")),
    )

    perguntas = _carregar_perguntas()
    limite = int(os.environ.get("EXP_LIMITE", "0"))
    if limite > 0:
        perguntas = perguntas[:limite]
    top_k = cfg.geracao.top_k_contexto

    citou_sem = citou_com = total_intervencoes = 0
    print(f"\nRodando {len(perguntas)} perguntas (top_k={top_k})...\n", flush=True)
    for i, pergunta in enumerate(perguntas, start=1):
        resultados = recuperador.buscar(pergunta, top_k)
        contextos = [por_id[r.chunk_id] for r in resultados]

        gerador.restringir_citacao = False
        ok_sem = bool(gerador.gerar(pergunta, contextos).fontes)

        gerador.restringir_citacao = True
        resp_com = gerador.gerar(pergunta, contextos)
        ok_com = bool(resp_com.fontes)
        restr = gerador.ultimo_restritor
        intervencoes = restr.intervencoes if restr else 0
        passos = restr.passos if restr else 0

        citou_sem += ok_sem
        citou_com += ok_com
        total_intervencoes += intervencoes
        print(
            f"[{i:02d}/{len(perguntas)}] sem={'ok' if ok_sem else '--'} "
            f"com={'ok' if ok_com else '--'} intervencoes={intervencoes} passos={passos}",
            flush=True,
        )
        if not ok_com:  # diagnóstico: por que a versão restrita não citou?
            print("     texto_com:", repr(resp_com.texto[:200]), flush=True)
            print(f"     estado: prompt_len={restr._prompt_len} consumidos={restr._consumidos} "
                  f"{restr._estado} | '[' no texto? {'[' in resp_com.texto}", flush=True)

    n = len(perguntas)
    print("\n==== Resultado ====")
    print(f"Citação bem-formada  SEM restrição: {citou_sem}/{n} ({100 * citou_sem / n:.0f}%)")
    print(f"Citação bem-formada  COM restrição: {citou_com}/{n} ({100 * citou_com / n:.0f}%)")
    print(f"Intervenções da máscara (tokens do modelo bloqueados): {total_intervencoes}")
    if total_intervencoes == 0:
        print("AVISO: 0 intervenções — o autômato não bloqueou nada; verificar a ligação.")


if __name__ == "__main__":
    main()
