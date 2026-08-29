"""Fase 1: quebra a pergunta em símbolos tipados.

Normaliza a escrita e traduz sinônimos para um símbolo único, de modo que a variação morre
aqui. Descarta ruído como um scanner descarta espaço e comentário, e deixa passar a palavra
desconhecida, que pode ser valor de campo. O vocabulário está em ``intencoes``.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto

from ..corpus import sem_acentos

# Uma "palavra" para o scanner: letras e dígitos. O resto é separador e não gera token.
_PALAVRA = re.compile(r"\w+", re.UNICODE)


class TipoToken(Enum):
    PALAVRA_CHAVE = auto()  # está no léxico; ``valor`` é o símbolo canônico (ex.: FALTA)
    NUMERO = auto()         # literal numérico
    RUIDO = auto()          # irrelevante para a gramática; descartado por padrão
    DESCONHECIDO = auto()   # fora do léxico; segue como possível valor de campo


@dataclass(frozen=True)
class Token:
    tipo: TipoToken
    valor: str    # símbolo canônico, ou a forma normalizada quando não há símbolo
    lexema: str   # o texto exatamente como o aluno escreveu
    inicio: int   # posição do lexema no texto original


def normalizar(texto: str) -> str:
    """Forma canônica de escrita: minúsculas e sem acento ("Ausências" -> "ausencias")."""
    return sem_acentos(texto.lower())


@dataclass(frozen=True)
class Lexico:
    """Tabela de símbolos: forma normalizada -> símbolo canônico, mais as palavras de ruído."""

    simbolo_por_variante: Mapping[str, str]
    ruido: frozenset[str]

    @property
    def simbolos_definidos(self) -> frozenset[str]:
        """Tudo que o léxico sabe produzir: o alfabeto da gramática de intenções."""
        return frozenset(self.simbolo_por_variante.values())

    @classmethod
    def de_grupos(
        cls,
        grupos: Mapping[str, Sequence[str]],
        ruido: Iterable[str],
    ) -> Lexico:
        """Inverte ``{símbolo: [variantes]}`` para o mapa de consulta, normalizando tudo.

        Falha alto em definição inconsistente: silenciosa, vira bug difícil de achar depois.
        """
        simbolo_por_variante: dict[str, str] = {}
        for simbolo, variantes in grupos.items():
            for variante in variantes:
                forma = normalizar(variante)
                anterior = simbolo_por_variante.get(forma)
                if anterior is not None and anterior != simbolo:
                    raise ValueError(
                        f"variante ambigua '{variante}': mapeada para {anterior} e {simbolo}"
                    )
                simbolo_por_variante[forma] = simbolo

        formas_ruido = frozenset(normalizar(palavra) for palavra in ruido)
        conflito = formas_ruido & simbolo_por_variante.keys()
        if conflito:
            raise ValueError(f"palavras listadas como ruido E como variante: {sorted(conflito)}")

        return cls(simbolo_por_variante, formas_ruido)


class AnalisadorLexico:
    """Varre a pergunta e devolve a sequência de tokens tipados."""

    def __init__(self, lexico: Lexico) -> None:
        self._lexico = lexico

    def analisar(self, texto: str, descartar_ruido: bool = True) -> list[Token]:
        tokens = [self._classificar(casamento) for casamento in _PALAVRA.finditer(texto)]
        if descartar_ruido:
            return [token for token in tokens if token.tipo is not TipoToken.RUIDO]
        return tokens

    def _classificar(self, casamento: re.Match[str]) -> Token:
        lexema = casamento.group()
        forma = normalizar(lexema)
        inicio = casamento.start()

        simbolo = self._lexico.simbolo_por_variante.get(forma)
        if simbolo is not None:
            return Token(TipoToken.PALAVRA_CHAVE, simbolo, lexema, inicio)
        if forma.isdigit():
            return Token(TipoToken.NUMERO, forma, lexema, inicio)
        if forma in self._lexico.ruido:
            return Token(TipoToken.RUIDO, forma, lexema, inicio)
        return Token(TipoToken.DESCONHECIDO, forma, lexema, inicio)


def simbolos(tokens: Iterable[Token]) -> list[str]:
    """Só os símbolos das palavras-chave, na ordem: a visão que a gramática enxerga."""
    return [t.valor for t in tokens if t.tipo is TipoToken.PALAVRA_CHAVE]
