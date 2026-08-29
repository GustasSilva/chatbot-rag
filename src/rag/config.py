"""Todos os parâmetros do assistente, num lugar só.

Uma estrutura imutável com valores padrão. É o arquivo de parâmetros do trabalho, e por ser
código o próprio interpretador confere nome e tipo de cada um, coisa que um YAML não faz.
Mudar um valor aqui muda o comportamento de todos os pontos de entrada de uma vez.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # ---- corpus -----------------------------------------------------------------------
    caminho_manual: str = "data/raw/manual_aluno_unip_2026.pdf"
    tamanho_chunk: int = 180        # em "tokens" de espaço em branco, não subword
    sobreposicao: int = 45

    # ---- BM25 -------------------------------------------------------------------------
    k1: float = 1.5
    b: float = 0.75
    dobrar_acentos: bool = False    # manter o acento: o português o distingue

    # ---- reranker ---------------------------------------------------------------------
    modelo_reranker: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    top_k_reranker: int = 20        # quantos candidatos do BM25 ele reordena

    # ---- núcleo -----------------------------------------------------------------------
    top_k_nucleo: int = 3           # trechos que a base de conhecimento traz
    max_intencoes: int = 3          # quantas intenções o núcleo reconhece num só input

    # ---- geração (plano B) ------------------------------------------------------------
    modelo_llm: str = "llama3.1:8b"
    host_ollama: str = "http://localhost:11434"
    temperatura: float = 0.0        # 0 para o comportamento ser reprodutível
    top_k_contexto: int = 5         # trechos que entram no prompt
    timeout_s: int = 120
    # Recusa antes de gerar quando nem o melhor trecho atinge este escore do reranker.
    # Calibrado contra o gold-set: nenhuma das 50 legítimas foi barrada (decisoes.md §11).
    piso_score: float = -3.2

    # ---- medição ----------------------------------------------------------------------
    limiar_relevancia: float = 0.5  # fração do trecho-fonte que precisa cair no chunk
