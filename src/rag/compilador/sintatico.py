"""Fase 2 do front-end: casa os tokens com a gramática e devolve a intenção.

Entra a lista de tokens, sai um :class:`Reconhecimento` ou ``None`` — e esse ``None`` é o sinal
para o controlador cair no plano B. Nenhuma resposta é montada aqui.

Para cada regra, varre os tokens uma vez, da esquerda para a direita, pegando a primeira
ocorrência de cada elemento e pulando o resto. Só ``PALAVRA_CHAVE`` casa: número e palavra
desconhecida sobram de propósito, porque são a matéria-prima dos campos da fase semântica.

Se mais de uma regra casar, vence a de mais símbolos obrigatórios. Por que o guloso é exato e
como o desempate funciona: ``docs/decisoes.md`` (seções 3 e 5).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .gramatica import Elemento, Gramatica, Juncao, Regra
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
    presentes = {t.valor for t in tokens if t.tipo is TipoToken.PALAVRA_CHAVE}
    indices: list[int] = []
    proximo = 0
    for elemento in regra.elementos:
        if elemento.excluido:
            # Guarda: a regra inteira é descartada se o símbolo proibido aparecer na pergunta.
            if presentes & elemento.alternativas:
                return None
            continue
        achado = _procurar(elemento, tokens, proximo)
        if achado is None:
            if elemento.opcional:
                continue
            return None
        inicio, fim = achado
        indices.append(inicio)
        proximo = fim + 1  # a ordem da regra é a ordem da frase
    return tuple(indices)


def _procurar(
    elemento: Elemento, tokens: Sequence[Token], inicio: int
) -> tuple[int, int] | None:
    """Posições que satisfazem o elemento inteiro, a partir de ``inicio``.

    Devolve o par (primeira, última) das posições usadas. Num elemento de símbolo único, as
    duas coincidem.
    """
    if elemento.extras and elemento.juncao is Juncao.LIVRE:
        return _casar_livre(elemento, tokens, inicio)
    for i in range(inicio, len(tokens)):
        if not _satisfaz(tokens[i], elemento.alternativas):
            continue
        fim = _casar_adjacentes(elemento.extras, tokens, i)
        if fim is not None:
            return i, fim
    return None


def _casar_livre(
    elemento: Elemento, tokens: Sequence[Token], inicio: int
) -> tuple[int, int] | None:
    """Todos os símbolos do elemento presentes, em qualquer ordem.

    Serve à pergunta cuja ordem varia sem mudar o sentido ("quantas faltas posso ter" × "é
    permitido faltar quantas vezes"). Pega a ocorrência mais à esquerda de cada símbolo, que
    consome o mínimo da frase e preserva a exatidão do guloso.
    """
    posicoes = []
    for conjunto in (elemento.alternativas, *elemento.extras):
        posicao = next(
            (i for i in range(inicio, len(tokens)) if _satisfaz(tokens[i], conjunto)), None
        )
        if posicao is None:
            return None
        posicoes.append(posicao)
    return min(posicoes), max(posicoes)


def _casar_adjacentes(
    extras: tuple[frozenset[str], ...], tokens: Sequence[Token], posicao: int
) -> int | None:
    """Confere que cada extra vem imediatamente depois, no fluxo de SÍMBOLOS.

    "Imediatamente" ignora palavra desconhecida e número: em "não fizer a matrícula", ``NEGACAO``
    e ``MATRICULA`` são adjacentes, porque "fizer" não é símbolo.
    """
    atual = posicao
    for conjunto in extras:
        seguinte = _proxima_palavra_chave(tokens, atual + 1)
        if seguinte is None or not _satisfaz(tokens[seguinte], conjunto):
            return None
        atual = seguinte
    return atual


def _proxima_palavra_chave(tokens: Sequence[Token], inicio: int) -> int | None:
    for i in range(inicio, len(tokens)):
        if tokens[i].tipo is TipoToken.PALAVRA_CHAVE:
            return i
    return None


def _satisfaz(token: Token, simbolos: frozenset[str]) -> bool:
    return token.tipo is TipoToken.PALAVRA_CHAVE and token.valor in simbolos
