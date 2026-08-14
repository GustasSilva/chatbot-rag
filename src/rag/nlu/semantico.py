"""Análise semântica: dá sentido à intenção reconhecida e monta a consulta ao Manual.

Fase 3 do front-end, a última antes da busca. Entra um :class:`~rag.nlu.sintatico.Reconhecimento`
(intenção + tokens); sai uma :class:`Consulta`: o que perguntar ao Manual, em palavras do Manual,
mais os campos que a pergunta trouxe. É o passo de *lowering* de um compilador — a forma de
superfície, cheia de variação, vira uma representação interna única e sem ambiguidade.

A consulta canônica
-------------------
Cada intenção tem uma **consulta fixa, escrita por nós no vocabulário do documento**. A frase do
aluno não chega ao recuperador: chega esta. Duas consequências que valem o projeto inteiro:

- **O núcleo responde sem IA.** Consulta determinística no Manual, mesma pergunta → mesma
  resposta, sem modelo no caminho.
- **Fecha o buraco léxico medido no Marco 3.** Lá, o BM25 desabava em pergunta de leigo
  (recall@5 0.17 contra 0.83 na técnica) justamente porque a palavra do aluno não é a palavra do
  documento. Aqui a tradução leigo → termo do documento acontece **antes** da busca, no léxico e
  nesta tabela, em vez de ser deixada para o recuperador adivinhar.

Campos
------
São os dados soltos que a regra não consumiu (a ``sobra`` do reconhecimento): o nome de uma
disciplina, um número de dias. Cada intenção declara que campos espera e de que tipo de token
eles vêm. Os campos **não entram na consulta**: a regra de frequência do Manual não menciona
"cálculo", e jogar o nome da disciplina na busca só atrapalharia o casamento. Eles seguem na
``Consulta`` para quem monta a resposta usar.

Conferência
-----------
``de_tabela`` exige que **toda regra da gramática tenha ação** e que não haja ação órfã. É o
mesmo tipo de conferência que a gramática faz contra o léxico, um andar acima: sem ela, uma regra
nova casaria a pergunta e depois estouraria na hora de agir — erro que aparece longe da causa.

Limitação conhecida: o valor de um campo é o **primeiro token do tipo esperado** que sobrou. É
uma heurística de posição, e erra quando sobra outra palavra desconhecida antes do valor
("cálculo integral" também vira só "cálculo"). O conserto previsto é a tabela de entidades citada
em ``lexico``: com ela o valor passa a ser reconhecido por tipo, como qualquer outro símbolo.
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
