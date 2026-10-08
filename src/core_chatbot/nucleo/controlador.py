"""Controlador: monta o assistente e decide, a cada pergunta, entre o núcleo e o caminho auxiliar.

Reconheceu, responde do Manual; não reconheceu, ou reconheceu e a busca voltou vazia, vai para o
caminho auxiliar. Sem caminho auxiliar, avisa que não entendeu. ``Origem`` registra qual foi.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto

from ..apresentacao import ROTULO, fontes_de
from ..config import Config
from ..corpus import Chunk, indexar_manual
from ..caminho_auxiliar import ChatbotRAG, Turno, montar_plano_b
from ..recuperacao import montar_esparsa, montar_reordenado
from .base_conhecimento import BaseConhecimento
from .fase1_lexica import AnalisadorLexico
from .fase3_semantica import AnalisadorSemantico
from .fase2_sintatica import AnalisadorSintatico

NAO_ENTENDI = "Não entendi a sua pergunta. Pode reformular?"


def _compor(respondidas: list) -> str:
    """Junta as respostas; com mais de uma, rotula cada qual pela sua intenção."""
    if len(respondidas) == 1:
        return respondidas[0][1].destaque
    return "\n\n".join(
        ROTULO.format(reconhecimento.intencao) + resposta.destaque
        for reconhecimento, resposta in respondidas
    )


class Origem(Enum):
    """De onde veio a resposta."""

    NUCLEO = auto()          # a gramática reconheceu e o Manual respondeu, sem modelo
    PLANO_B = auto()         # o caminho auxiliar respondeu ou recusou
    NAO_ENTENDIDA = auto()   # não reconheceu e não há caminho auxiliar


@dataclass(frozen=True)
class RespostaDialogo:
    """O que o controlador decidiu. É o que as medições consomem."""

    pergunta: str
    texto: str
    origem: Origem
    trechos: tuple[Chunk, ...]       # trechos consultados
    fontes: tuple[int, ...] = ()     # ids dos trechos que embasam a resposta
    intencoes: tuple[str, ...] = ()  # na ordem em que foram perguntadas


@dataclass(frozen=True)
class Atendimento:
    """O que a tela mostra: os trechos recortados e o tempo gasto."""

    pergunta: str
    texto: str
    origem: Origem
    intencoes: tuple[str, ...] = ()
    fontes: list[dict] = field(default_factory=list)
    ms: int = 0

    @property
    def sem_ia(self) -> bool:
        return self.origem is Origem.NUCLEO


class Dialogo:
    """Liga as três fases à base de conhecimento, com o caminho auxiliar como saída."""

    @classmethod
    def montar(
        cls, cfg: Config | None = None, com_plano_b: bool = True, saudar: bool = True
    ) -> Dialogo:
        """Do PDF ao assistente pronto. ``com_plano_b=False`` deixa só o núcleo, sem modelo."""
        cfg = cfg or Config()

        # 1. O Manual em trechos, cada um com a sua posição no texto.
        indice = indexar_manual(cfg)

        # 2. O núcleo consulta o Manual só com o BM25.
        esparsa = montar_esparsa(indice, cfg)
        base = BaseConhecimento(esparsa, indice.chunks, cfg.top_k_nucleo)

        # 3. O caminho auxiliar reaproveita o mesmo BM25, com o reordenador por cima.
        plano_b = None
        if com_plano_b:
            plano_b = montar_plano_b(
                montar_reordenado(indice, cfg, base=esparsa), indice, cfg, saudar
            )

        # 4. As três tabelas e as fases do núcleo sobre elas.
        return cls.de_manual(base, plano_b, cfg.max_intencoes)

    @classmethod
    def de_manual(
        cls,
        base: BaseConhecimento,
        plano_b: ChatbotRAG | None = None,
        max_intencoes: int = 3,
    ) -> Dialogo:
        """O controlador com as tabelas do Manual, sobre uma base já montada."""
        from .tabelas_do_manual import GRAMATICA_MANUAL, LEXICO_MANUAL, SEMANTICA_MANUAL

        return cls(
            AnalisadorLexico(LEXICO_MANUAL),
            AnalisadorSintatico(GRAMATICA_MANUAL),
            SEMANTICA_MANUAL,
            base,
            plano_b,
            max_intencoes,
        )

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

    def atender(
        self,
        pergunta: str,
        historico: list[Turno] | None = None,
        n_janela: int = 320,
    ) -> Atendimento:
        """Responde e prepara para a tela. O histórico só serve ao caminho auxiliar."""
        inicio = time.perf_counter()
        resposta = self.responder(pergunta, historico=historico or None)
        return Atendimento(
            pergunta=pergunta,
            texto=resposta.texto,
            origem=resposta.origem,
            intencoes=resposta.intencoes,
            fontes=fontes_de(resposta, n_janela),
            ms=round((time.perf_counter() - inicio) * 1000),
        )

    def responder(
        self, pergunta: str, historico: list[Turno] | None = None
    ) -> RespostaDialogo:
        """Núcleo primeiro; basta uma intenção achar trecho para ele responder."""
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

        # Na ordem em que o aluno perguntou, e sem repetir trecho de duas intenções.
        respondidas.sort(key=lambda par: min(t.inicio for t in par[0].casados))
        trechos: list[Chunk] = []
        for _, resposta in respondidas:
            trechos += [t for t in resposta.trechos if t.id not in {x.id for x in trechos}]

        return RespostaDialogo(
            pergunta=pergunta,
            texto=_compor(respondidas),
            origem=Origem.NUCLEO,
            trechos=tuple(trechos),
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
