"""Fase 3 do front-end: traduz a intenção na consulta que vai ao Manual.

Entra o reconhecimento, sai uma :class:`Consulta`. É o *lowering* de um compilador: a forma de
superfície, cheia de variação, vira uma representação interna única.

Cada intenção tem uma consulta fixa, escrita à mão no vocabulário do documento, e é ela que
chega ao recuperador, nunca a frase do aluno. Os **campos** são os dados soltos que a regra não
consumiu (nome de disciplina, número de dias) e não entram na consulta.

``de_tabela`` exige que toda regra da gramática tenha ação e que não haja ação órfã, senão uma
regra nova casaria a pergunta e estouraria na hora de agir.

Por que a consulta canônica importa tanto, e a limitação da colheita de campos:
``docs/decisoes.md`` (seção 7).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .gramatica import Gramatica
from .lexico import TipoToken, Token
from .sintatico import Reconhecimento


@dataclass(frozen=True)
class Campo:
    """Um dado que a intenção espera colher da sobra, e de que tipo de token ele vem."""

    nome: str
    tipo: TipoToken


@dataclass(frozen=True)
class Acao:
    """O que fazer com a intenção: a consulta canônica ao Manual e os campos a preencher."""

    consulta: str
    campos: tuple[Campo, ...] = ()


@dataclass(frozen=True)
class Consulta:
    """A saída do front-end: pergunta canônica pronta para a base de conhecimento."""

    intencao: str
    texto: str
    campos: Mapping[str, str] = field(default_factory=dict)


class AnalisadorSemantico:
    """Traduz o reconhecimento em consulta, segundo a tabela de ações."""

    def __init__(self, acoes: Mapping[str, Acao]) -> None:
        self._acoes = acoes

    @classmethod
    def de_tabela(cls, acoes: Mapping[str, Acao], gramatica: Gramatica) -> AnalisadorSemantico:
        """Confere que a tabela cobre exatamente as intenções da gramática, nem mais nem menos."""
        intencoes = {regra.intencao for regra in gramatica.regras}
        sem_acao = sorted(intencoes - acoes.keys())
        if sem_acao:
            raise ValueError(f"intencoes da gramatica sem acao definida: {sem_acao}")
        orfas = sorted(acoes.keys() - intencoes)
        if orfas:
            raise ValueError(f"acoes sem regra na gramatica: {orfas}")
        return cls(acoes)

    def analisar(self, reconhecimento: Reconhecimento) -> Consulta:
        """Monta a consulta da intenção reconhecida, preenchendo os campos que a sobra oferecer."""
        acao = self._acoes[reconhecimento.intencao]  # de_tabela garante que a chave existe
        campos = {}
        for campo in acao.campos:
            valor = _primeiro_valor(reconhecimento.sobra, campo.tipo)
            if valor is not None:
                campos[campo.nome] = valor
        return Consulta(reconhecimento.intencao, acao.consulta, campos)


def _primeiro_valor(sobra: Sequence[Token], tipo: TipoToken) -> str | None:
    """O lexema do primeiro token do tipo pedido — como o aluno escreveu, que é o que se exibe."""
    return next((token.lexema for token in sobra if token.tipo is tipo), None)
