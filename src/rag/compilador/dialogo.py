"""Controlador: orquestra as fases e decide quando chamar o plano B.

Único módulo que conhece as quatro fases e a saída de emergência. Reconheceu, responde do
Manual; não reconheceu, ou reconheceu mas a busca voltou vazia, vai para o plano B.

``plano_b`` é opcional de propósito: sem ele o assistente responde o que conhece e diz que não
entendeu o resto, que é a demonstração de que o núcleo é o compilador, e não a LLM.
:class:`Origem` deixa isso auditável resposta a resposta.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from ..corpus import Chunk
from ..ia import ChatbotRAG, Turno
from .base_conhecimento import BaseConhecimento
from .lexico import AnalisadorLexico
from .semantico import AnalisadorSemantico
from .sintatico import AnalisadorSintatico

NAO_ENTENDI = "Não entendi a sua pergunta. Pode reformular?"


def _compor(respondidas: list) -> str:
    """Junta as respostas; havendo mais de uma, rotula cada qual pela sua intenção.

    Com uma só o texto sai limpo, como sempre saiu. O rótulo existe porque duas respostas
    seguidas não dizem sozinhas qual delas responde o quê. Quem exibe tira o rótulo antes
    de procurar o destaque dentro do trecho (``apresentacao._SEM_ROTULO``).
    """
    if len(respondidas) == 1:
        return respondidas[0][1].destaque
    return "\n\n".join(
        f"[{reconhecimento.intencao}] {resposta.destaque}"
        for reconhecimento, resposta in respondidas
    )


class Origem(Enum):
    """De onde veio a resposta: a medida de cobertura do núcleo, resposta a resposta."""

    NUCLEO = auto()          # gramática reconheceu e o Manual respondeu, sem IA
    PLANO_B = auto()         # não reconheceu (ou não achou trecho): respondeu a LLM
    NAO_ENTENDIDA = auto()   # não reconheceu e não há plano B ligado


@dataclass(frozen=True)
class RespostaDialogo:
    pergunta: str
    texto: str                    # o que se mostra ao aluno
    origem: Origem
    trechos: tuple[Chunk, ...]    # trechos consultados (vazio quando não se entendeu)
    fontes: tuple[int, ...] = ()  # ids dos trechos que embasam a resposta
    intencoes: tuple[str, ...] = ()  # uma por pergunta reconhecida, na ordem da frase


class Dialogo:
    """Liga as fases do compilador à base de conhecimento, com o plano B como saída."""

    def __init__(
        self,
        lexico: AnalisadorLexico,
        sintatico: AnalisadorSintatico,
        semantico: AnalisadorSemantico,
        base: BaseConhecimento,
        plano_b: ChatbotRAG | None = None,
        max_intencoes: int = 3,
    ) -> None:
        self._max_intencoes = max_intencoes
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
        max_intencoes: int = 3,
    ) -> Dialogo:
        """Monta o controlador com o léxico, a gramática e as ações do Manual do Aluno."""
        from .intencoes import GRAMATICA_MANUAL, LEXICO_MANUAL, SEMANTICA_MANUAL

        return cls(
            AnalisadorLexico(LEXICO_MANUAL),
            AnalisadorSintatico(GRAMATICA_MANUAL),
            SEMANTICA_MANUAL,
            base,
            plano_b,
            max_intencoes,
        )

    def responder(
        self, pergunta: str, historico: list[Turno] | None = None
    ) -> RespostaDialogo:
        """Responde pelo núcleo quando a gramática reconhece; senão, recorre ao plano B.

        Uma pergunta pode trazer mais de uma intenção; cada uma é consultada no Manual e as
        respostas saem na ordem em que foram perguntadas. Basta uma intenção encontrar trecho
        para o núcleo responder: só cai no plano B quando nenhuma encontra.

        ``historico`` serve só ao plano B: o núcleo é sem estado por construção, cada intenção
        se resolve na própria frase.
        """
        reconhecidas = self._sintatico.analisar_todas(
            self._lexico.analisar(pergunta), self._max_intencoes
        )
        respondidas = [
            (reconhecimento, resposta)
            for reconhecimento in reconhecidas
            for resposta in [self._base.consultar(self._semantico.analisar(reconhecimento))]
            if resposta.encontrou
        ]
        if not respondidas:
            return self._recorrer_ao_plano_b(pergunta, historico)

        # Ordem de leitura, e não de reconhecimento: o aluno lê na ordem em que perguntou.
        respondidas.sort(key=lambda par: min(t.inicio for t in par[0].casados))
        trechos: list[Chunk] = []
        for _, resposta in respondidas:  # sem repetir trecho que duas intenções trouxeram
            trechos += [t for t in resposta.trechos if t.id not in {x.id for x in trechos}]

        return RespostaDialogo(
            pergunta=pergunta,
            texto=_compor(respondidas),
            origem=Origem.NUCLEO,
            trechos=tuple(trechos),
            # O destaque de cada intenção sai do 1º trecho dela: são esses que embasam.
            fontes=tuple(resposta.trechos[0].id for _, resposta in respondidas),
            intencoes=tuple(r.intencao for r, _ in respondidas),
        )

    def _recorrer_ao_plano_b(
        self, pergunta: str, historico: list[Turno] | None
    ) -> RespostaDialogo:
        if self._plano_b is None:
            return RespostaDialogo(pergunta, NAO_ENTENDI, Origem.NAO_ENTENDIDA, ())
        resposta = self._plano_b.responder(pergunta, historico=historico)
        return RespostaDialogo(
            pergunta=pergunta,
            texto=resposta.texto,
            origem=Origem.PLANO_B,
            trechos=tuple(resposta.trechos),
            fontes=tuple(resposta.fontes),
        )
