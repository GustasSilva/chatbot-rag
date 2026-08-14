"""Gramática de intenções — as formas de pergunta que o núcleo reconhece, e como escrevê-las.

Fase 2 do front-end. O alfabeto aqui **não é o caractere**: é o símbolo canônico produzido pela
análise léxica (``FALTA``, ``TRANCAR``, ``QUANTIDADE``...). Cada regra é uma sequência desses
símbolos e nomeia uma **intenção** — o que o aluno quer saber.

Casamento por ilha
------------------
A regra **não** precisa cobrir a frase inteira: ela casa como **subsequência**, ignorando os
tokens que sobram. É o que o desenho da arquitetura chama de "procurar o padrão que importa".
Linguagem natural não tem ordem fixa nem enxuta o bastante para exigir casamento total — mas a
concessão é só aparente, porque a regra continua denotando uma **linguagem regular** sobre o
alfabeto de símbolos: ``QUANTIDADE FALTA`` é açúcar sintático para ``Σ* QUANTIDADE Σ* FALTA Σ*``.
Nada de pilha, nada de retrocesso; o reconhecimento cabe num autômato finito.

Notação (o formato em que a gramática é escrita, em ``intencoes``)
------------------------------------------------------------------
::

    limite_faltas := QUANTIDADE FALTA DISCIPLINA?
    prazo_rematricula := QUANDO|PRAZO MATRICULA

- espaço separa os **elementos** da sequência (a ordem importa);
- ``?`` marca elemento **opcional**;
- ``|`` separa símbolos **equivalentes** naquela posição (um deles basta).

``Gramatica.de_notacao`` compila esse texto para objetos e **valida contra o léxico**: símbolo
que não existe na tabela de símbolos é erro de definição, e falha na hora — o análogo do
identificador não declarado. É por isso que a gramática mora ao lado do léxico e não solta.

Símbolos disjuntos dentro da regra
----------------------------------
Um símbolo não pode aparecer em dois elementos da mesma regra — ``de_notacao`` rejeita. Não é
capricho: é a condição que torna **exato** o reconhecimento guloso da fase sintática (que varre
os tokens uma vez, sem retrocesso). Com os elementos disjuntos, o token que casa um elemento não
serve a nenhum outro, então pegar sempre a ocorrência mais à esquerda nunca custa um casamento
possível — deixa o maior sufixo para os elementos seguintes. Sem essa condição o guloso falharia
em regras como ``X? X`` (consome o único ``X`` no opcional e não acha o obrigatório), e aí seria
preciso retroceder. Preferimos restringir a classe de gramática a complicar o algoritmo.

Ambiguidade
-----------
Mais de uma regra pode casar a mesma pergunta ("o que é o trancamento de matrícula" casa tanto a
definição quanto qualquer regra mais frouxa sobre ``TRANCAR``). O critério de desempate é o
mesmo *maximal munch* que um analisador léxico usa para escolher entre palavras-chave: vence a
regra que exigiu **mais símbolos obrigatórios**, porque é a mais específica. Daí
``Regra.obrigatorios`` já ser calculado aqui — quem aplica o critério é a fase sintática.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .lexico import Lexico

_OPCIONAL = "?"
_ALTERNATIVA = "|"


@dataclass(frozen=True)
class Elemento:
    """Um passo da regra: um símbolo, ou vários equivalentes, presente ou dispensável."""

    alternativas: frozenset[str]
    opcional: bool = False


@dataclass(frozen=True)
class Regra:
    """Uma intenção e a sequência de elementos que a reconhece."""

    intencao: str
    elementos: tuple[Elemento, ...]

    @property
    def obrigatorios(self) -> int:
        """Quantos elementos a pergunta precisa conter — o peso da regra no desempate."""
        return sum(1 for elemento in self.elementos if not elemento.opcional)


def compilar_elementos(notacao: str) -> tuple[Elemento, ...]:
    """Traduz a notação de uma regra ("QUANTIDADE FALTA DISCIPLINA?") para elementos."""
    elementos: list[Elemento] = []
    for parte in notacao.split():
        opcional = parte.endswith(_OPCIONAL)
        corpo = parte[: -len(_OPCIONAL)] if opcional else parte
        alternativas = corpo.split(_ALTERNATIVA)
        if not all(alternativas):  # vazio antes/depois de '|', ou elemento só com '?'
            raise ValueError(f"elemento malformado em '{notacao}': '{parte}'")
        elementos.append(Elemento(frozenset(alternativas), opcional))

    if not elementos:
        raise ValueError("regra vazia: uma intenção precisa de ao menos um elemento")
    return tuple(elementos)


@dataclass(frozen=True)
class Gramatica:
    """O conjunto de regras, já compilado e conferido contra o léxico."""

    regras: tuple[Regra, ...]

    @classmethod
    def de_notacao(cls, notacoes: Mapping[str, str], lexico: Lexico) -> Gramatica:
        """Compila ``{intenção: notação}`` validando cada símbolo contra a tabela de símbolos.

        Falha alto em dois erros de definição que, silenciosos, viram intenção que nunca casa ou
        intenção que casa demais: símbolo inexistente no léxico e regra sem nenhum elemento
        obrigatório (essa casaria qualquer pergunta, inclusive as de fora do escopo).
        """
        definidos = lexico.simbolos_definidos
        regras: list[Regra] = []
        for intencao, notacao in notacoes.items():
            regra = Regra(intencao, compilar_elementos(notacao))

            usados = {alt for elemento in regra.elementos for alt in elemento.alternativas}
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
                if sum(simbolo in e.alternativas for e in regra.elementos) > 1
            )
            if repetidos:
                raise ValueError(
                    f"regra '{intencao}' repete simbolo em elementos diferentes: {repetidos}"
                )
            regras.append(regra)

        return cls(tuple(regras))
