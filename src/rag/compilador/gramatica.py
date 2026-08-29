"""A notação em que as regras de intenção são escritas, e sua compilação.

O alfabeto aqui **não é o caractere**: é o símbolo canônico produzido pela análise léxica
(``FALTA``, ``TRANCAR``, ``QUANTIDADE``). Cada regra é uma sequência desses símbolos e nomeia
uma intenção. A regra casa como subsequência, ignorando os tokens entre os seus símbolos, e
ainda assim denota uma linguagem regular. As regras do Manual estão em ``intencoes``::

    limite_faltas     := QUANTIDADE FALTA DISCIPLINA?
    prazo_rematricula := QUANDO|PRAZO MATRICULA

Espaço separa os elementos e a ordem importa; ``?`` opcional; ``|`` símbolos equivalentes na
posição; ``+`` adjacência; ``&`` ordem livre; ``!`` exclusão.

``de_notacao`` compila e confere contra o léxico, rejeitando símbolo fora do léxico (o análogo
do identificador não declarado), regra só de opcionais e símbolo repetido em dois elementos.
Por que cada mecanismo existe, com as medições: ``docs/decisoes.md`` §2 a §5.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto

from .lexico import Lexico

_OPCIONAL = "?"
_ALTERNATIVA = "|"
_ADJACENTE = "+"
_LIVRE = "&"
_EXCLUSAO = "!"


class Juncao(Enum):
    """Como os símbolos de um mesmo elemento se relacionam entre si."""

    ADJACENTE = auto()  # A+B: B tem de ser o símbolo logo depois de A
    LIVRE = auto()      # A&B: os dois presentes, em qualquer ordem


@dataclass(frozen=True)
class Elemento:
    """Um passo da regra: um símbolo, ou vários equivalentes, presente ou dispensável."""

    alternativas: frozenset[str]
    opcional: bool = False
    extras: tuple[frozenset[str], ...] = ()   # os demais símbolos do mesmo passo
    juncao: Juncao = Juncao.ADJACENTE
    excluido: bool = False                    # inverte: a regra vale se o símbolo não aparecer


@dataclass(frozen=True)
class Regra:
    """Uma intenção e a sequência de elementos que a reconhece."""

    intencao: str
    elementos: tuple[Elemento, ...]

    @property
    def obrigatorios(self) -> int:
        """Quantos símbolos a pergunta precisa conter: o peso da regra no desempate (§5)."""
        return sum(
            1 + len(elemento.extras)
            for elemento in self.elementos
            if not elemento.opcional and not elemento.excluido
        )


def compilar_elementos(notacao: str) -> tuple[Elemento, ...]:
    """Traduz a notação de uma regra ("QUANTIDADE FALTA DISCIPLINA?") para elementos."""
    elementos: list[Elemento] = []
    for parte in notacao.split():
        excluido = parte.startswith(_EXCLUSAO)
        corpo = parte[len(_EXCLUSAO):] if excluido else parte
        opcional = corpo.endswith(_OPCIONAL)
        corpo = corpo[: -len(_OPCIONAL)] if opcional else corpo

        if _ADJACENTE in corpo and _LIVRE in corpo:
            raise ValueError(f"não misture '+' e '&' no mesmo elemento: '{parte}'")
        juncao = Juncao.LIVRE if _LIVRE in corpo else Juncao.ADJACENTE
        elos = corpo.split(_LIVRE if juncao is Juncao.LIVRE else _ADJACENTE)
        conjuntos = [frozenset(elo.split(_ALTERNATIVA)) for elo in elos]
        if not all(all(elo.split(_ALTERNATIVA)) for elo in elos) or not corpo:
            raise ValueError(f"elemento malformado em '{notacao}': '{parte}'")
        if excluido and (opcional or len(elos) > 1):
            raise ValueError(
                f"exclusão não aceita '?', '+' nem '&' em '{notacao}': '{parte}'"
            )
        elementos.append(
            Elemento(conjuntos[0], opcional, tuple(conjuntos[1:]), juncao, excluido)
        )

    if not elementos:
        raise ValueError("regra vazia: uma intenção precisa de ao menos um elemento")
    return tuple(elementos)


def _conjuntos(elemento: Elemento) -> tuple[frozenset[str], ...]:
    """Todos os conjuntos de símbolos do elemento: o próprio e os extras do mesmo passo."""
    return (elemento.alternativas, *elemento.extras)


@dataclass(frozen=True)
class Gramatica:
    """O conjunto de regras, já compilado e conferido contra o léxico."""

    regras: tuple[Regra, ...]

    @classmethod
    def de_notacao(cls, notacoes: Mapping[str, str], lexico: Lexico) -> Gramatica:
        """Compila ``{intenção: notação}`` conferindo cada símbolo contra a tabela de símbolos."""
        definidos = lexico.simbolos_definidos
        regras: list[Regra] = []
        for intencao, notacao in notacoes.items():
            regra = Regra(intencao, compilar_elementos(notacao))

            conjuntos = [c for elemento in regra.elementos for c in _conjuntos(elemento)]
            usados = {simbolo for conjunto in conjuntos for simbolo in conjunto}
            desconhecidos = sorted(usados - definidos)
            if desconhecidos:
                raise ValueError(
                    f"regra '{intencao}' usa simbolo fora do lexico: {desconhecidos}"
                )
            if regra.obrigatorios == 0:
                raise ValueError(
                    f"regra '{intencao}' e so de opcionais: casaria qualquer pergunta"
                )
            repetidos = sorted(
                simbolo
                for simbolo in usados
                if sum(simbolo in conjunto for conjunto in conjuntos) > 1
            )
            if repetidos:
                raise ValueError(
                    f"regra '{intencao}' repete simbolo em elementos diferentes: {repetidos}"
                )
            regras.append(regra)

        return cls(tuple(regras))
