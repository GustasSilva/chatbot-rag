"""Executa a consulta do front-end contra o Manual e devolve o trecho.

É a costura entre as duas metades do sistema, e **o caminho que responde sem IA**: da pergunta
até o trecho não há modelo de linguagem em lugar nenhum.

Depende do ``Recuperador`` abstrato, nunca de uma estratégia concreta. Não tem piso de score
porque aqui o portão é a gramática — fora de escopo não casa regra e nem chega até aqui
(``docs/decisoes.md`` §11).

A resposta traz o trecho inteiro, para rastreabilidade, e o ``destaque``: a frase que de fato
responde. Busca vazia devolve ``encontrou`` falso, e o que fazer é decisão do controlador.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..corpus.chunking import Chunk
from ..recuperacao.base import Recuperador
from ..recuperacao.esparsa import tokenizar
from .semantico import Consulta

# Fim de frase: ponto/!/? seguido de espaço. Heurística simples de propósito — abreviação
# ("art. 178") não quebra porque o dígito vem colado, e o custo de um corte errado é um
# destaque um pouco maior, não uma resposta errada.
_FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class RespostaNucleo:
    """O que o núcleo respondeu: a consulta executada e os trechos do Manual que a respondem."""

    consulta: Consulta
    trechos: tuple[Chunk, ...]
    destaque: str  # a frase do 1º trecho que responde — o que se mostra ao aluno

    @property
    def encontrou(self) -> bool:
        return bool(self.trechos)


def destacar(texto: str, consulta: str) -> str:
    """A frase do trecho com maior sobreposição de termos com a consulta.

    É a versão sem IA de "extrair a resposta do trecho": determinística e conferível. Usa o
    tokenizador do BM25 de propósito, para destacar não discordar de recuperar.

    Quatro critérios alternativos foram implementados e medidos, e todos ficaram piores que este.
    A tabela e o motivo estão em ``docs/decisoes.md`` §9 — não vale tentar de novo sem ler.
    """
    frases = [frase for frase in _FIM_DE_FRASE.split(texto) if frase.strip()]
    if not frases:
        return texto.strip()
    termos = set(tokenizar(consulta))
    # max devolve a primeira em caso de empate: ordem do documento, resultado estável.
    return max(frases, key=lambda frase: len(termos & set(tokenizar(frase)))).strip()


class BaseConhecimento:
    """Liga a consulta canônica ao Manual, pela estratégia de recuperação que receber."""

    def __init__(
        self,
        recuperador: Recuperador,
        chunks: list[Chunk],
        top_k: int = 3,
    ) -> None:
        self._recuperador = recuperador
        self._por_id = {chunk.id: chunk for chunk in chunks}
        self._top_k = top_k

    def consultar(self, consulta: Consulta) -> RespostaNucleo:
        """Busca no Manual pelo texto canônico da consulta — nunca pela frase do aluno."""
        resultados = self._recuperador.buscar(consulta.texto, self._top_k)
        trechos = tuple(self._por_id[resultado.chunk_id] for resultado in resultados)
        destaque = destacar(trechos[0].texto, consulta.texto) if trechos else ""
        return RespostaNucleo(consulta, trechos, destaque)
