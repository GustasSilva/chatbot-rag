"""Fase 2, análise sintática: casa os símbolos com as regras e devolve as intenções.

Cada regra é procurada como subsequência, da esquerda para a direita, tomando a primeira
ocorrência de cada elemento. Só palavras-chave casam: número e palavra desconhecida sobram para
os campos da fase 3. Lista vazia manda a pergunta para o caminho auxiliar.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .gramatica import Gramatica, Juncao, Regra
from .fase1_lexica import Token, TipoToken


@dataclass(frozen=True)
class Reconhecimento:
    """O que a fase sintática entendeu da pergunta."""

    intencao: str
    casados: tuple[Token, ...]  # os símbolos que satisfizeram a regra
    sobra: tuple[Token, ...]    # o resto, de onde a fase 3 tira os campos


class AnalisadorSintatico:
    """Reconhece as intenções de uma sequência de símbolos, segundo uma gramática."""

    def __init__(self, gramatica: Gramatica) -> None:
        self._gramatica = gramatica

    def analisar(self, tokens: Sequence[Token]) -> Reconhecimento | None:
        """Só a intenção principal, ou ``None`` se nenhuma regra casa."""
        melhor = self._melhor_regra(tokens)
        if melhor is None:
            return None
        return _reconhecimento(*melhor, tokens)

    def analisar_todas(
        self, tokens: Sequence[Token], maximo: int = 3
    ) -> list[Reconhecimento]:
        """Consumo iterado: casa a melhor regra, retira os símbolos que ela usou e repete.

        Retirar um símbolo leva junto as outras ocorrências dele ("colar grau" é uma menção só).
        O teto impede que sobras de uma mensagem longa casem regras em cadeia.
        """
        restantes = list(enumerate(tokens))  # (posição original, token)
        reconhecidas: list[Reconhecimento] = []
        while restantes and len(reconhecidas) < maximo:
            atuais = [token for _, token in restantes]
            melhor = self._melhor_regra(atuais)
            if melhor is None:
                break
            _, indices = melhor
            reconhecidas.append(_reconhecimento(*melhor, atuais))
            usados = set(indices)
            simbolos_usados = {atuais[i].valor for i in indices}
            restantes = [
                par
                for i, par in enumerate(restantes)
                if i not in usados and par[1].valor not in simbolos_usados
            ]
        return reconhecidas

    def _melhor_regra(
        self, tokens: Sequence[Token]
    ) -> tuple[Regra, tuple[int, ...]] | None:
        """Entre as regras que casam, vence a que cobre mais símbolos distintos; no empate, a de
        menor dispersão na frase; depois, a de mais símbolos obrigatórios; por fim, a primeira."""
        melhor: tuple[tuple[int, int, int], Regra, tuple[int, ...]] | None = None
        for regra in self._gramatica.regras:
            indices = _casar(regra, tokens)
            if indices is None:
                continue
            chave = (
                len({tokens[i].valor for i in indices}),
                -(max(indices) - min(indices)),
                regra.obrigatorios,
            )
            # '>' e não '>=': no empate total fica a primeira declarada.
            if melhor is None or chave > melhor[0]:
                melhor = (chave, regra, indices)
        return None if melhor is None else (melhor[1], melhor[2])


def _reconhecimento(
    regra: Regra, indices: tuple[int, ...], tokens: Sequence[Token]
) -> Reconhecimento:
    usados = set(indices)
    return Reconhecimento(
        intencao=regra.intencao,
        casados=tuple(tokens[i] for i in indices),
        sobra=tuple(token for i, token in enumerate(tokens) if i not in usados),
    )


def _casar(regra: Regra, tokens: Sequence[Token]) -> tuple[int, ...] | None:
    """Posições dos símbolos que satisfazem a regra, ou ``None`` se falta um obrigatório."""
    presentes = {t.valor for t in tokens if t.tipo is TipoToken.PALAVRA_CHAVE}
    indices: list[int] = []
    proximo = 0
    for elemento in regra.elementos:
        if elemento.excluido:
            if presentes & elemento.alternativas:
                return None  # o símbolo proibido apareceu
            continue

        conjuntos = (elemento.alternativas, *elemento.extras)
        achado: tuple[int, int] | None = None
        if elemento.extras and elemento.juncao is Juncao.LIVRE:
            # Ordem livre: a primeira ocorrência de cada símbolo, em qualquer ordem.
            posicoes = [
                next((i for i in range(proximo, len(tokens))
                      if _satisfaz(tokens[i], conjunto)), -1)
                for conjunto in conjuntos
            ]
            if -1 not in posicoes:
                achado = (min(posicoes), max(posicoes))
        else:
            for i in range(proximo, len(tokens)):
                if not _satisfaz(tokens[i], elemento.alternativas):
                    continue
                fim = _casar_adjacentes(elemento.extras, tokens, i)
                if fim is not None:
                    achado = (i, fim)
                    break

        if achado is None:
            if elemento.opcional:
                continue
            return None

        inicio, fim = achado
        indices.extend(
            i
            for i in range(inicio, fim + 1)
            if any(_satisfaz(tokens[i], conjunto) for conjunto in conjuntos)
        )
        proximo = fim + 1  # a ordem da regra é a ordem da frase
    return tuple(indices)


def _casar_adjacentes(
    extras: tuple[frozenset[str], ...], tokens: Sequence[Token], posicao: int
) -> int | None:
    """Cada extra vem logo depois no fluxo de símbolos; palavra sem símbolo não conta."""
    atual = posicao
    for conjunto in extras:
        seguinte = next(
            (
                i
                for i in range(atual + 1, len(tokens))
                if tokens[i].tipo is TipoToken.PALAVRA_CHAVE
            ),
            None,
        )
        if seguinte is None or not _satisfaz(tokens[seguinte], conjunto):
            return None
        atual = seguinte
    return atual


def _satisfaz(token: Token, simbolos: frozenset[str]) -> bool:
    return token.tipo is TipoToken.PALAVRA_CHAVE and token.valor in simbolos
