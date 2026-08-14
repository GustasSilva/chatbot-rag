"""Análise sintática: casa os tokens do aluno com a gramática de intenções.

Fase 2 do front-end, agora do lado do mecanismo. Entra a sequência de tokens que a análise
léxica produziu; sai uma :class:`Reconhecimento` — a intenção identificada, os tokens que
casaram a regra e os que sobraram — ou ``None``, que é o sinal para o controlador cair no plano
B (a LLM). Nenhuma resposta é montada aqui: esta fase só decide **o que o aluno quis dizer**.

Como reconhece
--------------
Para cada regra, varre os tokens **uma vez**, da esquerda para a direita, pegando para cada
elemento a primeira ocorrência ainda não usada. É o casamento por ilha descrito em
``gramatica``: os tokens entre os elementos são pulados, e o que não casou vira ``sobra``.

O guloso é exato porque a gramática garante elementos disjuntos dentro da regra (ver
``gramatica``): nenhum token disputado por dois elementos, logo a escolha mais à esquerda nunca
custa um casamento. Custo linear no número de tokens vezes o número de elementos, sem pilha e
sem retrocesso — o reconhecimento de uma linguagem regular, que é o que essas regras são.

Só ``PALAVRA_CHAVE`` participa do casamento. Número e palavra desconhecida nunca casam elemento
nenhum: sobram de propósito, porque são a matéria-prima dos **campos** que a fase semântica vai
preencher (o nome da disciplina, um prazo em dias).

Ambiguidade
-----------
Se mais de uma regra casar, vence a de mais símbolos obrigatórios (*maximal munch*: a mais
específica). Empate resolve pela ordem de declaração em ``intencoes.REGRAS``, o que mantém o
resultado determinístico — mas empate persistente entre duas regras é sinal de gramática mal
desenhada, e o lugar de corrigir é a gramática, não aqui.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .gramatica import Elemento, Gramatica, Regra
from .lexico import Token, TipoToken


@dataclass(frozen=True)
class Reconhecimento:
    """O que a fase sintática entendeu da pergunta."""

    intencao: str
    casados: tuple[Token, ...]  # os tokens que satisfizeram a regra, na ordem dos elementos
    sobra: tuple[Token, ...]    # o que a regra ignorou — de onde a semântica tira os campos


class AnalisadorSintatico:
    """Reconhece a intenção de uma sequência de tokens, segundo uma gramática."""

    def __init__(self, gramatica: Gramatica) -> None:
        self._gramatica = gramatica

    def analisar(self, tokens: Sequence[Token]) -> Reconhecimento | None:
        """Devolve a intenção mais específica que casa, ou ``None`` se nenhuma regra casa."""
        melhor: tuple[Regra, tuple[int, ...]] | None = None
        for regra in self._gramatica.regras:
            indices = _casar(regra, tokens)
            if indices is None:
                continue
            # '>' e não '>=': no empate fica a primeira declarada, e o resultado é estável.
            if melhor is None or regra.obrigatorios > melhor[0].obrigatorios:
                melhor = (regra, indices)

        if melhor is None:
            return None
        regra, indices = melhor
        usados = set(indices)
        return Reconhecimento(
            intencao=regra.intencao,
            casados=tuple(tokens[i] for i in indices),
            sobra=tuple(token for i, token in enumerate(tokens) if i not in usados),
        )


def _casar(regra: Regra, tokens: Sequence[Token]) -> tuple[int, ...] | None:
    """Índices dos tokens que satisfazem a regra, ou ``None`` se falta algum obrigatório."""
    indices: list[int] = []
    proximo = 0
    for elemento in regra.elementos:
        achado = _procurar(elemento, tokens, proximo)
        if achado is None:
            if elemento.opcional:
                continue
            return None
        indices.append(achado)
        proximo = achado + 1  # a ordem da regra é a ordem da frase
    return tuple(indices)


def _procurar(elemento: Elemento, tokens: Sequence[Token], inicio: int) -> int | None:
    """Primeira posição, a partir de ``inicio``, cujo token satisfaz o elemento."""
    for i in range(inicio, len(tokens)):
        token = tokens[i]
        if token.tipo is TipoToken.PALAVRA_CHAVE and token.valor in elemento.alternativas:
            return i
    return None
