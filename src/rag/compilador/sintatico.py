"""Fase 2: casa os tokens com a gramática e devolve as intenções.

Entra a lista de tokens, saem os :class:`Reconhecimento` da pergunta — lista vazia é o sinal
para o controlador cair no plano B.

O símbolo inicial da gramática é ``pergunta := regra+``: uma pergunta pode conter mais de uma
intenção. ``analisar_todas`` casa a regra que mais consome, **retira da frase os símbolos que
ela usou** e repete no que sobrou. É o mesmo que um compilador faz com uma sequência de
comandos. ``analisar`` continua existindo para quem quer só a principal. Para cada regra, varre os tokens uma vez, da esquerda para
a direita, pegando a primeira ocorrência de cada elemento. Só ``PALAVRA_CHAVE`` casa: número e
palavra desconhecida sobram de propósito, porque são a matéria-prima dos campos da fase
semântica.

Casando mais de uma regra, vence a que **consome mais símbolos da pergunta**; só no empate
entra o número de obrigatórios. É o *maximal munch* do analisador léxico, aplicado no nível da
regra. O critério anterior, só por obrigatórios, não distinguia ``COMO MATRICULA`` de
``COMO TRANCAR MATRICULA?`` — as duas contam dois obrigatórios, porque o terceiro símbolo é
opcional — e a segunda nunca respondia (``docs/decisoes.md`` §21).

Por que o guloso é exato, e como o desempate funciona: ``docs/decisoes.md`` §3, §5 e §21.
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
    sobra: tuple[Token, ...]    # o que a regra ignorou: de onde a semântica tira os campos


class AnalisadorSintatico:
    """Reconhece a intenção de uma sequência de tokens, segundo uma gramática."""

    def __init__(self, gramatica: Gramatica) -> None:
        self._gramatica = gramatica

    def analisar(self, tokens: Sequence[Token]) -> Reconhecimento | None:
        """Só a intenção que mais consome da pergunta, ou ``None`` se nenhuma regra casa."""
        melhor = self._melhor_regra(tokens)
        if melhor is None:
            return None
        return _reconhecimento(*melhor, tokens)

    def analisar_todas(
        self, tokens: Sequence[Token], maximo: int = 3
    ) -> list[Reconhecimento]:
        """Todas as intenções da pergunta, na ordem em que foram reconhecidas.

        Casa a regra que mais consome, retira os símbolos que ela usou e repete no que sobrou.
        O teto existe porque sobra de símbolos pode alimentar reconhecimento espúrio em cadeia:
        sem ele, um resto qualquer acabaria casando alguma regra de símbolo único.

        Retirar um símbolo leva junto as **outras ocorrências dele**. Aqui um símbolo nomeia um
        assunto, não uma posição: em "para colar grau preciso estar regular no ENADE", tanto
        "colar" quanto "grau" produzem ``COLACAO``, e são a mesma menção dita duas vezes. Sem
        essa regra, a sobra reconhecia uma segunda intenção de colação que ninguém perguntou.
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
        """A regra que melhor cobre a pergunta (``docs/decisoes.md`` §21 e §22).

        Três critérios, nesta ordem:

        1. **quantos símbolos distintos** ela cobre — o *maximal munch*. Distintos, e não
           posições: em "colar grau" as duas palavras dão ``COLACAO``, e contar as duas
           inflaria artificialmente a cobertura de quem alcança as duas;
        2. **menor dispersão** entre a primeira e a última posição usada — entre dois
           casamentos do mesmo tamanho vence o mais compacto, que é o que evita uma regra
           costurar símbolos de perguntas diferentes;
        3. **mais símbolos obrigatórios**, o critério original.
        """
        melhor: tuple[tuple[int, int, int], Regra, tuple[int, ...]] | None = None
        for regra in self._gramatica.regras:
            indices = _casar(regra, tokens)
            if indices is None:
                continue
            # '>' e não '>=': persistindo o empate fica a primeira declarada, e o resultado
            # é estável.
            chave = (
                len({tokens[i].valor for i in indices}),
                -(max(indices) - min(indices)),
                regra.obrigatorios,
            )
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
    """Posições dos tokens que satisfazem a regra, ou ``None`` se falta algum obrigatório.

    São TODAS as posições consumidas, o que faz de ``casados`` e ``sobra`` uma partição de fato
    e dá ao desempate a medida de quanto cada regra cobre da pergunta.
    """
    presentes = {t.valor for t in tokens if t.tipo is TipoToken.PALAVRA_CHAVE}
    indices: list[int] = []
    proximo = 0
    for elemento in regra.elementos:
        if elemento.excluido:
            if presentes & elemento.alternativas:
                return None  # o símbolo proibido apareceu: a regra inteira é descartada
            continue
        achado = _procurar(elemento, tokens, proximo)
        if achado is None:
            if elemento.opcional:
                continue
            return None
        inicio, fim = achado
        # Todas as posições que o elemento ocupa, e não só a primeira: com '&' e '+' ele cobre
        # mais de uma, e é isso que o desempate por consumo precisa contar. O filtro por
        # ``conjuntos`` evita levar junto uma palavra-chave que caiu no meio do intervalo sem
        # pertencer ao elemento.
        conjuntos = (elemento.alternativas, *elemento.extras)
        indices.extend(
            i
            for i in range(inicio, fim + 1)
            if any(_satisfaz(tokens[i], conjunto) for conjunto in conjuntos)
        )
        proximo = fim + 1  # a ordem da regra é a ordem da frase
    return tuple(indices)


def _procurar(
    elemento: Elemento, tokens: Sequence[Token], inicio: int
) -> tuple[int, int] | None:
    """Par (primeira, última) das posições que satisfazem o elemento inteiro."""
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

    Serve à pergunta cuja ordem varia sem mudar o sentido ("quantas faltas posso ter" x "é
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
    """Cada extra vem logo depois, no fluxo de SÍMBOLOS.

    "Logo depois" ignora palavra desconhecida e número: em "não fizer a matrícula", ``NEGACAO``
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
