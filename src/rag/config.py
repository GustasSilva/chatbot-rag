"""Carregamento tipado do ``config.yaml``.

Todos os parâmetros do experimento vivem no YAML; aqui eles viram dataclasses
imutáveis para evitar erros de chave e documentar o contrato de cada seção.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
CAMINHO_CONFIG_PADRAO = RAIZ_PROJETO / "config.yaml"


@dataclass(frozen=True)
class ConfigChunking:
    tamanho_tokens: int
    sobreposicao_tokens: int


@dataclass(frozen=True)
class ConfigEmbeddings:
    modelo: str
    prefixo_consulta: str
    prefixo_documento: str
    normalizar_l2: bool
    batch_size: int
    dispositivo: str | None


@dataclass(frozen=True)
class ConfigBM25:
    k1: float
    b: float
    dobrar_acentos: bool


@dataclass(frozen=True)
class ConfigHibrida:
    metodo: str
    rrf_k: int
    peso_densa: float
    peso_esparsa: float


@dataclass(frozen=True)
class ConfigReranker:
    modelo: str
    top_k_entrada: int


@dataclass(frozen=True)
class ConfigRecuperacao:
    ks: tuple[int, ...]
    top_k: int
    limiar_relevancia: float


@dataclass(frozen=True)
class ConfigGeracao:
    backend: str | None
    temperatura: float
    modelo: str | None = None
    modelo_fallback: str | None = None
    host: str = "http://localhost:11434"
    top_k_contexto: int = 5
    timeout_s: int = 120
    perfil_guardrail: str = "estrito"  # "estrito" (saúde) | "institucional" (produto, menos estrito)


@dataclass(frozen=True)
class Config:
    seed: int
    chunking: ConfigChunking
    embeddings: ConfigEmbeddings
    bm25: ConfigBM25
    hibrida: ConfigHibrida
    reranker: ConfigReranker
    recuperacao: ConfigRecuperacao
    geracao: ConfigGeracao


def carregar_config(caminho: str | Path | None = None) -> Config:
    """Lê o ``config.yaml`` e devolve a configuração tipada."""
    caminho = Path(caminho) if caminho is not None else CAMINHO_CONFIG_PADRAO
    with open(caminho, "r", encoding="utf-8") as arquivo:
        bruto = yaml.safe_load(arquivo)

    return Config(
        seed=int(bruto["seed"]),
        chunking=ConfigChunking(**bruto["chunking"]),
        embeddings=ConfigEmbeddings(**bruto["embeddings"]),
        bm25=ConfigBM25(**bruto["bm25"]),
        hibrida=ConfigHibrida(**bruto["hibrida"]),
        reranker=ConfigReranker(**bruto["reranker"]),
        recuperacao=ConfigRecuperacao(
            ks=tuple(bruto["recuperacao"]["ks"]),
            top_k=int(bruto["recuperacao"]["top_k"]),
            limiar_relevancia=float(bruto["recuperacao"]["limiar_relevancia"]),
        ),
        geracao=ConfigGeracao(**bruto["geracao"]),
    )
