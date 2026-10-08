"""Fase 1, análise léxica: troca cada palavra da pergunta por um símbolo tipado.

A palavra vai para minúsculas e sem acento e é procurada na tabela de símbolos. O ruído é
descartado; a palavra desconhecida segue, porque pode ser um dado da pergunta.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto

from ..corpus import PALAVRA, sem_acentos


class TipoToken(Enum):
    PALAVRA_CHAVE = auto()  # está na tabela; ``valor`` é o símbolo (ex.: FALTA)
    NUMERO = auto()
    RUIDO = auto()          # palavra de função, descartada
    DESCONHECIDO = auto()   # fora da tabela; pode virar campo


@dataclass(frozen=True)
class Token:
    tipo: TipoToken
    valor: str    # o símbolo, ou a forma normalizada quando não há símbolo
    lexema: str   # a palavra como o aluno escreveu
    inicio: int   # posição na pergunta


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento ("Ausências" -> "ausencias")."""
    return sem_acentos(texto.lower())


@dataclass(frozen=True)
class Lexico:
    """A tabela de símbolos (grafia -> símbolo) e a lista de descarte."""

    simbolo_por_variante: Mapping[str, str]
    ruido: frozenset[str]

    @property
    def simbolos_definidos(self) -> frozenset[str]:
        """O alfabeto da gramática de intenções."""
        return frozenset(self.simbolo_por_variante.values())

    @classmethod
    def de_grupos(
        cls,
        grupos: Mapping[str, Sequence[str]],
        ruido: Iterable[str],
    ) -> Lexico:
        """Monta a tabela a partir de ``{símbolo: [grafias]}``, recusando definição ambígua."""
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
    """Varre a pergunta e devolve a sequência de símbolos."""

    def __init__(self, lexico: Lexico) -> None:
        self._lexico = lexico

    def analisar(self, texto: str, descartar_ruido: bool = True) -> list[Token]:
        tokens = [self._classificar(casamento) for casamento in PALAVRA.finditer(texto)]
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
    """Só os símbolos das palavras-chave, na ordem."""
    return [t.valor for t in tokens if t.tipo is TipoToken.PALAVRA_CHAVE]
