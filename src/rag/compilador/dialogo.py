"""Controlador: orquestra as fases e decide quando chamar o plano B.

Único módulo que conhece as quatro fases e a saída de emergência. Reconheceu, responde do
Manual; não reconheceu, ou reconheceu mas a busca voltou vazia, vai para o plano B.

``plano_b`` é opcional de propósito: sem ele o assistente responde o que conhece e diz que não
entendeu o resto, que é a demonstração de que o núcleo é o compilador, não a LLM. :class:`Origem`
deixa isso auditável resposta a resposta.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from ..corpus.chunking import Chunk
from ..ia.chatbot import ChatbotRAG
from ..ia.generator import Turno
from .base_conhecimento import BaseConhecimento
from .lexico import AnalisadorLexico
from .semantico import AnalisadorSemantico
from .sintatico import AnalisadorSintatico

NAO_ENTENDI = "Não entendi a sua pergunta. Pode reformular?"


class Origem(Enum):
    """De onde veio a resposta — a medida de cobertura do núcleo, resposta a resposta."""

    NUCLEO = auto()          # gramática reconheceu e o Manual respondeu, sem IA
    PLANO_B = auto()         # não reconheceu (ou não achou trecho): respondeu a LLM
    NAO_ENTENDIDA = auto()   # não reconheceu e não há plano B ligado


@dataclass(frozen=True)
class RespostaDialogo:
    pergunta: str
    texto: str                  # o que se mostra ao aluno
    origem: Origem
    trechos: tuple[Chunk, ...]  # trechos consultados (vazio quando não se entendeu)
    fontes: tuple[int, ...] = ()  # ids dos trechos que embasam a resposta
    intencao: str | None = None


class Dialogo:
    """Liga as fases do compilador à base de conhecimento, com o plano B como saída."""

    def __init__(
        self,
        lexico: AnalisadorLexico,
        sintatico: AnalisadorSintatico,
        semantico: AnalisadorSemantico,
        base: BaseConhecimento,
        plano_b: ChatbotRAG | None = None,
    ) -> None:
        self._lexico = lexico
        self._sintatico = sintatico
        self._semantico = semantico
        self._base = base
        self._plano_b = plano_b

    @classmethod
    def de_manual(
        cls,
        base: BaseConhecimento,
        plano_b: ChatbotRAG | None = None,
    ) -> Dialogo:
        """Monta o controlador com o léxico, a gramática e as ações do Manual do Aluno."""
        from .intencoes import GRAMATICA_MANUAL, LEXICO_MANUAL, SEMANTICA_MANUAL

        return cls(
            AnalisadorLexico(LEXICO_MANUAL),
            AnalisadorSintatico(GRAMATICA_MANUAL),
            SEMANTICA_MANUAL,
            base,
            plano_b,
        )

    def responder(
        self, pergunta: str, historico: list[Turno] | None = None
    ) -> RespostaDialogo:
        """Responde pelo núcleo quando a gramática reconhece; senão, recorre ao plano B.

        ``historico`` serve só ao plano B: o núcleo é sem estado por construção, cada intenção se
        resolve na própria frase. Follow-up elíptico não casa regra e cai no plano B com ele.
        """
        reconhecimento = self._sintatico.analisar(self._lexico.analisar(pergunta))
        if reconhecimento is not None:
            resposta = self._base.consultar(self._semantico.analisar(reconhecimento))
            if resposta.encontrou:
                return RespostaDialogo(
                    pergunta=pergunta,
                    texto=resposta.destaque,
                    origem=Origem.NUCLEO,
                    trechos=resposta.trechos,
                    # O destaque sai do 1º trecho: é ele, e só ele, que embasa a resposta.
                    fontes=(resposta.trechos[0].id,),
                    intencao=reconhecimento.intencao,
                )
        return self._recorrer_ao_plano_b(pergunta, historico)

    def _recorrer_ao_plano_b(
        self, pergunta: str, historico: list[Turno] | None
    ) -> RespostaDialogo:
        if self._plano_b is None:
            return RespostaDialogo(pergunta, NAO_ENTENDI, Origem.NAO_ENTENDIDA, ())
        resposta = self._plano_b.responder(pergunta, historico=historico)
        return RespostaDialogo(
            pergunta=pergunta,
            texto=resposta.resposta.texto,
            origem=Origem.PLANO_B,
            trechos=tuple(resposta.contextos),
            fontes=tuple(resposta.resposta.fontes),
        )
