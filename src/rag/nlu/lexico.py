"""Análise léxica da pergunta do aluno — a primeira fase do front-end de compilador.

O scanner clássico lê caracteres e devolve uma sequência de **tokens tipados**, descartando o
que não interessa à gramática (espaço, comentário). Aqui a entrada é linguagem natural, então
duas coisas mudam, e são exatamente elas que fazem o trabalho da fase léxica:

- **Normalização.** O aluno escreve "Faltas", "faltas", "faltei", "ausências". Tudo isso é a
  mesma coisa para a gramática, então cada palavra é reduzida a uma forma canônica (minúsculas,
  sem acento) e depois traduzida para um **símbolo** único do léxico (``FALTA``). A variação de
  escrita morre aqui e não polui as fases seguintes.
- **Descarte de ruído.** Artigos, preposições e enfeites ("poxa", "por favor") são o análogo do
  espaço em branco: reconhecidos e jogados fora. Palavra que não está em léxico nenhum vira
  ``DESCONHECIDO`` (o análogo do identificador) e segue adiante, porque pode ser um valor de
  campo — o nome de uma disciplina, por exemplo.

Saída: ``list[Token]``, cada um com o símbolo canônico, o lexema exatamente como foi digitado e
a posição no texto original (para mensagens de erro na fase sintática).

O **mecanismo** está aqui; o **vocabulário concreto** do Manual do Aluno está em ``intencoes``.
Essa separação deixa o léxico crescer sem tocar em código.

Limitações conhecidas (viram trabalho futuro, na ordem em que devem doer):
- **Lexema de uma palavra só.** Termos compostos não são casados como uma unidade; exigiriam
  *maximal munch* sobre a sequência de palavras. Hoje a composição fica a cargo da gramática,
  que vê os símbolos em sequência. Casos observados no gold-set: "aluno-atleta" (vira ``ALUNO
  ATLETA``, o que funciona) e "prova on-line" (vira ``PROVA`` mais duas palavras soltas "on" e
  "line", o que não funciona — é o primeiro caso a pedir termos compostos).
- **Pontuação descartada.** O "?" final não vira token; a interrogação é inferida do símbolo
  interrogativo (``QUAL``, ``COMO``, ``QUE``...).
- **Sem tabela de entidades.** Nomes de disciplina caem em ``DESCONHECIDO``; quando a gramática
  precisar deles, entra um ``TipoToken.ENTIDADE`` alimentado por uma tabela própria.
- **Ordinais** ("1º") não são reconhecidos como número — a normalização os deixa como "1o".

Nota sobre reúso: a tokenização do BM25 (``retrieval.esparsa.tokenizar``) faz um recorte
parecido, mas serve à recuperação de informação (casar termos com o corpus), não à gramática.
São camadas diferentes e propositalmente independentes.
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
    """Tabela de símbolos do analisador: forma normalizada -> símbolo canônico, mais o ruído.

    Construa por :meth:`de_grupos`, que é como o vocabulário é escrito à mão (um símbolo, as
    suas variantes) — o mapa invertido que a varredura consulta é detalhe interno.
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

        Falha alto em definição inconsistente: a mesma palavra apontando para dois símbolos, ou
        listada ao mesmo tempo como ruído e como variante. São erros de escrita do vocabulário
        que, silenciosos, viram bug difícil de achar lá na frente.
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
