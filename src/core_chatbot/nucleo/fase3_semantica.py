"""Fase 3, análise semântica: troca a intenção pela consulta fixa, escrita no vocabulário do Manual.

A busca recebe essa consulta, e nunca a frase do aluno. Os campos são dados que a regra não
consumiu, como o nome de uma disciplina, e não entram na consulta.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .gramatica import Gramatica
from .fase1_lexica import TipoToken, Token
from .fase2_sintatica import Reconhecimento


@dataclass(frozen=True)
class Campo:
    """Um dado que a intenção colhe da sobra, e de que tipo de token ele vem."""

    nome: str
    tipo: TipoToken


@dataclass(frozen=True)
class Acao:
    """A consulta de uma intenção e os campos que ela colhe."""

    consulta: str
    campos: tuple[Campo, ...] = ()


@dataclass(frozen=True)
class Consulta:
    """A saída do núcleo: o texto que vai à busca."""

    intencao: str
    texto: str
    campos: Mapping[str, str] = field(default_factory=dict)


class AnalisadorSemantico:
    """Traduz o reconhecimento em consulta, segundo a tabela de consultas."""

    def __init__(self, acoes: Mapping[str, Acao]) -> None:
        self._acoes = acoes

    @classmethod
    def de_tabela(cls, acoes: Mapping[str, Acao], gramatica: Gramatica) -> AnalisadorSemantico:
        """Confere que cada intenção tem consulta e que nenhuma consulta sobra sem regra."""
        intencoes = {regra.intencao for regra in gramatica.regras}
        sem_acao = sorted(intencoes - acoes.keys())
        if sem_acao:
            raise ValueError(f"intencoes da gramatica sem acao definida: {sem_acao}")
        orfas = sorted(acoes.keys() - intencoes)
        if orfas:
            raise ValueError(f"acoes sem regra na gramatica: {orfas}")
        return cls(acoes)

    def analisar(self, reconhecimento: Reconhecimento) -> Consulta:
        acao = self._acoes[reconhecimento.intencao]
        campos = {}
        for campo in acao.campos:
            valor = _primeiro_valor(reconhecimento.sobra, campo.tipo)
            if valor is not None:
                campos[campo.nome] = valor
        return Consulta(reconhecimento.intencao, acao.consulta, campos)


def _primeiro_valor(sobra: Sequence[Token], tipo: TipoToken) -> str | None:
    """A primeira palavra do tipo pedido, como o aluno a escreveu."""
    return next((token.lexema for token in sobra if token.tipo is tipo), None)
