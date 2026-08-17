"""Fase 1 do front-end: quebra a pergunta em símbolos tipados.

Normaliza a escrita (minúsculas, sem acento) e traduz sinônimos para um símbolo único, de modo
que a variação morre aqui. Descarta ruído como um scanner descarta espaço e comentário, e deixa
passar a palavra desconhecida, que pode ser valor de campo.

Mecanismo aqui; vocabulário do Manual em ``intencoes``. Limitações e decisões em
``docs/decisoes.md`` (seção 12).
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto

# Uma "palavra" para o scanner: letras (acentuadas inclusive) e dígitos. Todo o resto
# (pontuação, símbolos) é separador e não gera token.
_PALAVRA = re.compile(r"\w+", re.UNICODE)


class TipoToken(Enum):
    PALAVRA_CHAVE = auto()  # está no léxico; ``valor`` é o símbolo canônico (ex.: FALTA)
    NUMERO = auto()         # literal numérico (ex.: 25)
    RUIDO = auto()          # palavra irrelevante para a gramática; descartada por padrão
    DESCONHECIDO = auto()   # fora do léxico; segue adiante como possível valor de campo


@dataclass(frozen=True)
class Token:
    tipo: TipoToken
    valor: str    # símbolo canônico, ou a forma normalizada quando não há símbolo
    lexema: str   # o texto exatamente como o aluno escreveu
    inicio: int   # posição do lexema no texto original (para mensagens de erro)


def normalizar(texto: str) -> str:
    """Forma canônica de escrita: minúsculas e sem acentos ("Ausências" -> "ausencias")."""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


@dataclass(frozen=True)
class Lexico:
    """Tabela de símbolos: forma normalizada -> símbolo canônico, mais as palavras de ruído.

    Construa por :meth:`de_grupos`, que é como o vocabulário é escrito à mão.
    """

    simbolo_por_variante: Mapping[str, str]
    ruido: frozenset[str]

    @property
    def simbolos_definidos(self) -> frozenset[str]:
        """Todos os símbolos que o léxico sabe produzir — o alfabeto da gramática de intenções."""
        return frozenset(self.simbolo_por_variante.values())

    @classmethod
    def de_grupos(
        cls,
        grupos: Mapping[str, Sequence[str]],
        ruido: Iterable[str],
    ) -> Lexico:
        """Inverte ``{símbolo: [variantes]}`` para o mapa de consulta, normalizando tudo.

        Falha alto em definição inconsistente (palavra apontando para dois símbolos, ou listada
        como ruído e como variante): silenciosas, viram bug difícil de achar depois.
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
        """Tokeniza ``texto``. O ruído sai da lista por padrão (mantê-lo só serve para inspeção)."""
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
    """Só os símbolos das palavras-chave, na ordem — a visão que a gramática enxerga."""
    return [t.valor for t in tokens if t.tipo is TipoToken.PALAVRA_CHAVE]
