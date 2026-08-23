"""Experimento (Estágio 2): efeito da gramática JSON na validade da saída estruturada.

Roda as perguntas do gold-set institucional pela pilha real (híbrida + reranker) e, com os MESMOS
contextos, pede ao modelo a resposta em JSON de duas formas:

  - SEM gramática (baseline): só o prompt pede JSON;
  - COM gramática: o esquema é forçado pelo motor de gramática da llama.cpp (autômato de pilha).

Mede a **taxa de JSON válido no esquema** (``json.loads`` + chaves/tipos/faixa corretos) de cada
uma. A expectativa: baseline < 100% (preâmbulo, cerca de markdown, chave errada) e gramática = 100%.

Envs: GGUF_MODEL, GGUF_NGL, GGUF_NCTX, EXP_LIMITE (roda só as N primeiras).
Uso:  GGUF_MODEL=<caminho> python scripts/estudo/exp_json.py
"""
from __future__ import annotations

import json
import os

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.ia.json_estruturado import validar
from rag.ia.llamacpp import GeradorLlamaCpp
from rag.pipeline import construir_indice, montar_reranker, montar_recuperadores

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
CAMINHO_GOLDSET = "data/goldsets/institucional.json"


def _carregar_perguntas() -> list[str]:
    with open(CAMINHO_GOLDSET, encoding="utf-8") as arquivo:
        return [item["pergunta"] for item in json.load(arquivo)["itens"]]


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
        n_ctx=int(os.environ.get("GGUF_NCTX", "4096")),
        n_gpu_layers=int(os.environ.get("GGUF_NGL", "-1")),
        max_tokens=256,  # respostas JSON são curtas; acelera (e o baseline não fica divagando)
    )

    perguntas = _carregar_perguntas()
    offset = int(os.environ.get("EXP_OFFSET", "0"))  # p/ rodar em lotes (evita o tempo-limite)
    limite = int(os.environ.get("EXP_LIMITE", "0"))
    perguntas = perguntas[offset:]
    if limite > 0:
        perguntas = perguntas[:limite]
    top_k = cfg.geracao.top_k_contexto

    validos_sem = validos_com = 0
    print(f"\nRodando {len(perguntas)} perguntas (offset={offset}, top_k={top_k})...\n", flush=True)
    for i, pergunta in enumerate(perguntas, start=offset + 1):
        resultados = recuperador.buscar(pergunta, top_k)
        contextos = [por_id[r.chunk_id] for r in resultados]
        k = len(contextos)

        raw_sem = gerador.gerar_json(pergunta, contextos, usar_gramatica=False)
        ok_sem, _, motivo_sem = validar(raw_sem, k)

        raw_com = gerador.gerar_json(pergunta, contextos, usar_gramatica=True)
        ok_com, _, motivo_com = validar(raw_com, k)

        validos_sem += ok_sem
        validos_com += ok_com
        print(
            f"[q{i:02d}] sem={'ok' if ok_sem else '--'} com={'ok' if ok_com else '--'}",
            flush=True,
        )
        if not ok_sem:  # o interessante: por que o baseline falhou?
            print(f"     baseline invalido ({motivo_sem}): {raw_sem[:160]!r}", flush=True)
        if not ok_com:  # não deveria acontecer — a gramática garante o esquema
            print(f"     ALERTA com-gramatica invalido ({motivo_com}): {raw_com[:160]!r}", flush=True)

    n = len(perguntas)
    print("\n==== Resultado ====")
    print(f"JSON valido no esquema  SEM gramática: {validos_sem}/{n} ({100 * validos_sem / n:.0f}%)")
    print(f"JSON valido no esquema  COM gramática: {validos_com}/{n} ({100 * validos_com / n:.0f}%)")


if __name__ == "__main__":
    main()
