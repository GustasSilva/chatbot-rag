"""Smoke test da decodificação restrita por gramática (Marco 0 da intervenção).

Isolado do RAG: alimenta trechos na mão direto no ``GeradorLlamaCpp``, então NÃO carrega
índice, embeddings nem reranker. Objetivo: validar, contra o tokenizer/modelo REAIS, o que os
testes unitários não cobrem — que (a) a lib carrega o GGUF, (b) o ``logits_processor`` é aceito
na geração, (c) a saída restrita sai com ``[n]`` bem-formado. Compara COM x SEM restrição
reusando o mesmo modelo carregado (a restrição é um atributo, alternável entre as duas chamadas).

Pré-requisitos:
  - ``pip install llama-cpp-python`` (com CUDA — ver README/handoff)
  - ``geracao.caminho_modelo_gguf`` no ``config.yaml`` apontando para o GGUF do Llama 3.1 8B Q4

Uso:  python scripts/estudo/marco_gramatica_smoke.py
"""
from __future__ import annotations

import os

from rag.config import carregar_config
from rag.corpus.chunking import Chunk
from rag.generation.llamacpp import GeradorLlamaCpp


def _trecho(id_: int, texto: str) -> Chunk:
    return Chunk(
        id=id_, doc_id="manual", texto=texto, inicio_char=0, fim_char=len(texto),
        indice_no_doc=id_,
    )


# Trechos plausíveis do domínio do Manual; o [1] responde à pergunta, os outros são distratores.
CONTEXTOS = [
    _trecho(1, "O aluno é reprovado por frequência quando ultrapassa 25% de faltas na disciplina."),
    _trecho(2, "A rematrícula deve ser feita dentro do prazo previsto no calendário acadêmico."),
    _trecho(3, "O trancamento de matrícula pode ser solicitado uma vez por período letivo."),
]
PERGUNTA = "Qual o limite de faltas para não ser reprovado?"


def _mostrar(titulo: str, resp) -> None:
    print(f"\n=== {titulo} ===")
    print("Resposta:", resp.texto)
    print("Fontes citadas (ids):", resp.fontes)


def main() -> None:
    cfg = carregar_config()
    # GGUF_MODEL permite apontar um GGUF (ex.: o blob do Ollama) sem editar o config.yaml.
    caminho = os.environ.get("GGUF_MODEL") or getattr(cfg.geracao, "caminho_modelo_gguf", None)
    if not caminho:
        raise SystemExit(
            "Defina a env GGUF_MODEL ou geracao.caminho_modelo_gguf (GGUF do Llama 3.1 8B Q4)."
        )
    gerador = GeradorLlamaCpp(
        caminho_modelo=caminho,
        perfil="institucional",
        temperatura=cfg.geracao.temperatura,
        n_ctx=2048,  # modesto: cabe folgado nos 6 GB da 3050 junto do modelo Q4
        n_gpu_layers=int(os.environ.get("GGUF_NGL", "-1")),  # -1 = tudo na GPU; reduza se faltar VRAM
    )

    gerador.restringir_citacao = True
    _mostrar("COM restrição por gramática", gerador.gerar(PERGUNTA, CONTEXTOS))

    gerador.restringir_citacao = False
    _mostrar("SEM restrição (baseline)", gerador.gerar(PERGUNTA, CONTEXTOS))


if __name__ == "__main__":
    main()
